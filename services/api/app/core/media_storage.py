"""Supabase Storage helpers for inventory scan images.

We store images in a Supabase Storage bucket and persist a stable reference
in the DB. API responses can convert stored references to signed URLs.
"""

from __future__ import annotations

import os
import re
import uuid
import logging
from typing import Optional, Tuple, Dict, Any

from datetime import datetime, timezone

from app.core.database import get_db_client


logger = logging.getLogger(__name__)


def _supabase_base_url() -> str:
    url = (os.getenv("SUPABASE_URL") or "").strip()
    if not url:
        raise ValueError("SUPABASE_URL is required for Storage operations")
    return url.rstrip("/")


def _supabase_service_key() -> str:
    key = (os.getenv("SUPABASE_SERVICE_KEY") or "").strip()
    if not key:
        raise ValueError("SUPABASE_SERVICE_KEY is required for Storage operations")
    return key


def _ensure_storage_bucket_exists(bucket_name: str) -> None:
    """Best-effort ensure a Supabase Storage bucket exists.

    This eliminates production failures when the bucket was never created.
    Requires SUPABASE_SERVICE_KEY (service role) in the environment.
    """

    b = (bucket_name or "").strip()
    if not b:
        raise ValueError("bucket_name is required")

    try:
        import httpx

        base = _supabase_base_url()
        key = _supabase_service_key()

        headers = {
            "authorization": f"Bearer {key}",
            "apikey": key,
            "content-type": "application/json",
        }

        # If it already exists, this will succeed and we do nothing.
        # If it doesn't exist, create it.
        get_url = f"{base}/storage/v1/bucket/{b}"
        with httpx.Client(timeout=8.0) as client:
            r = client.get(get_url, headers=headers)
            if r.status_code == 200:
                return

            # Create (ignore if already exists)
            create_url = f"{base}/storage/v1/bucket"
            payload = {"id": b, "name": b, "public": False}
            cr = client.post(create_url, headers=headers, json=payload)
            if cr.status_code in {200, 201, 204, 409}:
                return

            # Some Supabase projects return 400 with a JSON error body.
            logger.warning(
                "Failed to ensure storage bucket '%s' (status=%s body=%s)",
                b,
                cr.status_code,
                (cr.text or "")[:2000],
            )
    except Exception as e:
        # Never break core flows; upload() will still raise with details.
        logger.warning("Bucket ensure failed for '%s': %s", bucket_name, str(e))


INVENTORY_IMAGES_BUCKET = os.getenv("SUPABASE_INVENTORY_IMAGES_BUCKET", "inventory-images")
SCAN_VIDEOS_BUCKET = os.getenv("SUPABASE_SCAN_VIDEOS_BUCKET", "scan-videos")


def _ext_for_content_type(content_type: Optional[str]) -> str:
    ct = (content_type or "").lower().strip()
    if ct in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if ct == "image/png":
        return ".png"
    if ct == "image/webp":
        return ".webp"
    return ".jpg"


def _ext_for_video_content_type(content_type: Optional[str]) -> str:
    ct = (content_type or "").lower().strip()
    if ct in {"video/mp4"}:
        return ".mp4"
    if ct in {"video/quicktime"}:
        return ".mov"
    if ct in {"video/x-msvideo"}:
        return ".avi"
    if ct in {"video/x-matroska"}:
        return ".mkv"
    if ct in {"video/webm"}:
        return ".webm"
    return ".mp4"


def build_inventory_image_ref(user_id: str, object_path: str) -> str:
    # Stored in DB; used to detect that the value is a storage object, not an external URL.
    return f"{INVENTORY_IMAGES_BUCKET}/{user_id}/{object_path.lstrip('/')}"


def _is_storage_ref(value: str) -> bool:
    # We accept "<bucket>/<path>" references for any bucket.
    # (e.g. inventory-images/<user>/<uuid>.jpg, ingredient-images/thumbnails/...).
    raw = (value or "").strip()
    if not raw or raw.startswith("http://") or raw.startswith("https://"):
        return False
    return "/" in raw and not raw.startswith("/")


def _parse_storage_ref(value: str) -> Optional[Tuple[str, str]]:
    raw = (value or "").strip()
    if not _is_storage_ref(raw):
        return None
    # bucket/path (bucket must be a plausible storage bucket name)
    parts = raw.split("/", 1)
    if len(parts) != 2:
        return None
    bucket, object_path = parts[0].strip(), parts[1].strip()
    if not bucket or not object_path:
        return None
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{1,62}$", bucket):
        return None
    return bucket, object_path


def _storage_object_path_from_ref(value: str) -> str:
    parsed = _parse_storage_ref(value)
    if not parsed:
        return value
    _bucket, object_path = parsed
    return object_path


def upload_file_to_storage(
    *,
    file_content: bytes,
    file_path: str,
    content_type: Optional[str] = None,
    bucket_name: str,
    upsert: bool = False,
) -> str:
    """Upload a file to a specified Supabase Storage bucket.

    Returns a stable storage reference in the format "<bucket>/<path>" (not a signed URL).
    """

    client = get_db_client()
    path = (file_path or "").lstrip("/")
    if not path:
        raise ValueError("file_path is required")

    _ensure_storage_bucket_exists(bucket_name)
    storage = client.storage.from_(bucket_name)
    result = storage.upload(
        path=path,
        file=file_content,
        file_options={
            "content-type": (content_type or "application/octet-stream"),
            "upsert": bool(upsert),
        },
    )
    # supabase-py return types vary by version; handle dict-like or attribute-like errors.
    try:
        err = None
        if isinstance(result, dict):
            err = result.get("error")
        else:
            err = getattr(result, "error", None)
        if err:
            raise RuntimeError(f"Storage upload failed (bucket={bucket_name}, path={path}): {err}")
    except Exception:
        # If inspection fails, still return the reference (older SDK versions may not return a response).
        pass
    return f"{bucket_name}/{path}"


