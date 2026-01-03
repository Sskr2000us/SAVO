"""
Safety constraint builders for AI prompt generation.
Implements Section 11 of user_profile.md - Religious, Cultural, and Safety Constraints.
"""
from typing import Dict, List, Set, Tuple, Any
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# UNIVERSAL STAPLES (Always Assumable)
# ============================================================================

UNIVERSAL_STAPLES = {
    "water": {"category": "liquid", "allergen_free": True},
    "salt": {"category": "seasoning", "allergen_free": True},
    "neutral_cooking_oil": {"category": "fat", "allergen_free": True, "note": "vegetable/canola"},
    "heat_source": {"category": "equipment", "assumed": True},
    "basic_cookware": {"category": "equipment", "assumed": True}
}


# ============================================================================
# CULTURAL SOFT STAPLES (Only After Consent/Learning)
# ============================================================================

SOFT_STAPLES_BY_CULTURE = {
    "South_Indian": {
        "soft_staples": ["mustard_seeds", "curry_leaves", "urad_dal", "turmeric", "coconut"],
        "confirm_before_use": True,
        "removable": True
    },
    "Italian": {
        "soft_staples": ["olive_oil", "garlic", "basil", "tomato", "parmesan"],
        "confirm_before_use": True,
        "removable": True
    },
    "Mexican": {
        "soft_staples": ["cumin", "cilantro", "lime", "chili_powder", "tortillas"],
        "confirm_before_use": True,
        "removable": True
    },
    "Chinese": {
        "soft_staples": ["soy_sauce", "ginger", "garlic", "rice_vinegar", "sesame_oil"],
        "confirm_before_use": True,
        "removable": True
    },
    "Indian": {
        "soft_staples": ["cumin", "coriander", "turmeric", "garam_masala", "ginger"],
        "confirm_before_use": True,
        "removable": True
    },
    "Middle_Eastern": {
        "soft_staples": ["cumin", "tahini", "lemon", "olive_oil", "garlic"],
        "confirm_before_use": True,
        "removable": True
    },
    "Mediterranean": {
        "soft_staples": ["olive_oil", "garlic", "lemon", "oregano", "feta"],
        "confirm_before_use": True,
        "removable": True
    }
}


# ============================================================================
# NEVER ASSUME (Always Require Explicit Confirmation)
# ============================================================================

NEVER_ASSUME = [
    # Allergen risks
    "nuts", "tree_nuts", "peanuts", "almonds", "walnuts", "cashews",
    "dairy", "milk", "butter", "cheese", "cream", "yogurt",
    "eggs",
    "soy_sauce", "soy", "tofu",
    "sesame", "sesame_oil",
    "shellfish", "shrimp", "crab", "lobster",
    "fish", "salmon", "tuna",
    
    # Spice blends (unknown composition)
    "garam_masala", "curry_powder", "five_spice", "za'atar", "ras_el_hanout",
    
    # Alcohol
    "wine", "beer", "cooking_wine", "sherry", "sake", "mirin",
    "vanilla_extract",  # Contains alcohol
    
    # Religious/cultural sensitivities
    "ghee",  # Dairy + potential religious significance
    "onion",  # Jain restriction
    "garlic",  # Jain restriction
    "beef", "ground_beef", "steak",  # Hindu/religious
    "pork", "bacon", "ham", "sausage",  # Muslim/Jewish/religious
    
    # Root vegetables (Jain restriction)
    "potato", "carrot", "radish", "turnip", "beet",
    
    # Specialty items
    "miso", "tahini", "fish_sauce", "oyster_sauce", "anchovies"
]


# ============================================================================
# RELIGIOUS DIETARY MAPS
# ============================================================================

