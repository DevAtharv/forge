from __future__ import annotations

from typing import Any

from forge.config import ModelRoute
from forge.providers.base import Fetcher, LLMProvider, SearchProvider


class ProviderRegistry:
    def __init__(
        self,
        *,
        llm_providers: dict[str, LLMProvider],
        search_provider: SearchProvider,
        fetcher: Fetcher,
    ) -> None:
        self.llm_providers = llm_providers
        self.search_provider = search_provider
        self.fetcher = fetcher

    async def generate(
        self,
        routes: tuple[ModelRoute, ...],
        *,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        errors: list[str] = []
        for route in routes:
            provider = self.llm_providers.get(route.provider)
            if provider is None:
                errors.append(f"{route.provider}: provider not registered")
                continue
            try:
                return await provider.generate(
                    model=route.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    json_mode=json_mode,
                )
            except Exception as exc:  # pragma: no cover
                errors.append(f"{route.provider}/{route.model}: {exc}")
        raise RuntimeError("All provider routes failed: " + " | ".join(errors))

    async def close(self) -> None:
        for provider in self.llm_providers.values():
            await provider.close()
        await self.fetcher.close()
