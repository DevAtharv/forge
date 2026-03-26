from __future__ import annotations

import json

import pytest

from forge.agents.base import AgentInvocation
from forge.agents.task_agents import CodeAgent
from forge.schemas import ConversationRecord, UserProfile


class _DummyProviders:
    def __init__(self, payload: str) -> None:
        self.payload = payload
        self.calls = 0

    async def generate(self, *args, **kwargs) -> str:  # noqa: ANN002, ANN003
        self.calls += 1
        return self.payload


@pytest.mark.asyncio
async def test_code_agent_upgrades_low_quality_website_output(settings) -> None:
    low_quality_payload = json.dumps(
        {
            "summary": "basic starter",
            "user_visible_text": "I've created a basic structure and design for your portfolio website.",
            "artifacts": [
                {
                    "name": "script.js",
                    "content": "// Add JavaScript functionality here",
                    "mime_type": "text/javascript",
                    "language": "javascript",
                }
            ],
            "handoff": {},
            "citations": [],
            "confidence": 0.4,
            "internal_notes": [],
        }
    )
    providers = _DummyProviders(low_quality_payload)
    agent = CodeAgent(settings=settings, providers=providers)  # type: ignore[arg-type]

    invocation = AgentInvocation(
        agent="code",
        task="Build a website for a sweet shop with auth and deploy to vercel",
        original_task="Build a website for a sweet shop with auth and deploy to vercel",
        history=[ConversationRecord(user_id=1, role="user", content="make it modern", agents_used=[])],
        user_context="Stack: frontend",
        profile=UserProfile(user_id=1, username="athar"),
        shared_handoff={},
        image_bytes=None,
    )

    result = await agent.run(invocation)

    artifact_names = {item.name for item in result.artifacts}
    assert "index.html" in artifact_names
    assert "vercel.json" in artifact_names
    assert "terminal_commands.sh" in artifact_names
    assert "Supabase" in result.user_visible_text
    assert any(note.startswith("website_bundle_upgraded") for note in result.internal_notes)

