"""
Recipe endpoints - image generation, details, etc.
"""
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
import httpx

router = APIRouter()


class RecipeImageRequest(BaseModel):
    """Request for recipe image URL"""
    recipe_name: str = Field(..., description="Recipe name to generate image for")
    cuisine: str = Field(default="general", description="Cuisine type")


class RecipeImageResponse(BaseModel):
    """Response with recipe image URL"""
    recipe_name: str
    image_url: str
    source: str = Field(default="unsplash", description="Image source provider")


@router.post("/image", response_model=RecipeImageResponse)
async def get_recipe_image(req: RecipeImageRequest):
    """
    Get a recipe image URL from Unsplash (free, no API key needed)
    
    Alternative sources:
    - Unsplash: Free, high-quality food photos (used here)
    - Pexels: Free, requires API key
    - Pixabay: Free, simple API
    - DALL-E 3: $0.04/image, OpenAI API (best quality, custom generated)
    """
    try:
        # Use Unsplash Source API (no key required for basic usage)
        # Format: https://source.unsplash.com/featured/?food,pasta,italian
        
        # Clean recipe name for search query
        query_parts = [
            "food",
            req.cuisine.lower() if req.cuisine != "general" else "",
            req.recipe_name.lower().replace(" ", ",")
        ]
        query = ",".join(p for p in query_parts if p)
        
        # Unsplash featured random image (1200x800)
        image_url = f"https://source.unsplash.com/1200x800/?{query}"
        
        # Alternative: Use Unsplash API for consistent images
        # This requires an access key but gives better control
        # For production, consider using:
        # - Unsplash API with access key (free tier: 50 req/hour)
        # - Cache image URLs in database to avoid repeated lookups
        # - Pre-generate images for common recipes
        
        return RecipeImageResponse(
            recipe_name=req.recipe_name,
            image_url=image_url,
            source="unsplash"
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate image: {str(e)}"
        )


@router.get("/image/{recipe_name}")
async def get_recipe_image_by_name(recipe_name: str, cuisine: str = "general"):
    """Get recipe image by name (GET endpoint for convenience)"""
    req = RecipeImageRequest(recipe_name=recipe_name, cuisine=cuisine)
    return await get_recipe_image(req)
