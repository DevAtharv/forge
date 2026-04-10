import json

from fastapi.testclient import TestClient

from forge.bootstrap import ForgeContainer, create_app
from forge.agents.aggregator import PipelineAggregator
from forge.agents.orchestrator import OrchestratorAgent
from forge.agents.task_agents import CodeAgent, DebugAgent, PlannerAgent, ProfileSummaryAgent, ResearchAgent, ReviewerAgent
from forge.builder import HybridProjectBuilder
from forge.figma import FigmaTemplateService
from forge.integrations import IntegrationService
from forge.missions import MissionRunner
from forge.providers.base import Fetcher, FetchedDocument, SearchProvider
from forge.providers.registry import ProviderRegistry
from forge.schemas import ProjectRecord, ProjectRevision
from tests.support import FakeAuthClient, FakeTransport, NoopWorker
from forge.workers.processor import JobProcessor, PipelineExecutor
from tests.support import ProcessorWorker


class NoopSearch(SearchProvider):
    async def search(self, query: str, *, max_results: int):
        return []


class NoopFetch(Fetcher):
    async def fetch(self, url: str) -> FetchedDocument | None:
        return None

    async def close(self) -> None:
        return None


class SequencedProvider:
    def __init__(self, outputs):
        self.outputs = list(outputs)

    async def generate(self, **kwargs):
        if not self.outputs:
            raise RuntimeError("No more fake outputs configured.")
        return self.outputs.pop(0)

    async def close(self):
        return None


def test_webhook_deduplicates_updates(settings, store) -> None:
    providers = ProviderRegistry(llm_providers={}, search_provider=NoopSearch(), fetcher=NoopFetch())
    integrations = IntegrationService(settings=settings, store=store)
    container = ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        integrations=integrations,
        transport=FakeTransport(),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=FakeTransport(), builder=HybridProjectBuilder()),
        worker=NoopWorker(),
    )
    app = create_app(container)
    app.state.auth_client = FakeAuthClient()
    client = TestClient(app)

    payload = {
        "update_id": 99,
        "message": {
            "message_id": 1,
            "from": {"id": 42, "username": "alice"},
            "chat": {"id": 42, "type": "private"},
            "text": "hello",
        },
    }

    response_one = client.post("/webhook", json=payload, headers={"x-telegram-bot-api-secret-token": "secret"})
    response_two = client.post("/webhook", json=payload, headers={"x-telegram-bot-api-secret-token": "secret"})

    assert response_one.status_code == 200
    assert response_two.status_code == 200
    assert len(store._jobs) == 1


def test_root_serves_ui_and_demo_plan_endpoint_works(settings, store) -> None:
    providers = ProviderRegistry(llm_providers={}, search_provider=NoopSearch(), fetcher=NoopFetch())
    integrations = IntegrationService(settings=settings, store=store)
    container = ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        integrations=integrations,
        transport=FakeTransport(),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=FakeTransport(), builder=HybridProjectBuilder()),
        worker=NoopWorker(),
    )
    app = create_app(container)
    app.state.auth_client = FakeAuthClient()
    client = TestClient(app)

    root_response = client.get("/")
    demo_response = client.post("/demo/plan", json={"prompt": "Build me a full CRUD API with postgres"})

    assert root_response.status_code == 200
    assert "Your AI dev team on Telegram" in root_response.text
    assert demo_response.status_code == 200
    assert demo_response.json()["plan"]["stages"][0]["name"] == "plan"


def test_auth_and_protected_plan_endpoints_work(settings, store) -> None:
    providers = ProviderRegistry(llm_providers={}, search_provider=NoopSearch(), fetcher=NoopFetch())
    integrations = IntegrationService(settings=settings, store=store)
    container = ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        integrations=integrations,
        transport=FakeTransport(),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=FakeTransport(), builder=HybridProjectBuilder()),
        worker=NoopWorker(),
    )
    app = create_app(container)
    app.state.auth_client = FakeAuthClient()
    client = TestClient(app)

    sign_in = client.post("/api/auth/signin", json={"email": "demo@forge.dev", "password": "password123"})
    session = client.get("/api/auth/session", headers={"Authorization": "Bearer token-1"})
    plan = client.post(
        "/api/app/plan",
        json={"prompt": "Build me a full CRUD API with postgres"},
        headers={"Authorization": "Bearer token-1"},
    )

    assert sign_in.status_code == 200
    assert sign_in.json()["session"]["access_token"] == "token-1"
    assert session.status_code == 200
    assert session.json()["user"]["email"] == "demo@forge.dev"
    assert plan.status_code == 200
    assert plan.json()["plan"]["stages"][0]["name"] == "plan"


