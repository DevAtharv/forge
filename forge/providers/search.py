from __future__ import annotations

import asyncio
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
