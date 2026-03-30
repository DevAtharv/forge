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
        frame_url="https://www.figma.com/design/hrRH2ovobT1su8jB2j8emP/Illustration-Based-Portfolio-Website-Template--Community-?node-id=412-655&m=dev&t=osgzVLja695fzhgv-1",
    ),
    "portfolio": FigmaTemplate(
        key="portfolio",
        name="Forge Creator Portfolio",
        archetype="portfolio",
        description="Editorial portfolio layout with media-led hero, story sections, gallery, and contact blocks.",
        frame_url="https://www.figma.com/community/file/1364626512225196457",
    ),
    "weather-app": FigmaTemplate(
        key="weather-app",
        name="Forge Weather Studio",
        archetype="weather-app",
        description="Data-forward weather dashboard with search, current conditions, and 5-day forecast cards.",
        frame_url="https://www.figma.com/community/file/1388954110053705224",
    ),
    "ecommerce-storefront": FigmaTemplate(
        key="ecommerce-storefront",
        name="Forge Storefront",
        archetype="ecommerce-storefront",
        description="Modern storefront layout with collection shelves, merchandising banners, and conversion CTAs.",
        frame_url="https://www.figma.com/community/file/1102233251923362930",
    ),
    "auth-saas-dashboard": FigmaTemplate(
        key="auth-saas-dashboard",
        name="Forge SaaS Console",
        archetype="auth-saas-dashboard",
        description="Product dashboard with auth shell, metrics, feeds, settings surfaces, and action rails.",
        frame_url="https://www.figma.com/community/file/1202668208106821162",
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
