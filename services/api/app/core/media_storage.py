"""Supabase Storage helpers for inventory scan images.

We store images in a Supabase Storage bucket and persist a stable reference
in the DB. API responses can convert stored references to signed URLs.
"""

from __future__ import annotations

import os
import uuid
from typing import Optional

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
    return value.startswith(f"{INVENTORY_IMAGES_BUCKET}/")


def _storage_object_path_from_ref(value: str) -> str:
    # inventory-images/<user_id>/<path>  ->  <user_id>/<path>
    return value[len(f"{INVENTORY_IMAGES_BUCKET}/") :]


def upload_inventory_image(*, user_id: str, content: bytes, content_type: Optional[str] = None) -> str:
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

    return f"{INVENTORY_IMAGES_BUCKET}/{object_path}"


def to_signed_url(value: Optional[str], *, expires_in: int = 3600) -> Optional[str]:
    """Convert a stored reference into a signed URL, if applicable."""

    if not value:
        return value

    raw = value.strip()
    if raw.startswith("http://") or raw.startswith("https://"):
        return raw

    if not _is_storage_ref(raw):
        return raw

    client = get_db_client()
    object_path = _storage_object_path_from_ref(raw)

    try:
        storage = client.storage.from_(INVENTORY_IMAGES_BUCKET)
        res = storage.create_signed_url(object_path, expires_in)
        if isinstance(res, dict):
            return res.get("signedURL") or res.get("signedUrl") or raw
        return raw
    except Exception:
        return raw
