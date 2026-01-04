"""
Inventory Management API Routes with Database Integration
Handles inventory CRUD, low stock alerts, and automatic deduction
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import date, datetime

from app.core.database import (
    get_inventory,
    get_inventory_by_category,
    add_inventory_item,
    update_inventory_item,
    delete_inventory_item,
    get_low_stock_items,
    get_expiring_items,
    deduct_inventory_for_recipe
)
from app.middleware.auth import get_current_user

router = APIRouter()  # Remove duplicate prefix - already set in main router


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class InventoryItemCreate(BaseModel):
    """Request model for adding inventory item"""
    canonical_name: str = Field(..., description="Standardized ingredient name")
    display_name: str = Field(..., description="User-friendly display name")
    category: Optional[str] = Field(None, description="vegetables, dairy, meat, etc")
    
    quantity: float = Field(..., gt=0, description="Quantity")
    unit: str = Field(..., description="Unit of measurement")
    
    storage_location: str = Field(default="pantry", description="pantry|fridge|freezer|counter")
    item_state: str = Field(default="raw", description="raw|cooked|prepared")
    
    purchase_date: Optional[date] = None
    expiry_date: Optional[date] = None
    low_stock_threshold: float = Field(default=1.0, description="Alert when quantity <= this")
    
    source: str = Field(default="manual", description="manual|scan|import")
    scan_confidence: Optional[float] = Field(None, ge=0, le=1)
    
    # Optional packaged-good metadata (barcode lookups)
    barcode: Optional[str] = None
    product_name: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    package_size_text: Optional[str] = None

    notes: Optional[str] = None


class InventoryItemUpdate(BaseModel):
    """Request model for updating inventory item"""
    canonical_name: Optional[str] = None
    display_name: Optional[str] = None
    category: Optional[str] = None
    
    quantity: Optional[float] = Field(None, gt=0)
    unit: Optional[str] = None
    
    storage_location: Optional[str] = None
    item_state: Optional[str] = None
    
    purchase_date: Optional[date] = None
    expiry_date: Optional[date] = None
    low_stock_threshold: Optional[float] = None
    
    # Optional packaged-good metadata
    barcode: Optional[str] = None
    product_name: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None
    package_size_text: Optional[str] = None

    notes: Optional[str] = None


class InventoryDeductionRequest(BaseModel):
    """Request model for deducting inventory after recipe selection"""
    meal_plan_id: str = Field(..., description="Meal plan ID")
    ingredients: List[dict] = Field(..., description="List of {name, quantity, unit}")


# ============================================================================
# INVENTORY CRUD ENDPOINTS
# ============================================================================

@router.get("/items")
async def list_inventory(
    user_id: str = Depends(get_current_user),
    low_stock_only: bool = False,
    category: Optional[str] = None,
    include_inactive: bool = False,
):
    """
    Get user's inventory items.
    
    Query Parameters:
    - low_stock_only: If true, return only items below threshold
    - category: Filter by category (vegetables, dairy, etc)
    """
    try:
        if category:
            items = await get_inventory_by_category(user_id, category, include_inactive=include_inactive)
        else:
            items = await get_inventory(
                user_id,
                include_low_stock_only=low_stock_only,
                include_inactive=include_inactive,
            )
        
        return {
            "count": len(items),
            "items": items
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/items")
async def add_item(
    item: InventoryItemCreate,
    user_id: str = Depends(get_current_user)
):
    """
    Add new item to inventory.
    Low stock status is automatically calculated.
    """
    try:
        item_data = item.model_dump()
        
        # Convert dates to ISO format for database
        if item_data.get("purchase_date"):
            item_data["purchase_date"] = item_data["purchase_date"].isoformat()
        if item_data.get("expiry_date"):
            item_data["expiry_date"] = item_data["expiry_date"].isoformat()
        
        created_item = await add_inventory_item(user_id, item_data)
        
        return {
            "success": True,
            "message": "Item added to inventory",
            "item": created_item
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/items/{item_id}")
async def update_item(
    item_id: str,
    item: InventoryItemUpdate,
    user_id: str = Depends(get_current_user)
):
    """
    Update existing inventory item.
    Only provided fields will be updated.
    Low stock status is automatically recalculated.
    """
    try:
        # Verify item belongs to user
        user_items = await get_inventory(user_id)
        item_ids = [i["id"] for i in user_items]
        
        if item_id not in item_ids:
            raise HTTPException(
                status_code=404,
                detail="Item not found or access denied"
            )
        
        item_data = item.model_dump(exclude_unset=True)
        if not item_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Convert dates to ISO format
        if item_data.get("purchase_date"):
            item_data["purchase_date"] = item_data["purchase_date"].isoformat()
        if item_data.get("expiry_date"):
            item_data["expiry_date"] = item_data["expiry_date"].isoformat()
        
        updated_item = await update_inventory_item(item_id, item_data)
        
        return {
            "success": True,
            "message": "Item updated successfully",
            "item": updated_item
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/items/{item_id}")
async def remove_item(
    item_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Remove item from inventory.
    """
    try:
        # Verify item belongs to user
        user_items = await get_inventory(user_id)
        item_ids = [i["id"] for i in user_items]
        
        if item_id not in item_ids:
            raise HTTPException(
                status_code=404,
                detail="Item not found or access denied"
            )
        
        await delete_inventory_item(item_id)
        
        return {
            "success": True,
            "message": "Item removed from inventory"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SMART INVENTORY FEATURES
# ============================================================================

@router.get("/alerts/low-stock")
async def get_low_stock_alerts(
    user_id: str = Depends(get_current_user)
):
    """
    Get items that are running low (quantity <= threshold).
    Sorted by quantity ascending (most urgent first).
    """
    try:
        items = await get_low_stock_items(user_id)
        
        return {
            "alert_count": len(items),
            "items": items,
            "message": f"{len(items)} item(s) running low" if items else "All items well stocked"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts/expiring")
async def get_expiring_alerts(
    user_id: str = Depends(get_current_user),
    days: int = 3
):
    """
    Get items expiring within specified days.
    Sorted by expiry date (most urgent first).
    
    Query Parameters:
    - days: Number of days to look ahead (default 3)
    """
    try:
        if days < 1 or days > 30:
            raise HTTPException(
                status_code=400,
                detail="Days must be between 1 and 30"
            )
        
        items = await get_expiring_items(user_id, days)
        
        return {
            "alert_count": len(items),
            "items": items,
            "message": f"{len(items)} item(s) expiring within {days} days" if items else f"No items expiring within {days} days"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
async def get_inventory_summary(
    user_id: str = Depends(get_current_user)
):
    """
    Get comprehensive inventory summary with all alerts.
    """
    try:
        # Get all data in parallel
        all_items = await get_inventory(user_id)
        low_stock = await get_low_stock_items(user_id)
        expiring = await get_expiring_items(user_id, days=3)
        
        # Calculate category breakdown
        categories = {}
        for item in all_items:
            cat = item.get("category", "uncategorized")
            if cat not in categories:
                categories[cat] = {"count": 0, "items": []}
            categories[cat]["count"] += 1
            categories[cat]["items"].append(item["display_name"])
        
        return {
            "total_items": len(all_items),
            "total_unique_ingredients": len(set(i["canonical_name"] for i in all_items)),
            "categories": categories,
            "alerts": {
                "low_stock": {
                    "count": len(low_stock),
                    "items": low_stock
                },
                "expiring_soon": {
                    "count": len(expiring),
                    "items": expiring
                }
            },
            "storage_breakdown": {
                "pantry": len([i for i in all_items if i["storage_location"] == "pantry"]),
                "fridge": len([i for i in all_items if i["storage_location"] == "fridge"]),
                "freezer": len([i for i in all_items if i["storage_location"] == "freezer"]),
                "counter": len([i for i in all_items if i["storage_location"] == "counter"])
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AUTOMATIC INVENTORY DEDUCTION
# ============================================================================

@router.post("/deduct")
async def deduct_for_recipe(
    request: InventoryDeductionRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Automatically deduct inventory after user selects a recipe.
    
    This endpoint:
    1. Checks if sufficient inventory exists
    2. Deducts the required quantities
    3. Records usage in inventory_usage table
    4. Updates last_used_at timestamps
    5. Triggers low stock alerts if needed
    
    Request body example:
    {
        "meal_plan_id": "uuid-here",
        "ingredients": [
            {"name": "tomato", "quantity": 3, "unit": "pcs"},
            {"name": "pasta", "quantity": 200, "unit": "g"}
        ]
    }
    
    Response includes:
    - success: bool
    - message: str
    - insufficient_items: list (empty if all items available)
    """
    try:
        result = await deduct_inventory_for_recipe(
            user_id=user_id,
            meal_plan_id=request.meal_plan_id,
            ingredients=request.ingredients
        )
        
        if not result["success"]:
            return {
                "success": False,
                "message": result["message"],
                "insufficient_items": result["insufficient_items"],
                "recommendation": "Add missing items to inventory or choose another recipe"
            }
        
        # Check for new low stock items after deduction
        low_stock = await get_low_stock_items(user_id)
        
        return {
            "success": True,
            "message": "Inventory deducted successfully",
            "ingredients_used": len(request.ingredients),
            "low_stock_alerts": {
                "count": len(low_stock),
                "items": low_stock
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/manual-adjustment")
async def manual_inventory_adjustment(
    item_id: str,
    quantity_change: float,
    reason: str = "manual_adjustment",
    user_id: str = Depends(get_current_user)
):
    """
    Manually adjust inventory quantity (for corrections, waste, etc).
    
    Query Parameters:
    - item_id: Inventory item ID
    - quantity_change: Amount to add (positive) or remove (negative)
    - reason: Reason for adjustment (manual_adjustment, expired, discarded, etc)
    """
    try:
        # Get current item
        user_items = await get_inventory(user_id)
        item = next((i for i in user_items if i["id"] == item_id), None)
        
        if not item:
            raise HTTPException(
                status_code=404,
                detail="Item not found or access denied"
            )
        
        # Calculate new quantity
        new_quantity = item["quantity"] + quantity_change
        
        if new_quantity < 0:
            raise HTTPException(
                status_code=400,
                detail=f"Adjustment would result in negative quantity ({new_quantity})"
            )
        
        # Update item
        updated_item = await update_inventory_item(item_id, {"quantity": new_quantity})
        
        return {
            "success": True,
            "message": f"Quantity adjusted by {quantity_change:+.2f} {item['unit']}",
            "previous_quantity": item["quantity"],
            "new_quantity": new_quantity,
            "item": updated_item
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
