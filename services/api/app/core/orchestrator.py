from typing import Any, Dict, Optional
import json
import logging
from time import perf_counter
import uuid

from app.core.llm_client import get_llm_client, RateLimitException
from app.core.prompt_pack import get_schema, get_system_prompt_lines, get_task
from app.core.schema_validation import validate_json, SchemaValidationException
from app.core.settings import settings
from app.core.recipe_validators import (
    SemanticValidationException,
    format_semantic_issues_for_prompt,
    validate_menu_plan_semantics,
    validate_menu_plan_structure_against_metadata,
)

logger = logging.getLogger(__name__)


class AuthenticityJudgeException(Exception):
    def __init__(self, issues_text: str):
        super().__init__("Authenticity judge rejected plan")
        self.issues_text = issues_text


def _looks_like_dal_recipe(*, recipe: Dict[str, Any], course_header: str | None = None) -> bool:
    try:
        if isinstance(course_header, str) and course_header.strip().lower() == "dal":
            return True
    except Exception:
        pass

    rn = recipe.get("recipe_name")
    name = ""
    if isinstance(rn, dict):
        name = str(rn.get("en") or "")
        if not name.strip() and rn:
            # Any available language
            try:
                name = str(next(iter(rn.values())))
            except Exception:
                name = ""
    elif isinstance(rn, str):
        name = rn

    name_l = name.strip().lower()
    if not name_l:
        return False

    # Basic word boundary check: 'dal' as a word or suffix like 'dal tadka'.
    return bool(__import__("re").search(r"\bdal\b", name_l))


def _dal_has_lentils_or_pulses(recipe: Dict[str, Any]) -> bool:
    # Minimal keyword set. This is about dish correctness, not geography mapping.
    lentil_keywords = {
        "lentil",
        "lentils",
        "dal",
        "dahl",
        "toor",
        "tuvar",
        "moong",
        "mung",
        "masoor",
        "urad",
        "chana dal",
        "split peas",
        "pigeon pea",
    }

    def _names(list_value: Any) -> list[str]:
        if not isinstance(list_value, list):
            return []
        out: list[str] = []
        for it in list_value:
            if isinstance(it, dict):
                n = it.get("canonical_name") or it.get("name")
                if isinstance(n, str) and n.strip():
                    out.append(n.strip().lower())
        return out

    names = _names(recipe.get("ingredients_used")) + _names(recipe.get("new_ingredients_optional"))
    joined = " | ".join(names)
    if not joined:
        return False
    return any(k in joined for k in lentil_keywords)


def _ensure_dal_includes_lentils(recipe: Dict[str, Any]) -> None:
    if _dal_has_lentils_or_pulses(recipe):
        return
    existing = recipe.get("new_ingredients_optional")
    if not isinstance(existing, list):
        existing = []

    # Add a single, minimal optional item. Amount/unit are best-effort defaults.
    existing.append(
        {
            "canonical_name": "toor dal",
            "amount": 200,
            "unit": "g",
            "reason": "Dal is lentil-based; add a pulse (e.g., toor/moong/masoor) as the main ingredient.",
        }
    )
    recipe["new_ingredients_optional"] = existing


def _get_menu_plan_recipe_options_min_items(schema: Dict[str, Any]) -> int:
    """Best-effort extraction of recipe_options.minItems from MENU_PLAN_SCHEMA."""
    try:
        return int(
            schema["properties"]["menus"]["items"]["properties"]["courses"]["items"][
                "properties"
            ]["recipe_options"].get("minItems", 0)
        )
    except Exception:
        return 0


def _synthesize_minimal_recipe_option(*, recipe_id: str, recipe_name: str, cuisine: str) -> Dict[str, Any]:
    """Return a minimal, schema-valid recipe option.

    This is only used as a last-resort repair when the LLM returns empty/missing
    recipe_options, which would otherwise hard-fail schema validation.
    """

    name_obj: Dict[str, str] = {"en": recipe_name.strip() or "Recipe"}

    return {
        "recipe_id": recipe_id,
        "recipe_name": name_obj,
        "cuisine": cuisine or "unknown",
        "difficulty": "easy",
        "estimated_times": {"prep_minutes": 10, "cook_minutes": 15, "total_minutes": 25},
        "cooking_method": "stovetop",
        "ingredients_used": [
            {"inventory_id": "inv_unknown", "canonical_name": "salt", "amount": 1, "unit": "tsp"}
        ],
        "new_ingredients_optional": [],
        "steps": [
            {
                "step": 1,
                "instruction": {"en": "Prepare ingredients and cook until done."},
                "time_minutes": 15,
                "tips": [],
            }
        ],
        "nutrition_per_serving": {
            "calories_kcal": 400,
            "macros": {"protein_g": 20, "carbs_g": 40, "fat_g": 15},
            "micros": {"fiber_g": 0, "sodium_mg": 0},
        },
        "health_benefits": [],
        "health_fit": {"flags": [], "scores": {}, "adjustments": []},
        "leftover_forecast": {"expected_leftover_servings": 0, "reuse_ideas": []},
        "preservation_guidance": {
            "storage": "refrigerate",
            "safe_duration_hours": 24,
            "reheat_methods": [],
            "quality_notes": "Best within a day.",
        },
        "youtube_references": [],
        "agent_mode": "beginner_coach",
    }


