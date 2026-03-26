from __future__ import annotations

import re
from dataclasses import dataclass

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


class HybridProjectBuilder:
    def choose_blueprint(self, prompt: str, *, project_name: str | None = None) -> BuildBlueprint:
        lower = prompt.lower()
        name = project_name or self._infer_project_name(prompt)
        slug = slugify(name)
        if any(token in lower for token in ("shop", "store", "sweet", "ecommerce", "e-commerce")):
            return BuildBlueprint(
                archetype="ecommerce-storefront",
                project_name=name,
                slug=slug,
                title=f"{name} Storefront",
                headline="A premium storefront with account access, featured collections, and rapid checkout cues.",
                accent="#f59e0b",
            )
        if any(token in lower for token in ("portfolio", "artist", "singer", "creator")):
            return BuildBlueprint(
                archetype="portfolio",
                project_name=name,
                slug=slug,
                title=f"{name} Portfolio",
                headline="A cinematic portfolio with bold typography, media sections, and a protected workspace.",
                accent="#22c55e",
            )
        if any(token in lower for token in ("weather", "forecast", "climate")):
            return BuildBlueprint(
                archetype="weather-app",
                project_name=name,
                slug=slug,
                title=f"{name} Weather",
                headline="A polished live weather dashboard with forecast cards, city search, and launch-ready UI.",
                accent="#7dd3fc",
            )
        if any(token in lower for token in ("saas", "dashboard", "auth", "admin")):
            return BuildBlueprint(
                archetype="auth-saas-dashboard",
                project_name=name,
                slug=slug,
                title=f"{name} Workspace",
                headline="A product-grade authenticated dashboard with mission feed, projects, and deploy controls.",
                accent="#38bdf8",
            )
        if any(token in lower for token in ("api", "fastapi", "backend")):
            return BuildBlueprint(
                archetype="fastapi-backend",
                project_name=name,
                slug=slug,
                title=f"{name} API",
                headline="A backend-first workspace with generated endpoints, auth hooks, and deploy commands.",
                accent="#a78bfa",
            )
        return BuildBlueprint(
            archetype="landing-page",
            project_name=name,
            slug=slug,
            title=name,
            headline="A polished launch-ready web experience with authentication and deploy-ready structure.",
            accent="#38bdf8",
        )

    def build_files(self, blueprint: BuildBlueprint, prompt: str) -> list[Artifact]:
        if blueprint.archetype == "fastapi-backend":
            return self._build_fastapi_backend(blueprint, prompt)
        if blueprint.archetype == "weather-app":
            return self._build_weather_app(blueprint, prompt)
        return self._build_web_app(blueprint, prompt)

    def _infer_project_name(self, prompt: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", prompt).strip()
        if not cleaned:
            return "Forge Project"
        words = cleaned.split()
        return " ".join(words[:4]).title()

    def _build_web_app(self, blueprint: BuildBlueprint, prompt: str) -> list[Artifact]:
        title = blueprint.title
        slug = blueprint.slug
        accent = blueprint.accent
        files = {
            "package.json": f"""{{
  "name": "{slug}",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "@supabase/supabase-js": "^2.49.8",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  }},
  "devDependencies": {{
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^5.4.10"
  }}
}}""",
            "index.html": f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet" />
    <script type="module" src="/src/main.tsx"></script>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>""",
            "vite.config.ts": """import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
});""",
            "tsconfig.json": """{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": []
}""",
            "src/main.tsx": """import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);""",
            "src/lib/supabase.ts": """import { createClient } from "@supabase/supabase-js";

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL as string;
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string;

export const supabase =
  supabaseUrl && supabaseAnonKey ? createClient(supabaseUrl, supabaseAnonKey) : null;""",
            "src/pages/Login.tsx": """type LoginProps = {
  mode: "signin" | "signup";
  email: string;
  password: string;
  onEmailChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onModeChange: (mode: "signin" | "signup") => void;
  onSubmit: () => Promise<void>;
  status: string;
};

