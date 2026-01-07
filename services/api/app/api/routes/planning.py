"""Planning endpoints - daily/party/weekly meal planning."""

from datetime import date, datetime
import asyncio
import logging
import hashlib
import re
from time import perf_counter
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.planning import (
    DailyPlanRequest,
    PartyPlanRequest,
    WeeklyPlanRequest,
    MenuPlanResponse,
)
from app.models.nutrition import (
    UserNutritionProfile,
    RecipeNutritionEstimate,
    calculate_health_fit_score,
    generate_recipe_badges,
)
from app.models.skill import (
    SkillProgression,
    RecipeSkillFit,
    RecipeDifficulty,
)
from app.models.cuisine import rank_cuisines
from app.core.storage import get_storage
from app.core.orchestrator import plan_daily, plan_party, plan_weekly
from app.core.orchestration_rules import build_orchestration_context
from app.core.cuisine_metadata import get_cuisine_by_id, CUISINE_METADATA
from app.core.database import (
    get_full_profile,
    get_inventory,
    get_recipe_history,
    create_meal_plan,
    get_meal_plan_for_date,
    get_meal_plans,
    delete_latest_meal_plan,
    upsert_household_shopping_items,
)
from app.middleware.auth import get_current_user
from app.core.safety_constraints import (
    build_complete_safety_context,
    validate_recipe_safety,
    SAVOGoldenRule,
    validate_profile_completeness
)
from app.core.ingredient_combinations import (
    analyze_ingredients,
    generate_combination_recipe_prompt,
    IngredientCombinationEngine
)
from app.core.meal_courses import (
    plan_full_course_meal,
    generate_meal_prompt,
    MealStyle
)
from app.models.inventory import InventoryItem

router = APIRouter()

logger = logging.getLogger(__name__)


