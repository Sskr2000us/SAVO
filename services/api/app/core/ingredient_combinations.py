"""
SAVO — Ingredient Combination Intelligence

Handles multi-ingredient recipe generation with:
- Ingredient synergy detection (which ingredients work well together)
- Cultural pairing logic (traditional combinations across cuisines)
- Balanced recipe composition (protein + veg + starch)
- Nutritional completeness
- Safety constraint integration

Author: SAVO Team
Date: January 2, 2026
"""

from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class IngredientCategory(Enum):
    """Ingredient functional categories"""
    PROTEIN = "protein"
    VEGETABLE = "vegetable"
    STARCH = "starch"
    DAIRY = "dairy"
    SPICE = "spice"
    FAT = "fat"
    ACID = "acid"
    HERB = "herb"
    SWEETENER = "sweetener"
    GRAIN = "grain"
    LEGUME = "legume"


@dataclass
class IngredientProfile:
    """Rich profile of an ingredient"""
    name: str
    category: IngredientCategory
    flavor_profile: List[str]  # ["savory", "umami", "sweet", etc.]
    cuisines: List[str]  # Cuisines where commonly used
    pairs_well_with: List[str]  # Common pairings
    allergen_tags: List[str]  # Allergen warnings
    religious_tags: List[str]  # Religious considerations


