from __future__ import annotations

import pytest

from forge.builder import HybridProjectBuilder
from forge.integrations import IntegrationService
from forge.missions import MissionRunner
from forge.schemas import MissionRecord, OAuthConnection, ProjectRecord
from tests.support import FakeTransport


def test_hybrid_builder_generates_web_project_files() -> None:
    builder = HybridProjectBuilder()
    blueprint = builder.choose_blueprint("build me a website for a sweet shop with auth")
    artifacts = builder.build_files(blueprint, "build me a website for a sweet shop with auth")
    names = {item.name for item in artifacts}

    assert blueprint.archetype == "ecommerce-storefront"
    assert blueprint.figma_template_key == "ecommerce-storefront"
    assert blueprint.figma_template_name == "Forge Storefront"
    assert "package.json" in names
    assert "src/App.tsx" in names
    assert "vercel.json" in names


def test_hybrid_builder_generates_weather_project_files() -> None:
    builder = HybridProjectBuilder()
    blueprint = builder.choose_blueprint("Build a production ready weather app")
    artifacts = builder.build_files(blueprint, "Build a production ready weather app")
    files = {item.name: item.content for item in artifacts}

    assert blueprint.archetype == "weather-app"
    assert blueprint.figma_template_key == "weather-app"
    assert blueprint.figma_template_name == "Forge Weather Studio"
    assert "src/App.tsx" in files
    assert "Open-Meteo" in files["src/App.tsx"]
    assert "forecast-grid" in files["src/styles.css"]


def test_hybrid_builder_attaches_internal_figma_template_for_portfolio() -> None:
    builder = HybridProjectBuilder()
    blueprint = builder.choose_blueprint("build me a bold singer portfolio")

    assert blueprint.archetype == "portfolio"
    assert blueprint.figma_template_key == "portfolio"
    assert blueprint.figma_template_name == "Forge Creator Portfolio"
    assert "Editorial portfolio layout" in (blueprint.figma_template_description or "")


def test_hybrid_builder_attaches_food_delivery_template() -> None:
    builder = HybridProjectBuilder()
    blueprint = builder.choose_blueprint("build me a food delivery app")

    assert blueprint.archetype == "food-delivery-app"
    assert blueprint.figma_template_key == "food-delivery-app"
    assert blueprint.figma_template_name == "Forge Food Delivery"


def test_figma_service_resolves_configured_template_url(settings) -> None:
    from forge.figma import FigmaTemplateService

    service = FigmaTemplateService(settings)
    template = service.get_template_for_archetype("weather-app")

    assert template is not None
    assert template.frame_url == "https://figma.com/design/forge/weather?node-id=3-4"


def test_figma_service_marks_missing_template_slots(settings) -> None:
    from forge.figma import FigmaTemplateService

    service = FigmaTemplateService(settings)
    context = service.build_design_context("portfolio")

    assert context["type"] == "internal_figma_template"
    assert context["configured"] is False
    assert context["template_key"] == "portfolio"


@pytest.mark.asyncio
async def test_mission_runner_builds_project_without_github_and_marks_preview_pending_when_unconfigured(settings, store) -> None:
    runner = MissionRunner(
        store=store,
        integrations=IntegrationService(settings=settings, store=store),
        transport=FakeTransport(),
        builder=HybridProjectBuilder(),
    )
    mission = await store.create_mission(
        MissionRecord(
            workspace_user_id=1,
            source="web",
            kind="build",
            prompt="build me a landing page for a portfolio",
        )
    )

    result = await runner.run_mission(mission.id or "")

    assert result.status == "completed"
    assert result.approval_request is None
    assert result.bundle_name is not None
    assert "Code generated successfully" in result.response_text
    assert "Preview: not ready yet" in result.response_text

    projects = await store.list_projects(1)
    assert len(projects) == 1
    assert projects[0].preview_status == "failed"


@pytest.mark.asyncio
async def test_mission_runner_builds_project_with_managed_preview(settings, store, monkeypatch) -> None:
    settings.managed_preview_vercel_token = "forge-preview-token"

    async def fake_deploy_files(self, **kwargs):
        assert kwargs["project_name"].startswith("forge-preview-")
        return {"id": "dep_preview_1", "url": "preview-forge.vercel.app"}

    monkeypatch.setattr("forge.missions.VercelDeployClient.deploy_files", fake_deploy_files)

    runner = MissionRunner(
        store=store,
        integrations=IntegrationService(settings=settings, store=store),
        transport=FakeTransport(),
        builder=HybridProjectBuilder(),
    )
    mission = await store.create_mission(
        MissionRecord(
            workspace_user_id=1,
            source="web",
            kind="build",
            prompt="build me a landing page for a portfolio",
        )
    )

    result = await runner.run_mission(mission.id or "")

    assert result.status == "completed"
    assert result.preview_url == "https://preview-forge.vercel.app"
    assert "temporary Forge-managed preview" in result.response_text
    projects = await store.list_projects(1)
    assert projects[0].preview_url == "https://preview-forge.vercel.app"
    assert projects[0].preview_status == "ready"


@pytest.mark.asyncio
async def test_mission_runner_deploy_waits_for_vercel_connection_with_response_text(settings, store) -> None:
    runner = MissionRunner(
        store=store,
        integrations=IntegrationService(settings=settings, store=store),
        transport=FakeTransport(),
        builder=HybridProjectBuilder(),
    )
    project = await store.create_project(
        ProjectRecord(
            workspace_user_id=1,
            name="Weather Studio",
            slug="weather-studio",
            prompt="build me a weather app",
            archetype="weather-app",
            latest_manifest={"package.json": {"content": "{}"}},
        )
    )
    mission = await store.create_mission(
        MissionRecord(
            workspace_user_id=1,
            source="telegram",
            kind="deploy",
            prompt="deploy weather studio",
            project_id=project.id,
        )
    )

    result = await runner.run_mission(mission.id or "")

    assert result.status == "awaiting_approval"
    assert result.approval_request is not None
    assert result.approval_request["action"] == "connect_vercel"
    assert "connect Vercel" in result.response_text


@pytest.mark.asyncio
async def test_oauth_connection_round_trips_in_memory_store(settings, store) -> None:
    connection = await store.upsert_oauth_connection(
        OAuthConnection(
            workspace_user_id=12,
            provider="github",
            account_id="1",
            account_name="octocat",
            access_token_encrypted="encrypted",
        )
    )
    fetched = await store.get_oauth_connection(12, "github")

    assert fetched is not None
    assert fetched.account_name == connection.account_name


@pytest.mark.asyncio
async def test_mission_runner_persists_compact_memory_summary(settings, store) -> None:
    runner = MissionRunner(
        store=store,
        integrations=IntegrationService(settings=settings, store=store),
        transport=FakeTransport(),
        builder=HybridProjectBuilder(),
    )
    mission = await store.create_mission(
        MissionRecord(
            workspace_user_id=44,
            source="web",
            kind="build",
            prompt="build a premium landing page",
            status="completed",
            result_summary="Built Landing Page",
            response_text="Long response that should not be stored verbatim.",
            preview_url="https://preview.forgetest.dev",
        )
    )

    await runner._persist_mission_memory(mission)  # noqa: SLF001

    history = await store.get_recent_conversations(44, limit=5)
    assert history
    assert history[-1].content == "Built Landing Page\nPreview: https://preview.forgetest.dev"
