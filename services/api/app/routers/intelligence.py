"""
Visual Intelligence API Endpoints
Provides ingredient identification, visual feature extraction, and similarity search
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from typing import List, Optional
from pydantic import BaseModel
import uuid

from app.services.visual_intelligence import (
    VisualIntelligenceService,
    IdentificationResult,
    VisualFeatures
)
from app.core.database import get_db

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])

# Pydantic models for API
class IngredientMatchResponse(BaseModel):
    ingredient_id: str
    canonical_name: str
    confidence: float
    reasoning: str
    visual_similarity: float

class VisualFeaturesResponse(BaseModel):
    dominant_colors: List[str]
    color_histogram: dict
    texture_description: str
    brightness: float
    contrast: float

class IdentificationResponse(BaseModel):
    top_matches: List[IngredientMatchResponse]
    visual_features: VisualFeaturesResponse
    detected_state: str
    confidence_score: float
    processing_time_ms: int
    model_version: str

class SimilarIngredientResponse(BaseModel):
    ingredient_id: str
    canonical_name: str
    similarity_score: float
    visual_features: VisualFeaturesResponse

# Initialize service (singleton)
_visual_service = None

def get_visual_service() -> VisualIntelligenceService:
    """Get or create visual intelligence service instance"""
    global _visual_service
    if _visual_service is None:
        _visual_service = VisualIntelligenceService()
    return _visual_service

@router.post("/identify-ingredient", response_model=IdentificationResponse)
async def identify_ingredient(
    file: UploadFile = File(...),
    user_location: Optional[str] = None,
    cuisine_preference: Optional[str] = None,
    service: VisualIntelligenceService = Depends(get_visual_service),
    db = Depends(get_db)
):
    """
    Identify ingredient from uploaded image using GPT-4 Vision
    
    Args:
        file: Image file (JPEG, PNG, WebP)
        user_location: Optional user location for regional context
        cuisine_preference: Optional cuisine preference for better matching
    
    Returns:
        IdentificationResponse with top matches and visual features
    """
    
    # Validate file type
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Supported: JPEG, PNG, WebP"
        )
    
    # Read image data
    image_data = await file.read()
    
    # Validate file size (max 10MB)
    if len(image_data) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail="File too large. Maximum size: 10MB"
        )
    
    # Build context
    context = {}
    if user_location:
        context["location"] = user_location
    if cuisine_preference:
        context["cuisine"] = cuisine_preference
    
    try:
        # Identify ingredient
        result = await service.identify_ingredient(image_data, context)
        
        # Match against database
        if result.top_matches:
            for match in result.top_matches:
                # Query database for ingredient
                db_ingredient = await db.fetchrow(
                    """
                    SELECT id, canonical_name 
                    FROM master_ingredients 
                    WHERE LOWER(canonical_name) = LOWER($1)
                    LIMIT 1
                    """,
                    match.canonical_name
                )
                
                if db_ingredient:
                    match.ingredient_id = str(db_ingredient['id'])
                else:
                    # Try fuzzy match
                    db_ingredient = await db.fetchrow(
                        """
                        SELECT id, canonical_name,
                               similarity(canonical_name, $1) as sim
                        FROM master_ingredients
                        WHERE similarity(canonical_name, $1) > 0.3
                        ORDER BY sim DESC
                        LIMIT 1
                        """,
                        match.canonical_name
                    )
                    
                    if db_ingredient:
                        match.ingredient_id = str(db_ingredient['id'])
                        match.canonical_name = db_ingredient['canonical_name']
                    else:
                        match.ingredient_id = str(uuid.uuid4())  # Temporary ID
        
        # Convert to response model
        return IdentificationResponse(
            top_matches=[
                IngredientMatchResponse(**match.__dict__)
                for match in result.top_matches
            ],
            visual_features=VisualFeaturesResponse(**result.visual_features.__dict__),
            detected_state=result.detected_state,
            confidence_score=result.confidence_score,
            processing_time_ms=result.processing_time_ms,
            model_version=result.model_version
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Identification failed: {str(e)}"
        )

@router.post("/extract-visual-features", response_model=VisualFeaturesResponse)
async def extract_visual_features(
    file: UploadFile = File(...),
    service: VisualIntelligenceService = Depends(get_visual_service)
):
    """
    Extract visual features from image without identification
    
    Useful for:
    - Pre-processing before batch identification
    - Visual similarity search
    - Feature caching
    """
    
    # Validate file type
    if file.content_type not in ["image/jpeg", "image/png", "image/webp"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid file type. Supported: JPEG, PNG, WebP"
        )
    
    # Read image data
    image_data = await file.read()
    
    try:
        # Extract features
        signature = await service.extract_visual_signature(image_data)
        
        return VisualFeaturesResponse(
            dominant_colors=signature["dominant_colors"],
            color_histogram=signature["color_histogram"],
            texture_description=signature["texture"],
            brightness=signature["brightness"],
            contrast=signature["contrast"]
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Feature extraction failed: {str(e)}"
        )

@router.get("/similar-ingredients/{ingredient_id}", response_model=List[SimilarIngredientResponse])
async def get_similar_ingredients(
    ingredient_id: str,
    limit: int = 10,
    db = Depends(get_db)
):
    """
    Find visually similar ingredients to the given ingredient
    
    Uses stored visual features for similarity matching
    """
    
    try:
        # Get target ingredient features
        target = await db.fetchrow(
            """
            SELECT id, canonical_name, 
                   dominant_colors, surface_texture
            FROM master_ingredients
            WHERE id = $1
            """,
            uuid.UUID(ingredient_id)
        )
        
        if not target:
            raise HTTPException(status_code=404, detail="Ingredient not found")
        
        # Get all ingredients with visual features
        candidates = await db.fetch(
            """
            SELECT id, canonical_name,
                   dominant_colors, surface_texture
            FROM master_ingredients
            WHERE id != $1
              AND dominant_colors IS NOT NULL
            """,
            uuid.UUID(ingredient_id)
        )
        
        # Calculate similarity (simplified - just color overlap for now)
        similarities = []
        target_colors = set(target['dominant_colors'] or [])
        
        for candidate in candidates:
            candidate_colors = set(candidate['dominant_colors'] or [])
            
            if not candidate_colors:
                continue
            
            # Jaccard similarity
            intersection = len(target_colors & candidate_colors)
            union = len(target_colors | candidate_colors)
            similarity = intersection / union if union > 0 else 0.0
            
            if similarity > 0:
                similarities.append({
                    "ingredient_id": str(candidate['id']),
                    "canonical_name": candidate['canonical_name'],
                    "similarity_score": similarity,
                    "dominant_colors": list(candidate_colors),
                    "texture": candidate['surface_texture'] [0] if candidate['surface_texture'] else "unknown"
                })
        
        # Sort by similarity
        similarities.sort(key=lambda x: x['similarity_score'], reverse=True)
        
        # Return top matches
        return [
            SimilarIngredientResponse(
                ingredient_id=s["ingredient_id"],
                canonical_name=s["canonical_name"],
                similarity_score=s["similarity_score"],
                visual_features=VisualFeaturesResponse(
                    dominant_colors=s["dominant_colors"],
                    color_histogram={},
                    texture_description=s["texture"],
                    brightness=0.5,
                    contrast=0.5
                )
            )
            for s in similarities[:limit]
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Similarity search failed: {str(e)}"
        )

@router.post("/confirm-identification")
async def confirm_identification(
    scan_result_id: str,
    confirmed_ingredient_id: str,
    was_correct: bool,
    correction_reason: Optional[str] = None,
    db = Depends(get_db)
):
    """
    User confirms or corrects an identification result
    
    This feedback is used to:
    - Improve model accuracy
    - Track confusion patterns
    - Update confidence thresholds
    """
    
    try:
        # Update visual_scan_results
        await db.execute(
            """
            UPDATE visual_scan_results
            SET user_confirmed_ingredient_id = $1,
                was_correct = $2,
                correction_reason = $3
            WHERE id = $4
            """,
            uuid.UUID(confirmed_ingredient_id),
            was_correct,
            correction_reason,
            uuid.UUID(scan_result_id)
        )
        
        return {
            "success": True,
            "message": "Feedback recorded. Thank you for improving our system!"
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to record feedback: {str(e)}"
        )
