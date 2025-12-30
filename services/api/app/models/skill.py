"""
Recipe Difficulty and Skill Progression Models
Confidence-based cooking with gradual skill advancement
"""
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime


class RecipeDifficulty(BaseModel):
    """Recipe difficulty metadata"""
    level: Literal[1, 2, 3, 4, 5] = Field(
        description="1=Assembly, 2=Basic, 3=Technique, 4=Multi-step, 5=Advanced"
    )
    level_name: str = Field(
        description="Human-readable difficulty name"
    )
    skills_required: List[str] = Field(
        default=[],
        description="pan_fry, knife_skills, tempering, etc."
    )
    techniques: List[str] = Field(
        default=[],
        description="Specific techniques: julienne, sauté, braise, etc."
    )
    estimated_time_minutes: int = Field(ge=5, le=240)
    active_time_minutes: int = Field(
        ge=5, le=180,
        description="Time actually cooking (vs waiting)"
    )
    
    @staticmethod
    def get_level_name(level: int) -> str:
        """Get human-readable name for difficulty level"""
        names = {
            1: "Assembly / No-Skill",
            2: "Basic Cooking",
            3: "Technique-Based",
            4: "Multi-Step",
            5: "Advanced"
        }
        return names.get(level, "Unknown")


class SkillLevel(BaseModel):
    """User's current skill level and confidence"""
    current_level: Literal[1, 2, 3, 4, 5] = Field(default=2)
    confidence_score: float = Field(
        ge=0, le=1, default=0.5,
        description="Confidence in current level (0-1)"
    )
    recipes_completed: int = Field(default=0, description="Total recipes completed")
    successful_meals: int = Field(default=0, description="Completed without help")
    skill_signals: Dict[str, Any] = Field(
        default={},
        description="Tracking signals: steps_skipped, timing_accuracy, etc."
    )


class SkillProgression(BaseModel):
    """Skill advancement tracking"""
    current_level: int = Field(ge=1, le=5)
    confidence_score: float = Field(ge=0, le=1)
    
    # Signals used for progression
    recipes_completed: int = Field(default=0)
    steps_skipped: int = Field(default=0)
    timing_adjustments: int = Field(default=0)
    user_edits: int = Field(default=0)
    repeat_success: bool = Field(default=False)
    
    # Progression rules
    ready_to_advance: bool = Field(
        default=False,
        description="User ready for next level"
    )
    advancement_reason: Optional[str] = Field(
        default=None,
        description="Why ready to advance"
    )
    
    @staticmethod
    def evaluate_progression(
        current_level: int,
        recipes_completed: int,
        successful_meals: int,
        steps_skipped: int,
        timing_adjustments: int
    ) -> tuple[bool, str]:
        """
        Evaluate if user is ready to advance to next level
        
        Rules:
        - Level 1→2: 3 successful meals without help
        - Level 2→3: 5 successful meals + good timing
        - Level 3→4: 8 successful meals + minimal edits
        - Level 4→5: 12 successful meals + consistent success
        """
        ready = False
        reason = ""
        
        success_rate = successful_meals / max(recipes_completed, 1)
        
        if current_level == 1:
            if successful_meals >= 3 and success_rate >= 0.8:
                ready = True
                reason = "You've mastered simple assembly. Ready for basic cooking?"
        
        elif current_level == 2:
            if successful_meals >= 5 and timing_adjustments <= 2:
                ready = True
                reason = "Your timing is consistent. Want to try technique-based recipes?"
        
        elif current_level == 3:
            if successful_meals >= 8 and steps_skipped <= 3:
                ready = True
                reason = "You follow recipes confidently. Ready for multi-step dishes?"
        
        elif current_level == 4:
            if successful_meals >= 12 and success_rate >= 0.85:
                ready = True
                reason = "You're cooking like a pro! Try advanced techniques?"
        
        return ready, reason


class RecipeSkillFit(BaseModel):
    """Evaluation of recipe difficulty vs user skill"""
    user_level: int = Field(ge=1, le=5)
    recipe_level: int = Field(ge=1, le=5)
    
    fit_category: Literal["perfect", "stretch", "too_easy", "too_hard"] = Field(
        description="How recipe matches user skill"
    )
    
    recommendation: str = Field(
        description="Simple explanation for user"
    )
    
    @staticmethod
    def evaluate_fit(
        user_level: int,
        user_confidence: float,
        recipe_level: int
    ) -> "RecipeSkillFit":
        """Evaluate if recipe difficulty matches user skill"""
        
        diff = recipe_level - user_level
        
        # Perfect match (same level or one above with high confidence)
        if diff == 0:
            fit = "perfect"
            recommendation = "Matches your cooking level"
        elif diff == 1 and user_confidence >= 0.75:
            fit = "stretch"
            recommendation = "Slightly challenging, but you can do it"
        elif diff >= 2:
            fit = "too_hard"
            recommendation = "This might be frustrating. Start with easier versions?"
        else:  # diff < 0
            fit = "too_easy"
            recommendation = "This is below your skill level"
        
        return RecipeSkillFit(
            user_level=user_level,
            recipe_level=recipe_level,
            fit_category=fit,
            recommendation=recommendation
        )


class SkillNudge(BaseModel):
    """Optional skill advancement suggestion"""
    show_nudge: bool = Field(default=False)
    message: str = Field(
        default="",
        description="Encouraging message (never 'level up' or 'advanced')"
    )
    alternative_recipe_id: Optional[str] = Field(
        default=None,
        description="Slightly harder recipe option"
    )
    buttons: List[str] = Field(
        default=["Try it", "Maybe later"],
        description="Non-pressuring action buttons"
    )


# Difficulty level examples for reference
DIFFICULTY_EXAMPLES = {
    1: [
        "Salad bowls",
        "Sandwich wraps",
        "Yogurt parfait",
        "Toast with toppings"
    ],
    2: [
        "Scrambled eggs",
        "Stir-fry",
        "Simple pasta",
        "Basic curry"
    ],
    3: [
        "Tempering (tadka)",
        "Pan-seared fish",
        "Risotto",
        "Homemade pizza"
    ],
    4: [
        "Layered lasagna",
        "Biryani",
        "Soufflé",
        "Ramen from scratch"
    ],
    5: [
        "Sourdough bread",
        "French pastries",
        "Fermented foods",
        "Multi-course tasting menu"
    ]
}
