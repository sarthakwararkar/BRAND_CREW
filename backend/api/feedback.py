from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.db.models import FeedbackRequest
from backend.services import run_service

router = APIRouter(tags=["feedback"])


@router.post("/runs/{run_id}/feedback", status_code=202)
def submit_feedback(run_id: str, body: FeedbackRequest, background: BackgroundTasks):
    run = run_service.get_run(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    outputs = run_service.list_outputs(run_id)
    if not any(o["approval"] == "approved" for o in outputs):
        raise HTTPException(400, "approve at least one output before submitting feedback")
    run_service.save_feedback(
        run_id,
        [r.model_dump() for r in body.ratings],
        [m.model_dump() for m in body.metrics],
    )
    background.add_task(run_service.execute_analysis, run_id)   # second crew -> lessons into memory
    return {"status": "analysis_started", "run_id": run_id}
