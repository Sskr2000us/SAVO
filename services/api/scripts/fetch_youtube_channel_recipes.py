"""Fetch recipe entries from specific YouTube cooking channels.

Goal
- Fill out the catalog with additional recipe entries backed by YouTube videos.
- We only store *metadata* (title-derived name, thumbnail URL, video_url). We do not copy
  transcripts/descriptions.

Requirements
- YOUTUBE_API_KEY must be set (YouTube Data API v3)

Output
- JSON array compatible with `build_recipe_catalog.py`:
  - recipe_id
  - recipe_name (as {"en": ...})
  - cuisine
  - image_url (YouTube thumbnail)
  - video_url (watch URL)

Example
  python services/api/scripts/fetch_youtube_channel_recipes.py \
    --channel "IndiaRecipesTamil" \
    --channel "GomathisKitchen" \
    --channel "HomeCookingShow" \
    --channel "vahrehvah" \
    --limit 450 \
    --out data/recipes/youtube_channels.json
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
from dotenv import load_dotenv


YOUTUBE_API = "https://www.googleapis.com/youtube/v3"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def _clean_recipe_title(title: str) -> str:
    # Turn video titles into a clean-ish recipe name.
    t = (title or "").strip()
    t = re.sub(r"\s+", " ", t)

    # Remove common suffixes/prefixes.
    t = re.sub(r"(?i)\b(recipe|recipes|how to make|how-to|easy|quick)\b", "", t)
    t = re.sub(r"(?i)\b(in tamil|tamil|telugu|hindi|english)\b", "", t)
    t = re.sub(r"(?i)\b(step by step|step-by-step|restaurant style|street style)\b", "", t)

    # Remove bracketed noise.
    t = re.sub(r"\[[^\]]*\]", "", t)
    t = re.sub(r"\([^)]*\)", "", t)

    # Clean punctuation.
    t = re.sub(r"[|•·]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip(" -–—:")

    # Keep it bounded.
    if len(t) > 80:
        t = t[:80].rstrip()

    return t.strip() or (title or "").strip() or "Recipe"


def _yt_get(client: httpx.Client, endpoint: str, *, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{YOUTUBE_API}/{endpoint}"
    r = client.get(url, params=params, headers={"Accept": "application/json"})
    try:
        r.raise_for_status()
    except httpx.HTTPStatusError:
        # Avoid leaking the API key in exception messages.
        req_url = str(r.request.url)
        req_url = re.sub(r"([?&]key=)[^&]+", r"\1REDACTED", req_url)
        detail = ""
        try:
            data = r.json()
            if isinstance(data, dict):
                err = data.get("error")
                if isinstance(err, dict):
                    msg = err.get("message")
                    if isinstance(msg, str) and msg.strip():
                        detail = f" Details: {msg.strip()}"
        except Exception:
            pass
        raise RuntimeError(
            f"YouTube API request failed with HTTP {r.status_code} for endpoint '{endpoint}'."
            f"{detail} URL={req_url}"
        )
    data = r.json()
    if not isinstance(data, dict):
        raise ValueError(f"Unexpected response from {endpoint}")
    return data


def _resolve_channel_id(client: httpx.Client, *, api_key: str, query: str) -> Optional[str]:
    # Try search.list for channel.
    q = (query or "").strip()
    if not q:
        return None

    data = _yt_get(
        client,
        "search",
        params={
            "part": "snippet",
            "q": q,
            "type": "channel",
            "maxResults": 5,
            "key": api_key,
        },
    )

    items = data.get("items")
    if not isinstance(items, list):
        return None

    qn = _norm(q).replace("@", "")

    # Pick best match by substring against channelTitle.
    best: Tuple[int, Optional[str]] = (-1, None)
    for it in items:
        if not isinstance(it, dict):
            continue
        cid = (((it.get("id") or {}) if isinstance(it.get("id"), dict) else {}) or {}).get("channelId")
        cid = str(cid or "").strip()
        if not cid:
            continue
        snippet = it.get("snippet") if isinstance(it.get("snippet"), dict) else {}
        title = _norm(str(snippet.get("channelTitle") or ""))
        # crude score
        score = 0
        if qn and qn in title:
            score += 3
        if title and any(tok and tok in title for tok in qn.split()[:3]):
            score += 1
        if score > best[0]:
            best = (score, cid)

    return best[1] or None


def _fetch_channel_videos(
    client: httpx.Client,
    *,
    api_key: str,
    channel_id: str,
    per_channel_limit: int,
    order: str,
) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    page_token: Optional[str] = None

    while len(out) < per_channel_limit:
        data = _yt_get(
            client,
            "search",
            params={
                "part": "snippet",
                "channelId": channel_id,
                "type": "video",
                "order": order,
                "maxResults": 50,
                "pageToken": page_token or "",
                "key": api_key,
                "safeSearch": "moderate",
            },
        )

        items = data.get("items")
        if not isinstance(items, list) or not items:
            break

        for it in items:
            if not isinstance(it, dict):
                continue
            vid = (((it.get("id") or {}) if isinstance(it.get("id"), dict) else {}) or {}).get("videoId")
            vid = str(vid or "").strip()
            if not vid:
                continue
            snippet = it.get("snippet") if isinstance(it.get("snippet"), dict) else {}
            title = str(snippet.get("title") or "").strip()
            channel_title = str(snippet.get("channelTitle") or "").strip()
            thumbs = snippet.get("thumbnails") if isinstance(snippet.get("thumbnails"), dict) else {}
            thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}) if isinstance(thumbs, dict) else {}
            thumb_url = str((thumb or {}).get("url") or "").strip()

            out.append(
                {
                    "video_id": vid,
                    "title": title,
                    "channel": channel_title,
                    "thumbnail": thumb_url,
                }
            )
            if len(out) >= per_channel_limit:
                break

        page_token = str(data.get("nextPageToken") or "").strip() or None
        if not page_token:
            break

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch recipe entries from YouTube channels")
    parser.add_argument("--channel", action="append", required=True, help="Channel name/handle to search")
    parser.add_argument("--limit", type=int, default=450, help="Total number of video-backed recipe entries to produce")
    parser.add_argument(
        "--per-channel-limit",
        type=int,
        default=400,
        help="Max videos to consider per channel (before global limit trimming)",
    )
    parser.add_argument(
        "--cuisine",
        default="Indian",
        help="Cuisine label to assign to these channel-derived entries",
    )
    parser.add_argument(
        "--order",
        default="viewCount",
        choices=["date", "viewCount", "relevance", "rating", "title"],
        help="YouTube search order to use per channel (default: viewCount for 'popular')",
    )
    parser.add_argument(
        "--exclude-shorts",
        action="store_true",
        help="Drop videos that look like Shorts/non-recipe clips (title-based heuristic)",
    )
    parser.add_argument(
        "--api-key",
        default="",
        help="Optional YouTube Data API key. If omitted, uses YOUTUBE_API_KEY from environment/.env.",
    )

    parser.add_argument(
        "--out",
        default=str(_repo_root() / "data" / "recipes" / "youtube_channels.json"),
    )

    args = parser.parse_args()

    # Load environment variables from services/api/.env when present.
    try:
        load_dotenv(_repo_root() / "services" / "api" / ".env", override=False)
    except Exception:
        pass

    api_key = (str(args.api_key or "").strip() or (os.getenv("YOUTUBE_API_KEY") or "").strip())
    if not api_key:
        raise SystemExit(
            "YOUTUBE_API_KEY is not set. Set it in your environment, add it to services/api/.env, or pass --api-key."
        )

    total_limit = max(1, int(args.limit or 1))
    per_channel_limit = max(1, int(args.per_channel_limit or 1))
    cuisine = str(args.cuisine or "Indian").strip() or "Indian"
    order = str(args.order or "viewCount").strip() or "viewCount"
    exclude_shorts = bool(args.exclude_shorts)

    channels = [str(c).strip() for c in (args.channel or []) if str(c).strip()]
    if not channels:
        raise SystemExit("Provide at least one --channel")

    timeout = httpx.Timeout(30.0, connect=10.0)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        all_vids: List[Dict[str, Any]] = []
        seen_video_ids: set[str] = set()

        for ch in channels:
            cid = _resolve_channel_id(client, api_key=api_key, query=ch)
            if not cid:
                print(f"WARN: could not resolve channel: {ch}")
                continue

            vids = _fetch_channel_videos(
                client,
                api_key=api_key,
                channel_id=cid,
                per_channel_limit=per_channel_limit,
                order=order,
            )
            for v in vids:
                vid = str(v.get("video_id") or "").strip()
                if not vid or vid in seen_video_ids:
                    continue

                title = str(v.get("title") or "").strip().lower()
                if exclude_shorts:
                    # Simple best-effort filtering; avoids Shorts and obvious non-recipe content.
                    if "#short" in title or "shorts" in title:
                        continue
                    if "trailer" in title or "promo" in title:
                        continue
                    if "live" in title and "cook" not in title and "recipe" not in title:
                        continue

                seen_video_ids.add(vid)
                all_vids.append(v)

        recipes: List[Dict[str, Any]] = []
        for v in all_vids:
            if len(recipes) >= total_limit:
                break

            vid = str(v.get("video_id") or "").strip()
            title = str(v.get("title") or "").strip()
            channel_title = str(v.get("channel") or "").strip()
            thumb = str(v.get("thumbnail") or "").strip()

            name = _clean_recipe_title(title)

            recipes.append(
                {
                    "recipe_id": f"youtube:{vid}",
                    "recipe_name": {"en": name},
                    "cuisine": cuisine,
                    "cuisine_code": cuisine.lower().replace(" ", "_"),
                    "language": "en",
                    "difficulty": "easy",
                    "servings": 4,
                    # Image/video are links only (no rehosting).
                    "image_url": thumb or f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
                    "video_url": f"https://www.youtube.com/watch?v={vid}",
                    "source": {
                        "provider": "youtube",
                        "channel": channel_title,
                        "channel_query": str(args.channel),
                        "video_id": vid,
                        "video_title": title,
                    },
                    # Minimal instructions to keep UX coherent even without extraction.
                    "instructions": [
                        "Watch the linked video tutorial.",
                        "Use the steps shown in the video; this entry is a curated video reference.",
                    ],
                    "ingredients": [],
                }
            )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(recipes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Fetched {len(recipes)} video-backed entries -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
