from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query

from app.core.database import get_db_client
from app.core.settings import settings
from app.middleware.auth import get_current_user
from app.core.shadow_validation import run_pantry_shadow_validation

router = APIRouter(prefix="/api/migration", tags=["migration"])


def _pct(values: List[float], pct: float) -> Optional[float]:
    try:
        if not values:
            return None
        vs = sorted(values)
        if len(vs) == 1:
            return float(vs[0])
        p = float(pct)
        if p <= 0:
            return float(vs[0])
        if p >= 1:
            return float(vs[-1])
        idx = int((len(vs) - 1) * p)
        idx = max(0, min(idx, len(vs) - 1))
        return float(vs[idx])
    except Exception:
        return None


def _is_admin_request(admin_token: Optional[str]) -> bool:
    token = (admin_token or "").strip()
    expected = (getattr(settings, "admin_report_token", None) or "").strip()
    return bool(expected) and token == expected


@router.get("/status")
async def migration_status(user_id: str = Depends(get_current_user)) -> Dict[str, Any]:
    """Return current migration control-plane settings (for operators)."""
    return {
        "success": True,
        "schema_migration_mode": getattr(settings, "schema_migration_mode", "v1_only"),
        "enable_v2_shadow_read": bool(getattr(settings, "enable_v2_shadow_read", False)),
        "window": {
            "start": getattr(settings, "schema_migration_window_start", ""),
            "end": getattr(settings, "schema_migration_window_end", ""),
        },
        "rollout_phase": getattr(settings, "rollout_phase", "internal"),
        "progressive_v2_reads": {
            "enabled": bool(getattr(settings, "enable_progressive_v2_reads", False)),
            "percent": int(getattr(settings, "v2_read_rollout_percent", 0) or 0),
        },
        "user_id": user_id,
    }


