from __future__ import annotations

from dataclasses import dataclass

from forge.builder import HybridProjectBuilder, slugify
from forge.figma import FigmaTemplateService
from forge.integrations import GitHubRepoClient, IntegrationService, OAuthError, VercelDeployClient
from forge.memory import MemoryStore
from forge.schemas import Artifact, ConversationRecord, DeliveryPayload, DeploymentRecord, MissionRecord, ProjectRecord, ProjectRevision
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
            "Build is ready, but Forge needs your GitHub connection before it can save the project files.\n\n"
            f"{message}\n\n"
            "Next step: connect GitHub, then run the build again."
        )
    if action == "connect_vercel":
        return (
            "Deployment is ready to continue, but Forge needs your Vercel connection first.\n\n"
            f"{message}\n\n"
            "Next step: connect Vercel, then run the deploy again."
        )
    return message


def _mission_memory_summary(mission: MissionRecord) -> str:
    parts: list[str] = []
    if mission.kind == "build":
        parts.append(mission.result_summary or "Build completed.")
        if mission.repo_url:
            parts.append(f"GitHub: {mission.repo_url}")
    elif mission.kind == "deploy":
        parts.append(mission.result_summary or "Deployment completed.")
        if mission.deployment_url:
            parts.append(f"Live URL: {mission.deployment_url}")
        if mission.repo_url:
            parts.append(f"GitHub: {mission.repo_url}")
    else:
        parts.append(mission.result_summary or mission.response_text or "Mission completed.")
    return "\n".join(parts)


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
            await self._persist_mission_memory(completed)
            await self._notify_if_possible(completed)
            return completed
        if mission.kind == "deploy":
            completed = await self._run_deploy_mission(mission)
            await self._persist_mission_memory(completed)
            await self._notify_if_possible(completed)
            return completed
        completed = await self._run_build_mission(mission)
        await self._persist_mission_memory(completed)
        await self._notify_if_possible(completed)
        return completed

    async def _run_build_mission(self, mission: MissionRecord) -> MissionRecord:
        mission = await self.store.update_mission(mission.id or "", {"status": "planning"})
        project = None
        if mission.project_id:
            project = await self.store.get_project(mission.project_id)

        blueprint = self.builder.choose_blueprint(mission.prompt, project_name=project.name if project else None)
        artifacts = self.builder.build_files(blueprint, mission.prompt)
        manifest = _artifacts_to_manifest(artifacts)
        design_source = (
            self.figma.build_design_context(blueprint.archetype)
            if self.figma is not None
            else {
                "type": "internal_figma_template" if blueprint.figma_template_key else "scaffold",
                "configured": bool(blueprint.figma_template_url),
                "template_key": blueprint.figma_template_key,
                "template_name": blueprint.figma_template_name,
                "template_url": blueprint.figma_template_url,
                "template_description": blueprint.figma_template_description,
            }
        )

        mission = await self.store.update_mission(
            mission.id or "",
            {
                "status": "building",
                "plan": {
                    "archetype": blueprint.archetype,
                    "project_name": blueprint.project_name,
                    "slug": blueprint.slug,
                    "file_count": len(artifacts),
                    "design_source": design_source,
                },
            },
        )

        if project is None:
            project = await self.store.create_project(
                ProjectRecord(
                    workspace_user_id=mission.workspace_user_id,
                    name=blueprint.project_name,
                    slug=blueprint.slug,
                    prompt=mission.prompt,
                    archetype=blueprint.archetype,
                    latest_manifest=manifest,
                    latest_preview=artifacts[0].content[:1200] if artifacts else None,
                )
            )
            mission = await self.store.update_mission(mission.id or "", {"project_id": project.id})
        else:
            project = await self.store.update_project(
                project.id or "",
                {
                    "prompt": mission.prompt,
                    "archetype": blueprint.archetype,
                    "latest_manifest": manifest,
                    "latest_preview": artifacts[0].content[:1200] if artifacts else None,
                },
            )

        await self.store.create_project_revision(
            ProjectRevision(
                project_id=project.id or "",
                workspace_user_id=mission.workspace_user_id,
                mission_id=mission.id,
                summary=f"Generated {len(artifacts)} files for {project.name}",
                file_manifest=manifest,
            )
        )

        changed_files = list(manifest.keys())
        repo_url = None
        try:
            repo_url = await self._sync_project_repo(mission.workspace_user_id, project, artifacts)
        except OAuthError as exc:
            mission = await self.store.update_mission(
                mission.id or "",
                {
                    "status": "awaiting_approval",
                    "approval_request": {
                        "action": "connect_github",
                        "message": str(exc),
                    },
                    "result_summary": "GitHub connection required",
                    "response_text": _approval_response_text("connect_github", str(exc)),
                },
            )
            return mission

        project = await self.store.update_project(project.id or "", {"repo_url": repo_url})
        design_line = ""
        design_name = str(design_source.get("template_name") or "")
        design_key = str(design_source.get("template_key") or "")
        design_configured = bool(design_source.get("configured"))
        if design_name:
            design_line = (
                f"Design source: {design_name}"
                + (f" ({design_key})" if design_key else "")
                + (" [configured]\n" if design_configured else " [template slot ready]\n")
            )
        elif blueprint.figma_template_name:
            design_line = (
                f"Design source: {blueprint.figma_template_name}"
                + (f" ({blueprint.figma_template_key})" if blueprint.figma_template_key else "")
                + "\n"
            )
        response_text = (
            f"Project `{project.name}` is ready.\n"
            f"Archetype: {project.archetype}\n"
            f"Files generated: {len(changed_files)}\n"
            f"{design_line}"
            f"GitHub repo: {repo_url}\n"
            "GitHub is now the source of truth for project files and assets.\n\n"
            f"Next commands:\n"
            f"/deploy {project.slug}\n"
            f"/files {project.slug}"
        )
        return await self.store.update_mission(
            mission.id or "",
            {
                "status": "completed",
                "result_summary": f"Built {project.name}",
                "response_text": response_text,
                "repo_url": repo_url,
                "changed_files": changed_files,
            },
        )

    async def _run_deploy_mission(self, mission: MissionRecord) -> MissionRecord:
        mission = await self.store.update_mission(mission.id or "", {"status": "deploying"})
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

        try:
            _, token = await self.integrations.get_decrypted_connection(mission.workspace_user_id, "vercel")
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

        client = VercelDeployClient(token)
        deployment = await self.store.create_deployment(
            DeploymentRecord(
                project_id=project.id or "",
                workspace_user_id=mission.workspace_user_id,
                provider="vercel",
                status="deploying",
            )
        )
        try:
            payload = {name: str(data.get("content") or "") for name, data in manifest.items()}
            result = await client.deploy_files(project_name=project.slug, files=payload)
        finally:
            await client.close()

        deployment_url = result.get("url")
        if deployment_url and not str(deployment_url).startswith("http"):
            deployment_url = f"https://{deployment_url}"
        await self.store.update_deployment(
            deployment.id or "",
            {
                "status": "ready",
                "deployment_url": deployment_url,
                "external_id": result.get("id"),
                "metadata": result,
            },
        )
        await self.store.update_project(
            project.id or "",
            {
                "deployment_metadata": result,
            },
        )
        return await self.store.update_mission(
            mission.id or "",
            {
                "status": "completed",
                "result_summary": f"Deployed {project.name}",
                "response_text": (
                    f"Deployment complete for {project.name}.\n"
                    f"Live URL: {deployment_url}\n"
                    f"GitHub repo: {project.repo_url or 'connected repository'}"
                ),
                "deployment_url": deployment_url,
                "repo_url": project.repo_url,
            },
        )

    async def _complete_status_mission(self, mission: MissionRecord) -> MissionRecord:
        projects = await self.store.list_projects(mission.workspace_user_id)
        connections = await self.store.list_oauth_connections(mission.workspace_user_id)
        summary = (
            f"Connected providers: {', '.join(item.provider for item in connections) or 'none'}\n"
            f"Projects: {len(projects)}"
        )
        return await self.store.update_mission(
            mission.id or "",
            {"status": "completed", "result_summary": "Status ready", "response_text": summary},
        )

    async def _sync_project_repo(self, workspace_user_id: int, project: ProjectRecord, artifacts: list[Artifact]) -> str:
        connection, token = await self.integrations.get_decrypted_connection(workspace_user_id, "github")
        client = GitHubRepoClient(token)
        try:
            repo_name = project.repo_name or slugify(project.name)
            repo = await client.ensure_repo(repo_name)
            owner = repo["owner"]["login"]
            changed = await client.upsert_files(
                owner=owner,
                repo=repo["name"],
                files={artifact.name: artifact.content for artifact in artifacts},
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
        return DeliveryPayload(text=text)

    async def _notify_if_possible(self, mission: MissionRecord) -> None:
        if mission.chat_id:
            return
        link = await self.store.get_account_link_for_workspace(mission.workspace_user_id)
        if link is None:
            return
        if not mission.response_text:
            return
        await self.transport.send_status_message(link.telegram_user_id, mission.response_text)

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
                            "latest_mission_status": mission.status,
                        },
                    },
                )
