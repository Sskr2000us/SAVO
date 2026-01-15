"""Recipe generation endpoints (constraints-first, pantry-aware).

Implements the minimum backend surface required by docs/recipe_generation_user_stories.md:
- Resolve intent into locked constraints
- Pantry coverage + explicit missing items
- Deterministic retrieve/assemble first; constrained LLM generation only if needed
- Safety validation and feedback event capture

Notes:
- This router is additive; it does not replace existing planning flows.
- Telemetry is best-effort via public.event_log.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import asyncio
import json
import os
import random
import re
from pathlib import Path
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple, Literal
from uuid import UUID, uuid4, uuid5

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user
from app.core.database import get_db_client, get_full_profile, get_inventory
from app.core.events import emit_event
from app.core.ingredient_normalization import get_normalizer
from app.core.safety_constraints import validate_recipe_safety
from app.core.safety_constraints import (
    build_allergen_constraints,
    build_religious_constraints,
    build_dietary_constraints,
)
from app.core.llm_client import get_reasoning_client
from app.core.llm_utils import generate_json_with_retries
from app.core.cultural_intelligence import build_cultural_intelligence_prompt
from app.core.ingredient_combinations import IngredientCombinationEngine
from app.core.media_storage import to_signed_url


router = APIRouter()


_CATALOG_CACHE: dict[str, Any] = {
    "path": None,
    "mtime": None,
    "loaded_at": None,
    "items": None,
}


def _find_catalog_path() -> Path:
    """Locate ALL_RECIPES_COMPLETE.json by walking up from this file."""

    start = Path(__file__).resolve()
    cur = start
    for _ in range(10):
        candidate = cur.parent / "ALL_RECIPES_COMPLETE.json"
        if candidate.exists():
            return candidate
        cur = cur.parent
    # Fallback: repo root relative to services/api/app/api/routes/recipe_generation.py
    return start.parents[5] / "ALL_RECIPES_COMPLETE.json"


def _load_catalog_items() -> list[dict[str, Any]]:
    """Load catalog file with a small in-process cache (best-effort)."""

    path = _find_catalog_path()
    if not path.exists():
        return []

    try:
        mtime = path.stat().st_mtime
    except Exception:
        mtime = None

    cached_items = _CATALOG_CACHE.get("items")
    if cached_items is not None and _CATALOG_CACHE.get("path") == str(path) and _CATALOG_CACHE.get("mtime") == mtime:
        return cached_items

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        items: list[dict[str, Any]] = [x for x in data if isinstance(x, dict)]
        _CATALOG_CACHE.update(
            {
                "path": str(path),
                "mtime": mtime,
                "loaded_at": datetime.now(timezone.utc).isoformat(),
                "items": items,
            }
        )
        return items
    except Exception:
        return []


def _build_image_urls(*, recipe_name: str, cuisine: str, count: int = 3) -> list[str]:
    name = (recipe_name or "").strip() or "recipe"
    c = (cuisine or "general").strip() or "general"
    urls: list[str] = []
    for seed in range(max(1, int(count))):
        urls.append(
            "/recipes/image/proxy"
            f"?recipe_name={urllib.parse.quote_plus(name)}"
            f"&cuisine={urllib.parse.quote_plus(c)}"
            f"&seed={seed}"
        )
    return urls


# Hard time budget for constrained generation. If exceeded, we fail closed to the
# deterministic assembled recipe (existing fallback behavior).
# Keep this relatively tight; long hangs are unacceptable UX.
_GENERATION_BUDGET_SECONDS = int((os.getenv("SAVO_RECIPE_GENERATION_BUDGET_SECONDS") or "16").strip() or "16")


_UUID_NAMESPACE = uuid5(UUID("00000000-0000-0000-0000-000000000000"), "savo-ingredient")


_CREATIVE_RECIPE_KEYWORDS = {
    "native",
    "cultural",
    "authentic",
    "traditional",
    "regional",
    "heritage",
    "innovative",
    "creative",
    "fusion",
    "street food",
}


def _wants_native_or_innovative_recipe(request_text: str | None) -> bool:
    text = (request_text or "").strip().lower()
    if not text:
        return False
    # Conservative substring matching (supports phrases like "native style" / "cultural recipe").
    return any(k in text for k in _CREATIVE_RECIPE_KEYWORDS)


def _pick_cultural_focus_ingredients(*, pantry_names: list[str], expiring: list[str]) -> list[str]:
    # Keep this very small to avoid bloating the prompt.
    # Prefer expiring items, then whatever appears early in pantry_names.
    chosen: list[str] = []
    seen: set[str] = set()

    def _add(name: str) -> None:
        nm = (name or "").strip().lower()
        if not nm or nm in seen:
            return
        seen.add(nm)
        chosen.append(nm)

    for n in (expiring or [])[:6]:
        _add(n)
    for n in (pantry_names or [])[:12]:
        _add(n)

    return chosen[:8]


def _best_effort_recent_recipe_avoid_list(*, user_id: str, limit: int = 18) -> Dict[str, List[str]]:
    """Return a small list of recent recipe names/ids to avoid repeating.

    Uses `recipe_attempts` as best-effort memory. Never raises.
    """

    try:
        db = get_db_client()
        res = (
            db.table("recipe_attempts")
            .select("recipe_id,recipe")
            .eq("user_id", str(user_id))
            .order("created_at", desc=True)
            .limit(min(int(limit), 40))
            .execute()
        )
        rows = res.data or []
    except Exception:
        rows = []

    names: list[str] = []
    ids: list[str] = []
    fingerprints: list[str] = []
    seen_names: set[str] = set()
    seen_ids: set[str] = set()
    seen_fps: set[str] = set()

    for r in rows:
        if not isinstance(r, dict):
            continue
        rid = (r.get("recipe_id") or "").strip()
        if rid and rid not in seen_ids:
            seen_ids.add(rid)
            ids.append(rid)

        rec = r.get("recipe")
        if isinstance(rec, dict):
            nm = (rec.get("recipe_name") or rec.get("name") or "").strip().lower()
            if nm and nm not in seen_names:
                seen_names.add(nm)
                names.append(nm)

            fp = _recipe_fingerprint_from_recipe_dict(rec)
            if fp and fp not in seen_fps:
                seen_fps.add(fp)
                fingerprints.append(fp)

        if len(names) >= int(limit) and len(ids) >= int(limit):
            break

    return {
        "recipe_names": names[: int(limit)],
        "recipe_ids": ids[: int(limit)],
        "recipe_fingerprints": fingerprints[: int(limit)],
    }


def _recipe_fingerprint_from_recipe_dict(recipe: Dict[str, Any]) -> str:
    """Best-effort stable signature used for anti-repeat.

    Intentionally coarse: cuisine + top non-optional ingredients + techniques.
    """

    if not isinstance(recipe, dict):
        return ""

    cuisine = str(recipe.get("cuisine") or "mixed").strip().lower() or "mixed"

    techniques_in = recipe.get("techniques") or []
    techniques: list[str] = []
    if isinstance(techniques_in, list):
        for t in techniques_in:
            s = str(t or "").strip().lower()
            if s and s not in techniques:
                techniques.append(s)
    techniques = sorted(techniques)[:3]

    mains: list[str] = []
    ing_in = recipe.get("ingredients") or []
    if isinstance(ing_in, list):
        for it in ing_in:
            if not isinstance(it, dict):
                continue
            if bool(it.get("optional")):
                continue
            nm = str(it.get("canonical_name") or "").strip().lower()
            if not nm:
                continue
            if nm not in mains:
                mains.append(nm)
            if len(mains) >= 4:
                break
    mains = sorted(mains)[:4]

    return f"{cuisine}|{','.join(techniques)}|{','.join(mains)}"


def _extract_request_ingredient_hints(
    request_text: str | None,
    pantry_names: list[str],
    *,
    limit: int = 4,
) -> list[str]:
    """Extract pantry ingredient mentions from request_text.

    Pantry names are normalized (often snake_case). We normalize request_text into a
    snake-ish token stream to allow matching "olive oil" -> "olive_oil".
    """

    text = (request_text or "").strip().lower()
    if not text:
        return []

    # Normalize free text into a token stream that supports underscore matching.
    token_stream = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    if not token_stream:
        return []

    hits_with_pos: list[tuple[int, str]] = []
    for nm in (pantry_names or [])[:250]:
        key = str(nm or "").strip().lower()
        if not key:
            continue
        # Match on underscore boundaries to reduce false positives.
        m = re.search(rf"(^|_){re.escape(key)}(_|$)", token_stream)
        if not m:
            continue
        hits_with_pos.append((int(m.start()), key))

    hits_with_pos.sort(key=lambda t: t[0])
    out: list[str] = []
    for _, h in hits_with_pos:
        if h in out:
            continue
        out.append(h)
        if len(out) >= int(limit):
            break
    return out


def _best_effort_recipe_image_url(
    *,
    pantry: list[dict[str, Any]],
    recipe: "CanonicalRecipe",
) -> Optional[str]:
    """Pick a representative image URL for a recipe from the user's pantry.

    Inventory items generally have image_url/image_ref pointing at Supabase Storage.
    We return a signed URL so the client can display it immediately.
    """

    if not isinstance(pantry, list):
        return None

    try:
        normalizer = get_normalizer()
    except Exception:
        normalizer = None

    id_to_image: dict[str, str] = {}
    for it in pantry:
        if not isinstance(it, dict):
            continue

        nm = (it.get("canonical_name") or it.get("name") or "").strip()
        if not nm:
            continue

        canon = normalizer.normalize_name(nm) if normalizer is not None else nm.strip().lower()
        iid = _stable_ingredient_uuid(canon)

        raw = it.get("image_ref") or it.get("image_url") or it.get("image")
        raw_s = str(raw or "").strip()
        if not raw_s:
            continue

        signed = to_signed_url(raw_s, expires_in=3600) or raw_s
        signed_s = str(signed or "").strip()
        if signed_s:
            id_to_image[iid] = signed_s

    if not id_to_image:
        return None

    try:
        # Prefer the first non-optional ingredient with an image.
        for ing in (recipe.ingredients or []):
            if bool(getattr(ing, "optional", False)):
                continue
            iid = str(getattr(ing, "ingredient_id", "")).strip()
            if iid and id_to_image.get(iid):
                return id_to_image[iid]

        # Otherwise any ingredient image.
        for ing in (recipe.ingredients or []):
            iid = str(getattr(ing, "ingredient_id", "")).strip()
            if iid and id_to_image.get(iid):
                return id_to_image[iid]
    except Exception:
        return None

    return None


def _pick_option_focus_pairs(
    *,
    pantry_context: list[dict[str, Any]],
    profile: dict[str, Any],
    count: int,
    prefer_expiring: list[str],
) -> list[dict[str, Any]]:
    """Pick per-option "main ingredient" pairs.

    Goal: ensure the LLM has concrete anchors so it doesn't keep producing the
    same generic dish. Best-effort; never raises.
    """

    # Start from pantry_context because it's already sorted by expiry/quantity.
    names: list[str] = []
    ids_by_name: dict[str, str] = {}
    for row in pantry_context or []:
        if not isinstance(row, dict):
            continue
        nm = (row.get("canonical_name") or "").strip().lower()
        if not nm:
            continue
        if nm in ids_by_name:
            continue
        names.append(nm)
        ids_by_name[nm] = str(row.get("ingredient_id") or _stable_ingredient_uuid(nm))
        if len(names) >= 28:
            break

    # If pantry_context is empty, we fall back to prefer_expiring (names only).
    if not names:
        for n in (prefer_expiring or [])[:20]:
            nm = (n or "").strip().lower()
            if not nm or nm in ids_by_name:
                continue
            names.append(nm)
            ids_by_name[nm] = _stable_ingredient_uuid(nm)

    if len(names) < 2:
        return []

    engine = IngredientCombinationEngine()
    expiring_set = set([(x or "").strip().lower() for x in (prefer_expiring or []) if str(x or "").strip()])
    rng = random.Random(str(uuid4()))

    def _cat(name: str):
        try:
            prof = engine.get_ingredient_profile(name)
            return getattr(prof, "category", None)
        except Exception:
            return None

    # Score all pairs among our candidate set.
    candidates = list(names)
    pair_scores: list[tuple[float, tuple[str, str]]] = []

    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a = candidates[i]
            b = candidates[j]
            analysis = engine.analyze_combination([a, b], profile if isinstance(profile, dict) else {})
            viable = bool(analysis.get("is_viable"))
            synergy = float(analysis.get("synergy_score") or 0.0)
            if not viable and synergy < 0.20:
                continue

            ca = _cat(a)
            cb = _cat(b)
            score = synergy

            # Prefer "main ingredient" categories.
            try:
                low_value = {"spice", "herb", "acid", "fat", "sweetener"}
                if ca is not None and str(getattr(ca, "value", ca)).lower() in low_value:
                    score -= 0.35
                if cb is not None and str(getattr(cb, "value", cb)).lower() in low_value:
                    score -= 0.35
            except Exception:
                pass

            # Prefer protein/legume + veg, then veg + starch/grain.
            def _is(cat, nameset: set[str]) -> bool:
                if cat is None:
                    return False
                v = str(getattr(cat, "value", cat)).lower()
                return v in nameset

            is_protein_like_a = _is(ca, {"protein", "legume"})
            is_protein_like_b = _is(cb, {"protein", "legume"})
            is_veg_a = _is(ca, {"vegetable"})
            is_veg_b = _is(cb, {"vegetable"})
            is_starch_like_a = _is(ca, {"starch", "grain"})
            is_starch_like_b = _is(cb, {"starch", "grain"})

            if (is_protein_like_a and is_veg_b) or (is_protein_like_b and is_veg_a):
                score += 0.45
            elif (is_veg_a and is_starch_like_b) or (is_veg_b and is_starch_like_a):
                score += 0.35
            elif (is_protein_like_a and is_starch_like_b) or (is_protein_like_b and is_starch_like_a):
                score += 0.25
            elif ca is not None and cb is not None and str(getattr(ca, "value", ca)) != str(getattr(cb, "value", cb)):
                score += 0.12

            # Prefer expiring ingredients as anchors.
            if a in expiring_set:
                score += 0.18
            if b in expiring_set:
                score += 0.18

            # Tiny jitter to avoid deterministically picking the same pairs.
            score += rng.random() * 0.03
            pair_scores.append((score, (a, b)))

    pair_scores.sort(key=lambda t: t[0], reverse=True)

    picked: list[tuple[str, str]] = []
    usage: dict[str, int] = {}
    max_per_ingredient = 2

    for _, (a, b) in pair_scores:
        if len(picked) >= int(count):
            break
        ua = int(usage.get(a, 0))
        ub = int(usage.get(b, 0))
        if ua >= max_per_ingredient or ub >= max_per_ingredient:
            continue
        pair = tuple(sorted((a, b)))
        if pair in picked:
            continue
        picked.append(pair)
        usage[a] = ua + 1
        usage[b] = ub + 1

    # If we still don't have enough (e.g., tiny pantry), fill with any remaining distinct pairs.
    if len(picked) < int(count):
        for _, (a, b) in pair_scores:
            if len(picked) >= int(count):
                break
            pair = tuple(sorted((a, b)))
            if pair in picked:
                continue
            picked.append(pair)

    out: list[dict[str, Any]] = []
    for idx, (a, b) in enumerate(picked[: int(count)]):
        out.append(
            {
                "option_index": idx + 1,
                "main_ingredients": [a, b],
                "main_ingredient_ids": [ids_by_name.get(a) or _stable_ingredient_uuid(a), ids_by_name.get(b) or _stable_ingredient_uuid(b)],
            }
        )
    return out


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_ingredient_uuid(name: str) -> str:
    nm = (name or "").strip().lower()
    if not nm:
        return str(uuid4())
    return str(uuid5(_UUID_NAMESPACE, nm))


def _clean_tag(s: str) -> str:
    return (s or "").strip().lower().replace(" ", "_")


class LockedConstraints(BaseModel):
    cuisine: Optional[str] = None
    ingredients_allowed: List[str] = Field(default_factory=list)
    max_time_minutes: Optional[int] = None
    dietary: List[str] = Field(default_factory=list)
    techniques_allowed: List[str] = Field(default_factory=list)
    use_expiring_items: bool = False
    spice_level: Optional[str] = None


class RecipeGenerateRequest(BaseModel):
    request_text: Optional[str] = Field(default=None, description="Free-form user request")
    meal_type: Optional[Literal["breakfast", "lunch", "dinner", "snack", "any"]] = Field(
        default=None,
        description="Optional meal context hint for retrieval/generation.",
    )
    day_type: Optional[Literal["weekday", "weekend", "holiday"]] = Field(
        default=None,
        description="Optional day context hint for retrieval/generation.",
    )
    cuisine: Optional[str] = Field(default=None)
    dietary_tags: List[str] = Field(default_factory=list)
    max_time_minutes: Optional[int] = Field(default=None, ge=1, le=240)
    serves: int = Field(default=2, ge=1, le=12)
    include_inactive_inventory: bool = Field(default=False)
    use_expiring_items: bool = Field(default=False)
    spice_level: Optional[str] = Field(default=None)
    # Optional override: provide inventory explicitly (e.g. from a scan/selection flow)
    # to avoid a DB round-trip and to support "inventory-first" generation.
    # Supported shapes:
    # - {"available_ingredients": ["tomato", "onion"]}
    # - {"items": [{"canonical_name": "tomato"}, ...]}
    inventory: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional inventory override: {'available_ingredients': [...]} or {'items': [...]}.",
    )
    available_ingredients: List[str] = Field(
        default_factory=list,
        description="Optional convenience list of ingredient names (same as inventory.available_ingredients).",
    )
    allow_generation: bool = Field(
        default=True,
        description="If false, never call the LLM; only retrieved/assembled recipes are returned.",
    )
    request_text_forces_generation: bool = Field(
        default=True,
        description="If true, request_text will prefer LLM generation even if pantry coverage is high.",
    )
    output_language: Optional[str] = Field(
        default=None,
        description="Preferred output language (BCP-47-ish, e.g. 'en', 'hi', 'te'). Used for best-effort bilingual fields.",
    )
    output_languages: List[str] = Field(
        default_factory=list,
        description="Optional list of output languages. If provided, backend may include best-effort bilingual fields.",
    )
    creativity: Optional[Literal["standard", "high"]] = Field(
        default=None,
        description="Optional creativity level. 'high' forces LLM generation for more native/innovative recipes.",
    )


class RecipeGenerateOptionsRequest(RecipeGenerateRequest):
    count: int = Field(
        default=5,
        ge=1,
        le=8,
        description="Number of recipe options to return in a single call.",
    )


class CanonicalIngredient(BaseModel):
    canonical_name: str
    ingredient_id: str
    quantity: float
    unit: str
    optional: bool = False


class CanonicalRecipe(BaseModel):
    recipe_id: str
    recipe_name: str
    image_url: Optional[str] = None
    image_urls: List[str] = Field(default_factory=list)
    short_description: Optional[str] = None
    cuisine: str
    dietary_tags: List[str]
    prep_time_minutes: int
    difficulty: str
    ingredients: List[CanonicalIngredient]
    techniques: List[str]
    steps: List[str]
    serves: int
    chef_tips: List[str] = Field(default_factory=list)
    serving_suggestions: List[str] = Field(default_factory=list)
    cultural_context: Optional[Dict[str, Any]] = None
    created_from: str
    version: str = "v1"


class MissingIngredient(BaseModel):
    canonical_name: str
    quantity: float = 1
    unit: str = "pieces"


class TrustSignals(BaseModel):
    uses_what_you_have: bool
    estimated_time_minutes: int
    uses_expiring_items: bool
    adjustable_spice_level: bool = True


class RecipeI18n(BaseModel):
    recipe_name: Dict[str, str] = Field(default_factory=dict)
    steps: List[Dict[str, str]] = Field(default_factory=list)


class RecipeGenerateResponse(BaseModel):
    success: bool = True
    recipe: CanonicalRecipe
    locked_constraints: LockedConstraints
    pantry_coverage: float
    missing_ingredients: List[MissingIngredient] = Field(default_factory=list)
    mode: str
    reason: str
    trust_signals: TrustSignals
    i18n: Optional[RecipeI18n] = None


def _normalize_language_code(code: str | None) -> str:
    c = (code or "").strip().lower()
    if not c:
        return ""
    # Preserve simple BCP-47-ish tags but normalize case.
    return c


def _requested_translation_target(req: RecipeGenerateRequest) -> str:
    langs: list[str] = []
    if isinstance(getattr(req, "output_languages", None), list):
        langs.extend([_normalize_language_code(x) for x in (req.output_languages or [])])
    if isinstance(getattr(req, "output_language", None), str):
        langs.append(_normalize_language_code(req.output_language))

    # De-dupe while preserving order.
    seen: set[str] = set()
    ordered: list[str] = []
    for l in langs:
        if not l or l in seen:
            continue
        seen.add(l)
        ordered.append(l)

    for l in ordered:
        if l and l != "en":
            return l
    return ""


async def _translate_canonical_recipe_i18n(
    *,
    recipe: CanonicalRecipe,
    target_language: str,
    include_steps: bool,
) -> Optional[RecipeI18n]:
    target = _normalize_language_code(target_language)
    if not target or target == "en":
        return None

    base = RecipeI18n(
        recipe_name={"en": recipe.recipe_name},
        steps=[{"en": s} for s in (recipe.steps or [])],
    )

    schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "recipe_name": {"type": "string"},
        },
        "required": ["recipe_name"],
        "additionalProperties": False,
    }
    if include_steps:
        schema["properties"]["steps"] = {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
            "maxItems": 12,
        }
        schema["required"].append("steps")

    try:
        client = get_reasoning_client()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=(
                "Recipe generation provider is not configured correctly. "
                f"Reasoning provider error: {e}"
            ),
        )
    prompt = {
        "target_language": target,
        "source_language": "en",
        "recipe_name": recipe.recipe_name,
        "steps": recipe.steps if include_steps else [],
        "rules": [
            "keep_measurements_numbers_units_same",
            "do_not_translate_proper_nouns_or_brand_names",
            "keep_ingredient_names_as_common_local_terms_when_possible",
            "do_not_add_or_remove_steps",
        ],
    }

    try:
        translated = await asyncio.wait_for(
            generate_json_with_retries(
                client=client,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You translate recipe text. "
                            "Return JSON only matching the schema. "
                            "Do not change meaning, quantities, or step count."
                        ),
                    },
                    {"role": "user", "content": str(prompt)},
                ],
                schema=schema,
                max_attempts=1,
            ),
            timeout=9,
        )
    except Exception:
        return base

    try:
        if isinstance(translated, dict):
            t_name = (translated.get("recipe_name") or "").strip()
            if t_name:
                base.recipe_name[target] = t_name
            if include_steps:
                t_steps = translated.get("steps")
                if isinstance(t_steps, list):
                    for i, s in enumerate(t_steps):
                        if i >= len(base.steps):
                            break
                        line = (str(s) if s is not None else "").strip()
                        if line:
                            base.steps[i][target] = line
    except Exception:
        return base

    return base


async def _translate_canonical_recipes_batch_i18n(
    *,
    recipes: list[CanonicalRecipe],
    target_language: str,
) -> list[Optional[RecipeI18n]]:
    target = _normalize_language_code(target_language)
    if not target or target == "en" or not recipes:
        return [None for _ in recipes]

    bases: list[RecipeI18n] = [
        RecipeI18n(
            recipe_name={"en": r.recipe_name},
            steps=[{"en": s} for s in (r.steps or [])],
        )
        for r in recipes
    ]

    schema: Dict[str, Any] = {
        "type": "object",
        "properties": {
            "translations": {
                "type": "array",
                "minItems": len(recipes),
                "maxItems": len(recipes),
                "items": {
                    "type": "object",
                    "properties": {
                        "recipe_name": {"type": "string"},
                        "steps": {"type": "array", "items": {"type": "string"}, "minItems": 1, "maxItems": 12},
                    },
                    "required": ["recipe_name", "steps"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["translations"],
        "additionalProperties": False,
    }

    try:
        client = get_reasoning_client()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=(
                "Recipe generation provider is not configured correctly. "
                f"Reasoning provider error: {e}"
            ),
        )
    prompt = {
        "target_language": target,
        "source_language": "en",
        "recipes": [
            {
                "recipe_name": r.recipe_name,
                "steps": r.steps,
            }
            for r in recipes
        ],
        "rules": [
            "keep_measurements_numbers_units_same",
            "do_not_translate_proper_nouns_or_brand_names",
            "do_not_add_or_remove_steps",
        ],
    }

    try:
        translated = await asyncio.wait_for(
            generate_json_with_retries(
                client=client,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Translate each recipe_name and steps into target_language. "
                            "Return JSON only matching the schema."
                        ),
                    },
                    {"role": "user", "content": str(prompt)},
                ],
                schema=schema,
                max_attempts=1,
            ),
            timeout=11,
        )
    except Exception:
        return bases

    try:
        rows = translated.get("translations") if isinstance(translated, dict) else None
        if not isinstance(rows, list):
            return bases

        for idx, row in enumerate(rows):
            if idx >= len(bases) or not isinstance(row, dict):
                continue
            t_name = (row.get("recipe_name") or "").strip()
            if t_name:
                bases[idx].recipe_name[target] = t_name
            t_steps = row.get("steps")
            if isinstance(t_steps, list):
                for i, s in enumerate(t_steps):
                    if i >= len(bases[idx].steps):
                        break
                    line = (str(s) if s is not None else "").strip()
                    if line:
                        bases[idx].steps[i][target] = line
    except Exception:
        return bases

    return bases


class RecipeGenerateOptionsResponse(BaseModel):
    success: bool = True
    options: List[RecipeGenerateResponse] = Field(default_factory=list)


class RecipeAttemptRecord(BaseModel):
    id: str
    recipe_id: str
    mode: str
    reason: str
    pantry_coverage: float
    missing_ingredients: List[MissingIngredient] = Field(default_factory=list)
    saved: bool = False
    created_at: Optional[str] = None
    recipe: CanonicalRecipe


class RecipeAttemptListResponse(BaseModel):
    attempts: List[RecipeAttemptRecord]


class SaveAttemptResponse(BaseModel):
    success: bool = True


class CreateMealPlanRequest(BaseModel):
    plan_type: str = Field(description="daily|weekly|party")
    plan_date: date
    meal_type: Optional[str] = Field(default=None, description="breakfast|lunch|dinner|snack|any")
    servings: int = Field(default=4, ge=1, le=20)
    selected_cuisine: Optional[str] = None
    attempt_ids: List[str] = Field(default_factory=list, description="List of recipe_attempts.id")
    selected_attempt_id: Optional[str] = None


class CreateMealPlanResponse(BaseModel):
    success: bool = True
    plan_id: str
    shopping_list: List[MissingIngredient] = Field(default_factory=list)


class RecipeFeedbackRequest(BaseModel):
    recipe_id: str
    event: str = Field(..., description="recipe.accepted|recipe.modified|recipe.rejected")
    signals: Dict[str, Any] = Field(default_factory=dict)


def _resolve_intent_to_constraints(req: RecipeGenerateRequest) -> LockedConstraints:
    # Minimal, deterministic resolver (no LLM). If fields are missing, use conservative heuristics.
    text = (req.request_text or "").lower()

    cuisine = (req.cuisine or "").strip().lower() or None
    if not cuisine:
        if "italian" in text:
            cuisine = "italian"
        elif "indian" in text:
            cuisine = "indian"
        elif "mexican" in text:
            cuisine = "mexican"

    max_time = req.max_time_minutes
    if max_time is None:
        if "quick" in text or "fast" in text or "under 20" in text:
            max_time = 20
        elif "under 30" in text:
            max_time = 30

    dietary = [_clean_tag(t) for t in (req.dietary_tags or []) if _clean_tag(t)]
    if "vegan" in text and "vegan" not in dietary:
        dietary.append("vegan")
    if "vegetarian" in text and "vegetarian" not in dietary:
        dietary.append("vegetarian")

    use_expiring = bool(req.use_expiring_items or ("expiring" in text) or ("use expiring" in text))

    techniques: List[str] = []
    if cuisine == "italian":
        techniques = ["saute", "simmer"]
    elif cuisine == "indian":
        techniques = ["temper", "simmer"]

    return LockedConstraints(
        cuisine=cuisine,
        max_time_minutes=max_time,
        dietary=dietary,
        use_expiring_items=use_expiring,
        spice_level=(req.spice_level or None),
        techniques_allowed=techniques,
        ingredients_allowed=[],
    )


def _ingredient_id_map(names: List[str]) -> Dict[str, str]:
    """Return {ingredient_id: canonical_name} for stable pantry ingredient ids."""
    out: Dict[str, str] = {}
    for nm in names or []:
        if not nm:
            continue
        out[_stable_ingredient_uuid(nm)] = nm
    return out


def _suggest_missing_candidates(*, pantry_names: List[str], cuisine: Optional[str]) -> List[str]:
    """Deterministic missing candidates to explicitly label if not in pantry."""
    pantry_set = set(pantry_names or [])
    candidates: List[str] = []
    if cuisine == "italian":
        candidates = ["olive_oil", "garlic", "tomato", "basil"]
    elif cuisine == "indian":
        candidates = ["onion", "tomato", "cumin", "turmeric"]
    elif cuisine == "mexican":
        candidates = ["onion", "tomato", "lime", "cilantro"]
    else:
        candidates = []
    # Only return those missing from pantry.
    return [c for c in candidates if c not in pantry_set]


def _extract_pantry_names(pantry: List[Dict[str, Any]]) -> List[str]:
    normalizer = get_normalizer()
    out: List[str] = []
    for it in pantry or []:
        if not isinstance(it, dict):
            continue
        nm = (it.get("canonical_name") or it.get("name") or "").strip()
        if not nm:
            continue
        out.append(normalizer.normalize_name(nm))
    # stable order for determinism
    return sorted({x for x in out if x})


def _extract_inventory_override_names(req: RecipeGenerateRequest) -> List[str]:
    """Extract an explicit inventory list from the request (if provided).

    Returns a normalized, de-duped, sorted list of ingredient canonical names.
    """

    normalizer = get_normalizer()
    raw: list[str] = []

    if isinstance(getattr(req, "available_ingredients", None), list) and req.available_ingredients:
        for x in req.available_ingredients:
            if isinstance(x, str) and x.strip():
                raw.append(x.strip())

    inv = getattr(req, "inventory", None)
    if isinstance(inv, dict):
        avail = inv.get("available_ingredients")
        if isinstance(avail, list):
            for x in avail:
                if isinstance(x, str) and x.strip():
                    raw.append(x.strip())

        items = inv.get("items")
        if isinstance(items, list):
            for it in items:
                if not isinstance(it, dict):
                    continue
                nm = (it.get("canonical_name") or it.get("display_name") or it.get("name") or "").strip()
                if nm:
                    raw.append(nm)

    out = [normalizer.normalize_name(x) for x in raw if isinstance(x, str) and x.strip()]
    return sorted({x for x in out if x})


def _find_expiring_items(pantry: List[Dict[str, Any]], within_days: int = 3) -> List[str]:
    # Best-effort: relies on an optional `expiry_date` column.
    out: List[str] = []
    now = datetime.now(timezone.utc)
    normalizer = get_normalizer()
    for it in pantry or []:
        if not isinstance(it, dict):
            continue
        exp = it.get("expiry_date") or it.get("expiry")
        if not exp:
            continue
        try:
            dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            if dt <= now:
                nm = (it.get("canonical_name") or "").strip()
                if nm:
                    out.append(normalizer.normalize_name(nm))
            else:
                delta_days = (dt - now).total_seconds() / 86400.0
                if delta_days <= float(within_days):
                    nm = (it.get("canonical_name") or "").strip()
                    if nm:
                        out.append(normalizer.normalize_name(nm))
        except Exception:
            continue
    return sorted({x for x in out if x})


def _build_image_signals(pantry: List[Dict[str, Any]], limit: int = 40) -> List[Dict[str, Any]]:
    """Compact, no-raw-image signals to improve recipe realism.

    Avoid sending signed URLs; only send booleans + a few product fields.
    """

    if not isinstance(pantry, list):
        return []

    normalizer = get_normalizer()
    out: List[Dict[str, Any]] = []

    # get_inventory() already orders by updated_at desc; we keep that bias.
    for it in pantry[: int(limit) * 3]:
        if not isinstance(it, dict):
            continue

        nm = (it.get("canonical_name") or it.get("name") or "").strip()
        if not nm:
            continue

        canon = normalizer.normalize_name(nm)
        image_present = bool(it.get("image_url"))
        barcode_present = bool(it.get("barcode"))

        # Keep prompt lean: only include rows with some signal.
        if not image_present and not barcode_present:
            continue

        row: Dict[str, Any] = {
            "canonical_name": canon,
            "ingredient_id": _stable_ingredient_uuid(canon),
            "image_present": image_present,
            "barcode_present": barcode_present,
        }
        if barcode_present:
            if it.get("product_name"):
                row["product_name"] = it.get("product_name")
            if it.get("brand"):
                row["brand"] = it.get("brand")
            if it.get("package_size_text"):
                row["package_size_text"] = it.get("package_size_text")
        if it.get("updated_at"):
            row["last_seen_at"] = it.get("updated_at")

        out.append(row)
        if len(out) >= int(limit):
            break

    return out


def _combine_missing_ingredients(missing_lists: List[List[MissingIngredient]]) -> List[MissingIngredient]:
    """Best-effort consolidation for plan-level shopping list."""
    acc: Dict[Tuple[str, str], float] = {}
    for lst in missing_lists or []:
        for m in lst or []:
            try:
                key = (str(m.canonical_name or "missing_ingredient"), str(m.unit or "pieces"))
                acc[key] = float(acc.get(key, 0.0)) + float(m.quantity or 0.0)
            except Exception:
                continue
    out: List[MissingIngredient] = []
    for (nm, unit), qty in sorted(acc.items(), key=lambda x: x[0][0]):
        out.append(MissingIngredient(canonical_name=nm, quantity=float(qty), unit=unit))
    return out


def _best_effort_persist_recipe_attempt(*, user_id: str, attempt_id: str, payload: Dict[str, Any]) -> None:
    """Persist attempt for later saving/planning. Never fails the request."""
    try:
        db = get_db_client()
        row = dict(payload or {})
        row["id"] = attempt_id
        row["user_id"] = user_id
        # Drop None to reduce schema mismatch risk during rollout.
        row = {k: v for k, v in row.items() if v is not None}
        db.table("recipe_attempts").insert(row).execute()
    except Exception:
        return


def _compact_family_profile(profile: Dict[str, Any]) -> Dict[str, Any]:
    """Reduce profile payload to the fields most relevant for cooking constraints.

    `get_full_profile()` can return a rich object; we keep this small and stable.
    """

    if not isinstance(profile, dict):
        return {}

    out: Dict[str, Any] = {}

    members_in = profile.get("members")
    if isinstance(members_in, list):
        members_out: List[Dict[str, Any]] = []
        for m in members_in[:10]:
            if not isinstance(m, dict):
                continue
            members_out.append(
                {
                    "name": m.get("name"),
                    "age": m.get("age"),
                    "dietary_restrictions": m.get("dietary_restrictions", []),
                    "allergens": m.get("allergens", []),
                    "likes": m.get("likes", []),
                    "dislikes": m.get("dislikes", []),
                    "preferred_cuisines": m.get("preferred_cuisines") or m.get("cuisine_preferences"),
                }
            )
        if members_out:
            out["members"] = members_out

    # Capture a few commonly used top-level preference keys if present.
    for k in (
        "household_name",
        "region",
        "country",
        "primary_cuisines",
        "cuisine_preferences",
        "dietary_tags",
        "notes",
    ):
        if k in profile:
            out[k] = profile.get(k)

    return out


def _extract_pantry_context(
    pantry: List[Dict[str, Any]],
    limit: int = 80,
    *,
    prefer_expiring_items: bool = False,
    expiring_names: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Provide richer pantry context to the LLM (quantities/expiry) without huge tokens."""

    def _parse_iso_date(value: Any) -> Optional[date]:
        if value is None:
            return None
        s = str(value).strip()
        if not s:
            return None
        try:
            # Common Supabase/Postgres formats: YYYY-MM-DD or ISO datetime.
            return date.fromisoformat(s[:10])
        except Exception:
            return None

    def _parse_quantity_num(value: Any) -> Optional[float]:
        if value is None:
            return None
        if isinstance(value, (int, float)):
            try:
                return float(value)
            except Exception:
                return None
        s = str(value).strip()
        if not s:
            return None
        m = re.search(r"[-+]?\d*\.?\d+", s)
        if not m:
            return None
        try:
            return float(m.group(0))
        except Exception:
            return None

    if not isinstance(pantry, list):
        return []

    normalizer = get_normalizer()
    today = date.today()
    expiring_set = set(expiring_names or [])
    rows_with_keys: List[Tuple[Tuple[int, float, str], Dict[str, Any]]] = []

    for it in pantry:
        if not isinstance(it, dict):
            continue

        nm = (it.get("canonical_name") or it.get("name") or "").strip()
        if not nm:
            continue

        canon = normalizer.normalize_name(nm)
        qty = it.get("quantity")
        if qty is None:
            qty = it.get("amount")
        unit = it.get("unit")
        exp = it.get("expiry_date") or it.get("expiry")
        loc = it.get("location") or it.get("location_hint")

        exp_d = _parse_iso_date(exp)
        exp_days = (exp_d - today).days if exp_d else 10**9
        qty_num = _parse_quantity_num(qty) or 0.0

        row: Dict[str, Any] = {
            "canonical_name": canon,
            "ingredient_id": _stable_ingredient_uuid(canon),
        }
        if qty is not None:
            row["quantity"] = qty
        if unit is not None and str(unit).strip() != "":
            row["unit"] = str(unit).strip()
        if exp is not None and str(exp).strip() != "":
            row["expiry_date"] = str(exp).strip()
        if loc is not None and str(loc).strip() != "":
            row["location"] = str(loc).strip()

        # Ranking: soonest expiry first; higher quantity first; stable by name.
        expiring_bucket = 0 if (prefer_expiring_items and canon in expiring_set) else 1
        rows_with_keys.append(((expiring_bucket, exp_days, -qty_num, canon), row))

    rows_with_keys.sort(key=lambda t: t[0])
    return [row for _, row in rows_with_keys[: int(limit)]]


