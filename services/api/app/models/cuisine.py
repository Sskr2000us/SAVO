"""
Cuisine Ranking and Multi-Cuisine Decision Models
Global recipe support with intelligent cuisine selection
"""
from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field


class CuisineMetadata(BaseModel):
    """Metadata defining a cuisine's characteristics"""
    name: str = Field(description="Cuisine name: Italian, Indian, Thai, etc.")
    structure: List[str] = Field(
        description="Typical meal structure: soup, curry, rice, etc."
    )
    techniques: List[str] = Field(
        description="Common techniques: stir_fry, simmer, bake, etc."
    )
    flavor_profile: List[str] = Field(
        description="Flavor characteristics: spicy, sour, sweet, umami, etc."
    )
    staple_ingredients: List[str] = Field(
        description="Core ingredients: tomato, rice, noodles, etc."
    )
    typical_spice_level: Literal["none", "mild", "medium", "hot", "very_hot"] = Field(
        default="medium"
    )
    typical_difficulty: Literal[1, 2, 3, 4, 5] = Field(
        default=2,
        description="Average difficulty level for this cuisine"
    )


class CuisineScore(BaseModel):
    """Score for a candidate cuisine"""
    cuisine: str
    score: float = Field(ge=0, le=1, description="Overall fit score")
    reason: str = Field(description="Simple explanation of score")
    
    # Score breakdown
    ingredient_match: float = Field(ge=0, le=1)
    user_preference: float = Field(ge=0, le=1)
    recent_rotation_penalty: float = Field(ge=0, le=1)
    skill_fit: float = Field(ge=0, le=1)
    nutrition_fit: float = Field(ge=0, le=1)


class CuisineRankingRequest(BaseModel):
    """Request to rank cuisines for a meal"""
    available_ingredients: List[str]
    user_preferences: List[str] = Field(
        default=[],
        description="Preferred cuisines"
    )
    recent_cuisines: List[str] = Field(
        default=[],
        description="Cuisines used in last 7 days"
    )
    user_skill_level: int = Field(ge=1, le=5, default=2)
    nutrition_focus: List[str] = Field(default=[])
    health_conditions: List[str] = Field(default=[])


class CuisineRankingResponse(BaseModel):
    """Ranked list of cuisines"""
    candidate_cuisines: List[str]
    scores: List[CuisineScore]
    selected_cuisine: str
    explanation: str = Field(description="Why this cuisine was selected")


class MultiCuisineRules(BaseModel):
    """Rules for mixing cuisines in one meal"""
    enabled: bool = Field(default=True)
    max_cuisines_per_meal: int = Field(ge=1, le=3, default=2)
    
    allowed_modes: List[Literal["different_courses", "shared_base_ingredient"]] = Field(
        default=["different_courses", "shared_base_ingredient"]
    )
    
    # Compatibility rules
    avoid_conflicting_spice_profiles: bool = Field(default=True)
    reuse_prep_steps: bool = Field(
        default=True,
        description="Prefer cuisines that share prep techniques"
    )
    balance_effort_across_courses: bool = Field(
        default=True,
        description="Don't make all courses complex"
    )


class MultiCuisineStrategy(BaseModel):
    """Strategy for multi-cuisine meal"""
    mode: Literal["single_cuisine", "mixed_cuisine"] = Field(default="single_cuisine")
    
    selected_cuisines: List[str] = Field(
        description="Cuisines used in this meal"
    )
    
    course_assignments: Dict[str, str] = Field(
        description="Which cuisine for which course: {'starter': 'Mediterranean', 'main': 'Indian'}"
    )
    
    compatibility_check: Dict[str, Any] = Field(
        default={},
        description="Validation of cuisine mix"
    )
    
    explanation: str = Field(
        description="Simple explanation of multi-cuisine choice"
    )


# Cuisine database (simplified for MVP)
CUISINE_DATABASE: Dict[str, CuisineMetadata] = {
    "Italian": CuisineMetadata(
        name="Italian",
        structure=["antipasto", "primo", "secondo", "contorno"],
        techniques=["sauté", "simmer", "bake", "boil"],
        flavor_profile=["savory", "umami", "herbaceous"],
        staple_ingredients=["tomato", "pasta", "cheese", "olive_oil", "garlic"],
        typical_spice_level="mild",
        typical_difficulty=2
    ),
    "Indian": CuisineMetadata(
        name="Indian",
        structure=["appetizer", "curry", "rice", "roti", "raita"],
        techniques=["tempering", "simmer", "fry", "roast"],
        flavor_profile=["spicy", "aromatic", "complex"],
        staple_ingredients=["rice", "onion", "tomato", "spices", "lentils"],
        typical_spice_level="hot",
        typical_difficulty=3
    ),
    "Mexican": CuisineMetadata(
        name="Mexican",
        structure=["appetizer", "main", "salsa", "beans"],
        techniques=["grill", "simmer", "fry"],
        flavor_profile=["spicy", "tangy", "savory"],
        staple_ingredients=["corn", "beans", "tomato", "chili", "lime"],
        typical_spice_level="hot",
        typical_difficulty=2
    ),
    "Mediterranean": CuisineMetadata(
        name="Mediterranean",
        structure=["mezze", "main", "salad"],
        techniques=["grill", "roast", "raw"],
        flavor_profile=["fresh", "herbaceous", "citrus"],
        staple_ingredients=["olive_oil", "lemon", "herbs", "vegetables", "yogurt"],
        typical_spice_level="mild",
        typical_difficulty=1
    ),
    "Thai": CuisineMetadata(
        name="Thai",
        structure=["soup", "curry", "stir_fry", "rice"],
        techniques=["stir_fry", "simmer", "steam"],
        flavor_profile=["spicy", "sour", "sweet", "salty"],
        staple_ingredients=["rice", "coconut", "lemongrass", "chili", "fish_sauce"],
        typical_spice_level="hot",
        typical_difficulty=3
    ),
    "Chinese": CuisineMetadata(
        name="Chinese",
        structure=["soup", "stir_fry", "rice", "noodles"],
        techniques=["stir_fry", "steam", "braise"],
        flavor_profile=["umami", "savory", "balanced"],
        staple_ingredients=["rice", "soy_sauce", "ginger", "garlic", "vegetables"],
        typical_spice_level="mild",
        typical_difficulty=2
    ),
    "Japanese": CuisineMetadata(
        name="Japanese",
        structure=["miso", "main", "rice", "pickles"],
        techniques=["steam", "simmer", "raw", "grill"],
        flavor_profile=["umami", "subtle", "clean"],
        staple_ingredients=["rice", "soy_sauce", "miso", "seaweed", "fish"],
        typical_spice_level="none",
        typical_difficulty=3
    )
}