def test_signup_returns_session_when_supabase_uses_top_level_tokens(settings, store) -> None:
    providers = ProviderRegistry(llm_providers={}, search_provider=NoopSearch(), fetcher=NoopFetch())
    integrations = IntegrationService(settings=settings, store=store)
    container = ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        integrations=integrations,
        transport=FakeTransport(),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=FakeTransport(), builder=HybridProjectBuilder()),
        worker=NoopWorker(),
    )
    app = create_app(container)
    app.state.auth_client = FakeAuthClient()
    client = TestClient(app)

    response = client.post("/api/auth/signup", json={"email": "demo@forge.dev", "password": "password123"})

    assert response.status_code == 200
    assert response.json()["session"]["access_token"] == "token-1"
    assert response.json()["message"] == "Account created and signed in."


def test_dashboard_and_run_endpoints_return_workspace_data(settings, store) -> None:
    provider = SequencedProvider(
        [
            "{not-json",
            json.dumps(
                {
                    "summary": "Plan ready",
                    "user_visible_text": "1. Create auth flow.\n2. Add protected route.",
                    "artifacts": [],
                    "handoff": {"plan": "Create auth first"},
                    "citations": [],
                    "confidence": 0.8,
                    "internal_notes": [],
                }
            ),
            json.dumps(
                {
                    "summary": "Implementation ready",
                    "user_visible_text": "Built the FastAPI auth service and protected route.",
                    "artifacts": [
                        {
                            "name": "app.py",
                            "content": "from fastapi import FastAPI\napp = FastAPI()\n",
                            "mime_type": "text/plain",
                            "language": "python",
                        }
                    ],
                    "handoff": {"implementation_summary": "Added FastAPI app"},
                    "citations": [],
                    "confidence": 0.82,
                    "internal_notes": [],
                }
            ),
            json.dumps(
                {
                    "summary": "Review ready",
                    "user_visible_text": "Looks good. Add rate limiting for login endpoints.",
                    "artifacts": [],
                    "handoff": {"verdict": "good"},
                    "citations": [],
                    "confidence": 0.71,
                    "internal_notes": [],
                }
            ),
        ]
    )
    providers = ProviderRegistry(llm_providers={"fallback": provider}, search_provider=NoopSearch(), fetcher=NoopFetch())
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
        transport=FakeTransport(),
        orchestrator=orchestrator,
        executor=executor,
        profile_summary_agent=ProfileSummaryAgent(settings=settings, providers=providers),
        mission_runner=MissionRunner(
            store=store,
            integrations=IntegrationService(settings=settings, store=store),
            transport=FakeTransport(),
            builder=HybridProjectBuilder(),
        ),
    )
    integrations = IntegrationService(settings=settings, store=store)
    container = ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        integrations=integrations,
        transport=FakeTransport(),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=FakeTransport(), builder=HybridProjectBuilder()),
        worker=ProcessorWorker(processor=processor),
    )
    app = create_app(container)
    app.state.auth_client = FakeAuthClient()
    app.state.profile_refresher = None
    client = TestClient(app)

    dashboard = client.get("/api/app/dashboard", headers={"Authorization": "Bearer token-1"})
    run = client.post(
        "/api/app/run",
        json={"prompt": "Build me a production-ready FastAPI auth service"},
        headers={"Authorization": "Bearer token-1"},
    )

    assert dashboard.status_code == 200
    assert dashboard.json()["user"]["email"] == "demo@forge.dev"
    assert run.status_code == 200
    assert run.json()["message"] == "Mission queued. Forge will keep running it in the background."
    assert run.json()["mission"]["kind"] == "build"
    assert len(run.json()["history"]) >= 1


