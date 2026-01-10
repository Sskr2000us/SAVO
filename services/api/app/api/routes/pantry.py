from __future__ import annotations

from typing import Any, Dict, List, Optional

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user
from app.api.routes.scanning import ConfirmIngredientsRequest, confirm_ingredients, get_user_pantry
from app.core.database import get_db_client
from app.core.events import emit_event
from app.core.schema_migration import dual_write_enabled
from app.core.migration_telemetry import emit_migration_incident

router = APIRouter(prefix="/pantry", tags=["pantry"])


class PantryStatusUpdateIn(BaseModel):
    pantry_status: Optional[str] = Field(default=None, description="active|consumed|discarded")
    storage_location: Optional[str] = Field(default=None, description="pantry|fridge|freezer|counter")
    quantity: Optional[float] = None
    unit: Optional[str] = None
    notes: Optional[str] = None


class ConfirmItem(BaseModel):
    detected_id: str
    signal: str = Field(description="confirm|edit|delete")
    confirmed_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None

    barcode: Optional[str] = None
    barcode_name_hint: Optional[str] = None
    barcode_quantity_hint: Optional[float] = None
    barcode_unit_hint: Optional[str] = None


class PantryConfirmIn(BaseModel):
    scan_id: str
    items: List[ConfirmItem]


@router.post("/confirm")
async def pantry_confirm(
    payload: PantryConfirmIn,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Story wrapper: /pantry/confirm.

    Maps story signals confirm/edit/delete onto the existing scan confirmation workflow,
    then returns updated pantry state.
    """
    signal_map = {
        "confirm": "confirmed",
        "edit": "modified",
        "delete": "rejected",
    }

    confirmations: List[Dict[str, Any]] = []
    for it in payload.items or []:
        action = signal_map.get((it.signal or "").strip().lower())
        if not action:
            raise HTTPException(status_code=400, detail="Invalid signal; use confirm, edit, or delete")

        row: Dict[str, Any] = {
            "detected_id": it.detected_id,
            "action": action,
        }
        if action == "modified":
            if it.confirmed_name:
                row["confirmed_name"] = it.confirmed_name
            if it.quantity is not None:
                row["quantity"] = it.quantity
            if it.unit is not None:
                row["unit"] = it.unit

        # Optional barcode context for learning/audit.
        if it.barcode:
            row["barcode"] = it.barcode
        if it.barcode_name_hint:
            row["barcode_name_hint"] = it.barcode_name_hint
        if it.barcode_quantity_hint is not None:
            row["barcode_quantity_hint"] = it.barcode_quantity_hint
        if it.barcode_unit_hint:
            row["barcode_unit_hint"] = it.barcode_unit_hint

        confirmations.append(row)

    # Delegate to existing confirmation endpoint.
    confirm_req = ConfirmIngredientsRequest(scan_id=payload.scan_id, confirmations=confirmations)
    result = await confirm_ingredients(confirm_req, user_id=user_id)

    pantry_state = await get_user_pantry(background_tasks=BackgroundTasks(), user_id=user_id)

    return {
        "success": True,
        "scan_id": payload.scan_id,
        "result": result,
        "pantry": pantry_state.get("pantry"),
        "total_items": pantry_state.get("total_items"),
    }


@router.patch("/items/{item_id}")
async def pantry_update_item(
    item_id: str,
    payload: PantryStatusUpdateIn,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Explicit user-driven update to the pantry truth store.

    Updates `inventory_items` (single source of truth) and stamps last_confirmed_at.
    Supported changes:
    - pantry_status: active|consumed|discarded
    - storage_location: pantry|fridge|freezer|counter
    - quantity/unit, notes
    """
    db = get_db_client()
    now_iso = datetime.now(timezone.utc).isoformat()

    allowed_status = {"active", "consumed", "discarded"}
    allowed_locations = {"pantry", "fridge", "freezer", "counter"}

    # Load existing item and enforce ownership.
    existing = (
        db.table("inventory_items")
        .select("*")
        .eq("id", item_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Pantry item not found")
    item = existing.data[0]

    update: Dict[str, Any] = {"last_confirmed_at": now_iso}

    if payload.pantry_status is not None:
        st = (payload.pantry_status or "").strip().lower()
        if st not in allowed_status:
            raise HTTPException(status_code=400, detail="Invalid pantry_status")
        update["pantry_status"] = st
        if st != (str(item.get("pantry_status") or "active").strip().lower()):
            update["last_status_changed_at"] = now_iso
            # When user marks consumed/discarded, it should no longer be current.
            if st in {"consumed", "discarded"}:
                update["is_current"] = False
            else:
                update["is_current"] = True

    if payload.storage_location is not None:
        loc = (payload.storage_location or "").strip().lower()
        if loc not in allowed_locations:
            raise HTTPException(status_code=400, detail="Invalid storage_location")
        update["storage_location"] = loc

    if payload.quantity is not None:
        if payload.quantity < 0:
            raise HTTPException(status_code=400, detail="quantity must be >= 0")
        update["quantity"] = payload.quantity
    if payload.unit is not None:
        update["unit"] = (payload.unit or "").strip().lower() or item.get("unit")
    if payload.notes is not None:
        update["notes"] = payload.notes

    # No-op guard: require at least one explicit change besides last_confirmed_at.
    if set(update.keys()) == {"last_confirmed_at"}:
        raise HTTPException(status_code=400, detail="No fields to update")

    res = db.table("inventory_items").update(update).eq("id", item_id).eq("user_id", user_id).execute()
    updated_item = (res.data[0] if res.data else None)

    if dual_write_enabled():
        try:
            db.table("inventory_items_v2").update(update).eq("id", item_id).eq("user_id", user_id).execute()
        except Exception:
            try:
                emit_migration_incident(
                    user_id=user_id,
                    correlation_id=item_id,
                    incident_type="v2_write_failed",
                    operation="update",
                    v2_target="public.inventory_items_v2",
                    error="inventory_items_v2 update failed",
                    entity_id=item_id,
                    payload={"endpoint": "PATCH /pantry/items/{item_id}"},
                )
            except Exception:
                pass
            pass

    try:
        emit_event(
            event_type="pantry.item_updated",
            event_ts=now_iso,
            user_id=user_id,
            payload={
                "inventory_item_id": item_id,
                "changes": update,
                "before": {
                    "pantry_status": item.get("pantry_status"),
                    "storage_location": item.get("storage_location"),
                    "quantity": item.get("quantity"),
                    "unit": item.get("unit"),
                },
            },
        )
    except Exception:
        pass

    return {"success": True, "item": updated_item}
