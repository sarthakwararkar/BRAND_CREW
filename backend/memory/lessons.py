"""Dated, structured lessons + recency weighting. No dependency on CrewAI."""
from __future__ import annotations

import re
from datetime import date
from typing import Literal

from pydantic import BaseModel

from backend.config import settings

_DATE_RE = re.compile(r"date:\s*(\d{4}-\d{2}-\d{2})")

Outcome = Literal["worked", "flopped", "mixed"]


class Lesson(BaseModel):
    date: str                     # YYYY-MM-DD
    week_id: str                  # e.g. 2026-W42
    channel: str                  # blog | landing | linkedin | x | instagram
    angle: str
    outcome: Outcome
    evidence: str
    why: str
    recommendation: str

    def to_text(self) -> str:
        return (
            f"date: {self.date}\n"
            f"week_id: {self.week_id}\n"
            f"channel: {self.channel}\n"
            f'angle: "{self.angle}"\n'
            f"outcome: {self.outcome}\n"
            f'evidence: "{self.evidence}"\n'
            f'why: "{self.why}"\n'
            f'recommendation: "{self.recommendation}"'
        )


def parse_lesson_date(text: str) -> date | None:
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def age_in_weeks(d: date, today: date | None = None) -> float:
    today = today or date.today()
    return max(0.0, (today - d).days / 7.0)


def recency_weight(d: date | None, today: date | None = None, half_life_weeks: float | None = None) -> float:
    """1.0 for today, 0.5 after one half-life. Undated items are not penalised."""
    if d is None:
        return 1.0
    half_life = half_life_weeks or settings.recall_half_life_weeks
    return 0.5 ** (age_in_weeks(d, today) / half_life)


def store_lesson(mem, lesson: Lesson):
    """`mem` is an AgentMemory. Only agents with a write scope (the analyst) can store."""
    return mem.remember(lesson.to_text())
