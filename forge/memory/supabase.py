from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from forge.memory.base import MemoryStore
from forge.schemas import AccountLink, ConversationRecord, LinkToken, MessageJob, UserProfile


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

    async def _rpc(self, name: str, payload: dict[str, Any]) -> Any:
        response = await self._client.post(f"/rpc/{name}", json=payload)
        response.raise_for_status()
        return response.json()

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
        response = await self._client.post("/conversations", json=record.model_dump(mode="json"))
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
        data = await self._rpc(
            "complete_message_job",
            {"p_job_id": job_id, "p_result_preview": result_preview},
        )
        return MessageJob.model_validate(data)

    async def fail_message_job(
        self,
        job_id: str,
        *,
        error: str,
        max_attempts: int,
        retry_delay_seconds: int,
    ) -> MessageJob:
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
