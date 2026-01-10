from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from PIL import Image
import io

from app.core.database import get_db_client
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/scan", tags=["scan-frames"])


ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/jpg", "image/png"}
MAX_FRAMES_PER_SESSION = 20


def _assess_image_quality_simple(image_bytes: bytes) -> Dict[str, Any]:
    """Lightweight quality scoring (mirrors scanning.py intent without importing it)."""
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        # downsample for speed
        small = img.resize((128, 128))
        px = list(small.getdata())
        mean = sum(px) / max(1, len(px))
        # crude contrast proxy
        var = sum((p - mean) ** 2 for p in px) / max(1, len(px))

        issues: List[str] = []
        if mean < 50:
            issues.append("too_dark")
        if mean > 220:
            issues.append("too_bright")
        if var < 200:
            issues.append("too_blurry")

        return {
            "ok": len(issues) == 0,
            "issues": issues,
            "metrics": {"brightness": round(mean, 2), "contrast_var": round(var, 2)},
        }
    except Exception:
        return {"ok": False, "issues": ["unreadable"], "metrics": {}}


def _ahash(image_bytes: bytes) -> Optional[str]:
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("L").resize((8, 8))
        px = list(img.getdata())
        avg = sum(px) / 64.0
        bits = 0
        for i, p in enumerate(px):
            if p >= avg:
                bits |= (1 << i)
        return f"{bits:016x}"
    except Exception:
        return None


def _update_session(db, user_id: str, session_id: str, patch: Dict[str, Any]) -> None:
    try:
        db.table("scan_sessions").update(patch).eq("id", session_id).eq("user_id", user_id).execute()
    except Exception:
        return


