"""
Nutrition Intelligence Models
Nutrition scoring and health fit evaluation for recipe ranking
"""
from typing import Dict, List, Optional, Literal, Any
from pydantic import BaseModel, Field


class NutritionTargets(BaseModel):
    """Daily nutrition targets for a user/family"""
    calories: int = Field(default=2200, description="Daily calorie target")
    protein_g: int = Field(default=120, description="Daily protein in grams")
    carbs_g: int = Field(default=250, description="Daily carbs in grams")
    fat_g: int = Field(default=70, description="Daily fat in grams")
    fiber_g: Optional[int] = Field(default=30, description="Daily fiber in grams")
    sodium_mg: Optional[int] = Field(default=2300, description="Daily sodium in mg")
    sugar_g: Optional[int] = Field(default=50, description="Daily sugar in grams")


class MealLevelTargets(BaseModel):
    """Nutrition targets per meal type"""
    breakfast: Dict[str, float] = Field(
        default={"calories_pct": 25},
        description="Breakfast as % of daily"
    )
    lunch: Dict[str, float] = Field(
        default={"calories_pct": 35},
        description="Lunch as % of daily"
    )
    dinner: Dict[str, float] = Field(
        default={"calories_pct": 40},
        description="Dinner as % of daily"
    )


class NutritionFocus(BaseModel):
    """User's nutrition priorities"""
    focus_areas: List[Literal[
        "high_protein",
        "low_sugar",
        "low_sodium",
        "low_fat",
        "high_fiber",
        "balanced"
    ]] = Field(default=["balanced"])


class UserNutritionProfile(BaseModel):
    """Complete nutrition profile for a user/family"""
    daily_targets: NutritionTargets = Field(default_factory=NutritionTargets)
    meal_level_targets: MealLevelTargets = Field(default_factory=MealLevelTargets)
    allergens: List[str] = Field(
        default=[],
        description="Food allergens to avoid (e.g., peanuts, dairy)"
    )
    health_conditions: List[str] = Field(
        default=[],
        description="diabetes, hypertension, high_cholesterol, etc."
    )
    dietary_preferences: List[str] = Field(
        default=[],
        description="vegetarian, vegan, keto, etc."
    )
    nutrition_focus: List[str] = Field(
        default=["balanced"],
        description="high_protein, low_sugar, etc."
    )


class RecipeNutritionEstimate(BaseModel):
    """Estimated nutrition per serving"""
    calories: int = Field(description="Calories per serving")
    protein_g: float = Field(description="Protein in grams")
    carbs_g: float = Field(description="Carbs in grams")
    fat_g: float = Field(description="Fat in grams")
    fiber_g: Optional[float] = Field(default=0, description="Fiber in grams")
    sodium_mg: Optional[int] = Field(default=0, description="Sodium in mg")
    sugar_g: Optional[float] = Field(default=0, description="Sugar in grams")
    confidence_score: float = Field(
        default=0.8,
        description="Confidence in nutrition estimate (0-1)"
    )


class NutritionScoring(BaseModel):
    """Health fit scoring for a recipe"""
    health_fit_score: float = Field(
        ge=0, le=1,
        description="Overall health fit (0-1, higher is better)"
    )
    positive_flags: List[str] = Field(
        default=[],
        description="high_protein, high_fiber, low_sodium, etc."
    )
    warning_flags: List[str] = Field(
        default=[],
        description="high_sodium, high_sugar, high_fat, etc."
    )
    eligibility: Literal["recommended", "allowed", "avoid"] = Field(
        default="allowed",
        description="Recipe suitability for user"
    )
    explanation: str = Field(
        default="",
        description="Simple explanation of why this score"
    )


class NutritionEvaluationRequest(BaseModel):
    """Request to evaluate nutrition fit of a recipe"""
    recipe_id: Optional[str] = None
    servings: int = Field(ge=1, le=20)
    nutrition_estimate: RecipeNutritionEstimate
    nutrition_profile: UserNutritionProfile
    meal_type: Optional[Literal["breakfast", "lunch", "dinner", "snack"]] = None


class NutritionEvaluationResponse(BaseModel):
    """Response from nutrition evaluation"""
    per_serving: RecipeNutritionEstimate
    health_fit_score: float = Field(ge=0, le=1)
    warnings: List[str] = Field(default=[])
    positive_flags: List[str] = Field(default=[])
    eligibility: Literal["recommended", "allowed", "avoid"]
    explanation: str


class RecipeBadge(BaseModel):
    """Visual badge for recipe card"""
    icon: str = Field(description="Emoji or icon name")
    label: str = Field(description="Short label text")
    color: Literal["green", "yellow", "red", "blue"] = Field(default="green")
    tooltip: Optional[str] = Field(default=None, description="Expandable explanation")


