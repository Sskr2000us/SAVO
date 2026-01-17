from __future__ import annotations

from typing import Any, Dict, List, Optional


def _has(pantry_names: List[str], *needles: str) -> bool:
    p = " ".join((x or "").lower() for x in (pantry_names or []))
    return any(n.lower() in p for n in needles if (n or "").strip())


def build_pantry_bowl_plan(
    *,
    pantry_names: List[str],
    cuisine: Optional[str],
    request_text: str,
    expiring: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Deterministically propose a bowl structure.

    This is intentionally simple: the LLM still writes the final canonical recipe, but
    we give it a high-signal skeleton to reduce generic outputs.
    """

    c = (cuisine or "").strip().lower()
    rt = (request_text or "").strip().lower()

    base_options: list[str] = []
    if _has(pantry_names, "basmati", "rice"):
        base_options.append("rice")
    if _has(pantry_names, "quinoa"):
        base_options.append("quinoa")
    if _has(pantry_names, "millet", "ragi"):
        base_options.append("millet")

    if not base_options:
        base_options = ["rice"]

    if _has(pantry_names, "paneer"):
        main = "paneer"
    elif _has(pantry_names, "chickpea", "chana"):
        main = "chickpeas"
    elif _has(pantry_names, "lentil", "dal", "toor", "moong", "masoor"):
        main = "lentils"
    elif _has(pantry_names, "egg"):
        main = "eggs"
    else:
        main = "mixed vegetables"

    has_yogurt = _has(pantry_names, "yogurt", "curd")
    side = "cucumber raita" if (has_yogurt and _has(pantry_names, "cucumber")) else ("simple kachumber salad" if _has(pantry_names, "onion", "tomato") else "quick lemon-onion salad")

    condiment = "mint-coriander chutney" if _has(pantry_names, "mint", "coriander") else ("pickle" if _has(pantry_names, "pickle", "achar") else "lemon wedge")

    crunch = "roasted peanuts" if _has(pantry_names, "peanut") else ("roasted cashews" if _has(pantry_names, "cashew") else "tempered mustard-curry leaf tadka")

    style = "south_indian" if ("tamil" in c or "south" in c or _has(pantry_names, "curry leaves", "mustard seeds")) else "north_indian"
    if "biryani" in rt or "pulao" in rt:
        style = "north_indian"

    must_use: list[str] = []
    if expiring:
        must_use.extend([x for x in (expiring or [])[:2] if isinstance(x, str) and x.strip()])

    return {
        "intent": "indian_pantry_bowl",
        "style": style,
        "base_options": base_options,
        "chosen_main": main,
        "side": side,
        "condiment": condiment,
        "crunch": crunch,
        "must_use": must_use,
        "component_rules": [
            "bowl_must_have_base_main_side_condiment",
            "each_component_should_be_named_indian_element_not_generic",
            "overall_recipe_name_must_be_specific_not_pantry_bowl",
            "steps_should_assemble_components_then_finish_with_tempering_or_garnish",
        ],
    }