def upload_inventory_image(
    *,
    user_id: str,
    content: bytes,
    content_type: Optional[str] = None,
    asset_type: Optional[str] = None,
    source: Optional[str] = None,
    expires_at: Optional[str] = None,
    links: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> str:
    """Upload raw bytes to Supabase Storage and return the stored reference.

    The returned value is a stable reference stored in DB (NOT a signed URL).
    """

    client = get_db_client()
    ext = _ext_for_content_type(content_type)
    object_name = f"{uuid.uuid4().hex}{ext}"

    # We include user_id in the path so it's naturally partitioned.
    object_path = f"{user_id}/{object_name}"

    # Ensure bucket exists so uploads don't 500 in fresh Supabase projects.
    _ensure_storage_bucket_exists(INVENTORY_IMAGES_BUCKET)

    # If the object already exists, Supabase returns 409. Extremely unlikely with UUIDs.
    storage = client.storage.from_(INVENTORY_IMAGES_BUCKET)
    result = storage.upload(
        path=object_path,
        file=content,
        file_options={
            "content-type": (content_type or "image/jpeg"),
            "upsert": False,
        },
    )

    stored_ref = f"{INVENTORY_IMAGES_BUCKET}/{object_path}"

    # supabase-py return types vary by version; handle dict-like or attribute-like errors.
    try:
        err = None
        if isinstance(result, dict):
            err = result.get("error")
        else:
            err = getattr(result, "error", None)
        if err:
            raise RuntimeError(
                f"Storage upload failed (bucket={INVENTORY_IMAGES_BUCKET}, path={object_path}): {err}"
            )
    except Exception:
        # If inspection fails, continue; errors will still surface as exceptions from upload() itself.
        pass

    # Best-effort central tracking for retention/audit.
    try:
        db = get_db_client()
        if asset_type:
            row: Dict[str, Any] = {
                "user_id": user_id,
                "storage_ref": stored_ref,
                "media_type": "image",
                "asset_type": asset_type,
                "source": source,
                "content_type": content_type or "image/jpeg",
                "metadata": metadata or {},
            }
            if expires_at:
                row["expires_at"] = expires_at
            if isinstance(links, dict):
                # map well-known keys only
                for k in ("scan_id", "detected_id", "observation_id", "inventory_item_id"):
                    if links.get(k):
                        row[k] = links.get(k)
                # store everything else under metadata.links
                extra = {kk: vv for kk, vv in links.items() if kk not in {"scan_id", "detected_id", "observation_id", "inventory_item_id"}}
                if extra:
                    md = dict(row.get("metadata") or {})
                    md["links"] = extra
                    row["metadata"] = md
            db.table("media_assets").insert(row).execute()
    except Exception:
        pass

    return stored_ref


def upload_scan_video(
    *,
    user_id: str,
    content: bytes,
    content_type: Optional[str] = None,
    asset_type: str = "scan_video",
    source: Optional[str] = None,
    expires_at: Optional[str] = None,
    links: Optional[Dict[str, Any]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    filename: Optional[str] = None,
) -> str:
    """Upload raw video bytes and return a stable storage reference.

    Returned value is "<bucket>/<path>" (NOT a signed URL).
    """

    ct = (content_type or "application/octet-stream").strip().lower() or "application/octet-stream"
    ext = _ext_for_video_content_type(ct)
    base = uuid.uuid4().hex
    safe_name = None
    try:
        safe_name = (filename or "").strip()
        safe_name = safe_name.split("/")[-1].split("\\")[-1]
        safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", safe_name)
        safe_name = safe_name[:80] if safe_name else None
    except Exception:
        safe_name = None

    object_name = f"{base}{ext}"
    if safe_name:
        object_name = f"{base}_{safe_name}"
        if not object_name.lower().endswith(ext):
            object_name = f"{object_name}{ext}"

    object_path = f"{user_id}/{object_name}".lstrip("/")
    stored_ref = upload_file_to_storage(
        file_content=content,
        file_path=object_path,
        content_type=ct,
        bucket_name=SCAN_VIDEOS_BUCKET,
        upsert=False,
    )

    try:
        db = get_db_client()
        row: Dict[str, Any] = {
            "user_id": user_id,
            "storage_ref": stored_ref,
            "media_type": "video",
            "asset_type": asset_type,
            "source": source,
            "content_type": ct,
            "metadata": metadata or {},
        }
        if expires_at:
            row["expires_at"] = expires_at
        if isinstance(links, dict):
            for k in ("scan_id", "detected_id", "observation_id", "inventory_item_id"):
                if links.get(k):
                    row[k] = links.get(k)
            extra = {kk: vv for kk, vv in links.items() if kk not in {"scan_id", "detected_id", "observation_id", "inventory_item_id"}}
            if extra:
                md = dict(row.get("metadata") or {})
                md["links"] = extra
                row["metadata"] = md
        db.table("media_assets").insert(row).execute()
    except Exception:
        pass

    return stored_ref


def to_signed_url(value: Optional[str], *, expires_in: int = 3600) -> Optional[str]:
    """Convert a stored reference into a signed URL, if applicable.

    Supports any "<bucket>/<path>" storage reference.
    """

    if not value:
        return value

    raw = value.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw

    parsed = _parse_storage_ref(raw)
    if not parsed:
        return raw

    bucket, object_path = parsed
    client = get_db_client()

    try:
        storage = client.storage.from_(bucket)
        res = storage.create_signed_url(object_path, expires_in)
        if isinstance(res, dict):
            return res.get("signedURL") or res.get("signedUrl") or raw
        return raw
    except Exception:
        return raw
