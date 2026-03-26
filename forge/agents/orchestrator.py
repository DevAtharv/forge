from __future__ import annotations

import json

from forge.agents.base import extract_json_object
from forge.config import Settings
from forge.prompts import ORCHESTRATOR_SYSTEM
from forge.providers import ProviderRegistry
from forge.schemas import OrchestrationPlan, StagePlan, UserProfile


class OrchestratorAgent:
    def __init__(self, *, settings: Settings, providers: ProviderRegistry) -> None:
        self.settings = settings
        self.providers = providers

    async def plan(
        self,
        message: str,
        *,
        history: list,
        profile: UserProfile,
        has_image: bool,
    ) -> OrchestrationPlan:
        prompt = {
            "message": message,
            "has_image": has_image,
            "profile": profile.model_dump(mode="json"),
            "recent_history": [
                {"role": item.role, "content": item.content}
                for item in history[-5:]
            ],
        }
        messages = [
            {"role": "system", "content": ORCHESTRATOR_SYSTEM},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=True)},
        ]
        try:
            raw = await self.providers.generate(
                self.settings.orchestrator_routes,
                messages=messages,
                temperature=0.1,
                max_tokens=900,
                json_mode=True,
            )
            data = extract_json_object(raw)
            plan = OrchestrationPlan.model_validate(data)
            plan = self._normalize_plan(plan, message=message, has_image=has_image)
            self._validate_plan(plan)
            return plan
        except Exception:
            return self._heuristic_plan(message, has_image=has_image)

    def _validate_plan(self, plan: OrchestrationPlan) -> None:
        allowed = {"planner", "research", "code", "debug", "reviewer"}
        seen_code = False
        seen_reviewer_after_code = False
        for stage in plan.stages:
            if not set(stage.agents).issubset(allowed):
                raise ValueError("Invalid agent name in plan.")
            for agent in stage.agents:
                if agent == "code":
                    seen_code = True
                if agent == "reviewer" and seen_code:
                    seen_reviewer_after_code = True
        if seen_code and not seen_reviewer_after_code:
            raise ValueError("Reviewer must run after code.")

    def _normalize_plan(self, plan: OrchestrationPlan, *, message: str, has_image: bool) -> OrchestrationPlan:
        lower = message.lower().strip()
        wants_explanation = any(
            lower.startswith(prefix)
            for prefix in ("what is", "explain", "compare", "should i use", "why ")
        )
        code_signals = any(
            token in lower
            for token in ("build", "create", "implement", "write", "generate", "add ", "make ")
        )
        debug_signals = has_image or any(
            token in lower
            for token in ("error", "exception", "traceback", "crash", "500", "404", "bug", "failing")
        )
        website_signals = any(
            token in lower
            for token in ("website", "web site", "landing page", "portfolio", "frontend", "sweet shop", "ecommerce")
        )

        if not debug_signals:
            normalized_stages: list[StagePlan] = []
            for stage in plan.stages:
                filtered_agents = [agent for agent in stage.agents if agent != "debug"]
                if not filtered_agents:
                    continue
                filtered_tasks = {agent: task for agent, task in stage.tasks.items() if agent in filtered_agents}
                normalized_stages.append(
                    StagePlan(
                        name=stage.name,
                        agents=filtered_agents,
                        tasks=filtered_tasks,
                    )
                )
            if normalized_stages:
                plan = OrchestrationPlan(
                    intent=plan.intent,
                    response_format=plan.response_format,
                    context_policy=plan.context_policy,
                    stages=normalized_stages,
                )

        # Keep pure explanation prompts on the lightweight research path even if the LLM planner
        # tries to opportunistically add code or review stages.
        if plan.response_format == "explanation" and wants_explanation and not code_signals and not debug_signals:
            research_stages = [stage for stage in plan.stages if "research" in stage.agents]
            if research_stages:
                return OrchestrationPlan(
                    intent=plan.intent,
                    response_format="explanation",
                    context_policy=plan.context_policy,
                    stages=[
                        StagePlan(
                            name=stage.name,
                            agents=["research"],
                            tasks={"research": stage.tasks.get("research", message)},
                        )
                        for stage in research_stages
                    ],
                )
            return OrchestrationPlan(
                intent=plan.intent,
                response_format="explanation",
                context_policy=plan.context_policy,
                stages=[StagePlan(name="research", agents=["research"], tasks={"research": message})],
            )

        if code_signals and website_signals:
            has_planner = any("planner" in stage.agents for stage in plan.stages)
            has_code = any("code" in stage.agents for stage in plan.stages)
            has_reviewer = any("reviewer" in stage.agents for stage in plan.stages)
            if not (has_planner and has_code and has_reviewer):
                return OrchestrationPlan(
                    intent=plan.intent or "Plan and build a production website implementation",
                    response_format="code",
                    context_policy="recent_plus_profile_plus_summary",
                    stages=[
                        StagePlan(name="plan", agents=["planner"], tasks={"planner": message}),
                        StagePlan(name="implement", agents=["code"], tasks={"code": message}),
                        StagePlan(name="review", agents=["reviewer"], tasks={"reviewer": message}),
                    ],
                )

        return plan

    def _heuristic_plan(self, message: str, *, has_image: bool) -> OrchestrationPlan:
        lower = message.lower().strip()
        wants_explanation = any(
            lower.startswith(prefix)
            for prefix in ("what is", "explain", "compare", "should i use", "why ")
        )
        debug_signals = has_image or any(
            token in lower
            for token in ("error", "exception", "traceback", "crash", "500", "404", "bug", "failing")
        )
        code_signals = any(
            token in lower
            for token in ("build", "create", "implement", "write", "generate", "add ", "make ")
        )
        complex_signals = any(
            token in lower
            for token in ("full ", "complete ", "crud", "architecture", "system", "auth", "api", "postgres")
        )
        website_signals = any(
            token in lower
            for token in ("website", "web site", "landing page", "portfolio", "frontend", "sweet shop", "ecommerce")
        )

        if debug_signals and not code_signals and not wants_explanation:
            return OrchestrationPlan(
                intent="Debug the reported issue",
                response_format="mixed",
                context_policy="recent_plus_profile",
                stages=[StagePlan(name="debug", agents=["debug"], tasks={"debug": message or "Debug this issue"})],
            )

        if wants_explanation and not code_signals:
            return OrchestrationPlan(
                intent="Research and explain the requested topic",
                response_format="explanation",
                context_policy="recent",
                stages=[StagePlan(name="research", agents=["research"], tasks={"research": message})],
            )

        if code_signals and (complex_signals or website_signals):
            return OrchestrationPlan(
                intent="Plan, implement, and review the requested build",
                response_format="code",
                context_policy="recent_plus_profile_plus_summary",
                stages=[
                    StagePlan(name="plan", agents=["planner"], tasks={"planner": message}),
                    StagePlan(name="implement", agents=["code"], tasks={"code": message}),
                    StagePlan(name="review", agents=["reviewer"], tasks={"reviewer": message}),
                ],
            )

        if code_signals:
            return OrchestrationPlan(
                intent="Implement and review the requested change",
                response_format="code",
                context_policy="recent_plus_profile",
                stages=[
                    StagePlan(name="implement", agents=["code"], tasks={"code": message}),
                    StagePlan(name="review", agents=["reviewer"], tasks={"reviewer": message}),
                ],
            )

        return OrchestrationPlan(
            intent="Research the user's request",
            response_format="mixed",
            context_policy="recent",
            stages=[StagePlan(name="research", agents=["research"], tasks={"research": message})],
        )
