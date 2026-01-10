from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field

from app.core.database import get_db_client
from app.middleware.auth import get_current_user
from app.core.events import emit_event

router = APIRouter(prefix="/scan", tags=["scan-session"])


class ScanSessionStartIn(BaseModel):
    scan_type: str = Field(default="pantry", description="pantry|fridge|freezer|counter|shopping")
    location_hint: Optional[str] = None


class ScanSessionStartOut(BaseModel):
    success: bool
    session_id: str
    created_at: str
    correlation: Dict[str, Any]


class ScanSessionStatusOut(BaseModel):
    success: bool
    session_id: str
    status: str
    stage: str
    counts: Dict[str, int]
    blocking_issues: list
    updated_at: Optional[str] = None


class ScanSessionEndOut(BaseModel):
    success: bool
    session_id: str
    ended_at: str
    summary: Optional[Dict[str, Any]] = None


@router.post("/session/start", response_model=ScanSessionStartOut)
async def start_scan_session(
    payload: ScanSessionStartIn,
    x_app_version: Optional[str] = Header(default=None, alias="X-App-Version"),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Start a scan session (one pantry scan workflow)."""
    try:
        db = get_db_client()

        session_id = str(uuid4())
        correlation_id = str(uuid4())
        now = datetime.now(timezone.utc).isoformat()

        release_version = None
        try:
            import os

            release_version = (os.getenv("SAVO_RELEASE_VERSION") or os.getenv("SAVO_RELEASE") or "").strip() or None
        except Exception:
            release_version = None

        metadata: Dict[str, Any] = {}
        if x_app_version and x_app_version.strip():
            metadata["app_version"] = x_app_version.strip()
        if release_version:
            metadata["release_version"] = release_version

        row = {
            "id": session_id,
            "user_id": user_id,
            "status": "active",
            "stage": "collecting_frames",
            "scan_type": payload.scan_type,
            "location_hint": payload.location_hint,
            "correlation_id": correlation_id,
            "frames_received": 0,
            "frames_usable": 0,
            "last_quality_issues": [],
            "metadata": metadata,
            "updated_at": now,
        }

        # Best-effort insert; if schema lags, fail loudly here (this endpoint depends on the table).
        db.table("scan_sessions").insert(row).execute()

        emit_event(
            event_type="scan.started",
            user_id=user_id,
            session_id=session_id,
            model_version=None,
            release_version=release_version,
            app_version=(x_app_version or "").strip() or None,
            payload={
                "scan_type": payload.scan_type,
                "location_hint": payload.location_hint,
                "correlation_id": correlation_id,
            },
        )

        return {
            "success": True,
            "session_id": session_id,
            "created_at": now,
            "correlation": {
                "correlation_id": correlation_id,
                "release_version": release_version,
                "app_version": (x_app_version or "").strip() or None,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start scan session: {e}")


@router.get("/session/{session_id}/status", response_model=ScanSessionStatusOut)
async def scan_session_status(
    session_id: str,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return session status: frame counts, stage, and any blocking quality issues."""
    try:
        db = get_db_client()
        res = (
            db.table("scan_sessions")
            .select("id,status,stage,frames_received,frames_usable,last_quality_issues,updated_at")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )

        if not res.data:
            raise HTTPException(status_code=404, detail="Scan session not found")

        row = res.data[0]
        issues = row.get("last_quality_issues")
        if not isinstance(issues, list):
            issues = []

        return {
            "success": True,
            "session_id": session_id,
            "status": (row.get("status") or "unknown"),
            "stage": (row.get("stage") or "unknown"),
            "counts": {
                "frames_received": int(row.get("frames_received") or 0),
                "frames_usable": int(row.get("frames_usable") or 0),
            },
            "blocking_issues": issues,
            "updated_at": row.get("updated_at"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read scan session: {e}")


@router.post("/session/{session_id}/end", response_model=ScanSessionEndOut)
async def end_scan_session(
    session_id: str,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """End a scan session."""
    try:
        db = get_db_client()
        now = datetime.now(timezone.utc).isoformat()

        # Ensure it exists for the user.
        res = (
            db.table("scan_sessions")
            .select("id,created_at,status,stage,frames_received,frames_usable,last_quality_issues,correlation_id,metadata")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not res.data:
            raise HTTPException(status_code=404, detail="Scan session not found")

        row = res.data[0] if isinstance(res.data[0], dict) else {}

        db.table("scan_sessions").update(
            {
                "status": "ended",
                "stage": "ended",
                "updated_at": now,
            }
        ).eq("id", session_id).eq("user_id", user_id).execute()

        md = row.get("metadata")
        if not isinstance(md, dict):
            md = {}
        md = dict(md)

        issues = row.get("last_quality_issues")
        if not isinstance(issues, list):
            issues = []

        summary = {
            "status": "ended",
            "stage": "ended",
            "counts": {
                "frames_received": int(row.get("frames_received") or 0),
                "frames_usable": int(row.get("frames_usable") or 0),
            },
            "blocking_issues": issues,
            "correlation_id": row.get("correlation_id"),
            "last_scan_id": md.get("last_scan_id"),
        }

        # Emit scan.completed once per session.
        try:
            emitted = md.get("events_emitted")
            if not isinstance(emitted, dict):
                emitted = {}
            if not emitted.get("scan_completed"):
                duration_s = None
                try:
                    created_at = row.get("created_at")
                    if created_at:
                        from datetime import datetime

                        start_dt = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
                        end_dt = datetime.fromisoformat(str(now).replace("Z", "+00:00"))
                        duration_s = max(0.0, (end_dt - start_dt).total_seconds())
                except Exception:
                    duration_s = None

                emit_event(
                    event_type="scan.completed",
                    user_id=user_id,
                    session_id=session_id,
                    model_version=None,
                    release_version=(md.get("release_version") or None),
                    app_version=(md.get("app_version") or None),
                    payload={
                        "duration_s": duration_s,
                        "counts": summary.get("counts"),
                        "blocking_issues": issues,
                        "correlation_id": row.get("correlation_id"),
                        "last_scan_id": md.get("last_scan_id"),
                    },
                )
                emitted["scan_completed"] = True
                md["events_emitted"] = emitted
                db.table("scan_sessions").update({"metadata": md}).eq("id", session_id).eq("user_id", user_id).execute()
        except Exception:
            pass

        return {"success": True, "session_id": session_id, "ended_at": now, "summary": summary}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to end scan session: {e}")