def _repair_menu_plan_result(result: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    """Repair common LLM omissions so schema validation is less fragile."""
    # Normalize legacy status values.
    status = result.get("status")
    if status == "success":
        result["status"] = "ok"

    # Ensure required scalar fields have the correct type.
    # LLM occasionally returns null for required strings like selected_cuisine.
    selected_cuisine = result.get("selected_cuisine")
    if not isinstance(selected_cuisine, str) or not selected_cuisine.strip():
        result["selected_cuisine"] = "unknown"

    # If the LLM reports a non-ok status but omits error_message, synthesize one.
    # This prevents the client from falling back to a generic "Planning failed".
    status = result.get("status")
    if status in ["needs_clarification", "error"] and not result.get("error_message"):
        q = result.get("needs_clarification_questions")
        if isinstance(q, list) and q and isinstance(q[0], str) and q[0].strip():
            result["error_message"] = q[0].strip()
        else:
            result["error_message"] = "Planning requires additional information."

    # Legacy/alternate shape normalization:
    # Some older generators return menus as an object mapping course_header -> [recipe].
    # Convert to the current menus[] schema so we can validate and serve it.
    legacy_menus = result.get("menus")
    if isinstance(legacy_menus, dict):
        try:
            course_headers = [str(k) for k in legacy_menus.keys() if str(k).strip()]
        except Exception:
            course_headers = []

        # Best-effort servings inference.
        servings_count = 2
        try:
            s = result.get("servings")
            if isinstance(s, (int, float)) and s > 0:
                servings_count = float(s)
        except Exception:
            pass

        selected_cuisine_val = result.get("selected_cuisine")
        cuisine_for_fallback = (
            selected_cuisine_val
            if isinstance(selected_cuisine_val, str) and selected_cuisine_val.strip()
            else "unknown"
        )

        def _legacy_recipe_to_option(recipe: Any, *, course_header: str, idx: int) -> Dict[str, Any]:
            if not isinstance(recipe, dict):
                return _synthesize_minimal_recipe_option(
                    recipe_id=f"r_{course_header.lower().replace(' ', '_')}_{idx}",
                    recipe_name=f"{course_header} Option {idx}",
                    cuisine=cuisine_for_fallback,
                )

            name = recipe.get("name") or recipe.get("recipe_name") or f"{course_header} Option {idx}"
            if isinstance(name, dict):
                name_en = str(name.get("en") or "").strip() or str(next(iter(name.values()), ""))
            else:
                name_en = str(name or "").strip()

            ingredients_used: list[dict[str, Any]] = []
            ing = recipe.get("ingredients")
            if isinstance(ing, list):
                for raw in ing[:32]:
                    if isinstance(raw, str) and raw.strip():
                        ingredients_used.append(
                            {
                                "inventory_id": "inv_unknown",
                                "canonical_name": raw.strip(),
                                "amount": 0,
                                "unit": "",
                            }
                        )

            steps_out: list[dict[str, Any]] = []
            st = recipe.get("steps")
            if isinstance(st, list):
                for i, raw in enumerate(st[:10], start=1):
                    if isinstance(raw, str) and raw.strip():
                        steps_out.append(
                            {
                                "step": i,
                                "instruction": {"en": raw.strip()},
                                "time_minutes": 0,
                                "tips": [],
                            }
                        )

            if not steps_out:
                steps_out = [
                    {
                        "step": 1,
                        "instruction": {"en": "Prepare ingredients and cook until done."},
                        "time_minutes": 15,
                        "tips": [],
                    }
                ]

            nutrition = recipe.get("nutrition") if isinstance(recipe.get("nutrition"), dict) else {}
            calories = nutrition.get("calories") if isinstance(nutrition, dict) else None
            macros = {
                "protein_g": float(nutrition.get("protein_g", 0) or 0) if isinstance(nutrition, dict) else 0,
                "carbs_g": float(nutrition.get("carbs_g", 0) or 0) if isinstance(nutrition, dict) else 0,
                "fat_g": float(nutrition.get("fat_g", 0) or 0) if isinstance(nutrition, dict) else 0,
            }
            micros: dict[str, Any] = {}
            if isinstance(nutrition, dict):
                for k in ("fiber_g", "sodium_mg"):
                    v = nutrition.get(k)
                    if isinstance(v, (int, float)):
                        micros[k] = v

            health_fit_flags: list[str] = []
            hf = recipe.get("health_fit")
            if isinstance(hf, str) and hf.strip():
                health_fit_flags = [hf.strip()]

            preservation = recipe.get("preservation")
            storage = "refrigerate"
            if isinstance(preservation, str) and "freez" in preservation.lower():
                storage = "freeze"

            option: Dict[str, Any] = {
                "recipe_id": f"r_{course_header.lower().replace(' ', '_')}_{idx}",
                "recipe_name": {"en": name_en or f"{course_header} Option {idx}"},
                "cuisine": cuisine_for_fallback,
                "difficulty": "easy",
                "estimated_times": {"prep_minutes": 10, "cook_minutes": 15, "total_minutes": 25},
                "cooking_method": "stovetop",
                "ingredients_used": ingredients_used or [
                    {"inventory_id": "inv_unknown", "canonical_name": "salt", "amount": 1, "unit": "tsp"}
                ],
                "new_ingredients_optional": [],
                "steps": steps_out,
                "nutrition_per_serving": {
                    "calories_kcal": float(calories or 0) if isinstance(calories, (int, float)) else 0,
                    "macros": macros,
                    "micros": micros,
                },
                "health_benefits": recipe.get("health_benefits") if isinstance(recipe.get("health_benefits"), list) else [],
                "health_fit": {"flags": health_fit_flags, "scores": {}, "adjustments": []},
                "leftover_forecast": {"expected_leftover_servings": 0, "reuse_ideas": []},
                "preservation_guidance": {
                    "storage": storage,
                    "safe_duration_hours": 24,
                    "reheat_methods": [],
                    "quality_notes": "",
                },
                "youtube_references": recipe.get("youtube_references") if isinstance(recipe.get("youtube_references"), list) else [],
                "agent_mode": "beginner_coach",
            }
            return option

        courses_out: list[dict[str, Any]] = []
        for ch in course_headers:
            v = legacy_menus.get(ch)
            recipe_list = v if isinstance(v, list) else []
            options: list[dict[str, Any]] = []
            for idx, rec in enumerate(recipe_list[:3], start=1):
                options.append(_legacy_recipe_to_option(rec, course_header=ch, idx=idx))
            courses_out.append({"course_header": ch, "recipe_options": options})

        result["menu_headers"] = course_headers
        result["menus"] = [
            {
                "menu_type": "daily",
                "servings": {"count": servings_count, "scaling_factor": 1},
                "courses": courses_out,
            }
        ]

    # Normalize common alias fields.
    if "questions" in result and "needs_clarification_questions" not in result:
        q = result.get("questions")
        result["needs_clarification_questions"] = q if isinstance(q, list) else []
        result.pop("questions", None)

    # Additional alias normalization seen in some prompts/tooling.
    # Some generators return a single string field instead of the list.
    if result.get("status") == "needs_clarification":
        q = result.get("needs_clarification_questions")
        has_q_list = isinstance(q, list) and any(isinstance(item, str) and item.strip() for item in q)

        if not has_q_list:
            single = None
            for key in ("clarification_question", "clarification", "message"):
                v = result.get(key)
                if isinstance(v, str) and v.strip():
                    single = v.strip()
                    break

            if single:
                result["needs_clarification_questions"] = [single]
                # Keep response consistent: error_message should be a readable summary.
                if not isinstance(result.get("error_message"), str) or not result.get("error_message", "").strip():
                    result["error_message"] = single

    min_items = _get_menu_plan_recipe_options_min_items(schema)
    if min_items <= 0:
        return result

    menus = result.get("menus")
    if not isinstance(menus, list):
        return result

    # Ensure required top-level fields exist (schema allows empty arrays/objects).
    if not isinstance(result.get("menu_headers"), list):
        result["menu_headers"] = []
    if not isinstance(result.get("variety_log"), dict):
        result["variety_log"] = {"rules_applied": [], "excluded_recent": [], "diversity_scores": {}}
    if not isinstance(result.get("nutrition_summary"), dict):
        result["nutrition_summary"] = {"total_calories_kcal": 0, "per_member_estimates": [], "warnings": []}
    if not isinstance(result.get("waste_summary"), dict):
        result["waste_summary"] = {
            "expiring_items_used": [],
            "waste_reduction_score": 0,
            "waste_avoided_value_estimate": {"currency": "USD", "value": 0},
        }
    if not isinstance(result.get("shopping_suggestions"), list):
        result["shopping_suggestions"] = []

    selected_cuisine_val = result.get("selected_cuisine")
    cuisine_for_fallback = selected_cuisine_val if isinstance(selected_cuisine_val, str) and selected_cuisine_val.strip() else "unknown"

    for menu in menus:
        if not isinstance(menu, dict):
            continue
        courses = menu.get("courses")
        if not isinstance(courses, list):
            continue

        for course in courses:
            if not isinstance(course, dict):
                continue
            course_header = course.get("course_header")
            recipe_options = course.get("recipe_options")
            if not isinstance(recipe_options, list):
                recipe_options = []
                course["recipe_options"] = recipe_options

            # Ensure the course header is a string for naming fallbacks.
            ch = course_header if isinstance(course_header, str) and course_header.strip() else "Course"

            # If the LLM returned empty recipe_options, synthesize minimal schema-valid options.
            if not recipe_options:
                for idx in range(1, min_items + 1):
                    recipe_options.append(
                        _synthesize_minimal_recipe_option(
                            recipe_id=f"r_{ch.lower().replace(' ', '_')}_{idx}",
                            recipe_name=f"{ch} Option {idx}",
                            cuisine=cuisine_for_fallback,
                        )
                    )

            # Normalize each option to satisfy required keys and types.
            for opt_idx, opt in enumerate(list(recipe_options)):
                if not isinstance(opt, dict):
                    recipe_options[opt_idx] = _synthesize_minimal_recipe_option(
                        recipe_id=f"r_{ch.lower().replace(' ', '_')}_synth{opt_idx+1}",
                        recipe_name=f"{ch} Option {opt_idx + 1}",
                        cuisine=cuisine_for_fallback,
                    )
                    opt = recipe_options[opt_idx]

                rn = opt.get("recipe_name")
                if isinstance(rn, str) and rn.strip():
                    opt["recipe_name"] = {"en": rn.strip()}
                elif not isinstance(rn, dict):
                    opt["recipe_name"] = {"en": f"{ch} Option {opt_idx + 1}"}

                if not isinstance(opt.get("recipe_id"), str) or not str(opt.get("recipe_id") or "").strip():
                    opt["recipe_id"] = f"r_{ch.lower().replace(' ', '_')}_{opt_idx + 1}"

                if not isinstance(opt.get("cuisine"), str) or not str(opt.get("cuisine") or "").strip():
                    opt["cuisine"] = cuisine_for_fallback

                if opt.get("difficulty") not in ["easy", "medium", "hard"]:
                    opt["difficulty"] = "easy"

                et = opt.get("estimated_times")
                if not isinstance(et, dict):
                    opt["estimated_times"] = {"prep_minutes": 10, "cook_minutes": 15, "total_minutes": 25}
                else:
                    for k in ("prep_minutes", "cook_minutes", "total_minutes"):
                        if not isinstance(et.get(k), (int, float)):
                            et[k] = 0

                if not isinstance(opt.get("cooking_method"), str) or not str(opt.get("cooking_method") or "").strip():
                    opt["cooking_method"] = "stovetop"

                if not isinstance(opt.get("ingredients_used"), list):
                    opt["ingredients_used"] = []
                if not isinstance(opt.get("new_ingredients_optional"), list):
                    opt["new_ingredients_optional"] = []
                if not isinstance(opt.get("steps"), list) or not opt.get("steps"):
                    opt["steps"] = [
                        {
                            "step": 1,
                            "instruction": {"en": "Prepare ingredients and cook until done."},
                            "time_minutes": 15,
                            "tips": [],
                        }
                    ]

                nps = opt.get("nutrition_per_serving")
                if not isinstance(nps, dict):
                    opt["nutrition_per_serving"] = {
                        "calories_kcal": 0,
                        "macros": {"protein_g": 0, "carbs_g": 0, "fat_g": 0},
                        "micros": {},
                    }
                else:
                    if not isinstance(nps.get("calories_kcal"), (int, float)):
                        nps["calories_kcal"] = 0
                    if not isinstance(nps.get("macros"), dict):
                        nps["macros"] = {"protein_g": 0, "carbs_g": 0, "fat_g": 0}
                    if not isinstance(nps.get("micros"), dict):
                        nps["micros"] = {}

                if not isinstance(opt.get("health_benefits"), list):
                    opt["health_benefits"] = []

                hf = opt.get("health_fit")
                if not isinstance(hf, dict):
                    opt["health_fit"] = {"flags": [], "scores": {}, "adjustments": []}
                else:
                    if not isinstance(hf.get("flags"), list):
                        hf["flags"] = []
                    if not isinstance(hf.get("scores"), dict):
                        hf["scores"] = {}
                    if not isinstance(hf.get("adjustments"), list):
                        hf["adjustments"] = []

                lf = opt.get("leftover_forecast")
                if not isinstance(lf, dict):
                    opt["leftover_forecast"] = {"expected_leftover_servings": 0, "reuse_ideas": []}
                else:
                    if not isinstance(lf.get("expected_leftover_servings"), (int, float)):
                        lf["expected_leftover_servings"] = 0
                    if not isinstance(lf.get("reuse_ideas"), list):
                        lf["reuse_ideas"] = []

                pg = opt.get("preservation_guidance")
                if not isinstance(pg, dict):
                    opt["preservation_guidance"] = {
                        "storage": "refrigerate",
                        "safe_duration_hours": 24,
                        "reheat_methods": [],
                        "quality_notes": "Best within a day.",
                    }
                else:
                    if pg.get("storage") not in ["refrigerate", "freeze"]:
                        pg["storage"] = "refrigerate"
                    if not isinstance(pg.get("safe_duration_hours"), (int, float)):
                        pg["safe_duration_hours"] = 24
                    if not isinstance(pg.get("reheat_methods"), list):
                        pg["reheat_methods"] = []
                    if not isinstance(pg.get("quality_notes"), str):
                        pg["quality_notes"] = ""

                if not isinstance(opt.get("youtube_references"), list):
                    opt["youtube_references"] = []

                if not isinstance(opt.get("agent_mode"), str) or not str(opt.get("agent_mode") or "").strip():
                    opt["agent_mode"] = "beginner_coach"

            if len(recipe_options) >= min_items:
                continue

            base = recipe_options[-1]
            if not isinstance(base, dict):
                continue

            # Pad by cloning the last option and making recipe_id unique.
            for idx in range(len(recipe_options) + 1, min_items + 1):
                cloned = dict(base)
                try:
                    cloned["recipe_id"] = f"{base.get('recipe_id', 'recipe')}-alt{idx}"
                except Exception:
                    cloned["recipe_id"] = f"recipe-alt{idx}"
                recipe_options.append(cloned)

    return result


def _schema_is_object(schema: Dict[str, Any]) -> bool:
    t = schema.get("type")
    if t == "object":
        return True
    if isinstance(t, list) and "object" in t:
        return True
    return False


def _schema_is_array(schema: Dict[str, Any]) -> bool:
    t = schema.get("type")
    if t == "array":
        return True
    if isinstance(t, list) and "array" in t:
        return True
    return False


def _prune_additional_properties(instance: Any, schema: Dict[str, Any]) -> Any:
    """Remove unexpected fields when schema sets additionalProperties=false.

    This is a best-effort sanitizer for LLM outputs; it is not a full JSON Schema implementation.
    """
    if instance is None or not isinstance(schema, dict):
        return instance

    # Handle arrays
    if isinstance(instance, list) and _schema_is_array(schema):
        item_schema = schema.get("items")
        if isinstance(item_schema, dict):
            for i in range(len(instance)):
                instance[i] = _prune_additional_properties(instance[i], item_schema)
        return instance

    # Handle objects
    if isinstance(instance, dict) and _schema_is_object(schema):
        props = schema.get("properties") or {}
        pattern_props = schema.get("patternProperties") or {}
        additional = schema.get("additionalProperties", True)

        # Prune unexpected keys when additionalProperties is false
        if additional is False and isinstance(props, dict):
            allowed = set(props.keys())
            keys = list(instance.keys())
            for k in keys:
                if k in allowed:
                    continue
                matched_pattern = False
                if isinstance(pattern_props, dict) and pattern_props:
                    for pattern in pattern_props.keys():
                        try:
                            import re

                            if re.match(pattern, str(k)):
                                matched_pattern = True
                                break
                        except Exception:
                            continue
                if not matched_pattern:
                    instance.pop(k, None)

        # Recurse into known properties
        if isinstance(props, dict):
            for k, sub_schema in props.items():
                if k in instance and isinstance(sub_schema, dict):
                    instance[k] = _prune_additional_properties(instance[k], sub_schema)
        return instance

    return instance


def _build_messages(*, task_name: str, context: Dict[str, Any]) -> list[dict[str, str]]:
    system_lines = get_system_prompt_lines()
    task = get_task(task_name)

    system = "\n".join(system_lines)
    task_instructions = "\n".join(task.get("prompt", []))

    extra_instructions: list[dict[str, str]] = []
    try:
        output_languages = context.get("output_languages")
        if isinstance(output_languages, list):
            langs = [l.strip() for l in output_languages if isinstance(l, str) and l.strip()]
            if "en" in langs and len(langs) > 1:
                preferred = next((l for l in langs if l != "en"), None)
                if preferred:
                    extra_instructions.append(
                        {
                            "role": "user",
                            "content": (
                                "BILINGUAL_OUTPUT:\n"
                                f"- Include BOTH 'en' and '{preferred}' values for all multilingual fields (e.g., recipe_name and steps[].instruction).\n"
                                "- Always include a non-empty English ('en') string.\n"
                                f"- Also include a non-empty '{preferred}' string.\n"
                                "- Keep both strings semantically equivalent; do not mix languages in one value.\n"
                            ),
                        }
                    )
    except Exception:
        # Best-effort only; do not break prompt generation.
        pass
    context_json = json.dumps(context, ensure_ascii=False)

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": task_instructions},
        *extra_instructions,
        {"role": "user", "content": f"CONTEXT_JSON={context_json}"},
    ]


