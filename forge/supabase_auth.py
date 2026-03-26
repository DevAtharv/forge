from __future__ import annotations

from typing import Any

import httpx


class SupabaseAuthError(RuntimeError):
    def __init__(self, status_code: int, message: str, payload: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload or {}


class SupabaseAuthClient:
    def __init__(self, *, url: str, api_key: str, timeout_seconds: int = 10) -> None:
        self._url = url.rstrip("/")
        self._api_key = api_key
        self._client = (
            httpx.AsyncClient(
                base_url=self._url,
                timeout=timeout_seconds,
                headers={
                    "apikey": self._api_key,
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
            )
            if self.is_configured
            else None
        )

    @property
    def is_configured(self) -> bool:
        return bool(self._url and self._api_key)

    async def sign_up(self, *, email: str, password: str) -> dict[str, Any]:
        return await self._request_json("POST", "/auth/v1/signup", json={"email": email, "password": password})

    async def sign_in(self, *, email: str, password: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/auth/v1/token",
            params={"grant_type": "password"},
            json={"email": email, "password": password},
        )

    async def get_user(self, *, access_token: str) -> dict[str, Any]:
        return await self._request_json(
            "GET",
            "/auth/v1/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    async def sign_out(self, *, access_token: str) -> dict[str, Any]:
        return await self._request_json(
            "POST",
            "/auth/v1/logout",
            headers={"Authorization": f"Bearer {access_token}"},
        )

    async def _request_json(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if self._client is None:
            raise SupabaseAuthError(503, "Supabase auth is not configured.")

        try:
            response = await self._client.request(method, path, json=json, params=params, headers=headers)
        except httpx.TimeoutException as exc:
            raise SupabaseAuthError(504, "Supabase auth request timed out. Please try again.") from exc
        except httpx.RequestError as exc:
            raise SupabaseAuthError(502, "Supabase auth service is temporarily unreachable.") from exc
        try:
            payload = response.json()
        except ValueError:
            payload = {"message": response.text}

        if response.is_error:
            message = (
                payload.get("msg")
                or payload.get("error_description")
                or payload.get("message")
                or payload.get("error")
                or "Supabase auth request failed."
            )
            raise SupabaseAuthError(response.status_code, message, payload)

        return payload

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
