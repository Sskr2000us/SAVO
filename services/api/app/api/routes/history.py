"""
History endpoints - /history/recipes
"""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query, status

from app.models.history import RecipeHistoryCreate, RecipeHistoryResponse
from app.middleware.auth import get_current_user
from app.core.database import add_recipe_to_history, get_recipe_history

router = APIRouter()


@router.post("/recipes", response_model=RecipeHistoryResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe_history(
    entry: RecipeHistoryCreate,
    user_id: str = Depends(get_current_user),
):
    """Record a cooked recipe in history"""

    # Persist into the recipe_history table.
    # Keep payload compatible with the current migration schema.
    insert_data: Dict[str, Any] = {
        "recipe_name": entry.recipe_name,
        "cuisine": entry.cuisine,
        "was_successful": True,
    }

    if entry.user_rating is not None:
        insert_data["user_rating"] = entry.user_rating
    if entry.notes:
        insert_data["user_notes"] = entry.notes
    if entry.selected_from_plan_id:
        insert_data["meal_plan_id"] = entry.selected_from_plan_id

    row = await add_recipe_to_history(user_id, insert_data)

    cooked_at = row.get("completed_at") or row.get("cooked_at")
    history_id = row.get("id") or row.get("history_id")
    recipe_id = row.get("recipe_id") or entry.recipe_id

    # If DB didn't return a datetime, fall back to now.
    if cooked_at is None:
        from datetime import datetime

        cooked_at = datetime.utcnow()

    return RecipeHistoryResponse(
        history_id=str(history_id) if history_id is not None else "",
        recipe_id=str(recipe_id) if recipe_id is not None else "",
        cooked_at=cooked_at,
    )


@router.get("/recipes")
async def list_recipe_history(
    limit: int = Query(10, ge=1, le=100),
    cuisine: Optional[str] = Query(None),
    user_id: str = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Get most recent cooked recipes"""
    return await get_recipe_history(user_id=user_id, limit=limit, cuisine=cuisine)
