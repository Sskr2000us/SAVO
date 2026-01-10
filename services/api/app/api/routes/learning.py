from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.database import get_db_client
from app.middleware.auth import get_current_user
from app.api.routes.scanning import _anonymized_item_signature

router = APIRouter(prefix="/learning", tags=["learning"])


class LearningFeedbackIn(BaseModel):
    opt_in: bool = Field(default=False, description="True if user consents to learning")

    source_entity_type: str = Field(default="detected_ingredient")
    source_entity_id: str

    before: Dict[str, Any] = Field(default_factory=dict)
    after: Dict[str, Any] = Field(default_factory=dict)

    confidence: Optional[float] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class LearningDeltaIn(BaseModel):
    scan_id: str
    previous_scan_id: Optional[str] = None



@router.post("/feedback")
async def learning_feedback(
    payload: LearningFeedbackIn,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Story wrapper: /learning/feedback.

    Stores opt-in correction events with before/after snapshots and an anonymized signature.
    If opt_in is false, returns success without storing.

    Note: This endpoint is intentionally best-effort regarding downstream schema differences.
    """
    if not payload.opt_in:
        return {"success": True, "stored": False}

    db = get_db_client()
    now = datetime.now(timezone.utc).isoformat()

    before = payload.before if isinstance(payload.before, dict) else {}
    after = payload.after if isinstance(payload.after, dict) else {}

    signature = None
    try:
        signature = _anonymized_item_signature(user_id, {"id": payload.source_entity_id, **before}, extra=payload.extra)
    except Exception:
        signature = None

    row = {
        "user_id": user_id,
        "feedback_type": "cv_correction",
        "source_entity_type": payload.source_entity_type,
        "source_entity_id": payload.source_entity_id,
        "was_correct": False,
        "confidence_at_decision": payload.confidence,
        "correction_data": {
            "before": before,
            "after": after,
            **({"signature": signature} if signature else {}),
            **(payload.extra if isinstance(payload.extra, dict) else {}),
            "created_at": now,
        },
    }

    try:
        db.table("learning_feedback").insert(row).execute()
        return {"success": True, "stored": True}
    except Exception as e:
        # Operationally succeed but report not stored (e.g., schema constraint mismatch).
        return {"success": True, "stored": False, "warning": f"Failed to store learning event: {e}"}


@router.post("/delta")
async def learning_delta(
    payload: LearningDeltaIn,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Story endpoint: /learning/delta.

    Computes change insights between a scan and its previous scan (or an explicit previous_scan_id).
    Does not store raw frames or images.
    """
    db = get_db_client()

    scan_res = (
        db.table("ingredient_scans")
        .select("id,created_at")
        .eq("id", payload.scan_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    if not scan_res.data:
        return {"success": False, "error": "scan_not_found"}

    scan_row = scan_res.data[0]
    created_at = scan_row.get("created_at")

    prev_scan_id = payload.previous_scan_id
    if not prev_scan_id:
        try:
            prev = (
                db.table("ingredient_scans")
                .select("id")
                .eq("user_id", user_id)
                .lt("created_at", created_at)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            if prev.data and isinstance(prev.data[0], dict):
                prev_scan_id = prev.data[0].get("id")
        except Exception:
            prev_scan_id = None

    cur_dets = (
        db.table("detected_ingredients")
        .select("canonical_name,detected_name,detected_quantity,detected_unit")
        .eq("scan_id", payload.scan_id)
        .eq("user_id", user_id)
        .execute()
    )

    prev_dets = None
    if prev_scan_id:
        prev_dets = (
            db.table("detected_ingredients")
            .select("canonical_name,detected_name,detected_quantity,detected_unit")
            .eq("scan_id", prev_scan_id)
            .eq("user_id", user_id)
            .execute()
        )

    def _key(row: Dict[str, Any]) -> str:
        return ((row.get("canonical_name") or row.get("detected_name") or "") or "").strip().lower()

    cur_map: Dict[str, Dict[str, Any]] = {}
    for r in cur_dets.data or []:
        if not isinstance(r, dict):
            continue
        k = _key(r)
        if k:
            cur_map[k] = r

    prev_map: Dict[str, Dict[str, Any]] = {}
    for r in (prev_dets.data if prev_dets else []) or []:
        if not isinstance(r, dict):
            continue
        k = _key(r)
        if k:
            prev_map[k] = r

    new_items: List[Dict[str, Any]] = []
    changed_items: List[Dict[str, Any]] = []
    removed_items: List[Dict[str, Any]] = []

    for k, r in cur_map.items():
        if k not in prev_map:
            new_items.append({"name": r.get("canonical_name") or r.get("detected_name"), "quantity": r.get("detected_quantity"), "unit": r.get("detected_unit")})
            continue
        p = prev_map[k]
        cq, cu = r.get("detected_quantity"), r.get("detected_unit")
        pq, pu = p.get("detected_quantity"), p.get("detected_unit")
        if cq != pq or (cu or "") != (pu or ""):
            changed_items.append(
                {
                    "name": r.get("canonical_name") or r.get("detected_name"),
                    "before": {"quantity": pq, "unit": pu},
                    "after": {"quantity": cq, "unit": cu},
                }
            )

    for k, r in prev_map.items():
        if k not in cur_map:
            removed_items.append({"name": r.get("canonical_name") or r.get("detected_name"), "quantity": r.get("detected_quantity"), "unit": r.get("detected_unit")})

    return {
        "success": True,
        "scan_id": payload.scan_id,
        "previous_scan_id": prev_scan_id,
        "counts": {"new": len(new_items), "changed": len(changed_items), "removed": len(removed_items)},
        "new": new_items,
        "changed": changed_items,
        "removed": removed_items,
    }
