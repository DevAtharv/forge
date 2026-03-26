from __future__ import annotations

import logging
from typing import Any, Awaitable, Callable, TypeVar

from forge.memory.base import MemoryStore
from forge.schemas import (
    AccountLink,
    ConversationRecord,
    DeploymentRecord,
    LinkToken,
    MessageJob,
    MissionRecord,
    OAuthConnection,
    ProjectRecord,
    ProjectRevision,
    UserProfile,
)

T = TypeVar("T")

logger = logging.getLogger(__name__)


class ResilientMemoryStore(MemoryStore):
    def __init__(self, *, primary: MemoryStore, fallback: MemoryStore) -> None:
        self._primary = primary
        self._fallback = fallback

    async def _call_with_fallback(
        self,
        action: str,
        primary_call: Callable[[], Awaitable[T]],
        fallback_call: Callable[[], Awaitable[T]],
    ) -> T:
        try:
            return await primary_call()
        except Exception as exc:
            logger.warning("Primary memory store failed during %s; using fallback store: %s", action, exc)
            return await fallback_call()

    async def ensure_user_profile(self, user_id: int, username: str | None = None) -> UserProfile:
        return await self._call_with_fallback(
            "ensure_user_profile",
            lambda: self._primary.ensure_user_profile(user_id, username),
            lambda: self._fallback.ensure_user_profile(user_id, username),
        )

    async def get_user_profile(self, user_id: int) -> UserProfile:
        return await self._call_with_fallback(
            "get_user_profile",
            lambda: self._primary.get_user_profile(user_id),
            lambda: self._fallback.get_user_profile(user_id),
        )

    async def get_recent_conversations(self, user_id: int, *, limit: int) -> list[ConversationRecord]:
        return await self._call_with_fallback(
            "get_recent_conversations",
            lambda: self._primary.get_recent_conversations(user_id, limit=limit),
            lambda: self._fallback.get_recent_conversations(user_id, limit=limit),
        )

    async def append_conversation(self, record: ConversationRecord) -> ConversationRecord:
        return await self._call_with_fallback(
            "append_conversation",
            lambda: self._primary.append_conversation(record),
            lambda: self._fallback.append_conversation(record),
        )

    async def enqueue_message_job(self, job: MessageJob) -> MessageJob:
        return await self._call_with_fallback(
            "enqueue_message_job",
            lambda: self._primary.enqueue_message_job(job),
            lambda: self._fallback.enqueue_message_job(job),
        )

    async def claim_message_jobs(self, *, worker_id: str, limit: int, lock_timeout_seconds: int) -> list[MessageJob]:
        return await self._call_with_fallback(
            "claim_message_jobs",
            lambda: self._primary.claim_message_jobs(
                worker_id=worker_id,
                limit=limit,
                lock_timeout_seconds=lock_timeout_seconds,
            ),
            lambda: self._fallback.claim_message_jobs(
                worker_id=worker_id,
                limit=limit,
                lock_timeout_seconds=lock_timeout_seconds,
            ),
        )

    async def update_message_job_pipeline(self, job_id: str, pipeline: dict[str, Any]) -> None:
        await self._call_with_fallback(
            "update_message_job_pipeline",
            lambda: self._primary.update_message_job_pipeline(job_id, pipeline),
            lambda: self._fallback.update_message_job_pipeline(job_id, pipeline),
        )

    async def attach_status_message(self, job_id: str, status_message_id: int) -> None:
        await self._call_with_fallback(
            "attach_status_message",
            lambda: self._primary.attach_status_message(job_id, status_message_id),
            lambda: self._fallback.attach_status_message(job_id, status_message_id),
        )

    async def complete_message_job(self, job_id: str, *, result_preview: str) -> MessageJob:
        return await self._call_with_fallback(
            "complete_message_job",
            lambda: self._primary.complete_message_job(job_id, result_preview=result_preview),
            lambda: self._fallback.complete_message_job(job_id, result_preview=result_preview),
        )

    async def fail_message_job(
        self,
        job_id: str,
        *,
        error: str,
        max_attempts: int,
        retry_delay_seconds: int,
    ) -> MessageJob:
        return await self._call_with_fallback(
            "fail_message_job",
            lambda: self._primary.fail_message_job(
                job_id,
                error=error,
                max_attempts=max_attempts,
                retry_delay_seconds=retry_delay_seconds,
            ),
            lambda: self._fallback.fail_message_job(
                job_id,
                error=error,
                max_attempts=max_attempts,
                retry_delay_seconds=retry_delay_seconds,
            ),
        )

    async def update_user_profile(self, user_id: int, updates: dict[str, Any]) -> UserProfile:
        return await self._call_with_fallback(
            "update_user_profile",
            lambda: self._primary.update_user_profile(user_id, updates),
            lambda: self._fallback.update_user_profile(user_id, updates),
        )

    async def get_account_link_for_web(self, web_user_id: str) -> AccountLink | None:
        return await self._call_with_fallback(
            "get_account_link_for_web",
            lambda: self._primary.get_account_link_for_web(web_user_id),
            lambda: self._fallback.get_account_link_for_web(web_user_id),
        )

    async def get_account_link_for_telegram(self, telegram_user_id: int) -> AccountLink | None:
        return await self._call_with_fallback(
            "get_account_link_for_telegram",
            lambda: self._primary.get_account_link_for_telegram(telegram_user_id),
            lambda: self._fallback.get_account_link_for_telegram(telegram_user_id),
        )

    async def get_account_link_for_workspace(self, workspace_user_id: int) -> AccountLink | None:
        return await self._call_with_fallback(
            "get_account_link_for_workspace",
            lambda: self._primary.get_account_link_for_workspace(workspace_user_id),
            lambda: self._fallback.get_account_link_for_workspace(workspace_user_id),
        )

    async def create_link_token(
        self,
        *,
        web_user_id: str,
        workspace_user_id: int,
        web_email: str | None,
        expires_in_seconds: int,
    ) -> LinkToken:
        return await self._call_with_fallback(
            "create_link_token",
            lambda: self._primary.create_link_token(
                web_user_id=web_user_id,
                workspace_user_id=workspace_user_id,
                web_email=web_email,
                expires_in_seconds=expires_in_seconds,
            ),
            lambda: self._fallback.create_link_token(
                web_user_id=web_user_id,
                workspace_user_id=workspace_user_id,
                web_email=web_email,
                expires_in_seconds=expires_in_seconds,
            ),
        )

    async def get_active_link_token(self, web_user_id: str) -> LinkToken | None:
        return await self._call_with_fallback(
            "get_active_link_token",
            lambda: self._primary.get_active_link_token(web_user_id),
            lambda: self._fallback.get_active_link_token(web_user_id),
        )

    async def consume_link_token(
        self,
        *,
        code: str,
        telegram_user_id: int,
        telegram_username: str | None,
    ) -> AccountLink | None:
        return await self._call_with_fallback(
            "consume_link_token",
            lambda: self._primary.consume_link_token(
                code=code,
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
            ),
            lambda: self._fallback.consume_link_token(
                code=code,
                telegram_user_id=telegram_user_id,
                telegram_username=telegram_username,
            ),
        )

    async def close(self) -> None:
        try:
            await self._primary.close()
        finally:
            await self._fallback.close()

    async def upsert_oauth_connection(self, connection: OAuthConnection) -> OAuthConnection:
        return await self._call_with_fallback(
            "upsert_oauth_connection",
            lambda: self._primary.upsert_oauth_connection(connection),
            lambda: self._fallback.upsert_oauth_connection(connection),
        )

    async def get_oauth_connection(self, workspace_user_id: int, provider: str) -> OAuthConnection | None:
        return await self._call_with_fallback(
            "get_oauth_connection",
            lambda: self._primary.get_oauth_connection(workspace_user_id, provider),
            lambda: self._fallback.get_oauth_connection(workspace_user_id, provider),
        )

    async def list_oauth_connections(self, workspace_user_id: int) -> list[OAuthConnection]:
        return await self._call_with_fallback(
            "list_oauth_connections",
            lambda: self._primary.list_oauth_connections(workspace_user_id),
            lambda: self._fallback.list_oauth_connections(workspace_user_id),
        )

    async def create_project(self, project: ProjectRecord) -> ProjectRecord:
        return await self._call_with_fallback(
            "create_project",
            lambda: self._primary.create_project(project),
            lambda: self._fallback.create_project(project),
        )

    async def update_project(self, project_id: str, updates: dict[str, Any]) -> ProjectRecord:
        return await self._call_with_fallback(
            "update_project",
            lambda: self._primary.update_project(project_id, updates),
            lambda: self._fallback.update_project(project_id, updates),
        )

    async def get_project(self, project_id: str) -> ProjectRecord | None:
        return await self._call_with_fallback(
            "get_project",
            lambda: self._primary.get_project(project_id),
            lambda: self._fallback.get_project(project_id),
        )

    async def get_project_by_name(self, workspace_user_id: int, name: str) -> ProjectRecord | None:
        return await self._call_with_fallback(
            "get_project_by_name",
            lambda: self._primary.get_project_by_name(workspace_user_id, name),
            lambda: self._fallback.get_project_by_name(workspace_user_id, name),
        )

    async def list_projects(self, workspace_user_id: int) -> list[ProjectRecord]:
        return await self._call_with_fallback(
            "list_projects",
            lambda: self._primary.list_projects(workspace_user_id),
            lambda: self._fallback.list_projects(workspace_user_id),
        )

    async def create_project_revision(self, revision: ProjectRevision) -> ProjectRevision:
        return await self._call_with_fallback(
            "create_project_revision",
            lambda: self._primary.create_project_revision(revision),
            lambda: self._fallback.create_project_revision(revision),
        )

    async def list_project_revisions(self, project_id: str) -> list[ProjectRevision]:
        return await self._call_with_fallback(
            "list_project_revisions",
            lambda: self._primary.list_project_revisions(project_id),
            lambda: self._fallback.list_project_revisions(project_id),
        )

    async def create_deployment(self, deployment: DeploymentRecord) -> DeploymentRecord:
        return await self._call_with_fallback(
            "create_deployment",
            lambda: self._primary.create_deployment(deployment),
            lambda: self._fallback.create_deployment(deployment),
        )

    async def update_deployment(self, deployment_id: str, updates: dict[str, Any]) -> DeploymentRecord:
        return await self._call_with_fallback(
            "update_deployment",
            lambda: self._primary.update_deployment(deployment_id, updates),
            lambda: self._fallback.update_deployment(deployment_id, updates),
        )

    async def list_deployments(self, project_id: str) -> list[DeploymentRecord]:
        return await self._call_with_fallback(
            "list_deployments",
            lambda: self._primary.list_deployments(project_id),
            lambda: self._fallback.list_deployments(project_id),
        )

    async def create_mission(self, mission: MissionRecord) -> MissionRecord:
        return await self._call_with_fallback(
            "create_mission",
            lambda: self._primary.create_mission(mission),
            lambda: self._fallback.create_mission(mission),
        )

    async def get_mission(self, mission_id: str) -> MissionRecord | None:
        mission = await self._call_with_fallback(
            "get_mission",
            lambda: self._primary.get_mission(mission_id),
            lambda: self._fallback.get_mission(mission_id),
        )
        if mission is not None:
            return mission
        return await self._fallback.get_mission(mission_id)

    async def list_missions(self, workspace_user_id: int, *, limit: int) -> list[MissionRecord]:
        return await self._call_with_fallback(
            "list_missions",
            lambda: self._primary.list_missions(workspace_user_id, limit=limit),
            lambda: self._fallback.list_missions(workspace_user_id, limit=limit),
        )

    async def claim_missions(self, *, worker_id: str, limit: int, lock_timeout_seconds: int) -> list[MissionRecord]:
        return await self._call_with_fallback(
            "claim_missions",
            lambda: self._primary.claim_missions(
                worker_id=worker_id,
                limit=limit,
                lock_timeout_seconds=lock_timeout_seconds,
            ),
            lambda: self._fallback.claim_missions(
                worker_id=worker_id,
                limit=limit,
                lock_timeout_seconds=lock_timeout_seconds,
            ),
        )

    async def update_mission(self, mission_id: str, updates: dict[str, Any]) -> MissionRecord:
        return await self._call_with_fallback(
            "update_mission",
            lambda: self._primary.update_mission(mission_id, updates),
            lambda: self._fallback.update_mission(mission_id, updates),
        )
