"""Writes generated artifacts to data/outputs/<run_id>/ and builds a safe fallback landing page."""
from __future__ import annotations

import html as html_lib
import json
import re
from pathlib import Path
from typing import Any

from backend.config import settings
from backend.tools.image_tool import load_palette


def extract_html(raw: str) -> str:
    """Pull a full HTML document out of an LLM answer (strips code fences / chatter)."""
    if not raw:
        return ""
    fence = re.search(r"```(?:html)?\s*(<!DOCTYPE.*?</html>|<html.*?</html>)\s*```", raw, flags=re.S | re.I)
    if fence:
        return fence.group(1).strip()
    doc = re.search(r"(<!DOCTYPE html.*</html>|<html.*</html>)", raw, flags=re.S | re.I)
    return doc.group(1).strip() if doc else ""


def validate_landing_html(html: str) -> list[str]:
    issues: list[str] = []
    if "<title" not in html.lower():
        issues.append("missing <title>")
    if re.search(r"<script[^>]+src=", html, flags=re.I):
        issues.append("external <script src> found (page must be self-contained)")
    if re.search(r"""<link[^>]+href=["']https?://""", html, flags=re.I):
        issues.append("external stylesheet found")
    return issues


def render_fallback_landing(copy: dict[str, Any]) -> str:
    """Plain, brand-colored page built directly from the edited copy (used if the builder agent fails)."""
    colors = load_palette().get("colors", {})
    primary = colors.get("primary", "#4F46E5")
    bg = colors.get("background", "#F8FAFC")
    text = colors.get("text", "#0F172A")
    esc = html_lib.escape
    sections = "".join(
        f"<section><h2>{esc(s.get('heading', ''))}</h2><p>{esc(s.get('body', ''))}</p></section>"
        for s in copy.get("sections", [])
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(copy.get('headline', settings.brand_name))}</title>
<meta name="description" content="{esc(copy.get('meta_description', ''))}">
<style>
body{{margin:0;font-family:system-ui,sans-serif;background:{bg};color:{text};line-height:1.6}}
header{{padding:72px 24px;text-align:center;background:{primary};color:#fff}}
h1{{margin:0 0 12px;font-size:2.4rem}} main{{max-width:760px;margin:0 auto;padding:32px 24px}}
section{{margin:32px 0}} .cta{{display:inline-block;margin-top:16px;padding:12px 28px;border-radius:8px;background:#fff;color:{primary};font-weight:600;text-decoration:none}}
</style></head><body>
<header><h1>{esc(copy.get('headline', ''))}</h1><p>{esc(copy.get('subheadline', ''))}</p><a class="cta" href="#">{esc(copy.get('cta_text', 'Get started'))}</a></header>
<main>{sections}</main></body></html>"""


def _report_markdown(report: dict[str, Any]) -> str:
    lines = [f"# Editor Report", "", f"**Brand score:** {report.get('brand_score', '?')}/100", "", report.get("summary", ""), ""]
    for v in report.get("violations", []):
        lines.append(f"- **[{v.get('severity', '').upper()}] {v.get('rule', '')}** - {v.get('original', '')} -> {v.get('fix', '')}")
    return "\n".join(lines)


def save_run_outputs(run_id: str, content: dict[str, Any], report: dict[str, Any], landing_html: str) -> dict[str, str]:
    """Writes files and returns URL paths (served by FastAPI under /outputs)."""
    base = settings.outputs_dir / run_id
    (base / "landing").mkdir(parents=True, exist_ok=True)

    (base / "landing" / "index.html").write_text(landing_html, encoding="utf-8")
    blog_md = f"# {content.get('blog_title', '')}\n\n{content.get('blog_markdown', '')}\n"
    (base / "blog.md").write_text(blog_md, encoding="utf-8")
    social = {
        "linkedin": content.get("linkedin_post", ""),
        "x": content.get("x_post", ""),
        "instagram": content.get("instagram_caption", ""),
        "hashtags": content.get("hashtags", []),
    }
    (base / "social.json").write_text(json.dumps(social, indent=2, ensure_ascii=False), encoding="utf-8")
    (base / "editor_report.md").write_text(_report_markdown(report), encoding="utf-8")

    return {
        "landing": f"/outputs/{run_id}/landing/index.html",
        "blog": f"/outputs/{run_id}/blog.md",
        "social": f"/outputs/{run_id}/social.json",
        "editor_report": f"/outputs/{run_id}/editor_report.md",
    }
