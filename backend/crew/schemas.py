"""Pydantic output schemas for tasks + a tolerant parser."""
from __future__ import annotations

import re
from typing import Literal, Type, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T", bound=BaseModel)


class WeeklyPlan(BaseModel):
    theme: str
    audience_segment: str
    primary_keyword: str
    angles: list[str] = Field(description="2-3 angles to try this week")
    angle_to_avoid: str
    channels: list[str]
    rationale: str
    lessons_used: list[str] = Field(
        default_factory=list,
        description="Exact past-lesson angles this plan relies on. Empty list if none were available.",
    )


class SEOBrief(BaseModel):
    primary_keyword: str
    secondary_keywords: list[str]
    search_intent: str
    outline_suggestions: list[str]
    content_gaps: list[str]
    notes: str = ""


class LandingSection(BaseModel):
    heading: str
    body: str


class LandingCopy(BaseModel):
    headline: str
    subheadline: str
    sections: list[LandingSection]
    cta_text: str
    meta_description: str


class ContentDraft(BaseModel):
    angle_used: str = Field(description="Which planned angle this content follows")
    landing: LandingCopy
    blog_title: str
    blog_markdown: str
    linkedin_post: str
    x_post: str = Field(description="Max 280 characters")
    instagram_caption: str
    hashtags: list[str] = Field(default_factory=list)
    visual_direction: str = Field(default="", description="Imagery, colors and layout ideas for this content")


class VisualReport(BaseModel):
    applicable: bool = Field(
        default=True,
        description="False if no visual assets or visual notes exist to check",
    )
    passed: bool = Field(
        default=False,
        description="False unless the visual review explicitly confirms the draft passes",
    )
    issues: list[str] = Field(default_factory=list)
    suggested_fixes: list[str] = Field(default_factory=list)
    notes: str = "Visual review output was incomplete; treat this review as not passed."


class Violation(BaseModel):
    rule: str
    severity: Literal["low", "medium", "high"]
    original: str
    fix: str


class EditorReport(BaseModel):
    brand_score: int = Field(ge=0, le=100)
    summary: str
    violations: list[Violation] = Field(default_factory=list)
    recurring_patterns: list[str] = Field(
        default_factory=list,
        description="Mistakes the copywriter keeps making that deserve a standing reminder",
    )


class EditedContent(BaseModel):
    content: ContentDraft
    report: EditorReport


class LessonDraft(BaseModel):
    channel: str
    angle: str
    outcome: Literal["worked", "flopped", "mixed"]
    evidence: str
    why: str
    recommendation: str


class Lessons(BaseModel):
    lessons: list[LessonDraft]


SCHEMAS: dict[str, Type[BaseModel]] = {
    "WeeklyPlan": WeeklyPlan,
    "SEOBrief": SEOBrief,
    "ContentDraft": ContentDraft,
    "VisualReport": VisualReport,
    "EditedContent": EditedContent,
    "Lessons": Lessons,
}


def coerce_output(task_output, model_cls: Type[T]) -> T | None:
    """Get a typed model from a CrewAI TaskOutput, falling back to parsing the raw text."""
    parsed = getattr(task_output, "pydantic", None)
    if isinstance(parsed, model_cls):
        return parsed
    raw = (getattr(task_output, "raw", "") or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    for candidate in (raw, raw[raw.find("{"): raw.rfind("}") + 1] if "{" in raw else ""):
        if not candidate:
            continue
        try:
            return model_cls.model_validate_json(candidate)
        except Exception:
            continue
    return None
