from __future__ import annotations

import pytest

from forge.config import ModelRoute, Settings
from forge.memory.in_memory import InMemoryStore


@pytest.fixture
def settings() -> Settings:
    fallback = (ModelRoute("fallback", "model"),)
    return Settings(
        app_env="test",
        telegram_token="token",
        webhook_secret="secret",
        groq_api_key="groq",
        nvidia_api_key="nvidia",
        openrouter_api_key="openrouter",
        supabase_url="https://example.supabase.co",
        supabase_key="supabase-key",
        supabase_anon_key="supabase-anon-key",
        worker_id="test-worker",
        worker_poll_interval_seconds=0.01,
        worker_batch_size=1,
        worker_lock_timeout_seconds=60,
        worker_retry_backoff_seconds=1,
        worker_max_attempts=2,
        history_window=8,
        search_result_limit=3,
        fetch_timeout_seconds=5,
        cors_allowed_origins=(),
        orchestrator_routes=fallback,
        planner_routes=fallback,
        code_routes=fallback,
        debug_routes=fallback,
        reviewer_routes=fallback,
        research_routes=fallback,
        summary_routes=fallback,
    )


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()
