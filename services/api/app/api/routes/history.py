"""
History endpoints - POST /history/recipes
"""
from fastapi import APIRouter, status

from app.models.history import RecipeHistoryCreate, RecipeHistoryResponse
from app.core.storage import get_storage

router = APIRouter()


@router.post("/recipes", response_model=RecipeHistoryResponse, status_code=status.HTTP_201_CREATED)
async def create_recipe_history(entry: RecipeHistoryCreate):
    """Record a cooked recipe in history"""
    storage = get_storage()
    return storage.create_history_entry(entry)
