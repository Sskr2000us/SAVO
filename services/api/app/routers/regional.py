"""
Regional Intelligence API Router
Endpoints for regional variants, cuisine recommendations, and cultural context
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import asyncpg

from ..core.database import get_db_connection
from ..services.regional_intelligence_service import RegionalIntelligenceService

router = APIRouter(prefix="/api/regional", tags=["regional"])

# Initialize service
regional_service = RegionalIntelligenceService()


# Request/Response Models
class RegionalVariant(BaseModel):
    """Regional variant response model"""
    variant_id: str
    ingredient_name: str
    region: str
    country_code: str
    variant_notes: Optional[str]
    flavor_differences: Optional[str]
    appearance_differences: Optional[str]
    typical_uses: Optional[str]
    is_native: bool
    availability_level: str


class CuisineRecommendationRequest(BaseModel):
    """Request for cuisine-specific recommendations"""
    cuisine_type: str = Field(..., description="Cuisine type (indian, chinese, italian, etc.)")
    user_region: Optional[str] = Field(None, description="User's region for availability filtering")
    limit: int = Field(20, ge=1, le=50, description="Maximum recommendations")


class SeasonalAvailabilityRequest(BaseModel):
    """Request for seasonal availability check"""
    ingredient_id: str
    region: Optional[str] = None
    month: Optional[int] = Field(None, ge=1, le=12, description="Month (1-12)")


class LocalSourcingRequest(BaseModel):
    """Request for local sourcing suggestions"""
    ingredient_ids: List[str]
    user_region: str
    current_month: Optional[int] = Field(None, ge=1, le=12)


class CuisineComparisonRequest(BaseModel):
    """Request to compare cuisines"""
    cuisine_types: List[str] = Field(..., min_items=2, max_items=5)
    limit: int = Field(10, ge=1, le=20)


@router.get("/variants/{ingredient_id}", response_model=List[RegionalVariant])
async def get_regional_variants(
    ingredient_id: str,
    user_region: Optional[str] = None,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Get regional variants of an ingredient
    
    Args:
        ingredient_id: Ingredient UUID
        user_region: Optional user region for prioritization
        
    Returns:
        List of regional variants with cultural context
    """
    try:
        variants = await regional_service.get_regional_variants(
            conn,
            ingredient_id,
            user_region
        )
        
        if not variants:
            raise HTTPException(
                status_code=404,
                detail=f"No regional variants found for ingredient {ingredient_id}"
            )
        
        return variants
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cuisine-recommendations")
async def get_cuisine_recommendations(
    request: CuisineRecommendationRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Get ingredient recommendations for a specific cuisine
    
    Args:
        request: Cuisine recommendation request
        
    Returns:
        Categorized ingredient recommendations
    """
    try:
        recommendations = await regional_service.get_cuisine_recommendations(
            conn,
            request.cuisine_type,
            request.user_region,
            request.limit
        )
        
        if "error" in recommendations:
            raise HTTPException(status_code=500, detail=recommendations["error"])
        
        return recommendations
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cultural-context/{ingredient_id}")
async def get_cultural_context(
    ingredient_id: str,
    cuisine_type: Optional[str] = None,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Get cultural context for an ingredient
    
    Args:
        ingredient_id: Ingredient UUID
        cuisine_type: Optional cuisine filter
        
    Returns:
        Cultural context with regional variants, pairings, and uses
    """
    try:
        context = await regional_service.get_cultural_context(
            conn,
            ingredient_id,
            cuisine_type
        )
        
        if "error" in context:
            if context["error"] == "Ingredient not found":
                raise HTTPException(status_code=404, detail=context["error"])
            raise HTTPException(status_code=500, detail=context["error"])
        
        return context
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/seasonal-availability")
async def check_seasonal_availability(
    request: SeasonalAvailabilityRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Check seasonal availability of ingredient
    
    Args:
        request: Seasonal availability request
        
    Returns:
        Seasonal availability information with sourcing recommendations
    """
    try:
        availability = await regional_service.check_seasonal_availability(
            conn,
            request.ingredient_id,
            request.region,
            request.month
        )
        
        if "error" in availability:
            if availability["error"] == "Ingredient not found":
                raise HTTPException(status_code=404, detail=availability["error"])
            raise HTTPException(status_code=500, detail=availability["error"])
        
        return availability
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/local-sourcing")
async def get_local_sourcing_suggestions(
    request: LocalSourcingRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Get local sourcing suggestions for ingredients
    
    Args:
        request: Local sourcing request
        
    Returns:
        Sourcing suggestions with local/imported classification
    """
    try:
        suggestions = await regional_service.get_local_sourcing_suggestions(
            conn,
            request.ingredient_ids,
            request.user_region,
            request.current_month
        )
        
        if "error" in suggestions:
            raise HTTPException(status_code=500, detail=suggestions["error"])
        
        return suggestions
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/compare-cuisines")
async def compare_regional_cuisines(
    request: CuisineComparisonRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Compare ingredients across different regional cuisines
    
    Args:
        request: Cuisine comparison request
        
    Returns:
        Comparison of ingredients across cuisines with common ingredients
    """
    try:
        comparison = await regional_service.compare_regional_cuisines(
            conn,
            request.cuisine_types,
            request.limit
        )
        
        if "error" in comparison:
            raise HTTPException(status_code=500, detail=comparison["error"])
        
        return comparison
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "regional_intelligence",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "regional_variants",
            "cuisine_recommendations",
            "cultural_context",
            "seasonal_availability",
            "local_sourcing",
            "cuisine_comparison"
        ]
    }


# Utility endpoints
@router.get("/supported-cuisines")
async def get_supported_cuisines(
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Get list of supported cuisines"""
    try:
        cuisines = await conn.fetch("""
            SELECT DISTINCT unnest(cuisine_types) as cuisine_type
            FROM ingredient_pairings
            ORDER BY cuisine_type
        """)
        
        return {
            "supported_cuisines": [row["cuisine_type"] for row in cuisines],
            "total": len(cuisines)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/supported-regions")
async def get_supported_regions(
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """Get list of regions with variant data"""
    try:
        regions = await conn.fetch("""
            SELECT 
                region,
                country_code,
                COUNT(*) as ingredient_count
            FROM ingredient_regional_variants
            GROUP BY region, country_code
            ORDER BY ingredient_count DESC
        """)
        
        return {
            "supported_regions": [
                {
                    "region": row["region"],
                    "country_code": row["country_code"],
                    "ingredient_count": row["ingredient_count"]
                }
                for row in regions
            ],
            "total": len(regions)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
