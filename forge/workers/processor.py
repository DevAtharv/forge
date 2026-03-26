from __future__ import annotations

import asyncio
import re
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
from forge.integrations import OAuthError
from forge.memory import MemoryStore, build_user_context
from forge.missions import MissionRunner
from forge.schemas import ConversationRecord, DeliveryPayload, MessageJob, MissionRecord, OrchestrationPlan, StageExecution, UserProfile
from forge.telegram import TelegramTransport

StageCallback = Callable[[str], Awaitable[None]]


def _extract_message(raw_update: dict[str, Any]) -> dict[str, Any] | None:
    for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
        if raw_update.get(key):
            return raw_update[key]
    return None


def _extract_link_code(text: str) -> str | None:
    stripped = text.strip()
    if re.fullmatch(r"[A-Za-z0-9]{6}", stripped):
        return stripped.upper()
    if not stripped.lower().startswith("/link"):
        return None
    parts = stripped.split(maxsplit=1)
    if len(parts) < 2:
        return ""
    return parts[1].strip().upper()


def _parse_project_command(text: str) -> tuple[str, str] | None:
    stripped = text.strip()
    if not stripped.startswith("/"):
        return None
    parts = stripped.split(maxsplit=1)
    command = parts[0].lower()
    value = parts[1].strip() if len(parts) > 1 else ""
    if command in {"/connect", "/deploy", "/projects", "/status", "/new", "/build", "/files"}:
        return command, value
    return None


