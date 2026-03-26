from __future__ import annotations

import pytest

from forge.memory import InMemoryStore
from forge.memory.base import MemoryStore
from forge.memory.resilient import ResilientMemoryStore
from forge.schemas import ConversationRecord, MessageJob


class BrokenStore(MemoryStore):
    async def ensure_user_profile(self, user_id: int, username: str | None = None):
        raise RuntimeError("broken store")

    async def get_user_profile(self, user_id: int):
        raise RuntimeError("broken store")

    async def get_recent_conversations(self, user_id: int, *, limit: int):
        raise RuntimeError("broken store")

    async def append_conversation(self, record: ConversationRecord):
        raise RuntimeError("broken store")

    async def enqueue_message_job(self, job: MessageJob):
        raise RuntimeError("broken store")

    async def claim_message_jobs(self, *, worker_id: str, limit: int, lock_timeout_seconds: int):
        raise RuntimeError("broken store")

    async def update_message_job_pipeline(self, job_id: str, pipeline: dict):
        raise RuntimeError("broken store")

    async def attach_status_message(self, job_id: str, status_message_id: int):
        raise RuntimeError("broken store")

    async def complete_message_job(self, job_id: str, *, result_preview: str):
        raise RuntimeError("broken store")

    async def fail_message_job(self, job_id: str, *, error: str, max_attempts: int, retry_delay_seconds: int):
        raise RuntimeError("broken store")

    async def update_user_profile(self, user_id: int, updates: dict):
        raise RuntimeError("broken store")

    async def get_account_link_for_web(self, web_user_id: str):
        raise RuntimeError("broken store")

    async def get_account_link_for_telegram(self, telegram_user_id: int):
        raise RuntimeError("broken store")

    async def create_link_token(self, *, web_user_id: str, workspace_user_id: int, web_email: str | None, expires_in_seconds: int):
        raise RuntimeError("broken store")

    async def get_active_link_token(self, web_user_id: str):
        raise RuntimeError("broken store")

    async def consume_link_token(self, *, code: str, telegram_user_id: int, telegram_username: str | None):
        raise RuntimeError("broken store")


@pytest.mark.asyncio
async def test_resilient_store_falls_back_for_conversations_and_profiles() -> None:
    fallback = InMemoryStore()
    store = ResilientMemoryStore(primary=BrokenStore(), fallback=fallback)

    profile = await store.ensure_user_profile(7, "alice")
    record = await store.append_conversation(ConversationRecord(user_id=7, role="user", content="hello"))
    history = await store.get_recent_conversations(7, limit=5)

    assert profile.username == "alice"
    assert record.content == "hello"
    assert len(history) == 1


@pytest.mark.asyncio
async def test_resilient_store_falls_back_for_queue_lifecycle() -> None:
    fallback = InMemoryStore()
    store = ResilientMemoryStore(primary=BrokenStore(), fallback=fallback)

    job = await store.enqueue_message_job(
        MessageJob(telegram_update_id=10, user_id=7, chat_id=7, raw_update={"update_id": 10})
    )
    claimed = await store.claim_message_jobs(worker_id="worker-1", limit=1, lock_timeout_seconds=60)
    await store.attach_status_message(job.id or "", 101)
    await store.update_message_job_pipeline(job.id or "", {"intent": "test"})
    completed = await store.complete_message_job(job.id or "", result_preview="done")

    assert claimed[0].telegram_update_id == 10
    assert completed.status == "completed"
