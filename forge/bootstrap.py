from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from forge.agents import PipelineAggregator
from forge.agents.orchestrator import OrchestratorAgent
from forge.agents.task_agents import CodeAgent, DebugAgent, PlannerAgent, ProfileSummaryAgent, ResearchAgent, ReviewerAgent
from forge.api import build_router
from forge.builder import HybridProjectBuilder
from forge.config import Settings
from forge.figma import FigmaTemplateService
from forge.integrations import IntegrationService
from forge.memory import InMemoryStore, ResilientMemoryStore, SupabaseMemoryStore
from forge.missions import MissionRunner
from forge.providers import (
    DuckDuckGoSearchProvider,
    GroqProvider,
    HttpPageFetcher,
    OpenAICompatibleProvider,
    ProviderRegistry,
    RotatingOpenAIProvider,
    TavilySearchProvider,
)
from forge.supabase_auth import SupabaseAuthClient
from forge.telegram import TelegramTransport
from forge.workers import JobProcessor, PipelineExecutor, WorkerService

logger = logging.getLogger(__name__)


def _build_search_provider(settings: Settings):
    provider_name = settings.search_provider.strip().lower()
    if provider_name in {"auto", "tavily"} and settings.tavily_api_key:
        return TavilySearchProvider(
            api_key=settings.tavily_api_key,
            timeout_seconds=settings.fetch_timeout_seconds,
        )
    if provider_name == "tavily":
        logger.warning("FORGE_SEARCH_PROVIDER is set to tavily but TAVILY_API_KEY is missing; falling back to DuckDuckGo.")
    return DuckDuckGoSearchProvider()


@dataclass
class ForgeContainer:
    settings: Settings
    store: object
    providers: ProviderRegistry
    integrations: IntegrationService
    transport: TelegramTransport
    mission_runner: MissionRunner
    worker: WorkerService
    figma: FigmaTemplateService | None = None

    async def start(self) -> None:
        try:
            await self.transport.start()
        except Exception:
            logger.exception("Telegram transport failed to start; continuing without Telegram delivery.")
        try:
            await self.worker.start()
        except Exception:
            logger.exception("Forge worker failed to start; continuing with web APIs only.")

    async def stop(self) -> None:
        try:
            await self.worker.stop()
        except Exception:
            logger.exception("Forge worker failed to stop cleanly.")
        try:
            await self.transport.close()
        except Exception:
            logger.exception("Telegram transport failed to close cleanly.")
        try:
            await self.providers.close()
        except Exception:
            logger.exception("Providers failed to close cleanly.")
        try:
            await self.integrations.close()
        except Exception:
            logger.exception("Integrations failed to close cleanly.")
        try:
            await self.store.close()
        except Exception:
            logger.exception("Memory store failed to close cleanly.")


def build_container(settings: Settings | None = None) -> ForgeContainer:
    settings = settings or Settings.from_env()
    if settings.supabase_url and settings.supabase_key:
        store = ResilientMemoryStore(
            primary=SupabaseMemoryStore(
                url=settings.supabase_url,
                key=settings.supabase_key,
                timeout_seconds=settings.fetch_timeout_seconds,
            ),
            fallback=InMemoryStore(),
        )
    else:
        store = InMemoryStore()
    providers = ProviderRegistry(
        llm_providers={
            "gemini": RotatingOpenAIProvider(
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                api_keys=settings.gemini_api_keys,
                default_headers={"HTTP-Referer": "https://forge.local", "X-Title": "Forge"},
            ),
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
        search_provider=_build_search_provider(settings),
        fetcher=HttpPageFetcher(timeout_seconds=settings.fetch_timeout_seconds),
    )

    transport = TelegramTransport(settings.telegram_token)
    integrations = IntegrationService(settings=settings, store=store)
    figma = FigmaTemplateService(settings)
    builder = HybridProjectBuilder()
    mission_runner = MissionRunner(
        store=store,
        integrations=integrations,
        figma=figma,
        transport=transport,
        builder=builder,
    )
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
        mission_runner=mission_runner,
    )
    worker = WorkerService(settings=settings, store=store, processor=processor)
    return ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        integrations=integrations,
        figma=figma,
        transport=transport,
        mission_runner=mission_runner,
        worker=worker,
    )


def create_app(container: ForgeContainer | None = None) -> FastAPI:
    container = container or build_container()
    auth_client = SupabaseAuthClient(
        url=container.settings.supabase_url,
        api_key=container.settings.supabase_anon_key,
        timeout_seconds=container.settings.auth_timeout_seconds,
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
    app.state.integrations = container.integrations
    app.state.figma = container.figma or FigmaTemplateService(container.settings)
    app.state.mission_runner = container.mission_runner
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
