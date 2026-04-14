from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path


def _load_env_file(path: Path) -> None:
    if not path.exists() or not path.is_file():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or key in os.environ:
            continue
        if value and len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        os.environ[key] = value


def _load_local_env_files() -> None:
    root = Path.cwd()
    for name in (".env", ".env.local"):
        _load_env_file(root / name)


_load_local_env_files()


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name, default)
    if value is None:
        return None
    value = value.strip()
    return value or default


def _env_int(name: str, default: int) -> int:
    value = _env(name)
    if value is None:
        return default
    return int(value)


def _env_float(name: str, default: float) -> float:
    value = _env(name)
    if value is None:
        return default
    return float(value)


def _env_list(name: str) -> tuple[str, ...]:
    value = _env(name, "") or ""
    items = [item.strip() for item in value.split(",")]
    return tuple(item for item in items if item)


@dataclass(frozen=True)
class ModelRoute:
    provider: str
    model: str


def normalize_model_route(provider: str, model: str) -> tuple[str, str]:
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip()
    if normalized_provider == "openrouter" and normalized_model in {"openrouter/free", "openrouter/openrouter/free"}:
        return normalized_provider, "openrouter/auto"
    if normalized_provider == "nvidia" and normalized_model in {"meta/llama-3.1-70b-instruct"}:
        return normalized_provider, "nemotron-3-super-120b-a12b"
    return normalized_provider, normalized_model


def parse_model_routes(value: str, fallback: str) -> tuple[ModelRoute, ...]:
    raw = value or fallback
    routes: list[ModelRoute] = []
    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        if "/" not in token:
            raise ValueError(f"Invalid model route '{token}'. Expected provider/model.")
        provider, model = token.split("/", 1)
        provider, model = normalize_model_route(provider, model)
        routes.append(ModelRoute(provider=provider, model=model))
    return tuple(routes)


