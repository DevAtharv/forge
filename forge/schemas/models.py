from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    title: str
    url: str
    snippet: str | None = None


class Artifact(BaseModel):
    name: str
    content: str
    mime_type: str = "text/plain"
    language: str | None = None


class AgentResult(BaseModel):
    agent: str
    summary: str
    user_visible_text: str
    artifacts: list[Artifact] = Field(default_factory=list)
    handoff: dict[str, Any] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    confidence: float = 0.5
    internal_notes: list[str] = Field(default_factory=list)

    @classmethod
    def from_text(cls, agent: str, text: str, *, confidence: float = 0.5) -> "AgentResult":
        return cls(
            agent=agent,
            summary=text[:160],
            user_visible_text=text,
            confidence=confidence,
        )


class StagePlan(BaseModel):
    name: str
    agents: list[str]
    tasks: dict[str, str] = Field(default_factory=dict)


class OrchestrationPlan(BaseModel):
    intent: str
    response_format: Literal["code", "explanation", "mixed", "plan"] = "mixed"
    context_policy: Literal["recent", "recent_plus_profile", "recent_plus_profile_plus_summary"] = (
        "recent_plus_profile"
    )
    stages: list[StagePlan] = Field(default_factory=list)


class StageExecution(BaseModel):
    name: str
    outputs: dict[str, AgentResult] = Field(default_factory=dict)


class ConversationRecord(BaseModel):
    id: str | None = None
    user_id: int
    role: Literal["user", "assistant"]
    content: str
    agents_used: list[str] = Field(default_factory=list)
    created_at: datetime | None = None


class UserProfile(BaseModel):
    user_id: int
    username: str | None = None
    stack: list[str] = Field(default_factory=list)
    skill_level: str = "intermediate"
    current_projects: list[str] = Field(default_factory=list)
    preferences: dict[str, Any] = Field(default_factory=dict)
    summary: str | None = None
    active_context: dict[str, Any] = Field(default_factory=dict)
    last_seen: datetime | None = None
    last_context_refresh: datetime | None = None
    message_count: int = 0


class MessageJob(BaseModel):
    id: str | None = None
    telegram_update_id: int
    user_id: int
    chat_id: int
    raw_update: dict[str, Any]
    status: str = "queued"
    pipeline: dict[str, Any] | None = None
    attempts: int = 0
    available_at: datetime | None = None
    locked_at: datetime | None = None
    locked_by: str | None = None
    error: str | None = None
    result_preview: str | None = None
    status_message_id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class DeliveryPayload(BaseModel):
    text: str
    document_name: str | None = None
    document_bytes: bytes | None = None


class AccountLink(BaseModel):
    web_user_id: str
    workspace_user_id: int
    web_email: str | None = None
    telegram_user_id: int
    telegram_username: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class LinkToken(BaseModel):
    code: str
    web_user_id: str
    workspace_user_id: int
    web_email: str | None = None
    expires_at: datetime
    consumed_at: datetime | None = None
    telegram_user_id: int | None = None
    telegram_username: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