# Global ingredient knowledge base
INGREDIENT_DATABASE = {
    # Proteins
    "chicken": IngredientProfile(
        name="chicken",
        category=IngredientCategory.PROTEIN,
        flavor_profile=["savory", "mild", "umami"],
        cuisines=["italian", "indian", "chinese", "mexican", "french"],
        pairs_well_with=["garlic", "lemon", "rosemary", "ginger", "soy_sauce", "tomato"],
        allergen_tags=[],
        religious_tags=["halal_check", "kosher_check"]
    ),
    "paneer": IngredientProfile(
        name="paneer",
        category=IngredientCategory.PROTEIN,
        flavor_profile=["mild", "creamy"],
        cuisines=["indian", "south_asian"],
        pairs_well_with=["spinach", "tomato", "peas", "cumin", "turmeric"],
        allergen_tags=["dairy"],
        religious_tags=["vegetarian"]
    ),
    "black_channa": IngredientProfile(
        name="black_channa",
        category=IngredientCategory.LEGUME,
        flavor_profile=["earthy", "nutty"],
        cuisines=["indian", "middle_eastern", "south_indian"],
        pairs_well_with=["tamarind", "curry_leaves", "coconut", "tomato", "onion"],
        allergen_tags=[],
        religious_tags=["vegan", "vegetarian"]
    ),
    
    # Vegetables
    "tomato": IngredientProfile(
        name="tomato",
        category=IngredientCategory.VEGETABLE,
        flavor_profile=["savory", "sweet", "acidic"],
        cuisines=["italian", "indian", "mexican", "mediterranean"],
        pairs_well_with=["basil", "garlic", "onion", "mozzarella", "olive_oil"],
        allergen_tags=[],
        religious_tags=[]
    ),
    "onion": IngredientProfile(
        name="onion",
        category=IngredientCategory.VEGETABLE,
        flavor_profile=["savory", "sweet", "pungent"],
        cuisines=["italian", "indian", "french", "chinese", "mexican"],
        pairs_well_with=["garlic", "tomato", "potato", "bell_pepper"],
        allergen_tags=[],
        religious_tags=["jain_forbidden"]
    ),
    "eggplant": IngredientProfile(
        name="eggplant",
        category=IngredientCategory.VEGETABLE,
        flavor_profile=["mild", "earthy", "slightly_bitter"],
        cuisines=["italian", "indian", "middle_eastern", "chinese", "japanese"],
        pairs_well_with=["tomato", "garlic", "tahini", "miso", "tamarind"],
        allergen_tags=[],
        religious_tags=["vegan", "vegetarian"]
    ),
    "spinach": IngredientProfile(
        name="spinach",
        category=IngredientCategory.VEGETABLE,
        flavor_profile=["mild", "earthy"],
        cuisines=["indian", "italian", "mediterranean", "french"],
        pairs_well_with=["paneer", "garlic", "lemon", "ricotta", "chickpeas"],
        allergen_tags=[],
        religious_tags=["vegan", "vegetarian"]
    ),
    
    # Starches/Grains
    "rice": IngredientProfile(
        name="rice",
        category=IngredientCategory.GRAIN,
        flavor_profile=["neutral", "mild"],
        cuisines=["indian", "chinese", "japanese", "thai", "mexican"],
        pairs_well_with=["soy_sauce", "coconut", "spices", "vegetables"],
        allergen_tags=[],
        religious_tags=["vegan", "vegetarian"]
    ),
    "potato": IngredientProfile(
        name="potato",
        category=IngredientCategory.STARCH,
        flavor_profile=["neutral", "mild", "earthy"],
        cuisines=["indian", "european", "american", "french"],
        pairs_well_with=["butter", "cheese", "herbs", "curry", "garlic"],
        allergen_tags=[],
        religious_tags=["jain_forbidden"]  # Root vegetable
    ),
    
    # Dairy
    "mozzarella": IngredientProfile(
        name="mozzarella",
        category=IngredientCategory.DAIRY,
        flavor_profile=["mild", "creamy", "milky"],
        cuisines=["italian", "mediterranean"],
        pairs_well_with=["tomato", "basil", "olive_oil", "pizza_dough"],
        allergen_tags=["dairy"],
        religious_tags=["vegetarian", "not_vegan"]
    ),
    
    # Acids/Flavor enhancers
    "tamarind": IngredientProfile(
        name="tamarind",
        category=IngredientCategory.ACID,
        flavor_profile=["sour", "tangy", "slightly_sweet"],
        cuisines=["indian", "thai", "filipino", "south_indian"],
        pairs_well_with=["black_channa", "eggplant", "jaggery", "curry_leaves"],
        allergen_tags=[],
        religious_tags=["vegan", "vegetarian"]
    ),
    "lemon": IngredientProfile(
        name="lemon",
        category=IngredientCategory.ACID,
        flavor_profile=["sour", "bright", "citrus"],
        cuisines=["mediterranean", "italian", "middle_eastern", "indian"],
        pairs_well_with=["chicken", "fish", "herbs", "garlic"],
        allergen_tags=[],
        religious_tags=["vegan", "vegetarian"]
    ),
}


