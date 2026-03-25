from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from forge.memory.base import MemoryStore
from forge.schemas import ConversationRecord, MessageJob, UserProfile


class InMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._profiles: dict[int, UserProfile] = {}
        self._conversations: list[ConversationRecord] = []
        self._jobs: dict[str, MessageJob] = {}
        self._job_ids_by_update: dict[int, str] = {}
        self._lock = asyncio.Lock()

    async def ensure_user_profile(self, user_id: int, username: str | None = None) -> UserProfile:
        async with self._lock:
            profile = self._profiles.get(user_id)
            if profile is None:
                profile = UserProfile(user_id=user_id, username=username)
                self._profiles[user_id] = profile
            elif username and profile.username != username:
                profile.username = username
            return profile.model_copy(deep=True)

    async def get_user_profile(self, user_id: int) -> UserProfile:
        profile = self._profiles.get(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self._profiles[user_id] = profile
        return profile.model_copy(deep=True)

    async def get_recent_conversations(self, user_id: int, *, limit: int) -> list[ConversationRecord]:
        records = [record for record in self._conversations if record.user_id == user_id]
        return [item.model_copy(deep=True) for item in records[-limit:]]

    async def append_conversation(self, record: ConversationRecord) -> ConversationRecord:
        stored = record.model_copy(deep=True)
        stored.id = stored.id or str(uuid4())
        stored.created_at = stored.created_at or datetime.now(tz=UTC)
        self._conversations.append(stored)
        profile = self._profiles.get(record.user_id)
        if profile is not None:
            profile.message_count += 1
            profile.last_seen = datetime.now(tz=UTC)
        return stored.model_copy(deep=True)

    async def enqueue_message_job(self, job: MessageJob) -> MessageJob:
        async with self._lock:
            existing_id = self._job_ids_by_update.get(job.telegram_update_id)
            if existing_id:
                return self._jobs[existing_id].model_copy(deep=True)
            stored = job.model_copy(deep=True)
            stored.id = stored.id or str(uuid4())
            stored.status = "queued"
            stored.created_at = stored.created_at or datetime.now(tz=UTC)
            stored.updated_at = stored.created_at
            self._jobs[stored.id] = stored
            self._job_ids_by_update[stored.telegram_update_id] = stored.id
            return stored.model_copy(deep=True)

    async def claim_message_jobs(self, *, worker_id: str, limit: int, lock_timeout_seconds: int) -> list[MessageJob]:
        now = datetime.now(tz=UTC)
        claimed: list[MessageJob] = []
        async with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at or now)
            for job in jobs:
                available = job.available_at or datetime.min.replace(tzinfo=UTC)
                stale_lock = job.status == "running" and job.locked_at and job.locked_at < now - timedelta(seconds=lock_timeout_seconds)
                claimable = (job.status in {"queued", "retrying"} and available <= now) or stale_lock
                if not claimable:
                    continue
                job.status = "running"
                job.locked_by = worker_id
                job.locked_at = now
                job.updated_at = now
                claimed.append(job.model_copy(deep=True))
                if len(claimed) >= limit:
                    break
        return claimed

    async def update_message_job_pipeline(self, job_id: str, pipeline: dict[str, Any]) -> None:
        job = self._jobs[job_id]
        job.pipeline = pipeline
        job.updated_at = datetime.now(tz=UTC)

    async def attach_status_message(self, job_id: str, status_message_id: int) -> None:
        job = self._jobs[job_id]
        job.status_message_id = status_message_id
        job.updated_at = datetime.now(tz=UTC)

    async def complete_message_job(self, job_id: str, *, result_preview: str) -> MessageJob:
        job = self._jobs[job_id]
        job.status = "completed"
        job.result_preview = result_preview
        job.locked_at = None
        job.locked_by = None
        job.error = None
        job.updated_at = datetime.now(tz=UTC)
        return job.model_copy(deep=True)

    async def fail_message_job(
        self,
        job_id: str,
        *,
        error: str,
        max_attempts: int,
        retry_delay_seconds: int,
    ) -> MessageJob:
        job = self._jobs[job_id]
        job.attempts += 1
        job.error = error
        job.locked_at = None
        job.locked_by = None
        if job.attempts >= max_attempts:
            job.status = "dead_letter"
            job.available_at = None
        else:
            job.status = "retrying"
            job.available_at = datetime.now(tz=UTC) + timedelta(seconds=retry_delay_seconds * job.attempts)
        job.updated_at = datetime.now(tz=UTC)
        return job.model_copy(deep=True)

    async def update_user_profile(self, user_id: int, updates: dict[str, Any]) -> UserProfile:
        profile = self._profiles.get(user_id) or UserProfile(user_id=user_id)
        merged = profile.model_dump()
        for key, value in updates.items():
            if value is None:
                continue
            merged[key] = value
        updated = UserProfile.model_validate(merged)
        updated.last_context_refresh = datetime.now(tz=UTC)
        self._profiles[user_id] = updated
        return updated.model_copy(deep=True)
