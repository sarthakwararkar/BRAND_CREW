"""Central settings. Scope paths live in app/memory/scopes.py, everything else lives here."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent              # .../backend
PROJECT_DIR = BACKEND_DIR.parent                           # repo root

load_dotenv(BACKEND_DIR / ".env")
load_dotenv(PROJECT_DIR / ".env")


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, "") or default)
    except ValueError:
        return default


def _path(name: str, default: Path) -> Path:
    raw = os.getenv(name)
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (PROJECT_DIR / p).resolve()


@dataclass(frozen=True)
class Settings:
    # infra
    mongodb_uri: str
    mongodb_db: str
    admin_token: str
    cors_origins: list[str]

    # paths
    data_dir: Path
    brand_dir: Path
    outputs_dir: Path
    memory_store_path: Path

    # models (LiteLLM-style strings, e.g. "ollama_chat/qwen2.5:3b", "gemini/gemini-3.8-flash")
    fast_model: str
    strong_model: str
    vision_model: str
    code_model: str
    ollama_base_url: str

    # embeddings for memory
    embedder_provider: str
    embedder_model: str
    embedder_api_key: str

    # tools
    search_api_key: str
    search_country: str

    # brand + behaviour
    brand_name: str
    memory_fallback_to_files: bool
    recall_half_life_weeks: float
    cost_per_million_tokens_usd: float

    def embedder_config(self) -> dict | None:
        """Embedder dict for crewai Memory. Key names (model_name vs model) vary by provider."""
        if not self.embedder_provider:
            return None
        cfg = {"model_name": self.embedder_model} if self.embedder_model else {}
        if self.embedder_provider == "ollama":
            cfg["url"] = f"{self.ollama_base_url}/api/embeddings"
        if self.embedder_api_key:
            cfg["api_key"] = self.embedder_api_key
        return {"provider": self.embedder_provider, "config": cfg}


def load_settings() -> Settings:
    uri = os.getenv("MONGODB_URI", "").strip() or "mongodb://localhost:27017/brandcrew"
    db_name = urlparse(uri).path.lstrip("/") or "brandcrew"
    data_dir = BACKEND_DIR / "data"
    fast = os.getenv("FAST_MODEL", "").strip() or "ollama_chat/qwen2.5:3b"
    strong = os.getenv("STRONG_MODEL", "").strip() or fast
    gemini_api_key = os.getenv("GEMINI_API_KEY", "").strip()
    openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    embedder_provider = os.getenv("EMBEDDER_PROVIDER", "").strip()
    if not embedder_provider:
        if fast.startswith(("ollama/", "ollama_chat/")):
            embedder_provider = "ollama"
        elif gemini_api_key:
            embedder_provider = "google-generativeai"
        elif openai_api_key:
            embedder_provider = "openai"
    embedder_model = os.getenv("EMBEDDER_MODEL", "").strip()
    if not embedder_model:
        embedder_model = (
            "nomic-embed-text:latest"
            if embedder_provider == "ollama"
            else "gemini-embedding-001"
            if embedder_provider == "google-generativeai"
            else "text-embedding-3-small"
            if embedder_provider == "openai"
            else ""
        )
    if embedder_provider == "google-generativeai":
        embedder_api_key = gemini_api_key or os.getenv("GOOGLE_API_KEY", "").strip()
    elif embedder_provider == "openai":
        embedder_api_key = openai_api_key
    else:
        embedder_api_key = ""
    return Settings(
        mongodb_uri=uri,
        mongodb_db=db_name,
        admin_token=os.getenv("ADMIN_TOKEN", ""),
        cors_origins=[o.strip() for o in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",") if o.strip()],
        data_dir=data_dir,
        brand_dir=data_dir / "brand",
        outputs_dir=data_dir / "outputs",
        memory_store_path=_path("MEMORY_STORAGE_PATH", data_dir / "memory_store"),
        fast_model=fast,
        strong_model=strong,
        vision_model=os.getenv("VISION_MODEL", "").strip() or fast,
        code_model=os.getenv("CODE_MODEL", "").strip() or strong,
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "").strip().rstrip("/") or "http://localhost:11434",
        embedder_provider=embedder_provider,
        embedder_model=embedder_model,
        embedder_api_key=embedder_api_key,
        search_api_key=os.getenv("SEARCH_API_KEY", ""),
        search_country=os.getenv("SEARCH_COUNTRY", "in"),
        brand_name=os.getenv("BRAND_NAME", "Lumio"),
        memory_fallback_to_files=_bool("MEMORY_FALLBACK_TO_FILES", True),
        recall_half_life_weeks=_float("RECALL_HALF_LIFE_WEEKS", 8.0),
        cost_per_million_tokens_usd=_float("COST_PER_MILLION_TOKENS_USD", 0.0),
    )


settings = load_settings()
