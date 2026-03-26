from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import secrets
from typing import Any
from uuid import uuid4

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


class InMemoryStore(MemoryStore):
    def __init__(self) -> None:
        self._profiles: dict[int, UserProfile] = {}
        self._conversations: list[ConversationRecord] = []
        self._jobs: dict[str, MessageJob] = {}
        self._job_ids_by_update: dict[int, str] = {}
        self._account_links_by_web: dict[str, AccountLink] = {}
        self._account_links_by_telegram: dict[int, AccountLink] = {}
        self._link_tokens: dict[str, LinkToken] = {}
        self._oauth_connections: dict[tuple[int, str], OAuthConnection] = {}
        self._projects: dict[str, ProjectRecord] = {}
        self._project_revisions: dict[str, ProjectRevision] = {}
        self._deployments: dict[str, DeploymentRecord] = {}
        self._missions: dict[str, MissionRecord] = {}
        self._lock = asyncio.Lock()

    async def ensure_user_profile(self, user_id: int, username: str | None = None) -> UserProfile:
        async with self._lock:
            profile = self._profiles.get(user_id)
            if profile is None:
                profile = UserProfile(user_id=user_id, username=username)
                self._profiles[user_id] = profile
            elif username and profile.username != username:
                profile.username = username
            return profile.model_copy(deep=True)

    async def get_user_profile(self, user_id: int) -> UserProfile:
        profile = self._profiles.get(user_id)
        if profile is None:
            profile = UserProfile(user_id=user_id)
            self._profiles[user_id] = profile
        return profile.model_copy(deep=True)

    async def get_recent_conversations(self, user_id: int, *, limit: int) -> list[ConversationRecord]:
        records = [record for record in self._conversations if record.user_id == user_id]
        return [item.model_copy(deep=True) for item in records[-limit:]]

    async def append_conversation(self, record: ConversationRecord) -> ConversationRecord:
        stored = record.model_copy(deep=True)
        stored.id = stored.id or str(uuid4())
        stored.created_at = stored.created_at or datetime.now(tz=UTC)
        self._conversations.append(stored)
        profile = self._profiles.get(record.user_id)
        if profile is not None:
            profile.message_count += 1
            profile.last_seen = datetime.now(tz=UTC)
        return stored.model_copy(deep=True)

    async def enqueue_message_job(self, job: MessageJob) -> MessageJob:
        async with self._lock:
            existing_id = self._job_ids_by_update.get(job.telegram_update_id)
            if existing_id:
                return self._jobs[existing_id].model_copy(deep=True)
            stored = job.model_copy(deep=True)
            stored.id = stored.id or str(uuid4())
            stored.status = "queued"
            stored.created_at = stored.created_at or datetime.now(tz=UTC)
            stored.updated_at = stored.created_at
            self._jobs[stored.id] = stored
            self._job_ids_by_update[stored.telegram_update_id] = stored.id
            return stored.model_copy(deep=True)

    async def claim_message_jobs(self, *, worker_id: str, limit: int, lock_timeout_seconds: int) -> list[MessageJob]:
        now = datetime.now(tz=UTC)
        claimed: list[MessageJob] = []
        async with self._lock:
            jobs = sorted(self._jobs.values(), key=lambda item: item.created_at or now)
            for job in jobs:
                available = job.available_at or datetime.min.replace(tzinfo=UTC)
                stale_lock = job.status == "running" and job.locked_at and job.locked_at < now - timedelta(seconds=lock_timeout_seconds)
                claimable = (job.status in {"queued", "retrying"} and available <= now) or stale_lock
                if not claimable:
                    continue
                job.status = "running"
                job.locked_by = worker_id
                job.locked_at = now
                job.updated_at = now
                claimed.append(job.model_copy(deep=True))
                if len(claimed) >= limit:
                    break
        return claimed

    async def update_message_job_pipeline(self, job_id: str, pipeline: dict[str, Any]) -> None:
        job = self._jobs[job_id]
        job.pipeline = pipeline
        job.updated_at = datetime.now(tz=UTC)

    async def attach_status_message(self, job_id: str, status_message_id: int) -> None:
        job = self._jobs[job_id]
        job.status_message_id = status_message_id
        job.updated_at = datetime.now(tz=UTC)

    async def complete_message_job(self, job_id: str, *, result_preview: str) -> MessageJob:
        job = self._jobs[job_id]
        job.status = "completed"
        job.result_preview = result_preview
        job.locked_at = None
        job.locked_by = None
        job.error = None
        job.updated_at = datetime.now(tz=UTC)
        return job.model_copy(deep=True)

    async def fail_message_job(
        self,
        job_id: str,
        *,
        error: str,
        max_attempts: int,
        retry_delay_seconds: int,
    ) -> MessageJob:
        job = self._jobs[job_id]
        job.attempts += 1
        job.error = error
        job.locked_at = None
        job.locked_by = None
        if job.attempts >= max_attempts:
            job.status = "dead_letter"
            job.available_at = None
        else:
            job.status = "retrying"
            job.available_at = datetime.now(tz=UTC) + timedelta(seconds=retry_delay_seconds * job.attempts)
        job.updated_at = datetime.now(tz=UTC)
        return job.model_copy(deep=True)

    async def update_user_profile(self, user_id: int, updates: dict[str, Any]) -> UserProfile:
        profile = self._profiles.get(user_id) or UserProfile(user_id=user_id)
        merged = profile.model_dump()
        for key, value in updates.items():
            if value is None:
                continue
            merged[key] = value
        updated = UserProfile.model_validate(merged)
        updated.last_context_refresh = datetime.now(tz=UTC)
        self._profiles[user_id] = updated
        return updated.model_copy(deep=True)

    async def get_account_link_for_web(self, web_user_id: str) -> AccountLink | None:
        link = self._account_links_by_web.get(web_user_id)
        return link.model_copy(deep=True) if link else None

    async def get_account_link_for_telegram(self, telegram_user_id: int) -> AccountLink | None:
        link = self._account_links_by_telegram.get(telegram_user_id)
        return link.model_copy(deep=True) if link else None

    async def get_account_link_for_workspace(self, workspace_user_id: int) -> AccountLink | None:
        for link in self._account_links_by_web.values():
            if link.workspace_user_id == workspace_user_id:
                return link.model_copy(deep=True)
        return None

    async def create_link_token(
        self,
        *,
        web_user_id: str,
        workspace_user_id: int,
        web_email: str | None,
        expires_in_seconds: int,
    ) -> LinkToken:
        now = datetime.now(tz=UTC)
        for code, token in list(self._link_tokens.items()):
            if token.web_user_id == web_user_id and token.consumed_at is None and token.expires_at > now:
                return token.model_copy(deep=True)

        code = secrets.token_hex(3).upper()
        token = LinkToken(
            code=code,
            web_user_id=web_user_id,
            workspace_user_id=workspace_user_id,
            web_email=web_email,
            expires_at=now + timedelta(seconds=expires_in_seconds),
            created_at=now,
            updated_at=now,
        )
        self._link_tokens[code] = token
        return token.model_copy(deep=True)

    async def get_active_link_token(self, web_user_id: str) -> LinkToken | None:
        now = datetime.now(tz=UTC)
        for token in sorted(self._link_tokens.values(), key=lambda item: item.created_at or now, reverse=True):
            if token.web_user_id == web_user_id and token.consumed_at is None and token.expires_at > now:
                return token.model_copy(deep=True)
        return None

    async def consume_link_token(
        self,
        *,
        code: str,
        telegram_user_id: int,
        telegram_username: str | None,
    ) -> AccountLink | None:
        now = datetime.now(tz=UTC)
        token = self._link_tokens.get(code.strip().upper())
        if token is None or token.consumed_at is not None or token.expires_at <= now:
            return None

        token.consumed_at = now
        token.telegram_user_id = telegram_user_id
        token.telegram_username = telegram_username
        token.updated_at = now

        existing = self._account_links_by_telegram.get(telegram_user_id)
        if existing is not None and existing.web_user_id != token.web_user_id:
            self._account_links_by_web.pop(existing.web_user_id, None)

        link = AccountLink(
            web_user_id=token.web_user_id,
            workspace_user_id=token.workspace_user_id,
            web_email=token.web_email,
            telegram_user_id=telegram_user_id,
            telegram_username=telegram_username,
            created_at=now,
            updated_at=now,
        )
        self._account_links_by_web[token.web_user_id] = link
        self._account_links_by_telegram[telegram_user_id] = link
        return link.model_copy(deep=True)

    async def upsert_oauth_connection(self, connection: OAuthConnection) -> OAuthConnection:
        async with self._lock:
            stored = connection.model_copy(deep=True)
            stored.id = stored.id or str(uuid4())
            now = datetime.now(tz=UTC)
            existing = self._oauth_connections.get((stored.workspace_user_id, stored.provider))
            stored.created_at = existing.created_at if existing and existing.created_at else stored.created_at or now
            stored.updated_at = now
            self._oauth_connections[(stored.workspace_user_id, stored.provider)] = stored
            return stored.model_copy(deep=True)

    async def get_oauth_connection(self, workspace_user_id: int, provider: str) -> OAuthConnection | None:
        item = self._oauth_connections.get((workspace_user_id, provider))
        return item.model_copy(deep=True) if item else None

    async def list_oauth_connections(self, workspace_user_id: int) -> list[OAuthConnection]:
        items = [item for item in self._oauth_connections.values() if item.workspace_user_id == workspace_user_id]
        return [item.model_copy(deep=True) for item in items]

    async def create_project(self, project: ProjectRecord) -> ProjectRecord:
        async with self._lock:
            stored = project.model_copy(deep=True)
            now = datetime.now(tz=UTC)
            stored.id = stored.id or str(uuid4())
            stored.created_at = stored.created_at or now
            stored.updated_at = now
            self._projects[stored.id] = stored
            return stored.model_copy(deep=True)

    async def update_project(self, project_id: str, updates: dict[str, Any]) -> ProjectRecord:
        async with self._lock:
            project = self._projects[project_id]
            data = project.model_dump(mode="json")
            for key, value in updates.items():
                if value is not None:
                    data[key] = value
            updated = ProjectRecord.model_validate(data)
            updated.id = project.id
            updated.created_at = project.created_at
            updated.updated_at = datetime.now(tz=UTC)
            self._projects[project_id] = updated
            return updated.model_copy(deep=True)

    async def get_project(self, project_id: str) -> ProjectRecord | None:
        project = self._projects.get(project_id)
        return project.model_copy(deep=True) if project else None

    async def get_project_by_name(self, workspace_user_id: int, name: str) -> ProjectRecord | None:
        target = name.strip().lower()
        for project in self._projects.values():
            if project.workspace_user_id == workspace_user_id and (
                project.name.lower() == target or project.slug.lower() == target
            ):
                return project.model_copy(deep=True)
        return None

    async def list_projects(self, workspace_user_id: int) -> list[ProjectRecord]:
        items = [item for item in self._projects.values() if item.workspace_user_id == workspace_user_id]
        items.sort(key=lambda item: item.updated_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return [item.model_copy(deep=True) for item in items]

    async def create_project_revision(self, revision: ProjectRevision) -> ProjectRevision:
        async with self._lock:
            stored = revision.model_copy(deep=True)
            stored.id = stored.id or str(uuid4())
            stored.created_at = stored.created_at or datetime.now(tz=UTC)
            self._project_revisions[stored.id] = stored
            return stored.model_copy(deep=True)

    async def list_project_revisions(self, project_id: str) -> list[ProjectRevision]:
        items = [item for item in self._project_revisions.values() if item.project_id == project_id]
        items.sort(key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return [item.model_copy(deep=True) for item in items]

    async def create_deployment(self, deployment: DeploymentRecord) -> DeploymentRecord:
        async with self._lock:
            stored = deployment.model_copy(deep=True)
            now = datetime.now(tz=UTC)
            stored.id = stored.id or str(uuid4())
            stored.created_at = stored.created_at or now
            stored.updated_at = now
            self._deployments[stored.id] = stored
            return stored.model_copy(deep=True)

    async def update_deployment(self, deployment_id: str, updates: dict[str, Any]) -> DeploymentRecord:
        async with self._lock:
            deployment = self._deployments[deployment_id]
            data = deployment.model_dump(mode="json")
            for key, value in updates.items():
                if value is not None:
                    data[key] = value
            updated = DeploymentRecord.model_validate(data)
            updated.id = deployment.id
            updated.created_at = deployment.created_at
            updated.updated_at = datetime.now(tz=UTC)
            self._deployments[deployment_id] = updated
            return updated.model_copy(deep=True)

    async def list_deployments(self, project_id: str) -> list[DeploymentRecord]:
        items = [item for item in self._deployments.values() if item.project_id == project_id]
        items.sort(key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return [item.model_copy(deep=True) for item in items]

    async def create_mission(self, mission: MissionRecord) -> MissionRecord:
        async with self._lock:
            stored = mission.model_copy(deep=True)
            now = datetime.now(tz=UTC)
            stored.id = stored.id or str(uuid4())
            stored.created_at = stored.created_at or now
            stored.updated_at = now
            self._missions[stored.id] = stored
            return stored.model_copy(deep=True)

    async def get_mission(self, mission_id: str) -> MissionRecord | None:
        mission = self._missions.get(mission_id)
        return mission.model_copy(deep=True) if mission else None

    async def list_missions(self, workspace_user_id: int, *, limit: int) -> list[MissionRecord]:
        items = [item for item in self._missions.values() if item.workspace_user_id == workspace_user_id]
        items.sort(key=lambda item: item.created_at or datetime.min.replace(tzinfo=UTC), reverse=True)
        return [item.model_copy(deep=True) for item in items[:limit]]

    async def claim_missions(self, *, worker_id: str, limit: int, lock_timeout_seconds: int) -> list[MissionRecord]:
        now = datetime.now(tz=UTC)
        claimed: list[MissionRecord] = []
        async with self._lock:
            for mission in sorted(self._missions.values(), key=lambda item: item.created_at or now):
                stale_lock = mission.status in {"planning", "building", "reviewing", "deploying"} and mission.updated_at and (
                    mission.updated_at < now - timedelta(seconds=lock_timeout_seconds)
                )
                if mission.status != "queued" and not stale_lock:
                    continue
                mission.status = "planning"
                mission.updated_at = now
                mission.plan["claimed_by"] = worker_id
                claimed.append(mission.model_copy(deep=True))
                if len(claimed) >= limit:
                    break
        return claimed

    async def update_mission(self, mission_id: str, updates: dict[str, Any]) -> MissionRecord:
        async with self._lock:
            mission = self._missions[mission_id]
            data = mission.model_dump(mode="json")
            for key, value in updates.items():
                if value is not None:
                    data[key] = value
            updated = MissionRecord.model_validate(data)
            updated.id = mission.id
            updated.created_at = mission.created_at
            updated.updated_at = datetime.now(tz=UTC)
            if updated.status == "completed" and updated.completed_at is None:
                updated.completed_at = updated.updated_at
            self._missions[mission_id] = updated
            return updated.model_copy(deep=True)
