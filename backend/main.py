"""FastAPI entrypoint. Run uvicorn backend.main:app from the repository root."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError

from backend.api import approvals, brand, feedback, memory, runs
from backend.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
settings.outputs_dir.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    try:
        from backend.db.client import ensure_indexes

        ensure_indexes()
    except Exception as exc:     # API still starts so /api/health explains what is wrong
        logging.getLogger(__name__).warning("MongoDB not reachable at startup: %s", exc)
    yield


app = FastAPI(title="Brand Crew API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(PyMongoError)
async def handle_mongodb_error(_request: Request, _exc: PyMongoError) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={
            "detail": (
                "MongoDB is unavailable. Check MONGODB_URI, confirm your Atlas cluster is running, "
                "and allow your IP in Atlas Network Access."
            )
        },
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (runs.router, approvals.router, feedback.router, brand.router, memory.router):
    app.include_router(r, prefix="/api")

# Generated landing pages / blog / social files for iframe previews in the dashboard
app.mount("/outputs", StaticFiles(directory=settings.outputs_dir), name="outputs")


@app.get("/api/health")
def health():
    status = {"api": "ok"}
    try:
        from backend.db.client import get_client

        get_client().admin.command("ping")
        status["mongo"] = "ok"
    except Exception as exc:
        status["mongo"] = f"error: {exc}"
    return status
