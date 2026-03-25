from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from forge.schemas import ConversationRecord, MessageJob, UserProfile


class MemoryStore(ABC):
    @abstractmethod
    async def ensure_user_profile(self, user_id: int, username: str | None = None) -> UserProfile:
        raise NotImplementedError

    @abstractmethod
    async def get_user_profile(self, user_id: int) -> UserProfile:
        raise NotImplementedError

    @abstractmethod
    async def get_recent_conversations(self, user_id: int, *, limit: int) -> list[ConversationRecord]:
        raise NotImplementedError

    @abstractmethod
    async def append_conversation(self, record: ConversationRecord) -> ConversationRecord:
        raise NotImplementedError

    @abstractmethod
    async def enqueue_message_job(self, job: MessageJob) -> MessageJob:
        raise NotImplementedError

    @abstractmethod
    async def claim_message_jobs(self, *, worker_id: str, limit: int, lock_timeout_seconds: int) -> list[MessageJob]:
        raise NotImplementedError

    @abstractmethod
    async def update_message_job_pipeline(self, job_id: str, pipeline: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def attach_status_message(self, job_id: str, status_message_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def complete_message_job(self, job_id: str, *, result_preview: str) -> MessageJob:
        raise NotImplementedError

    @abstractmethod
    async def fail_message_job(
        self,
        job_id: str,
        *,
        error: str,
        max_attempts: int,
        retry_delay_seconds: int,
    ) -> MessageJob:
        raise NotImplementedError

    @abstractmethod
    async def update_user_profile(self, user_id: int, updates: dict[str, Any]) -> UserProfile:
        raise NotImplementedError

    async def close(self) -> None:
        return None
