from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

from app.core.database import get_db_client
from app.core.schema_migration import dual_write_enabled, v1_writes_allowed, v2_write_enabled
from app.core.migration_telemetry import emit_migration_incident


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
    vision_model_version: Optional[str] = None,
    quantity_model_version: Optional[str] = None,
    embedding_version: Optional[str] = None,
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

        vv = (
            (vision_model_version or model_version or os.getenv("SAVO_VISION_MODEL_VERSION") or "").strip()
            or None
        )
        qv = (
            (quantity_model_version or os.getenv("SAVO_QUANTITY_MODEL_VERSION") or "").strip()
            or None
        )
        ev = (
            (embedding_version or os.getenv("SAVO_EMBEDDING_VERSION") or "none").strip()
            or "none"
        )

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

        # V1 rows (legacy schema) and V2 rows (required version stamps).
        rows_v1 = rows
        rows_v2 = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            rr = dict(r)
            rr["vision_model_version"] = vv
            rr["quantity_model_version"] = qv
            rr["embedding_version"] = ev
            rows_v2.append(rr)

        # Primary write routing.
        wrote_primary = False
        if v1_writes_allowed():
            db.table("scan_observations").insert(rows_v1).execute()
            wrote_primary = True
        elif v2_write_enabled():
            # In v2_only / v1-writes-disabled mode, observations should still be recorded.
            db.table("scan_observations_v2").insert(rows_v2).execute()
            wrote_primary = True

        if not wrote_primary:
            return

        # Side-by-side: optional V2 shadow write.
        if dual_write_enabled():
            try:
                db.table("scan_observations_v2").insert(rows_v2).execute()
            except Exception as e:
                # If the DB rejects due to missing required versions, quarantine best-effort.
                try:
                    db.table("inference_quarantine").insert(
                        {
                            "user_id": user_id,
                            "source_table": "observations.scan_observations_v2",
                            "reason": "v2_insert_failed",
                            "row_data": {"rows": rows_v2[:50]},
                            "metadata": {
                                "error": str(e),
                                "source": source,
                                "row_count": len(rows_v2),
                                "correlation_id": correlation_id,
                                "session_id": session_id,
                            },
                        }
                    ).execute()
                except Exception:
                    pass

                try:
                    emit_migration_incident(
                        user_id=user_id,
                        correlation_id=correlation_id,
                        session_id=session_id,
                        incident_type="v2_write_failed",
                        operation="insert",
                        v2_target="observations.scan_observations_v2",
                        error=str(e),
                        payload={"source": source, "row_count": len(rows_v2)},
                    )
                except Exception:
                    pass
                return
    except Exception:
        return