def _pantry_coverage(*, pantry_names: List[str], ingredient_names: List[str]) -> Tuple[float, List[str]]:
    pantry_set = set(pantry_names or [])
    required = [x for x in ingredient_names if x]
    if not required:
        return 0.0, []
    missing = [x for x in required if x not in pantry_set]
    covered = len(required) - len(missing)
    return float(covered) / float(len(required)), missing


def _pantry_coverage_by_id(
    *,
    pantry_id_to_name: Dict[str, str],
    ingredient_ids: List[str],
    id_to_name_hint: Optional[Dict[str, str]] = None,
) -> Tuple[float, List[MissingIngredient]]:
    pantry_ids = set((pantry_id_to_name or {}).keys())
    req = [str(x) for x in (ingredient_ids or []) if str(x).strip()]
    if not req:
        return 0.0, []
    missing_ids = [x for x in req if x not in pantry_ids]
    covered = len(req) - len(missing_ids)
    coverage = float(covered) / float(len(req))

    hint = id_to_name_hint or {}
    missing_items: List[MissingIngredient] = []
    for mid in missing_ids:
        nm = hint.get(mid) or "missing_ingredient"
        missing_items.append(MissingIngredient(canonical_name=nm, quantity=1, unit="pieces"))
    return coverage, missing_items


