from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.core.database import get_db_client
from app.core.events import emit_event
from app.core.migration_telemetry import emit_shadow_report
from app.core.schema_migration import current_rollout_phase
from app.core.settings import settings
from app.core.unit_converter import UnitConverter


def _canonical_unit(unit: Optional[str]) -> str:
    """Normalize unit strings into UnitConverter-compatible unit names."""
    try:
        s = str(unit or "").strip().lower()
        if not s:
            return ""
        s = " ".join(s.split())

        aliases = {
            # Weight
            "g": "grams",
            "gram": "grams",
            "grams": "grams",
            "kgs": "kg",
            "kilogram": "kg",
            "kilograms": "kg",
            "mg": "mg",
            "milligram": "mg",
            "milligrams": "mg",
            "oz": "oz",
            "ounce": "oz",
            "ounces": "oz",
            "lb": "lb",
            "lbs": "lb",
            "pound": "lb",
            "pounds": "lb",

            # Volume
            "ml": "ml",
            "milliliter": "ml",
            "milliliters": "ml",
            "millilitre": "ml",
            "millilitres": "ml",
            "l": "liters",
            "liter": "liters",
            "liters": "liters",
            "litre": "liters",
            "litres": "liters",
            "cup": "cups",
            "cups": "cups",
            "tablespoon": "tbsp",
            "tablespoons": "tbsp",
            "tbsp": "tbsp",
            "teaspoon": "tsp",
            "teaspoons": "tsp",
            "tsp": "tsp",
            "floz": "fl oz",
            "fl_oz": "fl oz",
            "fl-oz": "fl oz",
            "fl oz": "fl oz",
            "gal": "gallon",
            "gallon": "gallon",
            "gallons": "gallon",
            "pt": "pint",
            "pint": "pint",
            "pints": "pint",
            "qt": "quart",
            "quart": "quart",
            "quarts": "quart",

            # Count
            "pc": "pieces",
            "pcs": "pieces",
            "piece": "pieces",
            "pieces": "pieces",
            "each": "pieces",
            "item": "items",
            "items": "items",
            "clove": "cloves",
            "cloves": "cloves",
            "slice": "slices",
            "slices": "slices",
            "leaf": "leaves",
            "leaves": "leaves",
            "can": "cans",
            "cans": "cans",
            "package": "packages",
            "packages": "packages",
        }
        return aliases.get(s, s)
    except Exception:
        return ""


def _accumulate_normalized_quantity(
    *,
    item: Dict[str, Any],
    totals: Dict[str, float],
    unknown_units: Dict[str, int],
    count_breakdown: Optional[Dict[str, float]] = None,
) -> None:
    """Accumulate canonicalized quantity totals.

    Canonical policy:
      - weight -> grams
      - volume -> ml
      - count  -> pieces
    """
    try:
        qty_raw = item.get("quantity")
        unit_raw = item.get("unit")
        if qty_raw is None:
            return
        try:
            qty = float(qty_raw)
        except Exception:
            return
        unit = _canonical_unit(unit_raw)
        if not unit:
            unknown_units[""] = unknown_units.get("", 0) + 1
            return

        cat = UnitConverter.get_unit_category(unit)
        if cat == "weight":
            totals["grams"] += float(UnitConverter.convert(qty, unit, "grams"))
            return
        if cat == "volume":
            totals["ml"] += float(UnitConverter.convert(qty, unit, "ml"))
            return
        if cat == "count":
            totals["pieces"] += float(UnitConverter.convert(qty, unit, "pieces"))
            if isinstance(count_breakdown, dict):
                count_breakdown[unit] = float(count_breakdown.get(unit, 0.0)) + float(qty)
            return

        unknown_units[unit] = unknown_units.get(unit, 0) + 1
    except Exception:
        return


def _canonicalize_totals(base_totals: Dict[str, float]) -> Dict[str, Any]:
    """Derive canonical totals from base totals (grams/ml/pieces)."""
    try:
        weight_u = _canonical_unit(settings.qty_canonical_weight_unit) or "grams"
        vol_u = _canonical_unit(settings.qty_canonical_volume_unit) or "ml"
        count_u = _canonical_unit(settings.qty_canonical_count_unit) or "pieces"

        # Convert from base units.
        grams = float(base_totals.get("grams", 0.0) or 0.0)
        ml = float(base_totals.get("ml", 0.0) or 0.0)
        pieces = float(base_totals.get("pieces", 0.0) or 0.0)

        weight_val = float(UnitConverter.convert(grams, "grams", weight_u)) if weight_u else grams
        vol_val = float(UnitConverter.convert(ml, "ml", vol_u)) if vol_u else ml
        count_val = float(UnitConverter.convert(pieces, "pieces", count_u)) if count_u else pieces

        return {
            "policy": {"weight": weight_u, "volume": vol_u, "count": count_u, "count_breakdown": settings.qty_count_breakdown},
            "totals": {"weight": weight_val, "volume": vol_val, "count": count_val},
        }
    except Exception:
        return {
            "policy": {"weight": "grams", "volume": "ml", "count": "pieces", "count_breakdown": False},
            "totals": {
                "weight": float(base_totals.get("grams", 0.0) or 0.0),
                "volume": float(base_totals.get("ml", 0.0) or 0.0),
                "count": float(base_totals.get("pieces", 0.0) or 0.0),
            },
        }


