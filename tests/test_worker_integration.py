import asyncio
import json

import pytest

from forge.agents.aggregator import PipelineAggregator
from forge.agents.orchestrator import OrchestratorAgent
from forge.agents.task_agents import CodeAgent, DebugAgent, PlannerAgent, ProfileSummaryAgent, ResearchAgent, ReviewerAgent
from forge.builder import HybridProjectBuilder
from forge.integrations import IntegrationService
from forge.missions import MissionRunner
from forge.providers.base import Fetcher, FetchedDocument, SearchHit, SearchProvider
from forge.providers.registry import ProviderRegistry
from forge.schemas import MessageJob
from forge.workers.processor import JobProcessor, PipelineExecutor
from tests.support import FakeTransport


class SequencedProvider:
    def __init__(self, outputs):
        self.outputs = list(outputs)

    async def generate(self, **kwargs):
        if not self.outputs:
            raise RuntimeError("No more fake outputs configured.")
        return self.outputs.pop(0)

    async def close(self):
        return None


class StaticSearch(SearchProvider):
    async def search(self, query: str, *, max_results: int):
        return [SearchHit(title="Example", url="https://example.com", snippet="A source")]


class FailingSearch(SearchProvider):
    async def search(self, query: str, *, max_results: int):
        raise RuntimeError("rate limited")


class StaticFetch(Fetcher):
    async def fetch(self, url: str) -> FetchedDocument | None:
        return FetchedDocument(url=url, title="Example", content="Example content from docs.")

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_worker_processes_code_pipeline_and_updates_memory(settings, store) -> None:
    provider = SequencedProvider(
        [
            "{not-json",
            json.dumps(
                {
                    "summary": "Plan ready",
                    "user_visible_text": "1. Create the route.\n2. Add auth.",
                    "artifacts": [],
                    "handoff": {"plan": "Create route then auth"},
                    "citations": [],
                    "confidence": 0.8,
                    "internal_notes": [],
                }
            ),
            json.dumps(
                {
                    "summary": "Code ready",
                    "user_visible_text": "Implemented the Flask auth route.",
                    "artifacts": [
                        {
                            "name": "app.py",
                            "content": "from flask import Flask\napp = Flask(__name__)\n",
                            "mime_type": "text/plain",
                            "language": "python",
                        }
                    ],
                    "handoff": {"implementation_summary": "Added Flask app"},
                    "citations": [],
                    "confidence": 0.8,
                    "internal_notes": [],
                }
            ),
            json.dumps(
                {
                    "summary": "Review complete",
                    "user_visible_text": "Looks good. Add rate limiting later.",
                    "artifacts": [],
                    "handoff": {"verdict": "good"},
                    "citations": [],
                    "confidence": 0.7,
                    "internal_notes": [],
                }
            ),
            json.dumps(
                {
                    "summary": "Profile updated",
                    "stack": ["Python", "Flask"],
                    "skill_level": "intermediate",
                    "current_projects": ["Telegram dev assistant"],
                    "preferences": {"style": "minimal"},
                    "active_context": {"current_goal": "flask auth"},
                }
            ),
        ]
    )
    providers = ProviderRegistry(
        llm_providers={"fallback": provider},
        search_provider=StaticSearch(),
        fetcher=StaticFetch(),
    )
    transport = FakeTransport()
    integrations = IntegrationService(settings=settings, store=store)
    orchestrator = OrchestratorAgent(settings=settings, providers=providers)
    executor = PipelineExecutor(
        planner=PlannerAgent(settings=settings, providers=providers),
        code=CodeAgent(settings=settings, providers=providers),
        debug=DebugAgent(settings=settings, providers=providers),
        research=ResearchAgent(settings=settings, providers=providers),
        reviewer=ReviewerAgent(settings=settings, providers=providers),
        aggregator=PipelineAggregator(),
    )
    processor = JobProcessor(
        settings=settings,
        store=store,
        transport=transport,
        orchestrator=orchestrator,
        executor=executor,
        profile_summary_agent=ProfileSummaryAgent(settings=settings, providers=providers),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=transport, builder=HybridProjectBuilder()),
    )

    job = await store.enqueue_message_job(
        MessageJob(
            telegram_update_id=1,
            user_id=42,
            chat_id=42,
            raw_update={
                "update_id": 1,
                "message": {
                    "message_id": 1,
                    "from": {"id": 42, "username": "alice"},
                    "chat": {"id": 42, "type": "private"},
                    "text": "add a full flask auth endpoint",
                },
            },
        )
    )

    await processor.process(job)
    await asyncio.sleep(0.05)

    profile = await store.get_user_profile(42)
    assert transport.status_messages
    assert transport.deliveries
    assert profile.stack == ["Python", "Flask"]
    assert len(store._conversations) == 2


