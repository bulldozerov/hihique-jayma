"""Gemini client for structured review responses."""

from typing import TypeVar

from google import genai
from google.genai import errors, types
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
        except errors.APIError as exc:
            raise RuntimeError(f"{stage}: Gemini API HTTP {exc.code}") from exc
        except httpx.RequestError as exc:
            raise RuntimeError(f"{stage}: Gemini API connection failed") from exc

        if not response.output_text:
            raise ValueError(f"{stage}: Gemini returned no text")
        try:
            return schema.model_validate_json(response.output_text)
        except ValidationError as exc:
            raise ValueError(f"{stage}: Gemini returned invalid review JSON") from exc


def open_client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key, http_options=types.HttpOptions(timeout=120_000))
