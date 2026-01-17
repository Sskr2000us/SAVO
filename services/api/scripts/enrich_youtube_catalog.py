"""Enrich YouTube catalog entries in ALL_RECIPES_COMPLETE.json.

This is an offline/batch helper (optional). It iterates over YouTube-backed recipes in
ALL_RECIPES_COMPLETE.json that lack structured ingredients/steps, calls the existing
YouTube transcript extraction pipeline, and writes a cached augmentation file:

  services/api/app/data/youtube_recipe_augmentations.json

The API can then merge these fields at request time, so YouTube recipes become usable
offline and matching works by ID.

Usage:
  python services/api/scripts/enrich_youtube_catalog.py --limit 25

Requires:
  - Working YouTube transcript access (youtube-transcript-api)
  - LLM credentials configured for the reasoning client
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

from app.core.llm_client import get_reasoning_client
from app.core.youtube_recipe_extraction import summarize_youtube_recipe


def _repo_root() -> Path:
    here = Path(__file__).resolve()
    # services/api/scripts -> repo root
    return here.parents[3]


def _catalog_path() -> Path:
    return _repo_root() / "ALL_RECIPES_COMPLETE.json"


def _augmentation_path() -> Path:
    # services/api/app/data
    here = Path(__file__).resolve()
    return here.parents[2] / "app" / "data" / "youtube_recipe_augmentations.json"


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _is_sparse(row: dict[str, Any]) -> bool:
    ing = row.get("ingredients")
    if isinstance(ing, list) and len([x for x in ing if x]) > 0:
        return False
    instr = row.get("instructions")
    if isinstance(instr, list):
        joined = " ".join([str(x) for x in instr if x is not None]).lower()
        if "watch" in joined and "video" in joined:
            return True
        if len([x for x in instr if str(x).strip()]) <= 1:
            return True
    if isinstance(instr, str):
        t = instr.lower()
        if "watch" in t and "video" in t:
            return True
    return True


def _youtube_video_id(recipe_id: str) -> str | None:
    rid = (recipe_id or "").strip()
    if rid.lower().startswith("youtube:"):
        vid = rid.split(":", 1)[1].strip()
        return vid if vid else None
    return None


async def _run(limit: int) -> int:
    catalog_path = _catalog_path()
    items = _load_json(catalog_path, [])
    if not isinstance(items, list):
        raise SystemExit(f"Catalog not found or invalid: {catalog_path}")

    aug_path = _augmentation_path()
    aug = _load_json(aug_path, {})
    if not isinstance(aug, dict):
        aug = {}

    llm_client = get_reasoning_client()

    count = 0
    for row in items:
        if limit and count >= limit:
            break
        if not isinstance(row, dict):
            continue
        rid = str(row.get("recipe_id") or "").strip()
        vid = _youtube_video_id(rid)
        if not vid:
            continue
        if not _is_sparse(row):
            continue
        if vid in aug:
            continue

        name_hint = ""
        rn = row.get("recipe_name")
        if isinstance(rn, dict):
            name_hint = str(rn.get("en") or "").strip()
        elif isinstance(rn, str):
            name_hint = rn.strip()
        if not name_hint:
            name_hint = rid

        summary = await summarize_youtube_recipe(
            video_id=vid,
            recipe_name=name_hint,
            output_language="en",
            transcript_language=None,
            llm_client=llm_client,
        )

        ingredients = summary.get("ingredients") if isinstance(summary, dict) else []
        steps = summary.get("steps") if isinstance(summary, dict) else []
        recipe_name_en = summary.get("recipe_name_en") if isinstance(summary, dict) else ""

        aug[vid] = {
            "recipe_name_en": recipe_name_en if isinstance(recipe_name_en, str) else "",
            "ingredients": ingredients if isinstance(ingredients, list) else [],
            "steps": steps if isinstance(steps, list) else [],
            "updated_at": "batch",
        }

        count += 1

    aug_path.parent.mkdir(parents=True, exist_ok=True)
    aug_path.write_text(json.dumps(aug, ensure_ascii=False, indent=2), encoding="utf-8")
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    args = parser.parse_args()

    n = asyncio.run(_run(int(args.limit)))
    print(f"Wrote {n} new YouTube augmentations to {_augmentation_path()}")


if __name__ == "__main__":
    main()
