from __future__ import annotations

import asyncio
import json
import re

import httpx
from bs4 import BeautifulSoup
from duckduckgo_search import DDGS

from forge.providers.base import Fetcher, FetchedDocument, SearchHit, SearchProvider


class DuckDuckGoSearchProvider(SearchProvider):
    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        return await asyncio.to_thread(self._search_sync, query, max_results)

    def _search_sync(self, query: str, max_results: int) -> list[SearchHit]:
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        hits: list[SearchHit] = []
        for item in results:
            title = item.get("title") or item.get("heading") or item.get("body") or item.get("href") or "Untitled"
            url = item.get("href") or item.get("url")
            if not url:
                continue
            hits.append(SearchHit(title=title.strip(), url=url.strip(), snippet=(item.get("body") or "").strip()))
        return hits


class TavilySearchProvider(SearchProvider):
    _FRESHNESS_TOKENS = (
        "latest",
        "today",
        "current",
        "right now",
        "breaking",
        "news",
        "price",
        "stock",
        "btc",
        "bitcoin",
        "ethereum",
        "weather",
        "score",
    )

    def __init__(self, *, api_key: str, timeout_seconds: int = 15) -> None:
        self._api_key = api_key.strip()
        self._client = httpx.AsyncClient(
            timeout=timeout_seconds,
            headers={
                "Content-Type": "application/json",
            },
        )

    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        topic = "news" if self._looks_fresh(query) else "general"
        payload = {
            "api_key": self._api_key,
            "query": query,
            "topic": topic,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": False,
            "include_raw_content": False,
        }
        response = await self._client.post("https://api.tavily.com/search", content=json.dumps(payload))
        response.raise_for_status()
        data = response.json()
        hits: list[SearchHit] = []
        for item in data.get("results") or []:
            url = (item.get("url") or "").strip()
            if not url:
                continue
            title = (item.get("title") or item.get("url") or "Untitled").strip()
            snippet = (item.get("content") or "").strip()
            hits.append(SearchHit(title=title, url=url, snippet=snippet))
        return hits

    def _looks_fresh(self, query: str) -> bool:
        lowered = query.lower()
        return any(token in lowered for token in self._FRESHNESS_TOKENS)

    async def close(self) -> None:
        await self._client.aclose()


class HttpPageFetcher(Fetcher):
    def __init__(self, *, timeout_seconds: int = 10) -> None:
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout_seconds,
            headers={"User-Agent": "ForgeBot/1.0 (+https://telegram.org)"},
        )

    async def fetch(self, url: str) -> FetchedDocument | None:
        response = await self._client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        body = response.text
        if "text/html" in content_type or "<html" in body.lower():
            title, content = self._extract_html(body)
        else:
            title, content = url, self._clean_text(body)
        if not content:
            return None
        return FetchedDocument(url=url, title=title or url, content=content[:12000])

    def _extract_html(self, html: str) -> tuple[str, str]:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "svg", "noscript", "footer", "nav", "form"]):
            tag.decompose()
        title = soup.title.string.strip() if soup.title and soup.title.string else "Untitled"
        text = soup.get_text("\n", strip=True)
        return title, self._clean_text(text)

    def _clean_text(self, value: str) -> str:
        value = re.sub(r"\s+", " ", value)
        return value.strip()

    async def close(self) -> None:
        await self._client.aclose()
