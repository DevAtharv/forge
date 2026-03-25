from __future__ import annotations

import asyncio

from forge.config import Settings
from forge.memory import MemoryStore
from forge.workers.processor import JobProcessor


class WorkerService:
    def __init__(self, *, settings: Settings, store: MemoryStore, processor: JobProcessor) -> None:
        self.settings = settings
        self.store = store
        self.processor = processor
        self._stop_event = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is None:
            self._stop_event.clear()
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is not None:
            await self._task
            self._task = None

    async def _run(self) -> None:
        while not self._stop_event.is_set():
            jobs = await self.store.claim_message_jobs(
                worker_id=self.settings.worker_id,
                limit=self.settings.worker_batch_size,
                lock_timeout_seconds=self.settings.worker_lock_timeout_seconds,
            )
            if not jobs:
                await self._sleep()
                continue
            for job in jobs:
                try:
                    await self.processor.process(job)
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    failed = await self.store.fail_message_job(
                        job.id or "",
                        error=str(exc),
                        max_attempts=self.settings.worker_max_attempts,
                        retry_delay_seconds=self.settings.worker_retry_backoff_seconds,
                    )
                    if failed.status == "dead_letter":
                        await self.processor.notify_terminal_failure(failed)

    async def _sleep(self) -> None:
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=self.settings.worker_poll_interval_seconds)
        except TimeoutError:
            return
