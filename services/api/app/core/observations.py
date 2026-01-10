from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from app.core.database import get_db_client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitize_raw_detection(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Remove fields that could contain image URLs or large payloads.

    We keep this conservative: the observations table is for auditable inference
    (what the model thought), not for media storage.
    """
    if not isinstance(raw, dict):
        return {}

    scrub_keys = {
        "thumbnail_url",
        "full_image_url",
        "image_url",
        "image",
        "frame",
        "frames",
        "pixels",
        "cropped_image",
    }

    cleaned: Dict[str, Any] = {}
    for k, v in raw.items():
        if k in scrub_keys:
            continue
        cleaned[k] = v
    return cleaned


def log_scan_observations(
    *,
    user_id: str,
    source: str,
    scan_id: Optional[str] = None,
    session_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    storage_location: Optional[str] = None,
    model_provider: Optional[str] = None,
    model_version: Optional[str] = None,
    taxonomy_version: Optional[str] = None,
    release_version: Optional[str] = None,
    app_version: Optional[str] = None,
    observations: Iterable[Dict[str, Any]],
    observed_at: Optional[str] = None,
) -> None:
    """Best-effort insert of auditable AI observations.

    Writes into `public.scan_observations` view (backed by observations.scan_observations).
    Never raises.

    Expected observation keys (best-effort):
    - detected_name, canonical_name, confidence, quantity, unit, bbox, metadata, raw
    - observed_entity_id
    """
    try:
        tv = (taxonomy_version or os.getenv("SAVO_TAXONOMY_VERSION") or "").strip() or None
        rows = []
        ts = observed_at or _now_iso()
        for ob in observations or []:
            if not isinstance(ob, dict):
                continue

            meta = ob.get("metadata")
            if not isinstance(meta, dict):
                meta = {}

            raw = ob.get("raw")
            if not isinstance(raw, dict):
                raw = dict(ob)

            rows.append(
                {
                    "observed_at": ts,
                    "user_id": user_id,
                    "scan_id": scan_id,
                    "session_id": session_id,
                    "correlation_id": correlation_id,
                    "source": source,
                    "storage_location": storage_location,
                    "observed_entity_type": ob.get("observed_entity_type") or "ingredient",
                    "observed_entity_id": ob.get("observed_entity_id"),
                    "detected_name": ob.get("detected_name"),
                    "canonical_name": ob.get("canonical_name"),
                    "confidence": ob.get("confidence"),
                    "quantity": ob.get("quantity"),
                    "unit": ob.get("unit"),
                    "bbox": ob.get("bbox"),
                    "crop_url": ob.get("crop_url"),
                    "metadata": meta,
                    "raw": _sanitize_raw_detection(raw),
                    "model_provider": model_provider,
                    "model_version": model_version,
                    "taxonomy_version": tv,
                    "release_version": release_version,
                    "app_version": app_version,
                }
            )

            if len(rows) >= 500:
                break

        if not rows:
            return

        db = get_db_client()
        db.table("scan_observations").insert(rows).execute()
    except Exception:
        return
