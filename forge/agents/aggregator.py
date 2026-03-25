from __future__ import annotations

from forge.schemas import AgentResult, Artifact, DeliveryPayload, OrchestrationPlan, StageExecution


AGENT_TITLES = {
    "planner": "Plan",
    "research": "Research",
    "code": "Implementation",
    "debug": "Debug",
    "reviewer": "Review",
}


class PipelineAggregator:
    def format(self, plan: OrchestrationPlan, stages: list[StageExecution]) -> DeliveryPayload:
        sections: list[str] = []
        artifacts: list[Artifact] = []
        citations: list[str] = []

        results = [result for stage in stages for result in stage.outputs.values()]
        for result in results:
            if result.user_visible_text.strip():
                sections.append(self._render_section(result, multi_section=len(results) > 1))
            artifacts.extend(result.artifacts)
            for citation in result.citations:
                line = f"- {citation.title}: {citation.url}"
                if line not in citations:
                    citations.append(line)

        text = "\n\n".join(section for section in sections if section.strip()).strip()
        if citations:
            text = f"{text}\n\nSources:\n" + "\n".join(citations) if text else "Sources:\n" + "\n".join(citations)
        if not text:
            text = "Forge finished the request, but no user-facing text was generated."

        should_attach = self._should_attach_document(plan, artifacts, text)
        if not should_attach:
            return DeliveryPayload(text=text)

        document_body = self._render_document(plan, stages, artifacts)
        summary = text
        if len(summary) > 1800:
            summary = summary[:1800].rstrip() + "\n\nFull output is attached as a document."
        elif artifacts:
            summary = summary + "\n\nFull output is attached as a document."
        return DeliveryPayload(
            text=summary,
            document_name="forge-response.md",
            document_bytes=document_body.encode("utf-8"),
        )

    def _render_section(self, result: AgentResult, *, multi_section: bool) -> str:
        title = AGENT_TITLES.get(result.agent, result.agent.title())
        if not multi_section:
            return result.user_visible_text.strip()
        return f"{title}\n{result.user_visible_text.strip()}"

    def _should_attach_document(self, plan: OrchestrationPlan, artifacts: list[Artifact], text: str) -> bool:
        if len(text) > 3200:
            return True
        if len(artifacts) > 1:
            return True
        if artifacts and (plan.response_format == "code" or any(len(item.content) > 1800 for item in artifacts)):
            return True
        return False

    def _render_document(self, plan: OrchestrationPlan, stages: list[StageExecution], artifacts: list[Artifact]) -> str:
        lines = ["# Forge Response", "", f"Response format: {plan.response_format}", ""]
        for stage in stages:
            lines.append(f"## Stage: {stage.name}")
            lines.append("")
            for name, result in stage.outputs.items():
                title = AGENT_TITLES.get(name, name.title())
                lines.append(f"### {title}")
                lines.append("")
                if result.user_visible_text.strip():
                    lines.append(result.user_visible_text.strip())
                    lines.append("")
                for citation in result.citations:
                    lines.append(f"- Source: {citation.title} ({citation.url})")
                if result.citations:
                    lines.append("")
        if artifacts:
            lines.append("## Artifacts")
            lines.append("")
            for artifact in artifacts:
                lines.append(f"### {artifact.name}")
                lines.append("")
                fence = artifact.language or ""
                lines.append(f"```{fence}")
                lines.append(artifact.content.rstrip())
                lines.append("```")
                lines.append("")
        return "\n".join(lines).strip() + "\n"