@pytest.mark.asyncio
async def test_worker_processes_image_debug_request(settings, store) -> None:
    provider = SequencedProvider(
        [
            "{not-json",
            json.dumps(
                {
                    "summary": "Debugged",
                    "user_visible_text": "Most likely cause: missing env var. Fix: set DATABASE_URL before startup.",
                    "artifacts": [],
                    "handoff": {"root_cause": "missing env var"},
                    "citations": [],
                    "confidence": 0.9,
                    "internal_notes": [],
                }
            ),
            json.dumps(
                {
                    "summary": "Profile updated",
                    "stack": [],
                    "skill_level": "intermediate",
                    "current_projects": ["Debugging a service issue"],
                    "preferences": {},
                    "active_context": {"current_goal": "fix startup error"},
                }
            ),
        ]
    )
    providers = ProviderRegistry(
        llm_providers={"fallback": provider},
        search_provider=StaticSearch(),
        fetcher=StaticFetch(),
    )
    transport = FakeTransport()
    transport.photo_bytes = b"fake-image"
    integrations = IntegrationService(settings=settings, store=store)
    orchestrator = OrchestratorAgent(settings=settings, providers=providers)
    executor = PipelineExecutor(
        planner=PlannerAgent(settings=settings, providers=providers),
        code=CodeAgent(settings=settings, providers=providers),
        debug=DebugAgent(settings=settings, providers=providers),
        research=ResearchAgent(settings=settings, providers=providers),
        reviewer=ReviewerAgent(settings=settings, providers=providers),
        aggregator=PipelineAggregator(),
    )
    processor = JobProcessor(
        settings=settings,
        store=store,
        transport=transport,
        orchestrator=orchestrator,
        executor=executor,
        profile_summary_agent=ProfileSummaryAgent(settings=settings, providers=providers),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=transport, builder=HybridProjectBuilder()),
    )

    job = await store.enqueue_message_job(
        MessageJob(
            telegram_update_id=2,
            user_id=88,
            chat_id=88,
            raw_update={
                "update_id": 2,
                "message": {
                    "message_id": 2,
                    "from": {"id": 88, "username": "bob"},
                    "chat": {"id": 88, "type": "private"},
                    "photo": [{"file_id": "abc", "file_size": 10}],
                },
            },
        )
    )

    await processor.process(job)
    await asyncio.sleep(0.05)

    assert transport.deliveries
    delivered_text = transport.deliveries[0][1].text
    assert "missing env var" in delivered_text.lower()


@pytest.mark.asyncio
async def test_worker_accepts_vercel_token_command(settings, store) -> None:
    providers = ProviderRegistry(
        llm_providers={},
        search_provider=StaticSearch(),
        fetcher=StaticFetch(),
    )
    transport = FakeTransport()
    integrations = IntegrationService(settings=settings, store=store)

    async def fake_connect_vercel_token(*, workspace_user_id: int, token: str):
        from forge.schemas import OAuthConnection

        assert workspace_user_id == 42
        assert token == "vercel-token-123"
        return OAuthConnection(
            workspace_user_id=workspace_user_id,
            provider="vercel",
            account_id="acct_1",
            account_name="atharv",
            access_token_encrypted="encrypted",
        )

    integrations.connect_vercel_token = fake_connect_vercel_token  # type: ignore[method-assign]
    orchestrator = OrchestratorAgent(settings=settings, providers=providers)
    executor = PipelineExecutor(
        planner=PlannerAgent(settings=settings, providers=providers),
        code=CodeAgent(settings=settings, providers=providers),
        debug=DebugAgent(settings=settings, providers=providers),
        research=ResearchAgent(settings=settings, providers=providers),
        reviewer=ReviewerAgent(settings=settings, providers=providers),
        aggregator=PipelineAggregator(),
    )
    processor = JobProcessor(
        settings=settings,
        store=store,
        transport=transport,
        orchestrator=orchestrator,
        executor=executor,
        profile_summary_agent=ProfileSummaryAgent(settings=settings, providers=providers),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=transport, builder=HybridProjectBuilder()),
    )

    job = await store.enqueue_message_job(
        MessageJob(
            telegram_update_id=999,
            user_id=42,
            chat_id=42,
            raw_update={
                "update_id": 999,
                "message": {
                    "message_id": 999,
                    "from": {"id": 42, "username": "alice"},
                    "chat": {"id": 42, "type": "private"},
                    "text": "/vercel vercel-token-123",
                },
            },
        )
    )

    await processor.process(job)

    assert transport.status_messages
    assert "Vercel connected as atharv" in transport.status_messages[-1][1]


