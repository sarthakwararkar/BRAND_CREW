"""Web/SEO search via Serper.dev. Returns a compact text digest for the SEO Researcher."""
from __future__ import annotations

from typing import Type

import httpx
from pydantic import BaseModel, Field

from backend.config import settings

SERPER_URL = "https://google.serper.dev/search"


def run_search(query: str, num: int = 8) -> str:
    if not settings.search_api_key:
        return "Search unavailable: SEARCH_API_KEY is not set. Base your keyword ideas on brand knowledge and say so."
    try:
        resp = httpx.post(
            SERPER_URL,
            headers={"X-API-KEY": settings.search_api_key, "Content-Type": "application/json"},
            json={"q": query, "num": num, "gl": settings.search_country},
            timeout=20,
        )
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:
        return f"Search failed: {exc}"

    lines: list[str] = [f"Results for: {query}"]
    for r in data.get("organic", [])[:num]:
        lines.append(f"- {r.get('title', '')}: {r.get('snippet', '')}")
    paa = data.get("peopleAlsoAsk", [])
    if paa:
        lines.append("People also ask:")
        lines += [f"- {q.get('question', '')}" for q in paa[:6]]
    related = data.get("relatedSearches", [])
    if related:
        lines.append("Related searches: " + "; ".join(r.get("query", "") for r in related[:8]))
    return "\n".join(lines)


def make_search_tool():
    from crewai.tools import BaseTool

    class SearchInput(BaseModel):
        query: str = Field(..., description="A search query, e.g. a candidate keyword or topic.")

    class WebSearchTool(BaseTool):
        name: str = "web_search"
        description: str = (
            "Search the web for keyword ideas, search intent, related searches and what competitors rank for. "
            "Use short, specific queries. Run several searches for different keyword candidates."
        )
        args_schema: Type[BaseModel] = SearchInput

        def _run(self, query: str) -> str:
            return run_search(query)

    return WebSearchTool()
