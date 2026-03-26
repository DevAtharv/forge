from __future__ import annotations

import pytest

from forge.builder import HybridProjectBuilder
from forge.integrations import IntegrationService
from forge.missions import MissionRunner
from forge.schemas import MissionRecord, OAuthConnection
from tests.support import FakeTransport


def test_hybrid_builder_generates_web_project_files() -> None:
    builder = HybridProjectBuilder()
    blueprint = builder.choose_blueprint("build me a website for a sweet shop with auth")
    artifacts = builder.build_files(blueprint, "build me a website for a sweet shop with auth")
    names = {item.name for item in artifacts}

    assert blueprint.archetype == "ecommerce-storefront"
    assert "package.json" in names
    assert "src/App.tsx" in names
    assert "vercel.json" in names


@pytest.mark.asyncio
async def test_mission_runner_builds_project_and_waits_for_github_connection(settings, store) -> None:
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

    assert result.status == "awaiting_approval"
    assert result.approval_request is not None
    assert result.approval_request["action"] == "connect_github"


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
