"""The performance crew: ratings + metrics -> distilled, dated lessons stored in /marketing/campaigns."""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any, Callable

from crewai import Crew, Process

from backend.crew.agents import build_agents
from backend.crew.schemas import Lessons, coerce_output
from backend.crew.tasks import build_tasks
from backend.memory import scopes as S
from backend.memory.lessons import Lesson, store_lesson
from backend.memory.seed import collect_company_chunks
from backend.memory.setup import get_agent_memory, get_backend

log = logging.getLogger(__name__)


def run_analysis_crew(
    run_id: str,
    week_id: str,
    payload: dict[str, Any],
    progress_cb: Callable[[str], None] | None = None,
    backend: Any | None = None,
) -> list[Lesson]:
    say = progress_cb or (lambda m: None)
    if not payload.get("outputs"):
        say("No approved outputs to analyze")
        return []

    backend = backend if backend is not None else get_backend()
    mem = get_agent_memory("performance_analyst", backend)

    lesson_context = mem.context_block("what worked or flopped past campaign lessons", limit=8,
                                       scopes=[S.MARKETING_CAMPAIGNS], recency=True)
    brand_context = mem.context_block("brand goals audience positioning", limit=3, scopes=[S.COMPANY_KNOWLEDGE],
                                      fallback=lambda: "\n\n".join(collect_company_chunks()[:3]))

    agents = build_agents(["performance_analyst"])
    tasks = build_tasks(
        agents, ["analyze_performance"],
        common={"week_id": week_id},
        per_task={"analyze_performance": {
            "payload_json": json.dumps(payload, indent=2, default=str),
            "lesson_context": lesson_context,
            "brand_context": brand_context,
        }},
    )
    crew = Crew(agents=list(agents.values()), tasks=tasks, process=Process.sequential, memory=False, verbose=True)
    say("Performance Analyst started")
    result = crew.kickoff()

    parsed = coerce_output(result.tasks_output[0], Lessons)
    if parsed is None:
        raise RuntimeError("Performance Analyst did not return valid lessons")

    today = date.today().isoformat()
    stored: list[Lesson] = []
    for draft in parsed.lessons:
        lesson = Lesson(date=today, week_id=week_id, **draft.model_dump())
        store_lesson(mem, lesson)       # analyst is the only agent with write access to campaigns
        stored.append(lesson)
    say(f"Stored {len(stored)} lessons in {S.MARKETING_CAMPAIGNS}")
    return stored
