from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FigmaTemplate:
    key: str
    name: str
    archetype: str
    description: str
    frame_url: str | None = None


DEFAULT_FIGMA_TEMPLATES: dict[str, FigmaTemplate] = {
    "landing-page": FigmaTemplate(
        key="landing-page",
        name="Forge Landing Page",
        archetype="landing-page",
        description="Launch-ready marketing layout with hero, proof, feature bands, and CTA sections.",
    ),
    "portfolio": FigmaTemplate(
        key="portfolio",
        name="Forge Creator Portfolio",
        archetype="portfolio",
        description="Editorial portfolio layout with media-led hero, story sections, gallery, and contact blocks.",
    ),
    "weather-app": FigmaTemplate(
        key="weather-app",
        name="Forge Weather Studio",
        archetype="weather-app",
        description="Data-forward weather dashboard with search, current conditions, and 5-day forecast cards.",
    ),
    "ecommerce-storefront": FigmaTemplate(
        key="ecommerce-storefront",
        name="Forge Storefront",
        archetype="ecommerce-storefront",
        description="Modern storefront layout with collection shelves, merchandising banners, and conversion CTAs.",
    ),
    "auth-saas-dashboard": FigmaTemplate(
        key="auth-saas-dashboard",
        name="Forge SaaS Console",
        archetype="auth-saas-dashboard",
        description="Product dashboard with auth shell, metrics, feeds, settings surfaces, and action rails.",
    ),
    "fastapi-backend": FigmaTemplate(
        key="fastapi-backend",
        name="Forge Backend Console",
        archetype="fastapi-backend",
        description="Internal operator console for backend-first products with docs, status, and deployment surfaces.",
    ),
}


def get_figma_template_for_archetype(archetype: str) -> FigmaTemplate | None:
    return DEFAULT_FIGMA_TEMPLATES.get(archetype)
