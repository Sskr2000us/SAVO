"""Inventory endpoints - CRUD operations, normalization, and scanning."""

from __future__ import annotations

from typing import List, Optional
import base64
import re
import uuid

from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form, Depends
from pydantic import ValidationError

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
from app.middleware.auth import get_current_user_optional
from app.core.media_storage import upload_inventory_image

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

    def _fallback_normalize(raw_items: list[dict]) -> dict:
        def _slug(text: str) -> str:
            text = (text or "").strip().lower()
            text = re.sub(r"[^a-z0-9\s-]", "", text)
            text = re.sub(r"\s+", " ", text).strip()
            return (text.replace(" ", "-") or "unknown")

        def _parse_qty_unit(quantity_estimate: str | None) -> tuple[float, str]:
            if not quantity_estimate:
                return 1.0, "pcs"
            q = quantity_estimate.strip().lower()
            m = re.search(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+)", q)
            if not m:
                return 1.0, "pcs"
            try:
                qty = float(m.group(1))
            except ValueError:
                qty = 1.0
            unit = m.group(2)
            return max(qty, 0.0), unit

        def _storage(storage_hint: str | None) -> str:
            if storage_hint in ("pantry", "fridge", "freezer"):
                return storage_hint
            return "pantry"

        def _freshness_days(storage: str) -> int:
            if storage == "fridge":
                return 7
            if storage == "freezer":
                return 90
            return 30

        normalized_inventory: list[dict] = []
        for raw in raw_items or []:
            display_name = (raw.get("display_name") or "").strip()
            if not display_name:
                continue

            qty, unit = _parse_qty_unit(raw.get("quantity_estimate"))
            storage_val = _storage(raw.get("storage_hint"))
            canonical_name = re.sub(r"\s+", " ", display_name).strip().lower()
            inv_id = str(uuid.uuid4())
            canonical_id = _slug(canonical_name)
            conf = raw.get("confidence")
            confidence = float(conf) if isinstance(conf, (int, float)) else 0.6

            normalized_inventory.append(
                {
                    "inventory_id": inv_id,
                    "canonical_ingredient_id": canonical_id,
                    "canonical_name": canonical_name,
                    "display_name": display_name,
                    "quantity": qty,
                    "unit": unit,
                    "state": "raw",
                    "storage": storage_val,
                    "freshness_days_remaining": _freshness_days(storage_val),
                    "confidence": max(0.0, min(confidence, 1.0)),
                }
            )

        return {
            "normalized_inventory": normalized_inventory,
            "staples_policy_applied": {
                "enabled": False,
                "staples_included": [],
                "staples_excluded": [],
            },
        }

    try:
        result = await normalize_inventory(context)
        if not isinstance(result, dict):
            return _fallback_normalize(req.raw_items)

        # Validate payload matches response model; if not, fail closed to fallback.
        try:
            validator = getattr(NormalizeInventoryResponse, "model_validate", None)
            if callable(validator):
                return validator(result)
            return NormalizeInventoryResponse.parse_obj(result)
        except ValidationError:
            return _fallback_normalize(req.raw_items)

    except Exception:
        return _fallback_normalize(req.raw_items)


