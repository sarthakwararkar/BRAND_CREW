"""Scope paths and who may read/write what. The ONLY place scope strings are defined."""
from __future__ import annotations

COMPANY_KNOWLEDGE = "/company/knowledge"
MARKETING_SEO = "/marketing/seo"
MARKETING_CAMPAIGNS = "/marketing/campaigns"
EDITOR_PRIVATE = "/editor/private"
VISUAL_BRAND = "/visual/brand"

ALL_SCOPES = [COMPANY_KNOWLEDGE, MARKETING_SEO, MARKETING_CAMPAIGNS, EDITOR_PRIVATE, VISUAL_BRAND]

# Human-seeded scopes. No agent-facing object can ever write here.
PROTECTED_SCOPES = frozenset({COMPANY_KNOWLEDGE, VISUAL_BRAND})

# "Slices": which scopes each agent can READ.
READ_SCOPES: dict[str, list[str]] = {
    "strategist": [MARKETING_CAMPAIGNS, MARKETING_SEO, COMPANY_KNOWLEDGE],
    "seo_researcher": [MARKETING_SEO, COMPANY_KNOWLEDGE],
    "copywriter": [MARKETING_CAMPAIGNS, COMPANY_KNOWLEDGE],
    "visual_brand": [VISUAL_BRAND, COMPANY_KNOWLEDGE],
    "brand_editor": [EDITOR_PRIVATE, COMPANY_KNOWLEDGE],
    "landing_builder": [COMPANY_KNOWLEDGE, VISUAL_BRAND],
    "performance_analyst": [MARKETING_CAMPAIGNS, COMPANY_KNOWLEDGE],
}

# The single scope each agent may WRITE to (agents not listed are read-only).
WRITE_SCOPES: dict[str, str] = {
    "seo_researcher": MARKETING_SEO,
    "brand_editor": EDITOR_PRIVATE,
    "performance_analyst": MARKETING_CAMPAIGNS,
}
