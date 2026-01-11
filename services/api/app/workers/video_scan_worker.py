from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.database import get_db_client
from app.core.media_storage import to_signed_url
from app.api.routes.video_scanning import _process_video_scan

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _worker_id() -> str:
    host = None
    try:
        host = socket.gethostname()
    except Exception:
        host = None
    return f"video-scan-worker@{host or 'unknown'}"


def _compute_max_frames(duration_seconds: Optional[int], requested: Optional[int]) -> int:
    try:
        mf = int(requested) if requested is not None else 12
    except Exception:
        mf = 12
    mf = min(max(1, mf), 20)
    if duration_seconds is not None:
        try:
            ds = int(duration_seconds)
        except Exception:
            ds = None
        if ds is not None and ds >= 25:
            mf = min(mf, 12)
    return mf


async def _download_video_bytes(video_ref: str) -> bytes:
    url = to_signed_url(video_ref, expires_in=3600)
    if not url or not isinstance(url, str):
        raise ValueError("Missing video_ref")

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        res = await client.get(url)
    if res.status_code != 200:
        raise ValueError(f"Failed to download video: HTTP {res.status_code}")
    return res.content


def _get_next_job(db) -> Optional[Dict[str, Any]]:
    # 1) Prefer pending jobs
    try:
        pending = (
            db.table("scan_jobs")
            .select("*")
            .eq("job_type", "video_scan")
            .eq("status", "pending")
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )
        if pending.data:
            return pending.data[0]
    except Exception:
        pass

    # 2) Reclaim stale running jobs
    stale_seconds = int(os.getenv("SAVO_VIDEO_SCAN_JOB_STALE_SECONDS", "600") or 600)
    stale_before = (datetime.utcnow() - timedelta(seconds=stale_seconds)).isoformat()
    try:
        stale = (
            db.table("scan_jobs")
            .select("*")
            .eq("job_type", "video_scan")
            .eq("status", "running")
            .lt("locked_at", stale_before)
            .order("locked_at", desc=False)
            .limit(1)
            .execute()
        )
        if stale.data:
            return stale.data[0]
    except Exception:
        pass

    return None


def _claim_job(db, job: Dict[str, Any], worker_id: str) -> Tuple[bool, int]:
    job_id = str(job.get("id") or "").strip()
    if not job_id:
        return False, 0
    attempts = 0
    try:
        attempts = int(job.get("attempts") or 0) + 1
    except Exception:
        attempts = 1

    try:
        res = (
            db.table("scan_jobs")
            .update(
                {
                    "status": "running",
                    "locked_at": _now_iso(),
                    "locked_by": worker_id,
                    "attempts": attempts,
                    "updated_at": _now_iso(),
                }
            )
            .eq("id", job_id)
            .execute()
        )
        # Best-effort: assume success if no exception.
        _ = res
        return True, attempts
    except Exception as e:
        logger.warning(f"Failed to claim job {job_id}: {e}")
        return False, attempts


async def _run_one_job() -> bool:
    db = get_db_client()
    worker_id = _worker_id()

    job = _get_next_job(db)
    if not job:
        return False

    scan_id = str(job.get("scan_id") or "").strip()
    user_id = str(job.get("user_id") or "").strip()
    if not scan_id or not user_id:
        try:
            db.table("scan_jobs").update(
                {"status": "failed", "last_error": "Missing scan_id/user_id", "updated_at": _now_iso()}
            ).eq("id", str(job.get("id"))).execute()
        except Exception:
            pass
        return True

    claimed, _attempts = _claim_job(db, job, worker_id)
    if not claimed:
        return True

    try:
        scan = (
            db.table("ingredient_scans")
            .select("scan_type, location_hint, image_metadata")
            .eq("id", scan_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if not scan.data:
            raise ValueError("Scan not found")
        row = scan.data[0]
        md = row.get("image_metadata")
        if not isinstance(md, dict):
            md = {}

        video_ref = (md.get("video_ref") or "").strip()
        if not video_ref:
            raise ValueError("Scan has no video_ref")

        duration_seconds = md.get("duration_seconds")
        max_frames = _compute_max_frames(duration_seconds, md.get("max_frames"))

        video_bytes = await _download_video_bytes(video_ref)

        await _process_video_scan(
            scan_id=scan_id,
            user_id=user_id,
            video_data=video_bytes,
            scan_type=(row.get("scan_type") or "pantry"),
            location_hint=row.get("location_hint"),
            max_frames=max_frames,
            duration_seconds=int(duration_seconds) if duration_seconds is not None else None,
            video_filename=md.get("video_filename"),
            video_size_mb=float(md.get("video_size_mb") or 0.0),
            barcode=md.get("barcode"),
            barcode_name_hint=md.get("barcode_name_hint"),
            barcode_quantity_hint=md.get("barcode_quantity_hint"),
            barcode_unit_hint=md.get("barcode_unit_hint"),
            barcode_ref=md.get("barcode_image_url"),
            barcode_product=md.get("barcode_product"),
        )

        try:
            db.table("scan_jobs").update({"status": "completed", "updated_at": _now_iso()}).eq(
                "id", str(job.get("id"))
            ).execute()
        except Exception:
            pass
        return True

    except Exception as e:
        logger.error(f"Video scan job failed for scan_id={scan_id}: {e}", exc_info=True)
        try:
            db.table("scan_jobs").update(
                {"status": "failed", "last_error": str(e)[:500], "updated_at": _now_iso()}
            ).eq("id", str(job.get("id"))).execute()
        except Exception:
            pass
        return True


async def worker_loop() -> None:
    poll = float(os.getenv("SAVO_VIDEO_SCAN_WORKER_POLL_SECONDS", "2") or 2)
    logger.info(f"Starting video scan worker loop (poll={poll}s)")

    while True:
        try:
            did_work = await _run_one_job()
            if not did_work:
                await asyncio.sleep(poll)
        except Exception as e:
            logger.error(f"Worker loop error: {e}", exc_info=True)
            await asyncio.sleep(max(1.0, poll))


def main() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()