def _try_retrieve_recipe(
    *,
    user_id: str,
    constraints: LockedConstraints,
    pantry_names: List[str],
    serves: int,
    seed: Optional[str] = None,
) -> Optional[Tuple[CanonicalRecipe, float, List[MissingIngredient]]]:
    """Best-effort recipe retrieval from the `recipes` table (if present)."""
    cuisine = (constraints.cuisine or "").strip().lower()
    db = get_db_client()
    normalizer = get_normalizer()

    try:
        q = db.table("recipes").select("id,name,cuisine,prep_time_minutes,difficulty,serves,recipe_ingredients(ingredient_name,quantity,unit)")
        if cuisine:
            # Support either exact match or partial match.
            q = q.ilike("cuisine", f"%{cuisine}%")
        res = q.limit(25).execute()
        rows = res.data or []
    except Exception:
        return None

    candidates: List[Tuple[float, CanonicalRecipe, float, List[MissingIngredient]]] = []

    for r in rows:
        if not isinstance(r, dict):
            continue
        rid = str(r.get("id") or "").strip()
        if not rid:
            continue
        name = str(r.get("name") or "Recipe").strip() or "Recipe"
        rcuisine = str(r.get("cuisine") or cuisine or "mixed").strip().lower() or "mixed"
        try:
            prep_time = int(r.get("prep_time_minutes") or 30)
        except Exception:
            prep_time = 30
        difficulty = str(r.get("difficulty") or "easy").strip().lower() or "easy"

        ing_rows = r.get("recipe_ingredients") or []
        ing_names: List[str] = []
        ingredients: List[CanonicalIngredient] = []
        if isinstance(ing_rows, list):
            for ing in ing_rows:
                if not isinstance(ing, dict):
                    continue
                nm = (ing.get("ingredient_name") or "").strip()
                if not nm:
                    continue
                canon = normalizer.normalize_name(nm)
                ing_names.append(canon)
                try:
                    qty = float(ing.get("quantity") or 1)
                except Exception:
                    qty = 1.0
                unit = str(ing.get("unit") or "pieces")
                ingredients.append(
                    CanonicalIngredient(
                        canonical_name=canon,
                        ingredient_id=_stable_ingredient_uuid(canon),
                        quantity=qty,
                        unit=unit,
                        optional=False,
                    )
                )

        cov, missing_names = _pantry_coverage(pantry_names=pantry_names, ingredient_names=ing_names)
        missing_items = [MissingIngredient(canonical_name=m) for m in missing_names]

        recipe = CanonicalRecipe(
            recipe_id=rid,
            recipe_name=name,
            cuisine=rcuisine,
            dietary_tags=list(constraints.dietary or []),
            prep_time_minutes=int(prep_time),
            difficulty=difficulty if difficulty in {"easy", "medium", "hard"} else "easy",
            ingredients=ingredients,
            techniques=list(constraints.techniques_allowed or []),
            steps=["Follow the recipe instructions."],
            serves=int(serves),
            created_from="retrieved",
            version="v1",
        )

        # Simple rank: pantry coverage dominates.
        score = float(cov or 0.0)
        candidates.append((score, recipe, float(cov or 0.0), missing_items))

    if not candidates:
        return None

    # Avoid the appearance of "hard caching": if multiple recipes tie for best pantry
    # coverage (very common when the pantry is large), do NOT always return the first.
    candidates.sort(key=lambda t: t[0], reverse=True)
    best_score = float(candidates[0][0])
    eps = 1e-9
    tied = [c for c in candidates if abs(float(c[0]) - best_score) <= eps]

    # Best-effort: avoid recently returned recipes to reduce repeats on "regenerate".
    recent_ids: set[str] = set()
    try:
        recent = (
            db.table("recipe_attempts")
            .select("recipe_id,created_at")
            .eq("user_id", str(user_id))
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )
        for r in (recent.data or []):
            if isinstance(r, dict) and r.get("recipe_id"):
                recent_ids.add(str(r.get("recipe_id")))
    except Exception:
        recent_ids = set()

    not_recent = [c for c in tied if str(getattr(c[1], "recipe_id", "")) not in recent_ids]
    pool = not_recent if not_recent else tied

    rng = random.Random(seed or str(uuid4()))
    pick = rng.choice(pool)
    _score, recipe, cov, missing_items = pick
    return recipe, cov, missing_items


