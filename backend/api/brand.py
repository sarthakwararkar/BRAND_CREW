import json

from fastapi import APIRouter, Header, HTTPException

from backend.config import settings
from backend.db.models import ReseedRequest

router = APIRouter(tags=["brand"])


def _read(rel: str) -> str:
    p = settings.brand_dir / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


@router.get("/brand")
def get_brand():
    palette = _read("visual/palette.json")
    return {
        "brand_name": settings.brand_name,
        "guidelines": _read("brand_guidelines.md"),
        "product_facts": _read("product_facts.md"),
        "banned_phrases": [l.strip() for l in _read("banned_phrases.txt").splitlines() if l.strip() and not l.startswith("#")],
        "palette": json.loads(palette) if palette else {},
        "visual_guidelines": _read("visual/visual_guidelines.md"),
    }


@router.post("/brand/reseed")
def reseed_brand(body: ReseedRequest, x_admin_token: str = Header(default="")):
    """Deliberate human action: re-load data/brand/* into the protected scopes."""
    if not settings.admin_token:
        raise HTTPException(503, "ADMIN_TOKEN is not configured")
    if x_admin_token != settings.admin_token:
        raise HTTPException(403, "invalid admin token")
    from backend.memory.seed import seed_all
    from backend.memory.setup import get_backend

    return seed_all(get_backend(), force=body.force)
