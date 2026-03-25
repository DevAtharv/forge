import pytest

from forge.agents.orchestrator import OrchestratorAgent
from forge.schemas import UserProfile


class BrokenProviderRegistry:
    async def generate(self, *args, **kwargs):
        return "{not-json"


@pytest.mark.asyncio
async def test_orchestrator_falls_back_to_heuristics_for_complex_code_request(settings) -> None:
    orchestrator = OrchestratorAgent(settings=settings, providers=BrokenProviderRegistry())
    profile = UserProfile(user_id=1)

    plan = await orchestrator.plan(
        "build me a full CRUD API with postgres",
        history=[],
        profile=profile,
        has_image=False,
    )

    assert [stage.name for stage in plan.stages] == ["plan", "implement", "review"]
    assert plan.stages[1].agents == ["code"]
    assert plan.stages[2].agents == ["reviewer"]
