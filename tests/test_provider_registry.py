import pytest

from forge.config import ModelRoute
from forge.providers.base import Fetcher, FetchedDocument, SearchProvider
from forge.providers.registry import ProviderRegistry


class FailingProvider:
    async def generate(self, **kwargs):
        raise RuntimeError("primary down")

    async def close(self):
        return None


class WorkingProvider:
    async def generate(self, **kwargs):
        return "ok"

    async def close(self):
        return None


class NoopSearch(SearchProvider):
    async def search(self, query: str, *, max_results: int):
        return []


class NoopFetch(Fetcher):
    async def fetch(self, url: str) -> FetchedDocument | None:
        return None

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_provider_registry_uses_fallback_route() -> None:
    registry = ProviderRegistry(
        llm_providers={"primary": FailingProvider(), "backup": WorkingProvider()},
        search_provider=NoopSearch(),
        fetcher=NoopFetch(),
    )

    result = await registry.generate(
        (ModelRoute("primary", "model-a"), ModelRoute("backup", "model-b")),
        messages=[{"role": "user", "content": "hi"}],
        temperature=0.1,
        max_tokens=10,
    )

    assert result == "ok"