def _authenticity_judge_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "is_authentic": {"type": "boolean"},
            "confidence": {"type": "number"},
            "issues": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string"},
                        "code": {"type": "string"},
                        "message": {"type": "string"},
                        "path": {"type": "string"},
                    },
                    "required": ["severity", "code", "message", "path"],
                    "additionalProperties": False,
                },
            },
            "suggested_fixes": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["is_authentic", "confidence", "issues", "suggested_fixes"],
        "additionalProperties": False,
    }


def _build_authenticity_judge_messages(
    *,
    task_name: str,
    plan_payload: Dict[str, Any],
    meal_type: Optional[str] = None,
) -> list[dict[str, str]]:
    # Keep this small to reduce truncation risk.
    plan_json = json.dumps(plan_payload, ensure_ascii=False)
    system = (
        "You are a strict culinary authenticity and validity judge. "
        "Your job is to detect semantically wrong / junk recipes (misnamed dishes, missing core base ingredients, unrealistic steps). "
        "Be conservative: if unsure, flag issues rather than approving. "
        "Return ONLY valid JSON matching the provided schema."
    )
    selected = plan_payload.get("selected_cuisine")
    selected_key = selected.strip().lower() if isinstance(selected, str) else ""
    meta_brief = {}
    if selected_key:
        try:
            from app.core.cuisine_metadata import CUISINE_METADATA

            m = CUISINE_METADATA.get(selected_key)
            if isinstance(m, dict):
                meta_brief = {
                    "name": m.get("name"),
                    "daily_structure": m.get("daily_structure"),
                    "party_structure": m.get("party_structure"),
                    "characteristics": m.get("characteristics"),
                    "keywords": m.get("keywords"),
                }
        except Exception:
            meta_brief = {}

    meal_line = f"MEAL_TYPE={meal_type.strip().lower()}\n" if isinstance(meal_type, str) and meal_type.strip() else ""

    user = (
        f"TASK={task_name}\n"
        f"{meal_line}"
        "Evaluate MENU_PLAN payload for authenticity and cuisine alignment.\n"
        "Selected cuisine is payload.selected_cuisine; you must enforce that dishes, course headers, and menu headers match CUISINE_METADATA for that cuisine.\n"
        "Rules:\n"
        "- Cuisine alignment: dishes should fit the selected cuisine's characteristics/keywords; avoid cross-cuisine mashups unless clearly labeled and appropriate.\n"
        "- Course structure: menu_headers and course_header should align with CUISINE_METADATA[selected_cuisine].daily_structure/party_structure.\n"
        "- Base-ingredient realism: dal requires pulses/lentils; biryani requires rice; roti/chapati requires atta; idli/dosa requires batter base; etc.\n"
        "- Ingredients must match dish; spices cannot be the main base ingredient.\n"
        "- Steps must be plausible and non-empty.\n"
        "- Missing required ingredients must go in new_ingredients_optional with a reason; do not pretend they exist in pantry.\n"
        "Output issues[] with a JSON pointer-ish path into the payload when possible.\n"
        f"CUISINE_METADATA_BRIEF={json.dumps(meta_brief, ensure_ascii=False)}\n"
        f"PLAN_JSON={plan_json}"
    )
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


