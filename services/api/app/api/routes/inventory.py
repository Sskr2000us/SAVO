"""
Inventory endpoints - CRUD operations and normalization
"""
from typing import List
from fastapi import APIRouter, HTTPException, status

from app.models.inventory import (
    InventoryItem,
    InventoryItemCreate,
    InventoryItemUpdate,
    NormalizeInventoryRequest,
    NormalizeInventoryResponse,
)
from app.core.storage import get_storage
from app.core.orchestrator import normalize_inventory

router = APIRouter()


@router.get("", response_model=List[InventoryItem])
async def list_inventory():
    """List all inventory items"""
    storage = get_storage()
    return storage.list_inventory()


@router.get("/{inventory_id}", response_model=InventoryItem)
async def get_inventory_item(inventory_id: str):
    """Get single inventory item"""
    storage = get_storage()
    item = storage.get_inventory_item(inventory_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item {inventory_id} not found"
        )
    return item


@router.post("", response_model=InventoryItem, status_code=status.HTTP_201_CREATED)
async def create_inventory_item(item: InventoryItemCreate):
    """Create new inventory item"""
    storage = get_storage()
    return storage.create_inventory_item(item)


@router.put("/{inventory_id}", response_model=InventoryItem)
async def update_inventory_item(inventory_id: str, updates: InventoryItemUpdate):
    """Update existing inventory item"""
    storage = get_storage()
    updated = storage.update_inventory_item(inventory_id, updates)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item {inventory_id} not found"
        )
    return updated


@router.delete("/{inventory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_inventory_item(inventory_id: str):
    """Delete inventory item"""
    storage = get_storage()
    deleted = storage.delete_inventory_item(inventory_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Inventory item {inventory_id} not found"
        )


@router.post("/normalize", response_model=NormalizeInventoryResponse)
async def post_normalize(req: NormalizeInventoryRequest):
    """Normalize raw inventory items using LLM"""
    context = {
        "raw_items": req.raw_items,
        "measurement_system": req.measurement_system,
        "output_language": req.output_language,
    }
    return await normalize_inventory(context)