def calculate_health_fit_score(
    nutrition: RecipeNutritionEstimate,
    profile: UserNutritionProfile,
    meal_type: Optional[str] = None
) -> NutritionScoring:
    """
    Calculate health fit score for a recipe based on user profile
    
    Scoring logic:
    - Start at 0.5 (neutral)
    - Add points for meeting nutrition focus (+0.1 each)
    - Subtract points for warnings (-0.15 each)
    - Bonus for health conditions compatibility (+0.2)
    """
    score = 0.5
    positive_flags = []
    warning_flags = []
    
    # Check protein goals
    if "high_protein" in profile.nutrition_focus and nutrition.protein_g >= 30:
        positive_flags.append("high_protein")
        score += 0.1
    
    # Check fiber
    if nutrition.fiber_g and nutrition.fiber_g >= 8:
        positive_flags.append("high_fiber")
        score += 0.1
    
    # Check sugar (especially for diabetes)
    if nutrition.sugar_g and nutrition.sugar_g > 15:
        warning_flags.append("high_sugar")
        if "diabetes" in profile.health_conditions:
            score -= 0.2
        else:
            score -= 0.1
    elif nutrition.sugar_g and nutrition.sugar_g < 8:
        positive_flags.append("low_sugar")
        if "diabetes" in profile.health_conditions:
            score += 0.2
    
    # Check sodium (hypertension)
    if nutrition.sodium_mg and nutrition.sodium_mg > 800:
        warning_flags.append("high_sodium")
        if "hypertension" in profile.health_conditions:
            score -= 0.2
        else:
            score -= 0.1
    elif nutrition.sodium_mg and nutrition.sodium_mg < 400:
        positive_flags.append("low_sodium")
        if "hypertension" in profile.health_conditions:
            score += 0.2
    
    # Check fat (cholesterol)
    if nutrition.fat_g > 25:
        warning_flags.append("high_fat")
        if "high_cholesterol" in profile.health_conditions:
            score -= 0.15
    elif nutrition.fat_g < 10:
        positive_flags.append("low_fat")
        if "high_cholesterol" in profile.health_conditions:
            score += 0.15
    
    # Clamp score between 0 and 1
    score = max(0.0, min(1.0, score))
    
    # Determine eligibility
    if score >= 0.75:
        eligibility = "recommended"
    elif score >= 0.5:
        eligibility = "allowed"
    else:
        eligibility = "avoid"
    
    # Generate explanation
    explanations = []
    if positive_flags:
        explanations.append(f"Good: {', '.join(positive_flags)}")
    if warning_flags:
        explanations.append(f"Note: {', '.join(warning_flags)}")
    if "diabetes" in profile.health_conditions and "low_sugar" in positive_flags:
        explanations.append("Diabetes-friendly")
    
    explanation = ". ".join(explanations) if explanations else "Balanced nutrition"
    
    return NutritionScoring(
        health_fit_score=score,
        positive_flags=positive_flags,
        warning_flags=warning_flags,
        eligibility=eligibility,
        explanation=explanation
    )


def generate_recipe_badges(
    nutrition_scoring: NutritionScoring,
    difficulty_level: int,
    time_minutes: int
) -> List[RecipeBadge]:
    """
    Generate up to 3 badges for recipe card
    Priority: Nutrition > Skill > Time
    """
    badges = []
    
    # Nutrition badge (highest priority)
    if nutrition_scoring.health_fit_score >= 0.8:
        badges.append(RecipeBadge(
            icon="🟢",
            label="Balanced",
            color="green",
            tooltip="Great nutritional fit for your profile"
        ))
    elif "high_protein" in nutrition_scoring.positive_flags:
        badges.append(RecipeBadge(
            icon="💪",
            label="High Protein",
            color="blue",
            tooltip=f"Protein: {nutrition_scoring.positive_flags}"
        ))
    
    # Skill badge
    if difficulty_level == 1:
        badges.append(RecipeBadge(
            icon="⭐",
            label="Easy",
            color="green",
            tooltip="Simple assembly, no complex techniques"
        ))
    elif difficulty_level == 2:
        badges.append(RecipeBadge(
            icon="⭐⭐",
            label="Medium",
            color="yellow",
            tooltip="Basic cooking skills required"
        ))
    
    # Time badge
    if time_minutes <= 20:
        badges.append(RecipeBadge(
            icon="⏱",
            label=f"{time_minutes} min",
            color="green",
            tooltip="Quick meal"
        ))
    elif time_minutes <= 40:
        badges.append(RecipeBadge(
            icon="⏱",
            label=f"{time_minutes} min",
            color="yellow",
            tooltip="Moderate prep time"
        ))
    
    # Return max 3 badges
    return badges[:3]