def _get_session_row(db, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
    try:
        res = (
            db.table("scan_sessions")
            .select("id,status,stage,frames_received,frames_usable,correlation_id,last_quality_issues,metadata")
            .eq("id", session_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not res.data:
            return None
        row = res.data[0]
        if not isinstance(row, dict):
            return None
        return row
    except Exception:
        return None


@router.post("/frame/upload")
async def upload_frame(
    image: UploadFile = File(...),
    session_id: str = Form(...),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Accept a single frame, quality-score it, and update session counters.

    This does NOT persist the frame bytes (privacy).
    """
    try:
        if image.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(status_code=400, detail="Invalid image format. Use JPEG or PNG.")

        data = await image.read()
        if not data:
            raise HTTPException(status_code=400, detail="Empty image")
        if len(data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large. Maximum 10MB.")

        db = get_db_client()
        now = datetime.now(timezone.utc).isoformat()

        # Validate session and enforce terminal/limit behavior.
        sess_row = _get_session_row(db, user_id, session_id)
        if not sess_row:
            raise HTTPException(status_code=404, detail="Scan session not found")

        if (sess_row.get("status") or "").lower() != "active":
            raise HTTPException(status_code=409, detail="Scan session is not active")

        current_received = int(sess_row.get("frames_received") or 0)
        if current_received >= MAX_FRAMES_PER_SESSION:
            raise HTTPException(status_code=400, detail=f"Frame limit reached (max {MAX_FRAMES_PER_SESSION} per session)")

        quality = _assess_image_quality_simple(data)
        is_quality_ok = bool(quality.get("ok"))
        issues = list(quality.get("issues") or [])

        frame_hash = _ahash(data)
        md = sess_row.get("metadata")
        if not isinstance(md, dict):
            md = {}
        md = dict(md)
        hashes = md.get("frame_hashes")
        if not isinstance(hashes, list):
            hashes = []
        hashes_norm = [h for h in hashes if isinstance(h, str) and h]
        is_duplicate = bool(frame_hash and frame_hash in set(hashes_norm))
        if is_duplicate:
            issues.append("duplicate")

        usable_for_vision = bool(is_quality_ok and not is_duplicate)

        # Bump counters best-effort.
        try:
            fr = current_received + 1
            fu = int(sess_row.get("frames_usable") or 0) + (1 if usable_for_vision else 0)
            md["last_frame_metrics"] = quality.get("metrics") or {}
            if frame_hash and not is_duplicate:
                hashes_norm.append(frame_hash)
                hashes_norm = hashes_norm[-50:]
                md["frame_hashes"] = hashes_norm

            _update_session(
                db,
                user_id,
                session_id,
                {
                    "frames_received": fr,
                    "frames_usable": fu,
                    "stage": "collecting_frames",
                    "last_quality_issues": issues,
                    "metadata": md,
                    "updated_at": now,
                },
            )
        except Exception:
            pass

        return {
            "success": True,
            "session_id": session_id,
            "deduped_count": 1 if is_duplicate else 0,
            "frame": {
                "usable": usable_for_vision,
                "issues": issues,
                "metrics": quality.get("metrics") or {},
                "ahash": frame_hash,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Frame upload failed: {e}")


@router.post("/frame/sample")
async def sample_frames(
    images: List[UploadFile] = File(...),
    session_id: Optional[str] = Form(default=None),
    max_samples: int = Form(default=8),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Given a list of frames, return indices of usable, deduped samples.

    This does NOT persist the frame bytes.
    """
    try:
        max_samples = max(1, min(int(max_samples), 20))
        if not images:
            raise HTTPException(status_code=400, detail="No images provided")

        if len(images) > 20:
            raise HTTPException(status_code=400, detail="Too many images. Maximum 20 per request.")

        # Optional session enforcement (terminal state + max total frames).
        db = None
        sess_row = None
        if session_id:
            db = get_db_client()
            sess_row = _get_session_row(db, user_id, session_id)
            if not sess_row:
                raise HTTPException(status_code=404, detail="Scan session not found")
            if (sess_row.get("status") or "").lower() != "active":
                raise HTTPException(status_code=409, detail="Scan session is not active")
            current_received = int(sess_row.get("frames_received") or 0)
            if current_received + len(images) > MAX_FRAMES_PER_SESSION:
                raise HTTPException(status_code=400, detail=f"Frame limit exceeded (max {MAX_FRAMES_PER_SESSION} per session)")

        usable: List[Dict[str, Any]] = []
        issues_union: set[str] = set()
        frame_reports: List[Dict[str, Any]] = []

        # Track duplicates across this request.
        request_seen: set[str] = set()

        # Track duplicates vs session history.
        session_hashes: set[str] = set()
        sess_md: Dict[str, Any] = {}
        if sess_row:
            sess_md = sess_row.get("metadata") if isinstance(sess_row.get("metadata"), dict) else {}
            prev = sess_md.get("frame_hashes")
            if isinstance(prev, list):
                session_hashes = {h for h in prev if isinstance(h, str) and h}

        for idx, img in enumerate(images):
            if img.content_type not in ALLOWED_IMAGE_TYPES:
                raise HTTPException(status_code=400, detail="Invalid image format. Use JPEG or PNG.")
            data = await img.read()
            if not data:
                raise HTTPException(status_code=400, detail="Empty image")

            q = _assess_image_quality_simple(data)
            h = _ahash(data)

            issues = list(q.get("issues") or [])
            is_quality_ok = bool(q.get("ok"))

            is_dup = False
            if h:
                if h in request_seen or h in session_hashes:
                    is_dup = True
                    issues.append("duplicate")
                request_seen.add(h)

            usable_for_vision = bool(is_quality_ok and not is_dup)
            if not is_quality_ok:
                for it in issues:
                    if isinstance(it, str) and it:
                        issues_union.add(it)
            if is_dup:
                issues_union.add("duplicate")

            frame_reports.append(
                {
                    "idx": idx,
                    "usable": usable_for_vision,
                    "issues": issues,
                    "metrics": q.get("metrics") or {},
                    "ahash": h,
                }
            )

            if usable_for_vision:
                usable.append({"idx": idx, "ahash": h})

        # Deduplicate by ahash.
        seen = set()
        deduped: List[int] = []
        for u in usable:
            h = u.get("ahash")
            key = h or f"idx:{u['idx']}"
            if key in seen:
                continue
            seen.add(key)
            deduped.append(int(u["idx"]))

        sampled = deduped[:max_samples]
        deduped_count = max(0, len(usable) - len(deduped))

        # Best-effort: update session counts.
        if session_id:
            try:
                now = datetime.now(timezone.utc).isoformat()
                if db is None:
                    db = get_db_client()
                fr0 = int(sess_row.get("frames_received") or 0) if sess_row else 0
                fu0 = int(sess_row.get("frames_usable") or 0) if sess_row else 0
                fr = fr0 + int(len(images))
                fu = fu0 + int(len(deduped))

                # Merge new frame hashes for dedupe across requests.
                md = sess_md if isinstance(sess_md, dict) else {}
                md = dict(md)
                prev_list = md.get("frame_hashes")
                prev_norm = [h for h in (prev_list if isinstance(prev_list, list) else []) if isinstance(h, str) and h]
                for rep in frame_reports:
                    h = rep.get("ahash")
                    if rep.get("usable") and isinstance(h, str) and h and h not in prev_norm:
                        prev_norm.append(h)
                md["frame_hashes"] = prev_norm[-50:]
                md["last_frame_metrics"] = (frame_reports[-1].get("metrics") if frame_reports else {}) or {}

                _update_session(
                    db,
                    user_id,
                    session_id,
                    {
                        "frames_received": fr,
                        "frames_usable": fu,
                        "stage": "collecting_frames",
                        "last_quality_issues": sorted(list(issues_union)),
                        "metadata": md,
                        "updated_at": now,
                    },
                )
            except Exception:
                pass

        return {
            "success": True,
            "session_id": session_id,
            "counts": {
                "received": len(images),
                "usable": len(deduped),
                "sampled": len(sampled),
            },
            "sample_indices": sampled,
            "deduped_count": deduped_count,
            "blocking_issues": sorted(list(issues_union)),
            "frames": frame_reports,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Frame sampling failed: {e}")
