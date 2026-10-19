"""The weekly content crew: strategist -> SEO -> copy -> visual check -> brand edit -> landing page.

Memory is handled explicitly (recall before the run, targeted writes after it) instead of
`Crew(memory=True)`: that keeps scopes clean, stops raw drafts from polluting long-term memory,
and makes "did it recall last week's lesson?" testable.
"""
from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, Callable

from crewai import Crew, Process

from backend.config import settings
from backend.crew.agents import build_agents
from backend.crew.schemas import (
    ContentDraft, EditedContent, EditorReport, SEOBrief, VisualReport, WeeklyPlan, coerce_output,
)
from backend.crew.tasks import build_tasks
from backend.memory import scopes as S
from backend.memory.seed import collect_company_chunks, collect_visual_chunks
from backend.memory.setup import AgentMemory, get_agent_memory, get_backend
from backend.tools.page_export import extract_html, render_fallback_landing, validate_landing_html

log = logging.getLogger(__name__)

TASK_ORDER = ["plan_week", "research_keywords", "draft_content", "check_visuals", "edit_for_brand", "build_landing_page"]
AGENT_ORDER = ["strategist", "seo_researcher", "copywriter", "visual_brand", "brand_editor", "landing_builder"]
STEP_LABELS = {
    "plan_week": "Strategist: weekly plan ready",
    "research_keywords": "SEO Researcher: keyword brief ready",
    "draft_content": "Copywriter: drafts ready",
    "check_visuals": "Visual Brand Reviewer: visual check done",
    "edit_for_brand": "Brand Editor: edits + report ready",
    "build_landing_page": "Landing Page Builder: page built",
}
EDITOR_SEEN = settings.memory_store_path / "editor_seen.json"


@dataclass
class WeeklyResult:
    plan: WeeklyPlan
    seo_brief: SEOBrief | None
    edited: EditedContent
    visual: VisualReport | None
    landing_html: str
    usage: dict[str, Any] | None
    lessons_recalled: int


# ------------------------------------------------------------------ context gathering
def _brand_files_text() -> str:
    return "\n\n".join(collect_company_chunks())


def _visual_files_text() -> str:
    return "\n\n".join(collect_visual_chunks())


def gather_contexts(mems: dict[str, AgentMemory]) -> tuple[dict[str, dict[str, str]], int]:
    """Each agent recalls only through its own slice. Returns (per-task variables, #lessons recalled)."""
    strat, seo, copy = mems["strategist"], mems["seo_researcher"], mems["copywriter"]
    vis, edit, build = mems["visual_brand"], mems["brand_editor"], mems["landing_builder"]

    lesson_items = strat.recall("past campaign angles that worked or flopped", limit=8,
                                scopes=[S.MARKETING_CAMPAIGNS], recency=True)
    lesson_context = AgentMemory.format_items(lesson_items) if lesson_items else "(nothing stored yet - first run)"

    per_task = {
        "plan_week": {
            "brand_context": strat.context_block("target audience positioning brand goals", limit=4,
                                                  scopes=[S.COMPANY_KNOWLEDGE], fallback=_brand_files_text),
            "lesson_context": lesson_context,
            "seo_context": strat.context_block("keywords targeted and content gaps", limit=6, scopes=[S.MARKETING_SEO]),
        },
        "research_keywords": {
            "brand_context": seo.context_block("audience product features topics", limit=5,
                                               scopes=[S.COMPANY_KNOWLEDGE], fallback=_brand_files_text),
            "seo_context": seo.context_block("keywords already targeted", limit=8, scopes=[S.MARKETING_SEO]),
        },
        "draft_content": {
            "brand_context": copy.context_block("brand voice tone rules do and dont terminology channel formatting", limit=8,
                                                scopes=[S.COMPANY_KNOWLEDGE], fallback=_brand_files_text),
            "lesson_context": copy.context_block("what worked or flopped before", limit=6,
                                                 scopes=[S.MARKETING_CAMPAIGNS], recency=True),
        },
        "check_visuals": {
            "visual_context": vis.context_block("palette fonts logo imagery layout rules", limit=8,
                                                scopes=[S.VISUAL_BRAND], fallback=_visual_files_text),
        },
        "edit_for_brand": {
            "brand_context": edit.context_block("brand voice rules banned phrases terminology formatting", limit=10,
                                                scopes=[S.COMPANY_KNOWLEDGE], fallback=_brand_files_text),
            "editor_notes": edit.context_block("recurring corrections", limit=8, scopes=[S.EDITOR_PRIVATE]),
        },
        "build_landing_page": {
            "visual_context": build.context_block("palette fonts layout rules", limit=6,
                                                  scopes=[S.VISUAL_BRAND], fallback=_visual_files_text),
            "brand_context": build.context_block("brand name tone call to action", limit=3,
                                                 scopes=[S.COMPANY_KNOWLEDGE], fallback=_brand_files_text),
        },
    }
    return per_task, len(lesson_items)


