---
name: super-base
description: Turn rough product ideas into a strong implementation base: scope, architecture, folder structure, starter data models, setup steps, and first build slices. Use when Codex needs to bootstrap a new app, MVP, internal tool, API service, dashboard, bot, or full-stack project from a short prompt, vague concept, or incomplete requirements.
---

# Super Base

## Overview

Turn an idea into a buildable starting point quickly. Favor a lean, opinionated base that can ship, while leaving clear seams for later expansion.

## Workflow

1. Extract the core product loop.
2. Choose the smallest architecture that supports it.
3. Define the first implementation slice.
4. Create only the files and structures needed to support that slice.

## Understand the Ask

Identify:

- Primary user
- Primary action they must complete
- Single source of truth for data
- Surfaces required now: API, worker, UI, auth, storage, integrations
- Constraints already implied by the repo or request

If the prompt is vague, infer the simplest credible product shape instead of blocking on missing details.

## Choose the Base

Prefer boring, reliable defaults.

Use this decision pattern:

- Single-page workflow or brochure site: static frontend first
- CRUD product with accounts and history: frontend + API + relational storage
- Async or long-running work: add background jobs only if the user flow truly needs them
- External providers: wrap them behind thin adapters
- AI features: define prompt inputs, outputs, and failure behavior before wiring providers

Avoid adding queues, event buses, microservices, plugin systems, or elaborate abstractions unless the request clearly justifies them.

## Produce the Initial Base

When implementing, prioritize these artifacts:

1. Project layout or changes to the existing layout
2. Minimal runtime entrypoints
3. Core schema or models
4. One vertical slice end to end
5. Setup notes only when needed for execution

Keep naming explicit. Keep boundaries obvious. Leave extension points where future features are likely, but do not scaffold speculative modules.

## Output Shape

For planning or explanation tasks, return:

1. A one-paragraph product interpretation
2. The recommended architecture in plain language
3. The first build slice
4. The highest-risk assumption

For implementation tasks, make the code changes directly and keep explanations short.

## Guardrails

- Preserve existing repo patterns unless they are clearly broken
- Do not invent unnecessary infrastructure
- Prefer one solid default over many optional branches
- Keep the first version easy to run locally
- Add tests around the first critical path when the repo already has test infrastructure

## Example Triggers

- "Build me a base for an AI support dashboard"
- "Set up the initial structure for a Telegram SaaS bot"
- "Create a practical MVP starting point for this idea"
- "Turn this rough spec into the first shippable app skeleton"

## Notes

If the repo already exists, act as a base-layer architect inside its constraints instead of rebuilding from scratch. If the user only wants a plan, stop at architecture and slice definition. If the user wants execution, implement the first vertical slice rather than broad empty scaffolding.
