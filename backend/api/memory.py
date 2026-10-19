"""Read-only memory inspector (debug / MemoryExplorer page)."""
from fastapi import APIRouter, HTTPException, Query

from backend.memory import scopes as S
from backend.memory.setup import _extract_score, _extract_text, get_backend

router = APIRouter(tags=["memory"])


@router.get("/memory/{scope_path:path}")
def inspect_scope(scope_path: str, q: str = Query("overview", description="semantic query"), limit: int = 20):
    scope = "/" + scope_path.strip("/")
    if scope not in S.ALL_SCOPES:
        raise HTTPException(404, f"unknown scope; choose one of {S.ALL_SCOPES}")
    backend = get_backend()
    records = None
    if hasattr(backend, "list_records"):
        try:
            records = backend.list_records(scope=scope, limit=limit)
        except Exception:
            records = None
    if records is None:
        try:
            records = backend.recall(q, scope=scope, limit=limit, depth="shallow")
        except TypeError:
            records = backend.recall(q, scope=scope, limit=limit)
    return {
        "scope": scope,
        "entries": [{"text": _extract_text(r), "score": _extract_score(r)} for r in records or []],
    }