@pytest.mark.asyncio
async def test_worker_accepts_plain_telegram_link_code(settings, store) -> None:
    providers = ProviderRegistry(
        llm_providers={"fallback": SequencedProvider([])},
        search_provider=StaticSearch(),
        fetcher=StaticFetch(),
    )
    transport = FakeTransport()
    integrations = IntegrationService(settings=settings, store=store)
    orchestrator = OrchestratorAgent(settings=settings, providers=providers)
    executor = PipelineExecutor(
        planner=PlannerAgent(settings=settings, providers=providers),
        code=CodeAgent(settings=settings, providers=providers),
        debug=DebugAgent(settings=settings, providers=providers),
        research=ResearchAgent(settings=settings, providers=providers),
        reviewer=ReviewerAgent(settings=settings, providers=providers),
        aggregator=PipelineAggregator(),
    )
    processor = JobProcessor(
        settings=settings,
        store=store,
        transport=transport,
        orchestrator=orchestrator,
        executor=executor,
        profile_summary_agent=ProfileSummaryAgent(settings=settings, providers=providers),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=transport, builder=HybridProjectBuilder()),
    )

    token = await store.create_link_token(
        web_user_id="web-user-1",
        workspace_user_id=101,
        web_email="forge@example.com",
    )
    job = await store.enqueue_message_job(
        MessageJob(
            telegram_update_id=3,
            user_id=501,
            chat_id=501,
            raw_update={
                "update_id": 3,
                "message": {
                    "message_id": 3,
                    "from": {"id": 501, "username": "atharv"},
                    "chat": {"id": 501, "type": "private"},
                    "text": token.code,
                },
            },
        )
    )

    await processor.process(job)

    link = await store.get_account_link_for_telegram(501)
    assert link is not None
    assert link.workspace_user_id == 101
    assert transport.status_messages
    assert "connected" in transport.status_messages[-1][1].lower()


@pytest.mark.asyncio
async def test_worker_routes_weather_build_prompt_into_mission(settings, store) -> None:
    providers = ProviderRegistry(
        llm_providers={"fallback": SequencedProvider([])},
        search_provider=StaticSearch(),
        fetcher=StaticFetch(),
    )
    transport = FakeTransport()
    integrations = IntegrationService(settings=settings, store=store)
    orchestrator = OrchestratorAgent(settings=settings, providers=providers)
    executor = PipelineExecutor(
        planner=PlannerAgent(settings=settings, providers=providers),
        code=CodeAgent(settings=settings, providers=providers),
        debug=DebugAgent(settings=settings, providers=providers),
        research=ResearchAgent(settings=settings, providers=providers),
        reviewer=ReviewerAgent(settings=settings, providers=providers),
        aggregator=PipelineAggregator(),
    )
    processor = JobProcessor(
        settings=settings,
        store=store,
        transport=transport,
        orchestrator=orchestrator,
        executor=executor,
        profile_summary_agent=ProfileSummaryAgent(settings=settings, providers=providers),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=transport, builder=HybridProjectBuilder()),
    )

    job = await store.enqueue_message_job(
        MessageJob(
            telegram_update_id=4,
            user_id=610,
            chat_id=610,
            raw_update={
                "update_id": 4,
                "message": {
                    "message_id": 4,
                    "from": {"id": 610, "username": "atharv"},
                    "chat": {"id": 610, "type": "private"},
                    "text": "Build a weather app",
                },
            },
        )
    )

    await processor.process(job)

    missions = await store.list_missions(610, limit=10)
    assert missions
    assert missions[0].kind == "build"
    assert transport.status_messages
    assert "website and preview" in transport.status_messages[0][1].lower()
    assert transport.deliveries
    payload = transport.deliveries[0][1]
    assert payload.document_name is not None
    assert payload.document_bytes is not None


