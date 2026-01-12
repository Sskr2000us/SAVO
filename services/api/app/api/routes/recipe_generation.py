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
import os
import random
import re
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


router = APIRouter()


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
    cuisine: Optional[str] = Field(default=None)
    dietary_tags: List[str] = Field(default_factory=list)
    max_time_minutes: Optional[int] = Field(default=None, ge=1, le=240)
    serves: int = Field(default=2, ge=1, le=12)
    include_inactive_inventory: bool = Field(default=False)
    use_expiring_items: bool = Field(default=False)
    spice_level: Optional[str] = Field(default=None)
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
    cuisine: str
    dietary_tags: List[str]
    prep_time_minutes: int
    difficulty: str
    ingredients: List[CanonicalIngredient]
    techniques: List[str]
    steps: List[str]
    serves: int
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
        cuisine=cuisine,
        dietary_tags=list(constraints.dietary or []),
        prep_time_minutes=int(prep_time),
        difficulty="easy",
        ingredients=ingredients,
        techniques=techniques,
        steps=steps,
        serves=int(serves),
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
    # Load profile + pantry truth
    try:
        profile = await get_full_profile(str(user_id))
    except Exception:
        profile = {}

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
        retrieved = _try_retrieve_recipe(
            user_id=str(user_id),
            constraints=constraints,
            pantry_names=pantry_names,
            serves=req.serves,
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

    # If the user explicitly asked for something (request_text), prefer generating a fresh recipe.
    # Deterministic retrieval/assembly tends to feel repetitive even with good pantry coverage.
    has_request_text = bool((req.request_text or "").strip())
    needs_generation = force_generation or has_request_text or (pantry_cov < preferred_threshold) or (not ok_safety)

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
            "locked_constraints": constraints.model_dump(),
            "family_profile": family_profile_compact,
            "safety_constraints": safety_constraints_text,
            "allowed_pantry_ingredients": [{"canonical_name": n, "ingredient_id": _stable_ingredient_uuid(n)} for n in pantry_names],
            "pantry_context": pantry_context,
            "pantry_image_signals": pantry_image_signals,
            "missing_candidates": [{"canonical_name": n, "ingredient_id": _stable_ingredient_uuid(n)} for n in missing_candidates],
            "expiring_items": expiring,
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
                                "If creative_intent is true, prioritize culturally authentic, regionally-native dishes and avoid generic names (e.g., 'Pantry Bowl'). "
                                "Prefer a specific named dish style appropriate to the cuisine (including sub-region if relevant). "
                                f"\n\nCULTURAL INTELLIGENCE CONTEXT (use as grounding, do not contradict safety/constraints):\n{cultural_intelligence_text}\n"
                                "Return JSON only that matches the schema." 
                            ),
                        },
                        {"role": "user", "content": str(prompt)},
                    ],
                    schema=schema,
                    # For creative requests, prioritize speed. If generation fails,
                    # we fail closed to assembled.
                    max_attempts=2,
                    repair_hint="constrained recipe json",
                    mode_hint="recipe",
                    # Encourage novelty while schema + validators keep structure/safety tight.
                    presence_penalty=0.4 if force_generation else None,
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
    # Load profile + pantry truth
    try:
        profile = await get_full_profile(str(user_id))
    except Exception:
        profile = {}

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

    # Prepare generation prompt
    count = max(1, min(int(req.count or 1), 8))
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
        "locked_constraints": constraints.model_dump(),
        "family_profile": family_profile_compact,
        "safety_constraints": safety_constraints_text,
        "allowed_pantry_ingredients": [{"canonical_name": n, "ingredient_id": _stable_ingredient_uuid(n)} for n in pantry_names],
        "pantry_context": pantry_context,
        "pantry_image_signals": pantry_image_signals,
        "missing_candidates": [{"canonical_name": n, "ingredient_id": _stable_ingredient_uuid(n)} for n in missing_candidates],
        "expiring_items": expiring,
        "preferred_pantry_coverage_threshold": preferred_threshold,
        "serves": int(req.serves),
        "creative_intent": bool(force_generation),
        "cultural_focus_ingredients": focus_ingredients,
        "option_count": int(count),
        "diversity_rules": [
            "return_up_to_option_count_recipes",
            "each_recipe_name_must_be_distinct",
            "vary_dish_type_and_primary_technique_across_options",
            "avoid_generic_names_like_pantry_bowl",
            "keep_each_recipe_compact_ingredients<=12_steps<=7",
        ],
        "hard_constraints": [
            "only_pantry_available_ingredients_or_explicitly_marked_missing",
            "cuisine_logic_must_match",
            "dietary_rules_must_be_enforced",
            "max_cooking_time_must_be_respected",
            "llm_never_decides_constraints_only_fills_structure",
            "ingredient_id_must_come_from_allowed_or_missing_lists_only",
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
                            "Keep each option compact: steps <= 6, ingredient list <= 10. "
                            "If creative_intent is true, prioritize culturally authentic, regionally-native dishes and avoid generic names (e.g., 'Pantry Bowl'). "
                            "Return BETWEEN 3 and option_count recipes if possible; do not fail the whole response if you cannot reach option_count. "
                            f"\n\nCULTURAL INTELLIGENCE CONTEXT (use as grounding, do not contradict safety/constraints):\n{cultural_intelligence_text}\n"
                            "Return JSON only that matches the schema."
                        ),
                    },
                    {"role": "user", "content": str(prompt)},
                ],
                schema=schema,
                max_attempts=2,
                repair_hint="constrained recipe options json",
                mode_hint="recipe",
                presence_penalty=0.5 if force_generation else 0.2,
            ),
            timeout=budget_seconds,
        )

        raw_recipes = generated.get("recipes") if isinstance(generated, dict) else None
        if not isinstance(raw_recipes, list) or not raw_recipes:
            raise ValueError("No recipes returned")

        options: list[RecipeGenerateResponse] = []
        seen_names: set[str] = set()

        for item in raw_recipes:
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

            # Basic dedupe by name
            nm = (recipe_obj.recipe_name or "").strip().lower()
            if not nm or nm in seen_names:
                continue
            seen_names.add(nm)

            ing_ids: List[str] = []
            try:
                for it in (item.get("ingredients") or []):
                    if isinstance(it, dict) and it.get("ingredient_id"):
                        ing_ids.append(str(it.get("ingredient_id")))
            except Exception:
                ing_ids = []

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

        return RecipeGenerateOptionsResponse(
            options=[
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
        )


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
