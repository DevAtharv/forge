import json

import pytest

from forge.agents.orchestrator import OrchestratorAgent
from forge.config import parse_model_routes
from forge.schemas import UserProfile


class BrokenProviderRegistry:
    async def generate(self, *args, **kwargs):
        return "{not-json"


class FixedProviderRegistry:
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def generate(self, *args, **kwargs):
        return json.dumps(self.payload)


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


@pytest.mark.asyncio
async def test_orchestrator_normalizes_explanation_plans_to_research_only(settings) -> None:
    orchestrator = OrchestratorAgent(
        settings=settings,
        providers=FixedProviderRegistry(
            {
                "intent": "Explain Redis and its use cases",
                "response_format": "explanation",
                "context_policy": "recent_plus_profile",
                "stages": [
                    {
                        "name": "Research Redis",
                        "agents": ["research"],
                        "tasks": {"research": "Provide an overview of Redis and its common use cases"},
                    },
                    {
                        "name": "Code Examples",
                        "agents": ["code", "reviewer"],
                        "tasks": {
                            "code": "Generate code snippets demonstrating Redis usage",
                            "reviewer": "Review the generated code for accuracy and best practices",
                        },
                    },
                ],
            }
        ),
    )
    profile = UserProfile(user_id=1)

    plan = await orchestrator.plan(
        "What is Redis and when should I use it?",
        history=[],
        profile=profile,
        has_image=False,
    )

    assert len(plan.stages) == 1
    assert plan.stages[0].agents == ["research"]


def test_openrouter_free_routes_are_normalized() -> None:
    routes = parse_model_routes("openrouter/openrouter/free,groq/llama-3.3-70b-versatile", "")

    assert routes[0].provider == "openrouter"
    assert routes[0].model == "openrouter/auto"


@pytest.mark.asyncio
async def test_orchestrator_drops_debug_stage_when_no_debug_signal(settings) -> None:
    orchestrator = OrchestratorAgent(
        settings=settings,
        providers=FixedProviderRegistry(
            {
                "intent": "Build website",
                "response_format": "mixed",
                "context_policy": "recent_plus_profile",
                "stages": [
                    {
                        "name": "Implement",
                        "agents": ["code", "debug", "reviewer"],
                        "tasks": {
                            "code": "Build sweet shop website",
                            "debug": "Test website for errors",
                            "reviewer": "Review generated website code",
                        },
                    }
                ],
            }
        ),
    )
    profile = UserProfile(user_id=1)

    plan = await orchestrator.plan(
        "Build me a website for a sweet shop",
        history=[],
        profile=profile,
        has_image=False,
    )

    assert "debug" not in plan.stages[0].agents