def test_dashboard_exposes_telegram_link_status_and_link_code(settings, store) -> None:
    providers = ProviderRegistry(llm_providers={}, search_provider=NoopSearch(), fetcher=NoopFetch())
    integrations = IntegrationService(settings=settings, store=store)
    container = ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        integrations=integrations,
        transport=FakeTransport(),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=FakeTransport(), builder=HybridProjectBuilder()),
        worker=NoopWorker(),
    )
    app = create_app(container)
    app.state.auth_client = FakeAuthClient()
    client = TestClient(app)

    link_response = client.post(
        "/api/app/link/telegram",
        json={"refresh": True},
        headers={"Authorization": "Bearer token-1"},
    )
    dashboard = client.get("/api/app/dashboard", headers={"Authorization": "Bearer token-1"})

    assert link_response.status_code == 200
    assert len(link_response.json()["code"]) == 6
    assert dashboard.status_code == 200
    assert dashboard.json()["telegram_link"]["pending_code"] == link_response.json()["code"]
    assert len(dashboard.json()["figma_templates"]) >= 1
    assert any(item["configured"] for item in dashboard.json()["figma_templates"])


def test_client_config_exposes_figma_template_status(settings, store) -> None:
    providers = ProviderRegistry(llm_providers={}, search_provider=NoopSearch(), fetcher=NoopFetch())
    integrations = IntegrationService(settings=settings, store=store)
    figma = FigmaTemplateService(settings)
    container = ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        integrations=integrations,
        figma=figma,
        transport=FakeTransport(),
        mission_runner=MissionRunner(
            store=store,
            integrations=integrations,
            figma=figma,
            transport=FakeTransport(),
            builder=HybridProjectBuilder(),
        ),
        worker=NoopWorker(),
    )
    app = create_app(container)
    app.state.auth_client = FakeAuthClient()
    client = TestClient(app)

    response = client.get("/api/client-config")

    assert response.status_code == 200
    payload = response.json()
    assert payload["integrations"]["figma"] is True
    assert any(item["configured"] for item in payload["figma_templates"])


def test_vercel_start_redirects_to_install_page_and_callback_uses_cookie_state(settings, store) -> None:
    providers = ProviderRegistry(llm_providers={}, search_provider=NoopSearch(), fetcher=NoopFetch())
    integrations = IntegrationService(settings=settings, store=store)
    container = ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        integrations=integrations,
        transport=FakeTransport(),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=FakeTransport(), builder=HybridProjectBuilder()),
        worker=NoopWorker(),
    )
    app = create_app(container)
    app.state.auth_client = FakeAuthClient()

    async def fake_complete_oauth(provider: str, *, code: str, state: str):
        from forge.schemas import OAuthConnection

        assert provider == "vercel"
        assert code == "code-123"
        assert state
        return OAuthConnection(
            workspace_user_id=-1,
            provider="vercel",
            account_id="acct_1",
            account_name="atharv",
            access_token_encrypted="encrypted",
        )

    app.state.integrations.complete_oauth = fake_complete_oauth  # type: ignore[method-assign]
    client = TestClient(app)

    start = client.get("/api/integrations/vercel/start", headers={"Authorization": "Bearer token-1"}, follow_redirects=False)
    assert start.status_code == 302
    assert start.headers["location"] == "https://vercel.com/integrations/forge"
    assert "forge_vercel_oauth_state=" in start.headers.get("set-cookie", "")

    callback = client.get("/api/integrations/vercel/callback?code=code-123", follow_redirects=False)
    assert callback.status_code == 302
    assert "integration=vercel" in callback.headers["location"]
    assert "status=connected" in callback.headers["location"]


def test_vercel_callback_without_state_redirects_with_human_message(settings, store) -> None:
    providers = ProviderRegistry(llm_providers={}, search_provider=NoopSearch(), fetcher=NoopFetch())
    integrations = IntegrationService(settings=settings, store=store)
    container = ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        integrations=integrations,
        transport=FakeTransport(),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=FakeTransport(), builder=HybridProjectBuilder()),
        worker=NoopWorker(),
    )
    app = create_app(container)
    app.state.auth_client = FakeAuthClient()
    client = TestClient(app)

    callback = client.get("/api/integrations/vercel/callback?code=code-123", follow_redirects=False)

    assert callback.status_code == 302
    assert "integration=vercel" in callback.headers["location"]
    assert "status=error" in callback.headers["location"]
    assert "Connection+expired" in callback.headers["location"]


