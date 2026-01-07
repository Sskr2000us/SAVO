"""
Waste Prevention API Router
Endpoints for spoilage prediction, expiry tracking, storage alerts, and waste analytics
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
import asyncpg

from ..core.database import get_db_connection
from ..services.waste_prevention_service import WastePreventionService

router = APIRouter(prefix="/api/waste", tags=["waste"])

# Initialize service
waste_service = WastePreventionService()


# Request/Response Models
class SpoilagePredictionRequest(BaseModel):
    """Request for spoilage prediction"""
    inventory_item_id: str
    current_temperature: Optional[float] = Field(None, description="Current storage temperature (°C)")
    current_humidity: Optional[int] = Field(None, ge=0, le=100, description="Current humidity (%)")


class ExpiringItemsRequest(BaseModel):
    """Request for expiring items"""
    user_id: str
    days_threshold: int = Field(7, ge=1, le=30, description="Days to look ahead")
    include_predictions: bool = Field(True, description="Include spoilage predictions")


class StorageAlertsRequest(BaseModel):
    """Request for storage alerts"""
    user_id: str


class RecipeSuggestionsRequest(BaseModel):
    """Request for recipe suggestions"""
    user_id: str
    days_threshold: int = Field(5, ge=1, le=14, description="Consider items expiring within N days")


class WasteAnalyticsRequest(BaseModel):
    """Request for waste analytics"""
    user_id: str
    days_lookback: int = Field(30, ge=7, le=90, description="Days to analyze")


@router.post("/predict-spoilage")
async def predict_spoilage(
    request: SpoilagePredictionRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Predict when an inventory item will spoil
    
    Args:
        request: Spoilage prediction request
        
    Returns:
        Spoilage prediction with confidence, recommendations, and warning signs
    """
    try:
        # Prepare storage conditions if provided
        current_conditions = None
        if request.current_temperature is not None or request.current_humidity is not None:
            current_conditions = {}
            if request.current_temperature is not None:
                current_conditions["temperature"] = request.current_temperature
            if request.current_humidity is not None:
                current_conditions["humidity"] = request.current_humidity
        
        prediction = await waste_service.predict_spoilage(
            conn,
            request.inventory_item_id,
            current_conditions
        )
        
        if "error" in prediction:
            if prediction["error"] == "Inventory item not found":
                raise HTTPException(status_code=404, detail=prediction["error"])
            raise HTTPException(status_code=500, detail=prediction["error"])
        
        return prediction
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/expiring-items")
async def get_expiring_items(
    request: ExpiringItemsRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Get inventory items expiring soon
    
    Args:
        request: Expiring items request
        
    Returns:
        Items categorized by urgency (critical, urgent, warning, caution)
    """
    try:
        expiring = await waste_service.get_expiring_items(
            conn,
            request.user_id,
            request.days_threshold,
            request.include_predictions
        )
        
        if "error" in expiring:
            raise HTTPException(status_code=500, detail=expiring["error"])
        
        return expiring
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/storage-alerts")
async def get_storage_alerts(
    request: StorageAlertsRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Get storage condition alerts
    
    Args:
        request: Storage alerts request
        
    Returns:
        List of items with storage issues and recommendations
    """
    try:
        alerts = await waste_service.get_storage_alerts(
            conn,
            request.user_id
        )
        
        if "error" in alerts:
            raise HTTPException(status_code=500, detail=alerts["error"])
        
        return alerts
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recipe-suggestions")
async def suggest_recipes_by_expiry(
    request: RecipeSuggestionsRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Suggest recipes using expiring ingredients
    
    Args:
        request: Recipe suggestions request
        
    Returns:
        Recipe/ingredient suggestions prioritized by urgency
    """
    try:
        suggestions = await waste_service.suggest_recipes_by_expiry(
            conn,
            request.user_id,
            request.days_threshold
        )
        
        if "error" in suggestions:
            raise HTTPException(status_code=500, detail=suggestions["error"])
        
        return suggestions
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analytics")
async def get_waste_analytics(
    request: WasteAnalyticsRequest,
    conn: asyncpg.Connection = Depends(get_db_connection)
):
    """
    Get waste analytics dashboard data
    
    Args:
        request: Waste analytics request
        
    Returns:
        Comprehensive waste analytics with trends and insights
    """
    try:
        analytics = await waste_service.get_waste_analytics(
            conn,
            request.user_id,
            request.days_lookback
        )
        
        if "error" in analytics:
            raise HTTPException(status_code=500, detail=analytics["error"])
        
        return analytics
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "waste_prevention",
        "timestamp": datetime.now().isoformat(),
        "features": [
            "spoilage_prediction",
            "expiry_tracking",
            "storage_alerts",
            "recipe_suggestions",
            "waste_analytics"
        ]
    }


# Utility endpoints
@router.get("/storage-requirements")
async def get_storage_requirements():
    """Get storage requirements by category"""
    return {
        "storage_requirements": waste_service.storage_requirements,
        "categories": list(waste_service.storage_requirements.keys())
    }


@router.get("/risk-levels")
async def get_risk_levels():
    """Get waste risk levels by category"""
    return {
        "risk_levels": waste_service.category_risk_levels,
        "categories": list(waste_service.category_risk_levels.keys())
    }