def _looks_like_build_request(text: str) -> bool:
    lower = text.lower()
    keyword_hits = (
        "create a website",
        "make a website",
        "build a website",
        "build an app",
        "build a web app",
        "web app",
        "landing page",
        "portfolio",
        "dashboard",
        "sweet shop",
        "ecommerce",
        "deploy it",
        "production ready",
        "weather app",
        "weather website",
    )
    if any(token in lower for token in keyword_hits):
        return True
    return bool(re.search(r"\b(build|create|make|design)\b.+\b(app|website|site|dashboard|landing page)\b", lower))


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
        mission_runner: MissionRunner,
    ) -> None:
        self.settings = settings
        self.store = store
        self.transport = transport
        self.orchestrator = orchestrator
        self.executor = executor
        self.profile_summary_agent = profile_summary_agent
        self.mission_runner = mission_runner

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

        link_code = _extract_link_code(text)
        if link_code is not None:
            if not link_code:
                await self.transport.send_status_message(
                    chat_id,
                    "Send /link CODE from Telegram after generating a code in the Forge website.",
                )
                await self.store.complete_message_job(job.id or "", result_preview="Missing Telegram link code.")
                return

            link = await self.store.consume_link_token(
                code=link_code,
                telegram_user_id=user_id,
                telegram_username=username,
            )
            if link is None:
                await self.transport.send_status_message(
                    chat_id,
                    "That link code is invalid or expired. Generate a fresh code in the Forge website and try again.",
                )
                await self.store.complete_message_job(job.id or "", result_preview="Invalid Telegram link code.")
                return

            await self.store.ensure_user_profile(link.workspace_user_id, link.web_email or username)
            await self.transport.send_status_message(
                chat_id,
                "Telegram is now connected to your Forge website workspace. Future bot messages will share that memory.",
            )
            await self.store.complete_message_job(job.id or "", result_preview="Telegram account linked.")
            return

        parsed_command = _parse_project_command(text)
        if parsed_command is not None:
            result_preview = await self._handle_command(
                chat_id=chat_id,
                user_id=user_id,
                username=username,
                command=parsed_command[0],
                value=parsed_command[1],
            )
            await self.store.complete_message_job(job.id or "", result_preview=result_preview)
            return

        if _looks_like_build_request(text) and not photo_sizes:
            link = await self.store.get_account_link_for_telegram(user_id)
            workspace_user_id = link.workspace_user_id if link is not None else user_id
            await self.store.ensure_user_profile(workspace_user_id, link.web_email if link else username)
            await self.store.append_conversation(ConversationRecord(user_id=workspace_user_id, role="user", content=text))
            status_message_id = await self.transport.send_status_message(chat_id, "Forge queued your build mission...")
            mission = await self.store.create_mission(
                MissionRecord(
                    workspace_user_id=workspace_user_id,
                    chat_id=chat_id,
                    source="telegram",
                    kind="build",
                    prompt=text,
                )
            )
            mission = await self.mission_runner.run_mission(mission.id or "")
            await self.transport.edit_status_message(chat_id, status_message_id, mission.response_text or "Build completed.")
            await self.store.complete_message_job(job.id or "", result_preview=mission.result_summary or "Build completed.")
            return

        status_message_id = await self.transport.send_status_message(chat_id, "Forge is assembling the right agents...")
        await self.store.attach_status_message(job.id or "", status_message_id)

        link = await self.store.get_account_link_for_telegram(user_id)
        workspace_user_id = link.workspace_user_id if link is not None else user_id

        await self.store.ensure_user_profile(workspace_user_id, link.web_email if link else username)
        profile = await self.store.get_user_profile(workspace_user_id)
        history = await self.store.get_recent_conversations(workspace_user_id, limit=self.settings.history_window)

        await self.store.append_conversation(ConversationRecord(user_id=workspace_user_id, role="user", content=text))

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
                user_id=workspace_user_id,
                role="assistant",
                content=delivery.text,
                agents_used=[name for stage in plan.stages for name in stage.agents],
            )
        )
        await self.store.complete_message_job(job.id or "", result_preview=delivery.text[:240])

        asyncio.create_task(self.refresh_profile(workspace_user_id, link.web_email if link else username))

    async def _handle_command(
        self,
        *,
        chat_id: int,
        user_id: int,
        username: str | None,
        command: str,
        value: str,
    ) -> str:
        link = await self.store.get_account_link_for_telegram(user_id)
        workspace_user_id = link.workspace_user_id if link is not None else user_id
        await self.store.ensure_user_profile(workspace_user_id, link.web_email if link else username)

        if command == "/status":
            mission = await self.store.create_mission(
                MissionRecord(
                    workspace_user_id=workspace_user_id,
                    chat_id=chat_id,
                    source="telegram",
                    kind="status",
                    prompt="status",
                )
            )
            mission = await self.mission_runner.run_mission(mission.id or "")
            await self.transport.send_status_message(chat_id, mission.response_text or "Status ready.")
            return mission.result_summary or "Status ready."

        if command == "/projects":
            projects = await self.store.list_projects(workspace_user_id)
            if not projects:
                text = "No projects yet. Use /new PROJECT_NAME or send a build request."
            else:
                text = "\n".join(f"- {item.slug}: {item.archetype}" for item in projects[:12])
            await self.transport.send_status_message(chat_id, text)
            return text[:240]

        if command == "/connect":
            provider = value.lower().strip()
            if provider not in {"github", "vercel"}:
                text = "Use /connect github or /connect vercel."
                await self.transport.send_status_message(chat_id, text)
                return text
            try:
                url = self.mission_runner.integrations.build_authorize_url(provider, workspace_user_id=workspace_user_id)
            except OAuthError as exc:
                await self.transport.send_status_message(chat_id, str(exc))
                return str(exc)
            text = f"Open this link to connect {provider.title()}:\n{url}"
            await self.transport.send_status_message(chat_id, text)
            return text[:240]

        if command == "/new":
            name = value or "Forge Project"
            await self.store.append_conversation(
                ConversationRecord(user_id=workspace_user_id, role="user", content=f"/new {name}")
            )
            mission = await self.store.create_mission(
                MissionRecord(
                    workspace_user_id=workspace_user_id,
                    chat_id=chat_id,
                    source="telegram",
                    kind="build",
                    prompt=f"Build a production-ready app called {name}",
                )
            )
            mission = await self.mission_runner.run_mission(mission.id or "")
            await self.transport.send_status_message(chat_id, mission.response_text or "Project created.")
            return mission.result_summary or "Project created."

        if command == "/build":
            await self.store.append_conversation(
                ConversationRecord(user_id=workspace_user_id, role="user", content=f"/build {value}")
            )
            mission = await self.store.create_mission(
                MissionRecord(
                    workspace_user_id=workspace_user_id,
                    chat_id=chat_id,
                    source="telegram",
                    kind="build",
                    prompt=value or "Build a production-ready app",
                )
            )
            mission = await self.mission_runner.run_mission(mission.id or "")
            await self.transport.send_status_message(chat_id, mission.response_text or "Build completed.")
            return mission.result_summary or "Build completed."

        if command == "/deploy":
            project = await self.store.get_project_by_name(workspace_user_id, value)
            if project is None:
                text = "Project not found. Use /projects to list available project slugs."
                await self.transport.send_status_message(chat_id, text)
                return text
            await self.store.append_conversation(
                ConversationRecord(user_id=workspace_user_id, role="user", content=f"/deploy {value}")
            )
            mission = await self.store.create_mission(
                MissionRecord(
                    workspace_user_id=workspace_user_id,
                    chat_id=chat_id,
                    source="telegram",
                    kind="deploy",
                    prompt=f"Deploy {project.name}",
                    project_id=project.id,
                )
            )
            mission = await self.mission_runner.run_mission(mission.id or "")
            await self.transport.send_status_message(chat_id, mission.response_text or "Deployment processed.")
            return mission.result_summary or "Deployment processed."

        if command == "/files":
            project = await self.store.get_project_by_name(workspace_user_id, value)
            if project is None:
                text = "Project not found. Use /projects to list available project slugs."
            else:
                text = "\n".join(f"- {name}" for name in sorted((project.latest_manifest or {}).keys())[:50])
            await self.transport.send_status_message(chat_id, text)
            return text[:240]

        fallback = "Unsupported command."
        await self.transport.send_status_message(chat_id, fallback)
        return fallback

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