# ------------------------------------------------------------------ memory side effects
def _seen() -> set[str]:
    if EDITOR_SEEN.exists():
        try:
            return set(json.loads(EDITOR_SEEN.read_text()))
        except json.JSONDecodeError:
            return set()
    return set()


def _mark_seen(seen: set[str]) -> None:
    EDITOR_SEEN.parent.mkdir(parents=True, exist_ok=True)
    EDITOR_SEEN.write_text(json.dumps(sorted(seen)))


def write_memory_side_effects(mems: dict[str, AgentMemory], week_id: str, seo: SEOBrief | None, report: EditorReport) -> None:
    """Store only distilled facts: keyword research and de-duplicated recurring editor corrections."""
    today = date.today().isoformat()
    if seo is not None:
        try:
            mems["seo_researcher"].remember(
                f"date: {today}\nweek_id: {week_id}\nprimary_keyword: {seo.primary_keyword}\n"
                f"secondary_keywords: {'; '.join(seo.secondary_keywords)}\nsearch_intent: {seo.search_intent}\n"
                f"content_gaps: {'; '.join(seo.content_gaps)}"
            )
        except Exception as exc:
            log.warning("could not store SEO research: %s", exc)

    candidates = [f"Recurring correction: {p}" for p in report.recurring_patterns]
    candidates += [f"Correction (high) {v.rule}: {v.original} -> {v.fix}" for v in report.violations if v.severity == "high"]
    seen = _seen()
    for text in candidates:
        key = hashlib.sha1(" ".join(text.lower().split()).encode()).hexdigest()
        if key in seen:
            continue
        try:
            mems["brand_editor"].remember(f"date: {today}\n{text}")
            seen.add(key)
        except Exception as exc:
            log.warning("could not store editor correction: %s", exc)
    _mark_seen(seen)


# ------------------------------------------------------------------ helpers
def _usage_dict(crew: Any) -> dict[str, Any] | None:
    um = getattr(crew, "usage_metrics", None)
    if um is None:
        return None
    data = um.model_dump() if hasattr(um, "model_dump") else dict(um)
    total = data.get("total_tokens") or 0
    if settings.cost_per_million_tokens_usd and total:
        data["estimated_cost_usd"] = round(total / 1_000_000 * settings.cost_per_million_tokens_usd, 4)
    log.info("run usage: %s", data)
    return data


# ------------------------------------------------------------------ main entrypoint
def run_weekly_crew(
    run_id: str,
    week_id: str,
    theme_override: str | None = None,
    progress_cb: Callable[[str], None] | None = None,
    backend: Any | None = None,
) -> WeeklyResult:
    say = progress_cb or (lambda m: None)
    backend = backend if backend is not None else get_backend()
    mems = {name: get_agent_memory(name, backend) for name in AGENT_ORDER}

    say("Recalling memory (past lessons, brand knowledge)")
    per_task, lessons_recalled = gather_contexts(mems)

    agents = build_agents(AGENT_ORDER)
    tasks = build_tasks(
        agents, TASK_ORDER,
        common={"week_id": week_id, "theme_override": theme_override or "(none)"},
        per_task=per_task,
    )

    done = {"n": 0}

    def on_task_done(_output: Any) -> None:
        if done["n"] < len(TASK_ORDER):
            say(STEP_LABELS[TASK_ORDER[done["n"]]])
        done["n"] += 1

    crew = Crew(
        agents=[agents[k] for k in AGENT_ORDER],
        tasks=tasks,
        process=Process.sequential,
        memory=False,                 # explicit memory handling, see module docstring
        verbose=True,
        task_callback=on_task_done,
    )
    say(f"Crew started for {week_id}")
    crew_output = crew.kickoff()
    outs = dict(zip(TASK_ORDER, crew_output.tasks_output))

    plan = coerce_output(outs["plan_week"], WeeklyPlan)
    if plan is None:
        raise RuntimeError("Strategist did not return a valid WeeklyPlan")
    seo = coerce_output(outs["research_keywords"], SEOBrief)
    visual = coerce_output(outs["check_visuals"], VisualReport)

    edited = coerce_output(outs["edit_for_brand"], EditedContent)
    if edited is None:
        draft = coerce_output(outs["draft_content"], ContentDraft)
        if draft is None:
            raise RuntimeError("Neither the Brand Editor nor the Copywriter returned valid content")
        say("Warning: editor output unreadable, using the unedited draft")
        edited = EditedContent(
            content=draft,
            report=EditorReport(brand_score=50, summary="Editor output could not be parsed; draft is UNREVIEWED."),
        )

    html = extract_html(getattr(outs["build_landing_page"], "raw", "") or "")
    if not html or any("external" in i for i in validate_landing_html(html)):
        say("Landing builder output unusable, generated fallback page from the copy")
        html = render_fallback_landing(edited.content.landing.model_dump())

    write_memory_side_effects(mems, week_id, seo, edited.report)

    return WeeklyResult(
        plan=plan, seo_brief=seo, edited=edited, visual=visual,
        landing_html=html, usage=_usage_dict(crew), lessons_recalled=lessons_recalled,
    )