def _inventory_status(item: Dict[str, Any], *, now: datetime, maybe_days: int, stale_days: int) -> str:
    """Mirror of scanning._inventory_status logic for shadow validation.

    Keep intentionally conservative and aligned with user-visible behavior.
    """
    try:
        if not bool(item.get("is_current", True)):
            return "inactive"

        last_seen_at = item.get("last_seen_at") or item.get("updated_at")
        if not last_seen_at:
            return "available"

        try:
            # Allow Z.
            s = str(last_seen_at)
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            ts = datetime.fromisoformat(s)
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            age_days = (now - ts.astimezone(timezone.utc)).total_seconds() / 86400.0
        except Exception:
            return "available"

        if age_days >= float(stale_days):
            return "stale"
        if age_days >= float(maybe_days):
            return "maybe"
        return "available"
    except Exception:
        return "available"


def run_pantry_shadow_validation(
    *,
    user_id: str,
    include_inactive: bool,
    maybe_days: int,
    stale_days: int,
    v1_visible_count: int,
    v1_total_count: int,
    v1_qty_sum: float,
    correlation_id: Optional[str] = None,
) -> None:
    """Background shadow read validator for pantry.

    - Never raises
    - Emits schema.v2_shadow_report (rich metrics + samples)
    - Emits schema.v2_shadow_divergence (simple count delta)
    """
    try:
        db = get_db_client()
        now = datetime.now(timezone.utc)

        items2 = (
            db.table("inventory_items_v2")
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )

        v2_total = len(items2.data or [])
        v2_visible = 0
        v2_qty_sum = 0.0
        v2_norm_totals = {"grams": 0.0, "ml": 0.0, "pieces": 0.0}
        v2_unknown_units: Dict[str, int] = {}
        v2_count_breakdown: Optional[Dict[str, float]] = {} if settings.qty_count_breakdown else None
        v2_by_id: Dict[str, Dict[str, Any]] = {}

        for item in items2.data or []:
            if not isinstance(item, dict):
                continue
            status = _inventory_status(item, now=now, maybe_days=maybe_days, stale_days=stale_days)
            if not include_inactive and status in {"inactive", "stale"}:
                continue
            v2_visible += 1
            try:
                v2_qty_sum += float(item.get("quantity") or 0.0)
            except Exception:
                pass
            _accumulate_normalized_quantity(
                item=item,
                totals=v2_norm_totals,
                unknown_units=v2_unknown_units,
                count_breakdown=v2_count_breakdown,
            )
            if item.get("id"):
                v2_by_id[str(item.get("id"))] = item

        mismatches = 0
        compared = 0
        samples: List[Dict[str, Any]] = []

        items1 = (
            db.table("inventory_items")
            .select(
                "id,canonical_name,quantity,unit,storage_location,item_state,source,is_current,pantry_status,last_seen_at,updated_at"
            )
            .eq("user_id", user_id)
            .execute()
        )

        v1_norm_totals = {"grams": 0.0, "ml": 0.0, "pieces": 0.0}
        v1_unknown_units: Dict[str, int] = {}
        v1_visible_recomputed = 0
        v1_count_breakdown: Optional[Dict[str, float]] = {} if settings.qty_count_breakdown else None
        for it in items1.data or []:
            if not isinstance(it, dict):
                continue

            status1 = _inventory_status(it, now=now, maybe_days=maybe_days, stale_days=stale_days)
            if not include_inactive and status1 in {"inactive", "stale"}:
                continue
            v1_visible_recomputed += 1
            _accumulate_normalized_quantity(
                item=it,
                totals=v1_norm_totals,
                unknown_units=v1_unknown_units,
                count_breakdown=v1_count_breakdown,
            )

            iid = it.get("id")
            if not iid:
                continue
            iid_s = str(iid)
            v2 = v2_by_id.get(iid_s)
            if not v2:
                continue
            compared += 1

            fields = [
                "canonical_name",
                "quantity",
                "unit",
                "storage_location",
                "item_state",
                "source",
                "is_current",
                "pantry_status",
            ]
            diff: Dict[str, Any] = {}
            for f in fields:
                v1v = it.get(f)
                v2v = v2.get(f)
                if v1v != v2v:
                    diff[f] = {"v1": v1v, "v2": v2v}

            if diff:
                mismatches += 1
                if len(samples) < 10:
                    samples.append({"id": iid_s, "diff": diff})

        mismatch_rate = (float(mismatches) / float(compared)) if compared else 0.0

        v1_norm_delta = {
            "grams": v2_norm_totals["grams"] - v1_norm_totals["grams"],
            "ml": v2_norm_totals["ml"] - v1_norm_totals["ml"],
            "pieces": v2_norm_totals["pieces"] - v1_norm_totals["pieces"],
        }

        v1_canonical = _canonicalize_totals(v1_norm_totals)
        v2_canonical = _canonicalize_totals(v2_norm_totals)
        canonical_delta = {
            "weight": float(v2_canonical.get("totals", {}).get("weight", 0.0) or 0.0)
            - float(v1_canonical.get("totals", {}).get("weight", 0.0) or 0.0),
            "volume": float(v2_canonical.get("totals", {}).get("volume", 0.0) or 0.0)
            - float(v1_canonical.get("totals", {}).get("volume", 0.0) or 0.0),
            "count": float(v2_canonical.get("totals", {}).get("count", 0.0) or 0.0)
            - float(v1_canonical.get("totals", {}).get("count", 0.0) or 0.0),
        }

        emit_shadow_report(
            user_id=user_id,
            endpoint="GET /api/scanning/pantry",
            correlation_id=correlation_id,
            payload={
                "kind": "pantry_shadow_validation",
                "include_inactive": include_inactive,
                "maybe_days": maybe_days,
                "stale_days": stale_days,
                "canonical_unit_policy": v1_canonical.get("policy"),
                "v1": {
                    "total": v1_total_count,
                    "visible": v1_visible_count,
                    "qty_sum": v1_qty_sum,
                    "qty_normalized": {
                        "grams": v1_norm_totals["grams"],
                        "ml": v1_norm_totals["ml"],
                        "pieces": v1_norm_totals["pieces"],
                        "unknown_unit_items": sum(v1_unknown_units.values()),
                        "unknown_units": v1_unknown_units,
                    },
                    "qty_normalized_canonical": v1_canonical.get("totals"),
                    **({"count_breakdown": v1_count_breakdown} if isinstance(v1_count_breakdown, dict) else {}),
                    "visible_recomputed": v1_visible_recomputed,
                },
                "v2": {
                    "total": v2_total,
                    "visible": v2_visible,
                    "qty_sum": v2_qty_sum,
                    "qty_normalized": {
                        "grams": v2_norm_totals["grams"],
                        "ml": v2_norm_totals["ml"],
                        "pieces": v2_norm_totals["pieces"],
                        "unknown_unit_items": sum(v2_unknown_units.values()),
                        "unknown_units": v2_unknown_units,
                    },
                    "qty_normalized_canonical": v2_canonical.get("totals"),
                    **({"count_breakdown": v2_count_breakdown} if isinstance(v2_count_breakdown, dict) else {}),
                },
                "deltas": {
                    "visible_count_delta": v2_visible - v1_visible_count,
                    "total_count_delta": v2_total - v1_total_count,
                    "qty_sum_delta": v2_qty_sum - v1_qty_sum,
                    "qty_normalized_delta": v1_norm_delta,
                    "qty_normalized_canonical_delta": canonical_delta,
                },
                "entity_compare": {
                    "compared": compared,
                    "mismatches": mismatches,
                    "mismatch_rate": mismatch_rate,
                    "samples": samples,
                },
            },
        )

        if v1_visible_count != v2_visible or v1_total_count != v2_total:
            emit_event(
                event_type="schema.v2_shadow_divergence",
                event_ts=datetime.now(timezone.utc).isoformat(),
                user_id=user_id,
                payload={
                    "endpoint": "GET /api/scanning/pantry",
                    "kind": "pantry_counts",
                    "rollout_phase": current_rollout_phase(),
                    "include_inactive": include_inactive,
                    "maybe_days": maybe_days,
                    "stale_days": stale_days,
                    "v1": {"total": v1_total_count, "visible": v1_visible_count},
                    "v2": {"total": v2_total, "visible": v2_visible},
                },
            )

    except Exception:
        return