async def run_task(
    *,
    task_name: str,
    output_schema_name: str,
    context: Dict[str, Any],
    max_retries: int = 1
) -> Dict[str, Any]:
    """
    Run LLM task with schema validation and retry logic (2.4 AI orchestration reliability)
    
    Fail-closed behavior:
    - If LLM returns non-JSON or schema-invalid on first try: send one corrective retry
    - If still invalid after retry: return status="error" with error details
    - If LLM cannot fulfill request: return status="needs_clarification" with questions
    - If primary provider hits 429 rate limit: fallback to configured fallback provider (429 only)
    """
    schema = get_schema(output_schema_name)
    messages = _build_messages(task_name=task_name, context=context)
    trace_id = uuid.uuid4().hex[:8]
    total_t0 = perf_counter()
    
    # Use reasoning provider for planning tasks (meal plans, recipes, etc.)
    # OpenAI GPT excels at structured JSON outputs and complex reasoning
    result = await _try_provider(
        provider=settings.reasoning_provider,
        messages=messages,
        schema=schema,
        task_name=task_name,
        output_schema_name=output_schema_name,
        max_retries=max_retries,
        context=context,
        trace_id=trace_id,
    )

    total_ms = int((perf_counter() - total_t0) * 1000)
    try:
        status_val = result.get("status") if isinstance(result, dict) else None
    except Exception:
        status_val = None
    logger.info(
        "orchestrator_task_done task=%s schema=%s trace=%s provider=%s status=%s total_ms=%s",
        task_name,
        output_schema_name,
        trace_id,
        settings.reasoning_provider,
        status_val,
        total_ms,
    )

    return result


