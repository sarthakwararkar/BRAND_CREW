"""Deterministic brand rules. The LLM editor can miss things; this cannot."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Type

from pydantic import BaseModel, Field

from backend.config import settings

ALLOWED_CAPS = {"AI", "SEO", "CTA", "FAQ", "API", "UI", "UX", "PDF", "GST", "UPI", "IIIT", "JEE", "GATE"}
EMOJI_RE = re.compile("[\U0001F300-\U0001FAFF\u2600-\u27BF]")
MAX_EXCLAMATIONS = 2
MAX_SHOUTING_WORDS = 2
MAX_EMOJI = 3
X_MAX_CHARS = 280


@dataclass
class Finding:
    rule: str
    severity: str          # low | medium | high
    detail: str
    excerpt: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@lru_cache(maxsize=1)
def load_banned_phrases() -> list[str]:
    path = settings.brand_dir / "banned_phrases.txt"
    if not path.exists():
        return []
    return [
        ln.strip().lower()
        for ln in path.read_text(encoding="utf-8").splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]


def check_text(text: str, channel: str | None = None) -> list[Finding]:
    findings: list[Finding] = []
    lowered = text.lower()

    for phrase in load_banned_phrases():
        if phrase in lowered:
            idx = lowered.index(phrase)
            findings.append(Finding("banned_phrase", "high", f'Uses banned phrase "{phrase}"', text[max(0, idx - 20): idx + len(phrase) + 20]))

    if text.count("!") > MAX_EXCLAMATIONS:
        findings.append(Finding("exclamation_overuse", "medium", f"{text.count('!')} exclamation marks (max {MAX_EXCLAMATIONS})"))

    shouting = [w for w in re.findall(r"\b[A-Z]{4,}\b", text) if w not in ALLOWED_CAPS]
    if len(shouting) > MAX_SHOUTING_WORDS:
        findings.append(Finding("all_caps", "low", "Too many ALL-CAPS words", ", ".join(shouting[:5])))

    name = settings.brand_name
    for token in re.findall(rf"\b{re.escape(name)}\b", text, flags=re.IGNORECASE):
        if token != name:
            findings.append(Finding("brand_name_casing", "medium", f'Brand name must be written "{name}"', token))
            break

    if len(EMOJI_RE.findall(text)) > MAX_EMOJI:
        findings.append(Finding("emoji_overuse", "low", f"More than {MAX_EMOJI} emoji"))

    if channel == "x" and len(text) > X_MAX_CHARS:
        findings.append(Finding("x_length", "medium", f"Post is {len(text)} chars (max {X_MAX_CHARS})"))

    return findings


def format_findings(findings: list[Finding]) -> str:
    if not findings:
        return "PASS: no deterministic brand-rule violations found."
    lines = [f"- [{f.severity.upper()}] {f.rule}: {f.detail}" + (f' (…{f.excerpt}…)' if f.excerpt else "") for f in findings]
    return "VIOLATIONS FOUND:\n" + "\n".join(lines)


# ---------- CrewAI tool wrapper (imported lazily so the checker is usable without crewai) ----------
def make_brand_checker_tool():
    from crewai.tools import BaseTool

    class BrandCheckerInput(BaseModel):
        text: str = Field(..., description="The full text to check against hard brand rules.")

    class BrandCheckerTool(BaseTool):
        name: str = "brand_rule_checker"
        description: str = (
            "Checks text against hard brand rules (banned phrases, exclamation marks, ALL-CAPS, "
            "brand-name casing, emoji count). Run it on your corrected text before finalising; "
            "fix every HIGH and MEDIUM finding."
        )
        args_schema: Type[BaseModel] = BrandCheckerInput

        def _run(self, text: str) -> str:
            return format_findings(check_text(text))

    return BrandCheckerTool()
