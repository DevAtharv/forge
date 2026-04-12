from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from forge.builder import HybridProjectBuilder, slugify
from forge.figma import FigmaTemplateService
from forge.integrations import GitHubRepoClient, IntegrationService, OAuthError, VercelDeployClient
from forge.memory import MemoryStore
from forge.project_bundle import build_project_bundle
from forge.schemas import (
    Artifact,
    ConversationRecord,
    DeliveryPayload,
    DeploymentRecord,
    MissionRecord,
    ProjectRecord,
    ProjectRevision,
)
from forge.telegram import TelegramTransport


def _artifacts_to_manifest(artifacts: list[Artifact]) -> dict[str, dict[str, str | None]]:
    return {
        item.name: {
            "language": item.language,
            "mime_type": item.mime_type,
            "content": item.content,
        }
        for item in artifacts
    }


def _approval_response_text(action: str, message: str) -> str:
    if action == "connect_github":
        return (
            "Publishing is ready to continue, but Forge needs your GitHub connection first.\n\n"
            f"{message}\n\n"
            "Next step: connect GitHub, then run `/publish github` again."
        )
    if action == "connect_vercel":
        return (
            "Publishing is ready to continue, but Forge needs your Vercel connection first.\n\n"
            f"{message}\n\n"
            "Next step: connect Vercel, then run `/publish vercel` again."
        )
    return message


def _mission_memory_summary(mission: MissionRecord) -> str:
    parts: list[str] = []
    if mission.kind in {"build", "edit"}:
        parts.append(mission.result_summary or "Build completed.")
        if mission.preview_url:
            parts.append(f"Preview: {mission.preview_url}")
    elif mission.kind in {"publish", "deploy"}:
        parts.append(mission.result_summary or "Publish completed.")
        if mission.deployment_url:
            parts.append(f"Deployment: {mission.deployment_url}")
        if mission.repo_url:
            parts.append(f"GitHub: {mission.repo_url}")
    else:
        parts.append(mission.result_summary or mission.response_text or "Mission completed.")
    return "\n".join(parts)


def _normalize_url(value: str | None) -> str | None:
    if not value:
        return None
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://{value}"


def _project_type_label(archetype: str) -> str:
    return archetype.replace("-", " ").title()


