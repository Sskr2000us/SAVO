from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Depends, HTTPException

from app.core.database import get_db_client
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


def _parse_dt(ts_raw: Any) -> Optional[datetime]:
    if not ts_raw:
        return None
    try:
        ts = datetime.fromisoformat(str(ts_raw).replace("Z", "+00:00"))
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return ts
    except Exception:
        return None


def _group_key(row: Dict[str, Any]) -> Tuple[str, str]:
    mv = (row.get("model_version") or "unknown").strip() if isinstance(row.get("model_version"), str) else "unknown"
    rv = (row.get("release_version") or "unknown").strip() if isinstance(row.get("release_version"), str) else "unknown"
    return mv or "unknown", rv or "unknown"


@router.get("/dashboard")
async def dashboard(
    days: int = 30,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """KPI dashboard for scan speed/fixability/improvement.

    Returns aggregates grouped by (model_version, release_version).
    """
    try:
        days = max(1, min(days, 180))
        since = datetime.now(timezone.utc) - timedelta(days=days)

        db = get_db_client()

        scans_res = (
            db.table("ingredient_scans")
            .select(
                "id,created_at,analysis_ms,confirm_ms,detected_count,confirmed_count,modified_count,rejected_count,auto_added_count,model_version,release_version"
            )
            .eq("user_id", user_id)
            .gte("created_at", since.isoformat())
            .order("created_at", desc=False)
            .limit(50000)
            .execute()
        )

        rows = scans_res.data or []

        out: Dict[str, Any] = {
            "success": True,
            "window_days": days,
            "groups": [],
        }

        buckets: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for r in rows:
            k = _group_key(r)
            b = buckets.setdefault(
                k,
                {
                    "model_version": k[0],
                    "release_version": k[1],
                    "scan_count": 0,
                    "analysis_ms": [],
                    "confirm_ms": [],
                    "detected": 0,
                    "confirmed": 0,
                    "modified": 0,
                    "rejected": 0,
                    "auto_added": 0,
                },
            )

            b["scan_count"] += 1

            for fld in ("analysis_ms", "confirm_ms"):
                v = r.get(fld)
                if isinstance(v, (int, float)):
                    b[fld].append(float(v))

            for fld, key in (
                ("detected_count", "detected"),
                ("confirmed_count", "confirmed"),
                ("modified_count", "modified"),
                ("rejected_count", "rejected"),
                ("auto_added_count", "auto_added"),
            ):
                v = r.get(fld)
                if isinstance(v, (int, float)):
                    b[key] += int(v)

        def _pct(values: List[float], p: float) -> Optional[float]:
            if not values:
                return None
            values_sorted = sorted(values)
            if len(values_sorted) == 1:
                return values_sorted[0]
            idx = int(round((len(values_sorted) - 1) * p))
            idx = max(0, min(idx, len(values_sorted) - 1))
            return values_sorted[idx]

        for _k, b in buckets.items():
            detected = int(b["detected"]) or 0
            corrected = int(b["modified"]) + int(b["rejected"]) if detected > 0 else 0
            correction_rate = (corrected / detected) if detected > 0 else None

            out["groups"].append(
                {
                    "model_version": b["model_version"],
                    "release_version": b["release_version"],
                    "scan_count": b["scan_count"],
                    "scan_time_ms": {
                        "p50_analysis": _pct(b["analysis_ms"], 0.50),
                        "p95_analysis": _pct(b["analysis_ms"], 0.95),
                        "p50_confirm": _pct(b["confirm_ms"], 0.50),
                        "p95_confirm": _pct(b["confirm_ms"], 0.95),
                    },
                    "corrections": {
                        "detected": detected,
                        "confirmed": int(b["confirmed"]),
                        "modified": int(b["modified"]),
                        "rejected": int(b["rejected"]),
                        "correction_rate": correction_rate,
                    },
                    "auto_add": {
                        "auto_added": int(b["auto_added"]),
                    },
                }
            )

        return out
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to build dashboard: {e}")


@router.get("/regression")
async def regression_alerts(
    days: int = 7,
    min_samples: int = 30,
    correction_rate_abs_spike: float = 0.10,
    false_positive_abs_spike: float = 0.05,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Detect regressions by comparing the last N days vs the prior N days.

    Alerts on:
    - correction_rate spikes (modified+rejected / detected)
    - auto-add false positive spikes (undo events / auto-saved)

    Note: false positives rely on inventory_item_events being present.
    """
    try:
        days = max(1, min(days, 60))
        now = datetime.now(timezone.utc)
        cur_since = now - timedelta(days=days)
        prev_since = now - timedelta(days=days * 2)

        db = get_db_client()

        def load_scan_window(since_dt: datetime, until_dt: datetime) -> List[Dict[str, Any]]:
            res = (
                db.table("ingredient_scans")
                .select("created_at,detected_count,modified_count,rejected_count,auto_added_count,model_version,release_version")
                .eq("user_id", user_id)
                .gte("created_at", since_dt.isoformat())
                .lt("created_at", until_dt.isoformat())
                .limit(50000)
                .execute()
            )
            return res.data or []

        cur_rows = load_scan_window(cur_since, now)
        prev_rows = load_scan_window(prev_since, cur_since)

        # inventory_item_events for undo/correction (delete or canonical_name change)
        def load_inv_events(since_dt: datetime, until_dt: datetime) -> List[Dict[str, Any]]:
            res = (
                db.table("inventory_item_events")
                .select(
                    "event_ts,event_type,before,after,item_source,item_model_version,item_release_version"
                )
                .eq("user_id", user_id)
                .gte("event_ts", since_dt.isoformat())
                .lt("event_ts", until_dt.isoformat())
                .limit(50000)
                .execute()
            )
            return res.data or []

        cur_inv = []
        prev_inv = []
        try:
            cur_inv = load_inv_events(cur_since, now)
            prev_inv = load_inv_events(prev_since, cur_since)
        except Exception:
            # Table may not exist yet in some deployments.
            cur_inv = []
            prev_inv = []

        def agg_scans(rows: List[Dict[str, Any]]) -> Dict[Tuple[str, str], Dict[str, int]]:
            out: Dict[Tuple[str, str], Dict[str, int]] = {}
            for r in rows:
                k = _group_key(r)
                b = out.setdefault(k, {"detected": 0, "modified": 0, "rejected": 0, "auto_added": 0, "scans": 0})
                b["scans"] += 1
                for fld, key in (
                    ("detected_count", "detected"),
                    ("modified_count", "modified"),
                    ("rejected_count", "rejected"),
                    ("auto_added_count", "auto_added"),
                ):
                    v = r.get(fld)
                    if isinstance(v, (int, float)):
                        b[key] += int(v)
            return out

        def agg_false_pos(inv_rows: List[Dict[str, Any]]) -> Dict[Tuple[str, str], int]:
            out: Dict[Tuple[str, str], int] = {}
            for r in inv_rows:
                mv = (r.get("item_model_version") or "unknown")
                rv = (r.get("item_release_version") or "unknown")
                k = (str(mv or "unknown"), str(rv or "unknown"))

                if (r.get("event_type") or "") == "delete":
                    out[k] = out.get(k, 0) + 1
                    continue

                if (r.get("event_type") or "") == "update":
                    before = r.get("before") if isinstance(r.get("before"), dict) else {}
                    after = r.get("after") if isinstance(r.get("after"), dict) else {}
                    if before.get("canonical_name") and after.get("canonical_name") and before.get("canonical_name") != after.get("canonical_name"):
                        out[k] = out.get(k, 0) + 1
            return out

        cur_scan = agg_scans(cur_rows)
        prev_scan = agg_scans(prev_rows)

        cur_fp = agg_false_pos(cur_inv)
        prev_fp = agg_false_pos(prev_inv)

        alerts: List[Dict[str, Any]] = []
        keys = set(cur_scan.keys()) | set(prev_scan.keys()) | set(cur_fp.keys()) | set(prev_fp.keys())

        for k in sorted(keys):
            cur = cur_scan.get(k, {"detected": 0, "modified": 0, "rejected": 0, "auto_added": 0, "scans": 0})
            prev = prev_scan.get(k, {"detected": 0, "modified": 0, "rejected": 0, "auto_added": 0, "scans": 0})

            cur_detected = cur["detected"]
            prev_detected = prev["detected"]

            cur_corr = ((cur["modified"] + cur["rejected"]) / cur_detected) if cur_detected > 0 else None
            prev_corr = ((prev["modified"] + prev["rejected"]) / prev_detected) if prev_detected > 0 else None

            cur_auto = cur["auto_added"]
            prev_auto = prev["auto_added"]
            cur_fp_rate = (cur_fp.get(k, 0) / cur_auto) if cur_auto > 0 else None
            prev_fp_rate = (prev_fp.get(k, 0) / prev_auto) if prev_auto > 0 else None

            sample_ok = (cur["scans"] + prev["scans"]) >= int(min_samples)

            if sample_ok and cur_corr is not None and prev_corr is not None:
                if (cur_corr - prev_corr) >= float(correction_rate_abs_spike):
                    alerts.append(
                        {
                            "type": "correction_rate_spike",
                            "model_version": k[0],
                            "release_version": k[1],
                            "current": cur_corr,
                            "previous": prev_corr,
                            "delta": cur_corr - prev_corr,
                            "samples_scans": cur["scans"],
                        }
                    )

            if sample_ok and cur_fp_rate is not None and prev_fp_rate is not None:
                if (cur_fp_rate - prev_fp_rate) >= float(false_positive_abs_spike):
                    alerts.append(
                        {
                            "type": "auto_add_false_positive_spike",
                            "model_version": k[0],
                            "release_version": k[1],
                            "current": cur_fp_rate,
                            "previous": prev_fp_rate,
                            "delta": cur_fp_rate - prev_fp_rate,
                            "samples_auto_added": cur_auto,
                        }
                    )

        return {
            "success": True,
            "window_days": days,
            "min_samples": min_samples,
            "alerts": alerts,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to compute regressions: {e}")
