from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional


def _snake_case(value: str) -> str:
    s = (value or "").strip().lower()
    s = s.replace("&", " and ")
    for ch in ["/", "-", ".", ",", "(", ")", "[", "]", "{", "}", ":", ";", "'", '"']:
        s = s.replace(ch, " ")
    s = "_".join(part for part in s.split() if part)
    while "__" in s:
        s = s.replace("__", "_")
    return s


@lru_cache(maxsize=1)
def _load_map() -> dict[str, str]:
    """Load canonical_name -> cuisine mapping.

    Best-effort: returns empty mapping if file missing.
    """
    here = Path(__file__).resolve()
    repo_root = here.parents[4]  # services/api/app/core -> repo root

    candidates = [
        repo_root / "docs" / "inventory_ingredient_map.v1.json",
    ]

    for path in candidates:
        try:
            if not path.exists():
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            items = payload.get("ingredients")
            if not isinstance(items, list):
                continue

            mapping: dict[str, str] = {}
            for row in items:
                if not isinstance(row, dict):
                    continue
                name = row.get("canonical_name")
                cuisine = row.get("cuisine")
                if not isinstance(name, str) or not name.strip():
                    continue
                if not isinstance(cuisine, str) or not cuisine.strip():
                    continue
                mapping[_snake_case(name)] = _snake_case(cuisine)
            return mapping
        except Exception:
            continue

    return {}


def lookup_cuisine(canonical_name: Optional[str], display_name: Optional[str] = None) -> Optional[str]:
    """Return a cuisine string if found (e.g., 'indian', 'italian')."""
    mapping = _load_map()
    if not mapping:
        return None

    key = _snake_case(canonical_name or "")
    if key and key in mapping:
        return mapping[key]

    key2 = _snake_case(display_name or "")
    if key2 and key2 in mapping:
        return mapping[key2]

    return None
