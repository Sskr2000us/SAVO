from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid

from app.core.events import emit_event
from app.core.schema_migration import current_rollout_phase


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def emit_migration_incident(
    *,
    user_id: Optional[str],
    correlation_id: Optional[str],
    incident_type: str,
    operation: str,
    v2_target: str,
    error: str,
    session_id: Optional[str] = None,
    entity_id: Optional[str] = None,
    payload: Optional[Dict[str, Any]] = None,
) -> str:
    """Record a non-blocking migration incident.

    Always returns a correlation_id (generates one if missing).
    """
    cid = (correlation_id or "").strip() or str(uuid.uuid4())

    p: Dict[str, Any] = {
        "rollout_phase": current_rollout_phase(),
        "correlation_id": cid,
        "incident_type": incident_type,
        "operation": operation,
        "v2_target": v2_target,
        "error": (error or "").strip()[:2000],
    }
    if payload:
        p.update(payload)

    emit_event(
        event_type="migration.incident",
        event_ts=_now_iso(),
        user_id=user_id,
        session_id=session_id,
        entity_id=entity_id,
        payload=p,
    )

    return cid


def emit_shadow_report(
    *,
    user_id: str,
    endpoint: str,
    correlation_id: Optional[str],
    session_id: Optional[str] = None,
    payload: Dict[str, Any],
) -> str:
    cid = (correlation_id or "").strip() or str(uuid.uuid4())
    p = dict(payload or {})
    p.setdefault("rollout_phase", current_rollout_phase())
    p.setdefault("correlation_id", cid)
    p.setdefault("endpoint", endpoint)

    emit_event(
        event_type="schema.v2_shadow_report",
        event_ts=_now_iso(),
        user_id=user_id,
        session_id=session_id,
        payload=p,
    )
    return cid
