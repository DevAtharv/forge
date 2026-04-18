from __future__ import annotations

import json
import re
from dataclasses import dataclass

from forge.figma_templates import get_figma_template_for_archetype
from forge.schemas import Artifact


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "forge-project"


@dataclass(frozen=True)
class BuildBlueprint:
    archetype: str
    project_name: str
    slug: str
    title: str
    headline: str
    accent: str
    figma_template_key: str | None = None
    figma_template_name: str | None = None
    figma_template_url: str | None = None
    figma_template_description: str | None = None


class HybridProjectBuilder:
    def choose_blueprint(self, prompt: str, *, project_name: str | None = None) -> BuildBlueprint:
        lower = prompt.lower()
        name = project_name or self._infer_project_name(prompt)
        slug = slugify(name)

        if any(token in lower for token in ("portfolio", "artist", "designer", "creator", "photographer", "writer")):
            return self._with_figma_template(
                BuildBlueprint(
                    archetype="portfolio",
                    project_name=name,
                    slug=slug,
                    title=f"{name} Portfolio",
                    headline="A cinematic portfolio with strong storytelling, featured work, and an intentional single-page flow.",
                    accent="#22c55e",
                )
            )

        if any(
            token in lower
            for token in (
                "tool",
                "app",
                "weather",
                "forecast",
                "calculator",
                "generator",
                "tracker",
                "converter",
                "dashboard",
            )
        ):
            return self._with_figma_template(
                BuildBlueprint(
                    archetype="simple-tool",
                    project_name=name,
                    slug=slug,
                    title=f"{name} Tool",
                    headline="A focused single-page tool with clear inputs, clear outputs, and polished presentation.",
                    accent="#7c3aed",
                )
            )

        return self._with_figma_template(
            BuildBlueprint(
                archetype="landing-page",
                project_name=name,
                slug=slug,
                title=name,
                headline="A polished launch-ready landing page with strong hierarchy, responsive sections, and clear calls to action.",
                accent="#0f766e",
            )
        )

    def _with_figma_template(self, blueprint: BuildBlueprint) -> BuildBlueprint:
        template = get_figma_template_for_archetype(blueprint.archetype)
        if template is None:
            return blueprint
        return BuildBlueprint(
            archetype=blueprint.archetype,
            project_name=blueprint.project_name,
            slug=blueprint.slug,
            title=blueprint.title,
            headline=blueprint.headline,
            accent=blueprint.accent,
            figma_template_key=template.key,
            figma_template_name=template.name,
            figma_template_url=template.frame_url,
            figma_template_description=template.description,
        )

    def build_files(self, blueprint: BuildBlueprint, prompt: str) -> list[Artifact]:
        files = self._build_nextjs_project(blueprint, prompt)
        return [
            Artifact(
                name=path,
                content=content,
                language=self._language_for_path(path),
                mime_type=self._mime_for_path(path),
            )
            for path, content in files.items()
        ]

    def _infer_project_name(self, prompt: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", prompt).strip()
        if not cleaned:
            return "Forge Project"
        words = cleaned.split()
        return " ".join(words[:4]).title()

    def _build_nextjs_project(self, blueprint: BuildBlueprint, prompt: str) -> dict[str, str]:
        sections = self._sections_for_blueprint(blueprint, prompt)
        serialized_sections = json.dumps(sections, indent=2)

        return {
            "package.json": self._package_json(blueprint.slug),
            "next.config.js": "/** @type {import('next').NextConfig} */\nconst nextConfig = {};\n\nmodule.exports = nextConfig;\n",
            "postcss.config.js": "module.exports = {\n  plugins: {\n    tailwindcss: {},\n    autoprefixer: {},\n  },\n};\n",
            "tailwind.config.js": "/** @type {import('tailwindcss').Config} */\nmodule.exports = {\n  content: [\"./app/**/*.{js,jsx}\", \"./components/**/*.{js,jsx}\"],\n  theme: {\n    extend: {\n      colors: {\n        ink: \"#0f172a\",\n        mist: \"#f8fafc\",\n        accent: \"var(--accent)\",\n        panel: \"var(--panel)\",\n      },\n      fontFamily: {\n        display: [\"Space Grotesk\", \"sans-serif\"],\n        body: [\"Manrope\", \"sans-serif\"],\n      },\n      boxShadow: {\n        panel: \"0 28px 80px rgba(15, 23, 42, 0.16)\",\n      },\n    },\n  },\n  plugins: [],\n};\n",
            "jsconfig.json": "{\n  \"compilerOptions\": {\n    \"baseUrl\": \".\"\n  }\n}\n",
            "app/layout.js": self._layout_js(blueprint.title),
            "app/page.js": self._page_js(blueprint, serialized_sections, prompt),
            "app/globals.css": self._globals_css(blueprint.accent),
            "components/section-data.js": f"export const pageSections = {serialized_sections};\n",
            "README.md": self._readme_md(blueprint),
            "vercel.json": "{\n  \"$schema\": \"https://openapi.vercel.sh/vercel.json\",\n  \"framework\": \"nextjs\"\n}\n",
            "terminal_commands.sh": "#!/usr/bin/env bash\nset -euo pipefail\nnpm install\nnpm run build\nnpx vercel --prod --yes\n",
        }

    def _package_json(self, slug: str) -> str:
        return (
            "{\n"
            f'  "name": "{slug}",\n'
            '  "private": true,\n'
            '  "version": "0.1.0",\n'
            '  "scripts": {\n'
            '    "dev": "next dev",\n'
            '    "build": "next build",\n'
            '    "start": "next start",\n'
            '    "lint": "next lint"\n'
            "  },\n"
            '  "dependencies": {\n'
            '    "next": "^14.2.28",\n'
            '    "react": "^18.3.1",\n'
            '    "react-dom": "^18.3.1"\n'
            "  },\n"
            '  "devDependencies": {\n'
            '    "autoprefixer": "^10.4.20",\n'
            '    "postcss": "^8.4.49",\n'
            '    "tailwindcss": "^3.4.17"\n'
            "  }\n"
            "}\n"
        )

    def _layout_js(self, title: str) -> str:
        safe_title = json.dumps(title)
        return (
            "import \"./globals.css\";\n\n"
            f"export const metadata = {{\n  title: {safe_title},\n  description: \"Generated by Forge with a constrained Next.js and Tailwind scaffold.\",\n}};\n\n"
            "export default function RootLayout({ children }) {\n"
            "  return (\n"
            "    <html lang=\"en\">\n"
            "      <body>{children}</body>\n"
            "    </html>\n"
            "  );\n"
            "}\n"
        )

    def _page_js(self, blueprint: BuildBlueprint, serialized_sections: str, prompt: str) -> str:
        intro = json.dumps(prompt.strip() or blueprint.headline)
        eyebrow = json.dumps(blueprint.archetype.replace("-", " ").title())
        title = json.dumps(blueprint.title)
        headline = json.dumps(blueprint.headline)
        return (
            "import { pageSections } from \"@/components/section-data\";\n\n"
            "const quickStats = [\n"
            "  { label: \"Build style\", value: \"Scaffold-first\" },\n"
            "  { label: \"Stack\", value: \"Next.js + Tailwind\" },\n"
            "  { label: \"Flow\", value: \"Single-page\" },\n"
            "];\n\n"
            "export default function HomePage() {\n"
            "  return (\n"
            "    <main className=\"min-h-screen bg-[var(--canvas)] text-slate-950\">\n"
            "      <div className=\"absolute inset-x-0 top-0 -z-10 h-[36rem] bg-[radial-gradient(circle_at_top,_rgba(255,255,255,0.8),_rgba(255,255,255,0))]\" />\n"
            "      <section className=\"mx-auto flex min-h-screen w-[min(1180px,calc(100vw-32px))] flex-col gap-10 py-8 md:py-12\">\n"
            "        <header className=\"glass-panel flex flex-col gap-6 rounded-[2rem] px-6 py-6 md:px-10 md:py-10\">\n"
            "          <div className=\"flex flex-col gap-4 md:flex-row md:items-start md:justify-between\">\n"
            "            <div className=\"max-w-3xl space-y-4\">\n"
            f"              <p className=\"eyebrow\">{eyebrow}</p>\n"
            f"              <h1 className=\"font-display text-4xl leading-[0.92] tracking-tight md:text-6xl\">{headline}</h1>\n"
            f"              <p className=\"max-w-2xl text-base text-slate-600 md:text-lg\">{intro}</p>\n"
            "            </div>\n"
            "            <div className=\"grid min-w-[240px] gap-3 sm:grid-cols-3 md:grid-cols-1\">\n"
            "              {quickStats.map((stat) => (\n"
            "                <article key={stat.label} className=\"rounded-[1.4rem] border border-white/70 bg-white/70 px-4 py-4 shadow-panel backdrop-blur\">\n"
            "                  <p className=\"text-xs uppercase tracking-[0.24em] text-slate-500\">{stat.label}</p>\n"
            "                  <strong className=\"mt-2 block text-lg font-semibold text-slate-900\">{stat.value}</strong>\n"
            "                </article>\n"
            "              ))}\n"
            "            </div>\n"
            "          </div>\n"
            "          <div className=\"flex flex-wrap gap-3\">\n"
            "            <a href=\"#sections\" className=\"rounded-full bg-[var(--accent)] px-5 py-3 text-sm font-semibold text-white transition hover:translate-y-[-1px]\">Explore Build</a>\n"
            "            <a href=\"#intent\" className=\"rounded-full border border-slate-300 px-5 py-3 text-sm font-semibold text-slate-800 transition hover:border-slate-900\">Prompt Intent</a>\n"
            "          </div>\n"
            "        </header>\n\n"
            "        <section className=\"grid gap-6 md:grid-cols-[1.1fr_0.9fr]\">\n"
            "          <article id=\"intent\" className=\"glass-panel rounded-[2rem] px-6 py-6 md:px-8 md:py-8\">\n"
            "            <p className=\"eyebrow\">Project Context</p>\n"
            f"            <h2 className=\"font-display text-3xl leading-tight text-slate-950\">{title}</h2>\n"
            "            <p className=\"mt-4 text-slate-600\">Forge keeps this implementation intentionally simple: a polished frontend built on top of a stable scaffold, with no hidden backend flows or authentication complexity.</p>\n"
            "          </article>\n"
            "          <article className=\"glass-panel rounded-[2rem] px-6 py-6 md:px-8 md:py-8\">\n"
            "            <p className=\"eyebrow\">Delivery Guardrails</p>\n"
            "            <ul className=\"grid gap-3 text-sm text-slate-700\">\n"
            "              <li className=\"rounded-2xl bg-white/70 px-4 py-4\">Single-page experience with responsive sections.</li>\n"
            "              <li className=\"rounded-2xl bg-white/70 px-4 py-4\">No auth, sessions, or backend coupling.</li>\n"
            "              <li className=\"rounded-2xl bg-white/70 px-4 py-4\">Vercel-friendly Next.js App Router structure.</li>\n"
            "            </ul>\n"
            "          </article>\n"
            "        </section>\n\n"
            "        <section id=\"sections\" className=\"grid gap-5\">\n"
            "          {pageSections.map((section) => (\n"
            "            <article key={section.title} className=\"glass-panel grid gap-5 rounded-[2rem] px-6 py-6 md:grid-cols-[0.8fr_1.2fr] md:px-8 md:py-8\">\n"
            "              <div>\n"
            "                <p className=\"eyebrow\">{section.kicker}</p>\n"
            "                <h3 className=\"font-display text-3xl leading-tight text-slate-950\">{section.title}</h3>\n"
            "              </div>\n"
            "              <div className=\"grid gap-3\">\n"
            "                <p className=\"text-slate-600\">{section.body}</p>\n"
            "                <div className=\"grid gap-3 sm:grid-cols-2\">\n"
            "                  {section.points.map((point) => (\n"
            "                    <div key={point} className=\"rounded-[1.35rem] border border-white/70 bg-white/75 px-4 py-4 text-sm text-slate-700 shadow-panel\">\n"
            "                      {point}\n"
            "                    </div>\n"
            "                  ))}\n"
            "                </div>\n"
            "              </div>\n"
            "            </article>\n"
            "          ))}\n"
            "        </section>\n"
            "      </section>\n"
            "    </main>\n"
            "  );\n"
            "}\n"
        )

    def _globals_css(self, accent: str) -> str:
        return f"""@import url("https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Space+Grotesk:wght@500;700&display=swap");

@tailwind base;
@tailwind components;
@tailwind utilities;

:root {{
  --canvas: #f3efe7;
  --ink: #0f172a;
  --panel: rgba(255, 255, 255, 0.72);
  --accent: {accent};
}}

* {{
  box-sizing: border-box;
}}

html {{
  scroll-behavior: smooth;
}}

body {{
  margin: 0;
  min-height: 100vh;
  font-family: "Manrope", sans-serif;
  background:
    radial-gradient(circle at top left, rgba(255, 255, 255, 0.92), rgba(255, 255, 255, 0)),
    linear-gradient(135deg, #f3efe7 0%, #efe4d3 45%, #e9ecef 100%);
  color: var(--ink);
}}

.glass-panel {{
  position: relative;
  overflow: hidden;
  border: 1px solid rgba(255, 255, 255, 0.72);
  background: var(--panel);
  box-shadow: 0 28px 80px rgba(15, 23, 42, 0.14);
  backdrop-filter: blur(18px);
}}

.eyebrow {{
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.26em;
  font-size: 0.72rem;
  color: color-mix(in srgb, var(--accent) 72%, #0f172a 28%);
}}
"""

    def _readme_md(self, blueprint: BuildBlueprint) -> str:
        return (
            f"# {blueprint.title}\n\n"
            "Generated by Forge's constrained scaffold pipeline.\n\n"
            "## Stack\n\n"
            "- Next.js App Router\n"
            "- Tailwind CSS\n"
            "- JavaScript only\n"
            "- Vercel-ready configuration\n\n"
            "## Run locally\n\n"
            "```bash\n"
            "npm install\n"
            "npm run dev\n"
            "```\n"
        )

    def _sections_for_blueprint(self, blueprint: BuildBlueprint, prompt: str) -> list[dict[str, object]]:
        if blueprint.archetype == "portfolio":
            return [
                {
                    "kicker": "Selected Work",
                    "title": "Projects that show craft instead of filler",
                    "body": "Use this section to spotlight high-signal work with strong outcomes, clear roles, and concise storytelling.",
                    "points": [
                        "Feature flagship work with visual proof.",
                        "Describe the role, constraints, and result.",
                        "Keep each project summary punchy and specific.",
                        "End with a clear invitation to collaborate.",
                    ],
                },
                {
                    "kicker": "Approach",
                    "title": "A clear process builds trust fast",
                    "body": "Structure the narrative around discovery, shaping, and shipping so visitors understand how the work gets done.",
                    "points": [
                        "Discovery grounded in user context.",
                        "Design direction with strong hierarchy.",
                        "Implementation that stays lightweight.",
                        "Delivery tuned for launch readiness.",
                    ],
                },
                {
                    "kicker": "Prompt Lens",
                    "title": "The original brief still drives the page",
                    "body": prompt.strip() or blueprint.headline,
                    "points": [
                        "Single-page structure keeps focus high.",
                        "No account wall or hidden backend dependencies.",
                        "Content can be swapped safely inside the scaffold.",
                        "Designed to stay easy to revise later.",
                    ],
                },
            ]

        if blueprint.archetype == "simple-tool":
            return [
                {
                    "kicker": "Inputs",
                    "title": "A simple tool needs immediate clarity",
                    "body": "Lead with obvious actions, lightweight explanation, and a surface that feels trustworthy before any interaction happens.",
                    "points": [
                        "Prominent primary action above the fold.",
                        "Clear explanatory copy without jargon.",
                        "Layout that works on desktop and mobile.",
                        "Styling that feels like a product, not a demo.",
                    ],
                },
                {
                    "kicker": "Outputs",
                    "title": "Make the result area feel ready for real use",
                    "body": "Whether the tool summarizes, calculates, converts, or previews something, the result panel should feel deliberate and easy to scan.",
                    "points": [
                        "Reserved space for results and feedback.",
                        "Supporting hints placed near the output.",
                        "Secondary details grouped, not scattered.",
                        "No fake backend steps or blocked workflows.",
                    ],
                },
                {
                    "kicker": "Prompt Lens",
                    "title": "Forge keeps the tool inside a safe frontend boundary",
                    "body": prompt.strip() or blueprint.headline,
                    "points": [
                        "No auth or persistent accounts required.",
                        "No custom API server or database assumptions.",
                        "Scaffold-first page structure for easy edits.",
                        "Vercel-friendly file set out of the box.",
                    ],
                },
            ]

        return [
            {
                "kicker": "Story",
                "title": "A landing page should lead with conviction",
                "body": "The hero, supporting proof, and call-to-action need to feel aligned, not assembled from unrelated blocks.",
                "points": [
                    "A high-contrast hero with clear value.",
                    "Proof points that reduce hesitation quickly.",
                    "A clean rhythm from section to section.",
                    "Calls to action that feel intentional.",
                ],
            },
            {
                "kicker": "Offer",
                "title": "Each section should earn the next scroll",
                "body": "Use mid-page sections to explain the offer, show what makes it credible, and keep momentum through the page.",
                "points": [
                    "Feature blocks with concise supporting copy.",
                    "A balanced mix of confidence and restraint.",
                    "Responsive layout tuned for small screens.",
                    "No multi-page detours or hidden complexity.",
                ],
            },
            {
                "kicker": "Prompt Lens",
                "title": "This build stays anchored to the original request",
                "body": prompt.strip() or blueprint.headline,
                "points": [
                    "Next.js App Router with Tailwind CSS.",
                    "JavaScript-first scaffold for predictable output.",
                    "No auth, backend, or database coupling.",
                    "Safe to iterate by swapping copy and sections.",
                ],
            },
        ]

    def _language_for_path(self, path: str) -> str | None:
        lower = path.lower()
        if lower.endswith(".js"):
            return "javascript"
        if lower.endswith(".css"):
            return "css"
        if lower.endswith(".json"):
            return "json"
        if lower.endswith(".md"):
            return "markdown"
        if lower.endswith(".sh"):
            return "bash"
        return None

    def _mime_for_path(self, path: str) -> str:
        lower = path.lower()
        if lower.endswith(".css"):
            return "text/css"
        if lower.endswith(".json"):
            return "application/json"
        if lower.endswith(".md"):
            return "text/markdown"
        if lower.endswith(".sh"):
            return "text/x-shellscript"
        if lower.endswith(".js"):
            return "text/javascript"
        return "text/plain"
