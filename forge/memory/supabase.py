from __future__ import annotations

from datetime import UTC, datetime, timedelta
import re
from typing import Any

import httpx

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


class SupabaseMemoryStore(MemoryStore):
    def __init__(self, *, url: str, key: str, timeout_seconds: int = 10) -> None:
        self._base_url = f"{url.rstrip('/')}/rest/v1"
        self._key = key
        self._client = httpx.AsyncClient(
            base_url=self._base_url,
            timeout=timeout_seconds,
            headers=self._headers(prefer="return=representation"),
        )

    def _headers(self, *, prefer: str | None = None) -> dict[str, str]:
        headers = {
            "apikey": self._key,
            "Authorization": f"Bearer {self._key}",
            "Content-Type": "application/json",
        }
        if prefer:
            headers["Prefer"] = prefer
        return headers

    @staticmethod
    def _insert_payload(model: Any) -> dict[str, Any]:
        return model.model_dump(mode="json", exclude_none=True)

    async def _rpc(self, name: str, payload: dict[str, Any]) -> Any:
        response = await self._client.post(f"/rpc/{name}", json=payload)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _missing_column_from_error(exc: httpx.HTTPStatusError) -> str | None:
        if exc.response is None:
            return None
        if exc.response.status_code != 400:
            return None
        body = exc.response.text or ""
        if "PGRST204" not in body:
            return None
        match = re.search(r"Could not find the '([^']+)' column", body)
        if not match:
            return None
        return match.group(1)

    async def _patch_with_schema_fallback(
        self,
        path: str,
        *,
        params: dict[str, Any],
        updates: dict[str, Any],
        max_attempts: int = 4,
    ) -> list[dict[str, Any]]:
        payload = dict(updates)
        attempts = 0
        while True:
            response = await self._client.patch(path, params=params, json=payload)
            try:
                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as exc:
                attempts += 1
                missing_column = self._missing_column_from_error(exc)
                if not missing_column or missing_column not in payload or attempts >= max_attempts:
                    raise
                payload.pop(missing_column, None)

    async def _get_message_job(self, job_id: str) -> MessageJob:
        response = await self._client.get(
            "/message_jobs",
            params={"id": f"eq.{job_id}", "select": "*", "limit": 1},
        )
        response.raise_for_status()
        records = response.json()
        if not records:
            raise httpx.HTTPStatusError(
                "Message job not found.",
                request=response.request,
                response=response,
            )
        return MessageJob.model_validate(records[0])

    async def ensure_user_profile(self, user_id: int, username: str | None = None) -> UserProfile:
        profile = await self.get_user_profile(user_id)
        updates: dict[str, Any] = {}
        if username and profile.username != username:
            updates["username"] = username
        if updates:
            return await self.update_user_profile(user_id, updates)
        return profile

    async def get_user_profile(self, user_id: int) -> UserProfile:
        response = await self._client.get(
            "/user_profiles",
            params={"user_id": f"eq.{user_id}", "select": "*", "limit": 1},
        )
        response.raise_for_status()
        records = response.json()
        if records:
            return UserProfile.model_validate(records[0])

        payload = {"user_id": user_id}
        create = await self._client.post(
            "/user_profiles",
            headers=self._headers(prefer="resolution=merge-duplicates,return=representation"),
            json=payload,
        )
        create.raise_for_status()
        return UserProfile.model_validate(create.json()[0])

    async def get_recent_conversations(self, user_id: int, *, limit: int) -> list[ConversationRecord]:
        response = await self._client.get(
            "/conversations",
            params={
                "user_id": f"eq.{user_id}",
                "select": "*",
                "order": "created_at.asc",
                "limit": str(limit),
            },
        )
        response.raise_for_status()
        return [ConversationRecord.model_validate(item) for item in response.json()]

    async def append_conversation(self, record: ConversationRecord) -> ConversationRecord:
        response = await self._client.post("/conversations", json=self._insert_payload(record))
        response.raise_for_status()
        return ConversationRecord.model_validate(response.json()[0])

    async def enqueue_message_job(self, job: MessageJob) -> MessageJob:
        payload = {
            "p_telegram_update_id": job.telegram_update_id,
            "p_user_id": job.user_id,
            "p_chat_id": job.chat_id,
            "p_raw_update": job.raw_update,
        }
        data = await self._rpc("enqueue_message_job", payload)
        return MessageJob.model_validate(data)

    async def claim_message_jobs(self, *, worker_id: str, limit: int, lock_timeout_seconds: int) -> list[MessageJob]:
        data = await self._rpc(
            "claim_message_jobs",
            {
                "p_worker_id": worker_id,
                "p_limit": limit,
                "p_lock_timeout_seconds": lock_timeout_seconds,
            },
        )
        return [MessageJob.model_validate(item) for item in data]

    async def update_message_job_pipeline(self, job_id: str, pipeline: dict[str, Any]) -> None:
        response = await self._client.patch(
            "/message_jobs",
            params={"id": f"eq.{job_id}"},
            json={"pipeline": pipeline},
        )
        response.raise_for_status()

    async def attach_status_message(self, job_id: str, status_message_id: int) -> None:
        response = await self._client.patch(
            "/message_jobs",
            params={"id": f"eq.{job_id}"},
            json={"status_message_id": status_message_id},
        )
        response.raise_for_status()

    async def complete_message_job(self, job_id: str, *, result_preview: str) -> MessageJob:
        try:
            data = await self._rpc(
                "complete_message_job",
                {"p_job_id": job_id, "p_result_preview": result_preview},
            )
            return MessageJob.model_validate(data)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 400:
                raise
            response = await self._client.patch(
                "/message_jobs",
                params={"id": f"eq.{job_id}", "select": "*"},
                json={
                    "status": "completed",
                    "result_preview": result_preview,
                    "locked_at": None,
                    "locked_by": None,
                    "error": None,
                },
            )
            response.raise_for_status()
            return MessageJob.model_validate(response.json()[0])

    async def fail_message_job(
        self,
        job_id: str,
        *,
        error: str,
        max_attempts: int,
        retry_delay_seconds: int,
    ) -> MessageJob:
        try:
            data = await self._rpc(
                "fail_message_job",
                {
                    "p_job_id": job_id,
                    "p_error": error,
                    "p_max_attempts": max_attempts,
                    "p_retry_delay_seconds": retry_delay_seconds,
                },
            )
            return MessageJob.model_validate(data)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code != 400:
                raise
            current = await self._get_message_job(job_id)
            next_attempt = (current.attempts or 0) + 1
            status = "dead_letter" if next_attempt >= max_attempts else "retrying"
            # message_jobs.available_at is NOT NULL — never PATCH null (matches fail_message_job SQL).
            if status == "retrying":
                available_at = datetime.now(tz=UTC) + timedelta(seconds=retry_delay_seconds * next_attempt)
                available_at_str = available_at.isoformat().replace("+00:00", "Z")
            else:
                available_at_str = datetime.now(tz=UTC).isoformat().replace("+00:00", "Z")
            response = await self._client.patch(
                "/message_jobs",
                params={"id": f"eq.{job_id}", "select": "*"},
                json={
                    "attempts": next_attempt,
                    "error": error,
                    "locked_at": None,
                    "locked_by": None,
                    "status": status,
                    "available_at": available_at_str,
                },
            )
            response.raise_for_status()
            return MessageJob.model_validate(response.json()[0])

    async def update_user_profile(self, user_id: int, updates: dict[str, Any]) -> UserProfile:
        payload = {"user_id": user_id, **updates}
        response = await self._client.post(
            "/user_profiles",
            headers=self._headers(prefer="resolution=merge-duplicates,return=representation"),
            json=payload,
        )
        response.raise_for_status()
        return UserProfile.model_validate(response.json()[0])

    async def get_account_link_for_web(self, web_user_id: str) -> AccountLink | None:
        response = await self._client.get(
            "/account_links",
            params={"web_user_id": f"eq.{web_user_id}", "select": "*", "limit": 1},
        )
        response.raise_for_status()
        records = response.json()
        return AccountLink.model_validate(records[0]) if records else None

    async def get_account_link_for_telegram(self, telegram_user_id: int) -> AccountLink | None:
        response = await self._client.get(
            "/account_links",
            params={"telegram_user_id": f"eq.{telegram_user_id}", "select": "*", "limit": 1},
        )
        response.raise_for_status()
        records = response.json()
        return AccountLink.model_validate(records[0]) if records else None

    async def get_account_link_for_workspace(self, workspace_user_id: int) -> AccountLink | None:
        response = await self._client.get(
            "/account_links",
            params={"workspace_user_id": f"eq.{workspace_user_id}", "select": "*", "limit": 1},
        )
        response.raise_for_status()
        records = response.json()
        return AccountLink.model_validate(records[0]) if records else None

    async def create_link_token(
        self,
        *,
        web_user_id: str,
        workspace_user_id: int,
        web_email: str | None,
        expires_in_seconds: int,
    ) -> LinkToken:
        data = await self._rpc(
            "create_link_token",
            {
                "p_web_user_id": web_user_id,
                "p_workspace_user_id": workspace_user_id,
                "p_web_email": web_email,
                "p_expires_in_seconds": expires_in_seconds,
            },
        )
        return LinkToken.model_validate(data)

    async def get_active_link_token(self, web_user_id: str) -> LinkToken | None:
        response = await self._client.get(
            "/link_tokens",
            params={
                "web_user_id": f"eq.{web_user_id}",
                "consumed_at": "is.null",
                "expires_at": f"gt.{datetime.now(tz=UTC).isoformat()}",
                "order": "created_at.desc",
                "limit": 1,
                "select": "*",
            },
        )
        response.raise_for_status()
        records = response.json()
        return LinkToken.model_validate(records[0]) if records else None

    async def consume_link_token(
        self,
        *,
        code: str,
        telegram_user_id: int,
        telegram_username: str | None,
    ) -> AccountLink | None:
        data = await self._rpc(
            "consume_link_token",
            {
                "p_code": code.strip().upper(),
                "p_telegram_user_id": telegram_user_id,
                "p_telegram_username": telegram_username,
            },
        )
        return AccountLink.model_validate(data) if data else None

    async def close(self) -> None:
        await self._client.aclose()

    async def upsert_oauth_connection(self, connection: OAuthConnection) -> OAuthConnection:
        response = await self._client.post(
            "/oauth_connections",
            headers=self._headers(prefer="resolution=merge-duplicates,return=representation"),
            json=self._insert_payload(connection),
        )
        response.raise_for_status()
        return OAuthConnection.model_validate(response.json()[0])

    async def get_oauth_connection(self, workspace_user_id: int, provider: str) -> OAuthConnection | None:
        response = await self._client.get(
            "/oauth_connections",
            params={
                "workspace_user_id": f"eq.{workspace_user_id}",
                "provider": f"eq.{provider}",
                "select": "*",
                "limit": 1,
            },
        )
        response.raise_for_status()
        records = response.json()
        return OAuthConnection.model_validate(records[0]) if records else None

    async def list_oauth_connections(self, workspace_user_id: int) -> list[OAuthConnection]:
        response = await self._client.get(
            "/oauth_connections",
            params={"workspace_user_id": f"eq.{workspace_user_id}", "select": "*"},
        )
        response.raise_for_status()
        return [OAuthConnection.model_validate(item) for item in response.json()]

    async def create_project(self, project: ProjectRecord) -> ProjectRecord:
        response = await self._client.post("/projects", json=self._insert_payload(project))
        response.raise_for_status()
        return ProjectRecord.model_validate(response.json()[0])

    async def update_project(self, project_id: str, updates: dict[str, Any]) -> ProjectRecord:
        rows = await self._patch_with_schema_fallback(
            "/projects",
            params={"id": f"eq.{project_id}", "select": "*"},
            updates=updates,
        )
        return ProjectRecord.model_validate(rows[0])

    async def get_project(self, project_id: str) -> ProjectRecord | None:
        response = await self._client.get(
            "/projects",
            params={"id": f"eq.{project_id}", "select": "*", "limit": 1},
        )
        response.raise_for_status()
        records = response.json()
        return ProjectRecord.model_validate(records[0]) if records else None

    async def get_project_by_name(self, workspace_user_id: int, name: str) -> ProjectRecord | None:
        projects = await self.list_projects(workspace_user_id)
        target = name.strip().lower()
        for project in projects:
            if project.name.lower() == target or project.slug.lower() == target:
                return project
        return None

    async def list_projects(self, workspace_user_id: int) -> list[ProjectRecord]:
        response = await self._client.get(
            "/projects",
            params={
                "workspace_user_id": f"eq.{workspace_user_id}",
                "select": "*",
                "order": "updated_at.desc",
            },
        )
        response.raise_for_status()
        return [ProjectRecord.model_validate(item) for item in response.json()]

    async def create_project_revision(self, revision: ProjectRevision) -> ProjectRevision:
        response = await self._client.post("/project_revisions", json=self._insert_payload(revision))
        response.raise_for_status()
        return ProjectRevision.model_validate(response.json()[0])

    async def update_project_revision(self, revision_id: str, updates: dict[str, Any]) -> ProjectRevision:
        rows = await self._patch_with_schema_fallback(
            "/project_revisions",
            params={"id": f"eq.{revision_id}", "select": "*"},
            updates=updates,
        )
        return ProjectRevision.model_validate(rows[0])

    async def list_project_revisions(self, project_id: str) -> list[ProjectRevision]:
        response = await self._client.get(
            "/project_revisions",
            params={"project_id": f"eq.{project_id}", "select": "*", "order": "created_at.desc"},
        )
        response.raise_for_status()
        return [ProjectRevision.model_validate(item) for item in response.json()]

    async def create_deployment(self, deployment: DeploymentRecord) -> DeploymentRecord:
        response = await self._client.post("/deployments", json=self._insert_payload(deployment))
        response.raise_for_status()
        return DeploymentRecord.model_validate(response.json()[0])

    async def update_deployment(self, deployment_id: str, updates: dict[str, Any]) -> DeploymentRecord:
        response = await self._client.patch(
            "/deployments",
            params={"id": f"eq.{deployment_id}", "select": "*"},
            json=updates,
        )
        response.raise_for_status()
        return DeploymentRecord.model_validate(response.json()[0])

    async def list_deployments(self, project_id: str) -> list[DeploymentRecord]:
        response = await self._client.get(
            "/deployments",
            params={"project_id": f"eq.{project_id}", "select": "*", "order": "created_at.desc"},
        )
        response.raise_for_status()
        return [DeploymentRecord.model_validate(item) for item in response.json()]

    async def create_mission(self, mission: MissionRecord) -> MissionRecord:
        response = await self._client.post("/missions", json=self._insert_payload(mission))
        response.raise_for_status()
        return MissionRecord.model_validate(response.json()[0])

    async def get_mission(self, mission_id: str) -> MissionRecord | None:
        response = await self._client.get(
            "/missions",
            params={"id": f"eq.{mission_id}", "select": "*", "limit": 1},
        )
        response.raise_for_status()
        records = response.json()
        return MissionRecord.model_validate(records[0]) if records else None

    async def list_missions(self, workspace_user_id: int, *, limit: int) -> list[MissionRecord]:
        response = await self._client.get(
            "/missions",
            params={
                "workspace_user_id": f"eq.{workspace_user_id}",
                "select": "*",
                "order": "created_at.desc",
                "limit": str(limit),
            },
        )
        response.raise_for_status()
        return [MissionRecord.model_validate(item) for item in response.json()]

    async def claim_missions(self, *, worker_id: str, limit: int, lock_timeout_seconds: int) -> list[MissionRecord]:
        data = await self._rpc(
            "claim_missions",
            {
                "p_worker_id": worker_id,
                "p_limit": limit,
                "p_lock_timeout_seconds": lock_timeout_seconds,
            },
        )
        return [MissionRecord.model_validate(item) for item in data]

    async def update_mission(self, mission_id: str, updates: dict[str, Any]) -> MissionRecord:
        response = await self._client.patch(
            "/missions",
            params={"id": f"eq.{mission_id}", "select": "*"},
            json=updates,
        )
        response.raise_for_status()
        return MissionRecord.model_validate(response.json()[0])
