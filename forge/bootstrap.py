from __future__ import annotations

from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from forge.agents import PipelineAggregator
from forge.agents.orchestrator import OrchestratorAgent
from forge.agents.task_agents import CodeAgent, DebugAgent, PlannerAgent, ProfileSummaryAgent, ResearchAgent, ReviewerAgent
from forge.api import build_router
from forge.config import Settings
from forge.memory import InMemoryStore, SupabaseMemoryStore
from forge.providers import DuckDuckGoSearchProvider, GroqProvider, HttpPageFetcher, OpenAICompatibleProvider, ProviderRegistry
from forge.supabase_auth import SupabaseAuthClient
from forge.telegram import TelegramTransport
from forge.workers import JobProcessor, PipelineExecutor, WorkerService


@dataclass
class ForgeContainer:
    settings: Settings
    store: object
    providers: ProviderRegistry
    transport: TelegramTransport
    worker: WorkerService

    async def start(self) -> None:
        await self.transport.start()
        await self.worker.start()

    async def stop(self) -> None:
        await self.worker.stop()
        await self.transport.close()
        await self.providers.close()
        await self.store.close()


def build_container(settings: Settings | None = None) -> ForgeContainer:
    settings = settings or Settings.from_env()
    if settings.supabase_url and settings.supabase_key:
        store = SupabaseMemoryStore(
            url=settings.supabase_url,
            key=settings.supabase_key,
            timeout_seconds=settings.fetch_timeout_seconds,
        )
    else:
        store = InMemoryStore()
    providers = ProviderRegistry(
        llm_providers={
            "groq": GroqProvider(settings.groq_api_key),
            "nvidia": OpenAICompatibleProvider(
                base_url="https://integrate.api.nvidia.com/v1",
                api_key=settings.nvidia_api_key,
            ),
            "openrouter": OpenAICompatibleProvider(
                base_url="https://openrouter.ai/api/v1",
                api_key=settings.openrouter_api_key,
                default_headers={
                    "HTTP-Referer": "https://forge.local",
                    "X-Title": "Forge",
                },
            ),
        },
        search_provider=DuckDuckGoSearchProvider(),
        fetcher=HttpPageFetcher(timeout_seconds=settings.fetch_timeout_seconds),
    )

    transport = TelegramTransport(settings.telegram_token)
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
    )
    worker = WorkerService(settings=settings, store=store, processor=processor)
    return ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        transport=transport,
        worker=worker,
    )


def create_app(container: ForgeContainer | None = None) -> FastAPI:
    container = container or build_container()
    auth_client = SupabaseAuthClient(
        url=container.settings.supabase_url,
        api_key=container.settings.supabase_anon_key,
        timeout_seconds=container.settings.fetch_timeout_seconds,
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await container.start()
        yield
        await container.stop()
        await auth_client.close()

    app = FastAPI(title="Forge", lifespan=lifespan)
    if container.settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=list(container.settings.cors_allowed_origins),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    app.state.container = container
    app.state.auth_client = auth_client
    app.state.settings = container.settings
    app.state.store = container.store
    app.state.orchestrator = (
        container.worker.processor.orchestrator
        if hasattr(container.worker, "processor")
        else OrchestratorAgent(settings=container.settings, providers=container.providers)
    )
    app.state.executor = container.worker.processor.executor if hasattr(container.worker, "processor") else None
    app.state.profile_refresher = (
        container.worker.processor.refresh_profile
        if hasattr(container.worker, "processor")
        else None
    )
    app.include_router(build_router(settings=container.settings, store=container.store))
    return app