class IngredientCombinationEngine:
    """
    Engine for analyzing ingredient combinations and generating
    intelligent multi-ingredient recipes.
    """
    
    def __init__(self):
        self.ingredient_db = INGREDIENT_DATABASE
    
    def get_ingredient_profile(self, ingredient: str) -> Optional[IngredientProfile]:
        """Get profile for ingredient (normalize name)"""
        normalized = ingredient.lower().strip().replace(" ", "_")
        return self.ingredient_db.get(normalized)
    
    def analyze_combination(
        self,
        ingredients: List[str],
        profile: dict
    ) -> Dict:
        """
        Analyze a combination of ingredients for recipe potential.
        
        Returns:
            {
                "is_viable": bool,
                "balance_score": float,  # 0-1, how balanced the combination is
                "missing_categories": list,  # e.g., ["protein"] if no protein
                "suggested_additions": list,  # Ingredients to complete the recipe
                "cuisine_matches": list,  # Cuisines that use these ingredients
                "safety_issues": list,  # Any allergen/religious conflicts
                "synergy_score": float,  # 0-1, how well ingredients work together
                "recipe_potential": str  # "high", "medium", "low"
            }
        """
        
        # Get profiles for all ingredients
        ingredient_profiles = []
        unknown_ingredients = []
        
        for ing in ingredients:
            prof = self.get_ingredient_profile(ing)
            if prof:
                ingredient_profiles.append(prof)
            else:
                unknown_ingredients.append(ing)
        
        if not ingredient_profiles:
            return {
                "is_viable": False,
                "reason": "No recognized ingredients",
                "unknown_ingredients": unknown_ingredients
            }
        
        # Analyze balance
        categories_present = {prof.category for prof in ingredient_profiles}
        balance_score = self._calculate_balance_score(categories_present)
        missing_categories = self._identify_missing_categories(categories_present)
        
        # Analyze synergy (do ingredients pair well?)
        synergy_score = self._calculate_synergy_score(ingredient_profiles)
        
        # Find cuisine matches
        cuisine_matches = self._find_cuisine_matches(ingredient_profiles)
        
        # Check safety
        safety_issues = self._check_safety(ingredient_profiles, profile)
        
        # Suggest additions
        suggested_additions = self._suggest_additions(
            ingredient_profiles,
            missing_categories,
            cuisine_matches
        )
        
        # Overall viability
        is_viable = (
            balance_score > 0.4 and
            synergy_score > 0.3 and
            len(safety_issues) == 0
        )
        
        # Recipe potential
        if balance_score > 0.8 and synergy_score > 0.7:
            recipe_potential = "high"
        elif balance_score > 0.5 and synergy_score > 0.5:
            recipe_potential = "medium"
        else:
            recipe_potential = "low"
        
        return {
            "is_viable": is_viable,
            "balance_score": balance_score,
            "synergy_score": synergy_score,
            "missing_categories": [cat.value for cat in missing_categories],
            "suggested_additions": suggested_additions,
            "cuisine_matches": cuisine_matches,
            "safety_issues": safety_issues,
            "recipe_potential": recipe_potential,
            "unknown_ingredients": unknown_ingredients
        }
    
    def _calculate_balance_score(self, categories: Set[IngredientCategory]) -> float:
        """
        Calculate how balanced the ingredient combination is.
        Ideal: protein + vegetable + starch/grain = 1.0
        """
        
        score = 0.0
        
        # Protein presence (0.35)
        if IngredientCategory.PROTEIN in categories or IngredientCategory.LEGUME in categories:
            score += 0.35
        
        # Vegetable presence (0.35)
        if IngredientCategory.VEGETABLE in categories:
            score += 0.35
        
        # Starch/grain presence (0.20)
        if IngredientCategory.STARCH in categories or IngredientCategory.GRAIN in categories:
            score += 0.20
        
        # Flavor enhancers (0.10)
        if any(cat in categories for cat in [
            IngredientCategory.SPICE,
            IngredientCategory.HERB,
            IngredientCategory.ACID
        ]):
            score += 0.10
        
        return min(score, 1.0)
    
    def _identify_missing_categories(
        self,
        categories: Set[IngredientCategory]
    ) -> List[IngredientCategory]:
        """Identify missing ingredient categories for a complete recipe"""
        
        missing = []
        
        # Check core categories
        if not (IngredientCategory.PROTEIN in categories or 
                IngredientCategory.LEGUME in categories):
            missing.append(IngredientCategory.PROTEIN)
        
        if IngredientCategory.VEGETABLE not in categories:
            missing.append(IngredientCategory.VEGETABLE)
        
        if not (IngredientCategory.STARCH in categories or 
                IngredientCategory.GRAIN in categories):
            missing.append(IngredientCategory.GRAIN)
        
        return missing
    
    def _calculate_synergy_score(self, profiles: List[IngredientProfile]) -> float:
        """
        Calculate how well ingredients work together.
        Based on traditional pairings.
        """
        
        if len(profiles) < 2:
            return 0.5  # Single ingredient = neutral
        
        total_pairs = 0
        good_pairs = 0
        
        for i, prof1 in enumerate(profiles):
            for prof2 in profiles[i+1:]:
                total_pairs += 1
                
                # Check if prof2 is in prof1's pairing list
                if prof2.name in prof1.pairs_well_with or prof1.name in prof2.pairs_well_with:
                    good_pairs += 1
                
                # Check if they share cuisine
                shared_cuisines = set(prof1.cuisines) & set(prof2.cuisines)
                if shared_cuisines:
                    good_pairs += 0.5  # Partial credit for same cuisine
        
        if total_pairs == 0:
            return 0.5
        
        return min(good_pairs / total_pairs, 1.0)
    
    def _find_cuisine_matches(self, profiles: List[IngredientProfile]) -> List[str]:
        """
        Find cuisines where ALL ingredients are commonly used.
        """
        
        if not profiles:
            return []
        
        # Start with first ingredient's cuisines
        common_cuisines = set(profiles[0].cuisines)
        
        # Intersect with other ingredients
        for prof in profiles[1:]:
            common_cuisines &= set(prof.cuisines)
        
        return sorted(list(common_cuisines))
    
    def _check_safety(
        self,
        profiles: List[IngredientProfile],
        user_profile: dict
    ) -> List[str]:
        """
        Check for allergen and religious conflicts.
        """
        
        issues = []
        
        # Get user allergens
        user_allergens = set()
        for member in user_profile.get("members", []):
            user_allergens.update(member.get("allergens", []))
        
        # Get user dietary restrictions
        dietary_restrictions = set()
        for member in user_profile.get("members", []):
            dietary_restrictions.update(member.get("dietary_restrictions", []))
        
        # Check each ingredient
        for prof in profiles:
            # Check allergens
            for allergen in prof.allergen_tags:
                if allergen in user_allergens:
                    issues.append(
                        f"{prof.name} contains {allergen} (declared allergen)"
                    )
            
            # Check religious restrictions
            if "jain" in dietary_restrictions or "no_onion" in dietary_restrictions:
                if "jain_forbidden" in prof.religious_tags:
                    issues.append(
                        f"{prof.name} not allowed for Jain dietary restrictions"
                    )
            
            if "vegan" in dietary_restrictions:
                if "not_vegan" in prof.religious_tags or "dairy" in prof.allergen_tags:
                    issues.append(
                        f"{prof.name} not suitable for vegan diet"
                    )
        
        return issues
    
    def _suggest_additions(
        self,
        profiles: List[IngredientProfile],
        missing_categories: List[IngredientCategory],
        cuisine_matches: List[str]
    ) -> List[str]:
        """
        Suggest ingredients to add for a complete recipe.
        """
        
        suggestions = []
        
        # Get primary cuisine if available
        primary_cuisine = cuisine_matches[0] if cuisine_matches else "general"
        
        # Suggest for missing categories
        for category in missing_categories:
            if category == IngredientCategory.PROTEIN:
                if "indian" in primary_cuisine:
                    suggestions.extend(["chicken", "paneer", "chickpeas"])
                else:
                    suggestions.extend(["chicken", "tofu", "eggs"])
            
            elif category == IngredientCategory.VEGETABLE:
                if "indian" in primary_cuisine:
                    suggestions.extend(["spinach", "peas", "bell_pepper"])
                else:
                    suggestions.extend(["broccoli", "carrots", "bell_pepper"])
            
            elif category == IngredientCategory.GRAIN:
                if "indian" in primary_cuisine:
                    suggestions.extend(["rice", "naan", "roti"])
                elif "italian" in primary_cuisine:
                    suggestions.extend(["pasta", "rice", "bread"])
                else:
                    suggestions.extend(["rice", "quinoa", "bread"])
        
        return suggestions[:5]  # Limit to top 5
    
    def generate_combination_prompt(
        self,
        ingredients: List[str],
        profile: dict,
        analysis: Dict
    ) -> str:
        """
        Generate AI prompt for multi-ingredient recipe.
        Integrates with Section 11 safety constraints + cultural intelligence.
        """
        
        from .safety_constraints import build_complete_safety_context
        from .cultural_intelligence import build_cultural_intelligence_prompt
        
        # Get safety context from Section 11
        safety_context = build_complete_safety_context(profile)
        
        # Get cultural intelligence context
        cultural_intelligence = build_cultural_intelligence_prompt(
            ingredients,
            cuisine=analysis.get("cuisine_matches", [None])[0]
        )
        
        # Build combination-specific context
        combination_context = f"""
INGREDIENT COMBINATION ANALYSIS:
- Available ingredients: {', '.join(ingredients)}
- Balance score: {analysis['balance_score']:.2f} (0=poor, 1=perfect)
- Synergy score: {analysis['synergy_score']:.2f} (ingredients work well together)
- Recipe potential: {analysis['recipe_potential'].upper()}
- Cuisine matches: {', '.join(analysis['cuisine_matches']) if analysis['cuisine_matches'] else 'Multiple options'}
- Missing categories: {', '.join(analysis['missing_categories']) if analysis['missing_categories'] else 'None - well balanced'}
- Suggested additions: {', '.join(analysis['suggested_additions'][:3]) if analysis['suggested_additions'] else 'None needed'}
"""
        
        if analysis['unknown_ingredients']:
            combination_context += f"\nNote: Some ingredients not in database: {', '.join(analysis['unknown_ingredients'])}\n"
        
        prompt = f"""
You are SAVO, an AI cooking assistant generating a recipe using multiple ingredients.

{safety_context}

{combination_context}

{cultural_intelligence}

INSTRUCTIONS:
1. Create a recipe that uses ALL provided ingredients: {', '.join(ingredients)}
2. STRICTLY respect all allergen and dietary constraints (see above)
3. If suggested additions would improve the recipe, include them in the recipe and add to shopping list
4. Choose a cuisine that matches the ingredient combination naturally
5. Ensure the recipe is balanced and nutritious
6. EXPLAIN WHY this combination works culturally, nutritionally, and traditionally
7. Format response as JSON with: title, cuisine, description, ingredients (with quantities), 
   steps (numbered), prep_time, cook_time, servings, difficulty, nutritional_notes, 
   cultural_context (object with: why_this_combo, nutritional_benefits, cultural_significance, 
   traditional_wisdom, flavor_science)

CULTURAL CONTEXT REQUIREMENTS:
- Explain why these ingredients are traditionally paired in this cuisine
- Describe nutritional synergies (e.g., "tamarind aids digestion of heavy chickpeas")
- Include texture and flavor balance reasoning
- Mention economic/seasonal/festive significance if relevant
- Use authentic cultural knowledge, not assumptions

Generate the recipe with full cultural reasoning now:
"""
        
        return prompt


# Convenience functions for API usage
def analyze_ingredients(ingredients: List[str], profile: dict) -> Dict:
    """
    Analyze ingredient combination for recipe viability.
    
    Args:
        ingredients: List of ingredient names
        profile: User profile with allergens/dietary restrictions
    
    Returns:
        Analysis dict with viability, scores, suggestions
    """
    engine = IngredientCombinationEngine()
    return engine.analyze_combination(ingredients, profile)


def generate_combination_recipe_prompt(
    ingredients: List[str],
    profile: dict
) -> Tuple[str, Dict]:
    """
    Generate AI prompt for multi-ingredient recipe.
    
    Args:
        ingredients: List of ingredient names
        profile: User profile
    
    Returns:
        (prompt_string, analysis_dict)
    """
    engine = IngredientCombinationEngine()
    analysis = engine.analyze_combination(ingredients, profile)
    
    if not analysis['is_viable']:
        return None, analysis
    
    prompt = engine.generate_combination_prompt(ingredients, profile, analysis)
    return prompt, analysis
