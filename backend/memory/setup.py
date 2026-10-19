"""Memory wiring. ALL direct CrewAI memory calls live in this package so API changes stay isolated.

Design: agents never get a writable handle to shared scopes. Each agent gets an `AgentMemory`
that (a) recalls across its read scopes (a "slice") and (b) can write to at most ONE scope of
its own. `/company/knowledge` and `/visual/brand` are protected and unwritable through it.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Callable, Iterable

from backend.config import settings
from backend.memory import scopes as S
from backend.memory.lessons import age_in_weeks, parse_lesson_date, recency_weight

log = logging.getLogger(__name__)


class ReadOnlyScopeError(PermissionError):
    """Raised when something tries to write where it is not allowed."""


@dataclass
class RecalledItem:
    text: str
    score: float
    scope: str


# ---------- tolerant extraction (CrewAI match objects vs plain dicts in tests) ----------
def _extract_text(match: Any) -> str:
    record = getattr(match, "record", None)
    if record is not None:
        return str(getattr(record, "content", record))
    if isinstance(match, dict):
        return str(match.get("content") or match.get("text") or match)
    return str(getattr(match, "content", match))


def _extract_score(match: Any) -> float:
    score = getattr(match, "score", None)
    if score is None and isinstance(match, dict):
        score = match.get("score")
    try:
        return float(score) if score is not None else 0.0
    except (TypeError, ValueError):
        return 0.0


def _call_recall(backend: Any, query: str, scope: str, limit: int):
    try:
        return backend.recall(query, scope=scope, limit=limit, depth="shallow")  # shallow = no LLM call
    except TypeError:
        return backend.recall(query, scope=scope, limit=limit)


class AgentMemory:
    def __init__(self, agent_name: str, backend: Any, read_scopes: Iterable[str], write_scope: str | None = None):
        if write_scope in S.PROTECTED_SCOPES:
            raise ReadOnlyScopeError(f"{write_scope} is protected; agent '{agent_name}' cannot write to it")
        self.agent_name = agent_name
        self.backend = backend
        self.read_scopes = list(read_scopes)
        self.write_scope = write_scope

    # ---- reading ----
    def recall(
        self,
        query: str,
        limit: int = 5,
        scopes: Iterable[str] | None = None,
        recency: bool = False,
    ) -> list[RecalledItem]:
        targets = list(scopes) if scopes else self.read_scopes
        not_allowed = [s for s in targets if s not in self.read_scopes]
        if not_allowed:
            raise PermissionError(f"'{self.agent_name}' cannot read {not_allowed}")

        items: list[RecalledItem] = []
        for scope in targets:
            try:
                matches = _call_recall(self.backend, query, scope, limit)
            except Exception as exc:  # embedder down, empty store, ...
                log.warning("recall failed for %s in %s: %s", self.agent_name, scope, exc)
                continue
            for m in matches or []:
                items.append(RecalledItem(_extract_text(m), _extract_score(m), scope))

        if recency:
            items.sort(key=lambda i: i.score * recency_weight(parse_lesson_date(i.text)), reverse=True)
        else:
            items.sort(key=lambda i: i.score, reverse=True)
        return items[:limit]

    def context_block(
        self,
        query: str,
        limit: int = 5,
        scopes: Iterable[str] | None = None,
        recency: bool = False,
        fallback: Callable[[], str] | str | None = None,
    ) -> str:
        """Prompt-ready text. Falls back to files when recall is empty (if enabled in settings)."""
        items = self.recall(query, limit=limit, scopes=scopes, recency=recency)
        if items:
            return self.format_items(items)
        if fallback is not None and settings.memory_fallback_to_files:
            text = fallback() if callable(fallback) else fallback
            if text:
                return "(memory empty - using seed files)\n" + text
        return "(nothing stored yet)"

    @staticmethod
    def format_items(items: list[RecalledItem]) -> str:
        lines = []
        for i, item in enumerate(items, 1):
            d = parse_lesson_date(item.text)
            age = f" [{round(age_in_weeks(d))}w old]" if d else ""
            lines.append(f"--- item {i} ({item.scope}){age} ---\n{item.text.strip()}")
        return "\n".join(lines)

    # ---- writing ----
    def remember(self, text: str, **kwargs: Any):
        if self.write_scope is None:
            raise ReadOnlyScopeError(f"'{self.agent_name}' is read-only")
        return self.backend.remember(text, scope=self.write_scope, **kwargs)

    # ---- optional: native CrewAI read-only slice ----
    def crewai_slice(self):
        return self.backend.slice(scopes=self.read_scopes, read_only=True)


@lru_cache(maxsize=1)
def get_backend():
    """The real CrewAI Memory object (one per process)."""
    try:
        from crewai import Memory
    except ImportError as exc:  # older crewai without unified memory
        raise RuntimeError(
            "This crewai version has no `Memory` class. Upgrade crewai or adapt app/memory/setup.py."
        ) from exc

    kwargs: dict[str, Any] = {}
    embedder = settings.embedder_config()
    if embedder:
        kwargs["embedder"] = embedder
    kwargs["storage"] = str(settings.memory_store_path)
    from backend.crew.llms import get_llm

    kwargs["llm"] = get_llm("fast")

    optional = ["llm", "storage"]  # dropped in this order if the installed version rejects them
    while True:
        try:
            return Memory(**kwargs)
        except TypeError:
            if not optional:
                raise
            dropped = optional.pop(0)
            log.warning("Memory() rejected '%s'; retrying without it", dropped)
            kwargs.pop(dropped, None)


def get_agent_memory(agent_name: str, backend: Any | None = None) -> AgentMemory:
    if agent_name not in S.READ_SCOPES:
        raise KeyError(f"unknown agent '{agent_name}'")
    return AgentMemory(
        agent_name=agent_name,
        backend=backend if backend is not None else get_backend(),
        read_scopes=S.READ_SCOPES[agent_name],
        write_scope=S.WRITE_SCOPES.get(agent_name),
    )