def test_vercel_token_connect_endpoint_stores_connection(settings, store) -> None:
    providers = ProviderRegistry(llm_providers={}, search_provider=NoopSearch(), fetcher=NoopFetch())
    integrations = IntegrationService(settings=settings, store=store)
    container = ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        integrations=integrations,
        transport=FakeTransport(),
        mission_runner=MissionRunner(store=store, integrations=integrations, transport=FakeTransport(), builder=HybridProjectBuilder()),
        worker=NoopWorker(),
    )
    app = create_app(container)
    app.state.auth_client = FakeAuthClient()

    async def fake_connect_vercel_token(*, workspace_user_id: int, token: str):
        from forge.schemas import OAuthConnection

        assert workspace_user_id
        assert token == "vercel-token-123"
        return OAuthConnection(
            workspace_user_id=workspace_user_id,
            provider="vercel",
            account_id="acct_1",
            account_name="atharv",
            access_token_encrypted="encrypted",
        )

    app.state.integrations.connect_vercel_token = fake_connect_vercel_token  # type: ignore[method-assign]
    client = TestClient(app)

    response = client.post(
        "/api/integrations/vercel/token",
        json={"token": "vercel-token-123"},
        headers={"Authorization": "Bearer token-1"},
    )

    assert response.status_code == 200
    assert response.json()["connection"]["provider"] == "vercel"
    assert "Vercel connected as" in response.json()["message"]


def test_project_detail_files_download_and_publish_endpoints(settings, store) -> None:
    providers = ProviderRegistry(llm_providers={}, search_provider=NoopSearch(), fetcher=NoopFetch())
    integrations = IntegrationService(settings=settings, store=store)
    runner = MissionRunner(store=store, integrations=integrations, transport=FakeTransport(), builder=HybridProjectBuilder())
    container = ForgeContainer(
        settings=settings,
        store=store,
        providers=providers,
        integrations=integrations,
        transport=FakeTransport(),
        mission_runner=runner,
        worker=NoopWorker(),
    )
    app = create_app(container)
    app.state.auth_client = FakeAuthClient()
    client = TestClient(app)

    project = ProjectRecord(
        id="project-1",
        workspace_user_id=-359812737456354032,
        name="Bright Studio",
        slug="bright-studio",
        prompt="build me a bright studio website",
        archetype="landing-page",
        latest_manifest={"package.json": {"content": "{}"}},
        preview_url="https://preview.example.vercel.app",
        preview_status="ready",
    )
    store._projects[project.id] = project  # noqa: SLF001
    store._project_revisions["revision-1"] = ProjectRevision(  # noqa: SLF001
        id="revision-1",
        project_id=project.id or "",
        workspace_user_id=project.workspace_user_id,
        summary="Generated 1 files for Bright Studio",
        file_manifest={"package.json": {"content": "{}"}},
        bundle_name="bright-studio.zip",
        bundle_file_count=1,
        preview_url=project.preview_url,
        preview_status="ready",
    )

    async def fake_refresh_project_preview(*, workspace_user_id: int, project_id: str):
        assert workspace_user_id == project.workspace_user_id
        assert project_id == "project-1"
        return await store.update_project(
            "project-1",
            {"preview_url": "https://preview-refresh.example.vercel.app", "preview_status": "ready"},
        )

    app.state.mission_runner.refresh_project_preview = fake_refresh_project_preview  # type: ignore[method-assign]

    detail = client.get("/api/app/projects/project-1", headers={"Authorization": "Bearer token-1"})
    files = client.get("/api/app/projects/project-1/files", headers={"Authorization": "Bearer token-1"})
    download = client.get("/api/app/projects/project-1/download", headers={"Authorization": "Bearer token-1"})
    preview = client.post("/api/app/projects/project-1/preview", headers={"Authorization": "Bearer token-1"})
    publish = client.post("/api/app/projects/project-1/publish/github", headers={"Authorization": "Bearer token-1"})

    assert detail.status_code == 200
    assert detail.json()["project"]["slug"] == "bright-studio"
    assert detail.json()["latest_revision"]["bundle_name"] == "bright-studio.zip"
    assert files.status_code == 200
    assert files.json()["files"] == ["package.json"]
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/zip"
    assert preview.status_code == 200
    assert preview.json()["project"]["preview_url"] == "https://preview-refresh.example.vercel.app"
    assert publish.status_code == 200
    assert publish.json()["mission"]["kind"] == "publish"
