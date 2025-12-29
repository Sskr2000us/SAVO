"""
Cuisines endpoint - GET /cuisines
"""
from fastapi import APIRouter
from app.core.cuisine_metadata import get_all_cuisines

router = APIRouter()


@router.get("/cuisines")
async def get_cuisines():
    """Get all available cuisines with daily/party structures"""
    return get_all_cuisines()
