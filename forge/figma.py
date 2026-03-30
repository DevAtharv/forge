from __future__ import annotations

from dataclasses import replace

from forge.config import Settings
from forge.figma_templates import DEFAULT_FIGMA_TEMPLATES, FigmaTemplate


class FigmaTemplateService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def list_templates(self) -> list[FigmaTemplate]:
        templates: list[FigmaTemplate] = []
        for template in DEFAULT_FIGMA_TEMPLATES.values():
            templates.append(self.resolve_template(template.key))
        return templates

    def resolve_template(self, key: str) -> FigmaTemplate:
        template = DEFAULT_FIGMA_TEMPLATES[key]
        override_url = (self.settings.figma_template_urls.get(template.archetype) or "").strip()
        if not override_url:
            return template
        return replace(template, frame_url=override_url)

    def get_template_for_archetype(self, archetype: str) -> FigmaTemplate | None:
        template = DEFAULT_FIGMA_TEMPLATES.get(archetype)
        if template is None:
            return None
        return self.resolve_template(template.key)

    def build_design_context(self, archetype: str) -> dict[str, object]:
        template = self.get_template_for_archetype(archetype)
        if template is None:
            return {
                "type": "scaffold",
                "configured": False,
            }
        return {
            "type": "internal_figma_template",
            "configured": bool(template.frame_url),
            "template_key": template.key,
            "template_name": template.name,
            "template_url": template.frame_url,
            "template_description": template.description,
        }
