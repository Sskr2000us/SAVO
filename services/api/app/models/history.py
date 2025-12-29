"""
Recipe history models for tracking cooked recipes (E5)
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class RecipeHistoryCreate(BaseModel):
    """Request to record a cooked recipe"""
    recipe_id: str = Field(..., description="Recipe ID that was cooked")
    recipe_name: str = Field(..., description="Recipe name")
    cuisine: str = Field(..., description="Cuisine type")
    cooking_method: str = Field(..., description="Primary cooking method used")
    servings_made: int = Field(..., ge=1, description="Number of servings prepared")
    selected_from_plan_id: Optional[str] = Field(None, description="Plan ID if selected from a generated plan")
    leftover_servings: Optional[int] = Field(None, ge=0, description="Estimated leftover servings")
    user_rating: Optional[int] = Field(None, ge=1, le=5, description="User rating 1-5 stars")
    notes: Optional[str] = Field(None, description="User notes about the cooking experience")


class RecipeHistoryResponse(BaseModel):
    """Response after recording recipe history"""
    history_id: str = Field(..., description="Unique history entry ID")
    recipe_id: str
    cooked_at: datetime
    message: str = Field(default="Recipe history recorded successfully")
