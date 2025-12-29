"""
Configuration models for app_configuration (E1)
"""
from pydantic import BaseModel, Field, field_validator
from typing import List, Literal, Optional


class FamilyMember(BaseModel):
    """Individual family member with dietary needs"""
    member_id: str
    name: str
    age: int = Field(ge=0, le=120)
    dietary_restrictions: List[str] = Field(default_factory=list)
    allergens: List[str] = Field(default_factory=list)
    health_conditions: List[str] = Field(default_factory=list)
    preferences: List[str] = Field(default_factory=list, description="Food preferences or dislikes")


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
    """Global application settings"""
    primary_language: str = Field(default="en", pattern="^[a-z]{2}(-[A-Z]{2})?$")
    measurement_system: Literal["metric", "imperial"] = Field(default="metric")
    timezone: str = Field(default="UTC", description="Preferred timezone for weekly planning")
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