RELIGIOUS_DIETARY_MAPS = {
    "jain": {
        "forbidden": ["onion", "garlic", "potato", "carrot", "radish", "turnip", "beet", "ginger"],
        "description": "Jain dietary restrictions (no onion, garlic, or root vegetables)",
        "category": "religious"
    },
    "halal": {
        "forbidden": ["pork", "bacon", "ham", "alcohol", "wine", "beer", "gelatin"],
        "requirements": "Meat must be halal-certified (proper slaughter)",
        "description": "Islamic halal dietary law",
        "category": "religious"
    },
    "kosher": {
        "forbidden": ["pork", "bacon", "shellfish", "shrimp", "crab", "lobster"],
        "requirements": "No mixing meat and dairy; meat must be kosher-certified",
        "description": "Jewish kosher dietary law",
        "category": "religious"
    },
    "no_beef": {
        "forbidden": ["beef", "ground_beef", "steak", "veal"],
        "description": "No beef products (Hindu/religious)",
        "category": "religious"
    },
    "no_pork": {
        "forbidden": ["pork", "bacon", "ham", "sausage", "pepperoni"],
        "description": "No pork products (Muslim/Jewish/religious)",
        "category": "religious"
    },
    "no_alcohol": {
        "forbidden": ["wine", "beer", "cooking_wine", "sherry", "sake", "mirin", "vanilla_extract"],
        "description": "No alcohol in any form",
        "category": "religious"
    }
}


# ============================================================================
# CONSTRAINT BUILDERS
# ============================================================================

def build_allergen_constraints(profile: Dict[str, Any]) -> str:
    """Build allergen constraints for AI prompt"""
    
    # Get all declared allergens across all family members
    all_allergens = set()
    for member in profile.get("members", []):
        allergens = member.get("allergens", [])
        all_allergens.update(allergens)
    
    if not all_allergens:
        return "No known allergens declared."
    
    # Format as STRICT constraint
    allergen_list = ", ".join(sorted(all_allergens))
    allergen_bullets = "\n".join(f"- {allergen} (in any form)" for allergen in sorted(all_allergens))
    
    return f"""
CRITICAL SAFETY CONSTRAINT - ALLERGENS:
The household has declared the following allergens: {allergen_list}

YOU MUST NEVER include ANY of these ingredients or derivatives:
{allergen_bullets}

This is a HARD constraint. If you cannot create a recipe without these ingredients, 
respond with: "I cannot safely suggest a recipe given your allergen restrictions."
"""


def build_religious_constraints(profile: Dict[str, Any]) -> str:
    """Build religious dietary restriction constraints for AI prompt"""
    
    # Aggregate all dietary restrictions
    restrictions = set()
    for member in profile.get("members", []):
        diet = member.get("dietary_restrictions", [])
        restrictions.update(diet)
    
    if not restrictions:
        return "No religious dietary restrictions."
    
    # Identify religious restrictions
    religious_restrictions = []
    constraint_text = []
    
    for restriction in sorted(restrictions):
        restriction_lower = restriction.lower().replace(" ", "_")
        
        if restriction_lower in RELIGIOUS_DIETARY_MAPS:
            religious_info = RELIGIOUS_DIETARY_MAPS[restriction_lower]
            religious_restrictions.append(restriction)
            
            forbidden_items = ", ".join(religious_info["forbidden"])
            constraint_text.append(f"- {religious_info['description']}")
            constraint_text.append(f"  Forbidden: {forbidden_items}")
            
            if "requirements" in religious_info:
                constraint_text.append(f"  Requirements: {religious_info['requirements']}")
    
    if not religious_restrictions:
        return "No religious dietary restrictions."
    
    return f"""
CRITICAL RELIGIOUS CONSTRAINTS (Deeply Held Beliefs):
The household follows these religious dietary restrictions:
{chr(10).join(constraint_text)}

These are HARD constraints representing religious beliefs.
You MUST respect these completely. If you cannot create a compliant recipe,
respond with: "I cannot suggest a recipe that respects your religious dietary restrictions."
"""


