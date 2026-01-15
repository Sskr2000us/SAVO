"""Fetch recipes from open/free sources and export a dataset for SAVO.

This script is intentionally conservative:
- It only targets sources that *explicitly* allow redistribution or provide an open API.
- It does NOT scrape random recipe blogs (often copyrighted).

Default source: TheMealDB (public JSON API)
- Includes dish image URLs and often a YouTube link per recipe.

Output format:
- JSON array of objects with at least: recipe_name, cuisine
- Also includes: recipe_id, ingredients, instructions, image_url, video_url, source metadata

Then use:
  python services/api/scripts/build_recipe_catalog.py --in <out.json> --add-image-urls --target-count 1000

Example:
  python services/api/scripts/fetch_open_recipe_sources.py --source themealdb --limit 1000 --out data/recipes/themealdb_1000.json

Note:
- Always verify the source’s license/terms for your use case.
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx


THEMEALDB_BASE = "https://www.themealdb.com/api/json/v1/1"


def _repo_root() -> Path:
    # services/api/scripts/fetch_open_recipe_sources.py -> repo root is parents[3]
    return Path(__file__).resolve().parents[3]


def _safe_str(v: Any) -> str:
    s = "" if v is None else str(v)
    return s.strip()


def _sleep_backoff(attempt: int) -> None:
    # 0.25s, 0.5s, 1s, 2s, 4s (cap)
    delay = min(4.0, 0.25 * (2 ** max(0, attempt)))
    time.sleep(delay)


def _get_json(client: httpx.Client, url: str, *, attempts: int = 5) -> Dict[str, Any]:
    last_err: Optional[Exception] = None
    for i in range(attempts):
        try:
            r = client.get(url, headers={"Accept": "application/json"})
            r.raise_for_status()
            data = r.json()
            if not isinstance(data, dict):
                raise ValueError("Expected JSON object")
            return data
        except Exception as e:
            last_err = e
            _sleep_backoff(i)
    raise RuntimeError(f"Failed to fetch {url}: {last_err}")


def _themealdb_collect_meals(*, limit: int) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    timeout = httpx.Timeout(20.0, connect=10.0)
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        # TheMealDB doesn’t provide a single “list all” endpoint for free tier.
        # Best-effort approach: search by first letter a-z and merge results.
        for c in "abcdefghijklmnopqrstuvwxyz":
            url = f"{THEMEALDB_BASE}/search.php?f={c}"
            data = _get_json(client, url)
            meals = data.get("meals")
            if not isinstance(meals, list):
                continue

            for meal in meals:
                if not isinstance(meal, dict):
                    continue
                mid = _safe_str(meal.get("idMeal"))
                if not mid or mid in seen_ids:
                    continue
                seen_ids.add(mid)
                out.append(meal)
                if len(out) >= limit:
                    return out

    return out


def _themealdb_to_savo_recipe(meal: Dict[str, Any]) -> Dict[str, Any]:
    mid = _safe_str(meal.get("idMeal"))
    name = _safe_str(meal.get("strMeal"))
    area = _safe_str(meal.get("strArea")) or "general"
    category = _safe_str(meal.get("strCategory"))

    instructions_raw = _safe_str(meal.get("strInstructions"))
    instructions = [s.strip() for s in instructions_raw.replace("\r", "\n").split("\n") if s.strip()]

    # Ingredients/measures: TheMealDB uses strIngredient1..20 and strMeasure1..20
    ingredients: List[Dict[str, Any]] = []
    for i in range(1, 21):
        ing = _safe_str(meal.get(f"strIngredient{i}"))
        meas = _safe_str(meal.get(f"strMeasure{i}"))
        if not ing:
            continue
        ingredients.append(
            {
                "name": ing,
                "measure": meas,
            }
        )

    image_url = _safe_str(meal.get("strMealThumb"))
    video_url = _safe_str(meal.get("strYoutube"))

    # Minimal catalog-compatible object (works with build_recipe_catalog.py)
    # You can extend fields later; consumers should ignore unknown keys.
    out: Dict[str, Any] = {
        "recipe_id": f"themealdb:{mid}" if mid else "",
        "recipe_name": {"en": name},
        "cuisine": area,
        "cuisine_code": area.lower().replace(" ", "_"),
        "category": category,
        "language": "en",
        "difficulty": "easy",
        "servings": 4,
        "ingredients": ingredients,
        "instructions": instructions,
        "image_url": image_url,
        "video_url": video_url,
        "source": {
            "provider": "themealdb",
            "id": mid,
            "original": {
                "strSource": _safe_str(meal.get("strSource")),
                "strTags": _safe_str(meal.get("strTags")),
            },
        },
    }

    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch recipes from open/free sources")
    parser.add_argument("--source", default="themealdb", choices=["themealdb"])
    parser.add_argument("--limit", type=int, default=1000)
    parser.add_argument(
        "--out",
        default=str(_repo_root() / "data" / "recipes" / "themealdb_recipes.json"),
        help="Output JSON file path",
    )

    args = parser.parse_args()

    limit = int(args.limit or 0)
    if limit <= 0:
        raise ValueError("--limit must be > 0")

    if args.source == "themealdb":
        raw_meals = _themealdb_collect_meals(limit=limit)
        recipes = [_themealdb_to_savo_recipe(m) for m in raw_meals]
    else:
        raise ValueError(f"Unknown source: {args.source}")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(recipes, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Fetched {len(recipes)} recipes from {args.source} -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
