"""Build a curated recipe catalog JSON for SAVO.

This script creates/updates the repo-root `ALL_RECIPES_COMPLETE.json` from one or
more input files and optionally attaches `video_url` and `image_urls` fields.

Important:
- Provide recipes you have rights to use.
- This tool does not scrape copyrighted recipe pages.

Usage examples:
  python services/api/scripts/build_recipe_catalog.py --in data/recipes/my_1000.json --target-count 1000

  python services/api/scripts/build_recipe_catalog.py \
    --in data/recipes/my_1000.json \
    --video-map data/recipes/video_map.csv \
    --add-image-urls \
    --target-count 1000

Input format:
- A JSON array of recipe objects.
- Each object must include at least `recipe_name` (string or {"en": "..."}) and `cuisine`.

Output:
- Writes a JSON array to `ALL_RECIPES_COMPLETE.json` by default.

Tip:
- To fetch from open/free sources (no scraping), see `services/api/scripts/fetch_open_recipe_sources.py`.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


_RE_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def _repo_root() -> Path:
    # services/api/scripts/build_recipe_catalog.py -> repo root is parents[3]
    return Path(__file__).resolve().parents[3]


def _normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _name_en(recipe: Dict[str, Any]) -> str:
    rn = recipe.get("recipe_name")
    if isinstance(rn, dict):
        en = rn.get("en")
        if isinstance(en, str) and en.strip():
            return _normalize_space(en)
        # best-effort: first non-empty string value
        for v in rn.values():
            if isinstance(v, str) and v.strip():
                return _normalize_space(v)
        return ""
    if isinstance(rn, str):
        return _normalize_space(rn)
    return ""


def _ensure_recipe_name_object(recipe: Dict[str, Any]) -> None:
    rn = recipe.get("recipe_name")
    if isinstance(rn, dict):
        if "en" not in rn:
            en = ""
            for v in rn.values():
                if isinstance(v, str) and v.strip():
                    en = _normalize_space(v)
                    break
            rn["en"] = en
        recipe["recipe_name"] = {k: str(v) for k, v in rn.items() if isinstance(k, str)}
        return

    if isinstance(rn, str):
        recipe["recipe_name"] = {"en": _normalize_space(rn)}
        return

    recipe["recipe_name"] = {"en": ""}


def _cuisine(recipe: Dict[str, Any]) -> str:
    c = recipe.get("cuisine")
    if isinstance(c, str) and c.strip():
        return _normalize_space(c)
    cc = recipe.get("cuisine_code")
    if isinstance(cc, str) and cc.strip():
        return _normalize_space(cc)
    return "general"


def _slug(value: str) -> str:
    s = (value or "").strip().lower()
    s = _RE_NON_ALNUM.sub("-", s).strip("-")
    s = re.sub(r"-+", "-", s)
    return s


def _stable_recipe_id(*, name_en: str, cuisine: str) -> str:
    base = _slug(name_en) or "recipe"
    c = _slug(cuisine) or "general"
    return f"{base}--{c}"[:96]


def _dedupe_key(recipe: Dict[str, Any]) -> Tuple[str, str]:
    return (_slug(_name_en(recipe)), _slug(_cuisine(recipe)))


def _load_json_list(path: Path) -> List[Dict[str, Any]]:
    raw = path.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError(f"Expected JSON array in {path}")
    out: List[Dict[str, Any]] = []
    for i, x in enumerate(data):
        if not isinstance(x, dict):
            raise ValueError(f"Entry {i} in {path} is not an object")
        out.append(dict(x))
    return out


def _load_video_map_csv(path: Path) -> Dict[Tuple[str, str], str]:
    """CSV columns supported:

    - recipe_name_en (or title) and cuisine and video_url
    - or recipe_id and video_url

    Matching uses (name_en, cuisine) when possible; falls back to recipe_id.
    """

    by_name: Dict[Tuple[str, str], str] = {}
    by_id: Dict[str, str] = {}

    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not isinstance(row, dict):
                continue
            vid = (row.get("video_url") or row.get("videoUrl") or "").strip()
            if not vid:
                continue

            rid = (row.get("recipe_id") or row.get("recipeId") or "").strip()
            if rid:
                by_id[rid] = vid

            title = (row.get("recipe_name_en") or row.get("title") or row.get("recipe_name") or "").strip()
            cuisine = (row.get("cuisine") or row.get("cuisine_code") or "general").strip()
            if title:
                by_name[(_slug(title), _slug(cuisine or "general"))] = vid

    # Merge: name match takes priority; id match later.
    # We return both in one mapping by using a special key shape.
    # Caller will check name first, then id.
    out: Dict[Tuple[str, str], str] = dict(by_name)
    for rid, url in by_id.items():
        out[(f"__id__:{rid}", "")] = url
    return out


def _build_image_urls(*, name_en: str, cuisine: str, count: int = 3) -> List[str]:
    # Store as relative API paths so mobile/web can prefix base URL.
    name_q = name_en
    cuisine_q = cuisine or "general"
    urls: List[str] = []
    for seed in range(max(1, int(count))):
        urls.append(
            "/recipes/image/proxy"
            f"?recipe_name={_urlencode(name_q)}"
            f"&cuisine={_urlencode(cuisine_q)}"
            f"&seed={seed}"
        )
    return urls


def _urlencode(value: str) -> str:
    # Avoid importing urllib just for this; minimal encoding.
    # This is sufficient for query use in our API (FastAPI decodes it).
    return (
        (value or "")
        .replace("%", "%25")
        .replace(" ", "%20")
        .replace("\n", "%0A")
        .replace("\r", "%0D")
        .replace("\t", "%09")
        .replace("&", "%26")
        .replace("?", "%3F")
        .replace("#", "%23")
        .replace("=", "%3D")
    )


def _youtube_search_url(*, name_en: str, cuisine: str) -> str:
    # We don't fetch videos at runtime; this provides a prebuilt link that the
    # client can open directly.
    q = _normalize_space(f"{name_en} {cuisine} recipe")
    return f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Build/validate SAVO recipe catalog")
    parser.add_argument("--in", dest="inputs", action="append", required=True, help="Input JSON file (array of recipes)")
    parser.add_argument("--out", dest="out", default=str(_repo_root() / "ALL_RECIPES_COMPLETE.json"))
    parser.add_argument("--target-count", type=int, default=1000)
    parser.add_argument("--video-map", dest="video_map", default=None, help="Optional CSV mapping to attach video_url")
    parser.add_argument(
        "--add-image-urls",
        action="store_true",
        help="Attach `image_urls` (3) using /recipes/image/proxy?seed=N",
    )
    parser.add_argument(
        "--allow-short",
        action="store_true",
        help="Allow outputs smaller than target-count (useful for testing)",
    )
    parser.add_argument(
        "--fill-missing-video-search",
        action="store_true",
        help="If a recipe has no video_url, set it to a YouTube search URL for the recipe name.",
    )

    args = parser.parse_args()

    target_count = int(args.target_count or 0)
    if target_count <= 0:
        raise ValueError("--target-count must be > 0")

    recipes_in: List[Dict[str, Any]] = []
    for p in args.inputs:
        path = Path(p)
        if not path.exists():
            raise FileNotFoundError(path)
        recipes_in.extend(_load_json_list(path))

    video_map: Dict[Tuple[str, str], str] = {}
    if args.video_map:
        vm_path = Path(args.video_map)
        if not vm_path.exists():
            raise FileNotFoundError(vm_path)
        video_map = _load_video_map_csv(vm_path)

    seen: set[Tuple[str, str]] = set()
    out: List[Dict[str, Any]] = []

    for recipe in recipes_in:
        if not isinstance(recipe, dict):
            continue

        _ensure_recipe_name_object(recipe)
        cuisine = _cuisine(recipe)
        name_en = _name_en(recipe)

        if not name_en:
            # Skip invalid entries rather than generating garbage.
            continue

        recipe.setdefault("cuisine", cuisine)
        recipe["cuisine"] = cuisine

        # Ensure recipe_id exists and is stable-ish.
        rid = str(recipe.get("recipe_id") or "").strip()
        if not rid:
            rid = _stable_recipe_id(name_en=name_en, cuisine=cuisine)
            recipe["recipe_id"] = rid

        # De-dupe by name+cuisine.
        key = _dedupe_key(recipe)
        if key in seen:
            continue
        seen.add(key)

        # Optional attachments.
        if video_map:
            by_name = video_map.get((_slug(name_en), _slug(cuisine)))
            by_id = video_map.get((f"__id__:{rid}", ""))
            vid = by_name or by_id
            if isinstance(vid, str) and vid.strip():
                recipe["video_url"] = vid.strip()

        if args.fill_missing_video_search and not (recipe.get("video_url") or "").strip():
            recipe["video_url"] = _youtube_search_url(name_en=name_en, cuisine=cuisine)

        if args.add_image_urls:
            recipe["image_urls"] = _build_image_urls(name_en=name_en, cuisine=cuisine, count=3)

        out.append(recipe)
        if len(out) >= target_count:
            break

    if not args.allow_short and len(out) < target_count:
        raise SystemExit(
            f"Not enough unique valid recipes to hit target-count={target_count}. Got {len(out)}. "
            "Provide more inputs or fix invalid entries."
        )

    out_path = Path(args.out)
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(out)} recipes -> {out_path}")
    if args.add_image_urls:
        print("Included image_urls (3) using /recipes/image/proxy?seed=N")
    if args.video_map:
        print(f"Attached video_url from {args.video_map}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
