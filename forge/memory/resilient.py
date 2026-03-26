from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, TypeVar

from forge.memory.base import MemoryStore
from forge.schemas import ConversationRecord, MessageJob, UserProfile

T = TypeVar("T")

logger = logging.getLogger(__name__)


class ResilientMemoryStore(MemoryStore):
    def __init__(self, *, primary: MemoryStore, fallback: MemoryStore) -> None:
        self._primary = primary
        self._fallback = fallback

    async def _call_with_fallback(
        self,
        action: str,
        primary_call: Callable[[], Awaitable[T]],
        fallback_call: Callable[[], Awaitable[T]],
    ) -> T:
        try:
            return await primary_call()
        except Exception as exc:
            logger.warning("Primary memory store failed during %s; using fallback store: %s", action, exc)
            return await fallback_call()

    async def ensure_user_profile(self, user_id: int, username: str | None = None) -> UserProfile:
        return await self._call_with_fallback(
            "ensure_user_profile",
            lambda: self._primary.ensure_user_profile(user_id, username),
            lambda: self._fallback.ensure_user_profile(user_id, username),
        )

    async def get_user_profile(self, user_id: int) -> UserProfile:
        return await self._call_with_fallback(
            "get_user_profile",
            lambda: self._primary.get_user_profile(user_id),
            lambda: self._fallback.get_user_profile(user_id),
        )

    async def get_recent_conversations(self, user_id: int, *, limit: int) -> list[ConversationRecord]:
        return await self._call_with_fallback(
            "get_recent_conversations",
            lambda: self._primary.get_recent_conversations(user_id, limit=limit),
            lambda: self._fallback.get_recent_conversations(user_id, limit=limit),
        )

    async def append_conversation(self, record: ConversationRecord) -> ConversationRecord:
        return await self._call_with_fallback(
            "append_conversation",
            lambda: self._primary.append_conversation(record),
            lambda: self._fallback.append_conversation(record),
        )

    async def enqueue_message_job(self, job: MessageJob) -> MessageJob:
        return await self._call_with_fallback(
            "enqueue_message_job",
            lambda: self._primary.enqueue_message_job(job),
            lambda: self._fallback.enqueue_message_job(job),
        )

    async def claim_message_jobs(self, *, worker_id: str, limit: int, lock_timeout_seconds: int) -> list[MessageJob]:
        return await self._call_with_fallback(
            "claim_message_jobs",
            lambda: self._primary.claim_message_jobs(
                worker_id=worker_id,
                limit=limit,
                lock_timeout_seconds=lock_timeout_seconds,
            ),
            lambda: self._fallback.claim_message_jobs(
                worker_id=worker_id,
                limit=limit,
                lock_timeout_seconds=lock_timeout_seconds,
            ),
        )

    async def update_message_job_pipeline(self, job_id: str, pipeline: dict[str, Any]) -> None:
        await self._call_with_fallback(
            "update_message_job_pipeline",
            lambda: self._primary.update_message_job_pipeline(job_id, pipeline),
            lambda: self._fallback.update_message_job_pipeline(job_id, pipeline),
        )

    async def attach_status_message(self, job_id: str, status_message_id: int) -> None:
        await self._call_with_fallback(
            "attach_status_message",
            lambda: self._primary.attach_status_message(job_id, status_message_id),
            lambda: self._fallback.attach_status_message(job_id, status_message_id),
        )

    async def complete_message_job(self, job_id: str, *, result_preview: str) -> MessageJob:
        return await self._call_with_fallback(
            "complete_message_job",
            lambda: self._primary.complete_message_job(job_id, result_preview=result_preview),
            lambda: self._fallback.complete_message_job(job_id, result_preview=result_preview),
        )

    async def fail_message_job(
        self,
        job_id: str,
        *,
        error: str,
        max_attempts: int,
        retry_delay_seconds: int,
    ) -> MessageJob:
        return await self._call_with_fallback(
            "fail_message_job",
            lambda: self._primary.fail_message_job(
                job_id,
                error=error,
                max_attempts=max_attempts,
                retry_delay_seconds=retry_delay_seconds,
            ),
            lambda: self._fallback.fail_message_job(
                job_id,
                error=error,
                max_attempts=max_attempts,
                retry_delay_seconds=retry_delay_seconds,
            ),
        )

    async def update_user_profile(self, user_id: int, updates: dict[str, Any]) -> UserProfile:
        return await self._call_with_fallback(
            "update_user_profile",
            lambda: self._primary.update_user_profile(user_id, updates),
            lambda: self._fallback.update_user_profile(user_id, updates),
        )

    async def close(self) -> None:
        try:
            await self._primary.close()
        finally:
            await self._fallback.close()
