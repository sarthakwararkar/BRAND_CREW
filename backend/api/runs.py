from fastapi import APIRouter, BackgroundTasks, HTTPException

from backend.db.models import StartRunRequest
from backend.services import run_service

router = APIRouter(tags=["runs"])


@router.post("/runs", status_code=202)
def start_run(body: StartRunRequest, background: BackgroundTasks):
    run = run_service.create_run(body.theme_override)
    background.add_task(run_service.execute_weekly_run, run["id"])
    return run


@router.get("/runs")
def list_runs():
    return run_service.list_runs()


@router.get("/runs/{run_id}")
def get_run(run_id: str):
    run = run_service.get_run(run_id)
    if run is None:
        raise HTTPException(404, "run not found")
    return {"run": run, "outputs": run_service.list_outputs(run_id)}
