"""Inventory endpoints - CRUD operations, normalization, and scanning."""

from __future__ import annotations

from typing import List, Optional
import base64

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form

from app.models.inventory import (
    InventoryItem,
    InventoryItemCreate,
    InventoryItemUpdate,
    NormalizeInventoryRequest,
    NormalizeInventoryResponse,
    ScanIngredientsResponse,
)
from app.core.storage import get_storage
from app.core.orchestrator import normalize_inventory
from app.core.settings import settings
from app.core.llm_client import GoogleClient, get_vision_client
from app.core.settings import settings

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
        # The prompt-pack binding expects INVENTORY. Preserve raw_items for backward compatibility.
        "inventory": req.raw_items,
        "raw_items": req.raw_items,
        "measurement_system": req.measurement_system,
        "output_language": req.output_language,
    }
    return await normalize_inventory(context)


@router.post("/scan", response_model=ScanIngredientsResponse)
async def post_scan_ingredients(
    image: UploadFile = File(..., description="Pantry/fridge photo"),
    storage_hint: Optional[str] = Form(
        None, description="Optional hint: pantry|refrigerator|freezer"
    ),
):
    """Scan an image and return ingredient candidates.

    This endpoint is intentionally lightweight and designed for a scan→confirm UX.
    It returns candidates only; canonical normalization should be done via /inventory/normalize.
    """

    if image.content_type is None or not image.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only image uploads are supported",
        )

    raw = await image.read()
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty image upload",
        )
    if len(raw) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image too large (max 5MB)",
        )

    provider = (settings.llm_provider or "mock").lower()

    # Mock provider: deterministic candidates for local dev.
    if provider == "mock":
        return ScanIngredientsResponse(
            status="ok",
            scanned_items=[
                {"ingredient": "tomato", "quantity_estimate": "4 pcs", "confidence": 0.91, "storage_hint": "refrigerator"},
                {"ingredient": "onion", "quantity_estimate": "2 pcs", "confidence": 0.86, "storage_hint": "pantry"},
                {"ingredient": "eggs", "quantity_estimate": "6 pcs", "confidence": 0.82, "storage_hint": "refrigerator"},
            ],
        )

    if provider != "google":
        return ScanIngredientsResponse(
            status="error",
            scanned_items=[],
            error_message=f"Ingredient scan requires SAVO_LLM_PROVIDER=google (current: {provider})",
        )

    mime_type = image.content_type or "image/jpeg"
    b64 = base64.b64encode(raw).decode("ascii")

    system = (
        "You are an ingredient detector for a cooking app. "
        "Your job is perception only: list visible food/ingredients and common packaged staples. "
        "Do not guess brands, expiry dates, or hidden items. "
        "Return ONLY JSON. No markdown, no prose."
    )
    user = (
        "From the image, return a JSON object with key scanned_items (array). "
        "Each item must have: ingredient (string), quantity_estimate (string|null), confidence (number 0..1), storage_hint (pantry|refrigerator|freezer|null). "
        "Rules: max 30 items; exclude non-food objects; prefer singular canonical ingredient names (e.g., 'tomato', 'milk'). "
        "If unsure, include the ingredient with lower confidence rather than omitting."
    )
    if storage_hint:
        user += f"\nContext hint: storage_hint={storage_hint}."

    try:
        # Use vision provider (Google Gemini Vision by default)
        # Optimized for image understanding and ingredient detection
        client = get_vision_client()
        
        # For Google, use the multimodal generation method
        if isinstance(client, GoogleClient):
            result = await client.generate_json_multimodal(
                system=system,
                user=user,
                inline_images=[{"mimeType": mime_type, "data": b64}],
                max_output_tokens=1024,
                temperature=0.2,
            )
        else:
            # Future: Add OpenAI Vision support here
            raise NotImplementedError(f"Vision provider {settings.vision_provider} not yet implemented for scanning")

        scanned_items = []
        if isinstance(result, dict):
            scanned_items = result.get("scanned_items") or []
        if not isinstance(scanned_items, list):
            scanned_items = []

        return ScanIngredientsResponse(status="ok", scanned_items=scanned_items)
    except Exception as e:
        return ScanIngredientsResponse(status="error", scanned_items=[], error_message=str(e))

