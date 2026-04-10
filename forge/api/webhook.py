from __future__ import annotations

import hashlib
from pathlib import Path
from urllib.parse import quote_plus

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from forge.config import Settings
from forge.integrations import OAuthError
from forge.memory import MemoryStore
from forge.memory.context import build_user_context
from forge.project_bundle import build_project_bundle
from forge.schemas import ConversationRecord, MessageJob, MissionRecord, UserProfile
from forge.supabase_auth import SupabaseAuthError


UI_DIR = Path(__file__).resolve().parents[2] / "frontend"
UI_HTML_PATH = UI_DIR / "index.html"


class DemoPlanRequest(BaseModel):
    prompt: str


class EmailPasswordRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)


class AppPlanRequest(BaseModel):
    prompt: str


class AppRunRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)


class LinkTelegramRequest(BaseModel):
    refresh: bool = False


class MissionRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=8000)
    kind: str = Field(default="build")


class DeployRequest(BaseModel):
    project_id: str


class VercelTokenConnectRequest(BaseModel):
    token: str = Field(min_length=10, max_length=5000)


def _extract_message(raw_update: dict) -> dict | None:
    for key in ("message", "edited_message", "channel_post", "edited_channel_post"):
        if raw_update.get(key):
            return raw_update[key]
    return None


def _derive_workspace_user_id(user: dict[str, object]) -> int:
    raw = str(user.get("id") or user.get("email") or user.get("phone") or "forge-web-user")
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return -(int(digest[:15], 16) or 1)


def _serialize_delivery(payload) -> dict[str, object]:
    document_text = payload.document_bytes.decode("utf-8") if payload.document_bytes else None
    return {
        "text": payload.text,
        "document_name": payload.document_name,
        "document_text": document_text,
    }


def _serialize_auth_session(result: dict[str, object]) -> dict[str, object] | None:
    nested_session = result.get("session")
    if isinstance(nested_session, dict):
        return nested_session

    access_token = result.get("access_token")
    if not access_token:
        return None

    return {
        "access_token": access_token,
        "refresh_token": result.get("refresh_token"),
        "expires_in": result.get("expires_in"),
        "token_type": result.get("token_type"),
    }


async def _project_detail_payload(store: MemoryStore, project_id: str) -> dict[str, object] | None:
    project = await store.get_project(project_id)
    if project is None:
        return None
    revisions = await store.list_project_revisions(project_id)
    latest_revision = revisions[0] if revisions else None
    manifest = latest_revision.file_manifest if latest_revision is not None else (project.latest_manifest or {})
    bundle_name = latest_revision.bundle_name if latest_revision is not None else None
    return {
        "project": project.model_dump(mode="json"),
        "latest_revision": latest_revision.model_dump(mode="json") if latest_revision else None,
        "files": sorted(manifest.keys()),
        "manifest": manifest,
        "download_name": bundle_name,
        "download_url": f"/api/app/projects/{project_id}/download",
        "preview_url": project.preview_url,
        "publish_urls": {
            "github": f"/api/app/projects/{project_id}/publish/github",
            "vercel": f"/api/app/projects/{project_id}/publish/vercel",
        },
    }


