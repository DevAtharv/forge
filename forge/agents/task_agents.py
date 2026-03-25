from __future__ import annotations

import base64
import json

from forge.agents.base import AgentInvocation, coerce_agent_result
from forge.config import Settings
from forge.prompts import (
    CODE_SYSTEM,
    DEBUG_SYSTEM,
    PLANNER_SYSTEM,
    PROFILE_SUMMARY_SYSTEM,
    RESEARCH_SYSTEM,
    REVIEWER_SYSTEM,
)
from forge.providers import ProviderRegistry
from forge.schemas import AgentResult, Citation


def _history_messages(invocation: AgentInvocation) -> list[dict[str, str]]:
    return [{"role": item.role, "content": item.content} for item in invocation.history[-6:]]


class PlannerAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def run(self, invocation: AgentInvocation) -> AgentResult:
        user_prompt = (
            f"Task:\n{invocation.task}\n\n"
            f"User context:\n{invocation.user_context or 'No durable context.'}\n\n"
            f"Shared handoff:\n{json.dumps(invocation.shared_handoff, ensure_ascii=True)}"
        )
        raw = await self.providers.generate(
            self.settings.planner_routes,
            messages=[
                {"role": "system", "content": PLANNER_SYSTEM},
                *_history_messages(invocation),
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1400,
            json_mode=True,
        )
        return coerce_agent_result("planner", raw)


class CodeAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def run(self, invocation: AgentInvocation) -> AgentResult:
        user_prompt = (
            f"Original task:\n{invocation.original_task}\n\n"
            f"Specific coding task:\n{invocation.task}\n\n"
            f"User context:\n{invocation.user_context or 'No durable context.'}\n\n"
            f"Planner/research handoff:\n{json.dumps(invocation.shared_handoff, ensure_ascii=True)}"
        )
        raw = await self.providers.generate(
            self.settings.code_routes,
            messages=[
                {"role": "system", "content": CODE_SYSTEM},
                *_history_messages(invocation),
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.15,
            max_tokens=3200,
            json_mode=True,
        )
        return coerce_agent_result("code", raw)


class DebugAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def run(self, invocation: AgentInvocation) -> AgentResult:
        if invocation.image_bytes:
            image_b64 = base64.b64encode(invocation.image_bytes).decode("ascii")
            user_payload: str | list[dict[str, object]] = [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                {
                    "type": "text",
                    "text": (
                        f"Task:\n{invocation.task or invocation.original_task}\n\n"
                        f"User context:\n{invocation.user_context or 'No durable context.'}"
                    ),
                },
            ]
        else:
            user_payload = (
                f"Task:\n{invocation.task or invocation.original_task}\n\n"
                f"User context:\n{invocation.user_context or 'No durable context.'}"
            )
        raw = await self.providers.generate(
            self.settings.debug_routes,
            messages=[
                {"role": "system", "content": DEBUG_SYSTEM},
                *_history_messages(invocation),
                {"role": "user", "content": user_payload},
            ],
            temperature=0.1,
            max_tokens=1400,
            json_mode=True,
        )
        return coerce_agent_result("debug", raw)


class ResearchAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def run(self, invocation: AgentInvocation) -> AgentResult:
        hits = await self.providers.search_provider.search(
            invocation.task,
            max_results=self.settings.search_result_limit,
        )
        documents = []
        for hit in hits:
            try:
                document = await self.providers.fetcher.fetch(hit.url)
            except Exception:
                continue
            if document:
                documents.append(document)
            if len(documents) >= min(3, self.settings.search_result_limit):
                break

        if documents:
            sources = [
                {"title": item.title, "url": item.url, "content": item.content[:3500]}
                for item in documents
            ]
            user_prompt = (
                f"Task:\n{invocation.task}\n\n"
                f"User context:\n{invocation.user_context or 'No durable context.'}\n\n"
                f"Retrieved sources:\n{json.dumps(sources, ensure_ascii=True)}"
            )
            raw = await self.providers.generate(
                self.settings.research_routes,
                messages=[
                    {"role": "system", "content": RESEARCH_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.25,
                max_tokens=1400,
                json_mode=True,
            )
            result = coerce_agent_result("research", raw)
            if not result.citations:
                result.citations = [
                    Citation(title=item.title, url=item.url, snippet=item.content[:180])
                    for item in documents
                ]
            result.internal_notes.append("retrieval_mode:live")
            return result

        fallback_prompt = (
            f"Task:\n{invocation.task}\n\n"
            "No live sources were available. Answer carefully and explicitly note that the reply falls back to model knowledge."
        )
        raw = await self.providers.generate(
            self.settings.research_routes,
            messages=[
                {"role": "system", "content": RESEARCH_SYSTEM},
                {"role": "user", "content": fallback_prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
            json_mode=True,
        )
        result = coerce_agent_result("research", raw)
        result.internal_notes.append("retrieval_mode:model_only_fallback")
        return result


class ReviewerAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def run(self, invocation: AgentInvocation) -> AgentResult:
        user_prompt = (
            f"Original task:\n{invocation.original_task}\n\n"
            f"Review focus:\n{invocation.task}\n\n"
            f"Shared handoff:\n{json.dumps(invocation.shared_handoff, ensure_ascii=True)}"
        )
        raw = await self.providers.generate(
            self.settings.reviewer_routes,
            messages=[
                {"role": "system", "content": REVIEWER_SYSTEM},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=1400,
            json_mode=True,
        )
        return coerce_agent_result("reviewer", raw)


class ProfileSummaryAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def summarize(self, payload: dict[str, object]) -> dict[str, object]:
        raw = await self.providers.generate(
            self.settings.summary_routes,
            messages=[
                {"role": "system", "content": PROFILE_SUMMARY_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
            ],
            temperature=0.1,
            max_tokens=800,
            json_mode=True,
        )
        return json.loads(raw)
