"""
Configuration models for app_configuration (E1)
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional, Dict, Any


class FamilyMember(BaseModel):
    """Individual family member with dietary needs and medical conditions"""
    member_id: str
    name: str
    age: int = Field(ge=0, le=120)
    age_category: Literal["child", "teen", "adult", "senior"] = Field(
        default="adult",
        description="Child: 0-12, Teen: 13-17, Adult: 18-64, Senior: 65+"
    )
    
    # Dietary Restrictions
    dietary_restrictions: List[str] = Field(
        default_factory=list,
        description="vegetarian, vegan, halal, kosher, gluten-free, dairy-free, etc."
    )
    allergens: List[str] = Field(
        default_factory=list,
        description="peanuts, tree nuts, shellfish, eggs, milk, soy, wheat, fish, etc."
    )
    
    # Medical Conditions affecting diet
    health_conditions: List[str] = Field(
        default_factory=list,
        description="diabetes, hypertension, high_cholesterol, kidney_disease, celiac, etc."
    )
    medical_dietary_needs: Dict[str, Any] = Field(
        default_factory=dict,
        description="Specific dietary requirements: {low_sodium: true, low_sugar: true, low_fat: true}"
    )
    
    # Preferences
    food_preferences: List[str] = Field(
        default_factory=list,
        description="Foods they like"
    )
    food_dislikes: List[str] = Field(
        default_factory=list,
        description="Foods they dislike or won't eat"
    )
    spice_tolerance: Literal["none", "mild", "medium", "hot", "very_hot"] = Field(
        default="medium",
        description="Spice level tolerance"
    )


class NutritionTargets(BaseModel):
    """Nutrition targets for the household"""
    daily_calories_per_person: Optional[int] = Field(None, ge=800, le=5000)
    max_sodium_mg: Optional[int] = Field(None, ge=0)
    min_protein_g: Optional[int] = Field(None, ge=0)
    max_sugar_g: Optional[int] = Field(None, ge=0)
    target_fiber_g: Optional[int] = Field(None, ge=0)


class HouseholdProfile(BaseModel):
    """Household profile with family members"""
    members: List[FamilyMember] = Field(default_factory=list)
    nutrition_targets: NutritionTargets = Field(default_factory=NutritionTargets)


class BehaviorSettings(BaseModel):
    """User behavior preferences for variety and ingredient usage"""
    avoid_repetition_days: int = Field(default=7, ge=1, le=30, description="Days to avoid repeating recipes/cuisines")
    rotate_cuisines: bool = Field(default=True, description="Rotate through different cuisines")
    rotate_methods: bool = Field(default=True, description="Rotate through different cooking methods")
    prefer_expiring_ingredients: bool = Field(default=True, description="Prioritize ingredients that are expiring soon")
    max_repeat_cuisine_per_week: int = Field(default=2, ge=1, le=7, description="Max times same cuisine in a week")
    use_leftovers_within_days: int = Field(default=2, ge=1, le=7, description="Schedule leftover reuse within X days")
    treat_meals_per_week: int = Field(default=1, ge=0, le=7, description="Special/treat meals per week")


class GlobalSettings(BaseModel):
    """Global application settings including cultural and regional preferences"""
    primary_language: str = Field(default="en", pattern="^[a-z]{2}(-[A-Z]{2})?$")
    measurement_system: Literal["metric", "imperial"] = Field(default="metric")
    timezone: str = Field(default="UTC", description="Preferred timezone for weekly planning")
    
    # Regional/Cultural Settings
    region: str = Field(
        default="US",
        description="Country/region code (US, IN, UK, etc.) - affects meal timing and culture"
    )
    culture: str = Field(
        default="western",
        description="Cultural food preference: western, indian, asian, middle_eastern, mediterranean, etc."
    )
    
    # Meal Timing and Types (regional variations)
    meal_times: Dict[str, str] = Field(
        default_factory=lambda: {
            "breakfast": "07:00-09:00",
            "lunch": "12:00-14:00",
            "dinner": "18:00-21:00"
        },
        description="Typical meal times in 24h format - used for time-based recommendations"
    )
    
    # Meal-Specific Preferences
    breakfast_preferences: Dict[str, Any] = Field(
        default_factory=lambda: {
            "style": "continental",  # continental, indian, american, etc.
            "light_or_heavy": "medium",
            "include_beverages": True
        },
        description="Breakfast-specific preferences"
    )
    lunch_preferences: Dict[str, Any] = Field(
        default_factory=lambda: {
            "style": "balanced",
            "portion_size": "medium",
            "include_rice_roti": True  # For Indian meals
        },
        description="Lunch-specific preferences"
    )
    dinner_preferences: Dict[str, Any] = Field(
        default_factory=lambda: {
            "style": "family_meal",
            "portion_size": "medium",
            "courses": 2  # Number of courses (starter + main, or main + dessert)
        },
        description="Dinner-specific preferences"
    )
    
    # Kitchen Equipment
    available_equipment: List[str] = Field(
        default_factory=lambda: ["stovetop", "oven", "microwave", "refrigerator"],
        description="Available kitchen equipment"
    )


class AppConfiguration(BaseModel):
    """Complete application configuration matching spec"""
    household_profile: HouseholdProfile = Field(default_factory=HouseholdProfile)
    global_settings: GlobalSettings = Field(default_factory=GlobalSettings)
    behavior_settings: BehaviorSettings = Field(default_factory=BehaviorSettings)

    @field_validator("household_profile")
    @classmethod
    def validate_household(cls, v: HouseholdProfile) -> HouseholdProfile:
        """Validate household has at least one member for proper planning"""
        # This is optional - can plan without members defined
        return v