@dataclass
class MissionRunner:
    store: MemoryStore
    integrations: IntegrationService
    transport: TelegramTransport
    builder: HybridProjectBuilder
    figma: FigmaTemplateService | None = None

    async def enqueue_web_mission(self, *, workspace_user_id: int, prompt: str, kind: str = "build") -> MissionRecord:
        mission = MissionRecord(
            workspace_user_id=workspace_user_id,
            source="web",
            kind=kind,
            prompt=prompt,
        )
        return await self.store.create_mission(mission)

    async def run_mission(self, mission_id: str) -> MissionRecord:
        mission = await self.store.get_mission(mission_id)
        if mission is None:
            raise RuntimeError("Mission not found.")

        if mission.kind == "status":
            completed = await self._complete_status_mission(mission)
        elif mission.kind in {"build", "edit"}:
            completed = await self._run_generate_mission(mission)
        elif mission.kind in {"publish", "deploy"}:
            completed = await self._run_publish_mission(mission)
        else:
            completed = await self.store.update_mission(
                mission.id or "",
                {
                    "status": "failed",
                    "error": f"Unsupported mission kind: {mission.kind}",
                    "response_text": "Forge could not understand this mission type.",
                },
            )

        await self._persist_mission_memory(completed)
        await self._notify_if_possible(completed)
        return completed

    async def refresh_project_preview(self, *, workspace_user_id: int, project_id: str) -> ProjectRecord:
        project = await self.store.get_project(project_id)
        if project is None or project.workspace_user_id != workspace_user_id:
            raise RuntimeError("Project not found.")

        revision = await self._get_latest_revision(project.id or "")
        if revision is None:
            bundle_name, _bundle_bytes = build_project_bundle(
                project_slug=project.slug,
                manifest=project.latest_manifest or {},
            )
            revision = await self.store.create_project_revision(
                ProjectRevision(
                    project_id=project.id or "",
                    workspace_user_id=workspace_user_id,
                    summary=f"Recovered revision for {project.name}",
                    file_manifest=project.latest_manifest or {},
                    bundle_name=bundle_name,
                    bundle_file_count=len(project.latest_manifest or {}),
                    preview_status="pending",
                )
            )

        preview = await self._deploy_preview_for_revision(project=project, revision=revision)
        return preview["project"]

    async def _run_generate_mission(self, mission: MissionRecord) -> MissionRecord:
        mission = await self.store.update_mission(mission.id or "", {"status": "planning", "approval_request": None})
        project = await self.store.get_project(mission.project_id or "") if mission.project_id else None

        blueprint_prompt = mission.prompt
        if project is not None:
            blueprint_prompt = f"{project.archetype} website update for {project.name}. {mission.prompt}"

        blueprint = self.builder.choose_blueprint(blueprint_prompt, project_name=project.name if project else None)
        artifacts = self.builder.build_files(blueprint, mission.prompt)
        manifest = _artifacts_to_manifest(artifacts)
        bundle_name, _bundle_bytes = build_project_bundle(project_slug=blueprint.slug, manifest=manifest)
        design_source = self._build_design_source(blueprint)

        mission = await self.store.update_mission(
            mission.id or "",
            {
                "status": "building",
                "plan": {
                    "archetype": blueprint.archetype,
                    "project_name": blueprint.project_name,
                    "slug": blueprint.slug,
                    "file_count": len(artifacts),
                    "website_type": _project_type_label(blueprint.archetype),
                    "design_source": design_source,
                },
            },
        )

        project = await self._upsert_project_for_build(mission=mission, blueprint=blueprint, manifest=manifest, project=project)
        revision = await self.store.create_project_revision(
            ProjectRevision(
                project_id=project.id or "",
                workspace_user_id=mission.workspace_user_id,
                mission_id=mission.id,
                summary=self._revision_summary(mission.kind, project.name, len(artifacts)),
                file_manifest=manifest,
                bundle_name=bundle_name,
                bundle_file_count=len(manifest),
                preview_status="pending",
            )
        )

        mission = await self.store.update_mission(
            mission.id or "",
            {
                "project_id": project.id,
                "status": "previewing",
                "changed_files": list(manifest.keys()),
                "bundle_name": bundle_name,
            },
        )

        preview_url = None
        preview_error = None
        try:
            preview_result = await self._deploy_preview_for_revision(project=project, revision=revision)
            project = preview_result["project"]
            revision = preview_result["revision"]
            preview_url = project.preview_url
        except Exception as exc:
            preview_error = str(exc)
            now = datetime.now(tz=UTC)
            project = await self.store.update_project(
                project.id or "",
                {
                    "preview_status": "failed",
                    "preview_updated_at": now,
                    "preview_metadata": {"error": preview_error},
                },
            )
            revision = await self.store.update_project_revision(
                revision.id or "",
                {
                    "preview_status": "failed",
                    "preview_metadata": {"error": preview_error},
                },
            )

        response_text = self._build_generate_response_text(
            project=project,
            mission=mission,
            revision=revision,
            preview_error=preview_error,
        )
        result_summary = (
            f"{'Updated' if mission.kind == 'edit' else 'Built'} {project.name}"
            + ("" if preview_url else " (preview pending)")
        )
        return await self.store.update_mission(
            mission.id or "",
            {
                "status": "completed",
                "result_summary": result_summary,
                "response_text": response_text,
                "preview_url": preview_url,
                "bundle_name": revision.bundle_name,
            },
        )

    async def _run_publish_mission(self, mission: MissionRecord) -> MissionRecord:
        mission = await self.store.update_mission(mission.id or "", {"status": "deploying", "approval_request": None})
        project = await self.store.get_project(mission.project_id or "")
        if project is None:
            return await self.store.update_mission(
                mission.id or "",
                {"status": "failed", "error": "Project not found.", "response_text": "Project not found."},
            )

        manifest = project.latest_manifest or {}
        if not manifest:
            return await self.store.update_mission(
                mission.id or "",
                {"status": "failed", "error": "Project has no saved files.", "response_text": "Project has no saved files."},
            )

        target = self._publish_target_for_mission(mission)
        if target == "github":
            try:
                repo_url = await self._sync_project_repo(mission.workspace_user_id, project, manifest)
            except OAuthError as exc:
                return await self.store.update_mission(
                    mission.id or "",
                    {
                        "status": "awaiting_approval",
                        "approval_request": {"action": "connect_github", "message": str(exc)},
                        "result_summary": "GitHub connection required",
                        "response_text": _approval_response_text("connect_github", str(exc)),
                    },
                )
            project = await self.store.update_project(project.id or "", {"repo_url": repo_url})
            return await self.store.update_mission(
                mission.id or "",
                {
                    "status": "completed",
                    "result_summary": f"Published {project.name} to GitHub",
                    "response_text": (
                        f"GitHub publish complete for {project.name}.\n"
                        f"Repository: {repo_url}\n\n"
                        "Next commands:\n"
                        f"/publish vercel {project.slug}\n"
                        f"/preview {project.slug}"
                    ),
                    "repo_url": repo_url,
                },
            )

        if target == "all":
            github_result = await self._run_publish_mission(
                await self.store.update_mission(
                    mission.id or "",
                    {"plan": {**mission.plan, "target": "github"}},
                )
            )
            if github_result.status != "completed":
                return github_result
            mission = await self.store.get_mission(mission.id or "") or github_result
            mission.plan["target"] = "vercel"
            await self.store.update_mission(mission.id or "", {"plan": mission.plan, "status": "deploying"})
            target = "vercel"

        if target == "vercel":
            try:
                deployment_result = await self._publish_project_to_user_vercel(
                    workspace_user_id=mission.workspace_user_id,
                    project=project,
                    manifest=manifest,
                )
            except OAuthError as exc:
                return await self.store.update_mission(
                    mission.id or "",
                    {
                        "status": "awaiting_approval",
                        "approval_request": {"action": "connect_vercel", "message": str(exc)},
                        "result_summary": "Vercel connection required",
                        "response_text": _approval_response_text("connect_vercel", str(exc)),
                    },
                )
            deployment_url = deployment_result["deployment_url"]
            return await self.store.update_mission(
                mission.id or "",
                {
                    "status": "completed",
                    "result_summary": f"Published {project.name} to Vercel",
                    "response_text": (
                        f"Vercel publish complete for {project.name}.\n"
                        f"Live URL: {deployment_url}\n"
                        f"Preview: {project.preview_url or 'not available'}\n"
                        f"GitHub repo: {project.repo_url or 'not published yet'}"
                    ),
                    "deployment_url": deployment_url,
                    "repo_url": project.repo_url,
                },
            )

        return await self.store.update_mission(
            mission.id or "",
            {
                "status": "failed",
                "error": f"Unsupported publish target: {target}",
                "response_text": "Use `/publish github`, `/publish vercel`, or `/publish all`.",
            },
        )

    async def _complete_status_mission(self, mission: MissionRecord) -> MissionRecord:
        projects = await self.store.list_projects(mission.workspace_user_id)
        connections = await self.store.list_oauth_connections(mission.workspace_user_id)
        latest_project = projects[0] if projects else None
        summary = (
            f"Connected providers: {', '.join(item.provider for item in connections) or 'none'}\n"
            f"Projects: {len(projects)}\n"
            f"Latest project: {latest_project.name if latest_project else 'none'}\n"
            f"Latest preview: {latest_project.preview_url if latest_project and latest_project.preview_url else 'not ready'}"
        )
        return await self.store.update_mission(
            mission.id or "",
            {"status": "completed", "result_summary": "Status ready", "response_text": summary},
        )

    async def _upsert_project_for_build(
        self,
        *,
        mission: MissionRecord,
        blueprint: Any,
        manifest: dict[str, dict[str, str | None]],
        project: ProjectRecord | None,
    ) -> ProjectRecord:
        updates = {
            "prompt": mission.prompt,
            "archetype": blueprint.archetype,
            "latest_manifest": manifest,
            "latest_preview": self._manifest_preview(manifest),
            "preview_status": "pending",
            "preview_url": None,
            "preview_deployment_id": None,
            "preview_metadata": {},
            "preview_updated_at": datetime.now(tz=UTC),
        }
        if project is None:
            project = await self.store.create_project(
                ProjectRecord(
                    workspace_user_id=mission.workspace_user_id,
                    name=blueprint.project_name,
                    slug=blueprint.slug,
                    prompt=mission.prompt,
                    archetype=blueprint.archetype,
                    latest_manifest=manifest,
                    latest_preview=self._manifest_preview(manifest),
                    preview_status="pending",
                )
            )
            await self.store.update_mission(mission.id or "", {"project_id": project.id})
            return project
        return await self.store.update_project(project.id or "", updates)

    async def _deploy_preview_for_revision(
        self,
        *,
        project: ProjectRecord,
        revision: ProjectRevision,
    ) -> dict[str, ProjectRecord | ProjectRevision | DeploymentRecord]:
        manifest = revision.file_manifest or project.latest_manifest or {}
        if not manifest:
            raise RuntimeError("Project has no saved files.")

        settings = self.integrations.settings
        token = settings.managed_preview_vercel_token.strip()
        if not token:
            raise RuntimeError("Managed preview is not configured yet.")

        deployment = await self.store.create_deployment(
            DeploymentRecord(
                project_id=project.id or "",
                workspace_user_id=project.workspace_user_id,
                provider="vercel",
                status="deploying",
                metadata={"purpose": "managed_preview", "revision_id": revision.id},
            )
        )

        client = VercelDeployClient(
            token,
            team_id=settings.managed_preview_vercel_team_id,
            team_slug=settings.managed_preview_vercel_team_slug,
        )
        try:
            files = {name: str(data.get("content") or "") for name, data in manifest.items()}
            result = await client.deploy_files(
                project_name=self._managed_preview_project_name(project),
                files=files,
                project_settings={
                    "framework": "vite",
                    "installCommand": "npm install",
                    "buildCommand": "npm run build",
                    "outputDirectory": "dist",
                },
                meta={
                    "forgeManagedPreview": "true",
                    "forgeProjectId": project.id or "",
                    "forgeRevisionId": revision.id or "",
                },
            )
        except Exception as exc:
            await self.store.update_deployment(
                deployment.id or "",
                {"status": "failed", "metadata": {"purpose": "managed_preview", "error": str(exc)}},
            )
            raise
        finally:
            await client.close()

        preview_url = _normalize_url(str(result.get("url") or ""))
        updated_deployment = await self.store.update_deployment(
            deployment.id or "",
            {
                "status": "ready",
                "deployment_url": preview_url,
                "external_id": result.get("id"),
                "metadata": {**result, "purpose": "managed_preview"},
            },
        )
        updated_project = await self.store.update_project(
            project.id or "",
            {
                "preview_url": preview_url,
                "preview_status": "ready",
                "preview_deployment_id": str(result.get("id") or ""),
                "preview_updated_at": datetime.now(tz=UTC),
                "preview_metadata": result,
            },
        )
        updated_revision = await self.store.update_project_revision(
            revision.id or "",
            {
                "preview_url": preview_url,
                "preview_status": "ready",
                "preview_deployment_id": str(result.get("id") or ""),
                "preview_metadata": result,
            },
        )
        return {"project": updated_project, "revision": updated_revision, "deployment": updated_deployment}

    async def _publish_project_to_user_vercel(
        self,
        *,
        workspace_user_id: int,
        project: ProjectRecord,
        manifest: dict[str, dict[str, str | None]],
    ) -> dict[str, Any]:
        connection, token = await self.integrations.get_decrypted_connection(workspace_user_id, "vercel")
        team_id = str(connection.metadata.get("team_id") or "")
        client = VercelDeployClient(token, team_id=team_id or None)
        deployment = await self.store.create_deployment(
            DeploymentRecord(
                project_id=project.id or "",
                workspace_user_id=workspace_user_id,
                provider="vercel",
                status="deploying",
                metadata={"purpose": "user_publish"},
            )
        )
        try:
            result = await client.deploy_files(
                project_name=project.slug,
                files={name: str(data.get("content") or "") for name, data in manifest.items()},
                project_settings={
                    "framework": "vite",
                    "installCommand": "npm install",
                    "buildCommand": "npm run build",
                    "outputDirectory": "dist",
                },
                meta={"forgePublish": "true", "forgeProjectId": project.id or ""},
            )
        finally:
            await client.close()

        deployment_url = _normalize_url(str(result.get("url") or ""))
        await self.store.update_deployment(
            deployment.id or "",
            {
                "status": "ready",
                "deployment_url": deployment_url,
                "external_id": result.get("id"),
                "metadata": {**result, "purpose": "user_publish"},
            },
        )
        await self.store.update_project(
            project.id or "",
            {
                "deployment_metadata": result,
            },
        )
        return {"deployment_url": deployment_url, "result": result}

    async def _sync_project_repo(
        self,
        workspace_user_id: int,
        project: ProjectRecord,
        manifest: dict[str, dict[str, str | None]],
    ) -> str:
        connection, token = await self.integrations.get_decrypted_connection(workspace_user_id, "github")
        client = GitHubRepoClient(token)
        try:
            repo_name = project.repo_name or slugify(project.name)
            repo = await client.ensure_repo(repo_name)
            owner = repo["owner"]["login"]
            await client.upsert_files(
                owner=owner,
                repo=repo["name"],
                files={path: str(data.get("content") or "") for path, data in manifest.items()},
                branch=project.default_branch,
            )
        finally:
            await client.close()
        await self.store.update_project(
            project.id or "",
            {
                "repo_owner": repo["owner"]["login"],
                "repo_name": repo["name"],
                "repo_url": repo.get("html_url"),
            },
        )
        return str(repo.get("html_url") or f"https://github.com/{connection.account_name}/{repo_name}")

    async def delivery_from_mission(self, mission: MissionRecord) -> DeliveryPayload:
        text = mission.response_text or mission.result_summary or "Mission completed."
        if mission.kind not in {"build", "edit"} or not mission.project_id:
            return DeliveryPayload(text=text)

        revision = await self._revision_for_mission(mission)
        project = await self.store.get_project(mission.project_id)
        manifest = revision.file_manifest if revision is not None else (project.latest_manifest if project is not None else {})
        if not manifest:
            return DeliveryPayload(text=text)

        project_slug = project.slug if project is not None else slugify("forge-project")
        bundle_name = mission.bundle_name or (revision.bundle_name if revision is not None else None)
        fallback_name, bundle_bytes = build_project_bundle(project_slug=project_slug, manifest=manifest)
        return DeliveryPayload(text=text, document_name=bundle_name or fallback_name, document_bytes=bundle_bytes)

    async def _notify_if_possible(self, mission: MissionRecord) -> None:
        if mission.chat_id:
            return
        link = await self.store.get_account_link_for_workspace(mission.workspace_user_id)
        if link is None or not mission.response_text:
            return
        payload = await self.delivery_from_mission(mission)
        await self.transport.deliver(link.telegram_user_id, payload)

    async def _persist_mission_memory(self, mission: MissionRecord) -> None:
        memory_summary = _mission_memory_summary(mission)
        if memory_summary:
            await self.store.append_conversation(
                ConversationRecord(
                    user_id=mission.workspace_user_id,
                    role="assistant",
                    content=memory_summary,
                    agents_used=["builder", mission.kind],
                )
            )
        if mission.project_id:
            project = await self.store.get_project(mission.project_id)
            if project is not None:
                profile = await self.store.get_user_profile(mission.workspace_user_id)
                current_projects = list(dict.fromkeys([project.name, *profile.current_projects]))
                await self.store.update_user_profile(
                    mission.workspace_user_id,
                    {
                        "current_projects": current_projects[:12],
                        "active_context": {
                            **profile.active_context,
                            "latest_project": project.slug,
                            "latest_project_id": project.id,
                            "latest_mission_status": mission.status,
                            "latest_preview_url": project.preview_url,
                        },
                    },
                )

    def _build_generate_response_text(
        self,
        *,
        project: ProjectRecord,
        mission: MissionRecord,
        revision: ProjectRevision,
        preview_error: str | None,
    ) -> str:
        top_files = sorted((revision.file_manifest or {}).keys())[:8]
        file_lines = "\n".join(f"- {name}" for name in top_files) or "- none"
        summary_intro = "Updated the latest revision." if mission.kind == "edit" else "Generated a complete React + Vite website."
        preview_line = (
            f"Preview: {project.preview_url}\nWorking preview: temporary Forge-managed URL"
            if project.preview_url
            else "Preview: not ready yet"
        )
        preview_note = ""
        if preview_error:
            preview_note = (
                "\n\nCode generated successfully, but the managed preview failed.\n"
                f"Reason: {preview_error}\n"
                "Retry with `/preview` after preview infrastructure is configured."
            )
        return (
            f"{project.name} is ready.\n"
            f"Website type: {_project_type_label(project.archetype)}\n"
            f"{summary_intro}\n"
            f"{preview_line}\n"
            f"Bundle: {revision.bundle_name or 'ready'}\n"
            f"Files generated: {revision.bundle_file_count}\n\n"
            f"Top files:\n{file_lines}\n\n"
            "Next commands:\n"
            f"/edit {project.slug} <instruction>\n"
            f"/preview {project.slug}\n"
            f"/files {project.slug}\n"
            f"/publish github {project.slug}\n"
            f"/publish vercel {project.slug}"
            f"{preview_note}"
        )

    def _build_design_source(self, blueprint: Any) -> dict[str, Any]:
        if self.figma is not None:
            return self.figma.build_design_context(blueprint.archetype)
        return {
            "type": "internal_figma_template" if blueprint.figma_template_key else "scaffold",
            "configured": bool(blueprint.figma_template_url),
            "template_key": blueprint.figma_template_key,
            "template_name": blueprint.figma_template_name,
            "template_url": blueprint.figma_template_url,
            "template_description": blueprint.figma_template_description,
        }

    def _manifest_preview(self, manifest: dict[str, dict[str, str | None]]) -> str | None:
        first = next(iter(manifest.values()), None)
        if first is None:
            return None
        return str(first.get("content") or "")[:1200]

    def _managed_preview_project_name(self, project: ProjectRecord) -> str:
        workspace_suffix = str(abs(project.workspace_user_id))[-8:]
        raw = f"forge-preview-{project.slug}-{workspace_suffix}"
        return raw[:100].rstrip("-")

    def _publish_target_for_mission(self, mission: MissionRecord) -> str:
        target = str(mission.plan.get("target") or "").strip().lower()
        if target:
            return target
        prompt = mission.prompt.lower()
        if "github" in prompt:
            return "github"
        if "all" in prompt:
            return "all"
        return "vercel"

    def _revision_summary(self, kind: str, project_name: str, file_count: int) -> str:
        prefix = "Updated" if kind == "edit" else "Generated"
        return f"{prefix} {file_count} files for {project_name}"

    async def _get_latest_revision(self, project_id: str) -> ProjectRevision | None:
        revisions = await self.store.list_project_revisions(project_id)
        return revisions[0] if revisions else None

    async def _revision_for_mission(self, mission: MissionRecord) -> ProjectRevision | None:
        if not mission.project_id:
            return None
        revisions = await self.store.list_project_revisions(mission.project_id)
        for revision in revisions:
            if revision.mission_id == mission.id:
                return revision
        return revisions[0] if revisions else None
