from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence


@dataclass(frozen=True)
class SemanticIssue:
    severity: str  # "error" | "warning"
    code: str
    message: str
    path: str


class SemanticValidationException(Exception):
    def __init__(self, issues: Sequence[SemanticIssue]):
        super().__init__("Semantic validation failed")
        self.issues = list(issues)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def _recipe_display_name(recipe: Dict[str, Any]) -> str:
    rn = recipe.get("recipe_name")
    if isinstance(rn, dict):
        en = rn.get("en")
        if isinstance(en, str) and en.strip():
            return en.strip()
        for v in rn.values():
            if isinstance(v, str) and v.strip():
                return v.strip()
        return ""
    if isinstance(rn, str):
        return rn.strip()
    return ""


def _ingredient_names(recipe: Dict[str, Any]) -> List[str]:
    out: List[str] = []
    for key in ("ingredients_used", "new_ingredients_optional"):
        items = recipe.get(key)
        if not isinstance(items, list):
            continue
        for it in items:
            if not isinstance(it, dict):
                continue
            n = it.get("canonical_name") or it.get("name")
            if isinstance(n, str) and n.strip():
                out.append(n.strip().lower())
    return out


def _has_any_keyword(names: Iterable[str], keywords: Iterable[str]) -> bool:
    joined = " | ".join(names)
    if not joined:
        return False
    return any(k in joined for k in keywords)


_DAL_BASE_KEYWORDS = {
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
    "rajma",
    "chickpea",
    "chickpeas",
    "chana",
}

_BIRYANI_BASE_KEYWORDS = {
    "rice",
    "basmati",
}

_ROTI_BASE_KEYWORDS = {
    "wheat flour",
    "atta",
    "whole wheat",
}

_POHA_BASE_KEYWORDS = {
    "poha",
    "flattened rice",
    "beaten rice",
}

_UPMA_BASE_KEYWORDS = {
    "semolina",
    "rava",
    "sooji",
}

_IDLI_DOSA_BASE_KEYWORDS = {
    "idli rice",
    "rice",
    "urad",
    "black gram",
    "batter",
}

_KHICHDI_BASE_KEYWORDS = {
    "rice",
    "dal",
    "lentil",
    "lentils",
    "moong",
    "masoor",
    "toor",
}


def _looks_like(recipe: Dict[str, Any], *, words: Iterable[str], course_header: Optional[str] = None) -> bool:
    name = _normalize_text(_recipe_display_name(recipe))
    if name and any(f" {w} " in f" {name} " or name.endswith(f" {w}") for w in words):
        return True

    if isinstance(course_header, str):
        ch = course_header.strip().lower()
        if ch and any(ch == w or f" {w} " in f" {ch} " for w in words):
            return True

    return False


def validate_recipe(*, recipe: Dict[str, Any], path_prefix: str, course_header: Optional[str]) -> List[SemanticIssue]:
    issues: List[SemanticIssue] = []

    # Basic trust guardrails: recipe must have some ingredients and steps.
    ingredients_used = recipe.get("ingredients_used")
    if not isinstance(ingredients_used, list) or len(ingredients_used) == 0:
        issues.append(
            SemanticIssue(
                severity="error",
                code="RECIPE_NO_INGREDIENTS",
                message="Recipe is missing ingredients_used; do not return empty ingredient lists.",
                path=f"{path_prefix}.ingredients_used",
            )
        )

    steps = recipe.get("steps")
    if not isinstance(steps, list) or len(steps) == 0:
        issues.append(
            SemanticIssue(
                severity="error",
                code="RECIPE_NO_STEPS",
                message="Recipe is missing steps; include at least 1 clear cooking step.",
                path=f"{path_prefix}.steps",
            )
        )

    # Dish-family authenticity checks (minimal but high-impact).
    names = _ingredient_names(recipe)

    if _looks_like(recipe, words={"dal"}, course_header=course_header):
        if not _has_any_keyword(names, _DAL_BASE_KEYWORDS):
            issues.append(
                SemanticIssue(
                    severity="error",
                    code="DAL_MISSING_PULSE_BASE",
                    message=(
                        "This recipe is labeled as dal but contains no pulse/lentil base. "
                        "Coriander seed is a spice, not the dal base. Include a lentil/pulse as the main ingredient."
                    ),
                    path=path_prefix,
                )
            )

    if _looks_like(recipe, words={"biryani"}, course_header=course_header):
        if not _has_any_keyword(names, _BIRYANI_BASE_KEYWORDS):
            issues.append(
                SemanticIssue(
                    severity="error",
                    code="BIRYANI_MISSING_RICE",
                    message="This recipe is labeled as biryani but has no rice/basmati in ingredients.",
                    path=path_prefix,
                )
            )

    if _looks_like(recipe, words={"roti", "chapati", "phulka"}, course_header=course_header):
        if not _has_any_keyword(names, _ROTI_BASE_KEYWORDS):
            issues.append(
                SemanticIssue(
                    severity="error",
                    code="ROTI_MISSING_ATTA",
                    message="This recipe is labeled as roti/chapati but has no wheat flour/atta in ingredients.",
                    path=path_prefix,
                )
            )

    if _looks_like(recipe, words={"poha"}, course_header=course_header):
        if not _has_any_keyword(names, _POHA_BASE_KEYWORDS):
            issues.append(
                SemanticIssue(
                    severity="error",
                    code="POHA_MISSING_POHA",
                    message="This recipe is labeled as poha but has no flattened rice/poha in ingredients.",
                    path=path_prefix,
                )
            )

    if _looks_like(recipe, words={"upma"}, course_header=course_header):
        if not _has_any_keyword(names, _UPMA_BASE_KEYWORDS):
            issues.append(
                SemanticIssue(
                    severity="error",
                    code="UPMA_MISSING_RAVA",
                    message="This recipe is labeled as upma but has no semolina/rava/sooji in ingredients.",
                    path=path_prefix,
                )
            )

    if _looks_like(recipe, words={"idli", "dosa"}, course_header=course_header):
        if not _has_any_keyword(names, _IDLI_DOSA_BASE_KEYWORDS):
            issues.append(
                SemanticIssue(
                    severity="error",
                    code="IDLI_DOSA_MISSING_BASE",
                    message="This recipe is labeled as idli/dosa but has no rice/urad/batter base in ingredients.",
                    path=path_prefix,
                )
            )

    if _looks_like(recipe, words={"khichdi", "khichri"}, course_header=course_header):
        if not _has_any_keyword(names, _KHICHDI_BASE_KEYWORDS):
            issues.append(
                SemanticIssue(
                    severity="error",
                    code="KHICHDI_MISSING_RICE_DAL",
                    message="This recipe is labeled as khichdi but is missing the rice + lentil base.",
                    path=path_prefix,
                )
            )

    return issues


