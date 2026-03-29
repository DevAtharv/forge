from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import httpx

from forge.config import Settings
from forge.memory import MemoryStore
from forge.schemas import OAuthConnection
from forge.security import SecretBox, SignedStateCodec


class OAuthError(RuntimeError):
    pass


@dataclass(frozen=True)
class OAuthProviderConfig:
    name: str
    client_id: str
    client_secret: str
    authorize_url: str
    token_url: str
    scopes: tuple[str, ...]


class IntegrationService:
    def __init__(self, *, settings: Settings, store: MemoryStore) -> None:
        self.settings = settings
        self.store = store
        self.secret_box = SecretBox(settings.credential_secret)
        self.state_codec = SignedStateCodec(settings.credential_secret)
        self._client = httpx.AsyncClient(timeout=settings.fetch_timeout_seconds)
        self._provider_configs = {
            "github": OAuthProviderConfig(
                name="github",
                client_id=settings.github_client_id,
                client_secret=settings.github_client_secret,
                authorize_url="https://github.com/login/oauth/authorize",
                token_url="https://github.com/login/oauth/access_token",
                scopes=("repo", "read:user", "user:email"),
            ),
            "vercel": OAuthProviderConfig(
                name="vercel",
                client_id=settings.vercel_client_id,
                client_secret=settings.vercel_client_secret,
                authorize_url="https://vercel.com/oauth/authorize",
                token_url="https://api.vercel.com/v2/oauth/access_token",
                scopes=("projects:write", "deployments:write", "user:read"),
            ),
        }

    def is_provider_configured(self, provider: str) -> bool:
        config = self._provider_configs[provider]
        return bool(config.client_id and config.client_secret)

    def build_authorize_url(self, provider: str, *, workspace_user_id: int) -> str:
        config = self._provider_configs[provider]
        if not self.is_provider_configured(provider):
            raise OAuthError(f"{provider.title()} OAuth is not configured.")
        if provider == "vercel":
            if not self.settings.vercel_integration_slug:
                raise OAuthError("Vercel integration slug is not configured.")
            state = self.state_codec.encode({"provider": provider, "workspace_user_id": workspace_user_id})
            return (
                f"{self.settings.public_base_url.rstrip('/')}/api/integrations/vercel/start"
                f"?state={state}"
            )
        redirect_uri = f"{self.settings.public_base_url.rstrip('/')}/api/integrations/{provider}/callback"
        state = self.state_codec.encode({"provider": provider, "workspace_user_id": workspace_user_id})
        params = {
            "client_id": config.client_id,
            "redirect_uri": redirect_uri,
            "scope": " ".join(config.scopes),
            "state": state,
        }
        request = httpx.Request("GET", config.authorize_url, params=params)
        return str(request.url)

    async def complete_oauth(self, provider: str, *, code: str, state: str) -> OAuthConnection:
        payload = self.state_codec.decode(state)
        if payload.get("provider") != provider:
            raise OAuthError("OAuth provider mismatch.")
        workspace_user_id = int(payload["workspace_user_id"])
        config = self._provider_configs[provider]
        redirect_uri = f"{self.settings.public_base_url.rstrip('/')}/api/integrations/{provider}/callback"

        if provider == "github":
            token_response = await self._client.post(
                config.token_url,
                headers={"Accept": "application/json"},
                data={
                    "client_id": config.client_id,
                    "client_secret": config.client_secret,
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "state": state,
                },
            )
            token_response.raise_for_status()
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            if not access_token:
                raise OAuthError("GitHub token exchange failed.")
            user = await self._client.get(
                "https://api.github.com/user",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            user.raise_for_status()
            user_data = user.json()
            scopes = [item for item in (token_data.get("scope") or "").split(",") if item]
            connection = OAuthConnection(
                workspace_user_id=workspace_user_id,
                provider="github",
                account_id=str(user_data["id"]),
                account_name=user_data.get("login"),
                access_token_encrypted=self.secret_box.encrypt(access_token),
                refresh_token_encrypted=None,
                scopes=scopes,
                metadata={"login": user_data.get("login"), "avatar_url": user_data.get("avatar_url")},
            )
            return await self.store.upsert_oauth_connection(connection)

        token_response = await self._client.post(
            config.token_url,
            json={
                "client_id": config.client_id,
                "client_secret": config.client_secret,
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )
        token_response.raise_for_status()
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            raise OAuthError("Vercel token exchange failed.")
        user = await self._client.get(
            "https://api.vercel.com/v2/user",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        user.raise_for_status()
        user_data = user.json().get("user", user.json())
        connection = OAuthConnection(
            workspace_user_id=workspace_user_id,
            provider="vercel",
            account_id=str(user_data.get("id") or user_data.get("uid") or ""),
            account_name=user_data.get("username") or user_data.get("name"),
            access_token_encrypted=self.secret_box.encrypt(access_token),
            refresh_token_encrypted=(
                self.secret_box.encrypt(token_data["refresh_token"]) if token_data.get("refresh_token") else None
            ),
            scopes=list(config.scopes),
            metadata={"team_id": token_data.get("teamId")},
        )
        return await self.store.upsert_oauth_connection(connection)

    async def get_decrypted_connection(self, workspace_user_id: int, provider: str) -> tuple[OAuthConnection, str]:
        connection = await self.store.get_oauth_connection(workspace_user_id, provider)
        if connection is None:
            raise OAuthError(f"{provider.title()} is not connected for this workspace.")
        return connection, self.secret_box.decrypt(connection.access_token_encrypted)

    async def close(self) -> None:
        await self._client.aclose()


class GitHubRepoClient:
    def __init__(self, token: str) -> None:
        self._token = token
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com",
            timeout=20,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )

    async def get_current_user(self) -> dict[str, Any]:
        response = await self._client.get("/user")
        response.raise_for_status()
        return response.json()

    async def ensure_repo(self, name: str, *, private: bool = False) -> dict[str, Any]:
        user = await self.get_current_user()
        owner = user["login"]
        existing = await self._client.get(f"/repos/{owner}/{name}")
        if existing.status_code == 200:
            return existing.json()
        if existing.status_code not in {404}:
            existing.raise_for_status()
        response = await self._client.post(
            "/user/repos",
            json={"name": name, "private": private, "auto_init": True},
        )
        response.raise_for_status()
        return response.json()

    async def upsert_files(self, *, owner: str, repo: str, files: dict[str, str], branch: str = "main") -> list[str]:
        changed: list[str] = []
        for path, content in files.items():
            sha = None
            existing = await self._client.get(f"/repos/{owner}/{repo}/contents/{path}", params={"ref": branch})
            if existing.status_code == 200:
                sha = existing.json().get("sha")
            elif existing.status_code not in {404}:
                existing.raise_for_status()
            response = await self._client.put(
                f"/repos/{owner}/{repo}/contents/{path}",
                json={
                    "message": f"Forge update {path}",
                    "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
                    "branch": branch,
                    **({"sha": sha} if sha else {}),
                },
            )
            response.raise_for_status()
            changed.append(path)
        return changed

    async def close(self) -> None:
        await self._client.aclose()


class VercelDeployClient:
    def __init__(self, token: str) -> None:
        self._client = httpx.AsyncClient(
            base_url="https://api.vercel.com",
            timeout=30,
            headers={"Authorization": f"Bearer {token}"},
        )

    async def deploy_files(self, *, project_name: str, files: dict[str, str]) -> dict[str, Any]:
        payload = {
            "name": project_name,
            "files": [{"file": path, "data": content} for path, content in files.items()],
            "projectSettings": {"framework": None},
        }
        response = await self._client.post("/v13/deployments", json=payload)
        response.raise_for_status()
        return response.json()

    async def close(self) -> None:
        await self._client.aclose()