async def _try_provider(
    *,
    provider: str,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    task_name: str,
    output_schema_name: str,
    max_retries: int,
    context: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Try a specific LLM provider with schema validation and retry logic.
    Raises RateLimitException if provider hits 429 after all retries.
    """
    client = get_llm_client(provider)
    last_error: Optional[str] = None
    
    for attempt in range(max_retries + 1):
        attempt_t0 = perf_counter()
        llm_ms: Optional[int] = None
        repair_ms: Optional[int] = None
        schema_ms: Optional[int] = None
        semantic_ms: Optional[int] = None
        judge_ms: Optional[int] = None
        try:
            llm_t0 = perf_counter()
            result = await client.generate_json(messages=messages, schema=schema)
            llm_ms = int((perf_counter() - llm_t0) * 1000)

            # Repair common issues before strict schema validation.
            if output_schema_name == "MENU_PLAN_SCHEMA" and isinstance(result, dict):
                repair_t0 = perf_counter()
                result = _repair_menu_plan_result(result, schema)
                result = _prune_additional_properties(result, schema)
                repair_ms = int((perf_counter() - repair_t0) * 1000)
            
            # Validate against schema
            schema_t0 = perf_counter()
            validate_json(result, schema)
            schema_ms = int((perf_counter() - schema_t0) * 1000)

            # Semantic/authenticity validation (fail closed): if it's structurally valid JSON
            # but semantically invalid (e.g., "dal" without pulses), retry with targeted feedback.
            if (
                output_schema_name == "MENU_PLAN_SCHEMA"
                and isinstance(result, dict)
                and result.get("status") == "ok"
            ):
                semantic_t0 = perf_counter()
                semantic_issues = validate_menu_plan_semantics(result)
                semantic_issues.extend(
                    validate_menu_plan_structure_against_metadata(payload=result, task_name=task_name)
                )
                fatal = [i for i in semantic_issues if i.severity == "error"]
                if fatal:
                    raise SemanticValidationException(fatal)
                semantic_ms = int((perf_counter() - semantic_t0) * 1000)

                if settings.enable_authenticity_judge:
                    meal_type = context.get("meal_type") if isinstance(context, dict) else None
                    judge_messages = _build_authenticity_judge_messages(
                        task_name=task_name,
                        plan_payload=result,
                        meal_type=meal_type if isinstance(meal_type, str) else None,
                    )
                    judge_schema = _authenticity_judge_schema()
                    judge_t0 = perf_counter()
                    judge = await client.generate_json(messages=judge_messages, schema=judge_schema)
                    judge_ms = int((perf_counter() - judge_t0) * 1000)
                    validate_json(judge, judge_schema)

                    if isinstance(judge, dict) and judge.get("is_authentic") is False:
                        issues = judge.get("issues") if isinstance(judge.get("issues"), list) else []
                        top = []
                        for it in issues[:8]:
                            if not isinstance(it, dict):
                                continue
                            sev = str(it.get("severity") or "error")
                            code = str(it.get("code") or "JUDGE_ISSUE")
                            msg = str(it.get("message") or "")
                            path = str(it.get("path") or "")
                            top.append(f"- {sev}:{code} {msg} (path: {path})")
                        summary = "\n".join(top) if top else "- JUDGE_REJECTED: Plan deemed inauthentic/invalid"

                        if settings.authenticity_judge_fail_closed:
                            raise AuthenticityJudgeException(summary)
                        logger.warning("Authenticity judge flagged issues but fail_closed=false. Issues=%s", summary)
            
            # Check if LLM itself returned an error status
            if isinstance(result, dict):
                status = result.get("status")
                if status in ["needs_clarification", "error"]:
                    # LLM is reporting it cannot fulfill request - this is valid
                    logger.info(f"Task {task_name} (provider={provider}) returned status={status}")
                    return result
            
            # Validation passed, return result
            attempt_ms = int((perf_counter() - attempt_t0) * 1000)
            logger.info(
                "orchestrator_attempt_ok task=%s schema=%s trace=%s provider=%s attempt=%s llm_ms=%s repair_ms=%s schema_ms=%s semantic_ms=%s judge_ms=%s attempt_ms=%s",
                task_name,
                output_schema_name,
                trace_id,
                provider,
                attempt + 1,
                llm_ms,
                repair_ms,
                schema_ms,
                semantic_ms,
                judge_ms,
                attempt_ms,
            )
            return result
            
        except RateLimitException as e:
            # Rate limit hit - try fallback if configured
            logger.warning(f"Task {task_name} hit rate limit on {provider}: {str(e)}")
            
            if settings.llm_fallback_provider and settings.llm_fallback_provider != provider:
                logger.info(f"Falling back from {provider} to {settings.llm_fallback_provider}")
                try:
                    # Try fallback provider (no additional retries for fallback)
                    fallback_result = await _try_provider(
                        provider=settings.llm_fallback_provider,
                        messages=messages,
                        schema=schema,
                        task_name=task_name,
                        output_schema_name=output_schema_name,
                        max_retries=0  # No retries for fallback
                    )
                    logger.info(f"Task {task_name} succeeded with fallback provider {settings.llm_fallback_provider}")
                    return fallback_result
                except Exception as fallback_error:
                    logger.error(f"Fallback provider {settings.llm_fallback_provider} also failed: {str(fallback_error)}")
                    last_error = f"Primary provider ({provider}) rate limited, fallback provider ({settings.llm_fallback_provider}) failed: {str(fallback_error)}"
            else:
                last_error = f"Rate limit exceeded on {provider} and no fallback configured"
            
            # No fallback available or fallback failed
            break
            
        except SchemaValidationException as e:
            last_error = f"Schema validation failed: {', '.join(e.errors)}"
            logger.warning(f"Task {task_name} (provider={provider}) attempt {attempt + 1} failed: {last_error}")
            logger.info(
                "orchestrator_attempt_fail task=%s schema=%s trace=%s provider=%s attempt=%s error=%s attempt_ms=%s llm_ms=%s repair_ms=%s",
                task_name,
                output_schema_name,
                trace_id,
                provider,
                attempt + 1,
                "SchemaValidationException",
                int((perf_counter() - attempt_t0) * 1000),
                llm_ms,
                repair_ms,
            )
            
            if attempt < max_retries:
                # Add corrective instruction for retry
                correction = (
                    f"CORRECTION REQUIRED: Your previous response had schema validation errors: {last_error}. "
                    f"Please generate a valid response that strictly matches the JSON schema. "
                    f"IMPORTANT: keep output minimal to avoid truncation. Use minified JSON (no newlines). "
                    f"Do NOT include unexpected fields like 'questions'. Use needs_clarification_questions only. "
                    f"For each recipe: youtube_references=[]; health_benefits=[]; new_ingredients_optional max 3 items (only truly needed); steps length 1-2 with tips=[]; "
                    f"health_fit.flags=[], health_fit.adjustments=[], health_fit.scores={{}}; leftover_forecast.reuse_ideas=[]."
                )
                messages.append({"role": "assistant", "content": "I will correct my response."})
                messages.append({"role": "user", "content": correction})
                continue

        except SemanticValidationException as e:
            last_error = f"Semantic validation failed: {len(e.issues)} issue(s)"
            logger.warning(
                f"Task {task_name} (provider={provider}) attempt {attempt + 1} failed: {last_error}"
            )
            logger.info(
                "orchestrator_attempt_fail task=%s schema=%s trace=%s provider=%s attempt=%s error=%s attempt_ms=%s llm_ms=%s",
                task_name,
                output_schema_name,
                trace_id,
                provider,
                attempt + 1,
                "SemanticValidationException",
                int((perf_counter() - attempt_t0) * 1000),
                llm_ms,
            )

            if attempt < max_retries:
                issue_text = format_semantic_issues_for_prompt(e.issues)
                correction = (
                    "CORRECTION REQUIRED: Your previous response was schema-valid JSON, but the recipes are semantically invalid/untrustworthy. "
                    "Fix the invalid recipes so they are authentic and logically correct (do not output junk).\n"
                    "Issues found:\n"
                    f"{issue_text}\n"
                    "Requirements:\n"
                    "- Keep the SAME JSON schema and required keys.\n"
                    "- For dish names like dal/biryani/roti/poha/upma/idli/dosa/khichdi: ensure the core base ingredient is present.\n"
                    "- If an ingredient is missing from pantry, put it in new_ingredients_optional with a short reason; do not pretend it's in pantry.\n"
                    "- Keep output concise (minified JSON; short text fields) to avoid truncation."
                )
                messages.append({"role": "assistant", "content": "I will regenerate authentic, valid recipes."})
                messages.append({"role": "user", "content": correction})
                continue

        except AuthenticityJudgeException as e:
            last_error = "Authenticity judge rejected plan"
            logger.warning(
                f"Task {task_name} (provider={provider}) attempt {attempt + 1} failed: {last_error}"
            )
            logger.info(
                "orchestrator_attempt_fail task=%s schema=%s trace=%s provider=%s attempt=%s error=%s attempt_ms=%s llm_ms=%s judge_ms=%s",
                task_name,
                output_schema_name,
                trace_id,
                provider,
                attempt + 1,
                "AuthenticityJudgeException",
                int((perf_counter() - attempt_t0) * 1000),
                llm_ms,
                judge_ms,
            )

            if attempt < max_retries:
                correction = (
                    "CORRECTION REQUIRED: An authenticity judge reviewed your schema-valid plan and rejected it as not trustworthy/authentic.\n"
                    "Judge issues:\n"
                    f"{e.issues_text}\n"
                    "Requirements:\n"
                    "- Regenerate ONLY the invalid parts; keep the response schema-valid.\n"
                    "- Ensure dish names match ingredients and core base ingredients are present.\n"
                    "- Do not output junk or placeholder recipes.\n"
                    "- Keep output concise (minified JSON; short text fields)."
                )
                messages.append({"role": "assistant", "content": "I will regenerate a trustworthy, authentic plan."})
                messages.append({"role": "user", "content": correction})
                continue
                
        except json.JSONDecodeError as e:
            last_error = f"Invalid JSON returned: {str(e)}"
            logger.warning(f"Task {task_name} (provider={provider}) attempt {attempt + 1} failed: {last_error}")
            logger.info(
                "orchestrator_attempt_fail task=%s schema=%s trace=%s provider=%s attempt=%s error=%s attempt_ms=%s",
                task_name,
                output_schema_name,
                trace_id,
                provider,
                attempt + 1,
                "JSONDecodeError",
                int((perf_counter() - attempt_t0) * 1000),
            )
            
            if attempt < max_retries:
                correction = (
                    f"CORRECTION REQUIRED: Your previous response was not valid JSON. "
                    f"Error: {str(e)}. Please return ONLY valid JSON matching the schema. "
                    f"IMPORTANT: keep output minimal to avoid truncation. Use minified JSON (no newlines). "
                    f"For each recipe: youtube_references=[]; new_ingredients_optional max 3 items (only truly needed); steps length 1-2 with tips=[]; "
                    f"health_fit.flags=[], health_fit.adjustments=[], health_fit.scores={{}}; leftover_forecast.reuse_ideas=[]."
                )
                messages.append({"role": "assistant", "content": "I will return valid JSON."})
                messages.append({"role": "user", "content": correction})
                continue

        except ValueError as e:
            # Provider can surface truncation (finish_reason=length) as a ValueError.
            # Retry with explicit instructions to reduce verbosity.
            if "Response truncated" in str(e):
                last_error = f"Response truncated: {str(e)}"
                logger.warning(
                    f"Task {task_name} (provider={provider}) attempt {attempt + 1} failed: {last_error}"
                )

                if attempt < max_retries:
                    correction = (
                        "CORRECTION REQUIRED: Your previous response was truncated due to length. "
                        "Return a STRICTLY schema-valid JSON response, but make it MUCH smaller: "
                        "use the minimum number of items needed; keep all free-text fields short; "
                        "for each recipe keep steps to 1-2 items and tips=[]; youtube_references=[]; "
                        "new_ingredients_optional max 3 items (only truly needed); leftover_forecast.reuse_ideas=[]. "
                        "IMPORTANT: Use minified JSON (no newlines) and do NOT include any extra keys."
                    )
                    messages.append({"role": "assistant", "content": "I will return a shorter, schema-valid response."})
                    messages.append({"role": "user", "content": correction})
                    continue

                # Final attempt exhausted: do not crash the API. Return an error-shaped response.
                break
            raise
                
        except Exception as e:
            last_error = f"Unexpected error: {str(e)}"
            logger.error(f"Task {task_name} (provider={provider}) attempt {attempt + 1} failed with unexpected error", exc_info=True)
            logger.info(
                "orchestrator_attempt_fail task=%s schema=%s trace=%s provider=%s attempt=%s error=%s attempt_ms=%s",
                task_name,
                output_schema_name,
                trace_id,
                provider,
                attempt + 1,
                type(e).__name__,
                int((perf_counter() - attempt_t0) * 1000),
            )
            if attempt < max_retries:
                continue
    
    # All retries exhausted - return error response in schema format
    logger.error(f"Task {task_name} (provider={provider}) failed after {max_retries + 1} attempts: {last_error}")
    
    return _build_error_response(output_schema_name, last_error, max_retries)


def _build_error_response(output_schema_name: str, error_message: str, max_retries: int) -> Dict[str, Any]:
    """Build error response matching the output schema structure"""
    # Never surface internal schema pointers / stack traces to the client UI.
    # Keep the detailed failure in logs (see run_task/_try_provider logging), but return a short message.
    raw = (error_message or "").strip()
    user_msg = "Recipe generation failed. Please try again."
    low = raw.lower()
    if "response truncated" in low or "finish_reason=length" in low:
        user_msg = "Recipe generation produced too much output. Please try again."
    elif "readtimeout" in low or "timed out" in low or "timeout" in low:
        user_msg = "Recipe generation timed out. Please try again."
    elif "schema validation" in low or "invalid json" in low:
        user_msg = "Recipe generation failed to produce a valid plan. Please try again."

    error_response = {
        "status": "error",
        "needs_clarification_questions": [],
        "error_message": user_msg,
    }
    
    # For MENU_PLAN_SCHEMA, add required fields
    if output_schema_name == "MENU_PLAN_SCHEMA":
        error_response.update({
            "selected_cuisine": "unknown",
            "menu_headers": [],
            "menus": [],
            "variety_log": {"rules_applied": [], "excluded_recent": [], "diversity_scores": {}},
            "nutrition_summary": {"total_calories_kcal": 0, "per_member_estimates": [], "warnings": []},
            "waste_summary": {
                "expiring_items_used": [],
                "waste_reduction_score": 0,
                "waste_avoided_value_estimate": {"currency": "USD", "value": 0}
            },
            "shopping_suggestions": []
        })
    
    return error_response


async def normalize_inventory(context: Dict[str, Any]) -> Dict[str, Any]:
    return await run_task(
        task_name="normalize_inventory",
        output_schema_name="NORMALIZATION_OUTPUT_SCHEMA",
        context=context,
    )


async def plan_daily(context: Dict[str, Any]) -> Dict[str, Any]:
    return await run_task(
        task_name="plan_daily_menu",
        output_schema_name="MENU_PLAN_SCHEMA",
        context=context,
        max_retries=2,
    )


async def plan_party(context: Dict[str, Any]) -> Dict[str, Any]:
    return await run_task(
        task_name="plan_party_menu",
        output_schema_name="MENU_PLAN_SCHEMA",
        context=context,
        max_retries=2,
    )


async def plan_weekly(context: Dict[str, Any]) -> Dict[str, Any]:
    return await run_task(
        task_name="plan_weekly",
        output_schema_name="MENU_PLAN_SCHEMA",
        context=context,
        max_retries=2,
    )


async def youtube_rank(context: Dict[str, Any]) -> Dict[str, Any]:
    return await run_task(
        task_name="youtube_rank",
        output_schema_name="YOUTUBE_RANK_SCHEMA",
        context=context,
    )