def build_dietary_constraints(profile: Dict[str, Any]) -> str:
    """Build general dietary restriction constraints for AI prompt"""
    
    # Aggregate all dietary restrictions
    restrictions = set()
    for member in profile.get("members", []):
        diet = member.get("dietary_restrictions", [])
        restrictions.update(diet)
    
    if not restrictions:
        return "No dietary restrictions."
    
    # Map restrictions to AI-friendly language
    restriction_map = {
        "vegetarian": "NO meat, poultry, or seafood",
        "vegan": "NO animal products (meat, dairy, eggs, honey)",
        "no_beef": "NO beef or beef products",
        "no_pork": "NO pork or pork products",
        "no_alcohol": "NO alcohol in any form (cooking wine, extracts)",
        "halal": "Only halal meat (no pork, proper slaughter)",
        "kosher": "Only kosher ingredients (no pork, no mixing meat/dairy)",
        "gluten_free": "NO gluten (wheat, barley, rye)",
        "dairy_free": "NO dairy products (milk, cheese, butter, cream)",
        "nut_free": "NO nuts or nut products",
        "jain": "NO onion, garlic, or root vegetables",
        "pescatarian": "NO meat or poultry (fish allowed)",
    }
    
    constraint_text = []
    for restriction in sorted(restrictions):
        restriction_key = restriction.lower().replace(" ", "_").replace("-", "_")
        if restriction_key in restriction_map:
            constraint_text.append(f"- {restriction_map[restriction_key]}")
        else:
            constraint_text.append(f"- {restriction}")
    
    return f"""
DIETARY CONSTRAINTS:
The household has the following dietary restrictions:
{chr(10).join(constraint_text)}

These are HARD constraints. You MUST respect these completely.
If you cannot create a compliant recipe, explain why.
"""


def build_cultural_context(profile: Dict[str, Any]) -> str:
    """Build cultural and regional context for AI prompt"""
    
    household = profile.get("household", {})
    region = household.get("region", "US")
    culture = household.get("culture", "western")
    
    # Get cultural soft staples if applicable
    cultural_staples = []
    culture_key = culture.replace(" ", "_").title()
    if culture_key in SOFT_STAPLES_BY_CULTURE:
        cultural_staples = SOFT_STAPLES_BY_CULTURE[culture_key]["soft_staples"]
    
    context = f"""
CULTURAL & REGIONAL CONTEXT:
- Region: {region}
- Cultural background: {culture}
"""
    
    if cultural_staples:
        staples_list = ", ".join(cultural_staples)
        context += f"""- Common ingredients in {culture} cuisine: {staples_list}
  (Ask before assuming availability of specialty items)
"""
    
    return context


def build_spice_preferences(profile: Dict[str, Any]) -> str:
    """Build spice tolerance preferences for AI prompt"""
    
    # Get spice tolerance from members
    tolerances = []
    for member in profile.get("members", []):
        tolerance = member.get("spice_tolerance")
        if tolerance:
            tolerances.append(tolerance)
    
    if not tolerances:
        return "No spice preference specified. Use medium spice level."
    
    # Map tolerance to AI guidance
    tolerance_map = {
        "none": "completely mild with no spices or heat",
        "mild": "gently seasoned with minimal heat",
        "medium": "moderately spiced with balanced flavors",
        "high": "well-spiced with noticeable heat",
        "very_high": "intensely spicy with bold heat"
    }
    
    # Use most restrictive tolerance (accommodate everyone)
    spice_levels = ["none", "mild", "medium", "high", "very_high"]
    primary_tolerance = min(
        tolerances, 
        key=lambda x: spice_levels.index(x) if x in spice_levels else 2
    )
    
    guidance = tolerance_map.get(primary_tolerance, "moderately spiced")
    
    return f"""
SPICE PREFERENCE (Soft Constraint):
The household prefers: {primary_tolerance.upper()} spice level
Interpretation: Create recipes that are {guidance}.

This is a PREFERENCE - you can suggest variations (e.g., "add more chili if desired")
but the base recipe should match their preference.
"""