export function Login(props: LoginProps) {
  const { mode, email, password, onEmailChange, onPasswordChange, onModeChange, onSubmit, status } = props;

  return (
    <section className="panel auth-panel">
      <p className="eyebrow">Workspace Access</p>
      <h2>Authenticate and launch the build pipeline.</h2>
      <div className="tab-row">
        <button className={mode === "signin" ? "tab active" : "tab"} onClick={() => onModeChange("signin")}>Sign In</button>
        <button className={mode === "signup" ? "tab active" : "tab"} onClick={() => onModeChange("signup")}>Create Account</button>
      </div>
      <label>Email</label>
      <input value={email} onChange={(event) => onEmailChange(event.target.value)} type="email" />
      <label>Password</label>
      <input value={password} onChange={(event) => onPasswordChange(event.target.value)} type="password" />
      <button className="primary-button" onClick={() => void onSubmit()}>
        {mode === "signup" ? "Create Workspace" : "Open Workspace"}
      </button>
      <p className="muted status-line">{status}</p>
    </section>
  );
}""",
            "src/pages/Dashboard.tsx": """type DashboardProps = {
  email: string;
  onSignOut: () => Promise<void>;
};

const cards = [
  { title: "Build Queue", value: "3", note: "active missions" },
  { title: "Deploy Readiness", value: "92%", note: "pre-flight score" },
  { title: "Git Sync", value: "clean", note: "latest revision pushed" },
];

export function Dashboard(props: DashboardProps) {
  return (
    <section className="panel dashboard-panel">
      <div className="dashboard-topbar">
        <div>
          <p className="eyebrow">Authenticated Workspace</p>
          <h2>__TITLE__</h2>
          <p className="muted">Signed in as {props.email}</p>
        </div>
        <button className="secondary-button" onClick={() => void props.onSignOut()}>
          Sign out
        </button>
      </div>
      <div className="metric-grid">
        {cards.map((card) => (
          <article className="metric-card" key={card.title}>
            <p>{card.title}</p>
            <strong>{card.value}</strong>
            <span>{card.note}</span>
          </article>
        ))}
      </div>
      <div className="mission-card">
        <p className="eyebrow">Current Prompt</p>
        <h3>__HEADLINE__</h3>
        <p className="muted">__PROMPT__</p>
      </div>
    </section>
  );
}""".replace("__TITLE__", title).replace("__HEADLINE__", blueprint.headline).replace("__PROMPT__", prompt),
            "src/App.tsx": """import { useEffect, useState } from "react";
import { supabase } from "./lib/supabase";
import { Dashboard } from "./pages/Dashboard";
import { Login } from "./pages/Login";

type AuthMode = "signin" | "signup";

export default function App() {
  const [mode, setMode] = useState<AuthMode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [status, setStatus] = useState("Connect Supabase to enable persistent auth.");
  const [userEmail, setUserEmail] = useState<string | null>(null);

  useEffect(() => {
    if (!supabase) {
      setStatus("Missing VITE_SUPABASE_URL or VITE_SUPABASE_ANON_KEY.");
      return;
    }
    void supabase.auth.getSession().then(({ data, error }) => {
      if (error) {
        setStatus(error.message);
        return;
      }
      setUserEmail(data.session?.user?.email ?? null);
      if (data.session?.user?.email) {
        setStatus("Session restored.");
      }
    });
  }, []);

  const submit = async () => {
    if (!supabase) {
      setStatus("Supabase is not configured.");
      return;
    }
    setStatus("Processing...");
    const response =
      mode === "signup"
        ? await supabase.auth.signUp({ email, password })
        : await supabase.auth.signInWithPassword({ email, password });
    if (response.error) {
      setStatus(response.error.message);
      return;
    }
    const resolvedEmail = response.data.user?.email ?? response.data.session?.user?.email ?? email;
    setUserEmail(resolvedEmail);
    setStatus(mode === "signup" ? "Account created. Check your email if verification is enabled." : "Signed in.");
  };

  const signOut = async () => {
    if (!supabase) {
      return;
    }
    const response = await supabase.auth.signOut();
    if (response.error) {
      setStatus(response.error.message);
      return;
    }
    setUserEmail(null);
    setStatus("Signed out.");
  };

  return (
    <main className="shell">
      <section className="hero-panel">
        <p className="eyebrow">Forge Hybrid Builder</p>
        <h1>Production-ready workspace generated from a structured scaffold, not weak one-shot output.</h1>
        <p className="muted">
          This starter includes Supabase authentication, a protected dashboard, strong visual hierarchy,
          and Vercel-ready deployment configuration.
        </p>
      </section>
      {userEmail ? (
        <Dashboard email={userEmail} onSignOut={signOut} />
      ) : (
        <Login
          mode={mode}
          email={email}
          password={password}
          onEmailChange={setEmail}
          onPasswordChange={setPassword}
          onModeChange={setMode}
          onSubmit={submit}
          status={status}
        />
      )}
    </main>
  );
}""",
            "src/styles.css": f""":root {{
  color-scheme: dark;
  --bg: #07111f;
  --panel: rgba(9, 16, 31, 0.78);
  --panel-border: rgba(255, 255, 255, 0.08);
  --text: #edf5ff;
  --muted: #b8c6dc;
  --accent: {accent};
}}

