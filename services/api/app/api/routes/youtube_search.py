"""
YouTube search API integration
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import httpx
import os

router = APIRouter()


class YouTubeSearchRequest(BaseModel):
    """Request to search YouTube videos"""
    recipe_name: str = Field(..., description="Recipe name to search for")
    cuisine: str = Field(default="", description="Cuisine type (optional)")
    max_results: int = Field(default=5, ge=1, le=10, description="Max videos to return")


class YouTubeSearchResponse(BaseModel):
    """YouTube search results"""
    candidates: list[dict]


@router.post("/search", response_model=YouTubeSearchResponse)
async def search_youtube(req: YouTubeSearchRequest):
    """
    Search YouTube for recipe videos
    
    Requires: YOUTUBE_API_KEY environment variable
    Get one free at: https://console.cloud.google.com/apis/credentials
    
    Free tier: 10,000 requests/day
    """
    api_key = os.getenv("YOUTUBE_API_KEY")
    if not api_key:
        # Return mock data if no API key
        return YouTubeSearchResponse(candidates=[
            {
                "video_id": f"mock_{req.recipe_name}_1",
                "title": f"How to Make {req.recipe_name}",
                "channel": "Cooking Channel",
                "language": "en",
                "transcript": f"Learn to make {req.recipe_name}...",
                "metadata": {"duration": "12:00", "views": 500000}
            }
        ])
    
    try:
        # Build search query
        query = req.recipe_name
        if req.cuisine:
            query = f"{req.recipe_name} {req.cuisine} recipe"
        else:
            query = f"{req.recipe_name} recipe"
        
        # Call YouTube Data API
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "type": "video",
                    "videoDuration": "medium",  # 4-20 minutes
                    "videoDefinition": "high",
                    "relevanceLanguage": "en",
                    "maxResults": req.max_results,
                    "q": query,
                    "key": api_key
                }
            )
            response.raise_for_status()
            data = response.json()
        
        # Convert to candidate format
        candidates = []
        for item in data.get("items", []):
            video_id = item["id"]["videoId"]
            snippet = item["snippet"]
            
            candidates.append({
                "video_id": video_id,
                "title": snippet["title"],
                "channel": snippet["channelTitle"],
                "language": "en",
                "transcript": snippet["description"][:500],  # Use description as transcript placeholder
                "metadata": {
                    "thumbnail": snippet["thumbnails"]["high"]["url"],
                    "published_at": snippet["publishedAt"]
                }
            })
        
        return YouTubeSearchResponse(candidates=candidates)
        
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"YouTube search failed: {str(e)}")