@pytest.mark.asyncio
async def test_research_agent_falls_back_when_search_is_unavailable(settings, store) -> None:
    provider = SequencedProvider(
        [
            "{not-json",
            json.dumps(
                {
                    "summary": "Model-only answer",
                    "user_visible_text": "Redis is an in-memory data store used for caching, queues, and fast lookups.",
                    "artifacts": [],
                    "handoff": {"mode": "model-only"},
                    "citations": [],
                    "confidence": 0.62,
                    "internal_notes": [],
                }
            ),
            json.dumps(
                {
                    "summary": "Profile updated",
                    "stack": [],
                    "skill_level": "intermediate",
                    "current_projects": [],
                    "preferences": {},
                    "active_context": {},
                }
            ),
        ]
    )
    providers = ProviderRegistry(
        llm_providers={"fallback": provider},
        search_provider=FailingSearch(),
        fetcher=StaticFetch(),
    )
    transport = FakeTransport()
    integrations = IntegrationService(settings=settings, store=store)
    orchestrator = OrchestratorAgent(settings=settings, providers=providers)
    executor = PipelineExecutor(
        planner=PlannerAgent(settings=settings, providers=providers),
        code=CodeAgent(settings=settings, providers=providers),
        debug=DebugAgent(settings=settings, providers=providers),
        research=ResearchAgent(settings=settings, providers=providers),
        reviewer=ReviewerAgent(settings=settings, providers=providers),
        aggregator=PipelineAggregator(),
    )
    processor = JobProcessor(
        settings=settings,
        store=store,
        transport=transport,
        orchestrator=orchestrator,
        executor=executor,
        profile_summary_agent=ProfileSummaryAgent(settings=settings, providers=providers),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=transport, builder=HybridProjectBuilder()),
    )

    job = await store.enqueue_message_job(
        MessageJob(
            telegram_update_id=3,
            user_id=77,
            chat_id=77,
            raw_update={
                "update_id": 3,
                "message": {
                    "message_id": 3,
                    "from": {"id": 77, "username": "carol"},
                    "chat": {"id": 77, "type": "private"},
                    "text": "what is redis and when should i use it",
                },
            },
        )
    )

    await processor.process(job)
    await asyncio.sleep(0.05)

    assert transport.deliveries
    delivered_text = transport.deliveries[0][1].text.lower()
    assert "redis" in delivered_text


@pytest.mark.asyncio
async def test_worker_consumes_telegram_link_code_before_pipeline(settings, store) -> None:
    token = await store.create_link_token(
        web_user_id="web-user-1",
        workspace_user_id=-41,
        web_email="demo@forge.dev",
        expires_in_seconds=600,
    )
    providers = ProviderRegistry(
        llm_providers={"fallback": SequencedProvider([])},
        search_provider=StaticSearch(),
        fetcher=StaticFetch(),
    )
    transport = FakeTransport()
    integrations = IntegrationService(settings=settings, store=store)
    orchestrator = OrchestratorAgent(settings=settings, providers=providers)
    executor = PipelineExecutor(
        planner=PlannerAgent(settings=settings, providers=providers),
        code=CodeAgent(settings=settings, providers=providers),
        debug=DebugAgent(settings=settings, providers=providers),
        research=ResearchAgent(settings=settings, providers=providers),
        reviewer=ReviewerAgent(settings=settings, providers=providers),
        aggregator=PipelineAggregator(),
    )
    processor = JobProcessor(
        settings=settings,
        store=store,
        transport=transport,
        orchestrator=orchestrator,
        executor=executor,
        profile_summary_agent=ProfileSummaryAgent(settings=settings, providers=providers),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=transport, builder=HybridProjectBuilder()),
    )

    job = await store.enqueue_message_job(
        MessageJob(
            telegram_update_id=4,
            user_id=501,
            chat_id=501,
            raw_update={
                "update_id": 4,
                "message": {
                    "message_id": 4,
                    "from": {"id": 501, "username": "tele-user"},
                    "chat": {"id": 501, "type": "private"},
                    "text": f"/link {token.code}",
                },
            },
        )
    )

    await processor.process(job)

    link = await store.get_account_link_for_telegram(501)
    assert link is not None
    assert link.workspace_user_id == -41
    assert transport.status_messages
    assert "connected" in transport.status_messages[0][1].lower()