def validate_menu_plan_semantics(payload: Dict[str, Any]) -> List[SemanticIssue]:
    issues: List[SemanticIssue] = []

    menus = payload.get("menus")
    if not isinstance(menus, list):
        return issues

    for mi, menu in enumerate(menus):
        if not isinstance(menu, dict):
            continue
        courses = menu.get("courses")
        if not isinstance(courses, list):
            continue
        for ci, course in enumerate(courses):
            if not isinstance(course, dict):
                continue
            course_header = course.get("course_header") if isinstance(course.get("course_header"), str) else None
            recipe_options = course.get("recipe_options")
            if not isinstance(recipe_options, list):
                continue
            for ri, recipe in enumerate(recipe_options):
                if not isinstance(recipe, dict):
                    continue
                path = f"menus[{mi}].courses[{ci}].recipe_options[{ri}]"
                issues.extend(validate_recipe(recipe=recipe, path_prefix=path, course_header=course_header))

    return issues


def validate_menu_plan_structure_against_metadata(
    *,
    payload: Dict[str, Any],
    task_name: str,
) -> List[SemanticIssue]:
    """Deterministic cuisine alignment checks using CUISINE_METADATA.

    This avoids geography tables: it only enforces the chosen cuisine's declared
    course structure (daily/party) and course header consistency.
    """

    issues: List[SemanticIssue] = []
    selected = payload.get("selected_cuisine")
    if not isinstance(selected, str) or not selected.strip() or selected.strip().lower() in {"unknown", "auto"}:
        return issues

    selected_key = selected.strip().lower()
    try:
        from app.core.cuisine_metadata import CUISINE_METADATA

        meta = CUISINE_METADATA.get(selected_key)
    except Exception:
        meta = None

    if not isinstance(meta, dict):
        return issues

    expected_headers: List[str] = []
    if "party" in task_name:
        expected_headers = meta.get("party_structure") or []
    else:
        # Default to daily structure for daily + weekly.
        expected_headers = meta.get("daily_structure") or []

    if not isinstance(expected_headers, list):
        expected_headers = []
    expected_headers = [str(h) for h in expected_headers if isinstance(h, str) and h.strip()]

    menu_headers = payload.get("menu_headers")
    if expected_headers and isinstance(menu_headers, list):
        got_headers = [str(h) for h in menu_headers if isinstance(h, str) and h.strip()]
        if got_headers and got_headers != expected_headers:
            issues.append(
                SemanticIssue(
                    severity="error",
                    code="MENU_HEADERS_MISMATCH",
                    message=(
                        f"menu_headers do not match CUISINE_METADATA[{selected_key}] structure. "
                        f"Expected={expected_headers} Got={got_headers}"
                    ),
                    path="menu_headers",
                )
            )

    # Course headers should align to one of the menu headers (or prefixed versions like "Appetizers 1").
    allowed_prefixes = set(expected_headers)
    menus = payload.get("menus")
    if not isinstance(menus, list) or not allowed_prefixes:
        return issues

    for mi, menu in enumerate(menus):
        if not isinstance(menu, dict):
            continue
        courses = menu.get("courses")
        if not isinstance(courses, list):
            continue
        for ci, course in enumerate(courses):
            if not isinstance(course, dict):
                continue
            ch = course.get("course_header")
            if not isinstance(ch, str) or not ch.strip():
                continue
            header = ch.strip()
            ok = header in allowed_prefixes or any(header.startswith(f"{p} ") for p in allowed_prefixes)
            if not ok:
                issues.append(
                    SemanticIssue(
                        severity="error",
                        code="COURSE_HEADER_NOT_IN_STRUCTURE",
                        message=(
                            f"course_header '{header}' is not part of the selected cuisine structure. "
                            f"Allowed prefixes={sorted(allowed_prefixes)}"
                        ),
                        path=f"menus[{mi}].courses[{ci}].course_header",
                    )
                )

    return issues


def format_semantic_issues_for_prompt(issues: Sequence[SemanticIssue], *, max_items: int = 8) -> str:
    # Keep it short to reduce truncation risk.
    lines: List[str] = []
    for it in list(issues)[:max_items]:
        lines.append(f"- {it.code}: {it.message} (path: {it.path})")
    if len(issues) > max_items:
        lines.append(f"- ...and {len(issues) - max_items} more issues")
    return "\n".join(lines)