@router.get("/reports")
async def list_migration_reports(
    limit: int = Query(default=100, ge=1, le=500),
    event_type: Optional[str] = Query(default=None, description="Filter to a single event type"),
    rollout_phase: Optional[str] = Query(default=None, description="Filter by payload.rollout_phase"),
    from_ts: Optional[str] = Query(default=None, description="ISO timestamp lower bound"),
    to_ts: Optional[str] = Query(default=None, description="ISO timestamp upper bound"),
    report_user_id: Optional[str] = Query(default=None, description="Admin-only: query reports for a specific user"),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Fetch shadow validation reports + incidents.

    - Default: returns only the caller's own records.
    - Admin-only (when SAVO_ADMIN_REPORT_TOKEN is set): can query any user via report_user_id.

    Rollout phase filtering is best-effort and relies on payload.rollout_phase.
    """
    db = get_db_client()

    is_admin = _is_admin_request(x_admin_token)
    target_user = user_id
    if report_user_id:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Admin token required for report_user_id")
        target_user = report_user_id

    q = (
        db.table("event_log")
        .select("id,event_type,event_ts,user_id,session_id,payload")
    )

    # Scope.
    q = q.eq("user_id", target_user)

    # Event type filter: by default return the migration-related set.
    if event_type and event_type.strip():
        q = q.eq("event_type", event_type.strip())
    else:
        # PostgREST doesn't support OR cleanly via supabase-py; do 3 queries and merge.
        # Keep it minimal: schema.v2_shadow_report + schema.v2_shadow_divergence + migration.incident.
        results: List[Dict[str, Any]] = []
        for et in ["schema.v2_shadow_report", "schema.v2_shadow_divergence", "migration.incident"]:
            qq = db.table("event_log").select("id,event_type,event_ts,user_id,session_id,payload").eq("user_id", target_user).eq("event_type", et)
            if rollout_phase and rollout_phase.strip():
                try:
                    qq = qq.contains("payload", {"rollout_phase": rollout_phase.strip()})
                except Exception:
                    pass
            if from_ts and from_ts.strip():
                qq = qq.gte("event_ts", from_ts.strip())
            if to_ts and to_ts.strip():
                qq = qq.lte("event_ts", to_ts.strip())
            res = qq.order("event_ts", desc=True).limit(int(limit)).execute()
            results.extend(res.data or [])

        # Sort + trim.
        results.sort(key=lambda r: str(r.get("event_ts") or ""), reverse=True)
        results = results[: int(limit)]
        return {"success": True, "user_id": target_user, "events": results, "count": len(results)}

    if rollout_phase and rollout_phase.strip():
        try:
            q = q.contains("payload", {"rollout_phase": rollout_phase.strip()})
        except Exception:
            pass

    if from_ts and from_ts.strip():
        q = q.gte("event_ts", from_ts.strip())
    if to_ts and to_ts.strip():
        q = q.lte("event_ts", to_ts.strip())

    res = q.order("event_ts", desc=True).limit(int(limit)).execute()
    events: List[Dict[str, Any]] = res.data or []
    return {"success": True, "user_id": target_user, "events": events, "count": len(events)}


@router.post("/run-shadow-validation")
async def run_shadow_validation(
    background_tasks: BackgroundTasks,
    include_inactive: bool = Query(default=False),
    maybe_days: int = Query(default=7, ge=1, le=365),
    stale_days: int = Query(default=30, ge=1, le=3650),
    report_user_id: Optional[str] = Query(default=None, description="Admin-only: run validation for a specific user"),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Trigger a background shadow validation run.

    Intended for reliability/ops: can be invoked by an external scheduler (cron/Render job)
    without impacting API latency.
    """
    is_admin = _is_admin_request(x_admin_token)
    target_user = user_id
    if report_user_id:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Admin token required for report_user_id")
        target_user = report_user_id

    # Compute lightweight V1 baselines inline (fast), then run V2 compare in background.
    db = get_db_client()
    now = datetime.utcnow().isoformat()
    items1 = (
        db.table("inventory_items")
        .select("id,quantity,is_current,last_seen_at,updated_at")
        .eq("user_id", target_user)
        .execute()
    )
    v1_total = len(items1.data or [])
    v1_visible = 0
    v1_qty_sum = 0.0
    for it in items1.data or []:
        if not isinstance(it, dict):
            continue
        if not include_inactive and not bool(it.get("is_current", True)):
            continue
        v1_visible += 1
        try:
            v1_qty_sum += float(it.get("quantity") or 0.0)
        except Exception:
            pass

    background_tasks.add_task(
        run_pantry_shadow_validation,
        user_id=target_user,
        include_inactive=include_inactive,
        maybe_days=maybe_days,
        stale_days=stale_days,
        v1_visible_count=v1_visible,
        v1_total_count=v1_total,
        v1_qty_sum=v1_qty_sum,
        correlation_id=now,
    )

    return {"success": True, "scheduled": True, "user_id": target_user}


@router.get("/metrics")
async def migration_metrics(
    minutes: int = Query(default=60, ge=1, le=24 * 60),
    limit: int = Query(default=2000, ge=100, le=5000),
    report_user_id: Optional[str] = Query(default=None, description="Admin-only: query metrics for a specific user"),
    x_admin_token: Optional[str] = Header(default=None, alias="X-Admin-Token"),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Lightweight migration health signals (best-effort).

    Designed for dashboards/alerts without requiring DB-side aggregates.
    """
    db = get_db_client()
    is_admin = _is_admin_request(x_admin_token)
    target_user = user_id
    if report_user_id:
        if not is_admin:
            raise HTTPException(status_code=403, detail="Admin token required for report_user_id")
        target_user = report_user_id

    from_ts = (datetime.now(timezone.utc) - timedelta(minutes=int(minutes))).isoformat()

    # ---------------------------------------------------------------------
    # api.latency
    # ---------------------------------------------------------------------
    latency_events = (
        db.table("event_log")
        .select("event_ts,payload")
        .eq("user_id", target_user)
        .eq("event_type", "api.latency")
        .gte("event_ts", from_ts)
        .order("event_ts", desc=True)
        .limit(int(limit))
        .execute()
    )

    lat_by_endpoint: Dict[str, List[float]] = {}
    for row in latency_events.data or []:
        if not isinstance(row, dict):
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        endpoint = str(payload.get("endpoint") or "unknown")
        ms = payload.get("ms")
        try:
            ms_f = float(ms)
        except Exception:
            continue
        lat_by_endpoint.setdefault(endpoint, []).append(ms_f)

    latency_summary: Dict[str, Any] = {}
    for endpoint, vals in lat_by_endpoint.items():
        if not vals:
            continue
        latency_summary[endpoint] = {
            "count": len(vals),
            "p50_ms": _pct(vals, 0.50),
            "p95_ms": _pct(vals, 0.95),
            "max_ms": max(vals) if vals else None,
        }

    # ---------------------------------------------------------------------
    # schema.v2_shadow_report
    # ---------------------------------------------------------------------
    shadow_events = (
        db.table("event_log")
        .select("event_ts,payload")
        .eq("user_id", target_user)
        .eq("event_type", "schema.v2_shadow_report")
        .gte("event_ts", from_ts)
        .order("event_ts", desc=True)
        .limit(int(limit))
        .execute()
    )

    mismatch_rates: List[float] = []
    compared_total = 0
    mismatches_total = 0
    for row in shadow_events.data or []:
        if not isinstance(row, dict):
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        ec = payload.get("entity_compare")
        if not isinstance(ec, dict):
            continue
        try:
            mismatch_rates.append(float(ec.get("mismatch_rate") or 0.0))
        except Exception:
            pass
        try:
            compared_total += int(ec.get("compared") or 0)
        except Exception:
            pass
        try:
            mismatches_total += int(ec.get("mismatches") or 0)
        except Exception:
            pass

    shadow_summary = {
        "reports": len(shadow_events.data or []),
        "avg_mismatch_rate": (sum(mismatch_rates) / len(mismatch_rates)) if mismatch_rates else None,
        "max_mismatch_rate": max(mismatch_rates) if mismatch_rates else None,
        "compared_total": compared_total,
        "mismatches_total": mismatches_total,
    }

    # ---------------------------------------------------------------------
    # migration.incident
    # ---------------------------------------------------------------------
    incident_events = (
        db.table("event_log")
        .select("event_ts,payload")
        .eq("user_id", target_user)
        .eq("event_type", "migration.incident")
        .gte("event_ts", from_ts)
        .order("event_ts", desc=True)
        .limit(int(limit))
        .execute()
    )

    by_type: Dict[str, int] = {}
    by_operation: Dict[str, int] = {}
    for row in incident_events.data or []:
        if not isinstance(row, dict):
            continue
        payload = row.get("payload")
        if not isinstance(payload, dict):
            continue
        t = str(payload.get("incident_type") or "unknown")
        op = str(payload.get("operation") or "unknown")
        by_type[t] = by_type.get(t, 0) + 1
        by_operation[op] = by_operation.get(op, 0) + 1

    incidents_summary = {
        "count": len(incident_events.data or []),
        "by_type": by_type,
        "by_operation": by_operation,
    }

    return {
        "success": True,
        "user_id": target_user,
        "window_minutes": int(minutes),
        "from_ts": from_ts,
        "latency": latency_summary,
        "shadow": shadow_summary,
        "incidents": incidents_summary,
    }
