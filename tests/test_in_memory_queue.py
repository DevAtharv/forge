from datetime import UTC, datetime, timedelta

import pytest

from forge.schemas import MessageJob


@pytest.mark.asyncio
async def test_in_memory_store_deduplicates_jobs_and_recovers_stale_running_job(store) -> None:
    first = await store.enqueue_message_job(
        MessageJob(telegram_update_id=1, user_id=10, chat_id=20, raw_update={"update_id": 1})
    )
    second = await store.enqueue_message_job(
        MessageJob(telegram_update_id=1, user_id=10, chat_id=20, raw_update={"update_id": 1})
    )

    assert first.id == second.id

    claimed = await store.claim_message_jobs(worker_id="worker-a", limit=1, lock_timeout_seconds=60)
    assert len(claimed) == 1

    store._jobs[first.id].status = "running"
    store._jobs[first.id].locked_at = datetime.now(tz=UTC) - timedelta(seconds=120)

    recovered = await store.claim_message_jobs(worker_id="worker-b", limit=1, lock_timeout_seconds=60)
    assert recovered[0].locked_by == "worker-b"


@pytest.mark.asyncio
async def test_in_memory_store_retries_and_dead_letters(store) -> None:
    job = await store.enqueue_message_job(
        MessageJob(telegram_update_id=2, user_id=10, chat_id=20, raw_update={"update_id": 2})
    )

    failed_once = await store.fail_message_job(job.id, error="boom", max_attempts=2, retry_delay_seconds=1)
    assert failed_once.status == "retrying"
    assert failed_once.attempts == 1

    failed_twice = await store.fail_message_job(job.id, error="boom", max_attempts=2, retry_delay_seconds=1)
    assert failed_twice.status == "dead_letter"
    assert failed_twice.attempts == 2
