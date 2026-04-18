from __future__ import annotations

import base64
import json

from forge.agents.base import AgentInvocation, coerce_agent_result
from forge.builder import HybridProjectBuilder
from forge.config import Settings
from forge.prompts import (
    CODE_SYSTEM,
    DEBUG_SYSTEM,
    PLANNER_SYSTEM,
    PROFILE_SUMMARY_SYSTEM,
    RESEARCH_SYSTEM,
    REVIEWER_SYSTEM,
    WEBSITE_BUILD_QUALITY_BRIEF,
)
from forge.providers import ProviderRegistry
from forge.schemas import AgentResult, Artifact, Citation


def _artifact_language_for_path(path: str) -> str | None:
    lower = path.lower()
    if lower.endswith(".js") or lower.endswith(".mjs") or lower.endswith(".cjs"):
        return "javascript"
    if lower.endswith(".jsx"):
        return "jsx"
    if lower.endswith(".ts"):
        return "typescript"
    if lower.endswith(".tsx"):
        return "tsx"
    if lower.endswith(".css"):
        return "css"
    if lower.endswith(".html"):
        return "html"
    if lower.endswith(".json"):
        return "json"
    if lower.endswith(".md"):
        return "markdown"
    if lower.endswith(".sh"):
        return "bash"
    return None


def _artifact_mime_for_path(path: str) -> str:
    lower = path.lower()
    if lower.endswith(".css"):
        return "text/css"
    if lower.endswith(".html"):
        return "text/html"
    if lower.endswith(".json"):
        return "application/json"
    if lower.endswith(".md"):
        return "text/markdown"
    if lower.endswith(".sh"):
        return "text/x-shellscript"
    if lower.endswith(".js") or lower.endswith(".jsx") or lower.endswith(".ts") or lower.endswith(".tsx"):
        return "text/javascript"
    return "text/plain"


def _expand_project_manifest_result(result: AgentResult) -> AgentResult:
    manifest_artifact = next((item for item in result.artifacts if item.name.lower() == "forge_project.json"), None)
    if manifest_artifact is None:
        return result

    try:
        manifest = json.loads(manifest_artifact.content)
    except Exception:
        result.internal_notes.append("forge_project_manifest_invalid")
        return result

    files = manifest.get("files")
    if not isinstance(files, list):
        result.internal_notes.append("forge_project_manifest_missing_files")
        return result

    expanded: list[Artifact] = []
    seen_names = {item.name for item in result.artifacts}
    for item in files:
        if not isinstance(item, dict):
            continue
        path = item.get("path")
        content = item.get("content")
        if not isinstance(path, str) or not isinstance(content, str):
            continue
        if path in seen_names:
            continue
        expanded.append(
            Artifact(
                name=path,
                content=content,
                language=_artifact_language_for_path(path),
                mime_type=_artifact_mime_for_path(path),
            )
        )

    if not expanded:
        result.internal_notes.append("forge_project_manifest_no_expansion")
        return result

    dependencies = manifest.get("dependencies")
    if isinstance(dependencies, dict):
        result.handoff.setdefault("dependencies", dependencies)
    project_name = manifest.get("project_name")
    if isinstance(project_name, str) and project_name.strip():
        result.handoff.setdefault("project_name", project_name.strip())
    result.handoff["files_created"] = [item.name for item in (*result.artifacts, *expanded)]
    result.internal_notes.append("forge_project_manifest_expanded")
    result.artifacts.extend(expanded)
    return result


def _history_messages(invocation: AgentInvocation) -> list[dict[str, str]]:
    return [{"role": item.role, "content": item.content} for item in invocation.history[-6:]]


def _needs_website_quality_brief(invocation: AgentInvocation) -> bool:
    text = f"{invocation.original_task}\n{invocation.task}".lower()
    website_signals = (
        "website",
        "web site",
        "landing page",
        "portfolio",
        "simple tool",
        "frontend",
        "user interface",
        "dashboard ui",
        "sweet shop",
        "ecommerce",
        "storefront",
        "home page",
    )
    deploy_signals = ("deploy", "deployment", "vercel", "ship it", "go live", "production url")
    has_website_signal = any(token in text for token in website_signals)
    has_deploy_signal = any(token in text for token in deploy_signals)
    return has_website_signal or has_deploy_signal


def _is_low_quality_website_result(result: AgentResult) -> bool:
    if not result.artifacts:
        return True
    full_text = "\n".join([result.user_visible_text, *(item.content for item in result.artifacts)]).lower()
    low_quality_markers = (
        "add javascript functionality here",
        "basic structure",
        "customize the html, css, and javascript",
        "placeholder",
        "todo",
        "lorem ipsum",
        "album 1",
        "video-id",
    )
    if any(marker in full_text for marker in low_quality_markers):
        return True
    if len(result.artifacts) < 4:
        return True
    artifact_names = {item.name.lower() for item in result.artifacts}
    required = {
        "package.json",
        "next.config.js",
        "tailwind.config.js",
        "postcss.config.js",
        "app/layout.js",
        "app/page.js",
        "app/globals.css",
        "vercel.json",
        "terminal_commands.sh",
    }
    return not required.issubset(artifact_names)


