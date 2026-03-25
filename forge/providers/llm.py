from __future__ import annotations

from typing import Any

from groq import AsyncGroq
from openai import AsyncOpenAI

from forge.providers.base import LLMProvider


class ProviderExecutionError(RuntimeError):
    """Raised when a provider cannot fulfill a request."""


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str) -> None:
        self._client = AsyncGroq(api_key=api_key) if api_key else None

    async def generate(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        if self._client is None:
            raise ProviderExecutionError("Groq API key is not configured.")

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return content if isinstance(content, str) else str(content)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()


class OpenAICompatibleProvider(LLMProvider):
    def __init__(self, *, base_url: str, api_key: str, default_headers: dict[str, str] | None = None) -> None:
        self._client = (
            AsyncOpenAI(base_url=base_url, api_key=api_key, default_headers=default_headers or {})
            if api_key
            else None
        )

    async def generate(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        if self._client is None:
            raise ProviderExecutionError("Provider API key is not configured.")

        kwargs: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        response = await self._client.chat.completions.create(**kwargs)
        content = response.choices[0].message.content
        return content if isinstance(content, str) else str(content)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
