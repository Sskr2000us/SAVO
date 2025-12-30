"""
Planning models for daily/party/weekly planning (E4)
"""
from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Literal, Optional, Any, Dict
from datetime import date


class AgeGroupCounts(BaseModel):
    """Explicit age group distribution for party planning"""
    child_0_12: int = Field(default=0, ge=0, description="Children aged 0-12")
    teen_13_17: int = Field(default=0, ge=0, description="Teens aged 13-17")
    adult_18_plus: int = Field(default=0, ge=0, description="Adults 18 and older")

    @model_validator(mode='after')
    def validate_at_least_one_person(self) -> 'AgeGroupCounts':
        """Ensure at least one person in some age group"""
        total = self.child_0_12 + self.teen_13_17 + self.adult_18_plus
        if total == 0:
            raise ValueError("Age groups must sum to at least 1 person")
        return self


class PartySettings(BaseModel):
    """Party planning settings with age distribution"""
    guest_count: int = Field(..., ge=2, le=80, description="Total number of guests")
    age_group_counts: AgeGroupCounts = Field(..., description="Age distribution of guests")

    @model_validator(mode='after')
    def validate_age_counts_match_guest_count(self) -> 'PartySettings':
        """Validate that age_group_counts sum equals guest_count"""
        age_sum = (
            self.age_group_counts.child_0_12 +
            self.age_group_counts.teen_13_17 +
            self.age_group_counts.adult_18_plus
        )
        if age_sum != self.guest_count:
            raise ValueError(
                f"Age group counts ({age_sum}) must sum to guest_count ({self.guest_count}). "
                f"child_0_12={self.age_group_counts.child_0_12}, "
                f"teen_13_17={self.age_group_counts.teen_13_17}, "
                f"adult_18_plus={self.age_group_counts.adult_18_plus}"
            )
        return self


class SessionRequest(BaseModel):
    """Base session request fields common to all planning types"""
    selected_cuisine: Optional[str] = Field(None, description="Cuisine selection, 'auto' for automatic")
    cuisine_preferences: Optional[List[str]] = Field(None, description="List of preferred cuisines")
    output_language: Optional[str] = Field(None, pattern="^[a-z]{2}(-[A-Z]{2})?$")
    measurement_system: Optional[Literal["metric", "imperial"]] = None
    inventory: Optional[Dict[str, Any]] = Field(None, description="Inventory with available_ingredients list")
    family_profile: Optional[Dict[str, Any]] = Field(None, description="Family profile with members, dietary restrictions")


class DailyPlanRequest(SessionRequest):
    """Request for daily meal planning with meal type and time context"""
    time_available_minutes: int = Field(..., ge=5, le=480, description="Total time available for cooking")
    servings: int = Field(..., ge=1, le=20, description="Number of servings needed")
    
    # Meal context for better recommendations
    meal_type: Optional[Literal["breakfast", "lunch", "dinner", "snack", "any"]] = Field(
        None,
        description="Type of meal being planned - helps with cultural/regional appropriateness"
    )
    meal_time: Optional[str] = Field(
        None,
        pattern="^([0-1][0-9]|2[0-3]):[0-5][0-9]$",
        description="Time of meal in 24h format (HH:MM) - used for regional meal type inference"
    )
    current_date: Optional[str] = Field(
        None,
        description="Current date (YYYY-MM-DD) - used for variety tracking"
    )


class PartyPlanRequest(SessionRequest):
    """Request for party meal planning with age-aware constraints"""
    party_settings: PartySettings = Field(..., description="Party settings including guest count and age distribution")


class WeeklyPlanRequest(SessionRequest):
    """Request for weekly meal planning with configurable horizon"""
    start_date: date = Field(..., description="Start date for weekly plan (YYYY-MM-DD)")
    num_days: int = Field(default=4, ge=1, le=4, description="Number of days to plan (1-4)")
    timezone: Optional[str] = Field(None, description="Timezone for day boundaries, fallback to app config")
    time_available_minutes: Optional[int] = Field(None, ge=5, le=480, description="Typical time available per day")
    servings: Optional[int] = Field(None, ge=1, le=20, description="Typical servings per day")


class MenuPlanResponse(BaseModel):
    """
    Response from planning endpoints (MENU_PLAN_SCHEMA)
    This is a simplified version - full schema validation happens via jsonschema
    """
    status: Literal["ok", "needs_clarification", "error"]
    selected_cuisine: str
    planning_window: Optional[Dict[str, Any]] = Field(
        None,
        description="For weekly plans: {start_date, num_days, timezone}"
    )
    menu_headers: List[str]
    menus: List[Dict[str, Any]]  # Full menu structure from schema
    variety_log: Dict[str, Any]
    nutrition_summary: Dict[str, Any]
    waste_summary: Dict[str, Any]
    shopping_suggestions: List[Dict[str, Any]]
    needs_clarification_questions: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None

    @model_validator(mode='after')
    def validate_planning_window_for_weekly(self) -> 'MenuPlanResponse':
        """Ensure planning_window exists if any menu is type weekly_day"""
        if self.menus:
            has_weekly = any(m.get("menu_type") == "weekly_day" for m in self.menus)
            if has_weekly and not self.planning_window:
                raise ValueError("planning_window is required when menu_type is weekly_day")
        return self