def rank_cuisines(
    available_ingredients: List[str],
    user_preferences: List[str],
    recent_cuisines: List[str],
    skill_level: int,
    nutrition_focus: List[str]
) -> List[CuisineScore]:
    """
    Rank cuisines based on multiple factors
    
    Scoring weights:
    - ingredient_match: 40%
    - user_preference: 20%
    - rotation_penalty: 15%
    - skill_fit: 15%
    - nutrition_fit: 10%
    """
    scores = []
    
    for cuisine_name, metadata in CUISINE_DATABASE.items():
        # Ingredient match score
        ingredient_matches = sum(
            1 for ing in available_ingredients
            if ing.lower() in [s.lower() for s in metadata.staple_ingredients]
        )
        ingredient_score = min(1.0, ingredient_matches / max(len(metadata.staple_ingredients) * 0.6, 1))
        
        # User preference score
        preference_score = 1.0 if cuisine_name in user_preferences else 0.5
        
        # Rotation penalty (avoid recent cuisines)
        rotation_penalty = 0.7 if cuisine_name in recent_cuisines else 1.0
        
        # Skill fit score
        skill_diff = abs(metadata.typical_difficulty - skill_level)
        skill_score = max(0.3, 1.0 - (skill_diff * 0.2))
        
        # Nutrition fit (simplified)
        nutrition_score = 0.8  # Default neutral
        if "low_fat" in nutrition_focus and cuisine_name == "Mediterranean":
            nutrition_score = 1.0
        elif "high_protein" in nutrition_focus and cuisine_name in ["Indian", "Mexican"]:
            nutrition_score = 0.9
        
        # Weighted total score
        total_score = (
            ingredient_score * 0.4 +
            preference_score * 0.2 +
            rotation_penalty * 0.15 +
            skill_score * 0.15 +
            nutrition_score * 0.1
        )
        
        # Generate reason
        reasons = []
        if ingredient_score >= 0.7:
            reasons.append("strong ingredient match")
        if cuisine_name in user_preferences:
            reasons.append("your favorite")
        if skill_diff == 0:
            reasons.append("matches your skill")
        
        reason = " and ".join(reasons) if reasons else "good fit"
        
        scores.append(CuisineScore(
            cuisine=cuisine_name,
            score=total_score,
            reason=reason.capitalize(),
            ingredient_match=ingredient_score,
            user_preference=preference_score,
            recent_rotation_penalty=rotation_penalty,
            skill_fit=skill_score,
            nutrition_fit=nutrition_score
        ))
    
    # Sort by score descending
    scores.sort(key=lambda x: x.score, reverse=True)
    return scores


def evaluate_multi_cuisine_compatibility(
    cuisine1: str,
    cuisine2: str,
    rules: MultiCuisineRules
) -> tuple[bool, str]:
    """
    Check if two cuisines can be mixed in one meal
    
    Returns: (compatible, reason)
    """
    meta1 = CUISINE_DATABASE.get(cuisine1)
    meta2 = CUISINE_DATABASE.get(cuisine2)
    
    if not meta1 or not meta2:
        return False, "Cuisine not found"
    
    # Check spice profile conflict
    if rules.avoid_conflicting_spice_profiles:
        spice_levels = ["none", "mild", "medium", "hot", "very_hot"]
        diff = abs(
            spice_levels.index(meta1.typical_spice_level) -
            spice_levels.index(meta2.typical_spice_level)
        )
        if diff >= 3:
            return False, "Spice levels too different"
    
    # Check technique overlap (for effort reuse)
    if rules.reuse_prep_steps:
        shared_techniques = set(meta1.techniques) & set(meta2.techniques)
        if not shared_techniques:
            return False, "No shared cooking techniques"
    
    # Check effort balance
    if rules.balance_effort_across_courses:
        avg_difficulty = (meta1.typical_difficulty + meta2.typical_difficulty) / 2
        if avg_difficulty >= 4:
            return False, "Combined effort too high"
    
    return True, "Compatible cuisines"
