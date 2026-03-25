from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SearchHit:
    title: str
    url: str
    snippet: str = ""


@dataclass(frozen=True)
class FetchedDocument:
    url: str
    title: str
    content: str


class LLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        temperature: float,
        max_tokens: int,
        json_mode: bool = False,
    ) -> str:
        raise NotImplementedError

    async def close(self) -> None:
        return None


class SearchProvider(ABC):
    @abstractmethod
    async def search(self, query: str, *, max_results: int) -> list[SearchHit]:
        raise NotImplementedError


class Fetcher(ABC):
    @abstractmethod
    async def fetch(self, url: str) -> FetchedDocument | None:
        raise NotImplementedError

    async def close(self) -> None:
        return None