def _sanitize_recipe_title(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return ""
    s = s.replace("_", " ")
    s = re.sub(r"\s+", " ", s).strip()

    # Strip ingredient-dump suffix patterns like "Dish (A, B, C)".
    m = re.match(r"^(.*)\(([^()]*)\)\s*$", s)
    if m:
        base = (m.group(1) or "").strip()
        inside = (m.group(2) or "").strip()
        if base and inside:
            has_digits = bool(re.search(r"\d", inside))
            looks_like_metadata = bool(
                re.search(
                    r"\b(min|mins|minute|minutes|serves|serving|servings|prep|cook|kcal|calories)\b",
                    inside,
                    flags=re.IGNORECASE,
                )
            )
            parts = [p.strip() for p in inside.split(",") if p.strip()]
            looks_like_list = ("_" in inside) or (len(parts) >= 2)
            if looks_like_list and (not has_digits) and (not looks_like_metadata):
                s = base

    return s.strip()


def _sanitize_recipe_names_in_payload(payload: Any) -> Any:
    if not isinstance(payload, dict):
        return payload
    menus = payload.get("menus")
    if not isinstance(menus, list):
        return payload

    for menu in menus:
        if not isinstance(menu, dict):
            continue
        courses = menu.get("courses")
        if not isinstance(courses, list):
            continue
        for course in courses:
            if not isinstance(course, dict):
                continue
            header = str(course.get("course_header") or "Recipe").strip() or "Recipe"
            opts = course.get("recipe_options")
            if not isinstance(opts, list):
                continue
            for idx, recipe in enumerate(opts):
                if not isinstance(recipe, dict):
                    continue

                rn = recipe.get("recipe_name")
                if isinstance(rn, str):
                    rn = {"en": rn}
                if not isinstance(rn, dict):
                    rn = {}

                cleaned: dict[str, str] = {}
                for k, v in rn.items():
                    if not isinstance(k, str):
                        continue
                    if not isinstance(v, str):
                        continue
                    t = _sanitize_recipe_title(v)
                    if t:
                        cleaned[k.strip().lower() or "en"] = t

                # Guarantee an English title.
                if not cleaned.get("en"):
                    name_fallback = recipe.get("name") if isinstance(recipe.get("name"), str) else ""
                    t = _sanitize_recipe_title(name_fallback)
                    if not t:
                        t = f"{header} {idx + 1}" if header else f"Recipe {idx + 1}"
                    cleaned["en"] = t

                recipe["recipe_name"] = cleaned

    return payload


def _derive_shopping_suggestions_from_plan_payload(
    payload: Dict[str, Any], *, primary_only: bool = True
) -> List[Dict[str, Any]]:
    """Convert recipe new_ingredients_optional into MENU_PLAN_SCHEMA.shopping_suggestions."""

    if not isinstance(payload, dict):
        return []

    suggestions: Dict[str, Dict[str, Any]] = {}

    def _is_optional_reason(reason: str) -> bool:
        r = (reason or "").strip().lower()
        if not r:
            return True
        for needle in ("optional", "if you have", "if available", "can skip", "may omit"):
            if needle in r:
                return True
        return False

    menus = payload.get("menus")
    if not isinstance(menus, list):
        return []

    for menu in menus:
        if not isinstance(menu, dict):
            continue
        courses = menu.get("courses")
        if not isinstance(courses, list):
            continue

        for course in courses:
            if not isinstance(course, dict):
                continue
            opts = course.get("recipe_options")
            if not isinstance(opts, list) or not opts:
                continue
            selected = [opts[0]] if primary_only else opts

            for opt in selected:
                if not isinstance(opt, dict):
                    continue
                new_items = opt.get("new_ingredients_optional")
                if not isinstance(new_items, list) or not new_items:
                    continue

                for raw in new_items:
                    if not isinstance(raw, dict):
                        continue
                    name = (raw.get("canonical_name") or "").strip()
                    if not name:
                        continue
                    unit = str(raw.get("unit") or "").strip()
                    reason = str(raw.get("reason") or "").strip()
                    optional = _is_optional_reason(reason)

                    qty = raw.get("amount")
                    quantity = float(qty) if isinstance(qty, (int, float)) else 0.0

                    key = f"{name.lower().strip()}|{unit.lower().strip()}"
                    existing = suggestions.get(key)
                    if existing is None:
                        suggestions[key] = {
                            "canonical_name": name,
                            "quantity": quantity,
                            "unit": unit,
                            "reason": reason or "Required for selected recipe(s).",
                            "optional": optional,
                        }
                    else:
                        # Sum numeric quantities when possible.
                        try:
                            existing["quantity"] = float(existing.get("quantity") or 0) + quantity
                        except Exception:
                            pass
                        # If any recipe says it's required, treat as required.
                        if existing.get("optional") is True and optional is False:
                            existing["optional"] = False

    # Filter out empty names and ensure required keys exist.
    out: List[Dict[str, Any]] = []
    for v in suggestions.values():
        if not isinstance(v, dict):
            continue
        nm = str(v.get("canonical_name") or "").strip()
        if not nm:
            continue
        out.append(
            {
                "canonical_name": nm,
                "quantity": float(v.get("quantity") or 0),
                "unit": str(v.get("unit") or ""),
                "reason": str(v.get("reason") or ""),
                "optional": bool(v.get("optional")),
            }
        )
    return out


def _merge_shopping_suggestions(
    existing: Any, derived: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    merged: Dict[str, Dict[str, Any]] = {}

    def _add(item: Dict[str, Any]) -> None:
        name = str(item.get("canonical_name") or "").strip()
        unit = str(item.get("unit") or "").strip()
        if not name:
            return
        key = f"{name.lower()}|{unit.lower()}"
        qty = item.get("quantity")
        quantity = float(qty) if isinstance(qty, (int, float)) else 0.0
        optional = bool(item.get("optional"))
        reason = str(item.get("reason") or "").strip()

        if key not in merged:
            merged[key] = {
                "canonical_name": name,
                "quantity": quantity,
                "unit": unit,
                "reason": reason,
                "optional": optional,
            }
            return

        cur = merged[key]
        cur["quantity"] = float(cur.get("quantity") or 0) + quantity
        if cur.get("optional") is True and optional is False:
            cur["optional"] = False
        if not cur.get("reason") and reason:
            cur["reason"] = reason

    if isinstance(existing, list):
        for it in existing:
            if isinstance(it, dict):
                _add(it)
    for it in derived or []:
        if isinstance(it, dict):
            _add(it)

    return list(merged.values())


def _normalize_cuisine_id(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    v = value.strip().lower()
    if not v:
        return None
    # Normalize common UI inputs like "South Indian" -> "south_indian".
    v = v.replace(" ", "_")
    v = v.replace("-", "_")
    # Drop punctuation/diacritics-ish separators into underscores.
    v = re.sub(r"[^a-z0-9_]+", "_", v)
    v = v.strip("_")
    while "__" in v:
        v = v.replace("__", "_")
    return v


def _coerce_menu_headers(payload: Any) -> Any:
    """Coerce payload.menu_headers into the MenuPlanResponse-required List[str].

    Some older saved payloads (and our initial fallback generator) used dicts in
    menu_headers. Pydantic v2 will raise a ValidationError, turning a recoverable
    response into a 500.
    """
    if not isinstance(payload, dict):
        return payload

    raw = payload.get("menu_headers")
    if isinstance(raw, list) and all(isinstance(x, str) and x.strip() for x in raw):
        return payload

    headers: list[str] = []

    def _add_header(s: Any) -> None:
        if isinstance(s, str) and s.strip():
            headers.append(s.strip())

    if isinstance(raw, list):
        for it in raw:
            _add_header(it)
            if isinstance(it, dict):
                meal_type = it.get("meal_type") or it.get("mealType") or it.get("menu_type") or it.get("menuType")
                servings = it.get("servings")
                mt = str(meal_type).strip() if meal_type is not None else "Menu"
                sfx = f" (serves {int(servings)})" if isinstance(servings, (int, float)) else ""
                headers.append(f"{mt.title()}{sfx}")
    elif isinstance(raw, dict):
        meal_type = raw.get("meal_type") or raw.get("mealType") or raw.get("menu_type") or raw.get("menuType")
        servings = raw.get("servings")
        mt = str(meal_type).strip() if meal_type is not None else "Menu"
        sfx = f" (serves {int(servings)})" if isinstance(servings, (int, float)) else ""
        headers.append(f"{mt.title()}{sfx}")

    if not headers:
        menus = payload.get("menus")
        if isinstance(menus, list):
            for m in menus:
                if not isinstance(m, dict):
                    continue
                mt = m.get("meal_type") or m.get("mealType") or m.get("menu_type") or m.get("menuType")
                if isinstance(mt, str) and mt.strip():
                    headers.append(mt.strip().title())

    payload["menu_headers"] = headers or ["Menu"]
    return payload


def _payload_has_recipes(payload: Any) -> bool:
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return False
    menus = payload.get("menus")
    if not isinstance(menus, list) or not menus:
        return False
    for m in menus:
        if not isinstance(m, dict):
            continue
        courses = m.get("courses")
        if not isinstance(courses, list):
            continue
        for c in courses:
            if not isinstance(c, dict):
                continue
            opts = c.get("recipe_options")
            if isinstance(opts, list) and len(opts) >= 1:
                return True
    return False


def _generate_fallback_recipes(
    *,
    inventory: List[InventoryItem],
    household: Dict[str, Any],
    members: List[Dict[str, Any]],
    servings: int,
    time_available: int,
    meal_type: str,
) -> Dict[str, Any]:
    """
    EMERGENCY FALLBACK: Generate simple, safe recipes when LLM fails.
    Uses inventory to suggest practical recipes that users can actually cook.
    """
    from datetime import datetime

    # Pick a display cuisine (best-effort) but keep schema fields correct.
    cuisine = "Indian"
    favs = household.get("favorite_cuisines") or household.get("favoriteCuisines") or []
    if isinstance(favs, list) and favs and isinstance(favs[0], str) and favs[0].strip():
        cuisine = favs[0].strip()

    # Dietary flags (very conservative defaults).
    is_vegetarian = any("vegetarian" in str(m.get("dietary_restrictions", [])).lower() for m in members)
    is_vegan = any("vegan" in str(m.get("dietary_restrictions", [])).lower() for m in members)
    if is_vegan:
        is_vegetarian = True

    inv_items = [i for i in (inventory or []) if getattr(i, "inventory_id", None) and getattr(i, "canonical_name", None)]
    inv_items = inv_items[:8]

    def _display_name(raw: str) -> str:
        s = (raw or "").replace("_", " ")
        s = re.sub(r"\s+", " ", s).strip()
        if not s:
            return raw or ""
        # Title-case each token without touching punctuation inside tokens (e.g., tri-color).
        return " ".join([t[:1].upper() + t[1:] if t else t for t in s.split(" ")])

    def _suggest_amount_and_unit(it: InventoryItem) -> tuple[float, str]:
        name = str(getattr(it, "canonical_name", "") or "").strip().lower()
        qty_raw = getattr(it, "quantity", 0) or 0
        try:
            qty = float(qty_raw)
        except Exception:
            qty = 0.0
        unit = str(getattr(it, "unit", "") or "").strip()
        unit_l = unit.lower()

        # If quantity is missing/unhelpful, default to 1.
        if qty <= 0:
            qty = 1.0

        # Heuristics: avoid "use the whole container" amounts.
        spicey = any(k in name for k in ["cumin", "coriander", "pepper", "chili", "masala", "spice", "seed"]) 
        starchy = any(k in name for k in ["pasta", "noodle", "rice", "rotini", "spaghetti", "penne"])

        if unit_l in {"g", "gram", "grams"}:
            if spicey:
                return (min(qty, 6.0), unit)
            if starchy:
                return (min(qty, 300.0), unit)
            return (min(qty, 200.0), unit)

        if unit_l in {"kg", "kilogram", "kilograms"}:
            if spicey:
                return (min(qty, 0.01), unit)
            if starchy:
                return (min(qty, 0.3), unit)
            return (min(qty, 0.2), unit)

        if unit_l in {"ml", "milliliter", "milliliters"}:
            return (min(qty, 250.0), unit)

        if unit_l in {"l", "liter", "liters"}:
            return (min(qty, 0.25), unit)

        if unit_l in {"pcs", "pc", "piece", "pieces"}:
            # Typically use 1–2 pieces.
            return (min(qty, 2.0), unit)

        # Unknown units: use a conservative fraction.
        return (min(qty, max(1.0, qty * 0.4)), unit)

    def _ingredients_used(max_n: int = 6) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for it in inv_items[:max_n]:
            amt, unit = _suggest_amount_and_unit(it)
            out.append(
                {
                    "inventory_id": str(getattr(it, "inventory_id")),
                    "canonical_name": str(getattr(it, "canonical_name")),
                    "amount": float(amt),
                    "unit": unit or str(getattr(it, "unit", "pcs")),
                }
            )
        return out

    def _health_benefits(ings: list[dict[str, Any]]) -> list[dict[str, str]]:
        # Schema requires objects: {ingredient, benefit}
        benefits: list[dict[str, str]] = []
        for it in ings[:3]:
            ing = str(it.get("canonical_name") or "ingredient")
            benefits.append({"ingredient": ing, "benefit": "Supports a balanced meal."})
        if not benefits:
            benefits.append({"ingredient": "pantry staples", "benefit": "Convenient home cooking."})
        return benefits

    top_names = [str(x.get("canonical_name")) for x in _ingredients_used(3) if isinstance(x, dict) and x.get("canonical_name")]
    top_phrase = ", ".join([_display_name(n) for n in top_names[:3]]) if top_names else "pantry ingredients"

    def _build_fallback_steps(*, cooking_method: str, total_minutes: int) -> list[dict[str, Any]]:
        base = max(12, int(total_minutes or 30))
        method = (cooking_method or "stovetop").strip().lower()
        # Pick a simple template based on pantry signals.
        names_l = " ".join([n.lower() for n in top_names])
        is_pasta = any(k in names_l for k in ["pasta", "rotini", "spaghetti", "penne", "noodle"])
        is_rice = ("rice" in names_l) and not is_pasta

        steps: list[tuple[str, int]] = []
        if is_pasta:
            steps = [
                ("Bring a pot of well-salted water to a boil.", 5),
                ("Cook the pasta until al dente; reserve 1/2 cup pasta water, then drain.", 10),
                (f"Warm a pan on medium heat; toast spices from {top_phrase} for aroma (if present).", 2),
                ("Add a little oil/butter (or any pantry fat) and gently bloom the spices.", 2),
                ("Stir in any nuts/creaminess ingredients (e.g., cashews/avocado) to build a quick sauce.", 4),
                ("Loosen with reserved pasta water until glossy and coating.", 2),
                ("Toss pasta into the sauce; taste and adjust salt/heat/acidity.", 3),
                ("Rest 2 minutes, then serve warm.", 2),
            ]
        elif is_rice:
            steps = [
                ("Rinse rice (if needed) and prep any aromatics/spices.", 5),
                ("Toast spices briefly in a pot with a little oil/butter.", 2),
                ("Add rice and toast 1–2 minutes for nuttiness.", 2),
                ("Add water/broth; bring to a boil, then cover and simmer on low.", 15),
                ("Let rest off-heat 5 minutes.", 5),
                ("Fluff rice; fold in any add-ins from the pantry.", 2),
                ("Taste and adjust seasoning.", 2),
                ("Serve warm with a simple side.", 1),
            ]
        else:
            steps = [
                (f"Prep {top_phrase} (wash/chop/measure).", 6),
                ("Warm a pan/pot on medium heat; add a little oil.", 2),
                ("Cook the main ingredient(s) first to build flavor.", 8),
                ("Add spices/seasoning gradually; stir to coat.", 3),
                ("Add any vegetables or bulk ingredients; cook until tender.", 8),
                ("Adjust texture with a splash of water/broth if needed.", 2),
                ("Taste and balance: salt + heat + acidity (lemon/vinegar if available).", 2),
                ("Serve hot; cool leftovers quickly for storage.", 1),
            ]

        # Scale time minutes roughly to fit the requested total.
        raw_total = sum(t for _, t in steps)
        if raw_total <= 0:
            raw_total = 1
        scale = max(0.5, min(2.0, base / raw_total))
        out: list[dict[str, Any]] = []
        for idx, (txt, mins) in enumerate(steps, start=1):
            out.append(
                {
                    "step": idx,
                    "instruction": {"en": txt},
                    "time_minutes": max(1, int(round(mins * scale))),
                    "tips": [],
                }
            )
        return out

    def _recipe(
        recipe_id: str,
        name_en: str,
        *,
        total_minutes: int,
        cooking_method: str,
        agent_mode: str = "beginner_coach",
    ) -> dict[str, Any]:
        total = max(10, int(total_minutes or 30))
        prep = max(3, int(total * 0.35))
        cook = max(5, total - prep)
        difficulty = "easy" if total <= 30 else ("medium" if total <= 60 else "hard")
        ings = _ingredients_used()
        return {
            "recipe_id": recipe_id,
            "recipe_name": {"en": name_en},
            "cuisine": cuisine,
            "difficulty": difficulty,
            "estimated_times": {"prep_minutes": prep, "cook_minutes": cook, "total_minutes": total},
            "cooking_method": cooking_method,
            "ingredients_used": ings,
            "new_ingredients_optional": [],
            "steps": _build_fallback_steps(cooking_method=cooking_method, total_minutes=total),
            "nutrition_per_serving": {
                "calories_kcal": 350,
                "macros": {"protein_g": 15, "carbs_g": 45, "fat_g": 12},
                "micros": {"fiber_g": 6, "sodium_mg": 600, "sugar_g": 6},
            },
            "health_benefits": _health_benefits(ings),
            "health_fit": {"flags": [], "adjustments": []},
            "leftover_forecast": {"expected_leftover_servings": 0, "reuse_ideas": []},
            "preservation_guidance": {
                "storage": "refrigerate",
                "safe_duration_hours": 24,
                "reheat_methods": ["stovetop", "microwave"],
                "quality_notes": "Best enjoyed fresh; refrigerate leftovers promptly.",
            },
            "chef_tips": ["Taste and adjust salt/spice at the end.", "Use medium heat to avoid burning."],
            "cultural_context": {"origin": cuisine, "occasions": "Everyday meal", "serving": "Family style"},
            "dietary_information": {
                "vegetarian": bool(is_vegetarian or is_vegan),
                "vegan": bool(is_vegan),
                "gluten_free": False,
                "allergens": [],
                "religious_compatibility": [],
            },
            "youtube_references": [],
            "agent_mode": agent_mode,
        }

    # Always return at least 2 recipe_options (schema minItems=2).
    r1 = _recipe(
        "fallback_pantry_meal_1",
        "Pantry Comfort Meal",
        total_minutes=min(int(time_available or 30), 45),
        cooking_method="stovetop",
    )
    r2 = _recipe(
        "fallback_pantry_meal_2",
        "Quick Pantry Stir-Fry",
        total_minutes=min(int(time_available or 25), 35),
        cooking_method="stovetop",
    )

    return {
        "status": "ok",
        "selected_cuisine": cuisine,
        "planning_window": None,
        "menu_headers": [str((meal_type or "dinner")).title()],
        "menus": [
            {
                "menu_type": "daily",
                "day_index": None,
                "date": None,
                "servings": {"count": servings, "scaling_factor": 1},
                "courses": [{"course_header": "Main", "recipe_options": [r1, r2]}],
            }
        ],
        "variety_log": {"rules_applied": ["fallback_mode"]},
        "nutrition_summary": {"total_calories_kcal": 700, "warnings": ["Fallback mode: simplified recipes."]},
        "waste_summary": {
            "expiring_items_used": [],
            "waste_reduction_score": 0.0,
            "waste_avoided_value_estimate": {"currency": "USD", "value": 0.0},
        },
        "shopping_suggestions": [],
        "needs_clarification_questions": [],
        "error_message": None,
        "_generated_at": datetime.utcnow().isoformat(),
        "_fallback_mode": True,
    }


def _generate_fallback_party_plan(
    *,
    inventory: List[InventoryItem],
    household: Dict[str, Any],
    members: List[Dict[str, Any]],
    guest_count: int,
) -> Dict[str, Any]:
    from datetime import datetime

    cuisine = "Indian"
    favs = household.get("favorite_cuisines") or household.get("favoriteCuisines") or []
    if isinstance(favs, list) and favs and isinstance(favs[0], str) and favs[0].strip():
        cuisine = favs[0].strip()

    inv_items = [i for i in (inventory or []) if getattr(i, "inventory_id", None) and getattr(i, "canonical_name", None)]
    inv_items = inv_items[:10]

    def _singular(label: str) -> str:
        s = (label or "").strip()
        if s.lower().endswith("ies") and len(s) > 3:
            return s[:-3] + "y"
        if s.lower().endswith("s") and len(s) > 1:
            return s[:-1]
        return s or "Course"

    def _display_name(raw: str) -> str:
        s = (raw or "").replace("_", " ")
        s = re.sub(r"\s+", " ", s).strip()
        if not s:
            return raw or ""
        return " ".join([t[:1].upper() + t[1:] if t else t for t in s.split(" ")])

    def _suggest_amount_and_unit(it: InventoryItem) -> tuple[float, str]:
        name = str(getattr(it, "canonical_name", "") or "").strip().lower()
        qty_raw = getattr(it, "quantity", 0) or 0
        try:
            qty = float(qty_raw)
        except Exception:
            qty = 0.0
        unit = str(getattr(it, "unit", "") or "").strip()
        unit_l = unit.lower()

        if qty <= 0:
            qty = 1.0

        spicey = any(k in name for k in ["cumin", "coriander", "pepper", "chili", "masala", "spice", "seed"])
        starchy = any(k in name for k in ["pasta", "noodle", "rice", "rotini", "spaghetti", "penne"])

        if unit_l in {"g", "gram", "grams"}:
            if spicey:
                return (min(qty, 6.0), unit)
            if starchy:
                return (min(qty, 350.0), unit)
            return (min(qty, 250.0), unit)

        if unit_l in {"kg", "kilogram", "kilograms"}:
            if spicey:
                return (min(qty, 0.02), unit)
            if starchy:
                return (min(qty, 0.35), unit)
            return (min(qty, 0.25), unit)

        if unit_l in {"pcs", "pc", "piece", "pieces"}:
            return (min(qty, 3.0), unit)

        return (min(qty, max(1.0, qty * 0.5)), unit)

    def _ingredients_used(seed: str, max_n: int = 6) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        if not inv_items:
            return out

        try:
            start = int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % len(inv_items)
        except Exception:
            start = 0

        chosen: list[InventoryItem] = []
        for i in range(min(max_n, len(inv_items))):
            chosen.append(inv_items[(start + i) % len(inv_items)])

        for it in chosen:
            amt, unit = _suggest_amount_and_unit(it)
            out.append(
                {
                    "inventory_id": str(getattr(it, "inventory_id")),
                    "canonical_name": str(getattr(it, "canonical_name")),
                    "amount": float(amt),
                    "unit": unit or str(getattr(it, "unit", "pcs")),
                }
            )
        return out

    def _health_benefits(ings: list[dict[str, Any]]) -> list[dict[str, str]]:
        benefits: list[dict[str, str]] = []
        for it in ings[:3]:
            ing = str(it.get("canonical_name") or "ingredient")
            benefits.append({"ingredient": ing, "benefit": "Adds nutrition and balance to the menu."})
        return benefits or [{"ingredient": "pantry staples", "benefit": "Convenient home cooking."}]

    def _recipe(recipe_id: str, course_label: str, option_idx: int, total_minutes: int) -> dict[str, Any]:
        total = max(10, int(total_minutes or 30))
        prep = max(3, int(total * 0.35))
        cook = max(5, total - prep)
        difficulty = "easy" if total <= 30 else ("medium" if total <= 60 else "hard")
        seed = f"{course_label}:{option_idx}:{recipe_id}"
        ings = _ingredients_used(seed, max_n=6)
        top_names = [str(x.get("canonical_name")) for x in ings[:3] if x.get("canonical_name")]
        top_phrase = ", ".join([_display_name(n) for n in top_names]) if top_names else "pantry ingredients"
        primary = _display_name(top_names[0]) if top_names else ""

        course_singular = _singular(course_label)
        base_name = f"{cuisine}-Style {course_singular}" if cuisine else f"{course_singular}"
        name_en = f"{base_name} with {primary}" if primary else base_name

        cooking_method = "stovetop"
        if course_label.lower().startswith("appet"):
            cooking_method = "no_cook"
        elif course_label.lower().startswith("dess"):
            cooking_method = "no_cook"
        elif course_label.lower().startswith("side"):
            cooking_method = "stovetop"
        elif course_label.lower().startswith("main"):
            cooking_method = "stovetop"

        step2 = "Cook on medium heat; serve warm."
        if cooking_method == "no_cook":
            step2 = "Mix, taste, and serve; chill briefly if desired."
        if course_label.lower().startswith("dess"):
            step2 = "Assemble and chill; serve cold."
        if course_label.lower().startswith("side"):
            step2 = "Season, cook briefly, and serve alongside the main."

        return {
            "recipe_id": recipe_id,
            "recipe_name": {"en": f"{name_en}"},
            "cuisine": cuisine,
            "difficulty": difficulty,
            "estimated_times": {"prep_minutes": prep, "cook_minutes": cook, "total_minutes": total},
            "cooking_method": cooking_method,
            "ingredients_used": ings,
            "new_ingredients_optional": [],
            "steps": [
                {"step": 1, "instruction": {"en": f"Prep {top_phrase}."}, "time_minutes": prep, "tips": []},
                {"step": 2, "instruction": {"en": step2}, "time_minutes": cook, "tips": []},
            ],
            "nutrition_per_serving": {
                "calories_kcal": 320,
                "macros": {"protein_g": 12, "carbs_g": 40, "fat_g": 10},
                "micros": {"fiber_g": 5, "sodium_mg": 650, "sugar_g": 7},
            },
            "health_benefits": _health_benefits(ings),
            "health_fit": {"flags": [], "adjustments": []},
            "leftover_forecast": {"expected_leftover_servings": 0, "reuse_ideas": []},
            "preservation_guidance": {
                "storage": "refrigerate",
                "safe_duration_hours": 24,
                "reheat_methods": ["stovetop", "microwave"],
                "quality_notes": "Refrigerate leftovers promptly.",
            },
            "chef_tips": ["Scale seasoning gradually for guests.", "Keep one mild option if kids are present."],
            "cultural_context": {"origin": cuisine, "occasions": "Party", "serving": "Buffet / family style"},
            "dietary_information": {
                "vegetarian": False,
                "vegan": False,
                "gluten_free": False,
                "allergens": [],
                "religious_compatibility": [],
            },
            "youtube_references": [],
            "agent_mode": "kid_friendly",
        }

    courses = []
    for label in ("Appetizers", "Mains", "Sides", "Desserts"):
        courses.append(
            {
                "course_header": label,
                "recipe_options": [
                    _recipe(f"fallback_party_{label.lower()}_1", label, 1, 35),
                    _recipe(f"fallback_party_{label.lower()}_2", label, 2, 40),
                ],
            }
        )

    return {
        "status": "ok",
        "selected_cuisine": cuisine,
        "planning_window": None,
        "menu_headers": ["Party"],
        "menus": [
            {
                "menu_type": "party",
                "day_index": None,
                "date": None,
                "servings": {"count": guest_count, "scaling_factor": 1},
                "courses": courses,
            }
        ],
        "variety_log": {"rules_applied": ["fallback_mode"]},
        "nutrition_summary": {"total_calories_kcal": 1200, "warnings": ["Fallback mode: simplified party menu."]},
        "waste_summary": {
            "expiring_items_used": [],
            "waste_reduction_score": 0.0,
            "waste_avoided_value_estimate": {"currency": "USD", "value": 0.0},
        },
        "shopping_suggestions": [],
        "needs_clarification_questions": [],
        "error_message": None,
        "_generated_at": datetime.utcnow().isoformat(),
        "_fallback_mode": True,
    }


def _allowed_cuisines_from_profile_and_request(req: Any, household: Any) -> set[str]:
    """Strict allow-list for cuisine selection.

    Priority:
    1) request.cuisine_preferences (explicit user intent)
    2) household favorites/regional cuisines (defaults)
    """
    allow: set[str] = set()

    prefs = getattr(req, "cuisine_preferences", None)
    if isinstance(prefs, list) and prefs:
        for p in prefs:
            cid = _normalize_cuisine_id(p)
            if cid:
                allow.add(cid)
        if allow:
            return allow

    if isinstance(household, dict):
        # Existing schema variants.
        for key in ("favorite_cuisines", "favoriteCuisines", "regional_cuisines", "regionalCuisines"):
            v = household.get(key)
            if isinstance(v, list) and v:
                for p in v:
                    cid = _normalize_cuisine_id(p)
                    if cid:
                        allow.add(cid)

    return allow


def _regional_profile_candidates(regional_profile: Any, *, max_results: int = 8) -> List[Dict[str, Any]]:
    """Recommend candidate cuisines from a regional profile.

    This is intentionally generic: no hard-coded mappings. It uses CUISINE_METADATA
    fields (countries/languages/region/subregion/name/characteristics) to score
    likely fits for the given location/language context.
    """
    if not isinstance(regional_profile, dict) or not regional_profile:
        return []

    def _as_str(x: Any) -> str:
        return x.strip() if isinstance(x, str) else ""

    def _norm_lang(x: str) -> str:
        # Accept BCP47-ish tags (en-US) and underscore variants (en_US).
        raw = x.strip().lower().replace("_", "-")
        if not raw:
            return ""
        return raw.split("-")[0].strip()

    def _lang_keys(value: Any) -> set[str]:
        out: set[str] = set()
        for s in _as_str_list(value):
            raw = s.strip().lower()
            if raw:
                out.add(raw)
            base = _norm_lang(s)
            if base:
                out.add(base)
        return out

    def _country_codes(value: Any) -> set[str]:
        # Prefer ISO-3166 alpha-2 codes, but don't assume inputs are validated.
        out: set[str] = set()
        for s in _as_str_list(value):
            code = s.strip().upper()
            if len(code) == 2 and code.isalpha():
                out.add(code)
        return out

    def _as_str_list(x: Any) -> List[str]:
        if isinstance(x, list):
            return [s.strip() for s in x if isinstance(s, str) and s.strip()]
        if isinstance(x, str) and x.strip():
            return [x.strip()]
        return []

    # Pull generic inputs.
    countries = _country_codes(regional_profile.get("countries") or regional_profile.get("country"))
    languages = _lang_keys(regional_profile.get("languages") or regional_profile.get("language"))

    token_sources = [
        regional_profile.get("region"),
        regional_profile.get("subregion"),
        regional_profile.get("country"),
        regional_profile.get("countries"),
        regional_profile.get("state"),
        regional_profile.get("province"),
        regional_profile.get("city"),
        regional_profile.get("locality"),
        regional_profile.get("area"),
        regional_profile.get("tags"),
    ]
    tokens: List[str] = []
    for src in token_sources:
        if isinstance(src, list):
            tokens.extend([_as_str(s) for s in src])
        else:
            v = _as_str(src)
            if v:
                tokens.append(v)

    # Normalize tokens for substring matching.
    tokens_norm = [re.sub(r"\s+", " ", t).strip().lower() for t in tokens if t.strip()]
    tokens_norm = [t for t in tokens_norm if t and len(t) >= 3]

    scored: List[Dict[str, Any]] = []
    for cuisine_id, meta in CUISINE_METADATA.items():
        if not isinstance(meta, dict):
            continue

        score = 0
        reasons: List[str] = []

        meta_countries = {s.upper() for s in (meta.get("countries") or []) if isinstance(s, str)}
        meta_langs = {s.lower() for s in (meta.get("languages") or []) if isinstance(s, str)}
        meta_lang_names = {s.lower() for s in (meta.get("language_names") or []) if isinstance(s, str)}
        meta_region = (meta.get("region") or "") if isinstance(meta.get("region"), str) else ""
        meta_subregion = (meta.get("subregion") or "") if isinstance(meta.get("subregion"), str) else ""
        meta_name = (meta.get("name") or "") if isinstance(meta.get("name"), str) else ""
        meta_chars = meta.get("characteristics") if isinstance(meta.get("characteristics"), list) else []
        meta_aliases = meta.get("aliases") if isinstance(meta.get("aliases"), list) else []
        meta_keywords = meta.get("keywords") if isinstance(meta.get("keywords"), list) else []
        meta_country_names = meta.get("country_names") if isinstance(meta.get("country_names"), list) else []

        if countries and meta_countries:
            inter = countries & meta_countries
            if inter:
                score += 3
                reasons.append(f"country:{','.join(sorted(inter))}")

        if languages and meta_langs:
            inter = languages & meta_langs
            if inter:
                score += 2
                reasons.append(f"lang:{','.join(sorted(inter))}")

        if languages and meta_lang_names:
            inter = languages & meta_lang_names
            if inter:
                score += 1
                reasons.append(f"lang_name:{','.join(sorted(inter))}")

        hay = " ".join(
            [
                meta_region.lower(),
                meta_subregion.lower(),
                meta_name.lower(),
                " ".join([c.lower() for c in meta_chars if isinstance(c, str)]),
                " ".join([a.lower() for a in meta_aliases if isinstance(a, str)]),
                " ".join([k.lower() for k in meta_keywords if isinstance(k, str)]),
                " ".join([cn.lower() for cn in meta_country_names if isinstance(cn, str)]),
                " ".join(sorted(list(meta_lang_names))),
            ]
        )

        for tok in tokens_norm:
            if tok and tok in hay:
                score += 1
                reasons.append(f"match:{tok}")

        if score <= 0:
            continue

        scored.append(
            {
                "cuisine_id": cuisine_id,
                "name": meta_name or cuisine_id,
                "score": score,
                "reasons": reasons[:6],
            }
        )

    scored.sort(key=lambda x: int(x.get("score", 0)), reverse=True)
    return scored[:max_results]


def _allowed_cuisines_from_regional_profile(household: Any) -> set[str]:
    if not isinstance(household, dict):
        return set()
    rp = household.get("regional_profile")
    candidates = _regional_profile_candidates(rp)
    out: set[str] = set()
    for c in candidates:
        cid = _normalize_cuisine_id(c.get("cuisine_id"))
        if cid:
            out.add(cid)
    return out


def _recipe_cuisine_id(recipe: Any) -> Optional[str]:
    if not isinstance(recipe, dict):
        return None
    for key in ("cuisine_id", "cuisineId", "cuisine"):
        val = recipe.get(key)
        cid = _normalize_cuisine_id(val)
        if cid:
            return cid
    return None


def _enforce_allowed_cuisines_in_payload(payload: Dict[str, Any], allowed: set[str]) -> Dict[str, Any]:
    """Filter recipe options to allowed cuisines.

    Keeps at least one option per course to avoid empty UI.
    """
    if not allowed:
        return payload
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return payload

    menus = payload.get("menus")
    if not isinstance(menus, list) or not menus:
        return payload

    excluded: list[str] = []

    for menu in menus:
        if not isinstance(menu, dict):
            continue
        courses = menu.get("courses")
        if not isinstance(courses, list):
            continue

        for course in courses:
            if not isinstance(course, dict):
                continue
            opts = course.get("recipe_options")
            if not isinstance(opts, list) or not opts:
                continue

            original = list(opts)
            kept: list[dict] = []
            for opt in opts:
                if not isinstance(opt, dict):
                    continue
                cid = _recipe_cuisine_id(opt)
                # If cuisine is missing, keep (LLM sometimes omits it).
                if cid is None or cid in allowed:
                    kept.append(opt)
                else:
                    excluded.append(cid)

            if not kept and original:
                kept = [original[0]]
            course["recipe_options"] = kept

    # Annotate variety_log for transparency/debugging.
    try:
        v = payload.get("variety_log")
        if not isinstance(v, dict):
            v = {"rules_applied": [], "excluded_recent": [], "diversity_scores": {}}
            payload["variety_log"] = v
        rules = v.get("rules_applied")
        if not isinstance(rules, list):
            rules = []
            v["rules_applied"] = rules
        rules.append({"rule": "strict_cuisine_allowlist", "allowed": sorted(list(allowed))})
        if excluded:
            v["excluded_by_cuisine_allowlist"] = sorted(list({c for c in excluded if c}))
    except Exception:
        pass

    return payload


def _recipe_dedupe_key(recipe: Any) -> Optional[str]:
    if not isinstance(recipe, dict):
        return None

    # Prefer name-based keys because LLM outputs often generate unique ids
    # for the same recipe, which makes id-based dedupe ineffective.
    rn = recipe.get("recipe_name")
    if isinstance(rn, dict):
        en = rn.get("en")
        if isinstance(en, str) and en.strip():
            return f"name:{en.strip().lower()}"

    name = recipe.get("name")
    if isinstance(name, str) and name.strip():
        return f"name:{name.strip().lower()}"

    rid = recipe.get("recipe_id") or recipe.get("id")
    if isinstance(rid, str) and rid.strip():
        return f"id:{rid.strip().lower()}"

    # Fallback: try a stable-ish key.
    cuisine = (recipe.get("cuisine") or "").strip().lower() if isinstance(recipe.get("cuisine"), str) else ""
    method = (recipe.get("cooking_method") or "").strip().lower() if isinstance(recipe.get("cooking_method"), str) else ""
    if cuisine or method:
        return f"fallback:{cuisine}|{method}"
    return None


def _dedupe_menu_plan_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort de-duplication of repeated recipe options.

    Prevents the UI from showing the exact same recipe multiple times in a course or across courses.
    """
    if not isinstance(payload, dict):
        return payload

    menus = payload.get("menus")
    if not isinstance(menus, list) or not menus:
        return payload

    seen: set[str] = set()

    for menu in menus:
        if not isinstance(menu, dict):
            continue
        courses = menu.get("courses")
        if not isinstance(courses, list):
            continue

        for course in courses:
            if not isinstance(course, dict):
                continue
            opts = course.get("recipe_options")
            if not isinstance(opts, list) or not opts:
                continue

            original = list(opts)
            new_opts: list[dict] = []
            local_seen: set[str] = set()
            for opt in opts:
                if not isinstance(opt, dict):
                    continue
                key = _recipe_dedupe_key(opt)
                if not key:
                    new_opts.append(opt)
                    continue
                if key in local_seen:
                    continue
                if key in seen:
                    continue
                local_seen.add(key)
                seen.add(key)
                new_opts.append(opt)

            if not new_opts and original:
                # Keep at least one option to avoid empty UI.
                first = original[0]
                if isinstance(first, dict):
                    new_opts = [first]

            course["recipe_options"] = new_opts

    payload["menus"] = menus
    return payload


def _recent_history_keys(history: Any, keep_last_n: int) -> set[str]:
    if not isinstance(history, list) or keep_last_n <= 0:
        return set()

    out: set[str] = set()
    for row in history[:keep_last_n]:
        if not isinstance(row, dict):
            continue
        rn = row.get("recipe_name") or row.get("name")
        if isinstance(rn, str) and rn.strip():
            out.add(f"name:{rn.strip().lower()}")
        rid = row.get("recipe_id") or row.get("id")
        if isinstance(rid, str) and rid.strip():
            out.add(f"id:{rid.strip().lower()}")
    return out


def _exclude_recent_recipes_from_payload(
    payload: Dict[str, Any],
    history: Any,
    *,
    cooldown_last_n: int = 3,
) -> Dict[str, Any]:
    """Exclude recently cooked recipes from the returned menu plan.

    This is a defensive layer on top of prompt-level variety instructions.
    """
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        return payload

    recent_keys = _recent_history_keys(history, cooldown_last_n)
    if not recent_keys:
        return payload

    menus = payload.get("menus")
    if not isinstance(menus, list) or not menus:
        return payload

    excluded: List[str] = []

    for menu in menus:
        if not isinstance(menu, dict):
            continue
        courses = menu.get("courses")
        if not isinstance(courses, list):
            continue

        for course in courses:
            if not isinstance(course, dict):
                continue
            opts = course.get("recipe_options")
            if not isinstance(opts, list) or not opts:
                continue

            original = list(opts)
            kept: list[dict] = []
            for opt in opts:
                if not isinstance(opt, dict):
                    continue
                key = _recipe_dedupe_key(opt)
                if key and key in recent_keys:
                    excluded.append(key)
                    continue
                kept.append(opt)

            if not kept and original:
                # Never return an empty course.
                kept = [original[0]]

            course["recipe_options"] = kept

    # Best-effort: capture exclusions for debugging/analytics.
    try:
        v = payload.get("variety_log")
        if not isinstance(v, dict):
            v = {"rules_applied": [], "excluded_recent": [], "diversity_scores": {}}
            payload["variety_log"] = v
        ex = v.get("excluded_recent")
        if not isinstance(ex, list):
            ex = []
            v["excluded_recent"] = ex
        # Dedup while keeping stable order.
        seen: set[str] = set(ex)
        for k in excluded:
            if k in seen:
                continue
            seen.add(k)
            ex.append(k)
    except Exception:
        pass

    return payload


def _inventory_snapshot_hash(inventory_models: List[InventoryItem]) -> str:
    """Stable-ish hash of current inventory to avoid reusing stale saved plans."""
    parts: list[str] = []
    for item in inventory_models or []:
        try:
            name = (item.canonical_name or "").strip().lower()
            if not name:
                continue
            qty = item.quantity
            unit = (item.unit or "").strip().lower()
            parts.append(f"{name}|{qty}|{unit}")
        except Exception:
            continue
    parts.sort()
    raw = "\n".join(parts).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _normalize_cuisine_preference(value: Any) -> Optional[str]:
    """Normalize cuisine inputs (ids/names/case) to the display names used by rank_cuisines."""
    if not isinstance(value, str):
        return None
    raw = value.strip()
    if not raw:
        return None

    raw_lower = raw.lower().replace("-", "_")

    # If the client sends cuisine_id (e.g. 'indian'), map to display name.
    meta = CUISINE_METADATA.get(raw_lower)
    if isinstance(meta, dict) and isinstance(meta.get("name"), str):
        return meta["name"].strip()

    # Otherwise normalize case-insensitively against known cuisine names.
    for cuisine_id, data in CUISINE_METADATA.items():
        name = data.get("name") if isinstance(data, dict) else None
        if isinstance(name, str) and name.strip().lower() == raw_lower:
            return name.strip()

    # Fallback: title-case (best effort)
    return raw[:1].upper() + raw[1:]


def _normalize_cuisine_preferences(values: Any) -> Optional[List[str]]:
    if not isinstance(values, list) or not values:
        return None
    out: List[str] = []
    seen = set()
    for v in values:
        norm = _normalize_cuisine_preference(v)
        if not norm:
            continue
        key = norm.lower()
        if key in seen:
            continue
        out.append(norm)
        seen.add(key)
    return out or None


def _coerce_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _parse_iso_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        # Accept "YYYY-MM-DD" or datetime-ish strings
        try:
            return date.fromisoformat(raw[:10])
        except Exception:
            return None
    return None


def _freshness_days_remaining(expiry_date_value: Any) -> Optional[int]:
    expiry = _parse_iso_date(expiry_date_value)
    if expiry is None:
        return None
    delta = (expiry - date.today()).days
    return max(0, delta)


def _db_inventory_to_models(db_items: List[Dict[str, Any]]) -> List[InventoryItem]:
    mapped: List[InventoryItem] = []
    for item in db_items or []:
        if not isinstance(item, dict):
            continue

        raw_state = (item.get("item_state") or item.get("state") or "raw")
        state = "raw"
        if isinstance(raw_state, str):
            s = raw_state.strip().lower()
            if s in {"raw", "cooked", "leftover", "frozen"}:
                state = s
            elif s == "prepared":
                state = "cooked"

        raw_storage = (item.get("storage_location") or item.get("storage") or "pantry")
        storage = "pantry"
        if isinstance(raw_storage, str):
            st = raw_storage.strip().lower()
            if st in {"pantry", "fridge", "freezer"}:
                storage = "fridge" if st == "fridge" else st
            elif st == "counter":
                storage = "pantry"

        inventory_id = item.get("id") or item.get("inventory_id")
        canonical_name = item.get("canonical_name")
        display_name = item.get("display_name") or canonical_name
        quantity = item.get("quantity")
        unit = item.get("unit")

        if not inventory_id or not canonical_name or quantity is None or not unit:
            continue

        mapped.append(
            InventoryItem(
                inventory_id=str(inventory_id),
                canonical_name=str(canonical_name),
                display_name=str(display_name) if display_name is not None else None,
                quantity=float(quantity),
                unit=str(unit),
                state=state,  # type: ignore[arg-type]
                storage=("freezer" if storage == "freezer" else ("fridge" if storage == "fridge" else "pantry")),
                freshness_days_remaining=_freshness_days_remaining(item.get("expiry_date")),
                notes=item.get("notes"),
            )
        )
    return mapped


def _member_for_app_config(member: Dict[str, Any]) -> Dict[str, Any]:
    # Shape this like app.models.config.FamilyMember (dict form)
    member_id = member.get("id") or member.get("member_id") or "unknown"
    age = member.get("age")
    try:
        age_int = int(age) if age is not None else 30
    except Exception:
        age_int = 30

    age_category = member.get("age_category")
    if not isinstance(age_category, str) or age_category not in {"child", "teen", "adult", "senior"}:
        if age_int < 13:
            age_category = "child"
        elif age_int < 18:
            age_category = "teen"
        elif age_int < 65:
            age_category = "adult"
        else:
            age_category = "senior"

    return {
        "member_id": str(member_id),
        "name": str(member.get("name") or member.get("member_name") or "Family Member"),
        "age": age_int,
        "age_category": age_category,
        "dietary_restrictions": [str(x) for x in _coerce_list(member.get("dietary_restrictions")) if x is not None],
        "allergens": [str(x) for x in _coerce_list(member.get("allergens")) if x is not None],
        "health_conditions": [str(x) for x in _coerce_list(member.get("health_conditions")) if x is not None],
        "medical_dietary_needs": member.get("medical_dietary_needs") or {},
        "food_preferences": [str(x) for x in _coerce_list(member.get("food_preferences")) if x is not None],
        "food_dislikes": [str(x) for x in _coerce_list(member.get("food_dislikes")) if x is not None],
        "spice_tolerance": str(member.get("spice_tolerance") or "medium"),
    }


def _inventory_for_llm(*, storage_inventory, request_inventory) -> list[dict]:
    """Return inventory in the prompt-pack friendly shape.

    The prompt pack expects inventory items like:
    {inventory_id, canonical_name, amount, unit, ...}
    """
    if isinstance(request_inventory, dict):
        available = request_inventory.get("available_ingredients")
        if isinstance(available, list) and available:
            items: list[dict] = []
            for i, name in enumerate(available, start=1):
                if not isinstance(name, str) or not name.strip():
                    continue
                canonical = name.strip()
                items.append(
                    {
                        "inventory_id": f"req_{i}",
                        "canonical_name": canonical,
                        "display_name": canonical,
                        "amount": 1,
                        "unit": "pcs",
                        "state": "raw",
                        "storage": "pantry",
                        "freshness_days_remaining": None,
                        "notes": None,
                    }
                )
            return items

        items_payload = request_inventory.get("items")
        if isinstance(items_payload, list) and items_payload:
            return [i for i in items_payload if isinstance(i, dict)]

    # Default: map storage inventory model -> prompt-pack keys
    mapped: list[dict] = []
    for item in storage_inventory:
        mapped.append(
            {
                "inventory_id": getattr(item, "inventory_id", None),
                "canonical_name": getattr(item, "canonical_name", None),
                "display_name": getattr(item, "display_name", None) or getattr(item, "canonical_name", None),
                "amount": getattr(item, "quantity", None),
                "unit": getattr(item, "unit", None),
                "state": getattr(item, "state", "raw"),
                "storage": getattr(item, "storage", "pantry"),
                "freshness_days_remaining": getattr(item, "freshness_days_remaining", None),
                "notes": getattr(item, "notes", None),
            }
        )
    return mapped


def _enhance_recipe_with_intelligence(
    recipe: dict,
    nutrition_profile,
    user_skill_level: int,
    user_confidence: float,
    meal_type: str
):
    """Enhance recipe with nutrition scores, skill fit, and badges"""
    # Extract recipe details
    recipe_time = recipe.get("estimated_time_minutes", 30)
    recipe_difficulty = recipe.get("difficulty_level", 2)
    
    # Intelligence Layer: Nutrition Scoring
    if nutrition_profile:
        # Estimate nutrition from recipe (simplified - in production, use actual nutrition data)
        nutrition_estimate = RecipeNutritionEstimate(
            calories=recipe.get("calories", 400),
            protein_g=recipe.get("protein", 20),
            carbs_g=recipe.get("carbs", 40),
            fat_g=recipe.get("fat", 15),
            sodium_mg=recipe.get("sodium", 600),
            sugar_g=recipe.get("sugar", 8),
            fiber_g=recipe.get("fiber", 5)
        )
        
        # Calculate health fit score
        nutrition_scoring = calculate_health_fit_score(
            nutrition_estimate=nutrition_estimate,
            user_profile=nutrition_profile,
            meal_type=meal_type
        )
        
        # Add to recipe
        recipe["nutrition_intelligence"] = {
            "health_fit_score": nutrition_scoring.health_fit_score,
            "eligibility": nutrition_scoring.eligibility,
            "explanation": nutrition_scoring.explanation,
            "positive_flags": nutrition_scoring.positive_flags,
            "warning_flags": nutrition_scoring.warning_flags
        }
    else:
        recipe["nutrition_intelligence"] = {
            "health_fit_score": 0.75,
            "eligibility": "recommended",
            "explanation": "Good nutritional balance for general health.",
            "positive_flags": ["balanced"],
            "warning_flags": []
        }
    
    # Intelligence Layer: Skill Fit Evaluation
    recipe_skill = RecipeDifficulty(
        level=recipe_difficulty,
        level_name=RecipeDifficulty.get_level_name(recipe_difficulty),
        skills_required=recipe.get("skills_required", ["basic_cooking"]),
        estimated_time_minutes=recipe_time,
        active_time_minutes=int(recipe_time * 0.6)
    )
    
    skill_fit = RecipeSkillFit.evaluate_fit(
        user_level=user_skill_level,
        user_confidence=user_confidence,
        recipe_difficulty=recipe_skill
    )
    
    recipe["skill_intelligence"] = {
        "fit_category": skill_fit.fit_category,
        "confidence_match": skill_fit.confidence_match,
        "recommendation": skill_fit.recommendation,
        "encouragement": skill_fit.encouragement
    }
    
    # Intelligence Layer: Generate Badges (max 3)
    badges = generate_recipe_badges(
        nutrition_scoring=nutrition_scoring if nutrition_profile else None,
        difficulty_level=recipe_difficulty,
        time_minutes=recipe_time
    )
    
    recipe["badges"] = [
        {
            "type": badge.badge_type,
            "label": badge.label,
            "priority": badge.priority,
            "explanation": badge.explanation
        }
        for badge in badges[:3]  # Max 3 badges
    ]
    
    # Build "Why This Recipe?" explanation
    why_sections = []
    
    # Health section
    if nutrition_profile:
        why_sections.append({
            "icon": "health",
            "title": "Health",
            "content": recipe["nutrition_intelligence"]["explanation"]
        })
    
    # Skill section
    why_sections.append({
        "icon": "skill",
        "title": "Skill",
        "content": recipe["skill_intelligence"]["recommendation"]
    })
    
    # Cuisine section (if available)
    if recipe.get("cuisine"):
        why_sections.append({
            "icon": "cuisine",
            "title": "Cuisine",
            "content": f"{recipe['cuisine']} cuisine fits your available ingredients and preferences."
        })
    
    # Time section
    if recipe_time <= 30:
        why_sections.append({
            "icon": "time",
            "title": "Time",
            "content": f"Quick meal ready in {recipe_time} minutes."
        })
    
    recipe["why_this_recipe"] = why_sections


def _build_planning_context(
    request,
    plan_type: str,
    party_settings=None,
    weekly_context=None,
    *,
    config_override=None,
    inventory_override=None,
    history_override=None,
    app_configuration_override: Optional[Dict[str, Any]] = None,
):
    """Build complete context for LLM including config, inventory, orchestration rules, and intelligence layers"""
    storage = get_storage()
    config = config_override or storage.get_config()
    inventory = inventory_override if inventory_override is not None else storage.list_inventory()
    history = history_override if history_override is not None else storage.get_recent_history()
    
    # Get selected cuisine or rank cuisines intelligently
    cuisine = request.selected_cuisine or "auto"
    cuisine_meta = get_cuisine_by_id(cuisine) if cuisine != "auto" else None
    
    # Intelligence Layer 1: Cuisine Ranking
    cuisine_scores = []
    if cuisine == "auto":
        # Rank cuisines based on ingredients, preferences, history, skill, nutrition
        available_ingredients = [item.canonical_name for item in inventory]
        user_preferences = _normalize_cuisine_preferences(request.cuisine_preferences) or []
        recent_cuisines = [h.get("cuisine", "") for h in history[:10] if h.get("cuisine")]
        
        # Get user skill level from config
        user_skill_level = 2  # Default to basic
        if config and config.household_profile and hasattr(config.household_profile, "skill_level"):
            user_skill_level = config.household_profile.skill_level or 2
        
        # Get nutrition focus
        nutrition_focus = []
        if config and config.household_profile and hasattr(config.household_profile, "nutrition_targets"):
            targets = config.household_profile.nutrition_targets
            if hasattr(targets, "protein_g") and targets.protein_g > 100:
                nutrition_focus.append("high_protein")
            if hasattr(targets, "sugar_g") and targets.sugar_g < 25:
                nutrition_focus.append("low_sugar")
        
        # Rank cuisines
        cuisine_scores = rank_cuisines(
            available_ingredients=available_ingredients,
            user_preferences=user_preferences,
            recent_cuisines=recent_cuisines,
            skill_level=user_skill_level,
            nutrition_focus=nutrition_focus
        )

        # If the user specified cuisine preferences, restrict the ranking hints to that set.
        if user_preferences:
            preferred_lower = {p.lower() for p in user_preferences}
            cuisine_scores = [s for s in cuisine_scores if getattr(s, "cuisine", "").lower() in preferred_lower]
    
    # Build orchestration context
    orch_context = build_orchestration_context(
        config=config,
        inventory=inventory,
        history=history,
        plan_type=plan_type,
        party_settings=party_settings,
        weekly_context=weekly_context
    )

    # Surface leftover inventory explicitly for the prompt pack.
    try:
        leftover_ids = [
            getattr(i, "inventory_id", None)
            for i in inventory
            if getattr(i, "state", None) == "leftover"
        ]
        leftover_ids = [x for x in leftover_ids if x]
        if isinstance(orch_context, dict):
            rules_ctx = orch_context.get("orchestration_rules")
            if isinstance(rules_ctx, dict):
                rules_ctx["leftover_inventory_ids"] = leftover_ids
    except Exception:
        # Best-effort only; planning should still function without leftovers metadata.
        pass
    
    # Determine output settings
    # Prefer explicit request overrides, then DB-backed app_configuration_override (if present), then local config defaults.
    def _cfg_get(path: list[str], default: Any = None) -> Any:
        cur: Any = app_configuration_override if isinstance(app_configuration_override, dict) else None
        for key in path:
            if not isinstance(cur, dict):
                return default
            cur = cur.get(key)
        return default if cur is None else cur

    # Household/profile language preferences may live under db_profile.household
    # depending on which client created the profile. Keep this best-effort and
    # do not assume a single canonical key.
    def _preferred_profile_language() -> Optional[str]:
        for path in (
            ["db_profile", "household", "preferred_language"],
            ["db_profile", "household", "preferredLanguage"],
            ["db_profile", "household", "primary_language"],
            ["db_profile", "household", "primaryLanguage"],
            ["db_profile", "household", "language"],
            ["db_profile", "household", "languageCode"],
        ):
            v = _cfg_get(path, None)
            if isinstance(v, str) and v.strip():
                return v.strip()
        return None

    output_lang = (
        getattr(request, "output_language", None)
        or _preferred_profile_language()
        or _cfg_get(["global_settings", "primary_language"], None)
        or config.global_settings.primary_language
    )
    measurement = (
        getattr(request, "measurement_system", None)
        or _cfg_get(["global_settings", "measurement_system"], None)
        or config.global_settings.measurement_system
    )

    output_languages = getattr(request, "output_languages", None)
    if not isinstance(output_languages, list) or not output_languages:
        # If the household has a preferred language and the request didn't include
        # output_languages, generate bilingual by default (en + preferred).
        pref = _preferred_profile_language()
        if isinstance(pref, str) and pref.strip() and pref.strip() != "en":
            # Use the preferred language as the primary output language unless the
            # request explicitly set a different output_language.
            if not getattr(request, "output_language", None):
                output_lang = pref.strip()
            output_languages = ["en", output_lang]
        else:
            output_languages = ["en"] if output_lang == "en" else ["en", output_lang]
    else:
        # Ensure english-first ordering and ensure the primary output language is present.
        normalized = [x for x in output_languages if isinstance(x, str) and x.strip()]
        if "en" in normalized:
            normalized = ["en"] + [l for l in normalized if l != "en"]
        else:
            normalized = ["en"] + normalized
        if output_lang and output_lang not in normalized:
            normalized.append(output_lang)
        output_languages = normalized
    
    inventory_items = _inventory_for_llm(storage_inventory=inventory, request_inventory=getattr(request, "inventory", None))

    # Keep prompts small to avoid TPM rate limits and long latencies.
    def _compact_inventory(items: Any, *, max_items: int = 60) -> list[dict[str, Any]]:
        if not isinstance(items, list):
            return []
        kept: list[dict[str, Any]] = []
        for it in items:
            if isinstance(it, dict):
                kept.append(it)

        def _score(d: dict[str, Any]) -> tuple[int, int, float]:
            # Higher priority first: leftovers, expiring soon, higher confidence
            state = str(d.get("state") or "").strip().lower()
            is_leftover = 1 if state == "leftover" else 0
            days = d.get("freshness_days_remaining")
            expiring = 0
            if isinstance(days, int) and days >= 0:
                expiring = 1 if days <= 2 else 0
            conf = d.get("confidence")
            conf_f = float(conf) if isinstance(conf, (int, float)) else 0.0
            return (is_leftover, expiring, conf_f)

        kept.sort(key=_score, reverse=True)
        kept = kept[:max_items]

        # Drop very verbose/low-signal keys if present.
        drop_keys = {
            "raw_text",
            "notes",
            "source",
            "created_at",
            "updated_at",
        }
        out: list[dict[str, Any]] = []
        for it in kept:
            slim = {k: v for k, v in it.items() if k not in drop_keys}
            out.append(slim)
        return out

    inventory_items = _compact_inventory(inventory_items)

    leftovers_inventory: list[dict] = []
    try:
        for item in inventory_items or []:
            if not isinstance(item, dict):
                continue
            state = item.get("state")
            if isinstance(state, str) and state.strip().lower() == "leftover":
                leftovers_inventory.append(item)
    except Exception:
        leftovers_inventory = []

    leftovers_expiring_soon: list[dict] = []
    for item in leftovers_inventory:
        days = item.get("freshness_days_remaining")
        if isinstance(days, int) and days <= 2:
            leftovers_expiring_soon.append(item)

    context = {
        "app_configuration": app_configuration_override or config.model_dump(mode='json'),
        "session_request": request.model_dump(mode='json'),
        "inventory": inventory_items,
        "leftovers_inventory": leftovers_inventory,
        "leftovers_summary": {
            "count": len(leftovers_inventory),
            "expiring_soon_count": len(leftovers_expiring_soon),
        },
        # Provide a compact cuisine metadata view (full CUISINE_METADATA is very large).
        "cuisine_metadata": {},
        "cuisine_rankings": [score.model_dump() for score in cuisine_scores[:5]],  # Top 5 cuisines
        "history_context": {
            # Keep only a compact view of recent history to avoid huge prompts.
            "recent_recipes": [],
        },
        "output_language": output_lang,
        "output_languages": output_languages,
        "measurement_system": measurement,
        "now_utc": datetime.utcnow().isoformat(),
        **orch_context
    }

    # Fill compact cuisine metadata for the cuisines most likely to be used.
    try:
        candidate_ids: list[str] = []
        # Include top-ranked cuisines.
        for s in cuisine_scores[:8]:
            cid = getattr(s, "cuisine", None)
            if isinstance(cid, str) and cid.strip():
                candidate_ids.append(cid.strip())
        # Include explicit preferences.
        prefs = _normalize_cuisine_preferences(getattr(request, "cuisine_preferences", None)) or []
        candidate_ids.extend([p for p in prefs if isinstance(p, str) and p.strip()])
        # Include selected cuisine if set.
        if isinstance(cuisine, str) and cuisine.strip() and cuisine != "auto":
            candidate_ids.append(cuisine.strip())

        # De-dupe preserving order.
        seen: set[str] = set()
        candidate_ids = [c for c in candidate_ids if not (c in seen or seen.add(c))]

        def _compact_meta(meta: Any) -> dict[str, Any]:
            if not isinstance(meta, dict):
                return {}
            keep = (
                "name",
                "region",
                "subregion",
                "countries",
                "country_names",
                "languages",
                "language_names",
                "daily_structure",
                "party_structure",
                "characteristics",
                "keywords",
                "aliases",
            )
            out = {k: meta.get(k) for k in keep if k in meta}
            return out

        compact_map: dict[str, Any] = {}
        for cid in candidate_ids[:12]:
            m = CUISINE_METADATA.get(cid)
            if isinstance(m, dict):
                compact_map[cid] = _compact_meta(m)
        context["cuisine_metadata"] = compact_map
    except Exception:
        # Best-effort only.
        pass

    # Compact history (drop large payloads; keep only key fields).
    try:
        slim_hist: list[dict[str, Any]] = []
        for h in history[:20] if isinstance(history, list) else []:
            if not isinstance(h, dict):
                continue
            slim_hist.append(
                {
                    "recipe_id": h.get("recipe_id") or h.get("id"),
                    "recipe_name": h.get("recipe_name") or h.get("name"),
                    "cuisine": h.get("cuisine"),
                    "cooked_at": h.get("cooked_at") or h.get("created_at") or h.get("date"),
                }
            )
        context["history_context"]["recent_recipes"] = slim_hist
    except Exception:
        pass

    # Provide prompt-pack bindings for time/servings when present.
    # (Prompt-pack tasks reference {{TIME_AVAILABLE_MIN}} and {{SERVINGS}} explicitly.)
    try:
        tmin = getattr(request, "time_available_minutes", None)
        if isinstance(tmin, (int, float)):
            context["time_available_minutes"] = tmin
            context["TIME_AVAILABLE_MIN"] = tmin
        srv = getattr(request, "servings", None)
        if isinstance(srv, (int, float)):
            context["servings"] = srv
            context["SERVINGS"] = srv
    except Exception:
        pass

    # Explicit family profile summary (small, high-signal) so the model reliably applies it.
    # Source of truth is DB profile if present: app_configuration.db_profile.{household,members}.
    try:
        app_cfg = context.get("app_configuration")
        db_profile = app_cfg.get("db_profile") if isinstance(app_cfg, dict) else None
        household = db_profile.get("household") if isinstance(db_profile, dict) else None
        members = db_profile.get("members") if isinstance(db_profile, dict) else None

        if not isinstance(members, list):
            members = []
        if not isinstance(household, dict):
            household = {}

        # Aggregate constraints across members (conservative: union allergens, union dietary).
        allergens: set[str] = set()
        dietary: set[str] = set()
        religious: set[str] = set()
        health_conditions: set[str] = set()
        spice_levels: list[str] = []

        for m in members:
            if not isinstance(m, dict):
                continue
            for a in _coerce_list(m.get("allergens")):
                if a is None:
                    continue
                s = str(a).strip()
                if s:
                    allergens.add(s.lower())
            for d in _coerce_list(m.get("dietary_restrictions")):
                if d is None:
                    continue
                s = str(d).strip()
                if s:
                    dietary.add(s.lower())
            for h in _coerce_list(m.get("health_conditions")):
                if h is None:
                    continue
                s = str(h).strip()
                if s:
                    health_conditions.add(s.lower())
            st = m.get("spice_tolerance")
            if isinstance(st, str) and st.strip():
                spice_levels.append(st.strip().lower())

        # Household-level religious constraints may be represented in dietary or household JSON.
        for r in _coerce_list(household.get("religious_constraints") or household.get("religious") or []):
            if r is None:
                continue
            s = str(r).strip()
            if s:
                religious.add(s)

        # Meal preferences: prefer explicit app_configuration_override.global_settings, then DB household.
        global_settings = app_cfg.get("global_settings") if isinstance(app_cfg, dict) else None

        def _pref_dict(val: Any) -> Dict[str, Any]:
            if isinstance(val, dict):
                return val
            if isinstance(val, list):
                # Legacy/UI variant: treat first string as style.
                for x in val:
                    if isinstance(x, str) and x.strip():
                        return {"style": x.strip().lower()}
                return {}
            if isinstance(val, str) and val.strip():
                return {"style": val.strip().lower()}
            return {}

        def _get_first(*values: Any) -> Any:
            for v in values:
                if v is None:
                    continue
                if isinstance(v, (dict, list)) and len(v) == 0:
                    continue
                if isinstance(v, str) and not v.strip():
                    continue
                return v
            return None

        breakfast_pref = _pref_dict(
            _get_first(
                (global_settings or {}).get("breakfast_preferences") if isinstance(global_settings, dict) else None,
                household.get("breakfast_preferences"),
                household.get("breakfastPreferences"),
                household.get("breakfast_style"),
                household.get("breakfastStyle"),
            )
        )
        lunch_pref = _pref_dict(
            _get_first(
                (global_settings or {}).get("lunch_preferences") if isinstance(global_settings, dict) else None,
                household.get("lunch_preferences"),
                household.get("lunchPreferences"),
                household.get("lunch_style"),
                household.get("lunchStyle"),
            )
        )
        dinner_pref = _pref_dict(
            _get_first(
                (global_settings or {}).get("dinner_preferences") if isinstance(global_settings, dict) else None,
                household.get("dinner_preferences"),
                household.get("dinnerPreferences"),
                household.get("dinner_style"),
                household.get("dinnerStyle"),
            )
        )

        dinner_courses = None
        for raw in (
            household.get("dinner_courses"),
            household.get("dinnerCourses"),
            dinner_pref.get("courses") if isinstance(dinner_pref, dict) else None,
        ):
            if raw is None:
                continue
            try:
                dinner_courses = int(raw)
                break
            except Exception:
                continue
        if dinner_courses is None:
            try:
                if isinstance(global_settings, dict):
                    dc = (global_settings.get("dinner_preferences") or {}).get("courses")
                    if dc is not None:
                        dinner_courses = int(dc)
            except Exception:
                dinner_courses = None

        family_profile = {
            "primary_language": household.get("primary_language") or household.get("language") or output_lang,
            "measurement_system": household.get("measurement_system") or measurement,
            "favorite_cuisines": household.get("favorite_cuisines") or household.get("favoriteCuisines") or [],
            "regional_profile": household.get("regional_profile") or {},
            "meal_preferences": {
                "breakfast": breakfast_pref,
                "lunch": lunch_pref,
                "dinner": dinner_pref,
                "dinner_courses": dinner_courses,
            },
            "members_count": len([m for m in members if isinstance(m, dict)]),
            "age_groups": {
                "child": len([m for m in members if isinstance(m, dict) and (m.get("age_category") == "child")]),
                "teen": len([m for m in members if isinstance(m, dict) and (m.get("age_category") == "teen")]),
                "adult": len([m for m in members if isinstance(m, dict) and (m.get("age_category") == "adult")]),
                "senior": len([m for m in members if isinstance(m, dict) and (m.get("age_category") == "senior")]),
            },
            "hard_constraints": {
                "avoid_allergens": sorted(allergens),
                "dietary_restrictions": sorted(dietary),
                "religious_constraints": sorted(religious),
                "health_conditions": sorted(health_conditions),
                "spice_tolerance_levels": spice_levels,
            },
        }

        context["family_profile"] = family_profile
        context["FAMILY_PROFILE"] = family_profile
    except Exception:
        # Best-effort; do not fail planning if profile summarization fails.
        pass

    # Surface household regional profile for culturally authentic planning.
    # Stored on household_profiles as JSONB.
    try:
        app_cfg = context.get("app_configuration")
        household = None
        if isinstance(app_cfg, dict):
            db_profile = app_cfg.get("db_profile")
            if isinstance(db_profile, dict) and isinstance(db_profile.get("household"), dict):
                household = db_profile.get("household")
            else:
                household = app_cfg.get("household_profile") or app_cfg.get("household")
        if isinstance(household, dict):
            regional_profile = household.get("regional_profile")
            if isinstance(regional_profile, dict) and regional_profile:
                context["regional_profile"] = regional_profile
    except Exception:
        pass

    # Prompt-pack compatibility aliases.
    # The prompt instructions refer to UPPERCASE bindings like SESSION_REQUEST and INVENTORY.
    # Our context JSON is lower_snake_case; provide aliases so the model reliably finds inputs.
    try:
        context["APP_CONFIGURATION"] = context.get("app_configuration")
        context["SESSION_REQUEST"] = context.get("session_request")
        context["INVENTORY"] = context.get("inventory")
        context["CUISINE_METADATA"] = context.get("cuisine_metadata")
        context["HISTORY_CONTEXT"] = context.get("history_context")
        context["OUTPUT_LANGUAGE"] = context.get("output_language")
        context["MEASUREMENT_SYSTEM"] = context.get("measurement_system")
        context["NOW_UTC"] = context.get("now_utc")
        # Ensure bindings exist even if callers set only snake_case.
        if "TIME_AVAILABLE_MIN" not in context and "time_available_minutes" in context:
            context["TIME_AVAILABLE_MIN"] = context.get("time_available_minutes")
        if "SERVINGS" not in context and "servings" in context:
            context["SERVINGS"] = context.get("servings")
        if "regional_profile" in context:
            context["REGIONAL_PROFILE"] = context.get("regional_profile")
        if "feature_flags" in context:
            context["FEATURE_FLAGS"] = context.get("feature_flags")
    except Exception:
        pass
    
    return context


@router.post("/daily", response_model=MenuPlanResponse)
async def post_daily(
    req: DailyPlanRequest,
    user_id: str = Depends(get_current_user),
    force_regenerate: bool = False,
):
    """Generate daily meal plan with full family profile and product intelligence"""
    logger.info(f"=== DAILY PLAN START === user_id={user_id} meal_type={req.meal_type} servings={req.servings}")
    total_t0 = perf_counter()
    storage = get_storage()
    config = storage.get_config()

    # Pull DB-backed profile (source of truth)
    try:
        logger.info(f"Fetching profile for user_id={user_id}")
        full_profile = await get_full_profile(user_id)
        logger.info(f"Profile fetched: members={len(full_profile.get('members', []))}")
    except Exception as e:
        logger.error(f"Failed to load profile: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to load user profile: {str(e)}")

    household = full_profile.get("household") or full_profile.get("profile") or {}
    members = full_profile.get("members") or []
    normalized_members: List[Dict[str, Any]] = []
    for m in members:
        if not isinstance(m, dict):
            continue
        # Ensure allergens key exists and is not None (Golden Rule requires explicit declaration)
        if "allergens" not in m or m.get("allergens") is None:
            m = {**m, "allergens": []}
        normalized_members.append(m)
    profile_dict = {"household": household, "members": normalized_members}

    # Load DB inventory/history early so we can avoid reusing stale plans when inventory changes.
    try:
        db_inventory = await get_inventory(user_id)
    except Exception:
        db_inventory = []
    try:
        db_history = await get_recipe_history(user_id, limit=50)
    except Exception:
        db_history = []

    inventory_models = _db_inventory_to_models(db_inventory)
    inventory_hash = _inventory_snapshot_hash(inventory_models)

    # Cuisine preferences: request takes precedence; otherwise fallback to DB household favorites.
    if not req.cuisine_preferences:
        db_favs = household.get("favorite_cuisines") or household.get("favoriteCuisines")
        if isinstance(db_favs, list) and db_favs:
            req.cuisine_preferences = db_favs
    req.cuisine_preferences = _normalize_cuisine_preferences(req.cuisine_preferences)

    # STRICT enforcement (default):
    # - If user provided cuisine preferences (directly or via household favorites), use them as allow-list.
    # - Otherwise, derive an allow-list from regional_profile (generic metadata-based matching; no hard-coded examples).
    allowed_cuisines = _allowed_cuisines_from_profile_and_request(req, household)
    if not allowed_cuisines:
        allowed_cuisines = _allowed_cuisines_from_regional_profile(household)

    # Reuse an existing saved plan for the day unless the request changed
    # AND the inventory snapshot hasn't materially changed.
    plan_date = _parse_iso_date(getattr(req, "current_date", None)) or date.today()
    if not force_regenerate:
        try:
            existing = await get_meal_plan_for_date(
                user_id,
                plan_date=plan_date,
                plan_type="daily",
                meal_type=req.meal_type,
            )
        except Exception:
            existing = None

        if isinstance(existing, dict):
            existing_payload = existing.get("recipes")
            if isinstance(existing_payload, dict) and existing_payload.get("status") == "ok":
                # Do not reuse previously-saved fallback payloads; they may be a degraded
                # structure from an earlier build and can break strict clients.
                if existing_payload.get("_fallback_mode") is True:
                    existing_payload = None

                if isinstance(existing_payload, dict):
                    existing_hash = existing_payload.get("_inventory_hash")
                    if isinstance(existing_hash, str) and existing_hash and existing_hash != inventory_hash:
                        existing_payload = None

                if isinstance(existing_payload, dict):
                    # Only reuse if core request knobs match.
                    if (
                        (existing.get("servings") == req.servings)
                        and (existing.get("time_available_minutes") == req.time_available_minutes)
                    ):
                        sel = existing_payload.get("selected_cuisine")
                        prefs = req.cuisine_preferences or []
                        if not prefs or (isinstance(sel, str) and sel.lower() in {p.lower() for p in prefs}):
                            existing_payload = _coerce_menu_headers(existing_payload)
                            return MenuPlanResponse(**existing_payload)
    
    # GOLDEN RULE: Check profile completeness and safety constraints
    golden_check = SAVOGoldenRule.check_before_generate(profile_dict)
    logger.info(f"Golden Rule check: can_proceed={golden_check['can_proceed']}")
    if not golden_check["can_proceed"]:
        # Render/Uvicorn often defaults to WARNING+ in production; keep this visible.
        # Do not log the full profile (PII/health-related fields may exist).
        logger.warning(
            "Golden Rule blocked /plan/daily user_id=%s action=%s missing_fields=%s members_count=%s message=%s",
            user_id,
            golden_check.get("action"),
            golden_check.get("missing_fields"),
            len(normalized_members),
            golden_check.get("message"),
        )
        return MenuPlanResponse(
            status="needs_clarification",
            needs_clarification_questions=[golden_check["message"]],
            error_message=golden_check.get("message", "Profile incomplete"),
            selected_cuisine="unknown",
            menu_headers=[],
            menus=[],
            variety_log={"rules_applied": [], "excluded_recent": [], "diversity_scores": {}},
            nutrition_summary={"total_calories_kcal": 0, "per_member_estimates": [], "warnings": []},
            waste_summary={
                "expiring_items_used": [],
                "waste_reduction_score": 0,
                "waste_avoided_value_estimate": {"currency": "USD", "value": 0},
            },
            shopping_suggestions=[],
        )

    # Product default: if the user didn't specify a goal, prioritize using what they have.
    if not getattr(req, "planning_goal", None) and inventory_models:
        try:
            req.planning_goal = "use_what_i_have"
        except Exception:
            pass

    # Inject DB-backed household/members into APP_CONFIGURATION for LLM safety compliance
    app_config_dict = config.model_dump(mode="json")
    nutrition_targets = household.get("nutrition_targets") or household.get("nutritionTargets") or {}
    if not isinstance(nutrition_targets, dict):
        nutrition_targets = {}
    app_config_dict["household_profile"] = {
        "members": [_member_for_app_config(m) for m in normalized_members],
        "nutrition_targets": nutrition_targets,
    }

    # Also include the raw DB profile in context (debuggable + future-proof)
    app_config_dict["db_profile"] = {
        "household": household,
        "members": normalized_members,
        "allergens": full_profile.get("allergens"),
        "dietary": full_profile.get("dietary"),
    }
    
    context = _build_planning_context(
        req,
        "daily",
        inventory_override=inventory_models,
        history_override=db_history,
        app_configuration_override=app_config_dict,
    )

    # Provide metadata-based cuisine candidates for the LLM to pick from.
    try:
        rp = household.get("regional_profile") if isinstance(household, dict) else None
        candidates = _regional_profile_candidates(rp)
        if candidates:
            context["regional_cuisine_candidates"] = candidates
            context["REGIONAL_CUISINE_CANDIDATES"] = candidates
    except Exception:
        pass
    context["time_available_minutes"] = req.time_available_minutes
    context["servings"] = req.servings
    
    # Add meal context for better recommendations
    if req.meal_type:
        context["meal_type"] = req.meal_type
    if req.meal_time:
        context["meal_time"] = req.meal_time
    if req.current_date:
        context["current_date"] = req.current_date

    # Advanced planning options (optional)
    if getattr(req, "planning_goal", None):
        context["planning_goal"] = req.planning_goal
    if getattr(req, "avoid_waste", None) is not None:
        context["avoid_waste"] = bool(req.avoid_waste)
    
    # Intelligence Layer 2: Build Nutrition Profile from family members
    nutrition_profile = None
    if normalized_members:
        # Aggregate health conditions and dietary needs
        all_health_conditions = []
        all_allergens = []
        all_dietary_restrictions = []
        
        for member in normalized_members:
            all_health_conditions.extend(_coerce_list(member.get("health_conditions")))
            all_allergens.extend(_coerce_list(member.get("allergens")))
            all_dietary_restrictions.extend(_coerce_list(member.get("dietary_restrictions")))
        
        # Create nutrition profile
        profile_kwargs = {
            "health_conditions": list(set(all_health_conditions)),  # Unique conditions
            "dietary_preferences": list(set(all_dietary_restrictions)),
            "allergens": list(set(all_allergens)),
        }
        if nutrition_targets:
            profile_kwargs["daily_targets"] = nutrition_targets
        nutrition_profile = UserNutritionProfile(**profile_kwargs)
        
        # Add to context for LLM
        context["nutrition_intelligence"] = {
            "health_conditions": nutrition_profile.health_conditions,
            "dietary_preferences": nutrition_profile.dietary_preferences,
            "allergens": nutrition_profile.allergens,
            "message": "Please respect these health conditions and allergens in recipe selection and preparation."
        }
        
        context["family_members"] = [_member_for_app_config(m) for m in normalized_members]
        
        # Add nutrition targets
        if nutrition_targets:
            context["nutrition_targets"] = nutrition_targets
    
    # Intelligence Layer 3: Add skill progression context
    user_skill_level = 2  # Default
    user_confidence = 0.7  # Default
    if isinstance(household, dict):
        try:
            user_skill_level = int(household.get("skill_level") or household.get("skillLevel") or user_skill_level)
        except Exception:
            pass
        try:
            user_confidence = float(household.get("confidence_score") or household.get("confidenceScore") or user_confidence)
        except Exception:
            pass
    
    context["skill_intelligence"] = {
        "user_level": user_skill_level,
        "confidence": user_confidence,
        "message": f"Please recommend recipes appropriate for skill level {user_skill_level} (1=beginner, 5=advanced)."
    }
    
    # Add cultural and regional preferences
    if config and config.global_settings:
        gs = config.global_settings
        context["region"] = gs.region
        context["culture"] = gs.culture
        context["meal_times"] = gs.meal_times
        
        # Add meal-specific preferences based on meal type
        if req.meal_type == "breakfast" or (req.meal_time and _is_breakfast_time(req.meal_time, gs.meal_times)):
            context["meal_preferences"] = gs.breakfast_preferences
        elif req.meal_type == "lunch" or (req.meal_time and _is_lunch_time(req.meal_time, gs.meal_times)):
            context["meal_preferences"] = gs.lunch_preferences
        elif req.meal_type == "dinner" or (req.meal_time and _is_dinner_time(req.meal_time, gs.meal_times)):
            context["meal_preferences"] = gs.dinner_preferences
    
    # Add complete safety context to prompt
    safety_context = build_complete_safety_context(profile_dict)
    context["safety_constraints"] = safety_context
    
    # Generate meal plan with aggressive timeout and fallback
    llm_t0 = perf_counter()
    logger.info(f"Starting LLM call for user_id={user_id}")
    result = None
    try:
        # Prefer real LLM generation; fall back only if it stalls.
        result = await asyncio.wait_for(plan_daily(context), timeout=20.0)
        logger.info(f"LLM call completed: status={result.get('status')} time={int((perf_counter() - llm_t0) * 1000)}ms")
    except asyncio.TimeoutError:
        logger.warning(f"LLM timeout after 20s, generating fallback recipes for user_id={user_id}")
        result = None
    except Exception as e:
        logger.exception("plan_daily crashed user_id=%s", user_id)
        result = None
    
    # FAIL-SAFE: If LLM failed, timed out, or returned needs_clarification, generate simple fallback
    if result is None or result.get("status") != "ok":
        logger.warning(f"LLM failed or returned non-ok status, generating FALLBACK recipes for user_id={user_id}")
        result = _generate_fallback_recipes(
            inventory=inventory_models,
            household=household,
            members=normalized_members,
            servings=req.servings,
            time_available=req.time_available_minutes,
            meal_type=req.meal_type,
        )
    
    llm_ms = int((perf_counter() - llm_t0) * 1000)

    # Enforce cuisine allow-list on output (hard guarantee).
    if isinstance(result, dict) and result.get("status") == "ok":
        result = _enforce_allowed_cuisines_in_payload(result, allowed_cuisines)

    # Avoid duplicated recipes in the returned menu.
    if isinstance(result, dict) and result.get("status") == "ok":
        result = _dedupe_menu_plan_payload(result)

    # Clean up recipe titles so UI never shows ingredient dumps in the name.
    result = _sanitize_recipe_names_in_payload(result)

    # Enforce a recent-recipe cooldown so CookNow doesn't repeat the last few cooks.
    if isinstance(result, dict) and result.get("status") == "ok":
        result = _exclude_recent_recipes_from_payload(result, db_history, cooldown_last_n=3)

    # Persist inventory snapshot hash inside the stored payload (response model ignores unknown keys).
    if isinstance(result, dict) and result.get("status") == "ok":
        result["_inventory_hash"] = inventory_hash

    # Normalize menu_headers so Pydantic response_model never 500s.
    result = _coerce_menu_headers(result)

    # Persist successful plan
    if isinstance(result, dict) and result.get("status") == "ok":
        try:
            await create_meal_plan(
                user_id,
                {
                    "plan_type": "daily",
                    "plan_date": plan_date.isoformat(),
                    "meal_type": req.meal_type,
                    "selected_cuisine": result.get("selected_cuisine"),
                    "servings": req.servings,
                    "time_available_minutes": req.time_available_minutes,
                    # Store the full validated plan payload for exact rehydration.
                    "recipes": result,
                },
            )
        except Exception:
            logger.exception("Failed to persist meal plan user_id=%s plan_date=%s", user_id, plan_date)

    status_val = result.get("status")
    if status_val and status_val != "ok":
        questions = result.get("needs_clarification_questions")
        first_q = None
        if isinstance(questions, list) and questions:
            first_q = questions[0]
        logger.warning(
            "plan_daily returned non-ok status user_id=%s status=%s selected_cuisine=%s error_message=%s first_question=%s",
            user_id,
            status_val,
            result.get("selected_cuisine"),
            result.get("error_message"),
            first_q,
        )
    
    # Intelligence Layer 4: Post-process recipes with health scores, skill fit, and badges
    # CRITICAL: Validate recipe safety before serving
    if result.get("recipes") and isinstance(result["recipes"], list):
        validated_recipes = []
        for recipe in result["recipes"]:
            # Validate safety first
            is_safe, violations = validate_recipe_safety(recipe, profile_dict)
            if not is_safe:
                # Log violation and skip recipe
                import logging
                logging.error(f"Recipe safety violation: {recipe.get('name', 'Unknown')} - {violations}")
                continue
            
            _enhance_recipe_with_intelligence(
                recipe=recipe,
                nutrition_profile=nutrition_profile,
                user_skill_level=user_skill_level,
                user_confidence=user_confidence,
                meal_type=req.meal_type or "dinner"
            )

    # Defensive: schema requires clarification details when status=needs_clarification.
    if isinstance(result, dict):
        status_val = result.get("status")
        if status_val == "needs_clarification":
            questions = result.get("needs_clarification_questions")
            has_questions = isinstance(questions, list) and any(str(q).strip() for q in questions)
            if not has_questions:
                # Try common alternate fields from upstream generators.
                single = None
                for key in ("clarification_question", "clarification", "message"):
                    v = result.get(key)
                    if isinstance(v, str) and v.strip():
                        single = v.strip()
                        break

                if single:
                    result["needs_clarification_questions"] = [single]
                    if not (result.get("error_message") or "").strip():
                        result["error_message"] = single
                elif not (result.get("error_message") or "").strip():
                    # Keep this consistent with the Pydantic model's fallback.
                    result["error_message"] = "Planning requires additional information."
        elif status_val == "error":
            if not (result.get("error_message") or "").strip():
                result["error_message"] = "Planning failed. Please try again."
    
    total_ms = int((perf_counter() - total_t0) * 1000)
    try:
        status_val = result.get("status") if isinstance(result, dict) else None
        sel = result.get("selected_cuisine") if isinstance(result, dict) else None
    except Exception:
        status_val = None
        sel = None

    if total_ms >= 4000:
        logger.info(
            "plan_daily_timing user_id=%s status=%s selected_cuisine=%s llm_ms=%s total_ms=%s",
            user_id,
            status_val,
            sel,
            llm_ms,
            total_ms,
        )
    else:
        logger.debug(
            "plan_daily_timing user_id=%s status=%s selected_cuisine=%s llm_ms=%s total_ms=%s",
            user_id,
            status_val,
            sel,
            llm_ms,
            total_ms,
        )

    return MenuPlanResponse(**result)


@router.get("/latest", response_model=MenuPlanResponse)
async def get_latest_plan(
    user_id: str = Depends(get_current_user),
    plan_type: str = "daily",
):
    """Fetch latest saved meal plan (does not trigger regeneration)."""
    plans = await get_meal_plans(user_id, plan_type=plan_type)
    if not plans:
        raise HTTPException(status_code=404, detail="No saved meal plans")

    payload = plans[0].get("recipes")
    if not isinstance(payload, dict):
        raise HTTPException(status_code=500, detail="Saved meal plan is not in expected format")

    # If the inventory has changed since this plan was generated, treat it as stale.
    try:
        db_inventory = await get_inventory(user_id)
    except Exception:
        db_inventory = []
    current_hash = _inventory_snapshot_hash(_db_inventory_to_models(db_inventory))
    saved_hash = payload.get("_inventory_hash")
    if isinstance(saved_hash, str) and saved_hash and saved_hash != current_hash:
        raise HTTPException(status_code=404, detail="Saved meal plan is stale")

    payload = _coerce_menu_headers(payload)
    return MenuPlanResponse(**payload)


@router.delete("/latest")
async def delete_latest_plan(
    user_id: str = Depends(get_current_user),
    plan_type: str = "daily",
    plan_date: Optional[str] = None,
):
    """Clear the most recent saved plan so the user can regenerate cleanly."""
    try:
        parsed_date = _parse_iso_date(plan_date) if plan_date else None
        deleted = await delete_latest_meal_plan(
            user_id,
            plan_type=plan_type,
            plan_date=parsed_date,
        )
        return {"success": True, "deleted": bool(deleted)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete plan: {str(e)}")


def _is_breakfast_time(time_str: str, meal_times: dict) -> bool:
    """Check if time falls in breakfast range"""
    breakfast_range = meal_times.get("breakfast", "07:00-09:00")
    start, end = breakfast_range.split("-")
    return start <= time_str <= end


def _is_lunch_time(time_str: str, meal_times: dict) -> bool:
    """Check if time falls in lunch range"""
    lunch_range = meal_times.get("lunch", "12:00-14:00")
    start, end = lunch_range.split("-")
    return start <= time_str <= end


def _is_dinner_time(time_str: str, meal_times: dict) -> bool:
    """Check if time falls in dinner range"""
    dinner_range = meal_times.get("dinner", "18:00-21:00")
    start, end = dinner_range.split("-")
    return start <= time_str <= end


@router.post("/party", response_model=MenuPlanResponse)
async def post_party(
    req: PartyPlanRequest,
    user_id: str = Depends(get_current_user),
    force_regenerate: bool = False,
):
    """Generate party meal plan with age-aware constraints"""
    total_t0 = perf_counter()
    # Validate party settings (Pydantic already validated, but double-check)
    if req.party_settings.guest_count < 2 or req.party_settings.guest_count > 80:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="guest_count must be between 2 and 80"
        )
    
    # Pull DB-backed inventory/history so party planning gets variety + inventory-first behavior.
    try:
        db_inventory = await get_inventory(user_id)
    except Exception:
        db_inventory = []
    try:
        db_history = await get_recipe_history(user_id, limit=50)
    except Exception:
        db_history = []

    # Pull DB-backed profile (source of truth for regional + favorites)
    try:
        full_profile = await get_full_profile(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load user profile: {str(e)}")

    household = (full_profile.get("household") or full_profile.get("profile") or {}) if isinstance(full_profile, dict) else {}

    members = full_profile.get("members") if isinstance(full_profile, dict) else []
    members = members if isinstance(members, list) else []
    normalized_members: List[Dict[str, Any]] = []
    for m in members:
        if not isinstance(m, dict):
            continue
        # Ensure allergens key exists and is not None (Golden Rule requires explicit declaration)
        if "allergens" not in m or m.get("allergens") is None:
            m = {**m, "allergens": []}
        normalized_members.append(m)
    profile_dict = {"household": household, "members": normalized_members}

    # Cuisine preferences: request takes precedence; otherwise fallback to DB household favorites.
    if not getattr(req, "cuisine_preferences", None):
        db_favs = household.get("favorite_cuisines") or household.get("favoriteCuisines")
        if isinstance(db_favs, list) and db_favs:
            req.cuisine_preferences = db_favs
    req.cuisine_preferences = _normalize_cuisine_preferences(getattr(req, "cuisine_preferences", None))

    inventory_models = _db_inventory_to_models(db_inventory)
    inventory_hash = _inventory_snapshot_hash(inventory_models)

    # GOLDEN RULE: avoid expensive generation if safety-critical profile fields are missing.
    golden_check = SAVOGoldenRule.check_before_generate(profile_dict)
    if not golden_check["can_proceed"]:
        logger.warning(
            "Golden Rule blocked /plan/party user_id=%s action=%s missing_fields=%s members_count=%s message=%s",
            user_id,
            golden_check.get("action"),
            golden_check.get("missing_fields"),
            len(normalized_members),
            golden_check.get("message"),
        )
        return MenuPlanResponse(
            status="needs_clarification",
            needs_clarification_questions=[golden_check["message"]],
            error_message=golden_check.get("message", "Profile incomplete"),
            selected_cuisine="unknown",
            menu_headers=[],
            menus=[],
            variety_log={"rules_applied": [], "excluded_recent": [], "diversity_scores": {}},
            nutrition_summary={"total_calories_kcal": 0, "per_member_estimates": [], "warnings": []},
            waste_summary={
                "expiring_items_used": [],
                "waste_reduction_score": 0,
                "waste_avoided_value_estimate": {"currency": "USD", "value": 0},
            },
            shopping_suggestions=[],
        )

    # Reuse an existing saved party plan for today unless request/inventory changed.
    # Party planning is expensive; caching avoids repeated long generations on web.
    plan_date = date.today()
    try:
        request_fingerprint = {
            "selected_cuisine": getattr(req, "selected_cuisine", None),
            "cuisine_preferences": getattr(req, "cuisine_preferences", None),
            "party_settings": req.party_settings.model_dump() if getattr(req, "party_settings", None) else None,
            "party_course_counts": req.party_course_counts.model_dump() if getattr(req, "party_course_counts", None) else None,
            "planning_goal": getattr(req, "planning_goal", None),
            "avoid_waste": getattr(req, "avoid_waste", None),
            "use_leftovers": getattr(req, "use_leftovers", None),
            "measurement_system": getattr(req, "measurement_system", None),
            "output_language": getattr(req, "output_language", None),
            "output_languages": getattr(req, "output_languages", None),
        }
        request_hash = hashlib.sha256(
            json.dumps(request_fingerprint, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
    except Exception:
        request_hash = ""

    if not force_regenerate:
        try:
            existing = await get_meal_plan_for_date(
                user_id,
                plan_date=plan_date,
                plan_type="party",
                meal_type=None,
            )
        except Exception:
            existing = None

        if isinstance(existing, dict):
            existing_payload = existing.get("recipes")
            if isinstance(existing_payload, dict) and existing_payload.get("status") == "ok":
                existing_inv_hash = existing_payload.get("_inventory_hash")
                if isinstance(existing_inv_hash, str) and existing_inv_hash and existing_inv_hash != inventory_hash:
                    existing_payload = None

            if (
                isinstance(existing_payload, dict)
                and existing_payload.get("status") == "ok"
                and not existing_payload.get("_fallback_mode")
            ):
                existing_req_hash = existing_payload.get("_request_hash")
                if request_hash and isinstance(existing_req_hash, str) and existing_req_hash == request_hash:
                    existing_payload = _coerce_menu_headers(existing_payload)
                    if _payload_has_recipes(existing_payload):
                        return MenuPlanResponse(**existing_payload)

    context = _build_planning_context(
        req,
        "party",
        party_settings=req.party_settings,
        inventory_override=inventory_models,
        history_override=db_history,
    )
    context["party_settings"] = req.party_settings.model_dump()
    try:
        context["PARTY_SETTINGS"] = context.get("party_settings")
    except Exception:
        pass
    if getattr(req, "party_course_counts", None) is not None:
        context["party_course_counts"] = req.party_course_counts.model_dump()
    
    # Use request preferences first; otherwise derive from household regional_profile.
    allowed_cuisines = _allowed_cuisines_from_profile_and_request(req, household)
    if not allowed_cuisines:
        allowed_cuisines = _allowed_cuisines_from_regional_profile(household)
    llm_t0 = perf_counter()
    result = None
    try:
        result = await asyncio.wait_for(plan_party(context), timeout=25.0)
    except asyncio.TimeoutError:
        logger.warning("LLM timeout for /plan/party user_id=%s, using fallback party plan", user_id)
        result = None
    except Exception:
        logger.exception("plan_party crashed user_id=%s", user_id)
        result = None

    llm_ms = int((perf_counter() - llm_t0) * 1000)

    if not isinstance(result, dict) or result.get("status") != "ok" or not _payload_has_recipes(result):
        logger.warning("/plan/party using fallback plan user_id=%s", user_id)
        result = _generate_fallback_party_plan(
            inventory=inventory_models,
            household=household,
            members=normalized_members,
            guest_count=getattr(req.party_settings, "guest_count", 6) or 6,
        )

    # Enforce a recent-recipe cooldown so users see variety across parties.
    if isinstance(result, dict) and result.get("status") == "ok":
        result = _exclude_recent_recipes_from_payload(result, db_history, cooldown_last_n=3)
    if isinstance(result, dict) and result.get("status") == "ok":
        result = _enforce_allowed_cuisines_in_payload(result, allowed_cuisines)

    # Avoid duplicates inside a party menu (e.g., same recipe across courses/options).
    if isinstance(result, dict) and result.get("status") == "ok":
        result = _dedupe_menu_plan_payload(result)

    # Clean up recipe titles so UI never shows ingredient dumps in the name.
    result = _sanitize_recipe_names_in_payload(result)

    # Normalize menu_headers so Pydantic response_model never 500s.
    result = _coerce_menu_headers(result)

    # Keep shopping_suggestions consistent with the selected dishes' missing ingredients.
    # (The LLM may omit shopping_suggestions; the client shopping cart/list depends on it.)
    if isinstance(result, dict) and result.get("status") == "ok":
        derived = _derive_shopping_suggestions_from_plan_payload(result, primary_only=True)
        if derived:
            result["shopping_suggestions"] = _merge_shopping_suggestions(
                result.get("shopping_suggestions"), derived
            )

        # Best-effort: sync to Supabase shopping list table for cross-device cart updates.
        try:
            household_id = household.get("id") if isinstance(household, dict) else None
            suggestions = result.get("shopping_suggestions")
            if isinstance(household_id, str) and household_id.strip() and isinstance(suggestions, list) and suggestions:
                await upsert_household_shopping_items(household_id.strip(), suggestions)
        except Exception:
            logger.exception("Failed to upsert household shopping items user_id=%s", user_id)

    # Persist successful party plan (keyed by today's date) so the web client doesn't repeatedly time out.
    if isinstance(result, dict) and result.get("status") == "ok":
        try:
            result["_inventory_hash"] = inventory_hash
            if request_hash:
                result["_request_hash"] = request_hash
            await create_meal_plan(
                user_id,
                {
                    "plan_type": "party",
                    "plan_date": plan_date.isoformat(),
                    "meal_type": None,
                    "selected_cuisine": result.get("selected_cuisine"),
                    "servings": getattr(req.party_settings, "guest_count", None),
                    "time_available_minutes": None,
                    "recipes": result,
                },
            )
        except Exception:
            logger.exception("Failed to persist party meal plan user_id=%s plan_date=%s", user_id, plan_date)
    total_ms = int((perf_counter() - total_t0) * 1000)
    try:
        status_val = result.get("status") if isinstance(result, dict) else None
        sel = result.get("selected_cuisine") if isinstance(result, dict) else None
    except Exception:
        status_val = None
        sel = None

    if total_ms >= 4000:
        logger.info(
            "plan_party_timing user_id=%s status=%s selected_cuisine=%s llm_ms=%s total_ms=%s",
            user_id,
            status_val,
            sel,
            llm_ms,
            total_ms,
        )
    else:
        logger.debug(
            "plan_party_timing user_id=%s status=%s selected_cuisine=%s llm_ms=%s total_ms=%s",
            user_id,
            status_val,
            sel,
            llm_ms,
            total_ms,
        )

    return MenuPlanResponse(**result)


@router.post("/weekly", response_model=MenuPlanResponse)
async def post_weekly(
    req: WeeklyPlanRequest,
    user_id: str = Depends(get_current_user),
):
    """Generate weekly meal plan with configurable horizon"""
    total_t0 = perf_counter()
    storage = get_storage()
    config = storage.get_config()

    # Pull DB-backed profile (source of truth for favorites)
    try:
        full_profile = await get_full_profile(user_id)
    except Exception:
        full_profile = {}

    household = (full_profile.get("household") or full_profile.get("profile") or {}) if isinstance(full_profile, dict) else {}

    # Cuisine preferences: request takes precedence; otherwise fallback to DB household favorites.
    if not getattr(req, "cuisine_preferences", None):
        db_favs = household.get("favorite_cuisines") or household.get("favoriteCuisines")
        if isinstance(db_favs, list) and db_favs:
            req.cuisine_preferences = db_favs
    req.cuisine_preferences = _normalize_cuisine_preferences(getattr(req, "cuisine_preferences", None))

    # Product default: if the user didn't specify a goal, prioritize using what they have.
    try:
        db_inventory = await get_inventory(user_id)
    except Exception:
        db_inventory = []
    try:
        db_history = await get_recipe_history(user_id, limit=50)
    except Exception:
        db_history = []

    inventory_models = _db_inventory_to_models(db_inventory)
    if not getattr(req, "planning_goal", None) and inventory_models:
        try:
            req.planning_goal = "use_what_i_have"
        except Exception:
            pass
    
    # Determine timezone with priority: request > config > UTC
    timezone = req.timezone or config.global_settings.timezone or "UTC"
    
    weekly_context = {
        "num_days": req.num_days,
        "start_date": req.start_date.isoformat(),
        "timezone": timezone,
        "current_cuisines": [],  # Will be built up as we plan each day
        "day_index": 0,
    }
    
    context = _build_planning_context(
        req,
        "weekly",
        weekly_context=weekly_context,
        inventory_override=inventory_models,
        history_override=db_history,
    )
    
    # Add weekly-specific fields
    context["start_date"] = req.start_date.isoformat()
    context["num_days"] = req.num_days
    context["timezone"] = timezone
    
    if req.time_available_minutes:
        context["time_available_minutes"] = req.time_available_minutes
    if req.servings:
        context["servings"] = req.servings
    
    llm_t0 = perf_counter()
    result = await plan_weekly(context)
    llm_ms = int((perf_counter() - llm_t0) * 1000)

    # Avoid duplicated recipes in the returned menu.
    if isinstance(result, dict) and result.get("status") == "ok":
        result = _dedupe_menu_plan_payload(result)

    # Persist successful plan (keyed by start_date)
    if isinstance(result, dict) and result.get("status") == "ok":
        # Enforce a recent-recipe cooldown so weekly plans don't repeat recent cooks.
        if isinstance(result, dict) and result.get("status") == "ok":
            result = _exclude_recent_recipes_from_payload(result, db_history, cooldown_last_n=3)

        # Enforce cuisine allow-list on output.
        allowed_cuisines = _allowed_cuisines_from_profile_and_request(req, household)
        if not allowed_cuisines:
            allowed_cuisines = _allowed_cuisines_from_regional_profile(household)
        if isinstance(result, dict) and result.get("status") == "ok":
            result = _enforce_allowed_cuisines_in_payload(result, allowed_cuisines)
        try:
            await create_meal_plan(
                user_id,
                {
                    "plan_type": "weekly",
                    "plan_date": req.start_date.isoformat(),
                    "meal_type": None,
                    "selected_cuisine": result.get("selected_cuisine"),
                    "servings": req.servings,
                    "time_available_minutes": req.time_available_minutes,
                    "recipes": result,
                },
            )
        except Exception:
            logger.exception(
                "Failed to persist weekly meal plan user_id=%s plan_date=%s",
                user_id,
                req.start_date,
            )

    total_ms = int((perf_counter() - total_t0) * 1000)
    try:
        status_val = result.get("status") if isinstance(result, dict) else None
        sel = result.get("selected_cuisine") if isinstance(result, dict) else None
    except Exception:
        status_val = None
        sel = None

    if total_ms >= 4000:
        logger.info(
            "plan_weekly_timing user_id=%s status=%s selected_cuisine=%s llm_ms=%s total_ms=%s",
            user_id,
            status_val,
            sel,
            llm_ms,
            total_ms,
        )
    else:
        logger.debug(
            "plan_weekly_timing user_id=%s status=%s selected_cuisine=%s llm_ms=%s total_ms=%s",
            user_id,
            status_val,
            sel,
            llm_ms,
            total_ms,
        )

    return MenuPlanResponse(**result)


# ============================================
# Multi-Ingredient Combination Endpoint
# ============================================

@router.post("/recipes/combination")
async def generate_combination_recipe(
    ingredients: List[str],
    user_id: str,
    cuisine: Optional[str] = None,
    meal_type: Optional[str] = "dinner",
    output_language: str = "en",
    secondary_language: Optional[str] = None,
):
    """
    Generate a recipe using multiple ingredients intelligently.
    
    Analyzes ingredient synergies, balance, and generates a cohesive recipe.
    
    Args:
        ingredients: List of ingredient names to use
        user_id: User UUID for profile and safety constraints
        cuisine: Optional cuisine preference
        meal_type: Type of meal (breakfast, lunch, dinner, snack)
    
    Returns:
        {
            "analysis": {ingredient combination analysis},
            "recipe": {generated recipe},
            "safety_validation": {validation results}
        }
    """
    from app.services.llm import get_llm_client
    import json
    
    if not ingredients or len(ingredients) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide at least 1 ingredient"
        )
    
    if len(ingredients) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 ingredients allowed"
        )
    
    # Get user profile
    storage = get_storage()
    profile = await storage.get_user_profile(user_id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    # Validate profile completeness (Golden Rule)
    is_complete, missing = validate_profile_completeness(profile)
    if not is_complete:
        return {
            "error": "Profile incomplete",
            "message": "Please complete your profile before generating recipes",
            "missing_fields": missing,
            "onboarding_required": True
        }
    
    # Analyze ingredient combination
    try:
        analysis = analyze_ingredients(ingredients, profile)
    except Exception as e:
        logger.error(f"Ingredient analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze ingredient combination"
        )
    
    # Check if combination is viable
    if not analysis.get("is_viable"):
        return {
            "success": False,
            "analysis": analysis,
            "message": "Ingredient combination has limitations",
            "suggestion": "Consider adding: " + ", ".join(analysis.get("suggested_additions", [])[:3])
        }
    
    # Check for safety issues
    if analysis.get("safety_issues"):
        return {
            "success": False,
            "analysis": analysis,
            "message": "Safety constraints prevent using these ingredients",
            "safety_issues": analysis["safety_issues"]
        }
    
    # Generate AI prompt
    prompt, _ = generate_combination_recipe_prompt(ingredients, profile)
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not generate recipe prompt for this combination"
        )
    
    # Call LLM
    try:
        llm = get_llm_client()
        llm_response = await llm.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=2000
        )
        
        # Parse recipe (assuming JSON response)
        recipe = json.loads(llm_response)
        
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate recipe"
        )
    
    # Normalize recipe into the bilingual-capable shape (recipe_name/lang maps).
    try:
        if isinstance(recipe, dict):
            # recipe_name
            if isinstance(recipe.get("recipe_name"), str):
                recipe["recipe_name"] = {"en": recipe.get("recipe_name")}
            elif not isinstance(recipe.get("recipe_name"), dict):
                # Common alias
                name = recipe.get("name")
                if isinstance(name, str) and name.strip():
                    recipe["recipe_name"] = {"en": name.strip()}
                else:
                    recipe.setdefault("recipe_name", {"en": ""})

            # steps[].instruction
            steps = recipe.get("steps")
            if isinstance(steps, list):
                normalized_steps = []
                for s in steps:
                    if not isinstance(s, dict):
                        continue
                    instr = s.get("instruction")
                    if isinstance(instr, str):
                        s["instruction"] = {"en": instr}
                    elif not isinstance(instr, dict):
                        s["instruction"] = {"en": ""}
                    normalized_steps.append(s)
                recipe["steps"] = normalized_steps
    except Exception:
        # Best-effort only
        pass

    # Force english-first output; add bilingual translation when requested.
    try:
        from app.api.routes.recipes import _translate_recipe_fields

        # We always treat English as the canonical first language for bilingual payloads.
        _ = output_language  # reserved; primary generation uses the prompt content.
        if isinstance(secondary_language, str) and secondary_language.strip():
            lang = secondary_language.strip()
            if lang.lower() != "en":
                recipe = await _translate_recipe_fields(recipe=recipe, target_language=lang)
    except Exception:
        # Translation is best-effort; still return the base recipe.
        pass

    # Validate recipe safety
    is_safe, violations = await validate_recipe_safety(recipe, profile)
    
    if not is_safe:
        logger.error(f"Recipe safety violation: {violations}")
        return {
            "success": False,
            "error": "Generated recipe violated safety constraints",
            "violations": violations,
            "retry_allowed": True
        }
    
    # Success
    return {
        "success": True,
        "analysis": analysis,
        "recipe": recipe,
        "safety_validation": {
            "is_safe": is_safe,
            "violations": []
        },
        "metadata": {
            "ingredients_used": ingredients,
            "cuisine": recipe.get("cuisine", cuisine),
            "meal_type": meal_type
        }
    }


# ============================================
# Full Course Meal Endpoint
# ============================================

@router.post("/recipes/full-course")
async def generate_full_course_meal(
    meal_style: str,
    cuisine: str,
    user_id: str,
    ingredients_available: Optional[List[str]] = None,
    context: Optional[str] = None
):
    """
    Generate a complete multi-course meal.
    
    Creates appetizer, main, dessert (or other course combinations)
    with cultural coherence and flavor progression.
    
    Args:
        meal_style: "casual", "standard", "formal", "italian", "indian", "chinese", "japanese"
        cuisine: Primary cuisine for the meal
        user_id: User UUID for profile and safety constraints
        ingredients_available: Optional ingredients to incorporate
        context: Additional user context (e.g., "anniversary dinner", "quick weeknight")
    
    Returns:
        {
            "meal_plan": {complete meal with all courses},
            "courses": [{recipe for each course}],
            "prep_strategy": {cooking order and timing}
        }
    """
    from app.services.llm import get_llm_client
    import json
    
    # Validate meal style
    valid_styles = ["casual", "standard", "formal", "italian", "french", "indian", "chinese", "japanese"]
    if meal_style.lower() not in valid_styles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid meal_style. Must be one of: {', '.join(valid_styles)}"
        )
    
    # Get user profile
    storage = get_storage()
    profile = await storage.get_user_profile(user_id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    # Validate profile completeness
    is_complete, missing = validate_profile_completeness(profile)
    if not is_complete:
        return {
            "error": "Profile incomplete",
            "message": "Please complete your profile before generating recipes",
            "missing_fields": missing,
            "onboarding_required": True
        }
    
    # Plan meal
    try:
        meal_plan = plan_full_course_meal(
            meal_style=meal_style.lower(),
            cuisine=cuisine,
            profile=profile,
            ingredients=ingredients_available
        )
    except Exception as e:
        logger.error(f"Meal planning failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to plan meal"
        )
    
    # Generate recipes for each course
    courses_generated = []
    llm = get_llm_client()
    
    for course_data in meal_plan["courses"]:
        try:
            # Generate recipe using course-specific prompt
            llm_response = await llm.generate(
                prompt=course_data["prompt"],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Parse recipe
            recipe = json.loads(llm_response)
            
            # Validate safety
            is_safe, violations = await validate_recipe_safety(recipe, profile)
            
            if not is_safe:
                logger.warning(f"Course {course_data['course_type']} failed safety: {violations}")
                # Try to regenerate once
                continue
            
            courses_generated.append({
                "course_type": course_data["course_type"],
                "recipe": recipe,
                "portion_size": course_data["portion_size"],
                "required": course_data["required"]
            })
            
        except Exception as e:
            logger.error(f"Course generation failed for {course_data['course_type']}: {e}")
            # If required course fails, entire meal fails
            if course_data["required"]:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to generate required {course_data['course_type']}"
                )
    
    if not courses_generated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate any courses"
        )
    
    # Build prep strategy
    prep_strategy = _build_prep_strategy(courses_generated, meal_plan)
    
    return {
        "success": True,
        "meal_plan": {
            "meal_style": meal_plan["meal_style"],
            "cuisine": meal_plan["cuisine"],
            "total_courses": len(courses_generated),
            "estimated_total_time": meal_plan["estimated_total_time"],
            "servings": meal_plan["servings"],
            "coherence_score": meal_plan["coherence_score"],
            "flavor_progression": meal_plan["flavor_progression"]
        },
        "courses": courses_generated,
        "prep_strategy": prep_strategy,
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "user_id": user_id
        }
    }


def _build_prep_strategy(courses: List[Dict], meal_plan: Dict) -> Dict:
    """Build cooking strategy for multi-course meal"""
    
    # Sort courses by cooking time (longest first)
    sorted_courses = sorted(
        courses,
        key=lambda c: c["recipe"].get("cook_time", 30),
        reverse=True
    )
    
    prep_order = []
    for idx, course in enumerate(sorted_courses, 1):
        prep_order.append({
            "step": idx,
            "course": course["course_type"],
            "action": f"Prepare {course['course_type']}",
            "timing_note": f"Start this {course['recipe'].get('prep_time', 15)} minutes before serving"
        })
    
    return {
        "prep_order": prep_order,
        "parallel_cooking": "Start longest-cooking items first, prepare quick items last",
        "make_ahead": [
            c["course_type"] for c in courses 
            if c["recipe"].get("can_make_ahead", False)
        ],
        "serving_sequence": [c["course_type"] for c in courses],
        "total_active_time": sum(c["recipe"].get("prep_time", 15) for c in courses) // 2  # Assume 50% parallel
    }
