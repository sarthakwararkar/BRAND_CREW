"""Lets the Visual Brand Agent inspect brand assets (palette, logo, sample posts) with a vision model."""
from __future__ import annotations

import base64
import json
import mimetypes
from pathlib import Path
from typing import Type

from pydantic import BaseModel, Field

from backend.config import settings

VISUAL_DIR = settings.brand_dir / "visual"
VISION_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def load_palette() -> dict:
    f = VISUAL_DIR / "palette.json"
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def list_assets() -> list[str]:
    if not VISUAL_DIR.exists():
        return []
    return sorted(str(p.relative_to(VISUAL_DIR)) for p in VISUAL_DIR.rglob("*") if p.is_file())


def describe_image(rel_path: str, question: str = "") -> str:
    path = (VISUAL_DIR / rel_path).resolve()
    if VISUAL_DIR.resolve() not in path.parents or not path.exists():
        return f"Asset not found: {rel_path}"
    if path.suffix.lower() not in VISION_EXTS:
        return f"{rel_path} is not a raster image the vision model can read; treat it by name/description only."

    mime = mimetypes.guess_type(path.name)[0] or "image/png"
    b64 = base64.b64encode(path.read_bytes()).decode()
    prompt = question or (
        "Describe this brand asset for a design reviewer: dominant colors (hex if possible), typography style, "
        "layout, imagery style, and mood. Be concise and factual."
    )
    try:
        import litellm

        ollama_options = (
            {"api_base": settings.ollama_base_url}
            if settings.vision_model.startswith(("ollama/", "ollama_chat/"))
            else {}
        )
        resp = litellm.completion(
            model=settings.vision_model,
            messages=[{"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
            ]}],
            **ollama_options,
        )
        return resp.choices[0].message.content
    except Exception as exc:
        return f"Vision call failed for {rel_path}: {exc}"


def make_image_tool():
    from crewai.tools import BaseTool

    class BrandImageInput(BaseModel):
        target: str = Field(
            ...,
            description='"palette" for colors/fonts/rules, "list" to list assets, or a relative asset path '
            '(e.g. "sample_posts/post1.png") to have it described by the vision model.',
        )

    class BrandImageTool(BaseTool):
        name: str = "brand_visual_assets"
        description: str = (
            "Inspect the brand's visual assets. Use target='palette' for official colors/fonts/rules, "
            "target='list' to see available files, or an asset path to get a vision-model description of it."
        )
        args_schema: Type[BaseModel] = BrandImageInput

        def _run(self, target: str) -> str:
            if target == "palette":
                return json.dumps(load_palette(), indent=2)
            if target == "list":
                return "\n".join(list_assets()) or "No visual assets found."
            return describe_image(target)

    return BrandImageTool()
