"""
YouTube ranking endpoint - POST /youtube/rank
"""
from fastapi import APIRouter

from app.models.youtube import YouTubeRankRequest, YouTubeRankResponse
from app.core.orchestrator import youtube_rank

router = APIRouter()


@router.post("/rank", response_model=YouTubeRankResponse)
async def post_rank(req: YouTubeRankRequest):
    """Rank YouTube videos for a recipe"""
    context = {
        "recipe_name": req.recipe_name,
        "recipe_cuisine": req.recipe_cuisine,
        "recipe_techniques": req.recipe_techniques,
        "candidates": [c.model_dump() for c in req.candidates],
        "output_language": req.output_language,
    }
    result = await youtube_rank(context)
    return YouTubeRankResponse(**result)