def build_router(*, settings: Settings, store: MemoryStore) -> APIRouter:
    router = APIRouter()

    def integration_redirect(provider: str, *, status: str, message: str | None = None, account: str | None = None) -> str:
        params = [f"integration={quote_plus(provider)}", f"status={quote_plus(status)}"]
        if account:
            params.append(f"account={quote_plus(account)}")
        if message:
            params.append(f"message={quote_plus(message)}")
        return f"{settings.frontend_base_url.rstrip('/')}?{'&'.join(params)}#/dashboard"

    def bearer_token_from_request(request: Request) -> str:
        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            raise HTTPException(status_code=401, detail="Missing bearer token.")
        return header.removeprefix("Bearer ").strip()

    async def authenticate_workspace_request(
        request: Request,
    ) -> tuple[dict[str, object], str, int, str, UserProfile]:
        auth_client = request.app.state.auth_client
        token = bearer_token_from_request(request)
        try:
            user = await auth_client.get_user(access_token=token)
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        web_user_id = str(user.get("id") or user.get("email") or user.get("phone") or "forge-web-user")
        workspace_user_id = _derive_workspace_user_id(user)
        link = await request.app.state.store.get_account_link_for_web(web_user_id)
        if link is not None:
            workspace_user_id = link.workspace_user_id
        username = str(user.get("email") or user.get("id") or "forge-user")
        await request.app.state.store.ensure_user_profile(workspace_user_id, username)
        profile = await request.app.state.store.get_user_profile(workspace_user_id)
        return user, web_user_id, workspace_user_id, username, profile

    @router.get("/", response_class=HTMLResponse)
    async def index() -> HTMLResponse:
        return HTMLResponse(UI_HTML_PATH.read_text(encoding="utf-8"))

    @router.get("/ui/{asset_name}")
    async def ui_asset(asset_name: str) -> FileResponse:
        asset_path = (UI_DIR / asset_name).resolve()
        if asset_path.parent != UI_DIR.resolve() or not asset_path.exists() or not asset_path.is_file():
            raise HTTPException(status_code=404, detail="Asset not found.")
        return FileResponse(asset_path)

    @router.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @router.get("/api/client-config")
    async def client_config(request: Request) -> dict[str, object]:
        auth_client = request.app.state.auth_client
        figma_templates = request.app.state.figma.list_templates()
        return {
            "auth_enabled": auth_client.is_configured,
            "auth_provider": "supabase",
            "app_name": "Forge",
            "telegram_bot_username": settings.telegram_bot_username,
            "integrations": {
                "github": request.app.state.integrations.is_provider_configured("github"),
                "vercel": request.app.state.integrations.is_provider_configured("vercel"),
                "figma": any(item.frame_url for item in figma_templates),
            },
            "figma_templates": [
                {
                    "key": item.key,
                    "name": item.name,
                    "archetype": item.archetype,
                    "description": item.description,
                    "configured": bool(item.frame_url),
                    "frame_url": item.frame_url,
                }
                for item in figma_templates
            ],
        }

    @router.post("/api/auth/signup")
    async def sign_up(payload: EmailPasswordRequest, request: Request) -> dict[str, object]:
        auth_client = request.app.state.auth_client
        try:
            result = await auth_client.sign_up(email=payload.email, password=payload.password)
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        session = _serialize_auth_session(result)

        return {
            "user": result.get("user"),
            "session": session,
            "message": (
                "Account created. Check your inbox if email confirmation is enabled."
                if session is None
                else "Account created and signed in."
            ),
        }

    @router.post("/api/auth/signin")
    async def sign_in(payload: EmailPasswordRequest, request: Request) -> dict[str, object]:
        auth_client = request.app.state.auth_client
        try:
            result = await auth_client.sign_in(email=payload.email, password=payload.password)
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

        return {
            "user": result.get("user"),
            "session": _serialize_auth_session(result),
            "message": "Signed in successfully.",
        }

    @router.get("/api/auth/session")
    async def session(request: Request) -> dict[str, object]:
        auth_client = request.app.state.auth_client
        token = bearer_token_from_request(request)
        try:
            user = await auth_client.get_user(access_token=token)
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        return {"user": user}

    @router.post("/api/auth/signout")
    async def sign_out(request: Request) -> dict[str, bool]:
        auth_client = request.app.state.auth_client
        token = bearer_token_from_request(request)
        try:
            await auth_client.sign_out(access_token=token)
        except SupabaseAuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        return {"ok": True}

    @router.post("/demo/plan")
    async def demo_plan(payload: DemoPlanRequest, request: Request) -> dict:
        plan = await request.app.state.orchestrator.plan(
            payload.prompt,
            history=[],
            profile=UserProfile(user_id=0, username="demo"),
            has_image=False,
        )
        return {"plan": plan.model_dump(mode="json")}

    @router.post("/api/app/plan")
    async def app_plan(payload: AppPlanRequest, request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, username, profile = await authenticate_workspace_request(request)

        plan = await request.app.state.orchestrator.plan(
            payload.prompt,
            history=[],
            profile=UserProfile(
                user_id=workspace_user_id,
                username=username,
                summary=profile.summary,
                stack=profile.stack,
                skill_level=profile.skill_level,
                current_projects=profile.current_projects,
                preferences=profile.preferences,
                active_context=profile.active_context,
            ),
            has_image=False,
        )
        return {"user": user, "plan": plan.model_dump(mode="json")}

    @router.get("/api/app/dashboard")
    async def app_dashboard(request: Request) -> dict[str, object]:
        user, web_user_id, workspace_user_id, _username, profile = await authenticate_workspace_request(request)
        history = await request.app.state.store.get_recent_conversations(workspace_user_id, limit=12)
        link = await request.app.state.store.get_account_link_for_web(web_user_id)
        token = await request.app.state.store.get_active_link_token(web_user_id)
        projects = await request.app.state.store.list_projects(workspace_user_id)
        missions = await request.app.state.store.list_missions(workspace_user_id, limit=10)
        integrations = await request.app.state.store.list_oauth_connections(workspace_user_id)
        figma_templates = request.app.state.figma.list_templates()
        return {
            "user": user,
            "profile": profile.model_dump(mode="json"),
            "history": [item.model_dump(mode="json") for item in history],
            "projects": [item.model_dump(mode="json") for item in projects],
            "missions": [item.model_dump(mode="json") for item in missions],
            "integrations": [item.model_dump(mode="json", exclude={"access_token_encrypted", "refresh_token_encrypted"}) for item in integrations],
            "figma_templates": [
                {
                    "key": item.key,
                    "name": item.name,
                    "archetype": item.archetype,
                    "description": item.description,
                    "configured": bool(item.frame_url),
                    "frame_url": item.frame_url,
                }
                for item in figma_templates
            ],
            "telegram_link": {
                "linked": link is not None,
                "telegram_user_id": link.telegram_user_id if link else None,
                "telegram_username": link.telegram_username if link else None,
                "bot_username": settings.telegram_bot_username,
                "pending_code": token.code if token else None,
                "pending_expires_at": token.expires_at if token else None,
            },
        }

    @router.get("/api/figma/templates")
    async def figma_templates(request: Request) -> dict[str, object]:
        _user, _web_user_id, _workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        templates = request.app.state.figma.list_templates()
        return {
            "templates": [
                {
                    "key": item.key,
                    "name": item.name,
                    "archetype": item.archetype,
                    "description": item.description,
                    "configured": bool(item.frame_url),
                    "frame_url": item.frame_url,
                }
                for item in templates
            ]
        }

    @router.post("/api/app/link/telegram")
    async def app_link_telegram(payload: LinkTelegramRequest, request: Request) -> dict[str, object]:
        user, web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        existing = await request.app.state.store.get_active_link_token(web_user_id)
        if existing is not None and not payload.refresh:
            token = existing
        else:
            token = await request.app.state.store.create_link_token(
                web_user_id=web_user_id,
                workspace_user_id=workspace_user_id,
                web_email=str(user.get("email") or ""),
                expires_in_seconds=600,
            )
        link = await request.app.state.store.get_account_link_for_web(web_user_id)
        return {
            "linked": link is not None,
            "telegram_user_id": link.telegram_user_id if link else None,
            "telegram_username": link.telegram_username if link else None,
            "bot_username": settings.telegram_bot_username,
            "code": token.code,
            "expires_at": token.expires_at,
            "message": "Send /link CODE to the Forge Telegram bot to connect this workspace.",
        }

    @router.get("/api/integrations/{provider}/start")
    async def integration_start(provider: str, request: Request):
        _user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        if provider not in {"github", "vercel"}:
            raise HTTPException(status_code=404, detail="Unknown provider.")
        if provider == "vercel":
            if not request.app.state.integrations.is_provider_configured("vercel"):
                raise HTTPException(status_code=400, detail="Vercel OAuth is not configured.")
            state = request.app.state.integrations.state_codec.encode(
                {"provider": "vercel", "workspace_user_id": workspace_user_id}
            )
            response = RedirectResponse(
                url=f"https://vercel.com/integrations/{settings.vercel_integration_slug}",
                status_code=302,
            )
            response.set_cookie(
                "forge_vercel_oauth_state",
                state,
                max_age=600,
                httponly=True,
                samesite="lax",
                secure=request.url.scheme == "https",
            )
            return response
        try:
            authorize_url = request.app.state.integrations.build_authorize_url(provider, workspace_user_id=workspace_user_id)
        except OAuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RedirectResponse(url=authorize_url, status_code=302)

    @router.get("/api/integrations/{provider}/callback")
    async def integration_callback(provider: str, code: str, request: Request, state: str | None = None) -> RedirectResponse:
        resolved_state = state
        if provider == "vercel" and not resolved_state:
            resolved_state = request.cookies.get("forge_vercel_oauth_state")
        if not resolved_state:
            return RedirectResponse(
                url=integration_redirect(provider, status="error", message="Connection expired. Start the connect flow again."),
                status_code=302,
            )
        try:
            connection = await request.app.state.integrations.complete_oauth(provider, code=code, state=resolved_state)
        except OAuthError as exc:
            response = RedirectResponse(
                url=integration_redirect(provider, status="error", message=str(exc) or "Connection failed."),
                status_code=302,
            )
            if provider == "vercel":
                response.delete_cookie("forge_vercel_oauth_state")
            return response
        response = RedirectResponse(
            url=integration_redirect(
                provider,
                status="connected",
                account=connection.account_name or connection.account_id,
                message=f"{provider.title()} connected successfully.",
            ),
            status_code=302,
        )
        if provider == "vercel":
            response.delete_cookie("forge_vercel_oauth_state")
        return response

    @router.post("/api/integrations/vercel/token")
    async def connect_vercel_token(payload: VercelTokenConnectRequest, request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        try:
            connection = await request.app.state.integrations.connect_vercel_token(
                workspace_user_id=workspace_user_id,
                token=payload.token,
            )
        except OAuthError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {
            "user": user,
            "connection": connection.model_dump(mode="json", exclude={"access_token_encrypted", "refresh_token_encrypted"}),
            "message": f"Vercel connected as {connection.account_name or connection.account_id}.",
        }

    @router.get("/api/app/projects")
    async def app_projects(request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        projects = await request.app.state.store.list_projects(workspace_user_id)
        return {"user": user, "projects": [item.model_dump(mode="json") for item in projects]}

    @router.get("/api/app/projects/{project_id}")
    async def app_project_detail(project_id: str, request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        detail = await _project_detail_payload(request.app.state.store, project_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        project = detail["project"]
        if not isinstance(project, dict) or project.get("workspace_user_id") != workspace_user_id:
            raise HTTPException(status_code=404, detail="Project not found.")
        return {"user": user, **detail}

    @router.get("/api/app/projects/{project_id}/files")
    async def app_project_files(project_id: str, request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        detail = await _project_detail_payload(request.app.state.store, project_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        project = detail["project"]
        if not isinstance(project, dict) or project.get("workspace_user_id") != workspace_user_id:
            raise HTTPException(status_code=404, detail="Project not found.")
        return {
            "user": user,
            "project": project,
            "files": detail["files"],
            "manifest": detail["manifest"],
        }

    @router.get("/api/app/projects/{project_id}/download")
    async def app_project_download(project_id: str, request: Request) -> Response:
        _user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        detail = await _project_detail_payload(request.app.state.store, project_id)
        if detail is None:
            raise HTTPException(status_code=404, detail="Project not found.")
        project = detail["project"]
        if not isinstance(project, dict) or project.get("workspace_user_id") != workspace_user_id:
            raise HTTPException(status_code=404, detail="Project not found.")
        manifest = detail["manifest"]
        if not isinstance(manifest, dict) or not manifest:
            raise HTTPException(status_code=400, detail="Project has no files.")
        bundle_name, bundle_bytes = build_project_bundle(str(project.get("slug") or "forge-project"), manifest)
        return Response(
            content=bundle_bytes,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{bundle_name}"'},
        )

    @router.post("/api/app/projects/{project_id}/preview")
    async def app_project_preview(project_id: str, request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        project = await request.app.state.store.get_project(project_id)
        if project is None or project.workspace_user_id != workspace_user_id:
            raise HTTPException(status_code=404, detail="Project not found.")
        try:
            refreshed = await request.app.state.mission_runner.refresh_project_preview(
                workspace_user_id=workspace_user_id,
                project_id=project_id,
            )
        except RuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"user": user, "project": refreshed.model_dump(mode="json")}

    @router.get("/api/app/missions")
    async def app_missions(request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        missions = await request.app.state.store.list_missions(workspace_user_id, limit=20)
        return {"user": user, "missions": [item.model_dump(mode="json") for item in missions]}

    @router.post("/api/app/missions")
    async def app_create_mission(payload: MissionRequest, request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        mission = await request.app.state.mission_runner.enqueue_web_mission(
            workspace_user_id=workspace_user_id,
            prompt=payload.prompt,
            kind=payload.kind,
        )
        import asyncio

        asyncio.create_task(request.app.state.mission_runner.run_mission(mission.id or ""))
        return {"user": user, "mission": mission.model_dump(mode="json")}

    @router.get("/api/app/missions/{mission_id}")
    async def app_get_mission(mission_id: str, request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        mission = await request.app.state.store.get_mission(mission_id)
        if mission is None or mission.workspace_user_id != workspace_user_id:
            raise HTTPException(status_code=404, detail="Mission not found.")
        return {"user": user, "mission": mission.model_dump(mode="json")}

    @router.post("/api/app/deploy")
    async def app_deploy(payload: DeployRequest, request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        project = await request.app.state.store.get_project(payload.project_id)
        if project is None or project.workspace_user_id != workspace_user_id:
            raise HTTPException(status_code=404, detail="Project not found.")
        mission = await request.app.state.store.create_mission(
            MissionRecord(
                workspace_user_id=workspace_user_id,
                source="web",
                kind="publish",
                prompt=f"Publish {project.name} to vercel",
                project_id=project.id,
                plan={"target": "vercel"},
            )
        )
        import asyncio

        asyncio.create_task(request.app.state.mission_runner.run_mission(mission.id or ""))
        return {"user": user, "mission": mission.model_dump(mode="json")}

    @router.post("/api/app/projects/{project_id}/publish/github")
    async def app_publish_github(project_id: str, request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        project = await request.app.state.store.get_project(project_id)
        if project is None or project.workspace_user_id != workspace_user_id:
            raise HTTPException(status_code=404, detail="Project not found.")
        mission = await request.app.state.store.create_mission(
            MissionRecord(
                workspace_user_id=workspace_user_id,
                source="web",
                kind="publish",
                prompt=f"Publish {project.name} to github",
                project_id=project.id,
                plan={"target": "github"},
            )
        )
        import asyncio

        asyncio.create_task(request.app.state.mission_runner.run_mission(mission.id or ""))
        return {"user": user, "mission": mission.model_dump(mode="json")}

    @router.post("/api/app/projects/{project_id}/publish/vercel")
    async def app_publish_vercel(project_id: str, request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, _username, _profile = await authenticate_workspace_request(request)
        project = await request.app.state.store.get_project(project_id)
        if project is None or project.workspace_user_id != workspace_user_id:
            raise HTTPException(status_code=404, detail="Project not found.")
        mission = await request.app.state.store.create_mission(
            MissionRecord(
                workspace_user_id=workspace_user_id,
                source="web",
                kind="publish",
                prompt=f"Publish {project.name} to vercel",
                project_id=project.id,
                plan={"target": "vercel"},
            )
        )
        import asyncio

        asyncio.create_task(request.app.state.mission_runner.run_mission(mission.id or ""))
        return {"user": user, "mission": mission.model_dump(mode="json")}

    @router.post("/api/app/run")
    async def app_run(payload: AppRunRequest, request: Request) -> dict[str, object]:
        user, _web_user_id, workspace_user_id, username, profile = await authenticate_workspace_request(request)
        await request.app.state.store.append_conversation(
            ConversationRecord(user_id=workspace_user_id, role="user", content=payload.prompt)
        )
        mission = await request.app.state.mission_runner.enqueue_web_mission(
            workspace_user_id=workspace_user_id,
            prompt=payload.prompt,
            kind="build",
        )
        import asyncio

        asyncio.create_task(request.app.state.mission_runner.run_mission(mission.id or ""))
        refreshed_profile = await request.app.state.store.get_user_profile(workspace_user_id)
        refreshed_history = await request.app.state.store.get_recent_conversations(workspace_user_id, limit=12)
        return {
            "user": user,
            "profile": refreshed_profile.model_dump(mode="json"),
            "history": [item.model_dump(mode="json") for item in refreshed_history],
            "mission": mission.model_dump(mode="json"),
            "message": "Mission queued. Forge will keep running it in the background.",
        }

    @router.post("/webhook")
    async def webhook(
        request: Request,
        x_telegram_bot_api_secret_token: str | None = Header(default=None),
    ) -> dict[str, bool]:
        if settings.webhook_secret and x_telegram_bot_api_secret_token != settings.webhook_secret:
            raise HTTPException(status_code=403, detail="Invalid secret.")

        payload = await request.json()
        message = _extract_message(payload)
        if not message:
            return {"ok": True}

        chat = message.get("chat") or {}
        user = message.get("from") or {}
        user_id = user.get("id") or chat.get("id")
        chat_id = chat.get("id") or user_id
        update_id = payload.get("update_id")
        if update_id is None or user_id is None or chat_id is None:
            return {"ok": True}

        await store.enqueue_message_job(
            MessageJob(
                telegram_update_id=int(update_id),
                user_id=int(user_id),
                chat_id=int(chat_id),
                raw_update=payload,
            )
        )
        return {"ok": True}

    return router
