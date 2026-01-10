from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import os

from app.core.database import get_db_client


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_event(
    *,
    event_type: str,
    user_id: Optional[str],
    entity_id: Optional[str] = None,
    entity_type: Optional[str] = None,
    household_id: Optional[str] = None,
    session_id: Optional[str] = None,
    model_version: Optional[str] = None,
    release_version: Optional[str] = None,
    app_version: Optional[str] = None,
    taxonomy_version: Optional[str] = None,
    schema_version: Optional[int] = 1,
    event_ts: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """Best-effort event emitter.

    Writes to public.event_log using the Supabase client.
    Never raises (telemetry must not break core flows).
    """
    try:
        db = get_db_client()
        tax_ver = taxonomy_version
        if tax_ver is None:
            tax_ver = os.getenv("SAVO_TAXONOMY_VERSION")
        row = {
            "event_type": event_type,
            "event_ts": event_ts or _now_iso(),
            "user_id": user_id,
            "household_id": household_id,
            "session_id": session_id,
            **({"entity_id": entity_id} if entity_id else {}),
            **({"entity_type": entity_type} if entity_type else {}),
            **({"schema_version": schema_version} if schema_version is not None else {}),
            **({"taxonomy_version": tax_ver} if tax_ver else {}),
            "model_version": model_version,
            "release_version": release_version,
            "app_version": app_version,
            "payload": payload or {},
        }
        db.table("event_log").insert(row).execute()
    except Exception:
        return


def emit_events(events: list[dict[str, Any]]) -> None:
    """Best-effort bulk insert for events.

    Each item must already match the event_log column names.
    Never raises.
    """
    try:
        if not events:
            return
        db = get_db_client()
        db.table("event_log").insert(events).execute()
    except Exception:
        return
