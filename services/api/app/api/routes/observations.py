from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import get_db_client
from app.core.media_storage import to_signed_url
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/observations", tags=["observations"])


@router.get("")
async def list_observations(
    scan_id: Optional[str] = Query(default=None, description="Filter by scan_id"),
    session_id: Optional[str] = Query(default=None, description="Filter by session_id"),
    limit: int = Query(default=200, ge=1, le=500),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return a user's AI observation history (auditable inference).

    Notes:
    - Observations are append-only and separate from pantry truth.
    - `crop_url` is returned as a short-lived signed URL when possible.
    """
    try:
        db = get_db_client()

        q = db.table("scan_observations").select("*").eq("user_id", user_id)

        if scan_id and scan_id.strip():
            q = q.eq("scan_id", scan_id.strip())

        if session_id and session_id.strip():
            q = q.eq("session_id", session_id.strip())

        res = q.order("observed_at", desc=True).limit(int(limit)).execute()
        rows: List[Dict[str, Any]] = res.data or []

        # Sign crop URLs for safe client viewing.
        for row in rows:
            if not isinstance(row, dict):
                continue
            crop = row.get("crop_url")
            if isinstance(crop, str) and crop.strip():
                row["crop_url"] = to_signed_url(crop.strip())

        return {"success": True, "observations": rows, "count": len(rows)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list observations: {e}")
