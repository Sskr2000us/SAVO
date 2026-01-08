from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnalyticsEventIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    ts: Optional[datetime] = None
    props: Dict[str, Any] = Field(default_factory=dict)


class AnalyticsEventsIn(BaseModel):
    events: List[AnalyticsEventIn] = Field(default_factory=list)


@router.post("/events")
async def ingest_events(
    payload: AnalyticsEventsIn,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Ingest product analytics events (activation funnel)."""
    try:
        from app.core.database import get_db_client

        supabase = get_db_client()

        now = datetime.now(timezone.utc)
        rows = []
        for ev in payload.events:
            name = ev.name.strip()
            if not name:
                continue
            ts = ev.ts
            if ts is None:
                ts = now
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)

            rows.append(
                {
                    "user_id": user_id,
                    "event_name": name,
                    "event_ts": ts.isoformat(),
                    "props": ev.props or {},
                }
            )

        if not rows:
            return {"success": True, "inserted": 0}

        res = supabase.table("product_events").insert(rows).execute()
        inserted = len(res.data) if getattr(res, "data", None) else len(rows)
        return {"success": True, "inserted": inserted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to ingest events: {e}")


def _median(values: List[float]) -> Optional[float]:
    if not values:
        return None
    values_sorted = sorted(values)
    n = len(values_sorted)
    mid = n // 2
    if n % 2 == 1:
        return values_sorted[mid]
    return (values_sorted[mid - 1] + values_sorted[mid]) / 2.0


@router.get("/activation")
async def activation_report(
    days: int = 30,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Returns an activation funnel report over the last N days.

    Note: authenticated for now (so superadmins can query it). This can be
    adjusted later to an admin-only auth policy.
    """
    try:
        from app.core.database import get_db_client

        supabase = get_db_client()

        days = max(1, min(days, 180))
        since = datetime.now(timezone.utc) - timedelta(days=days)

        # Fetch recent events (bounded). If you outgrow this, add server-side
        # aggregation or a materialized view.
        result = (
            supabase.table("product_events")
            .select("user_id,event_name,event_ts")
            .gte("event_ts", since.isoformat())
            .order("event_ts", desc=False)
            .limit(50000)
            .execute()
        )

        rows = result.data or []

        users_onboarding = set()
        users_scan_started = set()
        users_scan_completed = set()
        users_confirm_completed = set()
        users_first_value = set()

        # For activation within 2 minutes: first scan start -> first confirm
        scan_started_ts_by_user: Dict[str, datetime] = {}
        confirm_completed_ts_by_user: Dict[str, datetime] = {}

        # For median TTFV
        onboarding_ts_by_user: Dict[str, datetime] = {}
        first_value_ts_by_user: Dict[str, datetime] = {}

        for r in rows:
            uid = (r.get("user_id") or "").strip()
            name = (r.get("event_name") or "").strip()
            ts_raw = r.get("event_ts")
            if not uid or not name or not ts_raw:
                continue

            try:
                ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except Exception:
                continue

            if name == "onboarding_complete":
                users_onboarding.add(uid)
                onboarding_ts_by_user.setdefault(uid, ts)

            if name == "pantry_scan_started":
                users_scan_started.add(uid)
                scan_started_ts_by_user.setdefault(uid, ts)

            if name == "pantry_scan_completed":
                users_scan_completed.add(uid)

            if name == "pantry_confirm_completed":
                users_confirm_completed.add(uid)
                confirm_completed_ts_by_user.setdefault(uid, ts)

            if name in ("pantry_scan_completed", "pantry_confirm_completed", "recipe_cooked"):
                users_first_value.add(uid)
                existing = first_value_ts_by_user.get(uid)
                if existing is None or ts < existing:
                    first_value_ts_by_user[uid] = ts

        ttfv_seconds: List[float] = []
        for uid, onboard_ts in onboarding_ts_by_user.items():
            fv = first_value_ts_by_user.get(uid)
            if fv is None:
                continue
            delta = (fv - onboard_ts).total_seconds()
            if 0 <= delta <= 86400 * 30:
                ttfv_seconds.append(delta)

        activated_within_2m = set()
        scan_to_confirm_seconds: List[float] = []
        for uid, scan_ts in scan_started_ts_by_user.items():
            confirm_ts = confirm_completed_ts_by_user.get(uid)
            if confirm_ts is None:
                continue
            delta = (confirm_ts - scan_ts).total_seconds()
            if delta < 0:
                continue
            if delta <= 86400:
                scan_to_confirm_seconds.append(delta)
            if delta <= 120:
                activated_within_2m.add(uid)

        onboarding_n = len(users_onboarding)

        def rate(n: int) -> Optional[float]:
            if onboarding_n == 0:
                return None
            return n / onboarding_n

        return {
            "success": True,
            "window_days": days,
            "funnel": {
                "onboarding_complete": {
                    "users": onboarding_n,
                    "conversion": 1.0 if onboarding_n > 0 else None,
                },
                "scan_started": {
                    "users": len(users_scan_started),
                    "conversion": rate(len(users_scan_started)),
                },
                "scan_completed": {
                    "users": len(users_scan_completed),
                    "conversion": rate(len(users_scan_completed)),
                },
                "confirm_completed": {
                    "users": len(users_confirm_completed),
                    "conversion": rate(len(users_confirm_completed)),
                },
                "first_value": {
                    "users": len(users_first_value),
                    "conversion": rate(len(users_first_value)),
                },
                "activation_within_2m": {
                    "users": len(activated_within_2m),
                    "conversion": rate(len(activated_within_2m)),
                },
            },
            "time_to_first_value_seconds": {
                "samples": len(ttfv_seconds),
                "median": _median(ttfv_seconds),
            },
            "scan_to_confirm_seconds": {
                "samples": len(scan_to_confirm_seconds),
                "median": _median(scan_to_confirm_seconds),
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build report: {e}")


@router.get("/core-loop")
async def core_loop_report(
    days: int = 30,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Core loop drop-off: scan -> recipe shown -> recipe opened -> recipe saved/cooked."""
    try:
        from app.core.database import get_db_client

        supabase = get_db_client()

        days = max(1, min(days, 180))
        since = datetime.now(timezone.utc) - timedelta(days=days)

        result = (
            supabase.table("product_events")
            .select("user_id,event_name,event_ts")
            .gte("event_ts", since.isoformat())
            .order("event_ts", desc=False)
            .limit(50000)
            .execute()
        )

        rows = result.data or []

        users_scan_started = set()
        users_recipe_shown = set()
        users_recipe_opened = set()
        users_recipe_saved = set()
        users_recipe_cooked = set()

        for r in rows:
            uid = (r.get("user_id") or "").strip()
            name = (r.get("event_name") or "").strip()
            if not uid or not name:
                continue

            if name == "pantry_scan_started":
                users_scan_started.add(uid)
            elif name == "recipe_shown":
                users_recipe_shown.add(uid)
            elif name == "recipe_opened":
                users_recipe_opened.add(uid)
            elif name == "recipe_saved":
                users_recipe_saved.add(uid)
            elif name == "recipe_cooked":
                users_recipe_cooked.add(uid)

        baseline = len(users_scan_started)

        def rate_from_baseline(n: int) -> Optional[float]:
            if baseline == 0:
                return None
            return n / baseline

        return {
            "success": True,
            "window_days": days,
            "baseline": {"event": "pantry_scan_started", "users": baseline},
            "steps": {
                "scan_started": {"users": baseline, "conversion": 1.0 if baseline > 0 else None},
                "recipe_shown": {"users": len(users_recipe_shown), "conversion": rate_from_baseline(len(users_recipe_shown))},
                "recipe_opened": {"users": len(users_recipe_opened), "conversion": rate_from_baseline(len(users_recipe_opened))},
                "recipe_saved": {"users": len(users_recipe_saved), "conversion": rate_from_baseline(len(users_recipe_saved))},
                "recipe_cooked": {"users": len(users_recipe_cooked), "conversion": rate_from_baseline(len(users_recipe_cooked))},
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build report: {e}")


@router.get("/monetization")
async def monetization_report(
    days: int = 30,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Monetization/churn: paywall shown -> upgrade started/completed -> pro cancelled (with reasons)."""
    try:
        from app.core.database import get_db_client

        supabase = get_db_client()

        days = max(1, min(days, 180))
        since = datetime.now(timezone.utc) - timedelta(days=days)

        result = (
            supabase.table("product_events")
            .select("user_id,event_name,event_ts,props")
            .gte("event_ts", since.isoformat())
            .order("event_ts", desc=False)
            .limit(50000)
            .execute()
        )

        rows = result.data or []

        users_paywall = set()
        users_upgrade_started = set()
        users_upgrade_completed = set()
        users_pro_cancelled = set()

        paywall_trigger_counts: Dict[str, int] = {}
        churn_reason_counts: Dict[str, int] = {}

        for r in rows:
            uid = (r.get("user_id") or "").strip()
            name = (r.get("event_name") or "").strip()
            props = r.get("props") or {}
            if not uid or not name:
                continue

            if name == "paywall_shown":
                users_paywall.add(uid)
                trigger = "unknown"
                if isinstance(props, dict):
                    raw = props.get("trigger")
                    if raw is not None and str(raw).strip():
                        trigger = str(raw).strip()
                paywall_trigger_counts[trigger] = paywall_trigger_counts.get(trigger, 0) + 1

            elif name == "upgrade_started":
                users_upgrade_started.add(uid)
            elif name == "upgrade_completed":
                users_upgrade_completed.add(uid)
            elif name == "pro_cancelled":
                users_pro_cancelled.add(uid)
                reason = "unknown"
                if isinstance(props, dict):
                    raw = props.get("reason")
                    if raw is not None and str(raw).strip():
                        reason = str(raw).strip()
                churn_reason_counts[reason] = churn_reason_counts.get(reason, 0) + 1

        baseline = len(users_paywall)

        def rate_from_paywall(n: int) -> Optional[float]:
            if baseline == 0:
                return None
            return n / baseline

        return {
            "success": True,
            "window_days": days,
            "paywall": {
                "users": baseline,
                "triggers": paywall_trigger_counts,
            },
            "upgrade": {
                "started_users": len(users_upgrade_started),
                "completed_users": len(users_upgrade_completed),
                "started_conversion_from_paywall": rate_from_paywall(len(users_upgrade_started)),
                "completed_conversion_from_paywall": rate_from_paywall(len(users_upgrade_completed)),
            },
            "churn": {
                "pro_cancelled_users": len(users_pro_cancelled),
                "reasons": churn_reason_counts,
            },
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build report: {e}")
