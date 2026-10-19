"""Run lifecycle: create, execute (background), persist outputs, approvals, feedback, analysis."""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from backend.config import settings
from backend.db.client import get_db
from backend.db.models import LessonRef, Metric, Output, Rating, Run, new_id, utcnow
from backend.memory import scopes as S
from backend.services.scoring import score_output
from backend.tools.page_export import save_run_outputs

log = logging.getLogger(__name__)


# ------------------------------------------------------------------ helpers
def current_week_id(d: date | None = None) -> str:
    iso = (d or date.today()).isocalendar()
    return f"{iso.year}-W{iso.week:02d}"


def _to_doc(model) -> dict[str, Any]:
    doc = model.model_dump()
    doc["_id"] = doc.pop("id")
    return doc


def _from_doc(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = doc.pop("_id")
    return doc


# ------------------------------------------------------------------ runs
def create_run(theme_override: str | None = None) -> dict[str, Any]:
    run = Run(week_id=current_week_id(), theme_override=theme_override)
    get_db().runs.insert_one(_to_doc(run))
    return _from_doc(_to_doc(run))


def get_run(run_id: str) -> dict[str, Any] | None:
    return _from_doc(get_db().runs.find_one({"_id": run_id}))


def list_runs(limit: int = 50) -> list[dict[str, Any]]:
    runs = [_from_doc(d) for d in get_db().runs.find().sort("created_at", -1).limit(limit)]
    for run in runs:
        scores = [o["brand_score"] for o in get_db().outputs.find({"run_id": run["id"]}, {"brand_score": 1})]
        run["avg_brand_score"] = round(sum(scores) / len(scores), 1) if scores else None
    return runs


def update_run(run_id: str, **fields: Any) -> None:
    get_db().runs.update_one({"_id": run_id}, {"$set": fields})


def add_progress(run_id: str, message: str) -> None:
    log.info("[%s] %s", run_id, message)
    get_db().runs.update_one({"_id": run_id}, {"$push": {"progress": message}})


def list_outputs(run_id: str) -> list[dict[str, Any]]:
    return [_from_doc(d) for d in get_db().outputs.find({"run_id": run_id}).sort("created_at", 1)]


def get_output(output_id: str) -> dict[str, Any] | None:
    return _from_doc(get_db().outputs.find_one({"_id": output_id}))


# ------------------------------------------------------------------ weekly run
def _landing_text(c: dict[str, Any]) -> str:
    landing = c["landing"]
    parts = [landing["headline"], landing["subheadline"], landing["cta_text"]]
    parts += [f"{s['heading']}. {s['body']}" for s in landing["sections"]]
    return "\n".join(parts)


def persist_weekly_result(run_id: str, result) -> list[dict[str, Any]]:
    """Save files + Output documents. Scores = editor score capped by deterministic findings."""
    content = result.edited.content.model_dump()
    report = result.edited.report.model_dump()
    paths = save_run_outputs(run_id, content, report, result.landing_html)

    editor_score = report.get("brand_score")
    angle = content.get("angle_used") or (result.plan.angles[0] if result.plan.angles else "")
    meta = {"angle": angle, "keyword": result.plan.primary_keyword, "week_id": get_run(run_id)["week_id"]}
    visual = result.visual.model_dump() if result.visual else None

    specs = [
        ("landing", _landing_text(content), None, paths["landing"], None),
        ("blog", f"{content['blog_title']}\n\n{content['blog_markdown']}", None, paths["blog"], None),
        ("social_linkedin", content["linkedin_post"], "linkedin", None, None),
        ("social_x", content["x_post"], "x", None, None),
        ("social_instagram", f"{content['instagram_caption']}\n\n" + " ".join(content.get("hashtags", [])), "instagram", None, None),
    ]
    docs: list[dict[str, Any]] = []
    for out_type, text, channel, path, _ in specs:
        score, findings = score_output(editor_score, text, channel)
        out = Output(
            run_id=run_id, type=out_type, content=text, content_path=path,
            editor_report=report, brand_score=score,
            findings=[f.to_dict() for f in findings], visual_report=visual, meta=meta,
        )
        docs.append(_to_doc(out))
    get_db().outputs.insert_many(docs)
    return [_from_doc(d) for d in docs]


def execute_weekly_run(run_id: str) -> None:
    """Background task. Any failure marks the run failed instead of crashing the server."""
    try:
        run = get_run(run_id)
        update_run(run_id, status="running")
        from backend.crew.weekly_crew import run_weekly_crew   # lazy: keeps API start-up light

        result = run_weekly_crew(
            run_id, run["week_id"], run.get("theme_override"),
            progress_cb=lambda m: add_progress(run_id, m),
        )
        persist_weekly_result(run_id, result)
        update_run(
            run_id, status="awaiting_approval", plan=result.plan.model_dump(),
            usage={**(result.usage or {}), "lessons_recalled": result.lessons_recalled},
            completed_at=utcnow(),
        )
        add_progress(run_id, "Ready for your review")
    except Exception as exc:
        log.exception("weekly run %s failed", run_id)
        update_run(run_id, status="failed", error=str(exc))


# ------------------------------------------------------------------ approvals + feedback
def apply_decisions(run_id: str, decisions: list[dict[str, str]]) -> dict[str, Any]:
    outputs = {o["id"]: o for o in list_outputs(run_id)}
    for d in decisions:
        if d["output_id"] not in outputs:
            raise KeyError(f"output {d['output_id']} does not belong to run {run_id}")
        get_db().outputs.update_one({"_id": d["output_id"]}, {"$set": {"approval": d["approval"]}})
    refreshed = list_outputs(run_id)
    if refreshed and all(o["approval"] == "approved" for o in refreshed):
        update_run(run_id, status="approved")
    return {"run": get_run(run_id), "outputs": refreshed}


def save_feedback(run_id: str, ratings: list[dict[str, Any]], metrics: list[dict[str, Any]]) -> None:
    valid = {o["id"] for o in list_outputs(run_id)}
    db = get_db()
    for r in ratings:
        if r["output_id"] in valid:
            db.ratings.insert_one(_to_doc(Rating(**r)))
    for m in metrics:
        if m["output_id"] in valid:
            db.metrics.insert_one(_to_doc(Metric(**m)))


def build_analysis_payload(run_id: str) -> dict[str, Any]:
    """Only approved outputs go to the analyst. Rejected drafts never reach memory."""
    db = get_db()
    rows = []
    for o in list_outputs(run_id):
        if o["approval"] != "approved":
            continue
        rows.append({
            "output_id": o["id"],
            "type": o["type"],
            "angle": o["meta"].get("angle"),
            "keyword": o["meta"].get("keyword"),
            "brand_score": o["brand_score"],
            "excerpt": o["content"][:600],
            "ratings": [{"thumbs": r["thumbs"], "note": r["note"]} for r in db.ratings.find({"output_id": o["id"]})],
            "metrics": [
                {k: v for k, v in m.items() if k in {"impressions", "clicks", "ctr", "engagement", "conversions"} and v is not None}
                for m in db.metrics.find({"output_id": o["id"]})
            ],
        })
    return {"outputs": rows}


def execute_analysis(run_id: str) -> None:
    try:
        run = get_run(run_id)
        update_run(run_id, status="analyzing")
        from backend.crew.analysis_crew import run_analysis_crew

        lessons = run_analysis_crew(
            run_id, run["week_id"], build_analysis_payload(run_id),
            progress_cb=lambda m: add_progress(run_id, m),
        )
        for lesson in lessons:
            get_db().lesson_refs.insert_one(_to_doc(LessonRef(
                run_id=run_id, memory_scope=S.MARKETING_CAMPAIGNS,
                summary=f"[{lesson.outcome}] {lesson.channel}: {lesson.angle}",
            )))
        update_run(run_id, status="analyzed")
    except Exception as exc:
        log.exception("analysis for run %s failed", run_id)
        update_run(run_id, status="failed", error=str(exc))
