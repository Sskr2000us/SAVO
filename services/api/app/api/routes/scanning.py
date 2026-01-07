"""
Scanning API Routes
Endpoints for pantry/fridge scanning with Vision AI
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Any, List, Dict, Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
import io

from pydantic import BaseModel, Field

from PIL import Image, ImageFilter, ImageStat

from app.middleware.auth import get_current_user
from app.core.database import get_db_client
from app.core.vision_api import get_vision_client
from app.core.ingredient_normalization import get_normalizer
from app.api.routes.profile import get_full_profile
from app.core.media_storage import upload_inventory_image

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scanning", tags=["scanning"])


def _normalize_unit(unit: Optional[str]) -> str:
    u = (unit or "").strip().lower()
    if not u:
        return "pieces"
    if u in {"pcs", "pc", "piece"}:
        return "pieces"
    if u == "g":
        return "grams"
    if u == "l":
        return "liters"
    return u


def _scan_type_to_storage_location(scan_type: Optional[str]) -> str:
    st = (scan_type or "").strip().lower()
    if st in {"pantry", "fridge", "freezer", "counter"}:
        return st
    if st in {"shopping", "other"}:
        return "pantry"
    return "pantry"


def _titleize(name: str) -> str:
    return (name or "").replace("_", " ").strip().title()


def _assess_image_quality(image_data: bytes) -> Dict[str, Any]:
    """Return lightweight image quality signals for capture gating.

    Uses only Pillow (no numpy/opencv) to keep deps minimal.
    """
    try:
        img = Image.open(io.BytesIO(image_data))
        img = img.convert("RGB")
    except Exception:
        return {"ok": False, "issues": ["unreadable"], "metrics": {}}

    # Downscale for speed/consistency.
    try:
        img.thumbnail((640, 640))
    except Exception:
        pass

    gray = img.convert("L")
    stat = ImageStat.Stat(gray)

    brightness_mean = float(stat.mean[0]) if stat.mean else 0.0
    contrast_stddev = float(stat.stddev[0]) if stat.stddev else 0.0

    # Blur proxy: strength of high-frequency content.
    # Lower edge mean => likely blur / out-of-focus.
    try:
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edges)
        edge_mean = float(edge_stat.mean[0]) if edge_stat.mean else 0.0
        edge_stddev = float(edge_stat.stddev[0]) if edge_stat.stddev else 0.0
    except Exception:
        edge_mean = 0.0
        edge_stddev = 0.0

    issues: List[str] = []

    # Thresholds tuned conservatively to avoid blocking valid images.
    if brightness_mean < 55:
        issues.append("too_dark")
    elif brightness_mean > 215:
        issues.append("too_bright")

    if contrast_stddev < 18:
        issues.append("low_contrast")

    if edge_mean < 9.5 and edge_stddev < 18:
        issues.append("too_blurry")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "metrics": {
            "brightness_mean": round(brightness_mean, 2),
            "contrast_stddev": round(contrast_stddev, 2),
            "edge_mean": round(edge_mean, 2),
            "edge_stddev": round(edge_stddev, 2),
        },
    }


def _parse_ts(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        dt = ts
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if not isinstance(ts, str):
        return None
    raw = ts.strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _effective_seen_at(item: Dict[str, Any]) -> Optional[datetime]:
    for k in ("last_seen_at", "updated_at", "created_at"):
        dt = _parse_ts(item.get(k))
        if dt:
            return dt
    return None


def _inventory_status(
    item: Dict[str, Any],
    now: datetime,
    maybe_days: int,
    stale_days: int,
) -> str:
    # If the row is explicitly inactive, treat it as inactive regardless of time.
    if item.get("is_current") is False:
        return "inactive"

    # Defensive: normalize to tz-aware UTC so date math never fails.
    if isinstance(now, datetime) and now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    elif isinstance(now, datetime) and now.tzinfo is not None:
        now = now.astimezone(timezone.utc)

    seen_at = _effective_seen_at(item)
    if not seen_at:
        return "maybe"

    if seen_at.tzinfo is None:
        seen_at = seen_at.replace(tzinfo=timezone.utc)
    else:
        seen_at = seen_at.astimezone(timezone.utc)

    age_days = (now - seen_at).days
    if stale_days > 0 and age_days >= stale_days:
        return "stale"
    if maybe_days > 0 and age_days >= maybe_days:
        return "maybe"
    return "available"


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
    # Visual verification fields
    thumbnail_url: Optional[str] = None  # Cropped image of this ingredient
    full_image_url: Optional[str] = None  # Full scan image for reference


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


class ScanReceiptResponse(BaseModel):
    success: bool
    receipt_id: str
    added_count: int
    updated_count: int
    pantry_items: List[Dict]
    metadata: Dict
    message: Optional[str] = None


class ScanReceiptPreviewResponse(BaseModel):
    success: bool
    receipt_id: str
    items: List[Dict]
    metadata: Dict
    requires_confirmation: bool = True
    message: Optional[str] = None


class ReceiptConfirmItem(BaseModel):
    raw_name: Optional[str] = None
    canonical_name: Optional[str] = None
    display_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    confidence: Optional[float] = None


class ConfirmReceiptRequest(BaseModel):
    receipt_id: str
    items: List[ReceiptConfirmItem]
    storage_location: str = "pantry"


class PantryCleanupResponse(BaseModel):
    success: bool
    marked_inactive_count: int
    stale_days: int
    message: str


class PantrySummaryResponse(BaseModel):
    success: bool
    have: List[Dict]
    maybe_have: List[Dict]
    verify: List[Dict]
    totals: Dict[str, int]


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

        # Capture-quality gate (prevents wasting Vision calls on unusable frames).
        quality = _assess_image_quality(image_data)
        if not quality.get("ok"):
            issues = quality.get("issues") or []
            metrics = quality.get("metrics") or {}

            # Keep message short and actionable.
            if "too_dark" in issues:
                msg = "Too dark — turn on lights and retake."
            elif "too_blurry" in issues:
                msg = "Too blurry — hold steady and retake."
            elif "too_bright" in issues:
                msg = "Too bright/glare — adjust angle and retake."
            else:
                msg = "Image quality too low — please retake."

            raise HTTPException(
                status_code=400,
                detail={
                    "code": "image_quality",
                    "message": msg,
                    "issues": issues,
                    "metrics": metrics,
                },
            )
        
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

        # Upload image to Supabase Storage (best-effort)
        image_url = None
        try:
            image_url = upload_inventory_image(
                user_id=user_id,
                content=image_data,
                content_type=image.content_type,
            )
        except Exception as e:
            logger.warning(f"Failed to upload scan image: {e}")
        
        # Estimate API cost
        api_cost = await vision_client.estimate_api_cost(image_data)
        
        # Insert scan record
        scan_record = db.table("ingredient_scans").insert({
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
            
            # Process ingredient thumbnail (async, non-blocking)
            bbox = ingredient_data.get("bbox")
            thumbnail_url = None
            try:
                from app.core.image_processor import upload_ingredient_thumbnail
                thumbnail_url = await upload_ingredient_thumbnail(
                    user_id=user_id,
                    scan_id=scan_id,
                    detected_id=detected_id,
                    image_data=image_data,
                    bbox=bbox,
                    confidence=float(confidence),
                    confidence_category=vision_client.get_confidence_category(confidence)
                )
            except Exception as e:
                logger.warning(f"Failed to create thumbnail for {detected_id}: {e}")
            
            # Insert detected ingredient
            db.table("detected_ingredients").insert({
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
                "thumbnail_url": thumbnail_url,
                "full_image_url": image_url,
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
                confirmation_status="pending",
                thumbnail_url=thumbnail_url,
                full_image_url=image_url
            ))
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
        db.table("ingredient_scans").update({
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
        from app.core.unit_converter import UnitConverter

        db = get_db_client()
        normalizer = get_normalizer()
        
        # Verify scan belongs to user
        scan = db.table("ingredient_scans").select("*").eq("id", request.scan_id).eq("user_id", user_id).execute()
        if not scan.data:
            raise HTTPException(status_code=404, detail="Scan not found")

        scan_record = scan.data[0]
        storage_location = _scan_type_to_storage_location(scan_record.get("scan_type"))
        item_state = "raw"
        scan_image_url = scan_record.get("image_url")

        # Track scan time early for consistent last_seen_* stamps.
        now_iso = datetime.utcnow().isoformat()

        # Training consent + retention (best-effort)
        training_opt_in = False
        retention_days = 0
        try:
            hp = (
                db.table("household_profiles")
                .select("scan_training_opt_in, scan_training_retention_days")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            if hp.data:
                training_opt_in = bool(hp.data[0].get("scan_training_opt_in"))
                retention_days = int(hp.data[0].get("scan_training_retention_days") or 0)
        except Exception as e:
            logger.warning(f"Failed to read training consent settings: {e}")
        
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
            detected = db.table("detected_ingredients").select("*").eq("id", detected_id).eq("user_id", user_id).execute()
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
                # Determine final confirmed name
                final_name = None
                if action == "modified" and confirmed_name:
                    final_name = confirmed_name
                    modified_count += 1
                else:
                    final_name = detected_item.get("canonical_name") or detected_item.get("detected_name")
                    confirmed_count += 1

                canonical_name = normalizer.normalize_name(final_name or "")
                update_data["confirmed_name"] = canonical_name

                # Store ground-truth training label (only if explicitly opted-in)
                if training_opt_in and retention_days > 0:
                    try:
                        expires_at = (datetime.utcnow() + timedelta(days=retention_days)).isoformat()
                        db.table("scan_training_labels").insert(
                            {
                                "user_id": user_id,
                                "scan_id": request.scan_id,
                                "detected_id": detected_id,
                                "confirmed_name": canonical_name,
                                "original_detected_name": detected_item.get("detected_name"),
                                "bbox": detected_item.get("bbox"),
                                "image_url": scan_image_url,
                                "expires_at": expires_at,
                            }
                        ).execute()
                    except Exception as e:
                        logger.warning(f"Failed to store training label: {e}")
                
                # Update quantity if provided (user-entered)
                if quantity is not None:
                    update_data["detected_quantity"] = quantity
                    update_data["detected_unit"] = unit
                    update_data["quantity_confidence"] = 1.0  # User-entered = 100% confident

                # Upsert into canonical inventory (inventory_items)
                incoming_qty = None
                if quantity is not None:
                    incoming_qty = float(quantity)
                elif detected_item.get("detected_quantity") is not None:
                    incoming_qty = float(detected_item.get("detected_quantity"))
                else:
                    incoming_qty = 1.0

                incoming_unit = _normalize_unit(unit or detected_item.get("detected_unit") or "pieces")

                existing = (
                    db.table("inventory_items")
                    .select("*")
                    .eq("user_id", user_id)
                    .eq("canonical_name", canonical_name)
                    .eq("storage_location", storage_location)
                    .eq("item_state", item_state)
                    .order("updated_at", desc=True)
                    .limit(1)
                    .execute()
                )

                merged_qty = incoming_qty
                merged_unit = incoming_unit

                if existing.data:
                    existing_item = existing.data[0]
                    existing_qty = float(existing_item.get("quantity") or 0)
                    existing_unit = _normalize_unit(existing_item.get("unit") or "pieces")

                    if incoming_unit == existing_unit:
                        merged_qty = existing_qty + incoming_qty
                        merged_unit = existing_unit
                        update_payload = {
                            "quantity": merged_qty,
                            "unit": merged_unit,
                            "display_name": existing_item.get("display_name")
                            or _titleize(canonical_name),
                            "source": "scan",
                            "scan_confidence": float(detected_item.get("confidence") or 1.0),
                            "is_current": True,
                            "last_seen_at": now_iso,
                            "last_seen_scan_id": request.scan_id,
                        }
                        if scan_image_url and not existing_item.get("image_url"):
                            update_payload["image_url"] = scan_image_url
                        db.table("inventory_items").update(update_payload).eq("id", existing_item["id"]).execute()
                    elif UnitConverter.can_convert(incoming_unit, existing_unit):
                        converted = UnitConverter.convert(incoming_qty, incoming_unit, existing_unit)
                        merged_qty = existing_qty + float(converted)
                        merged_unit = existing_unit
                        update_payload = {
                            "quantity": merged_qty,
                            "unit": merged_unit,
                            "display_name": existing_item.get("display_name")
                            or _titleize(canonical_name),
                            "source": "scan",
                            "scan_confidence": float(detected_item.get("confidence") or 1.0),
                            "is_current": True,
                            "last_seen_at": now_iso,
                            "last_seen_scan_id": request.scan_id,
                        }
                        if scan_image_url and not existing_item.get("image_url"):
                            update_payload["image_url"] = scan_image_url
                        db.table("inventory_items").update(update_payload).eq("id", existing_item["id"]).execute()
                    else:
                        created = (
                            db.table("inventory_items")
                            .insert(
                                {
                                    "user_id": user_id,
                                    "canonical_name": canonical_name,
                                    "display_name": _titleize(final_name or canonical_name),
                                    "quantity": incoming_qty,
                                    "unit": incoming_unit,
                                    "storage_location": storage_location,
                                    "item_state": item_state,
                                    "source": "scan",
                                    "scan_confidence": float(detected_item.get("confidence") or 1.0),
                                    "image_url": scan_image_url,
                                    "is_current": True,
                                    "last_seen_at": now_iso,
                                    "last_seen_scan_id": request.scan_id,
                                }
                            )
                            .execute()
                        )
                        existing_item = created.data[0] if created.data else None
                else:
                    created = (
                        db.table("inventory_items")
                        .insert(
                            {
                                "user_id": user_id,
                                "canonical_name": canonical_name,
                                "display_name": _titleize(final_name or canonical_name),
                                "quantity": incoming_qty,
                                "unit": incoming_unit,
                                "storage_location": storage_location,
                                "item_state": item_state,
                                "source": "scan",
                                "scan_confidence": float(detected_item.get("confidence") or 1.0),
                                "image_url": scan_image_url,
                                "is_current": True,
                                "last_seen_at": now_iso,
                                "last_seen_scan_id": request.scan_id,
                            }
                        )
                        .execute()
                    )
                    existing_item = created.data[0] if created.data else None
                
                # Add to pantry (trigger will handle this automatically)
                # But we'll track for response
                pantry_items_added.append({
                    "name": canonical_name,
                    "display_name": _titleize(final_name or canonical_name),
                    "quantity": merged_qty,
                    "unit": merged_unit,
                    "source": "scan"
                })
                
            elif action == "rejected":
                rejected_count += 1
            
            # Update detected ingredient
            db.table("detected_ingredients").update(update_data).eq("id", detected_id).execute()

        # Latest-scan semantics (safer): after upserting the confirmed items for this scan,
        # mark older scan-sourced raw items in the same storage location inactive.
        # This avoids a window where everything is deactivated before the new items are written.
        try:
            (
                db.table("inventory_items")
                .update({"is_current": False})
                .eq("user_id", user_id)
                .eq("source", "scan")
                .eq("storage_location", storage_location)
                .eq("item_state", item_state)
                .eq("is_current", True)
                .neq("last_seen_scan_id", request.scan_id)
                .execute()
            )
        except Exception as e:
            logger.warning(f"Failed to deactivate previous scan inventory set: {e}")
        
        # Mark scan as completed (best-effort)
        try:
            db.table("ingredient_scans").update({"status": "completed"}).eq("id", request.scan_id).execute()
        except Exception:
            pass
        
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


@router.post("/scan-receipt", response_model=ScanReceiptResponse)
async def scan_receipt(
    image: UploadFile = File(..., description="Receipt image file (JPEG/PNG)"),
    storage_location: str = Form(default="pantry"),
    user_id: str = Depends(get_current_user),
):
    """Scan a grocery receipt and upsert items into inventory."""
    try:
        if image.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
            raise HTTPException(status_code=400, detail="Invalid image format. Use JPEG or PNG.")

        image_data = await image.read()
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large. Maximum 10MB.")

        db = get_db_client()
        normalizer = get_normalizer()

        # Receipt scan id (persisted to receipt_scans + inventory_items.last_seen_receipt_id).
        receipt_id = str(uuid4())
        now_iso = datetime.utcnow().isoformat()

        # Best-effort upload to storage for traceability (optional).
        image_url = None
        try:
            image_url = upload_inventory_image(
                user_id=user_id,
                content=image_data,
                content_type=image.content_type,
            )
        except Exception as e:
            logger.warning(f"Failed to upload receipt image: {e}")

        # Persist receipt scan event for referential integrity (best-effort until migration is applied).
        try:
            db.table("receipt_scans").insert(
                {
                    "id": receipt_id,
                    "user_id": user_id,
                    "image_url": image_url,
                    "created_at": now_iso,
                }
            ).execute()
        except Exception:
            pass

        # User profile context (optional; can help disambiguate items).
        profile = None
        try:
            profile = await get_full_profile(user_id)
        except Exception:
            profile = None

        vision_client = get_vision_client()
        analysis = await vision_client.analyze_receipt(
            image_data=image_data,
            user_preferences=profile,
        )

        if not analysis.get("success"):
            raise HTTPException(status_code=500, detail=f"Receipt analysis failed: {analysis.get('error')}")

        # Best-effort store analysis for later debugging/training.
        try:
            db.table("receipt_scans").update(
                {
                    "raw_text": analysis.get("raw_text"),
                    "analysis_json": analysis,
                    "status": "parsed",
                }
            ).eq("id", receipt_id).execute()
        except Exception:
            pass

        storage = _scan_type_to_storage_location(storage_location)
        item_state = "raw"

        added_count = 0
        updated_count = 0
        pantry_items: List[Dict] = []

        from app.core.unit_converter import UnitConverter

        def _is_source_check_violation(err: Exception) -> bool:
            payload = None
            if getattr(err, "args", None) and isinstance(err.args[0], dict):
                payload = err.args[0]
            if isinstance(payload, dict):
                if payload.get("code") != "23514":
                    return False
                text = f"{payload.get('message', '')} {payload.get('details', '')}"
                return "inventory_items_source_check" in text
            # Fallback string match (covers wrapped exceptions)
            text = str(err)
            return "inventory_items_source_check" in text and "23514" in text

        def _safe_update_inventory(item_id: str, payload: Dict) -> None:
            try:
                db.table("inventory_items").update(payload).eq("id", item_id).execute()
            except Exception as e:
                if _is_source_check_violation(e) and "source" in payload:
                    payload2 = dict(payload)
                    payload2.pop("source", None)
                    db.table("inventory_items").update(payload2).eq("id", item_id).execute()
                    return
                raise

        def _safe_insert_inventory(payload: Dict) -> None:
            try:
                db.table("inventory_items").insert(payload).execute()
            except Exception as e:
                if _is_source_check_violation(e) and payload.get("source") == "receipt":
                    payload2 = dict(payload)
                    payload2["source"] = "import"
                    db.table("inventory_items").insert(payload2).execute()
                    return
                raise

        for item in analysis.get("items", []):
            canonical = (item.get("canonical_name") or "").strip()
            if not canonical:
                # Fallback normalize if needed
                canonical = normalizer.normalize_name(item.get("raw_name") or "")
            if not canonical:
                continue

            incoming_qty = item.get("quantity")
            try:
                incoming_qty_f = float(incoming_qty) if incoming_qty is not None else 1.0
            except Exception:
                incoming_qty_f = 1.0

            incoming_unit = _normalize_unit(item.get("unit"))

            existing = (
                db.table("inventory_items")
                .select("*")
                .eq("user_id", user_id)
                .eq("canonical_name", canonical)
                .eq("storage_location", storage)
                .eq("item_state", item_state)
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )

            merged_qty = incoming_qty_f
            merged_unit = incoming_unit

            confidence = item.get("confidence")
            try:
                confidence_f = float(confidence) if confidence is not None else None
            except Exception:
                confidence_f = None

            if existing.data:
                existing_item = existing.data[0]
                existing_qty = float(existing_item.get("quantity") or 0)
                existing_unit = _normalize_unit(existing_item.get("unit") or "pieces")

                update_payload = {
                    "display_name": existing_item.get("display_name") or _titleize(canonical),
                    "source": "receipt",
                    "is_current": True,
                    "last_seen_at": now_iso,
                    "last_seen_receipt_id": receipt_id,
                }
                if image_url and not existing_item.get("image_url"):
                    update_payload["image_url"] = image_url

                if incoming_unit == existing_unit:
                    merged_qty = existing_qty + incoming_qty_f
                    merged_unit = existing_unit
                    update_payload.update({"quantity": merged_qty, "unit": merged_unit})
                    if confidence_f is not None:
                        update_payload["scan_confidence"] = confidence_f
                    _safe_update_inventory(existing_item["id"], update_payload)
                    updated_count += 1
                elif UnitConverter.can_convert(incoming_unit, existing_unit):
                    converted = UnitConverter.convert(incoming_qty_f, incoming_unit, existing_unit)
                    merged_qty = existing_qty + float(converted)
                    merged_unit = existing_unit
                    update_payload.update({"quantity": merged_qty, "unit": merged_unit})
                    if confidence_f is not None:
                        update_payload["scan_confidence"] = confidence_f
                    _safe_update_inventory(existing_item["id"], update_payload)
                    updated_count += 1
                else:
                    _safe_insert_inventory(
                        {
                            "user_id": user_id,
                            "canonical_name": canonical,
                            "display_name": _titleize(canonical),
                            "quantity": incoming_qty_f,
                            "unit": incoming_unit,
                            "storage_location": storage,
                            "item_state": item_state,
                            "source": "receipt",
                            "scan_confidence": confidence_f,
                            "image_url": image_url,
                            "is_current": True,
                            "last_seen_at": now_iso,
                            "last_seen_receipt_id": receipt_id,
                        }
                    )
                    added_count += 1

            else:
                _safe_insert_inventory(
                    {
                        "user_id": user_id,
                        "canonical_name": canonical,
                        "display_name": _titleize(canonical),
                        "quantity": incoming_qty_f,
                        "unit": incoming_unit,
                        "storage_location": storage,
                        "item_state": item_state,
                        "source": "receipt",
                        "scan_confidence": confidence_f,
                        "image_url": image_url,
                        "is_current": True,
                        "last_seen_at": now_iso,
                        "last_seen_receipt_id": receipt_id,
                    }
                )
                added_count += 1

            pantry_items.append(
                {
                    "name": canonical,
                    "display_name": _titleize(canonical),
                    "quantity": merged_qty,
                    "unit": merged_unit,
                    "source": "receipt",
                }
            )

        message = f"Receipt scanned. Added {added_count}, updated {updated_count} items."

        return ScanReceiptResponse(
            success=True,
            receipt_id=receipt_id,
            added_count=added_count,
            updated_count=updated_count,
            pantry_items=pantry_items,
            metadata=analysis.get("metadata") or {},
            message=message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Receipt scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Receipt scan failed: {str(e)}")


@router.post("/scan-receipt/preview", response_model=ScanReceiptPreviewResponse)
async def scan_receipt_preview(
    image: UploadFile = File(..., description="Receipt image file (JPEG/PNG)"),
    storage_location: str = Form(default="pantry"),
    user_id: str = Depends(get_current_user),
):
    """Scan a receipt and return detected items. Does NOT modify inventory."""

    try:
        if image.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
            raise HTTPException(status_code=400, detail="Invalid image format. Use JPEG or PNG.")

        image_data = await image.read()
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large. Maximum 10MB.")

        db = get_db_client()

        receipt_id = str(uuid4())
        now_iso = datetime.utcnow().isoformat()

        image_url = None
        try:
            image_url = upload_inventory_image(
                user_id=user_id,
                content=image_data,
                content_type=image.content_type,
            )
        except Exception as e:
            logger.warning(f"Failed to upload receipt image: {e}")

        try:
            db.table("receipt_scans").insert(
                {
                    "id": receipt_id,
                    "user_id": user_id,
                    "image_url": image_url,
                    "created_at": now_iso,
                    "status": "parsed",
                }
            ).execute()
        except Exception:
            pass

        profile = None
        try:
            profile = await get_full_profile(user_id)
        except Exception:
            profile = None

        vision_client = get_vision_client()
        analysis = await vision_client.analyze_receipt(
            image_data=image_data,
            user_preferences=profile,
        )

        if not analysis.get("success"):
            raise HTTPException(status_code=500, detail=f"Receipt analysis failed: {analysis.get('error')}")

        try:
            db.table("receipt_scans").update(
                {
                    "raw_text": analysis.get("raw_text"),
                    "analysis_json": analysis,
                    "status": "parsed",
                }
            ).eq("id", receipt_id).execute()
        except Exception:
            pass

        # Return items (no writes to inventory here)
        items = []
        for item in analysis.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            items.append(
                {
                    "raw_name": item.get("raw_name"),
                    "canonical_name": item.get("canonical_name"),
                    "quantity": item.get("quantity"),
                    "unit": item.get("unit"),
                    "confidence": float(item.get("confidence")) if item.get("confidence") is not None else None,
                    "raw_line": item.get("raw_line"),
                }
            )

        return ScanReceiptPreviewResponse(
            success=True,
            receipt_id=receipt_id,
            items=items,
            metadata=analysis.get("metadata") or {},
            requires_confirmation=True,
            message="Receipt scanned. Please confirm items before adding to inventory.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Receipt preview failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Receipt preview failed: {str(e)}")


@router.post("/scan-receipt/confirm", response_model=ScanReceiptResponse)
async def confirm_receipt_scan(
    request: ConfirmReceiptRequest,
    user_id: str = Depends(get_current_user),
):
    """Apply user-confirmed receipt items to inventory."""

    try:
        db = get_db_client()
        normalizer = get_normalizer()
        now_iso = datetime.utcnow().isoformat()

        storage = _scan_type_to_storage_location(request.storage_location)
        item_state = "raw"

        from app.core.unit_converter import UnitConverter

        added_count = 0
        updated_count = 0
        pantry_items: List[Dict] = []

        for item_in in request.items:
            raw_name = (item_in.raw_name or "").strip()
            canonical = (item_in.canonical_name or "").strip()
            display_name = (item_in.display_name or raw_name or canonical).strip()

            if not canonical:
                canonical = normalizer.normalize_name(raw_name or display_name)
            if not canonical:
                continue

            qty = item_in.quantity
            try:
                incoming_qty_f = float(qty) if qty is not None else 1.0
            except Exception:
                incoming_qty_f = 1.0

            incoming_unit = _normalize_unit(item_in.unit)

            existing = (
                db.table("inventory_items")
                .select("*")
                .eq("user_id", user_id)
                .eq("canonical_name", canonical)
                .eq("storage_location", storage)
                .eq("item_state", item_state)
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )

            merged_qty = incoming_qty_f
            merged_unit = incoming_unit

            confidence_f = None
            try:
                confidence_f = float(item_in.confidence) if item_in.confidence is not None else None
            except Exception:
                confidence_f = None

            if existing.data:
                existing_item = existing.data[0]
                existing_qty = float(existing_item.get("quantity") or 0)
                existing_unit = _normalize_unit(existing_item.get("unit") or "pieces")

                update_payload = {
                    "display_name": existing_item.get("display_name") or display_name or _titleize(canonical),
                    "source": "receipt",
                    "is_current": True,
                    "last_seen_at": now_iso,
                    "last_seen_receipt_id": request.receipt_id,
                }

                if incoming_unit == existing_unit:
                    merged_qty = existing_qty + incoming_qty_f
                    merged_unit = existing_unit
                    update_payload.update({"quantity": merged_qty, "unit": merged_unit})
                    if confidence_f is not None:
                        update_payload["scan_confidence"] = confidence_f
                    db.table("inventory_items").update(update_payload).eq("id", existing_item["id"]).execute()
                    updated_count += 1
                elif UnitConverter.can_convert(incoming_unit, existing_unit):
                    converted = UnitConverter.convert(incoming_qty_f, incoming_unit, existing_unit)
                    merged_qty = existing_qty + float(converted)
                    merged_unit = existing_unit
                    update_payload.update({"quantity": merged_qty, "unit": merged_unit})
                    if confidence_f is not None:
                        update_payload["scan_confidence"] = confidence_f
                    db.table("inventory_items").update(update_payload).eq("id", existing_item["id"]).execute()
                    updated_count += 1
                else:
                    db.table("inventory_items").insert(
                        {
                            "user_id": user_id,
                            "canonical_name": canonical,
                            "display_name": display_name or _titleize(canonical),
                            "quantity": incoming_qty_f,
                            "unit": incoming_unit,
                            "storage_location": storage,
                            "item_state": item_state,
                            "source": "receipt",
                            "scan_confidence": confidence_f,
                            "is_current": True,
                            "last_seen_at": now_iso,
                            "last_seen_receipt_id": request.receipt_id,
                        }
                    ).execute()
                    added_count += 1
            else:
                db.table("inventory_items").insert(
                    {
                        "user_id": user_id,
                        "canonical_name": canonical,
                        "display_name": display_name or _titleize(canonical),
                        "quantity": incoming_qty_f,
                        "unit": incoming_unit,
                        "storage_location": storage,
                        "item_state": item_state,
                        "source": "receipt",
                        "scan_confidence": confidence_f,
                        "is_current": True,
                        "last_seen_at": now_iso,
                        "last_seen_receipt_id": request.receipt_id,
                    }
                ).execute()
                added_count += 1

            pantry_items.append(
                {
                    "name": canonical,
                    "display_name": display_name or _titleize(canonical),
                    "quantity": merged_qty,
                    "unit": merged_unit,
                    "source": "receipt",
                }
            )

        try:
            db.table("receipt_scans").update(
                {
                    "status": "confirmed",
                    "confirmed_at": now_iso,
                }
            ).eq("id", request.receipt_id).eq("user_id", user_id).execute()
        except Exception:
            pass

        message = f"Receipt confirmed. Added {added_count}, updated {updated_count} items."
        return ScanReceiptResponse(
            success=True,
            receipt_id=request.receipt_id,
            added_count=added_count,
            updated_count=updated_count,
            pantry_items=pantry_items,
            metadata={"confirmed": True},
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Receipt confirm failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Receipt confirm failed: {str(e)}")


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
        scans_result = db.table("ingredient_scans") \
            .select("*, detected_ingredients(*)") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()
        
        # Get total count
        count_result = db.table("ingredient_scans") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .execute()
        
        total_scans = count_result.count if count_result.count else 0
        
        # Get accuracy stats
        accuracy_result = db.rpc("get_user_scanning_accuracy", {"p_user_id": user_id}).execute()
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
    include_inactive: bool = False,
    maybe_days: int = 7,
    stale_days: int = 30,
    user_id: str = Depends(get_current_user)
):
    """
    Get user's current pantry inventory
    
    Returns list of confirmed ingredients with expiry tracking
    """
    try:
        db = get_db_client()

        now = datetime.now(timezone.utc)

        # Canonical inventory is inventory_items; expose a backward-compatible pantry shape.
        items = (
            db.table("inventory_items")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        pantry = []
        for item in items.data or []:
            if not isinstance(item, dict):
                continue

            status = _inventory_status(item, now=now, maybe_days=maybe_days, stale_days=stale_days)
            if not include_inactive and status in {"inactive", "stale"}:
                continue

            pantry.append(
                {
                    "id": item.get("id"),
                    "ingredient_name": item.get("canonical_name"),
                    "display_name": item.get("display_name") or _titleize(item.get("canonical_name") or ""),
                    "quantity": item.get("quantity"),
                    "unit": item.get("unit"),
                    "storage_location": item.get("storage_location"),
                    "item_state": item.get("item_state"),
                    "source": item.get("source"),
                    "status": status,
                    "notes": item.get("notes"),
                    "expiry_date": item.get("expiry_date"),
                }
            )

        return {"success": True, "pantry": pantry, "total_items": len(pantry)}
        
    except Exception as e:
        logger.error(f"Failed to get pantry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get pantry: {str(e)}")


@router.post("/pantry/weekly-cleanup", response_model=PantryCleanupResponse)
async def pantry_weekly_cleanup(
    stale_days: int = 30,
    user_id: str = Depends(get_current_user),
):
    """Mark long-unseen scan/receipt items as inactive so the pantry stays manageable.

    Notes:
    - This does NOT delete rows.
    - Only affects scan/receipt sourced raw items.
    """
    try:
        if stale_days <= 0:
            raise HTTPException(status_code=400, detail="stale_days must be > 0")

        db = get_db_client()
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=stale_days)).isoformat()

        # Best-effort bulk update. Some rows may lack last_seen_at; handle those via a second pass.
        marked = 0
        try:
            res1 = (
                db.table("inventory_items")
                .update({"is_current": False})
                .eq("user_id", user_id)
                .eq("item_state", "raw")
                .in_("source", ["scan", "receipt"])
                .eq("is_current", True)
                .lt("last_seen_at", cutoff)
                .execute()
            )
            marked += len(res1.data or [])
        except Exception as e:
            logger.warning(f"Pantry cleanup bulk pass (last_seen_at) failed: {e}")

        try:
            res2 = (
                db.table("inventory_items")
                .update({"is_current": False})
                .eq("user_id", user_id)
                .eq("item_state", "raw")
                .in_("source", ["scan", "receipt"])
                .eq("is_current", True)
                .is_("last_seen_at", "null")
                .lt("updated_at", cutoff)
                .execute()
            )
            marked += len(res2.data or [])
        except Exception as e:
            logger.warning(f"Pantry cleanup bulk pass (updated_at) failed: {e}")

        return PantryCleanupResponse(
            success=True,
            marked_inactive_count=marked,
            stale_days=stale_days,
            message=f"Marked {marked} items inactive (not seen in {stale_days} days).",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pantry cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pantry cleanup failed: {str(e)}")


@router.get("/pantry/summary", response_model=PantrySummaryResponse)
async def pantry_summary(
    maybe_days: int = 7,
    stale_days: int = 30,
    max_verify: int = 5,
    user_id: str = Depends(get_current_user),
):
    """Return a lightweight pantry summary for planning.

    - **have**: fresh/high-confidence items (status=available)
    - **maybe_have**: older/uncertain items (status=maybe)
    - **verify**: up to max_verify items to ask the user about
    """
    try:
        db = get_db_client()
        now = datetime.now(timezone.utc)

        items = (
            db.table("inventory_items")
            .select("id, canonical_name, display_name, quantity, unit, storage_location, item_state, source, is_current, last_seen_at, updated_at")
            .eq("user_id", user_id)
            .eq("item_state", "raw")
            .execute()
        )

        have: List[Dict] = []
        maybe_have: List[Dict] = []
        verify_candidates: List[Dict] = []

        for item in items.data or []:
            if not isinstance(item, dict):
                continue

            status = _inventory_status(item, now=now, maybe_days=maybe_days, stale_days=stale_days)
            if status in {"inactive", "stale"}:
                continue

            entry = {
                "id": item.get("id"),
                "ingredient_name": item.get("canonical_name"),
                "display_name": item.get("display_name") or _titleize(item.get("canonical_name") or ""),
                "quantity": item.get("quantity"),
                "unit": item.get("unit"),
                "storage_location": item.get("storage_location"),
                "source": item.get("source"),
                "status": status,
            }

            if status == "available":
                have.append(entry)
            else:
                maybe_have.append(entry)

                seen_at = _effective_seen_at(item)
                age_days = (now - seen_at).days if seen_at else 9999
                verify_candidates.append({**entry, "age_days": age_days})

        verify_candidates.sort(key=lambda x: x.get("age_days", 9999), reverse=True)
        verify = verify_candidates[: max(0, min(int(max_verify), 10))]
        for v in verify:
            v.pop("age_days", None)

        return PantrySummaryResponse(
            success=True,
            have=have,
            maybe_have=maybe_have,
            verify=verify,
            totals={
                "have": len(have),
                "maybe_have": len(maybe_have),
                "verify": len(verify),
            },
        )
    except Exception as e:
        logger.error(f"Pantry summary failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pantry summary failed: {str(e)}")


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
        scan = db.table("ingredient_scans").select("id").eq("id", request.scan_id).eq("user_id", user_id).execute()
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
        
        db.table("scan_feedback").insert(feedback_data).execute()
        
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

        normalizer = get_normalizer()
        canonical_name = normalizer.normalize_name(ingredient_name)
        
        # Canonical inventory is inventory_items; delete matching items.
        result = (
            db.table("inventory_items")
            .delete()
            .eq("user_id", user_id)
            .eq("canonical_name", canonical_name)
            .execute()
        )
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Ingredient not found in pantry")
        
        return {
            "success": True,
            "message": f"Removed {canonical_name} from pantry"
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

        incoming_unit = _normalize_unit(request.unit)
        incoming_qty = float(request.quantity) if request.quantity is not None else 1.0
        
        # Validate unit if provided
        if request.unit:
            unit_category = UnitConverter.get_unit_category(request.unit)
            if unit_category == "unknown":
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown unit: {request.unit}. Try: grams, ml, pieces, cups"
                )
        
        # Check if ingredient already exists in canonical inventory
        existing = (
            db.table("inventory_items")
            .select("*")
            .eq("user_id", user_id)
            .eq("canonical_name", canonical_name)
            .eq("storage_location", "pantry")
            .eq("item_state", "raw")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        
        if existing.data:
            old_item = existing.data[0]
            old_qty = float(old_item.get("quantity") or 0)
            old_unit = _normalize_unit(old_item.get("unit") or incoming_unit)
            
            # Try to convert and add quantities
            new_qty = old_qty
            if incoming_unit == old_unit:
                new_qty = old_qty + incoming_qty
            elif UnitConverter.can_convert(incoming_unit, old_unit):
                converted_qty = UnitConverter.convert(incoming_qty, incoming_unit, old_unit)
                new_qty = old_qty + float(converted_qty)
            else:
                logger.warning(f"Cannot convert {incoming_unit} to {old_unit} for {canonical_name}")
                new_qty = old_qty

            db.table("inventory_items").update(
                {
                    "quantity": new_qty,
                    "unit": old_unit,
                    "display_name": old_item.get("display_name") or request.ingredient_name,
                    "source": "manual",
                    "scan_confidence": 1.0,
                    "notes": request.notes,
                }
            ).eq("id", old_item["id"]).execute()
            
            return {
                "success": True,
                "action": "updated",
                "ingredient": canonical_name,
                "display_name": request.ingredient_name,
                "quantity": new_qty,
                "unit": old_unit,
                "confidence": 1.0,
                "message": f"Updated {canonical_name} quantity to {new_qty} {old_unit}"
            }
        else:
            result = db.table("inventory_items").insert(
                {
                    "user_id": user_id,
                    "canonical_name": canonical_name,
                    "display_name": request.ingredient_name,
                    "quantity": incoming_qty,
                    "unit": incoming_unit,
                    "storage_location": "pantry",
                    "item_state": "raw",
                    "source": "manual",
                    "scan_confidence": 1.0,
                    "notes": request.notes,
                }
            ).execute()
            
            return {
                "success": True,
                "action": "added",
                "ingredient": canonical_name,
                "display_name": request.ingredient_name,
                "quantity": incoming_qty,
                "unit": incoming_unit,
                "confidence": 1.0,
                "message": f"Added {canonical_name} to your pantry"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add manual ingredient: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add ingredient: {str(e)}")


class CheckSufficiencyRequest(BaseModel):
    """Request to check recipe sufficiency"""
    recipe_id: Optional[str] = None
    recipe_ingredients: Optional[List[Dict[str, Any]]] = None
    recipe_servings: int = Field(default=4, ge=1, le=100)
    servings: int = Field(ge=1, le=100)


class CheckSufficiencyResponse(BaseModel):
    """Response with sufficiency status"""
    success: bool = True
    sufficient: bool
    missing: List[Dict]
    surplus: List[Dict]
    scaling_factor: float
    total_missing: int
    total_sufficient: int
    total_ingredients: int
    shopping_list: Optional[List[Dict]] = None
    message: Optional[str] = None


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
        
        normalizer = get_normalizer()

        # Minimal production logging for debugging (avoid logging ingredient names or full payload).
        try:
            uid_suffix = user_id[-6:] if isinstance(user_id, str) else "unknown"
        except Exception:
            uid_suffix = "unknown"

        logger.info(
            "check_sufficiency request uid_suffix=%s has_recipe_id=%s recipe_ingredients=%s recipe_servings=%s servings=%s",
            uid_suffix,
            bool(request.recipe_id),
            len(request.recipe_ingredients) if isinstance(request.recipe_ingredients, list) else 0,
            getattr(request, "recipe_servings", None),
            getattr(request, "servings", None),
        )

        # Resolve recipe ingredients
        recipe_ingredients: List[Dict[str, Any]] = []

        if isinstance(request.recipe_ingredients, list) and request.recipe_ingredients:
            # Accept from client (preferred path for LLM recipes)
            for ing in request.recipe_ingredients:
                if not isinstance(ing, dict):
                    continue
                name_raw = (ing.get("name") or ing.get("ingredient") or ing.get("canonical_name") or "").strip()
                if not name_raw:
                    continue
                try:
                    qty = float(ing.get("quantity") if ing.get("quantity") is not None else ing.get("amount") or 0)
                except Exception:
                    qty = 0.0
                unit = _normalize_unit((ing.get("unit") or "pieces"))
                recipe_ingredients.append(
                    {
                        "name": normalizer.normalize_name(name_raw),
                        "quantity": qty,
                        "unit": unit,
                    }
                )
        elif request.recipe_id:
            # Legacy path: attempt DB lookup
            recipe = (
                db.table("recipes")
                .select("*, recipe_ingredients(ingredient_name, quantity, unit)")
                .eq("id", request.recipe_id)
                .single()
                .execute()
            )
            if not recipe.data:
                raise HTTPException(status_code=404, detail="Recipe not found")
            for ing in recipe.data.get("recipe_ingredients") or []:
                try:
                    recipe_ingredients.append(
                        {
                            "name": normalizer.normalize_name((ing.get("ingredient_name") or "").strip()),
                            "quantity": float(ing.get("quantity") or 0),
                            "unit": _normalize_unit(ing.get("unit") or "pieces"),
                        }
                    )
                except Exception:
                    continue
        else:
            raise HTTPException(status_code=400, detail="Provide recipe_ingredients or recipe_id")

        if not recipe_ingredients:
            raise HTTPException(status_code=400, detail="No valid recipe ingredients provided")

        # Get user's canonical inventory (inventory_items)
        # Prefer current items when the schema supports it.
        try:
            pantry = (
                db.table("inventory_items")
                .select("canonical_name, quantity, unit")
                .eq("user_id", user_id)
                .eq("item_state", "raw")
                .in_("storage_location", ["pantry", "fridge", "freezer"])
                .eq("is_current", True)
                .execute()
            )
        except Exception:
            pantry = (
                db.table("inventory_items")
                .select("canonical_name, quantity, unit")
                .eq("user_id", user_id)
                .eq("item_state", "raw")
                .in_("storage_location", ["pantry", "fridge", "freezer"])
                .execute()
            )

        pantry_dict: Dict[str, Dict[str, Any]] = {}
        for item in pantry.data or []:
            if not isinstance(item, dict):
                continue
            name = (item.get("canonical_name") or "").strip()
            if not name:
                continue
            # Always normalize to ensure stable matching with recipe_ingredients.
            key = normalizer.normalize_name(name)
            if not key:
                continue
            try:
                qty = float(item.get("quantity") or 0)
            except Exception:
                qty = 0.0
            unit = _normalize_unit(item.get("unit") or "pieces")

            existing = pantry_dict.get(key)
            if not isinstance(existing, dict):
                pantry_dict[key] = {"quantity": qty, "unit": unit}
                continue

            # Aggregate quantities for duplicate keys (best-effort).
            try:
                from app.core.unit_converter import UnitConverter

                existing_unit = _normalize_unit(existing.get("unit") or unit)
                existing_qty = float(existing.get("quantity") or 0)

                if existing_unit and unit and existing_unit != unit:
                    if UnitConverter.can_convert(unit, existing_unit):
                        qty = UnitConverter.convert(qty, unit, existing_unit)
                        unit = existing_unit
                    elif UnitConverter.can_convert(existing_unit, unit):
                        existing_qty = UnitConverter.convert(existing_qty, existing_unit, unit)
                        existing_unit = unit
                    else:
                        # Different categories; keep the larger quantity to avoid inflation.
                        existing["quantity"] = max(existing_qty, qty)
                        existing["unit"] = existing_unit
                        continue

                existing["quantity"] = float(existing_qty) + float(qty)
                existing["unit"] = existing_unit
            except Exception:
                # Fallback: last write wins (still normalized).
                pantry_dict[key] = {"quantity": qty, "unit": unit}

        logger.info(
            "check_sufficiency inventory uid_suffix=%s pantry_items=%s",
            uid_suffix,
            len(pantry_dict),
        )
        
        # Calculate sufficiency
        result = ServingCalculator.check_sufficiency(
            pantry_items=pantry_dict,
            recipe_ingredients=recipe_ingredients,
            recipe_servings=request.recipe_servings,
            needed_servings=request.servings
        )
        
        # Generate shopping list if missing ingredients
        shopping_list = None
        if result["missing"]:
            shopping_list = ServingCalculator.generate_shopping_list(result["missing"])
        
        msg = (
            "You have enough ingredients."
            if result.get("sufficient")
            else f"Missing {result.get('total_missing', 0)} ingredient(s)."
        )

        logger.info(
            "check_sufficiency result uid_suffix=%s sufficient=%s missing=%s scaling_factor=%s",
            uid_suffix,
            bool(result.get("sufficient")),
            int(result.get("total_missing") or 0),
            float(result.get("scaling_factor") or 0),
        )

        return CheckSufficiencyResponse(
            sufficient=result["sufficient"],
            missing=result["missing"],
            surplus=result["surplus"],
            scaling_factor=result["scaling_factor"],
            total_missing=result["total_missing"],
            total_sufficient=result["total_sufficient"],
            total_ingredients=result["total_ingredients"],
            shopping_list=shopping_list,
            message=msg,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check sufficiency: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check sufficiency: {str(e)}")
        logger.error(f"Failed to remove from pantry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to remove from pantry: {str(e)}")
