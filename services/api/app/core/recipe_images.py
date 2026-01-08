from __future__ import annotations

import asyncio
import logging
import re
from typing import Any

from app.core.llm_client import get_reasoning_client

logger = logging.getLogger(__name__)


# Very small in-process cache to avoid repeating LLM calls.
# Keyed by normalized (recipe_name|cuisine|ingredients_fingerprint).
_IMAGE_QUERY_CACHE: dict[str, str] = {}
_IMAGE_QUERY_LOCK = asyncio.Lock()


def _normalize_text(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _fingerprint_ingredients(ingredients: list[str] | None) -> str:
    if not ingredients:
        return ""
    cleaned: list[str] = []
    for it in ingredients[:10]:
        if not isinstance(it, str):
            continue
        t = _normalize_text(it)
        if t:
            cleaned.append(t)
    cleaned = sorted(set(cleaned))
    return "|".join(cleaned)[:180]


def build_unsplash_query(*, recipe_name: str, cuisine: str = "") -> str:
    # Keep this conservative: keywords, no punctuation.
    name = _normalize_text(recipe_name)
    cuisine = _normalize_text(cuisine)

    parts: list[str] = ["food"]
    if cuisine and cuisine not in ("general", "mixed", "auto"):
        parts.append(cuisine)
    if name:
        parts.append(name)

    # Convert spaces to commas (Unsplash Source API treats comma-separated tokens well)
    query = ",".join([re.sub(r"[^a-z0-9\s]", " ", p).strip().replace(" ", ",") for p in parts if p])
    query = re.sub(r",+", ",", query).strip(",")
    return query or "food"


async def build_llm_image_query(
    *,
    recipe_name: str,
    cuisine: str = "",
    ingredients: list[str] | None = None,
) -> str:
    """Return a comma-separated query string for a plated-food photo.

    Uses the reasoning LLM to pick high-signal search keywords. Falls back
    to a deterministic query when the LLM is unavailable.
    """

    name = (recipe_name or "").strip()
    if not name:
        return build_unsplash_query(recipe_name="food", cuisine=cuisine)

    cuisine_clean = (cuisine or "").strip()
    fp = _fingerprint_ingredients(ingredients)
    cache_key = f"{_normalize_text(name)}|{_normalize_text(cuisine_clean)}|{fp}"

    async with _IMAGE_QUERY_LOCK:
        cached = _IMAGE_QUERY_CACHE.get(cache_key)
        if isinstance(cached, str) and cached.strip():
            return cached

    # LLM best-effort.
    try:
        client = get_reasoning_client()

        ing_line = ", ".join([_normalize_text(i) for i in (ingredients or []) if isinstance(i, str) and i.strip()])
        ing_line = ", ".join([s for s in ing_line.split(",") if s.strip()])
        ing_line = ing_line[:240]

        schema: dict[str, Any] = {
            "type": "object",
            "properties": {
                "keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 4,
                    "maxItems": 7,
                }
            },
            "required": ["keywords"],
            "additionalProperties": False,
        }

        messages = [
            {
                "role": "system",
                "content": (
                    "You generate search keywords for a REAL photo of a cooked dish. "
                    "Return JSON only. Rules: "
                    "- keywords must describe the finished plated dish (not raw ingredients) "
                    "- avoid brands, people, text, logos, packaging "
                    "- keep each keyword 1-3 words, lowercase "
                    "- include cuisine and dish-type cues where helpful"
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Dish name: {name}\n"
                    f"Cuisine: {cuisine_clean or 'general'}\n"
                    + (f"Key ingredients: {ing_line}\n" if ing_line else "")
                    + "Return keywords."
                ),
            },
        ]

        out = await client.generate_json(messages=messages, schema=schema)
        kws_raw = out.get("keywords") if isinstance(out, dict) else None
        kws: list[str] = []
        if isinstance(kws_raw, list):
            for k in kws_raw:
                s = _normalize_text(str(k))
                s = re.sub(r"[^a-z0-9\s]", " ", s).strip()
                s = re.sub(r"\s+", " ", s)
                if not s:
                    continue
                # keep short
                if len(s) > 40:
                    s = s[:40].strip()
                kws.append(s)

        # Ensure core terms exist.
        base = ["food"]
        if cuisine_clean and _normalize_text(cuisine_clean) not in ("general", "mixed", "auto"):
            base.append(_normalize_text(cuisine_clean))
        base.append(_normalize_text(name))

        all_terms: list[str] = []
        seen: set[str] = set()
        for term in base + kws:
            term = _normalize_text(term)
            if not term:
                continue
            if term in seen:
                continue
            seen.add(term)
            all_terms.append(term)

        query = ",".join([t.replace(" ", ",") for t in all_terms[:10] if t])
        query = re.sub(r",+", ",", query).strip(",")
        if not query:
            query = build_unsplash_query(recipe_name=name, cuisine=cuisine_clean)

        async with _IMAGE_QUERY_LOCK:
            _IMAGE_QUERY_CACHE[cache_key] = query
        return query

    except Exception as e:
        # Fall back to deterministic query; do not fail the request.
        logger.debug("LLM image query fallback for %s: %s", name, e)
        query = build_unsplash_query(recipe_name=name, cuisine=cuisine_clean)
        async with _IMAGE_QUERY_LOCK:
            _IMAGE_QUERY_CACHE[cache_key] = query
        return query