def _catalog_recipe_name_en(row: dict[str, Any]) -> str:
    rn = row.get("recipe_name")
    if isinstance(rn, dict):
        v = rn.get("en") or next((x for x in rn.values() if isinstance(x, str) and x.strip()), "")
        return str(v or "").strip()
    if isinstance(rn, str):
        return rn.strip()
    return ""


def _catalog_ingredient_names(row: dict[str, Any]) -> list[str]:
    ing = row.get("ingredients")
    if not isinstance(ing, list):
        return []
    out: list[str] = []
    for it in ing:
        if isinstance(it, dict):
            nm = (it.get("canonical_name") or it.get("name") or it.get("ingredient") or "").strip()
            if nm:
                out.append(nm)
        elif isinstance(it, str) and it.strip():
            out.append(it.strip())
    return out


def _try_retrieve_catalog_recipe(
    *,
    user_id: str,
    constraints: LockedConstraints,
    pantry_names: List[str],
    serves: int,
    meal_type: Optional[str] = None,
    day_type: Optional[str] = None,
    ignore_recent: bool = False,
    seed: Optional[str] = None,
    limit: int = 250,
) -> Optional[Tuple[CanonicalRecipe, float, List[MissingIngredient]]]:
    """Best-effort retrieval from ALL_RECIPES_COMPLETE.json.

    This is intentionally lightweight: we match by cuisine + pantry coverage and return
    a randomized pick among the top candidates to reduce repeats.
    """

    items = _load_catalog_items()
    if not items:
        return None

    cuisine = (constraints.cuisine or "").strip().lower()
    normalizer = get_normalizer()
    pantry_set = set(pantry_names or [])

    # Avoid recent returns (works if recipe_attempts persists recipe_id for catalog entries).
    # If ignore_recent=True, we intentionally bypass this to ensure we can always
    # fill a full set of options.
    recent_ids: set[str] = set()
    if not bool(ignore_recent):
        try:
            db = get_db_client()
            recent = (
                db.table("recipe_attempts")
                .select("recipe_id,created_at")
                .eq("user_id", str(user_id))
                .order("created_at", desc=True)
                .limit(20)
                .execute()
            )
            for r in (recent.data or []):
                if isinstance(r, dict) and r.get("recipe_id"):
                    recent_ids.add(str(r.get("recipe_id")))
        except Exception:
            recent_ids = set()

    candidates: list[Tuple[float, dict[str, Any], float, list[str], list[str]]] = []

    # Cap scan cost.
    scan = items[: max(50, int(limit))]
    rng = random.Random(seed or str(uuid4()))
    rng.shuffle(scan)

    for row in scan:
        if not isinstance(row, dict):
            continue
        rid = str(row.get("recipe_id") or "").strip()
        if not rid or rid in recent_ids:
            continue

        rc = str(row.get("cuisine") or "").strip().lower()
        if cuisine and rc and cuisine not in rc:
            continue

        name = _catalog_recipe_name_en(row)
        if not name:
            continue

        raw_ing = _catalog_ingredient_names(row)
        ing_names = [normalizer.normalize_name(x) for x in raw_ing if isinstance(x, str) and x.strip()]

        if ing_names:
            cov, missing = _pantry_coverage(pantry_names=pantry_names, ingredient_names=ing_names)
            score = float(cov)
        else:
            # Many video-backed catalog items don't have structured ingredients.
            # Use a weak signal: title contains pantry items.
            title = name.lower()
            hits = sum(1 for p in (list(pantry_set)[:40]) if p and p in title)
            score = min(0.55, hits / 4.0) if hits else 0.0
            missing = []

        # Context bonus: lightweight keyword-based signal.
        # Keep small so pantry coverage remains dominant.
        name_l = name.lower()
        bonus = 0.0
        mt = (meal_type or "").strip().lower()
        dt = (day_type or "").strip().lower()

        if mt and mt != "any":
            if mt == "breakfast":
                if any(k in name_l for k in [
                    "idli", "dosa", "pongal", "upma", "poha", "paratha", "pancake", "omelet", "omelette", "toast", "porridge",
                ]):
                    bonus += 0.12
            elif mt == "lunch":
                if any(k in name_l for k in [
                    "rice", "biryani", "thali", "curry", "dal", "sambar", "rasam", "pulav", "pulao", "salad", "bowl",
                ]):
                    bonus += 0.10
            elif mt == "dinner":
                if any(k in name_l for k in [
                    "curry", "gravy", "biryani", "roti", "naan", "korma", "stew", "soup",
                ]):
                    bonus += 0.10
            elif mt == "snack":
                if any(k in name_l for k in [
                    "vada", "samosa", "pakora", "bajji", "bond", "chaat", "cutlet", "fritter",
                ]):
                    bonus += 0.12

        prep = 0
        try:
            prep = int(row.get("prep_time_minutes") or 0)
        except Exception:
            prep = 0

        if dt == "weekday":
            if 0 < prep <= 30:
                bonus += 0.08
            elif prep >= 60:
                bonus -= 0.05
        elif dt == "weekend":
            if 0 < prep <= 60:
                bonus += 0.05
        elif dt == "holiday":
            if any(k in name_l for k in [
                "festival", "special", "feast", "biryani", "halwa", "payasam", "laddu", "sweet", "dessert",
            ]):
                bonus += 0.12

        bonus = max(-0.10, min(0.20, bonus))
        score = max(0.0, min(1.0, float(score) + float(bonus)))

        cov_out = float(cov) if ing_names else float(score)
        candidates.append((score, row, cov_out, missing, ing_names))

    if not candidates:
        return None

    candidates.sort(key=lambda t: t[0], reverse=True)
    best = float(candidates[0][0])
    top = [c for c in candidates if float(c[0]) >= max(0.01, best - 0.05)]
    pick = rng.choice(top[: min(25, len(top))])
    _score, row, cov, missing_names, picked_ingredients = pick

    rid = str(row.get("recipe_id") or str(uuid4()))
    rcuisine = str(row.get("cuisine") or cuisine or "mixed").strip().lower() or "mixed"
    difficulty = str(row.get("difficulty") or "easy").strip().lower() or "easy"
    if difficulty not in {"easy", "medium", "hard"}:
        difficulty = "easy"

    steps: list[str] = []
    instr = row.get("instructions")
    if isinstance(instr, list):
        steps = [str(x).strip() for x in instr if str(x).strip()]
    elif isinstance(instr, str) and instr.strip():
        steps = [s.strip() for s in instr.split("\n") if s.strip()]
    if not steps:
        steps = ["Follow the linked recipe/video instructions."]

    ingredients: list[CanonicalIngredient] = []
    for nm in (picked_ingredients or [])[:12]:
        ingredients.append(
            CanonicalIngredient(
                canonical_name=nm,
                ingredient_id=_stable_ingredient_uuid(nm),
                quantity=1,
                unit="pieces",
                optional=False,
            )
        )

    recipe = CanonicalRecipe(
        recipe_id=rid,
        recipe_name=_catalog_recipe_name_en(row) or "Recipe",
        cuisine=rcuisine,
        dietary_tags=list(constraints.dietary or []),
        prep_time_minutes=int(row.get("prep_time_minutes") or 30),
        difficulty=difficulty,
        ingredients=ingredients,
        techniques=list(constraints.techniques_allowed or []),
        steps=steps[:12],
        serves=int(serves),
        created_from="retrieved",
        version="v1",
    )

    # Ensure rich images for every recipe.
    recipe.image_urls = _build_image_urls(recipe_name=recipe.recipe_name, cuisine=recipe.cuisine, count=3)
    if recipe.image_urls and not (recipe.image_url or "").strip():
        recipe.image_url = recipe.image_urls[0]

    missing_items = [MissingIngredient(canonical_name=m) for m in (missing_names or [])]
    return recipe, float(cov or 0.0), missing_items


def _generated_share_exceeded(*, user_id: str, window_days: int = 7, max_share: float = 0.20) -> bool:
    """Best-effort guard for generated<=20% using recent event_log history."""
    db = get_db_client()
    since = (datetime.now(timezone.utc) - timedelta(days=int(window_days))).isoformat()
    try:
        res = (
            db.table("event_log")
            .select("event_type,event_ts")
            .eq("user_id", user_id)
            .gte("event_ts", since)
            .in_("event_type", ["recipe.mode_selected"])
            .limit(500)
            .execute()
        )
        rows = res.data or []
    except Exception:
        return False

    total = 0
    gen = 0
    for r in rows:
        if not isinstance(r, dict):
            continue
        total += 1
        payload = r.get("payload") if isinstance(r.get("payload"), dict) else {}
        if payload.get("mode") == "generated":
            gen += 1
    if total <= 0:
        return False
    return (float(gen) / float(total)) > float(max_share)