@router.post("/scan", response_model=ScanIngredientsResponse)
async def post_scan_ingredients(
    image: UploadFile = File(..., description="Pantry/fridge photo"),
    storage_hint: Optional[str] = Form(
        None, description="Optional hint: pantry|refrigerator|freezer"
    ),
    user_id: Optional[str] = Depends(get_current_user_optional),
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

    stored_image_ref: Optional[str] = None
    if user_id:
        try:
            stored_image_ref = upload_inventory_image(
                user_id=user_id,
                content=raw,
                content_type=image.content_type,
            )
        except Exception:
            stored_image_ref = None

    # Use vision provider (google or openai)
    provider = (settings.vision_provider or "mock").lower()

    # Mock provider: deterministic candidates for local dev.
    if provider == "mock":
        return ScanIngredientsResponse(
            status="ok",
            image_url=stored_image_ref,
            scanned_items=[
                {"ingredient": "tomato", "quantity_estimate": "4 pcs", "confidence": 0.91, "storage_hint": "fridge"},
                {"ingredient": "onion", "quantity_estimate": "2 pcs", "confidence": 0.88, "storage_hint": "pantry"},
                {"ingredient": "eggs", "quantity_estimate": "6 pcs", "confidence": 0.82, "storage_hint": "fridge"},
            ],
        )

    mime_type = image.content_type or "image/jpeg"
    b64 = base64.b64encode(raw).decode("ascii")

    system = (
        "You are an expert ingredient detector for a cooking app. "
        "Your job: Identify ALL visible food items, ingredients, and packaged products in kitchen photos. "
        "CRITICAL SKILLS REQUIRED:\n"
        "1. READ TEXT on product labels, packages, bottles, jars, and containers\n"
        "2. Identify fresh produce (fruits, vegetables, herbs)\n"
        "3. Recognize pantry staples (oils, sauces, spices, pasta, rice)\n"
        "4. Detect dairy products (milk, cheese, yogurt, butter)\n"
        "5. Spot proteins (meat packages, eggs, tofu)\n"
        "6. Notice condiments and seasonings\n"
        "RULES:\n"
        "- List EVERY food item you can see, even if partially visible\n"
        "- For packaged items: Read the label text to identify the exact product\n"
        "- Use specific names when labels are readable (e.g., 'mozzarella cheese' not just 'cheese')\n"
        "- Include brand names ONLY if clearly visible and helpful for identification\n"
        "- Return ONLY valid JSON. No markdown, no prose, no explanations."
    )
    user = (
        "Analyze this kitchen/pantry photo and return a JSON object with key 'scanned_items' (array). "
        "Each item must have these exact fields:\n"
        "- ingredient (string): The ingredient name (e.g., 'mozzarella cheese', 'olive oil', 'barilla pasta', 'garlic powder')\n"
        "- quantity_estimate (string|null): Estimated quantity if visible (e.g., '1 bottle', '500g package', '1 jar')\n"
        "- confidence (number): Your confidence 0.0-1.0 (be conservative: 0.95+ for clearly readable labels, 0.7-0.9 for recognizable items, 0.5-0.7 for partially visible)\n"
        "- storage_hint (string|null): Where to store: 'pantry', 'fridge', 'freezer', or null if unsure\n\n"
        "IMPORTANT:\n"
        "- Carefully READ all visible text on packages, labels, bottles, and jars\n"
        "- List up to 30 items (prioritize clearly visible items first)\n"
        "- Exclude non-food objects (dishes, utensils, appliances)\n"
        "- If you see text but can't read it clearly, still list the item type with lower confidence\n"
        "- Better to include an item with lower confidence than omit it entirely"
    )
    if storage_hint:
        user += f"\n\nContext: User indicated this photo is from {storage_hint}."

    try:
        # Use vision provider (Google or OpenAI Vision)
        # Google Gemini: Better for fresh produce, general object detection
        # OpenAI GPT-4o: Better for reading text on labels, packaged foods
        client = get_vision_client()
        
        # Both Google and OpenAI support multimodal generation
        result = await client.generate_json_multimodal(
            system=system,
            user=user,
            inline_images=[{"mimeType": mime_type, "data": b64}],
            max_output_tokens=1024,
            temperature=0.2,
        )

        scanned_items = []
        if isinstance(result, dict):
            scanned_items = result.get("scanned_items") or []
        if not isinstance(scanned_items, list):
            scanned_items = []

        return ScanIngredientsResponse(status="ok", scanned_items=scanned_items, image_url=stored_image_ref)
    except Exception as e:
        return ScanIngredientsResponse(status="error", scanned_items=[], image_url=stored_image_ref, error_message=str(e))

