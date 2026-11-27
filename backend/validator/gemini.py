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
        self.requests = 0

    def request(self, stage: str, prompt: str, schema: type[Result]) -> Result:
        if self.requests >= 5:
            raise RuntimeError("Gemini request limit exceeded for this review")
        self.requests += 1
        try:
            response = self.client.interactions.create(
                model=self.model,
                input=prompt,
                store=False,
                automatic_continuation=False,
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


def open_client(api_key: str) -> genai.Client:
    client = genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(
            timeout=120_000, retry_options=types.HttpRetryOptions(attempts=0)
        ),
    )
    # Client construction normalizes zero to one. Interactions counts retries
    # after the initial request and reads these options when first accessed.
    client._api_client._http_options.retry_options.attempts = 0
    return client
