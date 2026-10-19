"""One-time (deliberate) seeding of the protected scopes from data/brand/*.

Run:  python -m app.memory.seed [--force]
Crews never call this. It writes straight to the backend, bypassing AgentMemory on purpose.
"""
from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.memory import scopes as S

log = logging.getLogger(__name__)

MANIFEST = settings.memory_store_path / "seed_manifest.json"


def chunk_text(text: str, max_chars: int = 700) -> list[str]:
    """Split on blank lines, then merge small paragraphs up to max_chars."""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for p in paras:
        if current and len(current) + len(p) + 2 > max_chars:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}" if current else p
    if current:
        chunks.append(current)
    return chunks


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def collect_company_chunks() -> list[str]:
    brand = settings.brand_dir
    chunks: list[str] = []
    chunks += [f"[brand guidelines] {c}" for c in chunk_text(_read(brand / "brand_guidelines.md"))]
    chunks += [f"[product facts] {c}" for c in chunk_text(_read(brand / "product_facts.md"))]
    banned = [
        ln.strip() for ln in _read(brand / "banned_phrases.txt").splitlines()
        if ln.strip() and not ln.startswith("#")
    ]
    if banned:
        chunks.append("[banned phrases] Never use these words or phrases: " + "; ".join(banned))
    return chunks


def collect_visual_chunks() -> list[str]:
    vis = settings.brand_dir / "visual"
    chunks: list[str] = []
    palette_file = vis / "palette.json"
    if palette_file.exists():
        data = json.loads(palette_file.read_text(encoding="utf-8"))
        colors = ", ".join(f"{k} {v}" for k, v in data.get("colors", {}).items())
        fonts = ", ".join(f"{k}: {v}" for k, v in data.get("fonts", {}).items())
        chunks.append(f"[palette] Colors: {colors}. Fonts: {fonts}.")
        for rule in data.get("rules", []):
            chunks.append(f"[visual rule] {rule}")
    chunks += [f"[visual guidelines] {c}" for c in chunk_text(_read(vis / "visual_guidelines.md"))]
    chunks += [f"[sample posts] {c}" for c in chunk_text(_read(vis / "sample_posts" / "descriptions.md"))]
    return chunks


def _digest(chunks: list[str]) -> str:
    return hashlib.sha256("\n".join(chunks).encode("utf-8")).hexdigest()


def _load_manifest() -> dict[str, str]:
    if MANIFEST.exists():
        try:
            return json.loads(MANIFEST.read_text())
        except json.JSONDecodeError:
            return {}
    return {}


def _save_manifest(m: dict[str, str]) -> None:
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(m, indent=2))


def seed_scope(backend: Any, scope: str, chunks: list[str], force: bool = False) -> str:
    manifest = _load_manifest()
    digest = _digest(chunks)
    if not force and manifest.get(scope) == digest:
        return "unchanged"
    if force and hasattr(backend, "forget"):
        try:
            backend.forget(scope=scope)
        except Exception as exc:
            log.warning("could not clear %s before reseed (%s); old entries may remain", scope, exc)
    for chunk in chunks:
        backend.remember(chunk, scope=scope)
    manifest[scope] = digest
    _save_manifest(manifest)
    return f"seeded {len(chunks)} chunks"


def seed_all(backend: Any, force: bool = False) -> dict[str, str]:
    return {
        S.COMPANY_KNOWLEDGE: seed_scope(backend, S.COMPANY_KNOWLEDGE, collect_company_chunks(), force),
        S.VISUAL_BRAND: seed_scope(backend, S.VISUAL_BRAND, collect_visual_chunks(), force),
    }


if __name__ == "__main__":
    from backend.memory.setup import get_backend

    logging.basicConfig(level=logging.INFO)
    result = seed_all(get_backend(), force="--force" in sys.argv)
    for scope, status in result.items():
        print(f"{scope}: {status}")
