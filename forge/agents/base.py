from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from forge.schemas import AgentResult, ConversationRecord, UserProfile


def extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("Empty response.")
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(text[start : end + 1])


def coerce_agent_result(agent: str, payload: str) -> AgentResult:
    try:
        data = extract_json_object(payload)
        data["agent"] = agent
        return AgentResult.model_validate(data)
    except Exception:
        return AgentResult.from_text(agent=agent, text=payload, confidence=0.3)


@dataclass
class AgentInvocation:
    agent: str
    task: str
    original_task: str
    history: list[ConversationRecord]
    user_context: str
    profile: UserProfile
    shared_handoff: dict[str, Any] = field(default_factory=dict)
    image_bytes: bytes | None = None
