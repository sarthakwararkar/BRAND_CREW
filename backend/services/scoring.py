"""Brand-consistency score = the editor's LLM score, capped by deterministic penalties."""
from __future__ import annotations

from backend.tools.brand_checker import Finding, check_text

PENALTY = {"high": 15, "medium": 7, "low": 3}


def compute_brand_score(editor_score: int | None, findings: list[Finding]) -> int:
    base = 70 if editor_score is None else max(0, min(100, int(editor_score)))
    penalty = sum(PENALTY.get(f.severity, 0) for f in findings)
    return max(0, base - penalty)


def score_output(editor_score: int | None, text: str, channel: str | None = None) -> tuple[int, list[Finding]]:
    findings = check_text(text, channel)
    return compute_brand_score(editor_score, findings), findings
