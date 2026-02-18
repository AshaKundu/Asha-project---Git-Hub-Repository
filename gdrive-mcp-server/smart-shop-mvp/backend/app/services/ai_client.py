from __future__ import annotations

import os
from typing import List, Optional, Type

from openai import OpenAI
from pydantic import BaseModel

DEFAULT_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class OpenAIClient:
    def __init__(self) -> None:
        self._client = OpenAI()

    def parse(self, model: str, messages: List[dict], response_model: Type[BaseModel]):
        response = self._client.beta.chat.completions.parse(
            model=model,
            messages=messages,
            response_format=response_model,
            temperature=0.2,
        )
        return response.choices[0].message.parsed

    def create(self, model: str, messages: List[dict]):
        response = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=0.4,
        )
        return response.choices[0].message.content


def is_configured() -> bool:
    return bool(os.getenv("OPENAI_API_KEY"))


_client: Optional[OpenAIClient] = None


def get_client() -> Optional[OpenAIClient]:
    global _client
    if not is_configured():
        return None
    if _client is None:
        _client = OpenAIClient()
    return _client
