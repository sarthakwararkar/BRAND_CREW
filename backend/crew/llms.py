"""Per-agent LLM selection. Tiers map to models configured in .env."""
from __future__ import annotations

from crewai import LLM

from backend.config import settings

TIERS = {
    #  tier      model                    temperature
    "fast":   (lambda: settings.fast_model,   0.3),   # strategist, seo, analyst
    "strong": (lambda: settings.strong_model, 0.7),   # copywriter
    "editor": (lambda: settings.strong_model, 0.2),   # brand editor: precise, low creativity
    "vision": (lambda: settings.vision_model, 0.2),   # visual brand agent
    "code":   (lambda: settings.code_model,   0.3),   # landing page builder
}


def get_llm(tier: str) -> LLM:
    if tier not in TIERS:
        raise KeyError(f"unknown LLM tier '{tier}'")
    model_getter, temperature = TIERS[tier]
    model = model_getter()
    kwargs = {"model": model, "temperature": temperature}
    if model.startswith(("ollama/", "ollama_chat/")):
        kwargs["base_url"] = settings.ollama_base_url
    return LLM(**kwargs)
