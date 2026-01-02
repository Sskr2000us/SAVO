"""
Scanning API Routes
Endpoints for pantry/fridge scanning with Vision AI
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List, Dict, Optional
from uuid import UUID, uuid4
from datetime import datetime
from decimal import Decimal
import logging

from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user
from app.core.database import get_db_client
from app.core.vision_api import get_vision_client
from app.core.ingredient_normalization import get_normalizer
from app.api.routes.profile import get_full_profile

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scanning", tags=["scanning"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AnalyzeImageRequest(BaseModel):
    """Request model for image analysis"""
    scan_type: str = Field(default="pantry", pattern="^(pantry|fridge|counter|shopping|other)$")
    location_hint: Optional[str] = None


class DetectedIngredient(BaseModel):
    """Detected ingredient with confidence and alternatives"""
    id: str
    detected_name: str
    canonical_name: Optional[str]
    confidence: Decimal
    confidence_category: str  # "high", "medium", "low"
    category: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    quantity_confidence: Optional[float] = None
    quantity_source: Optional[str] = None
    close_alternatives: List[Dict] = []
    visual_similarity_group: Optional[str]
    allergen_warnings: List[Dict] = []
    bbox: Optional[Dict] = None
    confirmation_status: str = "pending"


class AnalyzeImageResponse(BaseModel):
    """Response from image analysis"""
    success: bool
    scan_id: str
    ingredients: List[DetectedIngredient]
    metadata: Dict
    requires_confirmation: bool
    message: Optional[str] = None


class ConfirmIngredientsRequest(BaseModel):
    """Request to confirm detected ingredients"""
    scan_id: str
    confirmations: List[Dict] = Field(
        ...,
        description="List of {detected_id, action, confirmed_name, quantity, unit}",
        example=[
            {"detected_id": "abc123", "action": "confirmed", "confirmed_name": "spinach", "quantity": 200, "unit": "grams"},
            {"detected_id": "def456", "action": "rejected"},
            {"detected_id": "ghi789", "action": "modified", "confirmed_name": "kale", "quantity": 150, "unit": "grams"}
        ]
    )


class ConfirmIngredientsResponse(BaseModel):
    """Response after confirmation"""
    success: bool
    confirmed_count: int
    rejected_count: int
    modified_count: int
    pantry_items_added: List[Dict]
    message: str


class ScanHistoryResponse(BaseModel):
    """User's scan history"""
    scans: List[Dict]
    total_scans: int
    accuracy_stats: Dict


