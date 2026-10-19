"""Agent factory. Roles/goals/backstories come from config/agents.yaml."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import yaml
from crewai import Agent

from backend.crew.llms import get_llm

CONFIG_PATH = Path(__file__).parent / "config" / "agents.yaml"


def _tool_registry() -> dict:
    # built lazily so importing this module never needs API keys
    from backend.tools.brand_checker import make_brand_checker_tool
    from backend.tools.image_tool import make_image_tool
    from backend.tools.search_tool import make_search_tool

    return {
        "web_search": make_search_tool,
        "brand_checker": make_brand_checker_tool,
        "brand_visual_assets": make_image_tool,
    }


def load_agent_config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def build_agents(keys: Iterable[str] | None = None) -> dict[str, Agent]:
    config = load_agent_config()
    registry = _tool_registry()
    agents: dict[str, Agent] = {}
    for key in (keys or config.keys()):
        cfg = config[key]
        tools = [registry[name]() for name in cfg.get("tools", [])]
        agents[key] = Agent(
            role=cfg["role"],
            goal=cfg["goal"],
            backstory=cfg["backstory"],
            llm=get_llm(cfg["llm_tier"]),
            tools=tools,
            allow_delegation=False,          # v1: keep behaviour predictable
            verbose=True,
            max_iter=cfg.get("max_iter", 6),
        )
    return agents
