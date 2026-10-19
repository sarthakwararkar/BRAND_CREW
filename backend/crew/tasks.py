"""Task factory. Descriptions come from config/tasks.yaml; {placeholders} are filled per run."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

import yaml
from crewai import Agent, Task

from backend.crew.schemas import SCHEMAS

CONFIG_PATH = Path(__file__).parent / "config" / "tasks.yaml"


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:   # leave unknown {placeholders} untouched
        return "{" + key + "}"


def render(template: str, variables: dict[str, Any]) -> str:
    return template.format_map(_SafeDict({k: ("" if v is None else v) for k, v in variables.items()}))


def load_task_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def build_tasks(
    agents: dict[str, Agent],
    keys: Iterable[str],
    common: dict[str, Any] | None = None,
    per_task: dict[str, dict[str, Any]] | None = None,
) -> list[Task]:
    """Build tasks in the order of `keys`. `context` references are resolved among built tasks."""
    config = load_task_config()
    common = common or {}
    per_task = per_task or {}
    built: dict[str, Task] = {}

    for key in keys:
        cfg = config[key]
        variables = {**common, **per_task.get(key, {})}
        kwargs: dict[str, Any] = dict(
            description=render(cfg["description"], variables),
            expected_output=render(cfg["expected_output"], variables),
            agent=agents[cfg["agent"]],
        )
        ctx = [built[c] for c in cfg.get("context", []) if c in built]
        if ctx:
            kwargs["context"] = ctx
        if cfg.get("output"):
            kwargs["output_pydantic"] = SCHEMAS[cfg["output"]]
        built[key] = Task(**kwargs)

    return [built[k] for k in keys]
