"""
YouTube search API integration
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import httpx
import os
import re


_STOPWORDS = {
    "a",
    "an",
    "and",
    "best",
    "easy",
    "for",
    "homemade",
    "how",
    "in",
    "make",
    "of",
    "recipe",
    "style",
    "the",
    "to",
    "with",
}


def _normalize_text(value: str) -> str:
    value = (value or "").strip().lower()
    value = re.sub(r"^\s*\d+\s*[\).:-]\s*", "", value)
    value = re.sub(r"\s+", " ", value)
    return value


def _tokenize(value: str) -> set[str]:
    value = _normalize_text(value)
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    tokens = {t for t in value.split() if t and t not in _STOPWORDS and len(t) > 1}
    return tokens


def _overlap_score(query: str, title: str) -> float:
    q = _tokenize(query)
    t = _tokenize(title)
    if not q or not t:
        return 0.0
    # Favor recall: coverage of query tokens in title.
    return len(q & t) / max(1, len(q))


def _build_query_variants(recipe_name: str, cuisine: str) -> list[str]:
    recipe = (recipe_name or "").strip()
    cuisine = (cuisine or "").strip()

    recipe_norm = re.sub(r"^\s*\d+\s*[\).:-]\s*", "", recipe).strip()
    recipe_norm = re.sub(r"\s+", " ", recipe_norm)

    cuisine_parts: list[str] = []
    if cuisine:
        # Support formats like "Mediterranean/Greek" or "Spanish (Mexican)".
        cuisine_parts = [
            p.strip() for p in re.split(r"[/,]|\(|\)", cuisine) if p and p.strip()
        ]

    variants: list[str] = []
    if recipe_norm and cuisine:
        variants.append(f"{recipe_norm} {cuisine} recipe")
    if recipe_norm:
        variants.append(f"{recipe_norm} recipe")
        variants.append(f"how to make {recipe_norm}")
    for c in cuisine_parts[:2]:
        if recipe_norm:
            variants.append(f"{recipe_norm} {c} recipe")

    # De-dup while preserving order.
    seen = set()
    out: list[str] = []
    for v in variants:
        key = _normalize_text(v)
        if key and key not in seen:
            out.append(v)
            seen.add(key)
    return out

router = APIRouter()


class YouTubeSearchRequest(BaseModel):
    """Request to search YouTube videos"""
    recipe_name: str = Field(..., description="Recipe name to search for")
    cuisine: str = Field(default="", description="Cuisine type (optional)")
    max_results: int = Field(default=5, ge=1, le=10, description="Max videos to return")


class YouTubeSearchResponse(BaseModel):
    """YouTube search results"""
    candidates: list[dict]


@router.post("/search", response_model=YouTubeSearchResponse)
async def search_youtube(req: YouTubeSearchRequest):
    """
    Search YouTube for recipe videos
    
    Requires: YOUTUBE_API_KEY environment variable
    Get one free at: https://console.cloud.google.com/apis/credentials
    
    Free tier: 10,000 requests/day
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        # Return empty results if no API key configured
        return YouTubeSearchResponse(candidates=[])
    
    try:
        queries = _build_query_variants(req.recipe_name, req.cuisine)
        if not queries:
            return YouTubeSearchResponse(candidates=[])

        def to_candidate(item: dict) -> dict:
            video_id = item["id"]["videoId"]
            snippet = item["snippet"]
            thumbs = snippet.get("thumbnails") or {}
            thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {})
            return {
                "video_id": video_id,
                "title": snippet.get("title") or "",
                "channel": snippet.get("channelTitle") or "",
                "language": "en",
                "transcript": (snippet.get("description") or "")[:500],
                "metadata": {
                    "thumbnail": thumb.get("url") or "",
                    "published_at": snippet.get("publishedAt") or "",
                },
            }

        # Multi-pass search: try stricter filters first, then relax to increase recall.
        passes: list[dict] = [
            {"videoDuration": "medium"},
            {"videoDuration": "any"},
            {},
        ]

        candidates_by_id: dict[str, dict] = {}
        async with httpx.AsyncClient(timeout=30) as client:
            for q in queries:
                for extra in passes:
                    params = {
                        "part": "snippet",
                        "type": "video",
                        "maxResults": req.max_results,
                        "q": q,
                        "key": api_key,
                        # Keep these light to avoid filtering everything out.
                        "safeSearch": "moderate",
                        **extra,
                    }

                    response = await client.get(
                        "https://www.googleapis.com/youtube/v3/search",
                        params=params,
                    )
                    response.raise_for_status()
                    data = response.json() or {}

                    items = data.get("items", []) or []
                    for item in items:
                        try:
                            cand = to_candidate(item)
                        except Exception:
                            continue
                        if cand.get("video_id"):
                            candidates_by_id[cand["video_id"]] = cand

                    # If we already have enough, stop early.
                    if len(candidates_by_id) >= req.max_results:
                        break
                if len(candidates_by_id) >= req.max_results:
                    break

        candidates = list(candidates_by_id.values())

        # Fuzzy sort: promote videos whose titles contain more of the recipe tokens.
        primary_query = queries[0]
        candidates.sort(key=lambda c: _overlap_score(primary_query, c.get("title", "")), reverse=True)

        return YouTubeSearchResponse(candidates=candidates[: req.max_results])
        
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube search failed: {str(e)}")
