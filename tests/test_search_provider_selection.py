from forge.bootstrap import _build_search_provider
from forge.config import Settings
from forge.providers import DuckDuckGoSearchProvider, TavilySearchProvider


def _settings(**overrides) -> Settings:
    base = Settings.from_env()
    data = base.__dict__.copy()
    data.update(overrides)
    return Settings(**data)


def test_auto_uses_tavily_when_api_key_present() -> None:
    provider = _build_search_provider(
        _settings(
            tavily_api_key="test-key",
            search_provider="auto",
        )
    )
    assert isinstance(provider, TavilySearchProvider)


def test_explicit_tavily_without_key_falls_back_to_duckduckgo() -> None:
    provider = _build_search_provider(
        _settings(
            tavily_api_key="",
            search_provider="tavily",
        )
    )
    assert isinstance(provider, DuckDuckGoSearchProvider)


def test_explicit_duckduckgo_ignores_tavily_key() -> None:
    provider = _build_search_provider(
        _settings(
            tavily_api_key="test-key",
            search_provider="duckduckgo",
        )
    )
    assert isinstance(provider, DuckDuckGoSearchProvider)
