"""
Graph Intelligence API Endpoints
Provides substitutions, confusions, pairings, and recipe compatibility
"""

from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional, List
from pydantic import BaseModel, Field
import asyncpg

from ..core.database import get_db_connection
from ..services.graph_intelligence_service import GraphIntelligenceService

router = APIRouter(prefix="/api/graph", tags=["graph"])
graph_service = GraphIntelligenceService()


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class SubstitutionContext(BaseModel):
    """Context for substitution recommendations"""
    form: Optional[str] = Field(None, description="Ingredient form (fresh, dried, powdered)")
    dish_type: Optional[str] = Field(None, description="Dish type (curry, stew, etc.)")
    cuisine: Optional[str] = Field(None, description="Cuisine type")
    dietary_restrictions: Optional[List[str]] = Field(None, description="Dietary restrictions")


class SubstitutionRequest(BaseModel):
    """Substitution request"""
    ingredient_id: str = Field(..., description="Source ingredient UUID")
    context: Optional[SubstitutionContext] = None
    limit: int = Field(10, ge=1, le=50)


class ConfusionRequest(BaseModel):
    """Confusion disambiguation request"""
    detected_ingredients: List[str] = Field(..., description="List of ingredient IDs", min_items=2)
    visual_features: Optional[dict] = Field(None, description="Visual features from image")
    user_context: Optional[dict] = Field(None, description="User context")


class PairingsRequest(BaseModel):
    """Pairing suggestion request"""
    ingredient_ids: List[str] = Field(..., description="List of ingredient IDs", min_items=1)
    cuisine_type: Optional[str] = None
    dish_type: Optional[str] = None
    limit: int = Field(20, ge=1, le=50)


class RecipeCompatibilityRequest(BaseModel):
    """Recipe compatibility request"""
    ingredient_ids: List[str] = Field(..., description="List of ingredient IDs", min_items=2)
    cuisine_type: Optional[str] = None


class GroceryListRequest(BaseModel):
    """Grocery list optimization request"""
    ingredient_ids: List[str] = Field(..., description="Ingredients needed")
    user_inventory: Optional[List[str]] = Field(None, description="Ingredients already owned")
    budget_constraint: Optional[float] = Field(None, description="Budget limit")


class SubstitutionFeedback(BaseModel):
    """Substitution feedback"""
    substitution_id: str
    was_accepted: bool
    feedback_note: Optional[str] = None


# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/substitutions")
async def get_substitutions(
    request: SubstitutionRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Get substitution recommendations for an ingredient
    
    **Context filters:**
    - form: fresh, dried, powdered
    - dish_type: curry, stew, marinade, etc.
    - cuisine: indian, italian, chinese, etc.
    - dietary_restrictions: vegetarian, vegan, gluten_free, etc.
    
    **Example:**
    ```json
    {
        "ingredient_id": "uuid-here",
        "context": {
            "form": "powdered",
            "dish_type": "curry",
            "cuisine": "indian"
        },
        "limit": 5
    }
    ```
    """
    try:
        context_dict = request.context.dict() if request.context else None
        
        substitutions = await graph_service.get_substitutions(
            conn,
            request.ingredient_id,
            context=context_dict,
            limit=request.limit
        )
        
        return {
            "ingredient_id": request.ingredient_id,
            "context": context_dict,
            "substitutions": substitutions,
            "count": len(substitutions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/substitutions/{ingredient_id}")
async def get_substitutions_simple(
    ingredient_id: str,
    limit: int = Query(10, ge=1, le=50),
    form: Optional[str] = Query(None),
    dish_type: Optional[str] = Query(None),
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Get substitutions (simple GET endpoint)
    
    **Example:**
    ```
    GET /api/graph/substitutions/{id}?limit=5&form=powdered&dish_type=curry
    ```
    """
    try:
        context = {}
        if form:
            context["form"] = form
        if dish_type:
            context["dish_type"] = dish_type
        
        substitutions = await graph_service.get_substitutions(
            conn,
            ingredient_id,
            context=context if context else None,
            limit=limit
        )
        
        return {
            "ingredient_id": ingredient_id,
            "substitutions": substitutions,
            "count": len(substitutions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resolve-confusion")
async def resolve_confusion(
    request: ConfusionRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Disambiguate between commonly confused ingredients
    
    **Use case:**
    - Visual scan detected multiple similar-looking ingredients
    - User reports confusion between ingredients
    - Need help distinguishing between similar items
    
    **Example:**
    ```json
    {
        "detected_ingredients": ["turmeric-id", "ginger-id"],
        "visual_features": {
            "dominant_colors": ["yellow", "orange"]
        }
    }
    ```
    """
    try:
        result = await graph_service.resolve_confusion(
            conn,
            request.detected_ingredients,
            visual_features=request.visual_features,
            user_context=request.user_context
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pairings")
async def get_pairings(
    request: PairingsRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Get complementary ingredient pairing suggestions
    
    **Use case:**
    - User has some ingredients, suggest what else to add
    - Building a recipe from scratch
    - Exploring flavor combinations
    
    **Example:**
    ```json
    {
        "ingredient_ids": ["cumin-id", "coriander-id"],
        "cuisine_type": "indian",
        "dish_type": "curry",
        "limit": 10
    }
    ```
    """
    try:
        pairings = await graph_service.get_pairings(
            conn,
            request.ingredient_ids,
            cuisine_type=request.cuisine_type,
            dish_type=request.dish_type,
            limit=request.limit
        )
        
        return {
            "input_ingredients": request.ingredient_ids,
            "cuisine_type": request.cuisine_type,
            "dish_type": request.dish_type,
            "pairings": pairings,
            "count": len(pairings)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/derived-from/{ingredient_id}")
async def get_derived_from(
    ingredient_id: str,
    limit: int = Query(50, ge=1, le=200),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get base ingredients that this ingredient is derived from."""
    try:
        rows = await graph_service.get_derived_from(conn, ingredient_id, limit=limit)
        return {"ingredient_id": ingredient_id, "derived_from": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/derivatives/{ingredient_id}")
async def get_derivatives(
    ingredient_id: str,
    limit: int = Query(50, ge=1, le=200),
    conn: asyncpg.Connection = Depends(get_db_connection),
):
    """Get ingredients derived from this base ingredient."""
    try:
        rows = await graph_service.get_derivatives(conn, ingredient_id, limit=limit)
        return {"ingredient_id": ingredient_id, "derivatives": rows, "count": len(rows)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recipe-compatibility")
async def calculate_recipe_compatibility(
    request: RecipeCompatibilityRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Calculate how well ingredients work together in a recipe
    
    **Use case:**
    - Validating a recipe's ingredient combinations
    - Checking if new ingredient fits existing recipe
    - Understanding ingredient harmony
    
    **Returns:**
    - Compatibility score (0.0 to 1.0)
    - Compatibility level (excellent, good, fair, poor)
    - Individual pairing details
    
    **Example:**
    ```json
    {
        "ingredient_ids": ["chicken-id", "yogurt-id", "ginger-id", "garlic-id"],
        "cuisine_type": "indian"
    }
    ```
    """
    try:
        result = await graph_service.calculate_recipe_compatibility(
            conn,
            request.ingredient_ids,
            cuisine_type=request.cuisine_type
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/optimize-grocery-list")
async def optimize_grocery_list(
    request: GroceryListRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Optimize grocery shopping list
    
    **Features:**
    - Identifies items already in inventory
    - Suggests item consolidations
    - Proposes cheaper/available substitutes
    - Groups by category for efficient shopping
    
    **Example:**
    ```json
    {
        "ingredient_ids": ["tomato-id", "onion-id", "garlic-id"],
        "user_inventory": ["onion-id"],
        "budget_constraint": 50.00
    }
    ```
    """
    try:
        result = await graph_service.optimize_grocery_list(
            conn,
            request.ingredient_ids,
            user_inventory=request.user_inventory,
            budget_constraint=request.budget_constraint
        )
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/substitution-feedback")
async def record_substitution_feedback(
    feedback: SubstitutionFeedback,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Record user feedback on substitution suggestion
    
    **Purpose:**
    - Learn from user acceptance/rejection
    - Improve future recommendations
    - Track substitution success rates
    
    **Example:**
    ```json
    {
        "substitution_id": "uuid-here",
        "was_accepted": true,
        "feedback_note": "Worked great in curry!"
    }
    ```
    """
    try:
        success = await graph_service.record_substitution_feedback(
            conn,
            feedback.substitution_id,
            feedback.was_accepted,
            feedback.feedback_note
        )
        
        if success:
            return {
                "status": "success",
                "message": "Feedback recorded"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to record feedback")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def graph_health():
    """Health check for graph intelligence service"""
    return {
        "status": "healthy",
        "service": "graph_intelligence",
        "features": {
            "substitutions": True,
            "confusion_disambiguation": True,
            "pairings": True,
            "recipe_compatibility": True,
            "grocery_optimization": True
        }
    }