* {{
  box-sizing: border-box;
}}

body {{
  margin: 0;
  font-family: Inter, sans-serif;
  background:
    radial-gradient(circle at top left, rgba(56, 189, 248, 0.18), transparent 30%),
    radial-gradient(circle at top right, rgba(245, 158, 11, 0.15), transparent 26%),
    linear-gradient(135deg, #07111f 0%, #0d172b 55%, #050912 100%);
  color: var(--text);
  min-height: 100vh;
}}

.shell {{
  width: min(1180px, 92vw);
  margin: 0 auto;
  padding: 40px 0 80px;
  display: grid;
  gap: 24px;
}}

.hero-panel,
.panel {{
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 24px;
  padding: 28px;
  backdrop-filter: blur(16px);
  box-shadow: 0 24px 70px rgba(0, 0, 0, 0.35);
}}

.hero-panel h1,
.panel h2 {{
  font-family: "Space Grotesk", sans-serif;
  line-height: 1.05;
  margin: 0 0 12px;
}}

.eyebrow {{
  text-transform: uppercase;
  letter-spacing: 0.16em;
  font-size: 0.78rem;
  color: var(--accent);
  margin: 0 0 10px;
}}

.muted {{
  color: var(--muted);
}}

.auth-panel,
.dashboard-panel {{
  display: grid;
  gap: 14px;
}}

label {{
  font-size: 0.9rem;
  color: var(--muted);
}}

input {{
  width: 100%;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.03);
  color: var(--text);
  padding: 14px 16px;
  font: inherit;
}}

button {{
  font: inherit;
  cursor: pointer;
}}

.primary-button,
.secondary-button,
.tab {{
  border-radius: 14px;
  border: 0;
  padding: 12px 16px;
}}

