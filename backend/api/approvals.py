from fastapi import APIRouter, HTTPException

from backend.db.models import ApproveRequest
from backend.services import run_service

router = APIRouter(tags=["approvals"])


@router.post("/runs/{run_id}/approve")
def approve(run_id: str, body: ApproveRequest):
    run = run_service.get_run(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    if run["status"] not in {"awaiting_approval", "approved", "analyzed"}:
        raise HTTPException(409, f"run is '{run['status']}', cannot approve yet")
    try:
        return run_service.apply_decisions(run_id, [d.model_dump() for d in body.decisions])
    except KeyError as exc:
        raise HTTPException(400, str(exc))
