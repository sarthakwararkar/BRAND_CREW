"""Pydantic models for MongoDB documents and API request bodies."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field

RunStatus = Literal["queued", "running", "awaiting_approval", "approved", "analyzing", "analyzed", "failed"]
OutputType = Literal["landing", "blog", "social_linkedin", "social_x", "social_instagram"]
Approval = Literal["pending", "approved", "needs_changes", "rejected"]


def new_id() -> str:
    return uuid4().hex[:12]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------- documents ----------------
class Run(BaseModel):
    id: str = Field(default_factory=new_id)
    week_id: str
    status: RunStatus = "queued"
    theme_override: str | None = None
    plan: dict[str, Any] | None = None
    progress: list[str] = Field(default_factory=list)
    usage: dict[str, Any] | None = None
    error: str | None = None
    created_at: datetime = Field(default_factory=utcnow)
    completed_at: datetime | None = None


class Output(BaseModel):
    id: str = Field(default_factory=new_id)
    run_id: str
    type: OutputType
    content: str = ""
    content_path: str | None = None          # URL path under /outputs for files
    editor_report: dict[str, Any] | None = None
    brand_score: int = 0                     # 0-100
    findings: list[dict[str, Any]] = Field(default_factory=list)   # deterministic checker results
    visual_report: dict[str, Any] | None = None
    approval: Approval = "pending"
    meta: dict[str, Any] = Field(default_factory=dict)             # angle, keyword, week_id
    created_at: datetime = Field(default_factory=utcnow)


class Rating(BaseModel):
    id: str = Field(default_factory=new_id)
    output_id: str
    thumbs: Literal["up", "down"]
    note: str = ""
    created_at: datetime = Field(default_factory=utcnow)


class Metric(BaseModel):
    id: str = Field(default_factory=new_id)
    output_id: str
    impressions: int | None = None
    clicks: int | None = None
    ctr: float | None = None
    engagement: int | None = None
    conversions: int | None = None
    recorded_at: datetime = Field(default_factory=utcnow)


class LessonRef(BaseModel):
    id: str = Field(default_factory=new_id)
    run_id: str
    memory_scope: str
    summary: str
    created_at: datetime = Field(default_factory=utcnow)


# ---------------- request bodies ----------------
class StartRunRequest(BaseModel):
    theme_override: str | None = None


class ApprovalDecision(BaseModel):
    output_id: str
    approval: Approval


class ApproveRequest(BaseModel):
    decisions: list[ApprovalDecision]


class RatingIn(BaseModel):
    output_id: str
    thumbs: Literal["up", "down"]
    note: str = ""


class MetricIn(BaseModel):
    output_id: str
    impressions: int | None = None
    clicks: int | None = None
    ctr: float | None = None
    engagement: int | None = None
    conversions: int | None = None


class FeedbackRequest(BaseModel):
    ratings: list[RatingIn] = Field(default_factory=list)
    metrics: list[MetricIn] = Field(default_factory=list)


class ReseedRequest(BaseModel):
    force: bool = True
