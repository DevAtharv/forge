# Forge

Forge is a production-biased MVP for a Telegram-native AI dev team. The canonical implementation lives in the `forge/` package and is exposed through `main.py`.

## What is implemented

- FastAPI webhook endpoint that verifies a Telegram secret and enqueues work without doing model calls inline.
- Durable job processing model with a background worker loop, retry handling, and dead-letter behavior.
- Stage-based orchestration with structured outputs for `planner`, `research`, `code`, `debug`, and `reviewer`.
- Provider abstraction layer for LLM, search, and fetch adapters with env-driven fallback chains.
- Hybrid project builder with reusable app scaffolds, GitHub-backed project persistence, and per-user Vercel deploy flow.
- Hybrid memory with recent history, durable profile context, and async profile refresh.
- Telegram-safe delivery with progress updates, chunking, and document attachment for larger code outputs.

## Project layout

- `main.py`: app entrypoint for `uvicorn`.
- `forge/bootstrap.py`: dependency wiring for the app, providers, transport, and worker.
- `forge/api/`: HTTP routes, including `/webhook` and `/health`.
- `forge/workers/`: queue processing and staged pipeline execution.
- `forge/agents/`: orchestrator, task agents, and final response aggregation.
- `forge/providers/`: provider interfaces plus Groq, OpenAI-compatible, search, and fetch adapters.
- `forge/integrations.py`: GitHub/Vercel OAuth and user-owned repo/deploy clients.
- `forge/builder.py`: hybrid builder and archetype scaffolds for app generation.
- `forge/missions.py`: background mission orchestration for build/deploy/status flows.
- `forge/memory/`: Supabase-backed and in-memory storage implementations.
- `forge/schemas/`: shared Pydantic models for jobs, plans, profiles, and agent outputs.
- `frontend/`: Vercel-ready static frontend for split deployment.
- `sql/schema.sql`: Supabase/Postgres schema and RPC helpers for queue claim/complete/fail flows.
- `tests/`: unit and integration coverage for the local execution path.

## Setup

1. Install dependencies:

```powershell
pip install -r requirements.txt
```

2. Create a `.env` from `.env.example` and fill in:

- `TELEGRAM_TOKEN`
- `WEBHOOK_SECRET`
- `GROQ_API_KEY`
- `NVIDIA_API_KEY`
- `OPENROUTER_API_KEY`
- `TAVILY_API_KEY` (optional, for keyed live web search)
- `FORGE_PUBLIC_BASE_URL`
- `FORGE_FRONTEND_BASE_URL`
- `FORGE_CREDENTIAL_SECRET`
- `GITHUB_CLIENT_ID`
- `GITHUB_CLIENT_SECRET`
- `VERCEL_CLIENT_ID`
- `VERCEL_CLIENT_SECRET`
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_ANON_KEY`

Optional live web search:

- Set `TAVILY_API_KEY` to enable API-backed web search for the research agent.
- `FORGE_SEARCH_PROVIDER=auto` uses Tavily when a key is present and falls back to DuckDuckGo otherwise.
- Set `FORGE_SEARCH_PROVIDER=tavily` to force Tavily, or `FORGE_SEARCH_PROVIDER=duckduckgo` to force the legacy provider.

3. Apply `sql/schema.sql` to your Supabase database.

4. Start the app locally:

```powershell
uvicorn main:app --reload
```

Python version:

- The repo pins Python `3.11.11` via [.python-version](C:/Users/athar/Desktop/Forge/.python-version).
- Render should also be set to `PYTHON_VERSION=3.11.11` to avoid `pydantic-core` source builds on newer runtimes.

## Telegram flow

1. Telegram sends an update to `/webhook`.
2. The webhook verifies the secret and enqueues a deduplicated `message_job`.
3. The worker loop claims the job and builds an orchestration plan.
4. Telegram commands and natural-language build prompts can be promoted into durable missions.
5. The worker claims both message jobs and missions, then runs builder/orchestrator flows in the background.
6. The transport sends status updates and final replies back to Telegram.

## Web UI and auth

- `/` serves the Forge control-room UI.
- `/ui/app.js` serves the browser workspace client for the control-room UI.
- `/api/client-config` tells the browser whether Supabase auth is configured.
- `/api/auth/signup`, `/api/auth/signin`, `/api/auth/session`, and `/api/auth/signout` proxy Supabase auth flows through the backend.
- `/api/app/dashboard` returns the authenticated workspace user, profile memory, and recent conversation.
- `/api/integrations/github/start` and `/api/integrations/vercel/start` begin per-user OAuth flows.
- `/api/app/projects`, `/api/app/missions`, and `/api/app/deploy` expose project/misson/deploy state for the authenticated workspace.
- `/api/app/plan` previews a protected orchestration plan for the authenticated workspace.
- `/api/app/run` enqueues a protected background mission and returns a mission id for polling.
- `/demo/plan` remains a public preview route for unauthenticated visitors.

## Notes

- The `forge/` package is the source of truth for the current implementation.
- There are older top-level stub folders in the repo (`api/`, `memory/`, `providers/`, `workers/`) that are not part of the main runtime path.
- The local test suite is designed to run with the in-memory store and fake transport/providers; real provider smoke tests still need actual credentials.

## Split Deployment

Backend on Render:

- Use `render.yaml`.
- Set `FORGE_CORS_ALLOWED_ORIGINS` to your Vercel frontend origin, for example `https://forge-ui.vercel.app`.
- Set all backend secrets in Render, including `SUPABASE_ANON_KEY`.

Frontend on Vercel:

- Deploy the `frontend/` directory as a separate project.
- Update [config.js](C:/Users/athar/Desktop/Forge/frontend/config.js) to your Render backend URL before deploying, for example `https://forge-bot.onrender.com`.
- The Vercel frontend calls the Render backend directly using that configured base URL.

Operational helpers:

- `python scripts/check_readiness.py`
- `python scripts/set_telegram_webhook.py --base-url https://your-render-backend.onrender.com`

## Vercel Sandbox

Install the Python SDK with:

```powershell
pip install -r requirements.txt
```

Example script:

```powershell
python scripts/vercel_sandbox_example.py
```

Notes:

- The repo now tracks `vercel==0.5.2` in [requirements.txt](C:/Users/athar/Desktop/Forge/requirements.txt).
- The example script lives at [vercel_sandbox_example.py](C:/Users/athar/Desktop/Forge/scripts/vercel_sandbox_example.py).
- On this Windows machine, importing `vercel.sandbox` currently fails because the installed SDK imports the Unix-only `termios` module. Run the example from Linux, macOS, or WSL until Vercel ships a Windows-compatible release.
