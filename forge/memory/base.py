from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

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


class MemoryStore(ABC):
    @abstractmethod
    async def ensure_user_profile(self, user_id: int, username: str | None = None) -> UserProfile:
        raise NotImplementedError

    @abstractmethod
    async def get_user_profile(self, user_id: int) -> UserProfile:
        raise NotImplementedError

    @abstractmethod
    async def get_recent_conversations(self, user_id: int, *, limit: int) -> list[ConversationRecord]:
        raise NotImplementedError

    @abstractmethod
    async def append_conversation(self, record: ConversationRecord) -> ConversationRecord:
        raise NotImplementedError

    @abstractmethod
    async def enqueue_message_job(self, job: MessageJob) -> MessageJob:
        raise NotImplementedError

    @abstractmethod
    async def claim_message_jobs(self, *, worker_id: str, limit: int, lock_timeout_seconds: int) -> list[MessageJob]:
        raise NotImplementedError

    @abstractmethod
    async def update_message_job_pipeline(self, job_id: str, pipeline: dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    async def attach_status_message(self, job_id: str, status_message_id: int) -> None:
        raise NotImplementedError

    @abstractmethod
    async def complete_message_job(self, job_id: str, *, result_preview: str) -> MessageJob:
        raise NotImplementedError

    @abstractmethod
    async def fail_message_job(
        self,
        job_id: str,
        *,
        error: str,
        max_attempts: int,
        retry_delay_seconds: int,
    ) -> MessageJob:
        raise NotImplementedError

    @abstractmethod
    async def update_user_profile(self, user_id: int, updates: dict[str, Any]) -> UserProfile:
        raise NotImplementedError

    @abstractmethod
    async def get_account_link_for_web(self, web_user_id: str) -> AccountLink | None:
        raise NotImplementedError

    @abstractmethod
    async def get_account_link_for_telegram(self, telegram_user_id: int) -> AccountLink | None:
        raise NotImplementedError

    @abstractmethod
    async def get_account_link_for_workspace(self, workspace_user_id: int) -> AccountLink | None:
        raise NotImplementedError

    @abstractmethod
    async def create_link_token(
        self,
        *,
        web_user_id: str,
        workspace_user_id: int,
        web_email: str | None,
        expires_in_seconds: int,
    ) -> LinkToken:
        raise NotImplementedError

    @abstractmethod
    async def get_active_link_token(self, web_user_id: str) -> LinkToken | None:
        raise NotImplementedError

    @abstractmethod
    async def consume_link_token(
        self,
        *,
        code: str,
        telegram_user_id: int,
        telegram_username: str | None,
    ) -> AccountLink | None:
        raise NotImplementedError

    async def close(self) -> None:
        return None

    @abstractmethod
    async def upsert_oauth_connection(self, connection: OAuthConnection) -> OAuthConnection:
        raise NotImplementedError

    @abstractmethod
    async def get_oauth_connection(self, workspace_user_id: int, provider: str) -> OAuthConnection | None:
        raise NotImplementedError

    @abstractmethod
    async def list_oauth_connections(self, workspace_user_id: int) -> list[OAuthConnection]:
        raise NotImplementedError

    @abstractmethod
    async def create_project(self, project: ProjectRecord) -> ProjectRecord:
        raise NotImplementedError

    @abstractmethod
    async def update_project(self, project_id: str, updates: dict[str, Any]) -> ProjectRecord:
        raise NotImplementedError

    @abstractmethod
    async def get_project(self, project_id: str) -> ProjectRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def get_project_by_name(self, workspace_user_id: int, name: str) -> ProjectRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def list_projects(self, workspace_user_id: int) -> list[ProjectRecord]:
        raise NotImplementedError

    @abstractmethod
    async def create_project_revision(self, revision: ProjectRevision) -> ProjectRevision:
        raise NotImplementedError

    @abstractmethod
    async def update_project_revision(self, revision_id: str, updates: dict[str, Any]) -> ProjectRevision:
        raise NotImplementedError

    @abstractmethod
    async def list_project_revisions(self, project_id: str) -> list[ProjectRevision]:
        raise NotImplementedError

    @abstractmethod
    async def create_deployment(self, deployment: DeploymentRecord) -> DeploymentRecord:
        raise NotImplementedError

    @abstractmethod
    async def update_deployment(self, deployment_id: str, updates: dict[str, Any]) -> DeploymentRecord:
        raise NotImplementedError

    @abstractmethod
    async def list_deployments(self, project_id: str) -> list[DeploymentRecord]:
        raise NotImplementedError

    @abstractmethod
    async def create_mission(self, mission: MissionRecord) -> MissionRecord:
        raise NotImplementedError

    @abstractmethod
    async def get_mission(self, mission_id: str) -> MissionRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def list_missions(self, workspace_user_id: int, *, limit: int) -> list[MissionRecord]:
        raise NotImplementedError

    @abstractmethod
    async def claim_missions(self, *, worker_id: str, limit: int, lock_timeout_seconds: int) -> list[MissionRecord]:
        raise NotImplementedError

    @abstractmethod
    async def update_mission(self, mission_id: str, updates: dict[str, Any]) -> MissionRecord:
        raise NotImplementedError