def _assemble_recipe(
    *,
    pantry_names: List[str],
    constraints: LockedConstraints,
    serves: int,
    expiring_names: List[str],
) -> Tuple[CanonicalRecipe, float, List[MissingIngredient]]:
    # Deterministic assembly: pick a small set of pantry ingredients and build a simple recipe.
    normalizer = get_normalizer()

    # Prefer expiring items when requested.
    pool = list(pantry_names)
    if constraints.use_expiring_items and expiring_names:
        pool = list(expiring_names) + [p for p in pantry_names if p not in set(expiring_names)]

    chosen = pool[:6]
    if constraints.cuisine == "italian":
        base = ["olive_oil", "garlic", "tomato"]
        for b in base:
            if b in pantry_names and b not in chosen:
                chosen.insert(0, b)
        chosen = chosen[:6]

    if constraints.cuisine == "indian":
        base = ["onion", "tomato"]
        for b in base:
            if b in pantry_names and b not in chosen:
                chosen.insert(0, b)
        chosen = chosen[:6]

    cuisine = constraints.cuisine or "mixed"
    max_time = constraints.max_time_minutes or 30
    prep_time = min(max_time, 30)

    ingredients = [
        CanonicalIngredient(
            canonical_name=nm,
            ingredient_id=_stable_ingredient_uuid(nm),
            quantity=1,
            unit="pieces",
            optional=False,
        )
        for nm in chosen
    ]

    # Pantry coverage is computed against chosen ingredients (should be 100%).
    coverage, missing = _pantry_coverage(pantry_names=pantry_names, ingredient_names=chosen)

    missing_items = [MissingIngredient(canonical_name=m) for m in missing]

    recipe_name = f"{cuisine.title()} Pantry Bowl" if cuisine != "mixed" else "Pantry Bowl"
    steps = [
        "Prep ingredients (wash, chop as needed).",
        "Saute aromatics in a pan with oil until fragrant.",
        "Add remaining ingredients and cook until tender.",
        "Season to taste and serve warm.",
    ]

    techniques = constraints.techniques_allowed or ["saute"]

    recipe = CanonicalRecipe(
        recipe_id=str(uuid4()),
        recipe_name=recipe_name,
        short_description=(
            f"A quick {cuisine} pantry recipe built around what you already have. "
            "Taste and adjust seasoning as you go."
        ),
        cuisine=cuisine,
        dietary_tags=list(constraints.dietary or []),
        prep_time_minutes=int(prep_time),
        difficulty="easy",
        ingredients=ingredients,
        techniques=techniques,
        steps=steps,
        serves=int(serves),
        chef_tips=[
            "Prep everything before you start cooking for best results.",
            "Add salt gradually and balance with a little acid at the end.",
        ],
        serving_suggestions=["Serve hot with a squeeze of lemon/lime if it fits the cuisine."],
        cultural_context={
            "note": "Deterministic fallback recipe; generate mode provides richer cultural grounding.",
        },
        created_from="assembled",
        version="v1",
    )
    return recipe, coverage, missing_items


def _canonical_recipe_json_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "recipe_id",
            "recipe_name",
            "cuisine",
            "dietary_tags",
            "prep_time_minutes",
            "difficulty",
            "ingredients",
            "techniques",
            "steps",
            "serves",
            "created_from",
            "version",
        ],
        "properties": {
            "recipe_id": {"type": "string"},
            "recipe_name": {"type": "string"},
            "image_url": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "short_description": {"anyOf": [{"type": "string"}, {"type": "null"}]},
            "cuisine": {"type": "string"},
            "dietary_tags": {"type": "array", "items": {"type": "string"}},
            "prep_time_minutes": {"type": "number"},
            "difficulty": {"type": "string", "enum": ["easy", "medium", "hard"]},
            "ingredients": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["canonical_name", "ingredient_id", "quantity", "unit", "optional"],
                    "properties": {
                        "canonical_name": {"type": "string"},
                        "ingredient_id": {"type": "string"},
                        "quantity": {"type": "number"},
                        "unit": {"type": "string"},
                        "optional": {"type": "boolean"},
                    },
                },
            },
            "techniques": {"type": "array", "items": {"type": "string"}},
            "steps": {"type": "array", "items": {"type": "string"}},
            "serves": {"type": "number"},
            "chef_tips": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            "serving_suggestions": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
            "cultural_context": {
                "anyOf": [
                    {"type": "object", "additionalProperties": True},
                    {"type": "null"},
                ]
            },
            "created_from": {"type": "string", "enum": ["retrieved", "assembled", "generated"]},
            "version": {"type": "string"},
        },
    }


def _canonical_recipe_options_json_schema(*, count: int) -> Dict[str, Any]:
    n = max(1, min(int(count or 1), 8))
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["recipes"],
        "properties": {
            "recipes": {
                "type": "array",
                # IMPORTANT: do not require an exact count here.
                # In practice, strict decoding for N full recipes can fail (timeouts/truncation),
                # which caused us to fall back to deterministic assembly and appear "repetitive".
                # We allow partial results and will still return whatever valid options we got.
                "minItems": 1,
                "maxItems": n,
                "items": _canonical_recipe_json_schema(),
            }
        },
    }


def _validate_against_constraints(
    *,
    recipe: Dict[str, Any],
    constraints: LockedConstraints,
    pantry_names: List[str],
) -> Tuple[bool, List[str]]:
    violations: List[str] = []

    cuisine = (recipe.get("cuisine") or "").strip().lower()
    if constraints.cuisine and cuisine != (constraints.cuisine or "").strip().lower():
        violations.append("cuisine_mismatch")

    try:
        t = int(recipe.get("prep_time_minutes") or 0)
        if constraints.max_time_minutes is not None and t > int(constraints.max_time_minutes):
            violations.append("max_time_exceeded")
    except Exception:
        violations.append("invalid_prep_time")

    # Pantry-only or explicitly missing: enforce ingredient ids correspond to allowed names.
    # Since canonical schema uses ingredient_id only, we conservatively enforce pantry coverage by count.
    ing = recipe.get("ingredients")
    if isinstance(ing, list):
        if not ing:
            violations.append("no_ingredients")
        # coverage check: if any ingredient is not in pantry, we will label missing externally.
        # Here we only ensure there is at least some overlap.
        if pantry_names and len(ing) > 0 and len(pantry_names) == 0:
            violations.append("empty_pantry")

    # Dietary tags must include requested ones
    desired = set(_clean_tag(x) for x in (constraints.dietary or []) if _clean_tag(x))
    actual = set(_clean_tag(x) for x in (recipe.get("dietary_tags") or []) if isinstance(x, str))
    if desired and not desired.issubset(actual):
        violations.append("dietary_tags_missing")

    return len(violations) == 0, violations


