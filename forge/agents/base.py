from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

from forge.schemas import AgentResult, Artifact, Citation, ConversationRecord, UserProfile


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
        return _coerce_agent_result_from_dict(agent=agent, data=data)
    except Exception:
        return AgentResult.from_text(agent=agent, text=payload, confidence=0.3)


def _coerce_agent_result_from_dict(agent: str, data: dict[str, Any]) -> AgentResult:
    summary = str(data.get("summary") or "").strip()
    user_visible_text = str(data.get("user_visible_text") or data.get("answer") or "").strip()
    if not summary and user_visible_text:
        summary = user_visible_text[:160]
    if not user_visible_text and summary:
        user_visible_text = summary
    if not user_visible_text:
        user_visible_text = "Completed."
    if not summary:
        summary = user_visible_text[:160]

    handoff = data.get("handoff")
    if not isinstance(handoff, dict):
        handoff = {}

    internal_notes_raw = data.get("internal_notes") or []
    internal_notes = [str(item) for item in internal_notes_raw] if isinstance(internal_notes_raw, list) else []

    confidence_raw = data.get("confidence", 0.5)
    try:
        confidence = float(confidence_raw)
    except (TypeError, ValueError):
        confidence = 0.5
    confidence = max(0.0, min(1.0, confidence))

    artifacts: list[Artifact] = []
    for item in data.get("artifacts") or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name")
        content = item.get("content")
        if not isinstance(name, str) or not isinstance(content, str):
            continue
        artifacts.append(
            Artifact(
                name=name,
                content=content,
                mime_type=str(item.get("mime_type") or "text/plain"),
                language=str(item.get("language")) if item.get("language") is not None else None,
            )
        )

    citations: list[Citation] = []
    for item in data.get("citations") or []:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        url = item.get("url")
        if not isinstance(title, str) or not isinstance(url, str):
            continue
        snippet = item.get("snippet")
        citations.append(Citation(title=title, url=url, snippet=str(snippet) if snippet is not None else None))

    return AgentResult(
        agent=agent,
        summary=summary,
        user_visible_text=user_visible_text,
        artifacts=artifacts,
        handoff=handoff,
        citations=citations,
        confidence=confidence,
        internal_notes=internal_notes,
    )


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
