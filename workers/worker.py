import time
import asyncio
import os
import socket
from memory import store as memory_store
from database import repo as job_repo
from providers.llm import run_llm
from providers.reviewer import review_text
from providers.search import search_sources


async def process_job(job: dict) -> dict:
    # Simple, staged orchestration mockup
    stages = [
        {
            "name": "plan",
            "agents": ["planner"],
            "tasks": {"planner": "generate_plan"},
        },
        {
            "name": "implement",
            "agents": ["research", "code", "reviewer"],
            "tasks": {
                "research": "retrieve_sources",
                "code": "generate_code",
                "reviewer": "review",
            },
        },
    ]

    results = []
    for stage in stages:
        stage_results = {}
        for agent in stage["agents"]:
            if agent == "planner":
                res = run_llm({"prompt": f"Plan for {job['telegram_update_id']}"})
            elif agent == "research":
                res = search_sources(
                    "planning for " + str(job["telegram_update_id"]), limit=2
                )
            elif agent == "code":
                res = run_llm({"prompt": "generate_code for task"})
            elif agent == "reviewer":
                res = review_text("dummy text for review")
            else:
                res = {"summary": "unknown_agent"}
            stage_results[agent] = res
        results.append({stage["name"]: stage_results})

    final_preview = {"stages": results}
    return {
        "final_preview": final_preview,
        "summary": "Orchestration completed (scaffold)",
        "user_visible_text": "Workflow completed.",
        "artifacts": [],
        "citations": [],
        "confidence": 0.5,
    }


async def start_worker(poll_interval: float = 2.0):
    while True:
        job = job_repo.claim_next_job()
        if job is None:
            await asyncio.sleep(poll_interval)
            continue
        # Update status to running and process
        try:
            res = await process_job(job)
            job_repo.update_job_by_update_id(
                job["telegram_update_id"],
                status="completed",
                updated_at=time.time(),
                result_preview=str(res.get("final_preview")),
            )
        except Exception as e:
            job_repo.update_job_by_update_id(
                job["telegram_update_id"],
                status="failed",
                error=str(e),
                updated_at=time.time(),
            )
        # Loop to next job after short pause
        await asyncio.sleep(0.1)