def _website_upgrade_result(invocation: AgentInvocation, original: AgentResult) -> AgentResult:
    prompt_hint = invocation.original_task.strip() or "Build a modern scaffold-first website."
    builder = HybridProjectBuilder()
    blueprint = builder.choose_blueprint(prompt_hint)
    artifacts = builder.build_files(blueprint, prompt_hint)
    summary = "Upgraded website output to Forge's deterministic Next.js and Tailwind scaffold."
    user_visible_text = (
        "I upgraded the website output because the initial code quality was below production standard. "
        "This bundle now includes a polished scaffold-first Next.js and Tailwind frontend with "
        "deployment-ready files and a simple single-page flow.\n\n"
        f"Mission intent captured: {prompt_hint}"
    )
    return AgentResult(
        agent=original.agent,
        summary=summary,
        user_visible_text=user_visible_text,
        artifacts=artifacts,
        handoff={
            **original.handoff,
            "implementation_summary": summary,
            "upgrade_reason": "low_quality_generated_output",
            "files_created": [item.name for item in artifacts],
        },
        citations=original.citations,
        confidence=max(original.confidence, 0.78),
        internal_notes=[*original.internal_notes, "website_bundle_upgraded:deterministic_template"],
    )


def _website_recovery_instruction(invocation: AgentInvocation) -> str:
    return (
        "The previous output quality was too basic. Regenerate with a production build contract.\n\n"
        "Required stack:\n"
        "- Next.js latest stable with App Router\n"
        "- Tailwind CSS\n"
        "- JavaScript only unless the user explicitly asks for TypeScript\n"
        "- Single-page frontend flow only\n\n"
        "Required primary artifact:\n"
        "- forge_project.json containing project_name, files[], and dependencies\n\n"
        "Required artifacts (all required):\n"
        "- package.json\n"
        "- next.config.js\n"
        "- tailwind.config.js\n"
        "- postcss.config.js\n"
        "- app/layout.js\n"
        "- app/page.js\n"
        "- app/globals.css\n"
        "- vercel.json\n"
        "- terminal_commands.sh\n\n"
        "Rules:\n"
        "- No placeholders, TODOs, fake values, or tutorial prose.\n"
        "- Include complete working code in every file artifact.\n"
        "- Use clear modern UI design with responsive behavior.\n"
        "- Do not add auth, sessions, databases, APIs, or backend logic.\n"
        "- Do not add unauthorized multi-page routing.\n"
        f"- User request: {invocation.original_task}"
    )


class PlannerAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def run(self, invocation: AgentInvocation) -> AgentResult:
        system_prompt = PLANNER_SYSTEM
        if _needs_website_quality_brief(invocation):
            system_prompt = f"{PLANNER_SYSTEM}\n\n{WEBSITE_BUILD_QUALITY_BRIEF}"
        user_prompt = (
            f"Task:\n{invocation.task}\n\n"
            f"User context:\n{invocation.user_context or 'No durable context.'}\n\n"
            f"Shared handoff:\n{json.dumps(invocation.shared_handoff, ensure_ascii=True)}"
        )
        raw = await self.providers.generate(
            self.settings.planner_routes,
            messages=[
                {"role": "system", "content": system_prompt},
                *_history_messages(invocation),
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
            max_tokens=1400,
            json_mode=True,
        )
        return coerce_agent_result("planner", raw)


class CodeAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def run(self, invocation: AgentInvocation) -> AgentResult:
        system_prompt = CODE_SYSTEM
        if _needs_website_quality_brief(invocation):
            system_prompt = f"{CODE_SYSTEM}\n\n{WEBSITE_BUILD_QUALITY_BRIEF}"
        user_prompt = (
            f"Original task:\n{invocation.original_task}\n\n"
            f"Specific coding task:\n{invocation.task}\n\n"
            f"User context:\n{invocation.user_context or 'No durable context.'}\n\n"
            f"Planner/research handoff:\n{json.dumps(invocation.shared_handoff, ensure_ascii=True)}"
        )
        raw = await self.providers.generate(
            self.settings.code_routes,
            messages=[
                {"role": "system", "content": system_prompt},
                *_history_messages(invocation),
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.15,
            max_tokens=3200,
            json_mode=True,
        )
        result = _expand_project_manifest_result(coerce_agent_result("code", raw))
        if _needs_website_quality_brief(invocation) and _is_low_quality_website_result(result):
            recovery_raw = await self.providers.generate(
                self.settings.code_routes,
                messages=[
                    {"role": "system", "content": f"{system_prompt}\n\n{_website_recovery_instruction(invocation)}"},
                    *_history_messages(invocation),
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.05,
                max_tokens=3600,
                json_mode=True,
            )
            recovered = _expand_project_manifest_result(coerce_agent_result("code", recovery_raw))
            if not _is_low_quality_website_result(recovered):
                recovered.internal_notes.append("website_quality_recovered:llm_second_pass")
                return recovered
            return _website_upgrade_result(invocation, recovered)
        return result


class DebugAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def run(self, invocation: AgentInvocation) -> AgentResult:
        if invocation.image_bytes:
            image_b64 = base64.b64encode(invocation.image_bytes).decode("ascii")
            user_payload: str | list[dict[str, object]] = [
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
                {
                    "type": "text",
                    "text": (
                        f"Task:\n{invocation.task or invocation.original_task}\n\n"
                        f"User context:\n{invocation.user_context or 'No durable context.'}"
                    ),
                },
            ]
        else:
            user_payload = (
                f"Task:\n{invocation.task or invocation.original_task}\n\n"
                f"User context:\n{invocation.user_context or 'No durable context.'}"
            )
        raw = await self.providers.generate(
            self.settings.debug_routes,
            messages=[
                {"role": "system", "content": DEBUG_SYSTEM},
                *_history_messages(invocation),
                {"role": "user", "content": user_payload},
            ],
            temperature=0.1,
            max_tokens=1400,
            json_mode=True,
        )
        return coerce_agent_result("debug", raw)


class ResearchAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def run(self, invocation: AgentInvocation) -> AgentResult:
        retrieval_note: str | None = None
        try:
            hits = await self.providers.search_provider.search(
                invocation.task,
                max_results=self.settings.search_result_limit,
            )
        except Exception as exc:
            hits = []
            retrieval_note = f"search_unavailable:{exc}"
        documents = []
        for hit in hits:
            try:
                document = await self.providers.fetcher.fetch(hit.url)
            except Exception:
                continue
            if document:
                documents.append(document)
            if len(documents) >= min(3, self.settings.search_result_limit):
                break

        if documents:
            sources = [
                {"title": item.title, "url": item.url, "content": item.content[:3500]}
                for item in documents
            ]
            user_prompt = (
                f"Task:\n{invocation.task}\n\n"
                f"User context:\n{invocation.user_context or 'No durable context.'}\n\n"
                f"Retrieved sources:\n{json.dumps(sources, ensure_ascii=True)}"
            )
            raw = await self.providers.generate(
                self.settings.research_routes,
                messages=[
                    {"role": "system", "content": RESEARCH_SYSTEM},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.25,
                max_tokens=1400,
                json_mode=True,
            )
            result = coerce_agent_result("research", raw)
            if not result.citations:
                result.citations = [
                    Citation(title=item.title, url=item.url, snippet=item.content[:180])
                    for item in documents
                ]
            result.internal_notes.append("retrieval_mode:live")
            return result

        fallback_prompt = (
            f"Task:\n{invocation.task}\n\n"
            "No live sources were available. Answer carefully and explicitly note that the reply falls back to model knowledge."
        )
        raw = await self.providers.generate(
            self.settings.research_routes,
            messages=[
                {"role": "system", "content": RESEARCH_SYSTEM},
                {"role": "user", "content": fallback_prompt},
            ],
            temperature=0.3,
            max_tokens=1000,
            json_mode=True,
        )
        result = coerce_agent_result("research", raw)
        if retrieval_note:
            result.internal_notes.append(retrieval_note)
        result.internal_notes.append("retrieval_mode:model_only_fallback")
        return result


class ReviewerAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def run(self, invocation: AgentInvocation) -> AgentResult:
        system_prompt = REVIEWER_SYSTEM
        if _needs_website_quality_brief(invocation):
            system_prompt = f"{REVIEWER_SYSTEM}\n\n{WEBSITE_BUILD_QUALITY_BRIEF}"
        user_prompt = (
            f"Original task:\n{invocation.original_task}\n\n"
            f"Review focus:\n{invocation.task}\n\n"
            f"Shared handoff:\n{json.dumps(invocation.shared_handoff, ensure_ascii=True)}"
        )
        raw = await self.providers.generate(
            self.settings.reviewer_routes,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            max_tokens=1400,
            json_mode=True,
        )
        return coerce_agent_result("reviewer", raw)


class ProfileSummaryAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def summarize(self, payload: dict[str, object]) -> dict[str, object]:
        raw = await self.providers.generate(
            self.settings.summary_routes,
            messages=[
                {"role": "system", "content": PROFILE_SUMMARY_SYSTEM},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=True)},
            ],
            temperature=0.1,
            max_tokens=800,
            json_mode=True,
        )
        return json.loads(raw)
