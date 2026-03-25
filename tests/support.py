from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class FakeTransport:
    def __init__(self) -> None:
        self.status_messages: list[tuple[int, str]] = []
        self.edits: list[tuple[int, int, str]] = []
        self.deliveries: list[tuple[int, Any, int | None]] = []
        self.photo_bytes: bytes | None = None
        self._counter = 100

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def send_status_message(self, chat_id: int, text: str) -> int:
        self._counter += 1
        self.status_messages.append((chat_id, text))
        return self._counter

    async def edit_status_message(self, chat_id: int, message_id: int, text: str) -> None:
        self.edits.append((chat_id, message_id, text))

    async def deliver(self, chat_id: int, payload, *, status_message_id: int | None = None) -> None:
        self.deliveries.append((chat_id, payload, status_message_id))

    async def download_photo(self, photo_sizes: list[dict[str, Any]]) -> bytes | None:
        return self.photo_bytes


@dataclass
class NoopWorker:
    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


@dataclass
class ProcessorWorker:
    processor: object

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None


class FakeAuthClient:
    def __init__(self, *, configured: bool = True) -> None:
        self.is_configured = configured
        self.calls: list[tuple[str, str]] = []

    async def sign_up(self, *, email: str, password: str) -> dict:
        self.calls.append(("signup", email))
        return {
            "user": {"id": "user-1", "email": email},
            "session": {"access_token": "token-1", "refresh_token": "refresh-1"},
        }

    async def sign_in(self, *, email: str, password: str) -> dict:
        self.calls.append(("signin", email))
        return {
            "user": {"id": "user-1", "email": email},
            "access_token": "token-1",
            "refresh_token": "refresh-1",
            "expires_in": 3600,
            "token_type": "bearer",
        }

    async def get_user(self, *, access_token: str) -> dict:
        self.calls.append(("session", access_token))
        return {"id": "user-1", "email": "demo@forge.dev"}

    async def sign_out(self, *, access_token: str) -> dict:
        self.calls.append(("signout", access_token))
        return {"ok": True}

    async def close(self) -> None:
        return None