@dataclass(frozen=True)
class Settings:
    app_env: str
    public_base_url: str
    frontend_base_url: str
    telegram_token: str
    webhook_secret: str
    groq_api_key: str
    nvidia_api_key: str
    openrouter_api_key: str
    tavily_api_key: str
    gemini_api_keys: tuple[str, ...]
    search_provider: str
    managed_preview_vercel_token: str
    managed_preview_vercel_team_id: str
    managed_preview_vercel_team_slug: str
    credential_secret: str
    github_client_id: str
    github_client_secret: str
    vercel_client_id: str
    vercel_client_secret: str
    vercel_integration_slug: str
    figma_template_urls: dict[str, str]
    supabase_url: str
    supabase_key: str
    supabase_anon_key: str
    telegram_bot_username: str
    worker_id: str
    worker_poll_interval_seconds: float
    worker_batch_size: int
    worker_lock_timeout_seconds: int
    worker_retry_backoff_seconds: int
    worker_max_attempts: int
    history_window: int
    search_result_limit: int
    fetch_timeout_seconds: int
    auth_timeout_seconds: int
    cors_allowed_origins: tuple[str, ...]
    orchestrator_routes: tuple[ModelRoute, ...]
    planner_routes: tuple[ModelRoute, ...]
    code_routes: tuple[ModelRoute, ...]
    debug_routes: tuple[ModelRoute, ...]
    reviewer_routes: tuple[ModelRoute, ...]
    research_routes: tuple[ModelRoute, ...]
    summary_routes: tuple[ModelRoute, ...]

    @classmethod
    def from_env(cls) -> "Settings":
        hostname = socket.gethostname().lower().replace(" ", "-")
        return cls(
            app_env=_env("APP_ENV", "development") or "development",
            public_base_url=_env("FORGE_PUBLIC_BASE_URL", "http://localhost:8000") or "http://localhost:8000",
            frontend_base_url=_env("FORGE_FRONTEND_BASE_URL", "http://localhost:3000") or "http://localhost:3000",
            telegram_token=_env("TELEGRAM_TOKEN", "") or "",
            webhook_secret=_env("WEBHOOK_SECRET", "") or "",
            groq_api_key=_env("GROQ_API_KEY", "") or "",
            nvidia_api_key=_env("NVIDIA_API_KEY", "") or "",
            openrouter_api_key=_env("OPENROUTER_API_KEY", "") or "",
            tavily_api_key=_env("TAVILY_API_KEY", "") or "",
            gemini_api_keys=_env_list("GEMINI_API_KEYS"),
            search_provider=_env("FORGE_SEARCH_PROVIDER", "auto") or "auto",
            managed_preview_vercel_token=_env("FORGE_MANAGED_PREVIEW_VERCEL_TOKEN", "") or "",
            managed_preview_vercel_team_id=_env("FORGE_MANAGED_PREVIEW_VERCEL_TEAM_ID", "") or "",
            managed_preview_vercel_team_slug=_env("FORGE_MANAGED_PREVIEW_VERCEL_TEAM_SLUG", "") or "",
            credential_secret=_env("FORGE_CREDENTIAL_SECRET", "forge-dev-secret") or "forge-dev-secret",
            github_client_id=_env("GITHUB_CLIENT_ID", "") or "",
            github_client_secret=_env("GITHUB_CLIENT_SECRET", "") or "",
            vercel_client_id=_env("VERCEL_CLIENT_ID", "") or "",
            vercel_client_secret=_env("VERCEL_CLIENT_SECRET", "") or "",
            vercel_integration_slug=_env("VERCEL_INTEGRATION_SLUG", "forge") or "forge",
            figma_template_urls={
                "landing-page": _env("FORGE_FIGMA_TEMPLATE_LANDING_PAGE", "") or "",
                "portfolio": _env("FORGE_FIGMA_TEMPLATE_PORTFOLIO", "") or "",
                "weather-app": _env("FORGE_FIGMA_TEMPLATE_WEATHER_APP", "") or "",
                "ecommerce-storefront": _env("FORGE_FIGMA_TEMPLATE_ECOMMERCE", "") or "",
                "food-delivery-app": _env("FORGE_FIGMA_TEMPLATE_FOOD_DELIVERY_APP", "") or "",
                "auth-saas-dashboard": _env("FORGE_FIGMA_TEMPLATE_AUTH_SAAS_DASHBOARD", "") or "",
                "fastapi-backend": _env("FORGE_FIGMA_TEMPLATE_FASTAPI_BACKEND", "") or "",
            },
            supabase_url=_env("SUPABASE_URL", "") or "",
            supabase_key=_env("SUPABASE_KEY", "") or "",
            supabase_anon_key=_env("SUPABASE_ANON_KEY", _env("SUPABASE_KEY", "") or "") or "",
            telegram_bot_username=_env("TELEGRAM_BOT_USERNAME", "ForggeBot") or "ForggeBot",
            worker_id=_env("FORGE_WORKER_ID", f"{hostname}-{os.getpid()}") or f"{hostname}-{os.getpid()}",
            worker_poll_interval_seconds=_env_float("FORGE_WORKER_POLL_INTERVAL_SECONDS", 0.5),
            worker_batch_size=_env_int("FORGE_WORKER_BATCH_SIZE", 1),
            worker_lock_timeout_seconds=_env_int("FORGE_WORKER_LOCK_TIMEOUT_SECONDS", 300),
            worker_retry_backoff_seconds=_env_int("FORGE_WORKER_RETRY_BACKOFF_SECONDS", 30),
            gemini_api_keys=_env_list("GEMINI_API_KEYS"),
            search_provider=_env("FORGE_SEARCH_PROVIDER", "auto") or "auto",
            managed_preview_vercel_token=_env("FORGE_MANAGED_PREVIEW_VERCEL_TOKEN", "") or "",
            managed_preview_vercel_team_id=_env("FORGE_MANAGED_PREVIEW_VERCEL_TEAM_ID", "") or "",
            managed_preview_vercel_team_slug=_env("FORGE_MANAGED_PREVIEW_VERCEL_TEAM_SLUG", "") or "",
            credential_secret=_env("FORGE_CREDENTIAL_SECRET", "forge-dev-secret") or "forge-dev-secret",
            github_client_id=_env("GITHUB_CLIENT_ID", "") or "",
            github_client_secret=_env("GITHUB_CLIENT_SECRET", "") or "",
            vercel_client_id=_env("VERCEL_CLIENT_ID", "") or "",
            vercel_client_secret=_env("VERCEL_CLIENT_SECRET", "") or "",
            vercel_integration_slug=_env("VERCEL_INTEGRATION_SLUG", "forge") or "forge",
            figma_template_urls={
                "landing-page": _env("FORGE_FIGMA_TEMPLATE_LANDING_PAGE", "") or "",
                "portfolio": _env("FORGE_FIGMA_TEMPLATE_PORTFOLIO", "") or "",
                "weather-app": _env("FORGE_FIGMA_TEMPLATE_WEATHER_APP", "") or "",
                "ecommerce-storefront": _env("FORGE_FIGMA_TEMPLATE_ECOMMERCE", "") or "",
                "food-delivery-app": _env("FORGE_FIGMA_TEMPLATE_FOOD_DELIVERY_APP", "") or "",
                "auth-saas-dashboard": _env("FORGE_FIGMA_TEMPLATE_AUTH_SAAS_DASHBOARD", "") or "",
                "fastapi-backend": _env("FORGE_FIGMA_TEMPLATE_FASTAPI_BACKEND", "") or "",
            },
            supabase_url=_env("SUPABASE_URL", "") or "",
            supabase_key=_env("SUPABASE_KEY", "") or "",
            supabase_anon_key=_env("SUPABASE_ANON_KEY", _env("SUPABASE_KEY", "") or "") or "",
            telegram_bot_username=_env("TELEGRAM_BOT_USERNAME", "ForggeBot") or "ForggeBot",
            worker_id=_env("FORGE_WORKER_ID", f"{hostname}-{os.getpid()}") or f"{hostname}-{os.getpid()}",
            worker_poll_interval_seconds=_env_float("FORGE_WORKER_POLL_INTERVAL_SECONDS", 0.5),
            worker_batch_size=_env_int("FORGE_WORKER_BATCH_SIZE", 1),
            worker_lock_timeout_seconds=_env_int("FORGE_WORKER_LOCK_TIMEOUT_SECONDS", 300),
            worker_retry_backoff_seconds=_env_int("FORGE_WORKER_RETRY_BACKOFF_SECONDS", 30),
            worker_max_attempts=_env_int("FORGE_WORKER_MAX_ATTEMPTS", 3),
            history_window=_env_int("FORGE_HISTORY_WINDOW", 8),
            search_result_limit=_env_int("FORGE_SEARCH_RESULT_LIMIT", 4),
            fetch_timeout_seconds=_env_int("FORGE_FETCH_TIMEOUT_SECONDS", 10),
            auth_timeout_seconds=_env_int("FORGE_AUTH_TIMEOUT_SECONDS", 20),
            cors_allowed_origins=_env_list("FORGE_CORS_ALLOWED_ORIGINS"),
            orchestrator_routes=parse_model_routes(
                _env("FORGE_ORCHESTRATOR_MODELS", "") or "",
                "gemini/gemini-flash-latest,groq/llama-3.3-70b-versatile,openrouter/openrouter/auto",
            ),
            planner_routes=parse_model_routes(
                _env("FORGE_PLANNER_MODELS", "") or "",
                "gemini/gemini-pro-latest,groq/llama-3.3-70b-versatile,openrouter/openrouter/auto",
            ),
            code_routes=parse_model_routes(
                _env("FORGE_CODE_MODELS", "") or "",
                "gemini/gemini-pro-latest,nvidia/moonshotai/kimi-k2-instruct,openrouter/openrouter/auto",
            ),
            debug_routes=parse_model_routes(
                _env("FORGE_DEBUG_MODELS", "") or "",
                "gemini/gemini-flash-latest,groq/llama-3.2-11b-vision-preview,openrouter/openrouter/auto",
            ),
            reviewer_routes=parse_model_routes(
                _env("FORGE_REVIEWER_MODELS", "") or "",
                "gemini/gemini-flash-latest,openrouter/openrouter/auto,groq/llama-3.3-70b-versatile",
            ),
            research_routes=parse_model_routes(
                _env("FORGE_RESEARCH_MODELS", "") or "",
                "gemini/gemini-flash-latest,openrouter/openrouter/auto,groq/llama-3.3-70b-versatile",
            ),
            summary_routes=parse_model_routes(
                _env("FORGE_SUMMARY_MODELS", "") or "",
                "gemini/gemini-flash-latest,groq/llama-3.3-70b-versatile,openrouter/openrouter/auto",
            ),
        )