@router.post("/generate", response_model=RecipeGenerateResponse)
async def generate_recipe(
    req: RecipeGenerateRequest,
    user_id: str = Depends(get_current_user),
):
    # Load profile + pantry truth (or request-provided inventory override).
    try:
        profile = await get_full_profile(str(user_id))
    except Exception:
        profile = {}

    override_names = _extract_inventory_override_names(req)
    pantry: list[dict[str, Any]] = []
    if override_names:
        pantry_names = override_names
        expiring = []
    else:
        try:
            pantry = await get_inventory(str(user_id), include_inactive=bool(req.include_inactive_inventory))
        except Exception:
            pantry = []
        pantry_names = _extract_pantry_names(pantry if isinstance(pantry, list) else [])
        expiring = _find_expiring_items(pantry if isinstance(pantry, list) else [])

    constraints = _resolve_intent_to_constraints(req)
    constraints.ingredients_allowed = pantry_names

    req_creativity = (req.creativity or "").strip().lower()
    force_generation = (req_creativity == "high") or _wants_native_or_innovative_recipe(req.request_text)

    attempt_id = str(uuid4())

    emit_event(
        event_type="recipe.constraints_locked",
        user_id=str(user_id),
        entity_type="recipe_attempt",
        entity_id=attempt_id,
        payload={"constraints": constraints.model_dump(), "request_text": req.request_text or ""},
    )

    preferred_threshold = 0.70

    # Try retrieved first.
    # Optimization: for explicit creative/native requests we skip retrieval to reduce latency
    # and maximize novelty.
    retrieved = None
    if not force_generation:
        # 1) DB recipes table (if present)
        retrieved = _try_retrieve_recipe(
            user_id=str(user_id),
            constraints=constraints,
            pantry_names=pantry_names,
            serves=req.serves,
            seed=attempt_id,
        )
        # 2) Global catalog (ALL_RECIPES_COMPLETE.json)
        if retrieved is None:
            retrieved = _try_retrieve_catalog_recipe(
                user_id=str(user_id),
                constraints=constraints,
                pantry_names=pantry_names,
                serves=req.serves,
                meal_type=req.meal_type,
                day_type=req.day_type,
                seed=attempt_id,
            )

    assembled, coverage, missing = _assemble_recipe(
        pantry_names=pantry_names,
        constraints=constraints,
        serves=req.serves,
        expiring_names=expiring,
    )

    recipe_obj: Optional[CanonicalRecipe] = None
    pantry_cov = 0.0
    missing_items: List[MissingIngredient] = []
    mode = "assembled"
    reason = "pantry_match"

    if retrieved is not None:
        r_recipe, r_cov, r_missing = retrieved
        # Validate safety before selecting.
        ok_r, _ = validate_recipe_safety(r_recipe.model_dump(), profile if isinstance(profile, dict) else {})
        if ok_r:
            recipe_obj = r_recipe
            pantry_cov = float(r_cov)
            missing_items = list(r_missing)
            mode = "retrieved"
            reason = "pantry_match"

    if recipe_obj is None:
        recipe_obj = assembled
        pantry_cov = float(coverage)
        missing_items = list(missing)
        mode = "assembled"
        reason = "pantry_match"

    # Always attach image_urls for UI richness.
    try:
        if not getattr(recipe_obj, "image_urls", None):
            recipe_obj.image_urls = _build_image_urls(recipe_name=recipe_obj.recipe_name, cuisine=recipe_obj.cuisine, count=3)
        if recipe_obj.image_urls and not (recipe_obj.image_url or "").strip():
            recipe_obj.image_url = recipe_obj.image_urls[0]
    except Exception:
        pass

    # Safety validation (hard guardrails)
    ok_safety, safety_violations = validate_recipe_safety(assembled.model_dump(), profile if isinstance(profile, dict) else {})
    if not ok_safety:
        # If assembled violates safety, try generated as a constrained repair.
        safety_hint = " ".join(safety_violations)[:500]
    else:
        safety_hint = ""

    # Decide if we need constrained generation.
    ok_safety, safety_violations = validate_recipe_safety(recipe_obj.model_dump(), profile if isinstance(profile, dict) else {})
    safety_hint = " ".join(safety_violations)[:500] if not ok_safety else ""

    # If request_text_forces_generation is enabled, a free-form request prefers a fresh recipe.
    has_request_text = bool((req.request_text or "").strip())
    needs_generation = (
        force_generation
        or (has_request_text and bool(req.request_text_forces_generation))
        or (pantry_cov < preferred_threshold)
        or (not ok_safety)
    )

    if not bool(req.allow_generation):
        needs_generation = False

    if needs_generation:
        # Enforce distribution target best-effort (generated <= 20%).
        if (not force_generation) and _generated_share_exceeded(user_id=str(user_id)):
            needs_generation = False

    if needs_generation:
        # Generated mode is allowed only after constraints are locked. This is best-effort and must be validated.
        mode = "generated"
        if force_generation:
            reason = "creative_request"
        else:
            reason = "pantry_match" if pantry_cov < preferred_threshold else "safety_repair"

        schema = _canonical_recipe_json_schema()
        try:
            client = get_reasoning_client()
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Recipe generation provider is not configured correctly. "
                    f"Reasoning provider error: {e}"
                ),
            )

        pantry_id_to_name = _ingredient_id_map(pantry_names)
        missing_candidates = _suggest_missing_candidates(pantry_names=pantry_names, cuisine=constraints.cuisine)
        missing_id_to_name = _ingredient_id_map(missing_candidates)

        family_profile_compact = _compact_family_profile(profile if isinstance(profile, dict) else {})
        pantry_context = _extract_pantry_context(
            pantry if isinstance(pantry, list) else [],
            # Keep prompts smaller/faster for creative requests.
            limit=40 if force_generation else 80,
            prefer_expiring_items=bool(constraints.use_expiring_items),
            expiring_names=expiring,
        )
        recent_avoid = _best_effort_recent_recipe_avoid_list(user_id=str(user_id), limit=12)

        requested_hints = _extract_request_ingredient_hints(req.request_text, pantry_names, limit=4)
        focus_pair = _pick_option_focus_pairs(
            pantry_context=pantry_context,
            profile=profile if isinstance(profile, dict) else {},
            count=1,
            prefer_expiring=expiring,
        )
        # If the user mentions ingredients explicitly, honor them as the main focus.
        if len(requested_hints) >= 2:
            a, b = requested_hints[0], requested_hints[1]
            focus_pair = [
                {
                    "option_index": 1,
                    "main_ingredients": [a, b],
                    "main_ingredient_ids": [_stable_ingredient_uuid(a), _stable_ingredient_uuid(b)],
                }
            ]
        pantry_image_signals = _build_image_signals(pantry if isinstance(pantry, list) else [])
        safety_constraints_text = {
            "allergens": build_allergen_constraints(profile if isinstance(profile, dict) else {}),
            "religious": build_religious_constraints(profile if isinstance(profile, dict) else {}),
            "dietary": build_dietary_constraints(profile if isinstance(profile, dict) else {}),
        }

        focus_ingredients = _pick_cultural_focus_ingredients(pantry_names=pantry_names, expiring=expiring)
        cultural_intelligence_text = build_cultural_intelligence_prompt(
            focus_ingredients,
            cuisine=constraints.cuisine,
        ).strip()

        prompt = {
            "request_text": (req.request_text or ""),
            "requested_ingredient_hints": requested_hints,
            "today_utc": _now_iso(),
            "locked_constraints": constraints.model_dump(),
            "family_profile": family_profile_compact,
            "safety_constraints": safety_constraints_text,
            "allowed_pantry_ingredients": [{"canonical_name": n, "ingredient_id": _stable_ingredient_uuid(n)} for n in pantry_names],
            "pantry_context": pantry_context,
            "pantry_image_signals": pantry_image_signals,
            "missing_candidates": [{"canonical_name": n, "ingredient_id": _stable_ingredient_uuid(n)} for n in missing_candidates],
            "expiring_items": expiring,
            "avoid_recent": recent_avoid,
            "main_ingredient_focus": (focus_pair[0] if isinstance(focus_pair, list) and focus_pair else None),
            "preferred_pantry_coverage_threshold": preferred_threshold,
            "serves": int(req.serves),
            "creative_intent": bool(force_generation),
            "cultural_focus_ingredients": focus_ingredients,
            "hard_constraints": [
                "only_pantry_available_ingredients_or_explicitly_marked_missing",
                "cuisine_logic_must_match",
                "dietary_rules_must_be_enforced",
                "max_cooking_time_must_be_respected",
                "llm_never_decides_constraints_only_fills_structure",
                "ingredient_id_must_come_from_allowed_or_missing_lists_only",
                "include_short_description_chef_tips_serving_suggestions_cultural_context",
            ],
            "safety_hint": safety_hint,
        }

        try:
            budget_seconds = 14 if force_generation else _GENERATION_BUDGET_SECONDS
            budget_seconds = max(8, int(budget_seconds))

            # Add a per-request nonce so repeated calls don't collapse into the same recipe.
            prompt["request_id"] = attempt_id
            prompt["variation_seed"] = str(uuid4())

            generated = await asyncio.wait_for(
                generate_json_with_retries(
                    client=client,
                    messages=[
                        {
                            "role": "system",
                            "content": (
                                "You are SAVO's constrained recipe generator. "
                                "You MUST follow the locked constraints exactly. "
                                "You must not invent constraints. "
                                "You MUST respect family_profile + safety_constraints. "
                                "You MUST maximize use of pantry_context and allowed_pantry_ingredients. "
                                "Use pantry_image_signals only as weak evidence of item type/freshness and packaged portions; be conservative about quantities. "
                                "CRITICAL: Every ingredient_id MUST match one of the provided allowed_pantry_ingredients or missing_candidates. "
                                "If main_ingredient_focus is provided, you MUST treat those main_ingredients as the centerpiece (both must appear as non-optional ingredients). "
                                "You MUST avoid repeating any recipe_names, recipe_ids, or recipe_fingerprints listed in avoid_recent. "
                                "Recipe_fingerprints represent the combination of cuisine + technique + main ingredients; do NOT repeat those patterns. "
                                "Recipe_name MUST be a specific, culturally grounded dish name (not generic like 'Pantry Bowl'). "
                                "Steps MUST be written in English (translation is handled separately). "
                                "You MUST include: short_description, chef_tips (3-6), serving_suggestions (2-5), and cultural_context (origin + why_native + serving_note). "
                                "If creative_intent is true, prioritize culturally authentic, regionally-native dishes with correct flavor logic (spice base, fat, acid, aromatics) for the cuisine. "
                                f"\n\nCULTURAL INTELLIGENCE CONTEXT (use as grounding, do not contradict safety/constraints):\n{cultural_intelligence_text}\n"
                                "Return JSON only that matches the schema." 
                            ),
                        },
                        {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                    ],
                    schema=schema,
                    # For creative requests, prioritize speed. If generation fails,
                    # we fail closed to assembled.
                    max_attempts=3,
                    repair_hint="constrained recipe json",
                    mode_hint="recipe",
                    temperature=0.85 if force_generation else 0.70,
                    # Encourage novelty while schema + validators keep structure/safety tight.
                    presence_penalty=0.5 if force_generation else 0.2,
                    frequency_penalty=0.10 if force_generation else 0.05,
                ),
                timeout=budget_seconds,
            )

            # Normalize fields and validate
            is_ok, violations = _validate_against_constraints(recipe=generated, constraints=constraints, pantry_names=pantry_names)
            ok2, safety_viol2 = validate_recipe_safety(generated, profile if isinstance(profile, dict) else {})

            if not is_ok:
                raise ValueError(f"Generated recipe violates constraints: {violations}")
            if not ok2:
                raise ValueError(f"Generated recipe violates safety: {safety_viol2}")

            recipe_obj = CanonicalRecipe(**{
                **generated,
                "recipe_id": (generated.get("recipe_id") or str(uuid4())),
                "version": (generated.get("version") or "v1"),
                "created_from": "generated",
            })

            # Pantry coverage for generated recipes is computed by stable ingredient_id mapping.
            ing_ids: List[str] = []
            try:
                for it in (generated.get("ingredients") or []):
                    if isinstance(it, dict) and it.get("ingredient_id"):
                        ing_ids.append(str(it.get("ingredient_id")))
            except Exception:
                ing_ids = []

            pantry_cov, missing_items = _pantry_coverage_by_id(
                pantry_id_to_name=pantry_id_to_name,
                ingredient_ids=ing_ids,
                id_to_name_hint={**missing_id_to_name},
            )

        except Exception as e:
            # Best-effort diagnostics. This endpoint used to swallow errors and always fall back,
            # making it look like "LLM never generates".
            try:
                emit_event(
                    event_type="recipe.generation.failed",
                    user_id=str(user_id),
                    entity_type="recipe_attempt",
                    entity_id=attempt_id,
                    payload={
                        "error": str(e)[:500],
                        "creative_intent": bool(force_generation),
                        "had_request_text": bool((req.request_text or "").strip()),
                        "budget_seconds": int(budget_seconds),
                    },
                )
            except Exception:
                pass

            # Fail closed: fall back to assembled recipe.
            mode = "assembled"
            reason = "fallback"
            recipe_obj = assembled
            pantry_cov = float(coverage)
            missing_items = list(missing)

    # Best-effort recipe image derived from pantry item images.
    try:
        img = _best_effort_recipe_image_url(
            pantry=pantry if isinstance(pantry, list) else [],
            recipe=recipe_obj,
        )
        if img and str(img).strip():
            recipe_obj.image_url = str(img).strip()
    except Exception:
        pass

    # Emit mode selection event
    emit_event(
        event_type="recipe.mode_selected",
        user_id=str(user_id),
        entity_type="recipe_attempt",
        entity_id=attempt_id,
        payload={
            "mode": mode,
            "reason": reason,
            "pantry_coverage": pantry_cov,
            "missing_count": len(missing_items),
        },
    )

    uses_what_you_have = pantry_cov >= preferred_threshold and len(missing_items) == 0
    uses_expiring = bool(constraints.use_expiring_items and expiring)

    trust = TrustSignals(
                                    timeout_seconds=11,
        estimated_time_minutes=int(getattr(recipe_obj, "prep_time_minutes", 0) or 0),
        uses_expiring_items=uses_expiring,
        adjustable_spice_level=True,
    )

    # Persist attempt + context for later saving/planning (best-effort).
    try:
        family_profile_compact = _compact_family_profile(profile if isinstance(profile, dict) else {})
        pantry_context_all = _extract_pantry_context(
            pantry if isinstance(pantry, list) else [],
            prefer_expiring_items=bool(constraints.use_expiring_items),
            expiring_names=expiring,
        )
        image_signals = _build_image_signals(pantry if isinstance(pantry, list) else [])
        _best_effort_persist_recipe_attempt(
            user_id=str(user_id),
            attempt_id=attempt_id,
            payload={
                "recipe_id": str(getattr(recipe_obj, "recipe_id", "")),
                "request_text": (req.request_text or ""),
                "mode": mode,
                "reason": reason,
                "pantry_coverage": float(pantry_cov or 0.0),
                "locked_constraints": constraints.model_dump(),
                "family_profile": family_profile_compact,
                "pantry_context": pantry_context_all,
                "missing_ingredients": [m.model_dump() for m in (missing_items or [])],
                "recipe": recipe_obj.model_dump(),
                "image_signals": image_signals,
            },
        )
    except Exception:
        pass

    target_language = _requested_translation_target(req)
    i18n = await _translate_canonical_recipe_i18n(
        recipe=recipe_obj,
        target_language=target_language,
        include_steps=True,
    )

    return RecipeGenerateResponse(
        recipe=recipe_obj,
        locked_constraints=constraints,
        pantry_coverage=pantry_cov,
        missing_ingredients=missing_items,
        mode=mode,
        reason=reason,
        trust_signals=trust,
        i18n=i18n,
    )


@router.post("/generate-options", response_model=RecipeGenerateOptionsResponse)
async def generate_recipe_options(
    req: RecipeGenerateOptionsRequest,
    user_id: str = Depends(get_current_user),
):
    # Load profile + pantry truth (or request-provided inventory override).
    try:
        profile = await get_full_profile(str(user_id))
    except Exception:
        profile = {}

    override_names = _extract_inventory_override_names(req)
    pantry: list[dict[str, Any]] = []
    if override_names:
        pantry_names = override_names
        expiring = []
    else:
        try:
            pantry = await get_inventory(str(user_id), include_inactive=bool(req.include_inactive_inventory))
        except Exception:
            pantry = []
        pantry_names = _extract_pantry_names(pantry if isinstance(pantry, list) else [])
        expiring = _find_expiring_items(pantry if isinstance(pantry, list) else [])

    constraints = _resolve_intent_to_constraints(req)
    constraints.ingredients_allowed = pantry_names

    req_creativity = (req.creativity or "").strip().lower()
    force_generation = (req_creativity == "high") or _wants_native_or_innovative_recipe(req.request_text)

    preferred_threshold = 0.70

    # Deterministic fallback (for fail-closed behavior)
    assembled, assembled_cov, assembled_missing = _assemble_recipe(
        pantry_names=pantry_names,
        constraints=constraints,
        serves=req.serves,
        expiring_names=expiring,
    )

    count = max(1, min(int(req.count or 1), 8))

    def _top_up_options_from_catalog(
        *,
        options: list[RecipeGenerateResponse],
        used_ids: set[str],
        constraints_override: Optional[LockedConstraints] = None,
        target_count: int,
        allow_recent: bool = False,
        max_attempts: int = 80,
        reason: str = "catalog_topup",
    ) -> None:
        tries = 0
        effective_constraints = constraints_override or constraints
        while len(options) < int(target_count) and tries < int(max_attempts):
            tries += 1
            picked = _try_retrieve_catalog_recipe(
                user_id=str(user_id),
                constraints=effective_constraints,
                pantry_names=pantry_names,
                serves=req.serves,
                meal_type=req.meal_type,
                day_type=req.day_type,
                ignore_recent=bool(allow_recent),
                seed=f"{user_id}:{uuid4()}",
            )
            if not picked:
                break
            recipe_obj, pantry_cov, missing_items = picked
            rid = str(getattr(recipe_obj, "recipe_id", "") or "").strip()
            if rid and rid in used_ids:
                continue
            if rid:
                used_ids.add(rid)
            trust = TrustSignals(
                uses_what_you_have=float(pantry_cov or 0.0) >= preferred_threshold and len(missing_items) == 0,
                estimated_time_minutes=int(getattr(recipe_obj, "prep_time_minutes", 0) or 0),
                uses_expiring_items=bool(constraints.use_expiring_items and expiring),
                adjustable_spice_level=True,
            )
            options.append(
                RecipeGenerateResponse(
                    recipe=recipe_obj,
                    locked_constraints=effective_constraints,
                    pantry_coverage=float(pantry_cov or 0.0),
                    missing_ingredients=list(missing_items or []),
                    mode="retrieved",
                    reason=str(reason),
                    trust_signals=trust,
                )
            )

    # Catalog-only mode (no LLM): return varied catalog picks.
    if not bool(req.allow_generation):
        options: list[RecipeGenerateResponse] = []
        used_ids: set[str] = set()
        # First pass: respect cuisine (if present) and avoid recent attempts.
        _top_up_options_from_catalog(
            options=options,
            used_ids=used_ids,
            constraints_override=constraints,
            target_count=int(count),
            allow_recent=False,
            max_attempts=80,
            reason="catalog_match",
        )

        # Second pass: relax cuisine matching if we still can't fill.
        if len(options) < int(count):
            relaxed = LockedConstraints(
                cuisine=None,
                ingredients_allowed=list(constraints.ingredients_allowed or []),
                max_time_minutes=constraints.max_time_minutes,
                dietary=list(constraints.dietary or []),
                techniques_allowed=list(constraints.techniques_allowed or []),
                use_expiring_items=bool(constraints.use_expiring_items),
                spice_level=constraints.spice_level,
            )
            _top_up_options_from_catalog(
                options=options,
                used_ids=used_ids,
                constraints_override=relaxed,
                target_count=int(count),
                allow_recent=False,
                max_attempts=120,
                reason="catalog_relaxed",
            )

        # Final pass: allow recent picks (still avoids duplicates within this response).
        if len(options) < int(count):
            _top_up_options_from_catalog(
                options=options,
                used_ids=used_ids,
                constraints_override=None,
                target_count=int(count),
                allow_recent=True,
                max_attempts=160,
                reason="catalog_relaxed_recent",
            )

        target_language = _requested_translation_target(req)
        i18n_list = await _translate_canonical_recipes_batch_i18n(
            recipes=[o.recipe for o in options],
            target_language=target_language,
        )
        for o, i18n in zip(options, i18n_list):
            o.i18n = i18n
        return RecipeGenerateOptionsResponse(options=options)

    # Prepare generation prompt
    schema = _canonical_recipe_options_json_schema(count=count)
    try:
        client = get_reasoning_client()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=(
                "Recipe generation provider is not configured correctly. "
                f"Reasoning provider error: {e}"
            ),
        )

    pantry_id_to_name = _ingredient_id_map(pantry_names)
    missing_candidates = _suggest_missing_candidates(pantry_names=pantry_names, cuisine=constraints.cuisine)
    missing_id_to_name = _ingredient_id_map(missing_candidates)

    family_profile_compact = _compact_family_profile(profile if isinstance(profile, dict) else {})
    pantry_context = _extract_pantry_context(
        pantry if isinstance(pantry, list) else [],
        # Keep prompts smaller/faster. Multi-option responses can get large.
        limit=35,
        prefer_expiring_items=bool(constraints.use_expiring_items),
        expiring_names=expiring,
    )
    recent_avoid = _best_effort_recent_recipe_avoid_list(user_id=str(user_id), limit=14)

    requested_hints = _extract_request_ingredient_hints(req.request_text, pantry_names, limit=4)
    option_focus = _pick_option_focus_pairs(
        pantry_context=pantry_context,
        profile=profile if isinstance(profile, dict) else {},
        count=int(count),
        prefer_expiring=expiring,
    )
    # If the user mentions ingredients, force the first option to center them.
    if len(requested_hints) >= 2:
        a, b = requested_hints[0], requested_hints[1]
        forced = {
            "option_index": 1,
            "main_ingredients": [a, b],
            "main_ingredient_ids": [_stable_ingredient_uuid(a), _stable_ingredient_uuid(b)],
        }
        option_focus = [forced] + [x for x in (option_focus or []) if isinstance(x, dict)][: max(0, int(count) - 1)]
    pantry_image_signals = _build_image_signals(pantry if isinstance(pantry, list) else [])
    safety_constraints_text = {
        "allergens": build_allergen_constraints(profile if isinstance(profile, dict) else {}),
        "religious": build_religious_constraints(profile if isinstance(profile, dict) else {}),
        "dietary": build_dietary_constraints(profile if isinstance(profile, dict) else {}),
    }

    focus_ingredients = _pick_cultural_focus_ingredients(pantry_names=pantry_names, expiring=expiring)
    cultural_intelligence_text = build_cultural_intelligence_prompt(
        focus_ingredients,
        cuisine=constraints.cuisine,
    ).strip()

    prompt = {
        "request_text": (req.request_text or ""),
        "meal_type": (req.meal_type or ""),
        "day_type": (req.day_type or ""),
        "requested_ingredient_hints": requested_hints,
        "today_utc": _now_iso(),
        "locked_constraints": constraints.model_dump(),
        "family_profile": family_profile_compact,
        "safety_constraints": safety_constraints_text,
        "allowed_pantry_ingredients": [{"canonical_name": n, "ingredient_id": _stable_ingredient_uuid(n)} for n in pantry_names],
        "pantry_context": pantry_context,
        "pantry_image_signals": pantry_image_signals,
        "missing_candidates": [{"canonical_name": n, "ingredient_id": _stable_ingredient_uuid(n)} for n in missing_candidates],
        "expiring_items": expiring,
        "avoid_recent": recent_avoid,
        "preferred_pantry_coverage_threshold": preferred_threshold,
        "serves": int(req.serves),
        "creative_intent": bool(force_generation),
        "option_focus_pairs": option_focus,
        "cultural_focus_ingredients": focus_ingredients,
        "option_count": int(count),
        "diversity_rules": [
            "return_up_to_option_count_recipes",
            "each_recipe_name_must_be_distinct",
            "vary_dish_type_and_primary_technique_across_options",
            "avoid_generic_names_like_pantry_bowl",
            "keep_each_recipe_compact_ingredients<=12_steps<=7",
            "use_option_focus_pairs_in_order_as_main_ingredients",
            "each_option_must_use_both_main_ingredients_as_non_optional",
            "do_not_repeat_any_recipe_in_avoid_recent",
        ],
        "hard_constraints": [
            "only_pantry_available_ingredients_or_explicitly_marked_missing",
            "cuisine_logic_must_match",
            "dietary_rules_must_be_enforced",
            "max_cooking_time_must_be_respected",
            "llm_never_decides_constraints_only_fills_structure",
            "ingredient_id_must_come_from_allowed_or_missing_lists_only",
            "include_short_description_chef_tips_serving_suggestions_cultural_context",
        ],
        "safety_hint": "",
    }

    # Track as a single multi-option request
    request_id = str(uuid4())
    emit_event(
        event_type="recipe.options.constraints_locked",
        user_id=str(user_id),
        entity_type="recipe_options_request",
        entity_id=request_id,
        payload={
            "constraints": constraints.model_dump(),
            "request_text": req.request_text or "",
            "count": int(count),
            "creative_intent": bool(force_generation),
        },
    )

    try:
        # Tight budget; multi-option payloads can be large, but long waits are worse than
        # returning fewer options.
        budget_seconds = 14 if int(count) <= 5 else 18
        if force_generation:
            budget_seconds = min(18, int(budget_seconds) + 2)

        # Add a per-request nonce to reduce repeated outputs across calls.
        prompt["options_request_id"] = request_id
        prompt["variation_seed"] = str(uuid4())

        generated = await asyncio.wait_for(
            generate_json_with_retries(
                client=client,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are SAVO's constrained recipe generator. "
                            "You MUST follow the locked constraints exactly. "
                            "You must not invent constraints. "
                            "You MUST respect family_profile + safety_constraints. "
                            "You MUST maximize use of pantry_context and allowed_pantry_ingredients. "
                            "CRITICAL: Every ingredient_id MUST match one of the provided allowed_pantry_ingredients or missing_candidates. "
                            "Return a DIVERSE set of options; do not repeat the same dish with minor variations. "
                            "If option_focus_pairs is provided, you MUST return recipes in the SAME order as option_focus_pairs and "
                            "treat each pair as the MAIN ingredients (must be present as non-optional ingredients). "
                            "You MUST avoid repeating any recipe_names, recipe_ids, or recipe_fingerprints listed in avoid_recent. "
                            "Steps MUST be written in English (translation is handled separately). "
                            "You MUST include: short_description, chef_tips (3-6), serving_suggestions (2-5), and cultural_context (origin + why_native + serving_note). "
                            "Keep each option compact: steps <= 6, ingredient list <= 10. "
                            "If creative_intent is true, prioritize culturally authentic, regionally-native dishes and avoid generic names (e.g., 'Pantry Bowl'). "
                            "Return BETWEEN 3 and option_count recipes if possible; do not fail the whole response if you cannot reach option_count. "
                            f"\n\nCULTURAL INTELLIGENCE CONTEXT (use as grounding, do not contradict safety/constraints):\n{cultural_intelligence_text}\n"
                            "Return JSON only that matches the schema."
                        ),
                    },
                    {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
                ],
                schema=schema,
                max_attempts=2,
                repair_hint="constrained recipe options json",
                mode_hint="recipe",
                temperature=0.85 if force_generation else 0.70,
                presence_penalty=0.5 if force_generation else 0.2,
                frequency_penalty=0.15 if force_generation else 0.05,
            ),
            timeout=budget_seconds,
        )

        raw_recipes = generated.get("recipes") if isinstance(generated, dict) else None
        if not isinstance(raw_recipes, list) or not raw_recipes:
            raise ValueError("No recipes returned")

        options: list[RecipeGenerateResponse] = []
        seen_names: set[str] = set()
        seen_fps: set[str] = set()
        recent_names = set((recent_avoid.get("recipe_names") or [])) if isinstance(recent_avoid, dict) else set()
        recent_ids = set((recent_avoid.get("recipe_ids") or [])) if isinstance(recent_avoid, dict) else set()
        recent_fps = set((recent_avoid.get("recipe_fingerprints") or [])) if isinstance(recent_avoid, dict) else set()

        for idx, item in enumerate(raw_recipes):
            if not isinstance(item, dict):
                continue

            is_ok, violations = _validate_against_constraints(recipe=item, constraints=constraints, pantry_names=pantry_names)
            if not is_ok:
                continue

            ok_safety, _ = validate_recipe_safety(item, profile if isinstance(profile, dict) else {})
            if not ok_safety:
                continue

            # Normalize + ensure ids
            normalized = {
                **item,
                "recipe_id": (item.get("recipe_id") or str(uuid4())),
                "version": (item.get("version") or "v1"),
                "created_from": "generated",
            }
            recipe_obj = CanonicalRecipe(**normalized)

            # Best-effort recipe image derived from pantry item images.
            try:
                img = _best_effort_recipe_image_url(
                    pantry=pantry if isinstance(pantry, list) else [],
                    recipe=recipe_obj,
                )
                if img and str(img).strip():
                    recipe_obj.image_url = str(img).strip()
            except Exception:
                pass

            fp = _recipe_fingerprint_from_recipe_dict(normalized)
            if fp:
                if fp in seen_fps:
                    continue
                if fp in recent_fps:
                    continue
                seen_fps.add(fp)

            # Basic dedupe by name
            nm = (recipe_obj.recipe_name or "").strip().lower()
            if not nm or nm in seen_names:
                continue
            if nm in recent_names:
                continue
            if str(recipe_obj.recipe_id or "").strip() in recent_ids:
                continue
            seen_names.add(nm)

            ing_ids: List[str] = []
            try:
                for it in (item.get("ingredients") or []):
                    if isinstance(it, dict) and it.get("ingredient_id"):
                        ing_ids.append(str(it.get("ingredient_id")))
            except Exception:
                ing_ids = []

            # Enforce the 2-item "main ingredient" focus when we have a blueprint.
            if isinstance(option_focus, list) and idx < len(option_focus):
                focus = option_focus[idx]
                if isinstance(focus, dict):
                    focus_ids = focus.get("main_ingredient_ids")
                    if isinstance(focus_ids, list) and len(focus_ids) >= 2:
                        focus_ids_s = [str(x) for x in focus_ids if str(x).strip()]
                        if focus_ids_s:
                            matches = len(set(ing_ids) & set(focus_ids_s))
                            if matches < 2:
                                continue

            pantry_cov, missing_items = _pantry_coverage_by_id(
                pantry_id_to_name=pantry_id_to_name,
                ingredient_ids=ing_ids,
                id_to_name_hint={**missing_id_to_name},
            )

            uses_what_you_have = float(pantry_cov or 0.0) >= preferred_threshold and len(missing_items) == 0
            uses_expiring = bool(constraints.use_expiring_items and expiring)
            trust = TrustSignals(
                uses_what_you_have=uses_what_you_have,
                estimated_time_minutes=int(getattr(recipe_obj, "prep_time_minutes", 0) or 0),
                uses_expiring_items=uses_expiring,
                adjustable_spice_level=True,
            )

            attempt_id = str(uuid4())
            emit_event(
                event_type="recipe.mode_selected",
                user_id=str(user_id),
                entity_type="recipe_attempt",
                entity_id=attempt_id,
                payload={
                    "mode": "generated",
                    "reason": "creative_request" if force_generation else "pantry_match",
                    "pantry_coverage": float(pantry_cov or 0.0),
                    "missing_count": len(missing_items),
                    "options_request_id": request_id,
                },
            )

            # Best-effort persist each option as its own attempt.
            try:
                pantry_context_all = _extract_pantry_context(
                    pantry if isinstance(pantry, list) else [],
                    prefer_expiring_items=bool(constraints.use_expiring_items),
                    expiring_names=expiring,
                )
                image_signals = _build_image_signals(pantry if isinstance(pantry, list) else [])
                _best_effort_persist_recipe_attempt(
                    user_id=str(user_id),
                    attempt_id=attempt_id,
                    payload={
                        "recipe_id": str(getattr(recipe_obj, "recipe_id", "")),
                        "request_text": (req.request_text or ""),
                        "mode": "generated",
                        "reason": "creative_request" if force_generation else "pantry_match",
                        "pantry_coverage": float(pantry_cov or 0.0),
                        "locked_constraints": constraints.model_dump(),
                        "family_profile": family_profile_compact,
                        "pantry_context": pantry_context_all,
                        "missing_ingredients": [m.model_dump() for m in (missing_items or [])],
                        "recipe": recipe_obj.model_dump(),
                        "image_signals": image_signals,
                        "options_request_id": request_id,
                    },
                )
            except Exception:
                pass

            options.append(
                RecipeGenerateResponse(
                    recipe=recipe_obj,
                    locked_constraints=constraints,
                    pantry_coverage=float(pantry_cov or 0.0),
                    missing_ingredients=list(missing_items or []),
                    mode="generated",
                    reason="creative_request" if force_generation else "pantry_match",
                    trust_signals=trust,
                )
            )

        if not options:
            raise ValueError("No valid options")

        emit_event(
            event_type="recipe.options.generated",
            user_id=str(user_id),
            entity_type="recipe_options_request",
            entity_id=request_id,
            payload={
                "requested": int(count),
                "returned": int(len(options)),
                "creative_intent": bool(force_generation),
            },
        )

        target_language = _requested_translation_target(req)
        i18n_list = await _translate_canonical_recipes_batch_i18n(
            recipes=[o.recipe for o in options],
            target_language=target_language,
        )
        for o, i18n in zip(options, i18n_list):
            o.i18n = i18n

        # Enforce full option_count: backfill any shortfall with catalog picks.
        if len(options) < int(count):
            used_ids: set[str] = set()
            for o in options:
                rid = str(getattr(o.recipe, "recipe_id", "") or "").strip()
                if rid:
                    used_ids.add(rid)
            _top_up_options_from_catalog(
                options=options,
                used_ids=used_ids,
                constraints_override=constraints,
                target_count=int(count),
                allow_recent=False,
                max_attempts=120,
                reason="catalog_topup",
            )
            if len(options) < int(count):
                _top_up_options_from_catalog(
                    options=options,
                    used_ids=used_ids,
                    constraints_override=None,
                    target_count=int(count),
                    allow_recent=True,
                    max_attempts=160,
                    reason="catalog_topup_relaxed",
                )

        # Re-translate if we topped up.
        if len(i18n_list) != len(options):
            target_language = _requested_translation_target(req)
            i18n_list = await _translate_canonical_recipes_batch_i18n(
                recipes=[o.recipe for o in options],
                target_language=target_language,
            )
            for o, i18n in zip(options, i18n_list):
                o.i18n = i18n

        return RecipeGenerateOptionsResponse(options=options)

    except Exception as e:
        try:
            emit_event(
                event_type="recipe.options.generation.failed",
                user_id=str(user_id),
                entity_type="recipe_options_request",
                entity_id=request_id,
                payload={
                    "error": str(e)[:500],
                    "requested": int(count),
                    "creative_intent": bool(force_generation),
                    "budget_seconds": int(budget_seconds) if "budget_seconds" in locals() else None,
                },
            )
        except Exception:
            pass

        # Fail closed: return at least one deterministic option.
        attempt_id = str(uuid4())
        trust = TrustSignals(
            uses_what_you_have=float(assembled_cov or 0.0) >= preferred_threshold and len(assembled_missing or []) == 0,
            estimated_time_minutes=int(getattr(assembled, "prep_time_minutes", 0) or 0),
            uses_expiring_items=bool(constraints.use_expiring_items and expiring),
            adjustable_spice_level=True,
        )

        emit_event(
            event_type="recipe.options.fallback",
            user_id=str(user_id),
            entity_type="recipe_options_request",
            entity_id=request_id,
            payload={"requested": int(count), "returned": 1},
        )

        try:
            family_profile_compact = _compact_family_profile(profile if isinstance(profile, dict) else {})
            pantry_context_all = _extract_pantry_context(
                pantry if isinstance(pantry, list) else [],
                prefer_expiring_items=bool(constraints.use_expiring_items),
                expiring_names=expiring,
            )
            image_signals = _build_image_signals(pantry if isinstance(pantry, list) else [])
            _best_effort_persist_recipe_attempt(
                user_id=str(user_id),
                attempt_id=attempt_id,
                payload={
                    "recipe_id": str(getattr(assembled, "recipe_id", "")),
                    "request_text": (req.request_text or ""),
                    "mode": "assembled",
                    "reason": "fallback",
                    "pantry_coverage": float(assembled_cov or 0.0),
                    "locked_constraints": constraints.model_dump(),
                    "family_profile": family_profile_compact,
                    "pantry_context": pantry_context_all,
                    "missing_ingredients": [m.model_dump() for m in (assembled_missing or [])],
                    "recipe": assembled.model_dump(),
                    "image_signals": image_signals,
                    "options_request_id": request_id,
                },
            )
        except Exception:
            pass

        target_language = _requested_translation_target(req)
        i18n = await _translate_canonical_recipe_i18n(
            recipe=assembled,
            target_language=target_language,
            include_steps=True,
        )

        try:
            img = _best_effort_recipe_image_url(
                pantry=pantry if isinstance(pantry, list) else [],
                recipe=assembled,
            )
            if img and str(img).strip():
                assembled.image_url = str(img).strip()
        except Exception:
            pass

        # Enforce full option_count: include the deterministic assembled fallback, then
        # backfill with catalog picks so clients always receive a presentable list.
        fallback_options: list[RecipeGenerateResponse] = [
            RecipeGenerateResponse(
                recipe=assembled,
                locked_constraints=constraints,
                pantry_coverage=float(assembled_cov or 0.0),
                missing_ingredients=list(assembled_missing or []),
                mode="assembled",
                reason="fallback",
                trust_signals=trust,
                i18n=i18n,
            )
        ]

        used_ids = {str(getattr(assembled, "recipe_id", "") or "").strip()}
        _top_up_options_from_catalog(
            options=fallback_options,
            used_ids=used_ids,
            constraints_override=constraints,
            target_count=int(count),
            allow_recent=True,
            max_attempts=200,
            reason="catalog_fallback",
        )

        # Best-effort translate the final list (assembled already has i18n).
        try:
            target_language = _requested_translation_target(req)
            i18n_list = await _translate_canonical_recipes_batch_i18n(
                recipes=[o.recipe for o in fallback_options],
                target_language=target_language,
            )
            for o, i18n_obj in zip(fallback_options, i18n_list):
                o.i18n = i18n_obj
        except Exception:
            pass

        return RecipeGenerateOptionsResponse(options=fallback_options)