.primary-button {{
  background: linear-gradient(90deg, var(--accent), #38bdf8);
  color: #051018;
  font-weight: 700;
}}

.secondary-button {{
  background: rgba(255, 255, 255, 0.06);
  color: var(--text);
}}

.tab-row {{
  display: flex;
  gap: 10px;
}}

.tab {{
  background: rgba(255, 255, 255, 0.05);
  color: var(--muted);
}}

.tab.active {{
  color: var(--text);
  background: rgba(255, 255, 255, 0.12);
}}

.metric-grid {{
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 14px;
}}

.metric-card,
.mission-card {{
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 18px;
  padding: 18px;
  background: rgba(255, 255, 255, 0.03);
}}

.metric-card strong {{
  display: block;
  font-size: 1.8rem;
  font-family: "Space Grotesk", sans-serif;
  margin: 8px 0 4px;
}}

.dashboard-topbar {{
  display: flex;
  justify-content: space-between;
  gap: 18px;
  align-items: start;
}}

.status-line {{
  min-height: 1.2rem;
}}

@media (max-width: 820px) {{
  .metric-grid {{
    grid-template-columns: 1fr;
  }}

  .dashboard-topbar {{
    flex-direction: column;
  }}
}}""",
            ".env.example": """VITE_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
VITE_SUPABASE_ANON_KEY=YOUR_SUPABASE_ANON_KEY""",
            "vercel.json": """{
  "cleanUrls": true,
  "trailingSlash": false
}""",
            "terminal_commands.sh": """#!/usr/bin/env bash
set -euo pipefail
npm install
npm run build
npx vercel --prod --yes""",
        }
        return [
            Artifact(
                name=path,
                content=content,
                language=self._language_for_path(path),
                mime_type=self._mime_for_path(path),
            )
            for path, content in files.items()
        ]

    def _build_weather_app(self, blueprint: BuildBlueprint, prompt: str) -> list[Artifact]:
        slug = blueprint.slug
        title = blueprint.title
        files = {
            "package.json": f"""{{
  "name": "{slug}",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {{
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview"
  }},
  "dependencies": {{
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  }},
  "devDependencies": {{
    "@types/react": "^18.3.18",
    "@types/react-dom": "^18.3.5",
    "@vitejs/plugin-react": "^4.3.4",
    "typescript": "^5.6.3",
    "vite": "^5.4.10"
  }}
}}""",
            "index.html": f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Instrument+Sans:wght@400;500;600&display=swap" rel="stylesheet" />
    <script type="module" src="/src/main.tsx"></script>
  </head>
  <body>
    <div id="root"></div>
  </body>
</html>""",
            "vite.config.ts": """import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
});""",
            "tsconfig.json": """{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "allowJs": false,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "allowSyntheticDefaultImports": true,
    "strict": true,
    "forceConsistentCasingInFileNames": true,
    "module": "ESNext",
    "moduleResolution": "Node",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx"
  },
  "include": ["src"],
  "references": []
}""",
            "src/main.tsx": """import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./styles.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);""",
            "src/App.tsx": """import { useEffect, useState } from "react";

type WeatherPayload = {
  city: string;
  temperature: number;
  windspeed: number;
  weatherCode: number;
  time: string;
  forecast: Array<{ label: string; high: number; low: number }>;
};

const seedCities = ["London", "Tokyo", "New York", "Delhi"];

const codeLabels: Record<number, string> = {
  0: "Clear sky",
  1: "Mostly clear",
  2: "Partly cloudy",
  3: "Overcast",
  45: "Fog",
  51: "Light drizzle",
  61: "Light rain",
  63: "Rain",
  71: "Snow",
  95: "Thunderstorm",
};

async function fetchWeather(city: string): Promise<WeatherPayload> {
  const geoResponse = await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(city)}&count=1`);
  const geo = await geoResponse.json();
  const place = geo.results?.[0];
  if (!place) {
    throw new Error("City not found.");
  }

  const weatherResponse = await fetch(
    `https://api.open-meteo.com/v1/forecast?latitude=${place.latitude}&longitude=${place.longitude}&current=temperature_2m,weather_code,wind_speed_10m&daily=temperature_2m_max,temperature_2m_min&timezone=auto`,
  );
  const weather = await weatherResponse.json();

  return {
    city: `${place.name}, ${place.country_code}`,
    temperature: Math.round(weather.current.temperature_2m),
    windspeed: Math.round(weather.current.wind_speed_10m),
    weatherCode: weather.current.weather_code,
    time: weather.current.time,
    forecast: weather.daily.time.slice(0, 5).map((date: string, index: number) => ({
      label: new Date(date).toLocaleDateString(undefined, { weekday: "short" }),
      high: Math.round(weather.daily.temperature_2m_max[index]),
      low: Math.round(weather.daily.temperature_2m_min[index]),
    })),
  };
}

export default function App() {
  const [query, setQuery] = useState("Delhi");
  const [weather, setWeather] = useState<WeatherPayload | null>(null);
  const [status, setStatus] = useState("Loading live weather...");

  useEffect(() => {
    void loadCity("Delhi");
  }, []);

  const loadCity = async (city: string) => {
    setStatus(`Loading ${city}...`);
    try {
      const payload = await fetchWeather(city);
      setWeather(payload);
      setStatus("Live data loaded from Open-Meteo.");
      setQuery(city);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : "Failed to load weather.");
    }
  };

  return (
    <main className="shell">
      <section className="hero">
        <div className="hero-copy">
          <p className="eyebrow">Forge Weather Studio</p>
          <h1>Live forecast, bold visuals, and a landing page that feels like a real product.</h1>
          <p className="subcopy">
            Generated from a stronger Forge scaffold for prompts like: __PROMPT__
          </p>
          <div className="search-row">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search a city"
            />
            <button onClick={() => void loadCity(query)}>Check weather</button>
          </div>
          <div className="chip-row">
            {seedCities.map((city) => (
              <button key={city} className="chip" onClick={() => void loadCity(city)}>
                {city}
              </button>
            ))}
          </div>
          <p className="status">{status}</p>
        </div>
        <div className="hero-card">
          <p className="hero-card-label">Current Conditions</p>
          <h2>{weather?.city ?? "Waiting for data"}</h2>
          <div className="temp-row">
            <strong>{weather ? `${weather.temperature}°` : "--"}</strong>
            <span>{weather ? codeLabels[weather.weatherCode] ?? "Dynamic weather" : "Forecast incoming"}</span>
          </div>
          <div className="detail-grid">
            <article>
              <span>Wind</span>
              <strong>{weather ? `${weather.windspeed} km/h` : "--"}</strong>
            </article>
            <article>
              <span>Updated</span>
              <strong>{weather ? new Date(weather.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "--"}</strong>
            </article>
          </div>
        </div>
      </section>

      <section className="forecast-panel">
        <div className="section-head">
          <p className="eyebrow">Five Day Outlook</p>
          <h3>Forecast cards with real temperature ranges</h3>
        </div>
        <div className="forecast-grid">
          {(weather?.forecast ?? []).map((day) => (
            <article key={day.label} className="forecast-card">
              <p>{day.label}</p>
              <strong>{day.high}°</strong>
              <span>{day.low}° overnight</span>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}""".replace("__PROMPT__", prompt),
            "src/styles.css": """:root {
  color-scheme: dark;
  --bg-1: #031525;
  --bg-2: #0c2340;
  --panel: rgba(8, 22, 40, 0.72);
  --panel-border: rgba(255, 255, 255, 0.1);
  --text: #f3f8ff;
  --muted: #a9bbd3;
  --accent: #7dd3fc;
  --accent-2: #fde68a;
}

* {
  box-sizing: border-box;
}

body {
  margin: 0;
  min-height: 100vh;
  font-family: "Instrument Sans", sans-serif;
  color: var(--text);
  background:
    radial-gradient(circle at top left, rgba(125, 211, 252, 0.32), transparent 28%),
    radial-gradient(circle at 80% 10%, rgba(253, 230, 138, 0.18), transparent 24%),
    linear-gradient(145deg, var(--bg-1) 0%, var(--bg-2) 48%, #020814 100%);
}

.shell {
  width: min(1180px, calc(100vw - 32px));
  margin: 0 auto;
  padding: 32px 0 72px;
}

.hero,
.forecast-panel {
  background: var(--panel);
  border: 1px solid var(--panel-border);
  border-radius: 28px;
  backdrop-filter: blur(20px);
  box-shadow: 0 28px 60px rgba(0, 0, 0, 0.28);
}

.hero {
  display: grid;
  grid-template-columns: 1.3fr 0.9fr;
  gap: 24px;
  padding: 28px;
}

.hero-copy h1,
.hero-card h2,
.section-head h3 {
  margin: 0;
  font-family: Sora, sans-serif;
}

.hero-copy h1 {
  font-size: clamp(2.4rem, 5vw, 4.6rem);
  line-height: 0.96;
  margin-bottom: 14px;
}

.eyebrow {
  margin: 0 0 12px;
  text-transform: uppercase;
  letter-spacing: 0.18em;
  color: var(--accent);
  font-size: 0.74rem;
}

.subcopy,
.status,
.hero-card-label,
.forecast-card span,
.detail-grid span {
  color: var(--muted);
}

.search-row {
  display: flex;
  gap: 12px;
  margin: 22px 0 14px;
}

.search-row input,
.search-row button,
.chip {
  border: 0;
  border-radius: 16px;
  font: inherit;
}

.search-row input {
  flex: 1;
  padding: 15px 16px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text);
}

.search-row button,
.chip {
  cursor: pointer;
}

.search-row button {
  padding: 15px 18px;
  background: linear-gradient(135deg, var(--accent), #38bdf8);
  color: #052033;
  font-weight: 700;
}

.chip-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.chip {
  padding: 10px 14px;
  background: rgba(255, 255, 255, 0.06);
  color: var(--text);
}

.hero-card {
  border-radius: 24px;
  padding: 24px;
  background:
    linear-gradient(180deg, rgba(125, 211, 252, 0.18), rgba(255, 255, 255, 0.02)),
    rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.temp-row {
  display: flex;
  align-items: end;
  gap: 14px;
  margin: 20px 0;
}

.temp-row strong {
  font-size: clamp(3.5rem, 10vw, 6rem);
  line-height: 0.9;
  font-family: Sora, sans-serif;
}

.detail-grid,
.forecast-grid {
  display: grid;
  gap: 14px;
}

.detail-grid {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.detail-grid article,
.forecast-card {
  border-radius: 18px;
  padding: 16px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid rgba(255, 255, 255, 0.08);
}

.forecast-panel {
  margin-top: 22px;
  padding: 26px;
}

.forecast-grid {
  grid-template-columns: repeat(5, minmax(0, 1fr));
}

.forecast-card strong {
  display: block;
  margin: 10px 0 4px;
  font-size: 1.6rem;
  font-family: Sora, sans-serif;
}

@media (max-width: 900px) {
  .hero {
    grid-template-columns: 1fr;
  }

  .forecast-grid {
    grid-template-columns: 1fr 1fr;
  }
}

@media (max-width: 560px) {
  .shell {
    width: min(100vw - 20px, 1180px);
    padding-top: 18px;
  }

  .hero,
  .forecast-panel {
    padding: 18px;
    border-radius: 22px;
  }

  .search-row,
  .forecast-grid,
  .detail-grid {
    grid-template-columns: 1fr;
  }

  .search-row {
    display: grid;
  }
}""",
            "README.md": f"""# {title}

Generated by Forge Hybrid Builder.

## What you get

- Vite + React + TypeScript frontend
- Real live weather data from Open-Meteo
- Mobile-friendly forecast dashboard
- Vercel-ready deployment config

## Run locally

```bash
npm install
npm run dev
```""",
            "vercel.json": """{
  "cleanUrls": true,
  "trailingSlash": false
}""",
            "terminal_commands.sh": """#!/usr/bin/env bash
set -euo pipefail
npm install
npm run build
npx vercel --prod --yes""",
        }
        return [
            Artifact(
                name=path,
                content=content,
                language=self._language_for_path(path),
                mime_type=self._mime_for_path(path),
            )
            for path, content in files.items()
        ]

    def _build_fastapi_backend(self, blueprint: BuildBlueprint, prompt: str) -> list[Artifact]:
        slug = blueprint.slug
        files = {
            "requirements.txt": """fastapi==0.115.0
uvicorn==0.30.0
pydantic==2.9.2
python-dotenv==1.0.1""",
            "main.py": f"""from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="{blueprint.title}")


class HealthResponse(BaseModel):
    status: str
    project: str


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", project="{blueprint.title}")


@app.get("/")
async def root() -> dict[str, str]:
    return {{
        "message": "{prompt}",
        "project": "{blueprint.project_name}",
    }}
""",
            "README.md": f"""# {blueprint.title}

Generated by Forge Hybrid Builder.

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```""",
            "vercel.json": """{
  "version": 2,
  "builds": [{ "src": "main.py", "use": "@vercel/python" }],
  "routes": [{ "src": "/(.*)", "dest": "main.py" }]
}""",
            "terminal_commands.sh": """#!/usr/bin/env bash
set -euo pipefail
pip install -r requirements.txt
uvicorn main:app --reload""",
        }
        return [
            Artifact(
                name=path,
                content=content,
                language=self._language_for_path(path),
                mime_type=self._mime_for_path(path),
            )
            for path, content in files.items()
        ]

    def _language_for_path(self, path: str) -> str | None:
        if path.endswith(".tsx"):
            return "tsx"
        if path.endswith(".ts"):
            return "typescript"
        if path.endswith(".css"):
            return "css"
        if path.endswith(".html"):
            return "html"
        if path.endswith(".json"):
            return "json"
        if path.endswith(".py"):
            return "python"
        if path.endswith(".sh"):
            return "bash"
        if path.endswith(".md"):
            return "markdown"
        return None

    def _mime_for_path(self, path: str) -> str:
        if path.endswith(".tsx") or path.endswith(".ts"):
            return "text/typescript"
        if path.endswith(".css"):
            return "text/css"
        if path.endswith(".html"):
            return "text/html"
        if path.endswith(".json"):
            return "application/json"
        if path.endswith(".py"):
            return "text/x-python"
        if path.endswith(".sh"):
            return "text/x-shellscript"
        if path.endswith(".md"):
            return "text/markdown"
        return "text/plain"
