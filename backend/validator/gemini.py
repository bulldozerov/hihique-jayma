"""Gemini client for structured review responses."""

from typing import TypeVar

from google import genai
from google.genai import errors, types
from google.genai._gaos.lib.compat_errors import APIConnectionError, APIStatusError
import httpx
from pydantic import BaseModel, ValidationError

Result = TypeVar("Result", bound=BaseModel)


class GeminiReviewer:
    def __init__(self, client: genai.Client, model: str) -> None:
        self.client = client
        self.model = model

    def request(self, stage: str, prompt: str, schema: type[Result]) -> Result:
        try:
            response = self.client.interactions.create(
                model=self.model,
                input=prompt,
                store=False,
                response_format={
                    "type": "text",
                    "mime_type": "application/json",
                    "schema": schema.model_json_schema(),
                },
            )
        except (errors.APIError, APIStatusError) as exc:
            status = exc.status_code if isinstance(exc, APIStatusError) else exc.code
            message = f"{stage}: Gemini API HTTP {status} ({self.model})"
            if status == 503:
                message += ". Модель временно недоступна. Повторите запуск позже."
            raise RuntimeError(message) from exc
        except (APIConnectionError, httpx.RequestError) as exc:
            raise RuntimeError(f"{stage}: Gemini API connection failed") from exc

        if not response.output_text:
            raise ValueError(f"{stage}: Gemini returned no text")
        try:
            return schema.model_validate_json(response.output_text)
        except ValidationError as exc:
            raise ValueError(f"{stage}: Gemini returned invalid review JSON") from exc


def open_client(api_key: str, *, retries: bool = True) -> genai.Client:
    retry_options = types.HttpRetryOptions(
        attempts=4 if retries else 1,
        initial_delay=2,
        max_delay=8,
        jitter=1,
        http_status_codes=[408, 429, 500, 502, 503, 504],
    )
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(timeout=120_000, retry_options=retry_options),
    )