@router.get("/attempts", response_model=RecipeAttemptListResponse)
async def list_recipe_attempts(
    saved_only: bool = False,
    limit: int = 25,
    user_id: str = Depends(get_current_user),
):
    db = get_db_client()
    q = db.table("recipe_attempts").select(
        "id,recipe_id,mode,reason,pantry_coverage,missing_ingredients,saved,created_at,recipe"
    )
    q = q.eq("user_id", str(user_id))
    if saved_only:
        q = q.eq("saved", True)
    res = q.order("created_at", desc=True).limit(min(int(limit), 100)).execute()
    rows = res.data or []

    attempts: List[RecipeAttemptRecord] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            missing_raw = r.get("missing_ingredients") or []
            missing_objs = [MissingIngredient(**m) for m in missing_raw] if isinstance(missing_raw, list) else []
            attempts.append(
                RecipeAttemptRecord(
                    id=str(r.get("id")),
                    recipe_id=str(r.get("recipe_id")),
                    mode=str(r.get("mode") or ""),
                    reason=str(r.get("reason") or ""),
                    pantry_coverage=float(r.get("pantry_coverage") or 0.0),
                    missing_ingredients=missing_objs,
                    saved=bool(r.get("saved") or False),
                    created_at=str(r.get("created_at")) if r.get("created_at") else None,
                    recipe=CanonicalRecipe(**(r.get("recipe") or {})),
                )
            )
        except Exception:
            continue

    return RecipeAttemptListResponse(attempts=attempts)