def build_pantry_context(profile: Dict[str, Any]) -> str:
    """Build pantry availability context for AI prompt"""
    
    household = profile.get("household", {})
    basic_spices = household.get("basic_spices_available")
    
    if basic_spices == "yes":
        return """
PANTRY AVAILABILITY:
User has basic spices available (salt, pepper, garlic powder, onion powder, paprika, cumin, etc.)
You can assume these are on hand without listing them in shopping lists.
"""
    elif basic_spices == "some":
        return """
PANTRY AVAILABILITY:
User has SOME basic spices. Include common spices (salt, pepper, garlic) but list specialty spices 
in shopping list (cumin, paprika, herbs, etc.)
"""
    elif basic_spices == "no":
        return """
PANTRY AVAILABILITY:
User prefers simple cooking without many spices. Keep recipes simple with minimal seasoning.
If spices are needed, include ALL spices in shopping list (even salt and pepper).
"""
    else:
        return """
PANTRY AVAILABILITY:
Pantry status unknown. Assume moderate spice availability but include specialty items in shopping list.
Ask user about availability of specialty ingredients before suggesting.
"""


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def validate_recipe_safety(recipe: Dict[str, Any], profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Validate recipe against hard constraints before showing to user.
    
    Returns:
        (is_safe, violations) - True if safe, list of violations if not
    """
    violations = []
    
    # Get ingredients as lowercase text
    ingredients = recipe.get("ingredients", [])
    ingredients_text = " ".join(str(ing).lower() for ing in ingredients)
    
    # Check allergens in ingredients
    all_allergens = set()
    for member in profile.get("members", []):
        all_allergens.update(member.get("allergens", []))
    
    for allergen in all_allergens:
        allergen_lower = allergen.lower()
        if allergen_lower in ingredients_text:
            violations.append(f"⚠️ Contains allergen: {allergen}")
    
    # Check dietary restrictions
    restrictions = set()
    for member in profile.get("members", []):
        restrictions.update(member.get("dietary_restrictions", []))
    
    # Check vegetarian/vegan
    if "vegetarian" in restrictions or "vegan" in restrictions:
        meat_keywords = ["chicken", "beef", "pork", "fish", "shrimp", "meat", "lamb", "bacon", "sausage"]
        for meat in meat_keywords:
            if meat in ingredients_text:
                violations.append(f"⚠️ Contains meat ({meat}) for vegetarian household")
    
    if "vegan" in restrictions:
        animal_keywords = ["milk", "butter", "cheese", "egg", "honey", "cream", "yogurt", "ghee"]
        for animal in animal_keywords:
            if animal in ingredients_text:
                violations.append(f"⚠️ Contains animal product ({animal}) for vegan household")
    
    # Check religious restrictions
    for restriction in restrictions:
        restriction_key = restriction.lower().replace(" ", "_")
        if restriction_key in RELIGIOUS_DIETARY_MAPS:
            forbidden = RELIGIOUS_DIETARY_MAPS[restriction_key]["forbidden"]
            for forbidden_item in forbidden:
                if forbidden_item.lower() in ingredients_text:
                    violations.append(
                        f"⚠️ Contains {forbidden_item} - violates {restriction} dietary restriction"
                    )
    
    is_safe = len(violations) == 0
    return is_safe, violations


def validate_profile_completeness(profile: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Check if profile has minimum required data for AI generation.
    
    Returns:
        (is_complete, missing_fields)
    """
    missing = []
    
    # Safety-critical fields: members + explicit allergen declarations.
    # Household-level preferences (language, cuisine prefs, nutrition targets, etc.)
    # should not block safety gating by themselves.

    members = profile.get("members")
    if not isinstance(members, list) or len(members) == 0:
        missing.append("family members")
    
    # Allergens are REQUIRED to be explicitly declared (even if empty)
    # Require this for every member so we don't accidentally proceed when some
    # members have unknown allergen status.
    allergens_declared_for_all = True
    for member in members or []:
        if not isinstance(member, dict):
            continue
        if "allergens" not in member:
            allergens_declared_for_all = False
            break
        # Treat null/empty string as not explicitly declared
        if member.get("allergens") is None:
            allergens_declared_for_all = False
            break

    if (members and len(members) > 0) and not allergens_declared_for_all:
        missing.append("allergen declarations (required for safety)")
    
    is_complete = len(missing) == 0
    return is_complete, missing


# ============================================================================
# GOLDEN RULE ENFORCEMENT
# ============================================================================

class SAVOGoldenRule:
    """
    Enforce: If SAVO isn't sure, it asks. If it can't ask, it refuses.
    
    The single principle that defines SAVO's standard.
    """
    
    @staticmethod
    def check_before_generate(profile: Dict[str, Any], request: str = "") -> Dict[str, Any]:
        """
        Pre-generation safety gate.
        
        Returns dict with:
            - can_proceed: bool
            - action: "proceed" | "ask" | "refuse"
            - message: str (explanation)
            - alternatives: List[str] (optional)
        """
        
        # Check 1: Profile complete?
        is_complete, missing = validate_profile_completeness(profile)
        if not is_complete:
            return {
                "can_proceed": False,
                "action": "ask",
                "message": f"I need to know about {', '.join(missing)} first for safety.",
                "missing_fields": missing
            }
        
        # Check 2: Request conflicts with restrictions?
        if request:
            conflicts = SAVOGoldenRule._detect_conflicts(profile, request)
            if conflicts:
                return {
                    "can_proceed": False,
                    "action": "refuse",
                    "message": f"I can't make {request} because: {conflicts['reason']}",
                    "alternative": conflicts.get("alternative")
                }
        
        # All clear
        return {
            "can_proceed": True,
            "action": "proceed"
        }
    
    @staticmethod
    def _detect_conflicts(profile: Dict[str, Any], request: str) -> Dict[str, Any]:
        """Detect conflicts between user request and dietary restrictions"""
        request_lower = request.lower()
        
        # Get all restrictions
        all_allergens = set()
        all_restrictions = set()
        
        for member in profile.get("members", []):
            all_allergens.update(member.get("allergens", []))
            all_restrictions.update(member.get("dietary_restrictions", []))
        
        # Check allergen conflicts
        for allergen in all_allergens:
            allergen_lower = allergen.lower()
            # Check for allergen name or common derivatives
            allergen_keywords = [allergen_lower]
            
            # Add common variations
            if "peanut" in allergen_lower:
                allergen_keywords.extend(["peanut", "peanuts", "peanut butter"])
            elif "dairy" in allergen_lower:
                allergen_keywords.extend(["dairy", "milk", "cheese", "butter", "cream"])
            elif "shellfish" in allergen_lower:
                allergen_keywords.extend(["shellfish", "shrimp", "crab", "lobster"])
            
            for keyword in allergen_keywords:
                if keyword in request_lower:
                    return {
                        "reason": f"your household has a {allergen} allergy",
                        "alternative": f"I can suggest a {allergen}-free alternative"
                    }
        
        # Check religious/dietary conflicts
        conflict_map = {
            "pork": ["halal", "kosher", "no_pork"],
            "bacon": ["halal", "kosher", "no_pork"],
            "ham": ["halal", "kosher", "no_pork"],
            "beef": ["no_beef"],
            "meat": ["vegetarian", "vegan"],
            "chicken": ["vegetarian", "vegan"],
            "dairy": ["vegan", "dairy_free"],
            "cheese": ["vegan", "dairy_free"],
            "milk": ["vegan", "dairy_free"],
        }
        
        for ingredient, conflicting_restrictions in conflict_map.items():
            if ingredient in request_lower:
                for restriction in conflicting_restrictions:
                    if restriction in all_restrictions or restriction.replace("_", " ") in all_restrictions:
                        return {
                            "reason": f"your household follows {restriction} dietary restrictions",
                            "alternative": f"I can suggest a {restriction}-friendly alternative"
                        }
        
        return None


# ============================================================================
# COMPLETE PROMPT BUILDER
# ============================================================================

def build_complete_safety_context(profile: Dict[str, Any]) -> str:
    """
    Build complete safety and cultural context for AI prompt.
    Combines allergens, religious restrictions, cultural context, and preferences.
    """
    
    # Check golden rule first
    golden_check = SAVOGoldenRule.check_before_generate(profile)
    if not golden_check["can_proceed"]:
        logger.warning(f"Golden rule check failed: {golden_check['message']}")
        # Continue anyway but log warning
    
    # Build all constraint sections
    allergen_constraints = build_allergen_constraints(profile)
    religious_constraints = build_religious_constraints(profile)
    dietary_constraints = build_dietary_constraints(profile)
    cultural_context = build_cultural_context(profile)
    spice_preferences = build_spice_preferences(profile)
    pantry_context = build_pantry_context(profile)
    
    # Combine all contexts
    complete_context = f"""
{allergen_constraints}

{religious_constraints}

{dietary_constraints}

{cultural_context}

{spice_preferences}

{pantry_context}

GOLDEN RULE:
If you're unsure about ingredient availability or substitutions, ask the user.
If you cannot create a safe recipe that respects all constraints, explain why clearly.
"""
    
    return complete_context
