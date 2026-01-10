from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.database import get_db_client
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("")
async def list_events(
    limit: int = Query(default=100, ge=1, le=500),
    event_type: Optional[str] = Query(default=None),
    session_id: Optional[str] = Query(default=None),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return a user's event history for auditability.

    This is the primary mechanism to satisfy "full history of what changed and why".
    Events are append-only in the DB; this endpoint is read-only.
    """
    try:
        db = get_db_client()

        q = (
            db.table("event_log")
            .select("id,event_type,event_ts,user_id,household_id,session_id,model_version,release_version,app_version,payload")
            .eq("user_id", user_id)
        )

        if event_type and event_type.strip():
            q = q.eq("event_type", event_type.strip())

        if session_id and session_id.strip():
            q = q.eq("session_id", session_id.strip())

        res = q.order("event_ts", desc=True).limit(int(limit)).execute()
        events: List[Dict[str, Any]] = res.data or []

        return {"success": True, "events": events, "count": len(events)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list events: {e}")
