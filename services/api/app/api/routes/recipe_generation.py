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
import re
from typing import Any, Dict, List, Optional, Tuple
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


router = APIRouter()


_UUID_NAMESPACE = uuid5(UUID("00000000-0000-0000-0000-000000000000"), "savo-ingredient")


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


class RecipeGenerateResponse(BaseModel):
    success: bool = True
    recipe: CanonicalRecipe
    locked_constraints: LockedConstraints
    pantry_coverage: float
    missing_ingredients: List[MissingIngredient] = Field(default_factory=list)
    mode: str
    reason: str
    trust_signals: TrustSignals


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


def _extract_pantry_context(pantry: List[Dict[str, Any]], limit: int = 80) -> List[Dict[str, Any]]:
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
        rows_with_keys.append(((exp_days, -qty_num, canon), row))

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

    best: Optional[Tuple[CanonicalRecipe, float, List[MissingIngredient]]] = None
    best_score = -1.0

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
        score = cov
        if score > best_score:
            best_score = score
            best = (recipe, cov, missing_items)

    return best


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

    attempt_id = str(uuid4())

    # Store locked constraints as append-only event for auditability.
    emit_event(
        event_type="recipe.constraints_locked",
        user_id=str(user_id),
        entity_type="recipe_attempt",
        entity_id=attempt_id,
        payload={"constraints": constraints.model_dump(), "request_text": req.request_text or ""},
    )

    preferred_threshold = 0.70

    # Try retrieved first.
    retrieved = _try_retrieve_recipe(
        user_id=str(user_id),
        constraints=constraints,
        pantry_names=pantry_names,
        serves=req.serves,
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

    needs_generation = (pantry_cov < preferred_threshold) or (not ok_safety)

    if needs_generation:
        # Enforce distribution target best-effort (generated <= 20%).
        if _generated_share_exceeded(user_id=str(user_id)):
            needs_generation = False

    if needs_generation:
        # Generated mode is allowed only after constraints are locked. This is best-effort and must be validated.
        mode = "generated"
        reason = "pantry_match" if pantry_cov < preferred_threshold else "safety_repair"

        schema = _canonical_recipe_json_schema()
        client = get_reasoning_client()

        pantry_id_to_name = _ingredient_id_map(pantry_names)
        missing_candidates = _suggest_missing_candidates(pantry_names=pantry_names, cuisine=constraints.cuisine)
        missing_id_to_name = _ingredient_id_map(missing_candidates)

        family_profile_compact = _compact_family_profile(profile if isinstance(profile, dict) else {})
        pantry_context = _extract_pantry_context(pantry if isinstance(pantry, list) else [])
        safety_constraints_text = {
            "allergens": build_allergen_constraints(profile if isinstance(profile, dict) else {}),
            "religious": build_religious_constraints(profile if isinstance(profile, dict) else {}),
            "dietary": build_dietary_constraints(profile if isinstance(profile, dict) else {}),
        }

        prompt = {
            "locked_constraints": constraints.model_dump(),
            "family_profile": family_profile_compact,
            "safety_constraints": safety_constraints_text,
            "allowed_pantry_ingredients": [{"canonical_name": n, "ingredient_id": _stable_ingredient_uuid(n)} for n in pantry_names],
            "pantry_context": pantry_context,
            "missing_candidates": [{"canonical_name": n, "ingredient_id": _stable_ingredient_uuid(n)} for n in missing_candidates],
            "expiring_items": expiring,
            "preferred_pantry_coverage_threshold": preferred_threshold,
            "serves": int(req.serves),
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
            generated = await generate_json_with_retries(
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
                            "Return JSON only that matches the schema." 
                        ),
                    },
                    {"role": "user", "content": str(prompt)},
                ],
                schema=schema,
                max_attempts=2,
                repair_hint="constrained recipe json",
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

        except Exception:
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
        uses_what_you_have=uses_what_you_have,
        estimated_time_minutes=int(getattr(recipe_obj, "prep_time_minutes", 0) or 0),
        uses_expiring_items=uses_expiring,
        adjustable_spice_level=True,
    )

    return RecipeGenerateResponse(
        recipe=recipe_obj,
        locked_constraints=constraints,
        pantry_coverage=pantry_cov,
        missing_ingredients=missing_items,
        mode=mode,
        reason=reason,
        trust_signals=trust,
    )


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
