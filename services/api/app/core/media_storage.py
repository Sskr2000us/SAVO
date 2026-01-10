"""Supabase Storage helpers for inventory scan images.

We store images in a Supabase Storage bucket and persist a stable reference
in the DB. API responses can convert stored references to signed URLs.
"""

from __future__ import annotations

import os
import re
import uuid
from typing import Optional, Tuple, Dict, Any

from datetime import datetime, timezone

from app.core.database import get_db_client


INVENTORY_IMAGES_BUCKET = os.getenv("SUPABASE_INVENTORY_IMAGES_BUCKET", "inventory-images")


def _ext_for_content_type(content_type: Optional[str]) -> str:
    ct = (content_type or "").lower().strip()
    if ct in {"image/jpeg", "image/jpg"}:
        return ".jpg"
    if ct == "image/png":
        return ".png"
    if ct == "image/webp":
        return ".webp"
    return ".jpg"


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

    storage = client.storage.from_(bucket_name)
    storage.upload(
        path=path,
        file=file_content,
        file_options={
            "content-type": (content_type or "application/octet-stream"),
            "upsert": bool(upsert),
        },
    )
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

    storage = client.storage.from_(INVENTORY_IMAGES_BUCKET)

    # If the object already exists, Supabase returns 409. Extremely unlikely with UUIDs.
    storage.upload(
        path=object_path,
        file=content,
        file_options={
            "content-type": (content_type or "image/jpeg"),
            "upsert": False,
        },
    )

    stored_ref = f"{INVENTORY_IMAGES_BUCKET}/{object_path}"

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