@router.get("/attempts/by_recipe/{recipe_id}", response_model=RecipeAttemptListResponse)
async def list_attempts_by_recipe(
    recipe_id: str,
    limit: int = 5,
    user_id: str = Depends(get_current_user),
):
    db = get_db_client()
    res = (
        db.table("recipe_attempts")
        .select("id,recipe_id,mode,reason,pantry_coverage,missing_ingredients,saved,created_at,recipe")
        .eq("user_id", str(user_id))
        .eq("recipe_id", str(recipe_id))
        .order("created_at", desc=True)
        .limit(min(int(limit), 20))
        .execute()
    )
    rows = res.data or []

    attempts: List[RecipeAttemptRecord] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        try:
            missing_raw = r.get("missing_ingredients") or []
            missing_objs = [MissingIngredient(**m) for m in missing_raw] if isinstance(missing_raw, list) else []
            attempts.append(
                RecipeAttemptRecord(
                    id=str(r.get("id")),
                    recipe_id=str(r.get("recipe_id")),
                    mode=str(r.get("mode") or ""),
                    reason=str(r.get("reason") or ""),
                    pantry_coverage=float(r.get("pantry_coverage") or 0.0),
                    missing_ingredients=missing_objs,
                    saved=bool(r.get("saved") or False),
                    created_at=str(r.get("created_at")) if r.get("created_at") else None,
                    recipe=CanonicalRecipe(**(r.get("recipe") or {})),
                )
            )
        except Exception:
            continue

    return RecipeAttemptListResponse(attempts=attempts)


@router.post("/attempts/{attempt_id}/save", response_model=SaveAttemptResponse)
async def save_recipe_attempt(
    attempt_id: str,
    user_id: str = Depends(get_current_user),
):
    db = get_db_client()
    try:
        db.table("recipe_attempts").update(
            {"saved": True, "saved_at": datetime.now(timezone.utc).isoformat()}
        ).eq("user_id", str(user_id)).eq("id", attempt_id).execute()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save attempt: {e}")
    return SaveAttemptResponse(success=True)


@router.post("/plans", response_model=CreateMealPlanResponse)
async def create_meal_plan(
    req: CreateMealPlanRequest,
    user_id: str = Depends(get_current_user),
):
    if req.plan_type not in {"daily", "weekly", "party"}:
        raise HTTPException(status_code=400, detail="Invalid plan_type")
    if req.meal_type is not None and req.meal_type not in {"breakfast", "lunch", "dinner", "snack", "any"}:
        raise HTTPException(status_code=400, detail="Invalid meal_type")

    attempt_ids = [str(x) for x in (req.attempt_ids or []) if str(x).strip()]
    if not attempt_ids:
        raise HTTPException(status_code=400, detail="attempt_ids is required")

    db = get_db_client()
    try:
        res = (
            db.table("recipe_attempts")
            .select("id,recipe_id,mode,reason,pantry_coverage,missing_ingredients,recipe")
            .eq("user_id", str(user_id))
            .in_("id", attempt_ids)
            .execute()
        )
        rows = res.data or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load attempts: {e}")

    recipes_blob: List[Dict[str, Any]] = []
    missing_lists: List[List[MissingIngredient]] = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        miss_raw = r.get("missing_ingredients") or []
        miss = [MissingIngredient(**m) for m in miss_raw] if isinstance(miss_raw, list) else []
        missing_lists.append(miss)
        recipes_blob.append(
            {
                "attempt_id": str(r.get("id")),
                "recipe_id": str(r.get("recipe_id")),
                "mode": r.get("mode"),
                "reason": r.get("reason"),
                "pantry_coverage": r.get("pantry_coverage"),
                "missing_ingredients": [m.model_dump() for m in miss],
                "recipe": r.get("recipe"),
            }
        )

    if not recipes_blob:
        raise HTTPException(status_code=400, detail="No valid attempts found")

    shopping_list = _combine_missing_ingredients(missing_lists)
    selected_attempt_id = req.selected_attempt_id or str(recipes_blob[0].get("attempt_id"))
    selected_recipe_id = None
    for rb in recipes_blob:
        if str(rb.get("attempt_id")) == str(selected_attempt_id):
            selected_recipe_id = str(rb.get("recipe_id"))
            break
    if not selected_recipe_id:
        selected_recipe_id = str(recipes_blob[0].get("recipe_id"))

    try:
        insert_row = {
            "user_id": str(user_id),
            "plan_type": req.plan_type,
            "plan_date": req.plan_date.isoformat(),
            "meal_type": req.meal_type or "any",
            "selected_cuisine": req.selected_cuisine,
            "servings": int(req.servings),
            "recipes": recipes_blob,
            "selected_recipe_id": str(selected_recipe_id),
            "status": "planned",
            "shopping_list": [m.model_dump() for m in shopping_list],
        }
        created = db.table("meal_plans").insert({k: v for k, v in insert_row.items() if v is not None}).execute().data
        row0 = (created or [None])[0] or {}
        plan_id = str(row0.get("id") or "")
        if not plan_id:
            raise RuntimeError("Missing plan id")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create meal plan: {e}")

    return CreateMealPlanResponse(success=True, plan_id=plan_id, shopping_list=shopping_list)


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def recipe_feedback(
    req: RecipeFeedbackRequest,
    user_id: str = Depends(get_current_user),
):
    ev = (req.event or "").strip()
    if ev not in {"recipe.accepted", "recipe.modified", "recipe.rejected"}:
        raise HTTPException(status_code=400, detail="event must be one of recipe.accepted|recipe.modified|recipe.rejected")

    rid = (req.recipe_id or "").strip()
    if not rid:
        raise HTTPException(status_code=400, detail="recipe_id is required")

    emit_event(
        event_type=ev,
        user_id=str(user_id),
        entity_type="recipe",
        entity_id=rid,
        payload={"signals": req.signals or {}, "ts": _now_iso()},
    )

    return None
