from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable

from forge.agents import (
    AgentInvocation,
    CodeAgent,
    DebugAgent,
    PipelineAggregator,
    PlannerAgent,
    ProfileSummaryAgent,
    ResearchAgent,
    ReviewerAgent,
)
from forge.agents.orchestrator import OrchestratorAgent
from forge.config import Settings
from forge.memory import MemoryStore, build_user_context
from forge.schemas import ConversationRecord, DeliveryPayload, MessageJob, OrchestrationPlan, StageExecution, UserProfile
from forge.telegram import TelegramTransport

StageCallback = Callable[[str], Awaitable[None]]


def _extract_message(raw_update: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
        if raw_update.get(key):
            return raw_update[key]
    return None


class PipelineExecutor:
    def __init__(
        self,
        *,
        planner: PlannerAgent,
        code: CodeAgent,
        debug: DebugAgent,
        research: ResearchAgent,
        reviewer: ReviewerAgent,
        aggregator: PipelineAggregator,
    ) -> None:
        self._agents = {
            "planner": planner,
            "code": code,
            "debug": debug,
            "research": research,
            "reviewer": reviewer,
        }
        self._aggregator = aggregator

    async def execute(
        self,
        *,
        plan: OrchestrationPlan,
        original_task: str,
        history: list[ConversationRecord],
        user_context: str,
        profile: UserProfile,
        image_bytes: bytes | None,
        on_stage_start: StageCallback | None = None,
    ) -> tuple[DeliveryPayload, list[StageExecution]]:
        shared_handoff: dict[str, Any] = {}
        stage_executions: list[StageExecution] = []

        for stage in plan.stages:
            if on_stage_start:
                await on_stage_start(stage.name)
            invocations = []
            for agent_name in stage.agents:
                task = stage.tasks.get(agent_name, original_task)
                invocations.append(
                    AgentInvocation(
                        agent=agent_name,
                        task=task,
                        original_task=original_task,
                        history=history,
                        user_context=user_context,
                        profile=profile,
                        shared_handoff=shared_handoff.copy(),
                        image_bytes=image_bytes,
                    )
                )
            results = await asyncio.gather(*[self._agents[inv.agent].run(inv) for inv in invocations])
            stage_output = {}
            for agent_name, result in zip(stage.agents, results):
                stage_output[agent_name] = result
                shared_handoff[agent_name] = result.handoff
                shared_handoff[f"{agent_name}_summary"] = result.summary
                if result.artifacts:
                    shared_handoff[f"{agent_name}_artifacts"] = [item.model_dump() for item in result.artifacts]
            stage_executions.append(StageExecution(name=stage.name, outputs=stage_output))

        delivery = self._aggregator.format(plan, stage_executions)
        return delivery, stage_executions


class JobProcessor:
    def __init__(
        self,
        *,
        settings: Settings,
        store: MemoryStore,
        transport: TelegramTransport,
        orchestrator: OrchestratorAgent,
        executor: PipelineExecutor,
        profile_summary_agent: ProfileSummaryAgent,
    ) -> None:
        self.settings = settings
        self.store = store
        self.transport = transport
        self.orchestrator = orchestrator
        self.executor = executor
        self.profile_summary_agent = profile_summary_agent

    async def process(self, job: MessageJob) -> None:
        message = _extract_message(job.raw_update)
        if not message:
            await self.store.complete_message_job(job.id or "", result_preview="Ignored unsupported update.")
            return

        chat_id = int(message.get("chat", {}).get("id", job.chat_id))
        user = message.get("from") or {}
        user_id = int(user.get("id", job.user_id))
        username = user.get("username")
        text = (message.get("text") or message.get("caption") or "").strip()
        photo_sizes = message.get("photo") or []
        if not text and photo_sizes:
            text = "Debug this issue from the attached screenshot."
        elif not text:
            text = "Help me with this request."

        status_message_id = await self.transport.send_status_message(chat_id, "Forge is assembling the right agents...")
        await self.store.attach_status_message(job.id or "", status_message_id)

        await self.store.ensure_user_profile(user_id, username)
        profile = await self.store.get_user_profile(user_id)
        history = await self.store.get_recent_conversations(user_id, limit=self.settings.history_window)

        await self.store.append_conversation(ConversationRecord(user_id=user_id, role="user", content=text))

        image_bytes = await self.transport.download_photo(photo_sizes)
        plan = await self.orchestrator.plan(text, history=history, profile=profile, has_image=bool(image_bytes))
        await self.store.update_message_job_pipeline(job.id or "", plan.model_dump(mode="json"))

        user_context = build_user_context(profile, history, plan.context_policy)

        async def on_stage_start(stage_name: str) -> None:
            await self.transport.edit_status_message(
                chat_id,
                status_message_id,
                f"Forge is running stage: {stage_name}...",
            )

        delivery, _executions = await self.executor.execute(
            plan=plan,
            original_task=text,
            history=history,
            user_context=user_context,
            profile=profile,
            image_bytes=image_bytes,
            on_stage_start=on_stage_start,
        )

        await self.transport.deliver(chat_id, delivery, status_message_id=status_message_id)
        await self.store.append_conversation(
            ConversationRecord(
                user_id=user_id,
                role="assistant",
                content=delivery.text,
                agents_used=[name for stage in plan.stages for name in stage.agents],
            )
        )
        await self.store.complete_message_job(job.id or "", result_preview=delivery.text[:240])

        asyncio.create_task(self.refresh_profile(user_id, username))

    async def refresh_profile(self, user_id: int, username: str | None) -> None:
        profile = await self.store.get_user_profile(user_id)
        history = await self.store.get_recent_conversations(user_id, limit=max(10, self.settings.history_window))
        payload = {
            "username": username or profile.username,
            "existing_profile": profile.model_dump(mode="json"),
            "recent_conversation": [{"role": item.role, "content": item.content} for item in history[-10:]],
        }
        try:
            summary = await self.profile_summary_agent.summarize(payload)
        except Exception:
            return

        updates = {
            "username": username or profile.username,
            "summary": summary.get("summary"),
            "stack": summary.get("stack") or profile.stack,
            "skill_level": summary.get("skill_level") or profile.skill_level,
            "current_projects": summary.get("current_projects") or profile.current_projects,
            "preferences": summary.get("preferences") or profile.preferences,
            "active_context": summary.get("active_context") or profile.active_context,
        }
        await self.store.update_user_profile(user_id, updates)

    async def notify_terminal_failure(self, job: MessageJob) -> None:
        if not job.status_message_id:
            return
        message = (
            "Forge could not finish this request after multiple attempts.\n\n"
            f"Last error: {job.error or 'unknown error'}"
        )
        await self.transport.edit_status_message(job.chat_id, job.status_message_id, message)