class SubmitFeedbackRequest(BaseModel):
    """User feedback on detection quality"""
    scan_id: str
    detected_id: Optional[str] = None
    feedback_type: str = Field(pattern="^(correction|missing|false_positive|rating|comment)$")
    detected_name: Optional[str] = None
    correct_name: Optional[str] = None
    overall_rating: Optional[int] = Field(None, ge=1, le=5)
    accuracy_rating: Optional[int] = Field(None, ge=1, le=5)
    speed_rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = None


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/analyze-image", response_model=AnalyzeImageResponse)
async def analyze_image(
    image: UploadFile = File(..., description="Image file (JPEG/PNG)"),
    scan_type: str = Form(default="pantry"),
    location_hint: Optional[str] = Form(default=None),
    user_id: str = Depends(get_current_user)
):
    """
    Analyze pantry/fridge image and detect ingredients
    
    - **image**: Image file to analyze
    - **scan_type**: Type of scan (pantry/fridge/counter/shopping/other)
    - **location_hint**: Optional hint about location
    
    Returns detected ingredients with confidence scores and close alternatives
    """
    try:
        # Validate image file
        if image.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
            raise HTTPException(status_code=400, detail="Invalid image format. Use JPEG or PNG.")
        
        # Read image data
        image_data = await image.read()
        
        if len(image_data) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail="Image too large. Maximum 10MB.")
        
        # Get user profile for context
        profile = await get_full_profile(user_id)
        
        # Analyze image with Vision API
        vision_client = get_vision_client()
        analysis_result = await vision_client.analyze_image(
            image_data=image_data,
            scan_type=scan_type,
            location_hint=location_hint,
            user_preferences=profile
        )
        
        if not analysis_result["success"]:
            raise HTTPException(status_code=500, detail=f"Vision analysis failed: {analysis_result.get('error')}")
        
        # Create scan record in database
        db = get_db_client()
        scan_id = str(uuid4())
        
        # TODO: Upload image to storage (Supabase Storage or S3)
        image_url = None  # Placeholder
        
        # Estimate API cost
        api_cost = await vision_client.estimate_api_cost(image_data)
        
        # Insert scan record
        scan_record = await db.table("ingredient_scans").insert({
            "id": scan_id,
            "user_id": user_id,
            "image_url": image_url,
            "image_hash": analysis_result["metadata"]["image_hash"],
            "image_metadata": {
                "width": analysis_result["metadata"]["image_size"][0],
                "height": analysis_result["metadata"]["image_size"][1],
                "format": image.content_type,
                "size_bytes": len(image_data)
            },
            "scan_type": scan_type,
            "location_hint": location_hint,
            "status": "processing",
            "vision_provider": "openai",
            "api_cost_cents": api_cost
        }).execute()
        
        # Insert detected ingredients
        detected_ingredients = []
        requires_confirmation = False
        
        for ingredient_data in analysis_result["ingredients"]:
            detected_id = str(uuid4())
            confidence = ingredient_data["confidence"]
            
            # Check if needs confirmation
            if confidence < Decimal("0.80"):
                requires_confirmation = True
            
            # Insert detected ingredient
            await db.table("detected_ingredients").insert({
                "id": detected_id,
                "scan_id": scan_id,
                "user_id": user_id,
                "detected_name": ingredient_data["detected_name"],
                "canonical_name": ingredient_data.get("canonical_name"),
                "confidence": float(confidence),
                "detected_quantity": ingredient_data.get("quantity"),
                "detected_unit": ingredient_data.get("unit"),
                "quantity_confidence": ingredient_data.get("quantity_confidence"),
                "bbox": ingredient_data.get("bbox"),
                "close_alternatives": ingredient_data.get("close_alternatives", []),
                "visual_similarity_group": ingredient_data.get("visual_similarity_group"),
                "allergen_warnings": ingredient_data.get("allergen_warnings", []),
                "confirmation_status": "pending"
            }).execute()
            
            # Build response ingredient
            detected_ingredients.append(DetectedIngredient(
                id=detected_id,
                detected_name=ingredient_data["detected_name"],
                canonical_name=ingredient_data.get("canonical_name"),
                confidence=confidence,
                confidence_category=vision_client.get_confidence_category(confidence),
                category=ingredient_data.get("category", "other"),
                quantity=ingredient_data.get("quantity"),
                unit=ingredient_data.get("unit"),
                quantity_confidence=ingredient_data.get("quantity_confidence"),
                quantity_source=ingredient_data.get("quantity_source"),
                close_alternatives=ingredient_data.get("close_alternatives", []),
                visual_similarity_group=ingredient_data.get("visual_similarity_group"),
                allergen_warnings=ingredient_data.get("allergen_warnings", []),
                bbox=ingredient_data.get("bbox"),
                confirmation_status="pending"
            ))
        
        # Update scan processing time
        await db.table("ingredient_scans").update({
            "processing_time_ms": analysis_result["metadata"]["processing_time_ms"]
        }).eq("id", scan_id).execute()
        
        # Build response
        message = None
        if requires_confirmation:
            message = "Some ingredients detected with lower confidence. Please review and confirm."
        else:
            message = "All ingredients detected with high confidence!"
        
        return AnalyzeImageResponse(
            success=True,
            scan_id=scan_id,
            ingredients=detected_ingredients,
            metadata=analysis_result["metadata"],
            requires_confirmation=requires_confirmation,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/confirm-ingredients", response_model=ConfirmIngredientsResponse)
async def confirm_ingredients(
    request: ConfirmIngredientsRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Confirm, reject, or modify detected ingredients
    
    - **scan_id**: ID of the scan
    - **confirmations**: List of confirmation actions
    
    Confirmed ingredients are automatically added to user's pantry
    """
    try:
        db = get_db_client()
        
        # Verify scan belongs to user
        scan = await db.table("ingredient_scans").select("*").eq("id", request.scan_id).eq("user_id", user_id).execute()
        if not scan.data:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        confirmed_count = 0
        rejected_count = 0
        modified_count = 0
        pantry_items_added = []
        
        # Process each confirmation
        for confirmation in request.confirmations:
            detected_id = confirmation["detected_id"]
            action = confirmation["action"]
            confirmed_name = confirmation.get("confirmed_name")
            quantity = confirmation.get("quantity")
            unit = confirmation.get("unit")
            
            # Verify detected ingredient exists
            detected = await db.table("detected_ingredients").select("*").eq("id", detected_id).eq("user_id", user_id).execute()
            if not detected.data:
                logger.warning(f"Detected ingredient {detected_id} not found for user {user_id}")
                continue
            
            detected_item = detected.data[0]
            
            # Update confirmation status
            update_data = {
                "confirmation_status": action,
                "confirmed_at": datetime.utcnow().isoformat()
            }
            
            if action in ["confirmed", "modified"]:
                # Set confirmed name
                if action == "modified" and confirmed_name:
                    update_data["confirmed_name"] = confirmed_name
                    modified_count += 1
                else:
                    update_data["confirmed_name"] = detected_item["canonical_name"] or detected_item["detected_name"]
                    confirmed_count += 1
                
                # Update quantity if provided (user-entered)
                if quantity is not None:
                    update_data["detected_quantity"] = quantity
                    update_data["detected_unit"] = unit
                    update_data["quantity_confidence"] = 1.0  # User-entered = 100% confident
                
                # Add to pantry (trigger will handle this automatically)
                # But we'll track for response
                pantry_items_added.append({
                    "name": update_data["confirmed_name"],
                    "display_name": update_data["confirmed_name"].replace("_", " ").title(),
                    "quantity": quantity,
                    "unit": unit,
                    "source": "scan"
                })
                
            elif action == "rejected":
                rejected_count += 1
            
            # Update detected ingredient
            await db.table("detected_ingredients").update(update_data).eq("id", detected_id).execute()
        
        # Scan completion will be handled by trigger
        
        # Build response message
        message = f"Confirmed {confirmed_count}, modified {modified_count}, rejected {rejected_count} ingredients."
        if pantry_items_added:
            message += f" Added {len(pantry_items_added)} items to your pantry."
        
        return ConfirmIngredientsResponse(
            success=True,
            confirmed_count=confirmed_count,
            rejected_count=rejected_count,
            modified_count=modified_count,
            pantry_items_added=pantry_items_added,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingredient confirmation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Confirmation failed: {str(e)}")


@router.get("/history", response_model=ScanHistoryResponse)
async def get_scan_history(
    limit: int = 20,
    offset: int = 0,
    user_id: str = Depends(get_current_user)
):
    """
    Get user's scan history with accuracy stats
    
    - **limit**: Number of scans to return
    - **offset**: Pagination offset
    """
    try:
        db = get_db_client()
        
        # Get scans
        scans_result = await db.table("ingredient_scans") \
            .select("*, detected_ingredients(*)") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()
        
        # Get total count
        count_result = await db.table("ingredient_scans") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .execute()
        
        total_scans = count_result.count if count_result.count else 0
        
        # Get accuracy stats
        accuracy_result = await db.rpc("get_user_scanning_accuracy", {"p_user_id": user_id}).execute()
        accuracy_stats = accuracy_result.data[0] if accuracy_result.data else {
            "total_detections": 0,
            "confirmed_count": 0,
            "modified_count": 0,
            "rejected_count": 0,
            "accuracy_pct": 0
        }
        
        return ScanHistoryResponse(
            scans=scans_result.data,
            total_scans=total_scans,
            accuracy_stats=accuracy_stats
        )
        
    except Exception as e:
        logger.error(f"Failed to get scan history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.get("/pantry")
async def get_user_pantry(
    user_id: str = Depends(get_current_user)
):
    """
    Get user's current pantry inventory
    
    Returns list of confirmed ingredients with expiry tracking
    """
    try:
        db = get_db_client()
        
        # Call database function
        result = await db.rpc("get_user_pantry", {"p_user_id": user_id}).execute()
        
        return {
            "success": True,
            "pantry": result.data,
            "total_items": len(result.data)
        }
        
    except Exception as e:
        logger.error(f"Failed to get pantry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get pantry: {str(e)}")


@router.post("/feedback")
async def submit_feedback(
    request: SubmitFeedbackRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Submit feedback on detection quality
    
    - **scan_id**: ID of the scan
    - **feedback_type**: Type of feedback (correction/missing/false_positive/rating/comment)
    - **detected_name**: What AI detected (for corrections)
    - **correct_name**: What it should have been (for corrections)
    - **ratings**: Optional 1-5 star ratings
    - **comment**: Optional text comment
    """
    try:
        db = get_db_client()
        
        # Verify scan belongs to user
        scan = await db.table("ingredient_scans").select("id").eq("id", request.scan_id).eq("user_id", user_id).execute()
        if not scan.data:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Insert feedback
        feedback_data = {
            "user_id": user_id,
            "scan_id": request.scan_id,
            "feedback_type": request.feedback_type
        }
        
        if request.detected_id:
            feedback_data["detected_id"] = request.detected_id
        if request.detected_name:
            feedback_data["detected_name"] = request.detected_name
        if request.correct_name:
            feedback_data["correct_name"] = request.correct_name
        if request.overall_rating:
            feedback_data["overall_rating"] = request.overall_rating
        if request.accuracy_rating:
            feedback_data["accuracy_rating"] = request.accuracy_rating
        if request.speed_rating:
            feedback_data["speed_rating"] = request.speed_rating
        if request.comment:
            feedback_data["comment"] = request.comment
        
        await db.table("scan_feedback").insert(feedback_data).execute()
        
        return {
            "success": True,
            "message": "Thank you for your feedback! It helps improve detection accuracy."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


@router.delete("/pantry/{ingredient_name}")
async def remove_from_pantry(
    ingredient_name: str,
    user_id: str = Depends(get_current_user)
):
    """
    Remove ingredient from pantry (mark as used/removed)
    """
    try:
        db = get_db_client()
        
        # Update pantry item status
        result = await db.table("user_pantry") \
            .update({
                "status": "removed",
                "removed_at": datetime.utcnow().isoformat()
            }) \
            .eq("user_id", user_id) \
            .eq("ingredient_name", ingredient_name) \
            .execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Ingredient not found in pantry")
        
        return {
            "success": True,
            "message": f"Removed {ingredient_name} from pantry"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove from pantry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to remove: {str(e)}")


# ============================================================================
# NEW ENDPOINTS: Manual Entry & Serving Calculator
# ============================================================================

class ManualIngredientRequest(BaseModel):
    """Request to manually add ingredient"""
    ingredient_name: str
    quantity: Optional[float] = None
    unit: Optional[str] = "pieces"
    notes: Optional[str] = None


@router.post("/manual")
async def add_manual_ingredient(
    request: ManualIngredientRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Manually add ingredient to pantry
    
    Allows users to add ingredients without scanning:
    - Quick add from autocomplete
    - Voice input ("Add 2 tomatoes")
    - Bulk import from shopping list
    """
    try:
        from app.core.unit_converter import UnitConverter
        
        db = get_db_client()
        normalizer = get_normalizer()
        
        # Normalize ingredient name
        canonical_name = normalizer.normalize_name(request.ingredient_name)
        
        # Validate unit if provided
        if request.unit:
            unit_category = UnitConverter.get_unit_category(request.unit)
            if unit_category == "unknown":
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown unit: {request.unit}. Try: grams, ml, pieces, cups"
                )
        
        # Check if ingredient already exists in pantry
        existing = await db.table("user_pantry") \
            .select("*") \
            .eq("user_id", user_id) \
            .eq("ingredient_name", canonical_name) \
            .eq("status", "available") \
            .execute()
        
        if existing.data:
            # Update existing quantity
            old_item = existing.data[0]
            old_qty = old_item.get("quantity") or 0
            old_unit = old_item.get("unit") or request.unit
            
            # Try to convert and add quantities
            new_qty = old_qty
            if request.quantity:
                if old_unit == request.unit:
                    new_qty = old_qty + request.quantity
                elif UnitConverter.can_convert(request.unit, old_unit):
                    converted_qty = UnitConverter.convert(request.quantity, request.unit, old_unit)
                    new_qty = old_qty + converted_qty
                else:
                    # Can't convert, keep old quantity and warn
                    logger.warning(f"Cannot convert {request.unit} to {old_unit} for {canonical_name}")
                    new_qty = old_qty
            
            await db.table("user_pantry") \
                .update({
                    "quantity": new_qty,
                    "unit": old_unit,
                    "updated_at": datetime.utcnow().isoformat()
                }) \
                .eq("id", old_item["id"]) \
                .execute()
            
            return {
                "success": True,
                "action": "updated",
                "ingredient": canonical_name,
                "display_name": request.ingredient_name,
                "quantity": new_qty,
                "unit": old_unit,
                "message": f"Updated {canonical_name} quantity to {new_qty} {old_unit}"
            }
        else:
            # Insert new ingredient
            result = await db.table("user_pantry").insert({
                "user_id": user_id,
                "ingredient_name": canonical_name,
                "display_name": request.ingredient_name,
                "quantity": request.quantity,
                "unit": request.unit,
                "estimated": False,  # User-entered
                "confidence": 1.0,
                "source": "manual",
                "status": "available",
                "notes": request.notes
            }).execute()
            
            return {
                "success": True,
                "action": "added",
                "ingredient": canonical_name,
                "display_name": request.ingredient_name,
                "quantity": request.quantity,
                "unit": request.unit,
                "message": f"Added {canonical_name} to your pantry"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add manual ingredient: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add ingredient: {str(e)}")


class CheckSufficiencyRequest(BaseModel):
    """Request to check recipe sufficiency"""
    recipe_id: str
    servings: int = Field(ge=1, le=100)


class CheckSufficiencyResponse(BaseModel):
    """Response with sufficiency status"""
    sufficient: bool
    missing: List[Dict]
    surplus: List[Dict]
    scaling_factor: float
    total_missing: int
    total_sufficient: int
    total_ingredients: int
    shopping_list: Optional[List[Dict]] = None


@router.post("/check-sufficiency", response_model=CheckSufficiencyResponse)
async def check_recipe_sufficiency(
    request: CheckSufficiencyRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Check if user has enough ingredients for recipe
    
    Answers: "Do I have enough to make this recipe for N people?"
    
    Returns:
    - sufficient: True/False
    - missing: List of ingredients to buy with quantities
    - surplus: List of ingredients with excess
    - shopping_list: Practical shopping list with rounded quantities
    """
    try:
        from app.core.serving_calculator import ServingCalculator
        
        db = get_db_client()
        
        # Get recipe with ingredients
        recipe = await db.table("recipes") \
            .select("*, recipe_ingredients(ingredient_name, quantity, unit)") \
            .eq("id", request.recipe_id) \
            .single() \
            .execute()
        
        if not recipe.data:
            raise HTTPException(status_code=404, detail="Recipe not found")
        
        # Get user's pantry with quantities
        pantry = await db.table("user_pantry") \
            .select("ingredient_name, quantity, unit") \
            .eq("user_id", user_id) \
            .eq("status", "available") \
            .execute()
        
        # Convert pantry to dict
        pantry_dict = {
            item["ingredient_name"]: {
                "quantity": item.get("quantity") or 0,
                "unit": item.get("unit") or "pieces"
            }
            for item in pantry.data
        }
        
        # Calculate sufficiency
        result = ServingCalculator.check_sufficiency(
            pantry_items=pantry_dict,
            recipe_ingredients=recipe.data["recipe_ingredients"],
            recipe_servings=recipe.data.get("servings", 4),
            needed_servings=request.servings
        )
        
        # Generate shopping list if missing ingredients
        shopping_list = None
        if result["missing"]:
            shopping_list = ServingCalculator.generate_shopping_list(result["missing"])
        
        return CheckSufficiencyResponse(
            sufficient=result["sufficient"],
            missing=result["missing"],
            surplus=result["surplus"],
            scaling_factor=result["scaling_factor"],
            total_missing=result["total_missing"],
            total_sufficient=result["total_sufficient"],
            total_ingredients=result["total_ingredients"],
            shopping_list=shopping_list
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check sufficiency: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check sufficiency: {str(e)}")
        logger.error(f"Failed to remove from pantry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to remove from pantry: {str(e)}")
