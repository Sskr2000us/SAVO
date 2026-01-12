"""
Scanning API Routes
Endpoints for pantry/fridge scanning with Vision AI
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Header, BackgroundTasks
from typing import Any, List, Dict, Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
import io
import statistics
import os
import hashlib
import time

from pydantic import BaseModel, Field

from PIL import Image, ImageFilter, ImageStat

from app.middleware.auth import get_current_user
from app.core.database import get_db_client
from app.core.vision_api import get_vision_client
from app.core.ingredient_normalization import get_normalizer
from app.api.routes.profile import get_full_profile
from app.core.media_storage import upload_inventory_image, to_signed_url
from app.core.events import emit_event, emit_events
from app.core.observations import log_scan_observations
from app.core.schema_migration import (
    current_rollout_phase,
    dual_write_enabled,
    inventory_truth_read_table_for_user,
    inventory_truth_write_table,
    should_read_v2_for_user,
    v2_shadow_read_enabled,
)
from app.core.migration_telemetry import emit_migration_incident
from app.core.shadow_validation import run_pantry_shadow_validation

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scanning", tags=["scanning"])


def _resolve_master_ingredient_id(db, name: str) -> Optional[str]:
    """Best-effort resolve a master ingredient UUID from a name.

    Uses canonical name first, then aliases. If the matched ingredient is deprecated
    and has a replacement, follows `replaced_by_id` (up to a few hops).
    """

    def _follow_redirect(ingredient_row: Optional[Dict[str, Any]]) -> Optional[str]:
        seen = set()
        hops = 0
        row = ingredient_row
        while row and hops < 5:
            ing_id = row.get("id")
            if not ing_id or ing_id in seen:
                break
            seen.add(ing_id)
            status = (row.get("status") or "").strip().lower()
            replaced_by = row.get("replaced_by_id")
            if status != "deprecated" or not replaced_by:
                return str(ing_id)
            try:
                next_row = (
                    db.table("master_ingredients")
                    .select("id,status,replaced_by_id")
                    .eq("id", str(replaced_by))
                    .limit(1)
                    .execute()
                )
                row = next_row.data[0] if next_row.data else None
            except Exception:
                break
            hops += 1
        return str(row.get("id")) if row and row.get("id") else None

    n = (name or "").strip()
    if not n:
        return None

    # 1) canonical_name match
    try:
        res = (
            db.table("master_ingredients")
            .select("id,status,replaced_by_id")
            .ilike("canonical_name", n)
            .limit(1)
            .execute()
        )
        if res.data:
            return _follow_redirect(res.data[0])
    except Exception:
        pass

    # 2) alias match
    try:
        alias = (
            db.table("ingredient_aliases")
            .select("ingredient_id")
            .ilike("alias_name", n)
            .limit(1)
            .execute()
        )
        if alias.data and alias.data[0].get("ingredient_id"):
            ing_id = str(alias.data[0]["ingredient_id"])
            mi = (
                db.table("master_ingredients")
                .select("id,status,replaced_by_id")
                .eq("id", ing_id)
                .limit(1)
                .execute()
            )
            if mi.data:
                return _follow_redirect(mi.data[0])
            return ing_id
    except Exception:
        pass

    return None


def _resolve_inventory_taxonomy(
    db,
    *,
    canonical_name: str,
    ingredient_id: Optional[str] = None,

) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Resolve (category, subcategory, cuisine) from master_ingredients.

    Best-effort only; returns (None, None, None) if the taxonomy cannot be resolved.
    """

    cid = (canonical_name or "").strip()
    ing_id = (ingredient_id or "").strip() or None

    def _norm_token(s: Any) -> Optional[str]:
        if s is None:
            return None
        txt = str(s).strip().lower()
        if not txt:
            return None
        txt = txt.replace(" ", "_").replace("-", "_")
        while "__" in txt:
            txt = txt.replace("__", "_")
        return txt

    # App taxonomy expects plural-ish buckets in some cases.
    _CATEGORY_CANON = {
        "grain": "grains",
        "grains": "grains",
        "pulse": "pulses",
        "pulses": "pulses",
        "spice": "spices",
        "spices": "spices",
        "vegetable": "vegetables",
        "vegetables": "vegetables",
        "fruit": "fruits",
        "fruits": "fruits",
        "protein": "proteins",
        "proteins": "proteins",
        "oil": "oils",
        "oils": "oils",
    }

    def _pick(row: Optional[Dict[str, Any]]) -> tuple[Optional[str], Optional[str], Optional[str]]:
        if not row or not isinstance(row, dict):
            return None, None, None
        cat_s = _norm_token(row.get("category"))
        sub_s = _norm_token(row.get("subcategory"))
        cui_s = _norm_token(row.get("cuisine"))

        if cat_s and cat_s in _CATEGORY_CANON:
            cat_s = _CATEGORY_CANON[cat_s]
        # Basic plural normalization for common subcategories.
        if sub_s == "lentil":
            sub_s = "lentils"
        elif sub_s == "bean":
            sub_s = "beans"
        elif sub_s == "chickpea":
            sub_s = "chickpeas"

        return (cat_s or None), (sub_s or None), (cui_s or None)

    def _select_taxonomy_by_id(_id: str) -> Optional[Dict[str, Any]]:
        # Some deployments don't have master_ingredients.cuisine; don't let that break category/subcategory.
        try:
            res = (
                db.table("master_ingredients")
                .select("category, subcategory, cuisine")
                .eq("id", _id)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
        except Exception:
            pass
        try:
            res = (
                db.table("master_ingredients")
                .select("category, subcategory")
                .eq("id", _id)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
        except Exception:
            pass
        return None

    def _select_taxonomy_by_name(_name: str) -> Optional[Dict[str, Any]]:
        try:
            res = (
                db.table("master_ingredients")
                .select("category, subcategory, cuisine")
                .eq("canonical_name", _name)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
        except Exception:
            pass
        try:
            res = (
                db.table("master_ingredients")
                .select("category, subcategory")
                .eq("canonical_name", _name)
                .limit(1)
                .execute()
            )
            if res.data:
                return res.data[0]
        except Exception:
            pass
        return None

    # 1) Direct by ingredient_id
    if ing_id:
        row = _select_taxonomy_by_id(ing_id)
        if row:
            return _pick(row)

    # 2) Fallback by canonical_name
    if cid:
        row = _select_taxonomy_by_name(cid)
        if row:
            return _pick(row)

    return None, None, None


def _anonymized_item_signature(user_id: str, detected_item: Dict[str, Any], extra: Optional[Dict[str, Any]] = None) -> str:
    """Return a stable, anonymized signature for an item-like entity.

    This is intended for ML learning logs, not for security.
    Uses SHA-256 over non-PII-ish attributes + a server-side salt.
    """
    salt = os.getenv("SAVO_ANON_SIG_SALT", "")
    md = detected_item.get("metadata") if isinstance(detected_item, dict) else None
    if not isinstance(md, dict):
        md = {}
    bbox = detected_item.get("bbox") if isinstance(detected_item, dict) else None
    if isinstance(bbox, dict):
        try:
            bbox_norm = {
                "x": round(float(bbox.get("x") or 0.0), 3),
                "y": round(float(bbox.get("y") or 0.0), 3),
                "w": round(float(bbox.get("width") or 0.0), 3),
                "h": round(float(bbox.get("height") or 0.0), 3),
            }
        except Exception:
            bbox_norm = {}
    else:
        bbox_norm = {}

    payload = {
        "u": str(user_id),
        "detected_id": str(detected_item.get("id") or ""),
        "name": str(detected_item.get("canonical_name") or detected_item.get("detected_name") or ""),
        "container_hash": str(md.get("container_hash") or ""),
        "barcode": str(md.get("barcode") or ""),
        "bbox": bbox_norm,
    }
    if isinstance(extra, dict):
        payload.update(extra)
    raw = (salt + "|" + str(payload)).encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()


def _retry_without_missing_column(db, table: str, op: str, payload: Dict[str, Any], where: Optional[Dict[str, Any]] = None):
    """Best-effort: PostgREST schema cache can lag migrations; retry once removing missing columns."""
    try:
        if op == "insert":
            return db.table(table).insert(payload).execute()
        if op == "update":
            q = db.table(table).update(payload)
            if where:
                for k, v in where.items():
                    q = q.eq(k, v)
            return q.execute()
        raise ValueError("Unsupported op")
    except Exception as e:
        msg = str(e)
        # Common PostgREST error: 'column "foo" of relation "bar" does not exist'
        missing = None
        try:
            import re

            m = re.search(r'column\s+"([a-zA-Z0-9_]+)"\s+of\s+relation', msg)
            if m:
                missing = m.group(1)
            if not missing:
                # Supabase/PostgREST schema cache error style:
                # "Could not find the 'metadata' column of 'detected_ingredients' in the schema cache"
                m2 = re.search(r"Could not find the '([a-zA-Z0-9_]+)' column of '([a-zA-Z0-9_]+)'", msg)
                if m2:
                    missing = m2.group(1)
        except Exception:
            missing = None
        if missing and missing in payload:
            payload = dict(payload)
            payload.pop(missing, None)
            if op == "insert":
                return db.table(table).insert(payload).execute()
            q = db.table(table).update(payload)
            if where:
                for k, v in where.items():
                    q = q.eq(k, v)
            return q.execute()
        raise


def _dual_write_inventory(
    db,
    op: str,
    payload: Dict[str, Any],
    where: Optional[Dict[str, Any]] = None,
    *,
    user_id: Optional[str] = None,
    correlation_id: Optional[str] = None,
    session_id: Optional[str] = None,
    endpoint: Optional[str] = None,
):
    """Write pantry truth to the authoritative table and (optionally) mirror.

    - v1_only: writes V1
    - dual_write: writes V1 + best-effort mirror into V2 (window-gated)
    - v2_only (or v1 writes disabled): writes V2 only

    Returns the primary PostgREST response.
    """
    p = dict(payload or {})
    primary_table = inventory_truth_write_table()

    if op == "insert" and (dual_write_enabled() or primary_table == "inventory_items_v2") and not p.get("id"):
        p["id"] = str(uuid4())

    res = _retry_without_missing_column(db, primary_table, op, p, where=where)

    # Append-only event for replayability (best-effort; must not break flow).
    try:
        from app.core.events import emit_event

        item_after = None
        try:
            item_after = (res.data[0] if getattr(res, "data", None) else None)
        except Exception:
            item_after = None

        if op in {"insert", "update"}:
            emit_event(
                event_type="inventory.item_upserted",
                event_ts=datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
                user_id=user_id,
                entity_type="inventory_item",
                entity_id=str((item_after or {}).get("id") or p.get("id") or "") or None,
                session_id=session_id,
                taxonomy_version=(p.get("taxonomy_version") if isinstance(p, dict) else None),
                model_version=(p.get("model_version") if isinstance(p, dict) else None),
                payload={
                    "op": op,
                    "table": primary_table,
                    "endpoint": endpoint,
                    "where": where or {},
                    **({"correlation_id": correlation_id} if correlation_id else {}),
                    "item": item_after or p,
                },
            )
    except Exception:
        pass

    if dual_write_enabled() and primary_table == "inventory_items":
        try:
            _retry_without_missing_column(db, "inventory_items_v2", op, p, where=where)
        except Exception as e:
            try:
                emit_migration_incident(
                    user_id=user_id,
                    correlation_id=correlation_id,
                    session_id=session_id,
                    incident_type="v2_write_failed",
                    operation=op,
                    v2_target="public.inventory_items_v2",
                    error=str(e),
                    entity_id=(p.get("id") if isinstance(p, dict) else None),
                    payload={
                        "endpoint": endpoint,
                        "where": where,
                        "keys": sorted([k for k in (p or {}).keys()])[:50],
                    },
                )
            except Exception:
                pass

    return res


def _shadow_compare_pantry_v2(
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
    return run_pantry_shadow_validation(
        user_id=user_id,
        include_inactive=include_inactive,
        maybe_days=maybe_days,
        stale_days=stale_days,
        v1_visible_count=v1_visible_count,
        v1_total_count=v1_total_count,
        v1_qty_sum=v1_qty_sum,
        correlation_id=correlation_id,
    )


def _normalize_unit(unit: Optional[str]) -> str:
    u = (unit or "").strip().lower()
    if not u:
        return "pieces"
    if u in {"pcs", "pc", "piece"}:
        return "pieces"
    if u == "g":
        return "grams"
    if u == "l":
        return "liters"
    return u


def _scan_type_to_storage_location(scan_type: Optional[str]) -> str:
    st = (scan_type or "").strip().lower()
    if st in {"pantry", "fridge", "freezer", "counter"}:
        return st
    if st in {"shopping", "other"}:
        return "pantry"
    return "pantry"


def _titleize(name: str) -> str:
    return (name or "").replace("_", " ").strip().title()


def _assess_image_quality(image_data: bytes) -> Dict[str, Any]:
    """Return lightweight image quality signals for capture gating.

    Uses only Pillow (no numpy/opencv) to keep deps minimal.
    """
    try:
        img = Image.open(io.BytesIO(image_data))
        img = img.convert("RGB")
    except Exception:
        return {"ok": False, "issues": ["unreadable"], "metrics": {}}

    # Downscale for speed/consistency.
    try:
        img.thumbnail((640, 640))
    except Exception:
        pass

    gray = img.convert("L")
    stat = ImageStat.Stat(gray)

    brightness_mean = float(stat.mean[0]) if stat.mean else 0.0
    contrast_stddev = float(stat.stddev[0]) if stat.stddev else 0.0

    # Blur proxy: strength of high-frequency content.
    # Lower edge mean => likely blur / out-of-focus.
    try:
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_stat = ImageStat.Stat(edges)
        edge_mean = float(edge_stat.mean[0]) if edge_stat.mean else 0.0
        edge_stddev = float(edge_stat.stddev[0]) if edge_stat.stddev else 0.0
    except Exception:
        edge_mean = 0.0
        edge_stddev = 0.0

    issues: List[str] = []

    # Thresholds tuned conservatively to avoid blocking valid images.
    if brightness_mean < 55:
        issues.append("too_dark")
    elif brightness_mean > 215:
        issues.append("too_bright")

    if contrast_stddev < 18:
        issues.append("low_contrast")

    if edge_mean < 9.5 and edge_stddev < 18:
        issues.append("too_blurry")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "metrics": {
            "brightness_mean": round(brightness_mean, 2),
            "contrast_stddev": round(contrast_stddev, 2),
            "edge_mean": round(edge_mean, 2),
            "edge_stddev": round(edge_stddev, 2),
        },
    }


def _safe_crop_by_bbox(image_data: bytes, bbox: Optional[Dict[str, Any]]) -> Optional[Image.Image]:
    if not bbox or not isinstance(bbox, dict):
        return None
    if not all(k in bbox for k in ["x", "y", "width", "height"]):
        return None

    try:
        img = Image.open(io.BytesIO(image_data)).convert("RGB")
    except Exception:
        return None

    try:
        img_width, img_height = img.size
        x = float(bbox.get("x"))
        y = float(bbox.get("y"))
        w = float(bbox.get("width"))
        h = float(bbox.get("height"))
    except Exception:
        return None

    if img_width <= 1 or img_height <= 1:
        return None

    # Clamp normalized coords.
    x = max(0.0, min(1.0, x))
    y = max(0.0, min(1.0, y))
    w = max(0.0, min(1.0, w))
    h = max(0.0, min(1.0, h))
    if w <= 0.0 or h <= 0.0:
        return None

    left = int(x * img_width)
    top = int(y * img_height)
    right = int((x + w) * img_width)
    bottom = int((y + h) * img_height)

    # Small padding to reduce sensitivity to bbox jitter.
    pad_x = int(max(2, (right - left) * 0.08))
    pad_y = int(max(2, (bottom - top) * 0.08))
    left = max(0, left - pad_x)
    top = max(0, top - pad_y)
    right = min(img_width, right + pad_x)
    bottom = min(img_height, bottom + pad_y)
    if right <= left or bottom <= top:
        return None

    try:
        return img.crop((left, top, right, bottom))
    except Exception:
        return None


def _average_hash(img: Image.Image) -> str:
    """Simple 8x8 aHash for lightweight visual fingerprinting."""
    try:
        gray = img.convert("L").resize((8, 8), Image.Resampling.LANCZOS)
        pixels = list(gray.getdata())
        avg = sum(pixels) / max(1, len(pixels))
        bits = [1 if p >= avg else 0 for p in pixels]
        hex_str = ""
        for i in range(0, 64, 4):
            nibble = (bits[i] << 3) | (bits[i + 1] << 2) | (bits[i + 2] << 1) | bits[i + 3]
            hex_str += format(nibble, "x")
        return hex_str
    except Exception:
        return ""


def _compute_container_hash(image_data: bytes, bbox: Optional[Dict[str, Any]]) -> Optional[str]:
    cropped = _safe_crop_by_bbox(image_data, bbox)
    if cropped is None:
        return None
    ah = _average_hash(cropped)
    return ah or None


def _load_previous_scan_quantities(db, user_id: str) -> Dict[str, Dict[str, Any]]:
    """Load the latest prior scan's detected quantities (best-effort)."""
    try:
        scans = (
            db.table("ingredient_scans")
            .select("id, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        if not scans.data:
            return {}
        prev_scan_id = scans.data[0].get("id")
        if not prev_scan_id:
            return {}

        rows = (
            db.table("detected_ingredients")
            .select("canonical_name, detected_name, detected_quantity, detected_unit")
            .eq("user_id", user_id)
            .eq("scan_id", prev_scan_id)
            .execute()
        )
        out: Dict[str, Dict[str, Any]] = {}
        for r in rows.data or []:
            key = (r.get("canonical_name") or r.get("detected_name") or "").strip().lower()
            if not key:
                continue
            out[key] = {
                "quantity": r.get("detected_quantity"),
                "unit": r.get("detected_unit"),
            }
        return out
    except Exception:
        return {}


def _apply_scan_delta(current: List[Dict[str, Any]], previous: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    current_keys = set()
    new_count = 0
    changed_count = 0

    for det in current:
        if not isinstance(det, dict):
            continue
        key = (det.get("canonical_name") or det.get("detected_name") or "").strip().lower()
        if not key:
            continue
        current_keys.add(key)
        prev = previous.get(key)
        if not prev:
            det["change_status"] = "new"
            new_count += 1
            continue

        prev_q = prev.get("quantity")
        prev_u = prev.get("unit")
        det["previous_quantity"] = prev_q
        det["previous_unit"] = prev_u

        q = det.get("quantity")
        u = det.get("unit")
        try:
            qf = float(q) if q is not None else None
            pqf = float(prev_q) if prev_q is not None else None
        except Exception:
            qf, pqf = None, None

        if qf is None or pqf is None:
            det["change_status"] = "unchanged"
            continue
        if (u or "") and (prev_u or "") and _normalize_unit(u) != _normalize_unit(prev_u):
            det["change_status"] = "unchanged"
            continue

        baseline = max(abs(pqf), 1.0)
        if abs(qf - pqf) / baseline >= 0.25:
            det["change_status"] = "changed"
            changed_count += 1
        else:
            det["change_status"] = "unchanged"

    removed = sorted(list(set(previous.keys()) - current_keys))
    return {
        "new_count": new_count,
        "removed_count": len(removed),
        "changed_count": changed_count,
        "removed_items": [{"name": k} for k in removed[:20]],
    }


def _apply_barcode_hints_to_detections(
    detections: List[Dict[str, Any]],
    barcode_name_hint: Optional[str],
    barcode_quantity_hint: Optional[float],
    barcode_unit_hint: Optional[str],
) -> None:
    """Best-effort: apply barcode hints only when the match is unambiguous.

    Acceptance intent: barcode can improve packaged identity/quantity, but must never be required.

    Safety rules:
    - Apply only if exactly 1 total detection OR exactly 1 packaged detection.
    - Quantity hint overwrites only when missing or low-confidence.
    - Name hint overwrites only when detection confidence isn't already high.
    """

    if not detections:
        return

    bcn = (barcode_name_hint or "").strip()
    bcu = (barcode_unit_hint or "").strip()
    bcq: Optional[float]
    try:
        bcq = float(barcode_quantity_hint) if barcode_quantity_hint is not None else None
    except Exception:
        bcq = None

    if not bcn and bcq is None:
        return

    target: Optional[Dict[str, Any]] = None
    if len(detections) == 1:
        target = detections[0]
    else:
        packaged = [d for d in detections if (d.get("item_form") or "").strip().lower() == "packaged"]
        if len(packaged) == 1:
            target = packaged[0]

    if not isinstance(target, dict):
        return

    if bcq is not None and bcq > 0:
        qc = target.get("quantity_confidence")
        try:
            qc_val = float(qc) if qc is not None else None
        except Exception:
            qc_val = None
        if target.get("quantity") is None or qc_val is None or qc_val < 0.70:
            target["quantity"] = bcq
            if bcu:
                target["unit"] = _normalize_unit(bcu)
            target["quantity_source"] = "barcode"
            target["quantity_confidence"] = 0.95

    if bcn:
        conf = target.get("confidence")
        try:
            conf_val = float(conf) if conf is not None else 0.0
        except Exception:
            conf_val = 0.0
        if conf_val < 0.85:
            try:
                normalizer = get_normalizer()
                target["detected_name"] = bcn
                target["canonical_name"] = normalizer.normalize_name(bcn)
            except Exception:
                target["detected_name"] = bcn


def _get_container_quantity_prior(db, user_id: str, container_hash: str) -> Optional[Dict[str, Any]]:
    """Learn a typical quantity for a reused container fingerprint (jar/tin/etc)."""
    if not container_hash:
        return None
    try:
        rows = None
        try:
            # Prefer server-side filtering (JSON path) when supported.
            rows = (
                db.table("detected_ingredients")
                .select("detected_quantity, detected_unit, confirmation_status")
                .eq("user_id", user_id)
                .eq("metadata->>container_hash", container_hash)
                .order("created_at", desc=True)
                .limit(50)
                .execute()
            )
        except Exception:
            rows = None

        if rows is None:
            # Fallback: fetch recent rows and filter metadata client-side.
            recent = (
                db.table("detected_ingredients")
                .select("detected_quantity, detected_unit, confirmation_status, metadata")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(200)
                .execute()
            )
            filtered = []
            for r in recent.data or []:
                md = r.get("metadata")
                if isinstance(md, dict) and (md.get("container_hash") == container_hash):
                    filtered.append(r)
            rows = type("_Rows", (), {"data": filtered})

        samples: List[float] = []
        units: List[str] = []
        for r in rows.data or []:
            if r.get("confirmation_status") not in {"confirmed", "modified"}:
                continue
            q = r.get("detected_quantity")
            u = r.get("detected_unit")
            try:
                qf = float(q)
            except Exception:
                continue
            if qf <= 0:
                continue
            samples.append(qf)
            units.append(_normalize_unit(u))

        if len(samples) < 2:
            return None

        unit = max(set(units), key=lambda x: units.count(x)) if units else "pieces"
        median_qty = float(statistics.median(samples))
        confidence = min(0.95, 0.60 + 0.05 * len(samples))
        return {
            "quantity": median_qty,
            "unit": unit,
            "sample_count": len(samples),
            "confidence": confidence,
        }
    except Exception:
        return None


def _parse_ts(ts: Any) -> Optional[datetime]:
    if ts is None:
        return None
    if isinstance(ts, datetime):
        dt = ts
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    if not isinstance(ts, str):
        return None
    raw = ts.strip()
    if not raw:
        return None
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _effective_seen_at(item: Dict[str, Any]) -> Optional[datetime]:
    for k in ("last_seen_at", "updated_at", "created_at"):
        dt = _parse_ts(item.get(k))
        if dt:
            return dt
    return None


def _inventory_status(
    item: Dict[str, Any],
    now: datetime,
    maybe_days: int,
    stale_days: int,
) -> str:
    # If the row is explicitly inactive, treat it as inactive regardless of time.
    if item.get("is_current") is False:
        return "inactive"

    # Defensive: normalize to tz-aware UTC so date math never fails.
    if isinstance(now, datetime) and now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    elif isinstance(now, datetime) and now.tzinfo is not None:
        now = now.astimezone(timezone.utc)

    seen_at = _effective_seen_at(item)
    if not seen_at:
        return "maybe"

    if seen_at.tzinfo is None:
        seen_at = seen_at.replace(tzinfo=timezone.utc)
    else:
        seen_at = seen_at.astimezone(timezone.utc)

    age_days = (now - seen_at).days
    if stale_days > 0 and age_days >= stale_days:
        return "stale"
    if maybe_days > 0 and age_days >= maybe_days:
        return "maybe"
    return "available"


# ============================================================================
# Request/Response Models
# ============================================================================

class AnalyzeImageRequest(BaseModel):
    """Request model for image analysis"""
    scan_type: str = Field(default="pantry", pattern="^(pantry|fridge|counter|shopping|other)$")
    location_hint: Optional[str] = None


class DetectedIngredient(BaseModel):
    """Detected ingredient with confidence and alternatives"""
    id: str
    detected_name: str
    canonical_name: Optional[str]
    confidence: Decimal
    confidence_category: str  # "high", "medium", "low"
    category: str
    item_form: Optional[str] = None  # packaged|loose|unknown
    quantity: Optional[float] = None
    unit: Optional[str] = None
    quantity_confidence: Optional[float] = None
    quantity_source: Optional[str] = None
    change_status: Optional[str] = None  # new|changed|unchanged
    previous_quantity: Optional[float] = None
    previous_unit: Optional[str] = None
    close_alternatives: List[Dict] = []
    visual_similarity_group: Optional[str]
    allergen_warnings: List[Dict] = []
    bbox: Optional[Dict] = None
    confirmation_status: str = "pending"
    # Visual verification fields
    thumbnail_url: Optional[str] = None  # Cropped image of this ingredient
    full_image_url: Optional[str] = None  # Full scan image for reference


class AnalyzeImageResponse(BaseModel):
    """Response from image analysis"""
    success: bool
    scan_id: str
    ingredients: List[DetectedIngredient]
    metadata: Dict
    requires_confirmation: bool
    message: Optional[str] = None


class ConfirmIngredientsRequest(BaseModel):
    """Request to confirm detected ingredients"""
    scan_id: str
    confirmations: List[Dict] = Field(
        ...,
        description="List of {detected_id, action, confirmed_name, quantity, unit}",
        example=[
            {"detected_id": "abc123", "action": "confirmed", "confirmed_name": "spinach", "quantity": 200, "unit": "grams"},
            {"detected_id": "def456", "action": "rejected"},
            {"detected_id": "ghi789", "action": "modified", "confirmed_name": "kale", "quantity": 150, "unit": "grams"}
        ]
    )


class ConfirmIngredientsResponse(BaseModel):
    """Response after confirmation"""
    success: bool
    confirmed_count: int
    rejected_count: int
    modified_count: int
    pantry_items_added: List[Dict]
    message: str


class ScanHistoryResponse(BaseModel):
    """User's scan history"""
    scans: List[Dict]
    total_scans: int
    accuracy_stats: Dict


class SubmitFeedbackRequest(BaseModel):
    """User feedback on detection quality"""
    scan_id: str
    detected_id: Optional[str] = None
    feedback_type: str = Field(pattern="^(correction|missing|false_positive|rating|comment)$")
    detected_name: Optional[str] = None
    correct_name: Optional[str] = None
    overall_rating: Optional[int] = Field(None, ge=1, le=5)
    accuracy_rating: Optional[int] = Field(None, ge=1, le=5)


class BarcodeLookupResponse(BaseModel):
    success: bool
    found: bool
    barcode: str
    product: Optional[Dict[str, Any]] = None
    message: Optional[str] = None
    speed_rating: Optional[int] = Field(None, ge=1, le=5)
    comment: Optional[str] = None


class ScanReceiptResponse(BaseModel):
    success: bool
    receipt_id: str
    added_count: int
    updated_count: int
    pantry_items: List[Dict]
    metadata: Dict
    message: Optional[str] = None


class ScanReceiptPreviewResponse(BaseModel):
    success: bool
    receipt_id: str
    items: List[Dict]
    metadata: Dict
    requires_confirmation: bool = True
    message: Optional[str] = None


class ReceiptConfirmItem(BaseModel):
    raw_name: Optional[str] = None
    canonical_name: Optional[str] = None
    display_name: Optional[str] = None
    quantity: Optional[float] = None
    unit: Optional[str] = None
    confidence: Optional[float] = None


class ConfirmReceiptRequest(BaseModel):
    receipt_id: str
    items: List[ReceiptConfirmItem]
    storage_location: str = "pantry"


class PantryCleanupResponse(BaseModel):
    success: bool
    marked_inactive_count: int
    stale_days: int
    message: str


class PantrySummaryResponse(BaseModel):
    success: bool
    have: List[Dict]
    maybe_have: List[Dict]
    verify: List[Dict]
    totals: Dict[str, int]


# ============================================================================
# Endpoints
# ============================================================================

@router.post("/analyze-image", response_model=AnalyzeImageResponse)
async def analyze_image(
    image: UploadFile = File(..., description="Image file (JPEG/PNG)"),
    scan_type: str = Form(default="pantry"),
    location_hint: Optional[str] = Form(default=None),
    session_id: Optional[str] = Form(default=None),
    barcode: Optional[str] = Form(default=None),
    barcode_name_hint: Optional[str] = Form(default=None),
    barcode_quantity_hint: Optional[float] = Form(default=None),
    barcode_unit_hint: Optional[str] = Form(default=None),
    x_app_version: Optional[str] = Header(default=None, alias="X-App-Version"),
    user_id: str = Depends(get_current_user)
):
    """
    Analyze pantry/fridge image and detect ingredients
    
    - **image**: Image file to analyze
    - **scan_type**: Type of scan (pantry/fridge/counter/shopping/other)
    - **location_hint**: Optional hint about location
    
    Returns detected ingredients with confidence scores and close alternatives
    """
    try:
        db = get_db_client()
        now_iso = datetime.now(timezone.utc).isoformat()

        event_rows: List[Dict[str, Any]] = []

        correlation_id: Optional[str] = None
        if session_id:
            try:
                sres = (
                    db.table("scan_sessions")
                    .select("correlation_id")
                    .eq("id", session_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                if sres.data and isinstance(sres.data[0], dict):
                    correlation_id = (sres.data[0].get("correlation_id") or None)
            except Exception:
                correlation_id = None

        # Validate image file
        if image.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
            raise HTTPException(status_code=400, detail="Invalid image format. Use JPEG or PNG.")
        
        # Read image data
        image_data = await image.read()

        # Best-effort: session bookkeeping (received a frame)
        if session_id:
            try:
                sess = (
                    db.table("scan_sessions")
                    .select("frames_received,frames_usable")
                    .eq("id", session_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                if sess.data:
                    fr = int(sess.data[0].get("frames_received") or 0) + 1
                    fu = int(sess.data[0].get("frames_usable") or 0)
                    db.table("scan_sessions").update(
                        {
                            "frames_received": fr,
                            "frames_usable": fu,
                            "stage": "processing",
                            "updated_at": now_iso,
                        }
                    ).eq("id", session_id).eq("user_id", user_id).execute()
            except Exception:
                pass
        
        if len(image_data) > 10 * 1024 * 1024:  # 10MB limit
            raise HTTPException(status_code=400, detail="Image too large. Maximum 10MB.")

        # Capture-quality gate (prevents wasting Vision calls on unusable frames).
        quality = _assess_image_quality(image_data)
        if not quality.get("ok"):
            issues = quality.get("issues") or []
            metrics = quality.get("metrics") or {}

            if session_id:
                try:
                    db.table("scan_sessions").update(
                        {
                            "stage": "collecting_frames",
                            "last_quality_issues": issues,
                            "updated_at": now_iso,
                        }
                    ).eq("id", session_id).eq("user_id", user_id).execute()
                except Exception:
                    pass

            # Keep message short and actionable.
            if "too_dark" in issues:
                msg = "Too dark — turn on lights and retake."
            elif "too_blurry" in issues:
                msg = "Too blurry — hold steady and retake."
            elif "too_bright" in issues:
                msg = "Too bright/glare — adjust angle and retake."
            else:
                msg = "Image quality too low — please retake."

            raise HTTPException(
                status_code=400,
                detail={
                    "code": "image_quality",
                    "message": msg,
                    "issues": issues,
                    "metrics": metrics,
                },
            )
        
        # Get user profile for context
        profile = await get_full_profile(user_id)
        
        # Analyze image with Vision API
        started = time.perf_counter()
        vision_client = get_vision_client()
        model_version = getattr(vision_client, "model", None)
        model_provider = "openai"
        analysis_result = await vision_client.analyze_image(
            image_data=image_data,
            scan_type=scan_type,
            location_hint=location_hint,
            user_preferences=profile,
            barcode=(barcode or None),
            barcode_name_hint=(barcode_name_hint or None),
            barcode_quantity_hint=barcode_quantity_hint,
            barcode_unit_hint=_normalize_unit(barcode_unit_hint) if barcode_unit_hint else None,
        )
        
        if not analysis_result["success"]:
            raise HTTPException(status_code=500, detail=f"Vision analysis failed: {analysis_result.get('error')}")

        analysis_ms = int(max(0.0, (time.perf_counter() - started) * 1000.0))
        release_version = (os.getenv("SAVO_RELEASE_VERSION") or os.getenv("SAVO_RELEASE") or "").strip() or None
        app_version = (x_app_version or "").strip() or None

        # If barcode hints were provided, apply them only when unambiguous.
        _apply_barcode_hints_to_detections(
            analysis_result.get("ingredients") or [],
            barcode_name_hint=barcode_name_hint,
            barcode_quantity_hint=barcode_quantity_hint,
            barcode_unit_hint=barcode_unit_hint,
        )
        
        # Create scan record in database
        scan_id = str(uuid4())

        # Best-effort delta baseline (latest prior scan).
        previous_quantities = _load_previous_scan_quantities(db, user_id)

        # Upload image to Supabase Storage (best-effort)
        image_url = None
        try:
            expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
            image_url = upload_inventory_image(
                user_id=user_id,
                content=image_data,
                content_type=image.content_type,
                asset_type="scan_reference",
                source="scan",
                expires_at=expires_at,
                links={"scan_id": scan_id},
            )
        except Exception as e:
            logger.warning(f"Failed to upload scan image: {e}")
        
        # Estimate API cost
        api_cost = await vision_client.estimate_api_cost(image_data)
        
        # Insert scan record
        scan_record_payload = {
            "id": scan_id,
            "user_id": user_id,
            "image_url": image_url,
            "image_hash": analysis_result["metadata"]["image_hash"],
            "image_metadata": {
                "width": analysis_result["metadata"]["image_size"][0],
                "height": analysis_result["metadata"]["image_size"][1],
                "format": image.content_type,
                "size_bytes": len(image_data),
                **({"barcode": (barcode or "").strip()} if (barcode or "").strip() else {}),
                **({"barcode_name_hint": (barcode_name_hint or "").strip()} if (barcode_name_hint or "").strip() else {}),
                **({"barcode_quantity_hint": barcode_quantity_hint} if barcode_quantity_hint is not None else {}),
                **({"barcode_unit_hint": _normalize_unit(barcode_unit_hint)} if (barcode_unit_hint or "").strip() else {}),
                **({"model_version": model_version} if model_version else {}),
                "model_provider": model_provider,
                "analysis_ms": analysis_ms,
                **({"release_version": release_version} if release_version else {}),
                **({"app_version": app_version} if app_version else {}),
                **({"session_id": session_id} if session_id else {}),
                **({"correlation_id": correlation_id} if correlation_id else {}),
            },
            "scan_type": scan_type,
            "location_hint": location_hint,
            "status": "processing",
            "vision_provider": "openai",
            "api_cost_cents": api_cost,
            **({"session_id": session_id} if session_id else {}),
            **({"correlation_id": correlation_id} if correlation_id else {}),
            **({"model_version": model_version} if model_version else {}),
            "model_provider": model_provider,
            "analysis_ms": analysis_ms,
            **({"release_version": release_version} if release_version else {}),
            **({"app_version": app_version} if app_version else {}),
        }
        _retry_without_missing_column(db, "ingredient_scans", "insert", scan_record_payload)

        if session_id:
            try:
                sess = (
                    db.table("scan_sessions")
                    .select("frames_received,frames_usable,metadata")
                    .eq("id", session_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                if sess.data:
                    fr = int(sess.data[0].get("frames_received") or 0)
                    fu = int(sess.data[0].get("frames_usable") or 0) + 1
                    md = sess.data[0].get("metadata")
                    if not isinstance(md, dict):
                        md = {}
                    md = dict(md)
                    md["last_scan_id"] = scan_id
                    db.table("scan_sessions").update(
                        {
                            "frames_received": fr,
                            "frames_usable": fu,
                            "stage": "completed",
                            "last_quality_issues": [],
                            "metadata": md,
                            "updated_at": now_iso,
                        }
                    ).eq("id", session_id).eq("user_id", user_id).execute()
            except Exception:
                pass
        
        # Pre-pass: container fingerprint + learned quantity priors.
        for ingredient_data in analysis_result["ingredients"]:
            container_hash = _compute_container_hash(image_data, ingredient_data.get("bbox"))
            if container_hash:
                ingredient_data["container_hash"] = container_hash
                prior = _get_container_quantity_prior(db, user_id, container_hash)
                if prior is not None:
                    qc = ingredient_data.get("quantity_confidence")
                    try:
                        qc_val = float(qc) if qc is not None else None
                    except Exception:
                        qc_val = None
                    if ingredient_data.get("quantity") is None or qc_val is None or qc_val < 0.65:
                        ingredient_data["quantity"] = prior.get("quantity")
                        ingredient_data["unit"] = prior.get("unit")
                        ingredient_data["quantity_source"] = "container_history"
                        ingredient_data["quantity_confidence"] = float(prior.get("confidence") or 0.75)
                        ingredient_data["container_match_count"] = int(prior.get("sample_count") or 0)

        # Annotate delta vs previous scan and include a summary in metadata.
        delta = _apply_scan_delta(analysis_result["ingredients"], previous_quantities)
        analysis_result["metadata"] = analysis_result.get("metadata") or {}
        analysis_result["metadata"]["delta"] = delta

        # Insert detected ingredients
        detected_ingredients = []
        requires_confirmation = False
        obs_rows: List[Dict[str, Any]] = []

        # Always include a scan_summary observation for auditability.
        try:
            obs_rows.append(
                {
                    "observed_entity_type": "scan_summary",
                    "observed_entity_id": None,
                    "detected_name": None,
                    "canonical_name": None,
                    "confidence": None,
                    "quantity": None,
                    "unit": None,
                    "bbox": None,
                    "crop_url": None,
                    "metadata": {
                        "scan_type": scan_type,
                        "location_hint": location_hint,
                        "analysis_ms": analysis_ms,
                        "api_cost_cents": api_cost,
                        "delta": delta,
                        **({"barcode": (barcode or "").strip()} if (barcode or "").strip() else {}),
                        **({"correlation_id": correlation_id} if correlation_id else {}),
                        **({"session_id": session_id} if session_id else {}),
                    },
                    "raw": {
                        "vision_provider": "openai",
                        "model_provider": model_provider,
                        "model_version": model_version,
                    },
                }
            )
        except Exception:
            pass

        for ingredient_data in analysis_result["ingredients"]:
            detected_id = str(uuid4())
            confidence = ingredient_data["confidence"]
            
            # Check if needs confirmation
            if confidence < Decimal("0.80"):
                requires_confirmation = True
            
            # Process ingredient thumbnail (async, non-blocking)
            bbox = ingredient_data.get("bbox")
            thumbnail_url = None
            try:
                from app.core.image_processor import upload_ingredient_thumbnail
                thumbnail_url = await upload_ingredient_thumbnail(
                    user_id=user_id,
                    scan_id=scan_id,
                    detected_id=detected_id,
                    image_data=image_data,
                    bbox=bbox,
                    confidence=float(confidence),
                    confidence_category=vision_client.get_confidence_category(confidence)
                )
            except Exception as e:
                logger.warning(f"Failed to create thumbnail for {detected_id}: {e}")
            
            # Insert detected ingredient
            detected_payload = {
                "id": detected_id,
                "scan_id": scan_id,
                "user_id": user_id,
                **({"session_id": session_id} if session_id else {}),
                **({"correlation_id": correlation_id} if correlation_id else {}),
                "detected_name": ingredient_data["detected_name"],
                "canonical_name": ingredient_data.get("canonical_name"),
                "confidence": float(confidence),
                "detected_quantity": ingredient_data.get("quantity"),
                "detected_unit": ingredient_data.get("unit"),
                "quantity_confidence": ingredient_data.get("quantity_confidence"),
                "bbox": ingredient_data.get("bbox"),
                "close_alternatives": ingredient_data.get("close_alternatives", []),
                "visual_similarity_group": ingredient_data.get("visual_similarity_group"),
                "allergen_warnings": ingredient_data.get("allergen_warnings", []),
                "thumbnail_url": thumbnail_url,
                "full_image_url": image_url,
                "confirmation_status": "pending",
                "metadata": {
                    "container_hash": ingredient_data.get("container_hash"),
                    "container_match_count": ingredient_data.get("container_match_count"),
                    **({"barcode": (barcode or "").strip()} if (barcode or "").strip() else {}),
                    **({"model_version": model_version} if model_version else {}),
                    "model_provider": model_provider,
                    **({"session_id": session_id} if session_id else {}),
                    **({"correlation_id": correlation_id} if correlation_id else {}),
                },
                **({"model_version": model_version} if model_version else {}),
                "model_provider": model_provider,
            }
            _retry_without_missing_column(db, "detected_ingredients", "insert", detected_payload)

            # Auditable observation row (best-effort; no images)
            try:
                obs_rows.append(
                    {
                        "observed_entity_id": detected_id,
                        "detected_name": ingredient_data.get("detected_name"),
                        "canonical_name": ingredient_data.get("canonical_name"),
                        "confidence": float(confidence) if confidence is not None else None,
                        "quantity": ingredient_data.get("quantity"),
                        "unit": ingredient_data.get("unit"),
                        "bbox": ingredient_data.get("bbox"),
                        "crop_url": thumbnail_url,
                        "metadata": {
                            "scan_type": scan_type,
                            "location_hint": location_hint,
                            **({"barcode": (barcode or "").strip()} if (barcode or "").strip() else {}),
                            **({"correlation_id": correlation_id} if correlation_id else {}),
                            **({"session_id": session_id} if session_id else {}),
                        },
                        "raw": {
                            "detected_name": ingredient_data.get("detected_name"),
                            "canonical_name": ingredient_data.get("canonical_name"),
                            "confidence": float(confidence) if confidence is not None else None,
                            "quantity": ingredient_data.get("quantity"),
                            "unit": ingredient_data.get("unit"),
                            "quantity_confidence": ingredient_data.get("quantity_confidence"),
                            "quantity_source": ingredient_data.get("quantity_source"),
                            "close_alternatives": ingredient_data.get("close_alternatives", []),
                            "allergen_warnings": ingredient_data.get("allergen_warnings", []),
                            "bbox": ingredient_data.get("bbox"),
                        },
                    }
                )
            except Exception:
                pass

            # Telemetry: vision.item_detected (no raw frames)
            try:
                event_rows.append(
                    {
                        "event_type": "vision.item_detected",
                        "event_ts": now_iso,
                        "user_id": user_id,
                        "household_id": None,
                        "session_id": session_id,
                        "model_version": model_version,
                        "release_version": release_version,
                        "app_version": app_version,
                        "payload": {
                            "scan_id": scan_id,
                            "detected_id": detected_id,
                            "detected_name": ingredient_data.get("detected_name"),
                            "canonical_ingredient": ingredient_data.get("canonical_name"),
                            "confidence": float(confidence),
                            "bbox": ingredient_data.get("bbox"),
                            **({"correlation_id": correlation_id} if correlation_id else {}),
                        },
                    }
                )
            except Exception:
                pass
            
            # Build response ingredient
            detected_ingredients.append(DetectedIngredient(
                id=detected_id,
                detected_name=ingredient_data["detected_name"],
                canonical_name=ingredient_data.get("canonical_name"),
                confidence=confidence,
                confidence_category=vision_client.get_confidence_category(confidence),
                category=ingredient_data.get("category", "other"),
                item_form=ingredient_data.get("item_form"),
                quantity=ingredient_data.get("quantity"),
                unit=ingredient_data.get("unit"),
                quantity_confidence=ingredient_data.get("quantity_confidence"),
                quantity_source=ingredient_data.get("quantity_source"),
                change_status=ingredient_data.get("change_status"),
                previous_quantity=ingredient_data.get("previous_quantity"),
                previous_unit=ingredient_data.get("previous_unit"),
                close_alternatives=ingredient_data.get("close_alternatives", []),
                visual_similarity_group=ingredient_data.get("visual_similarity_group"),
                allergen_warnings=ingredient_data.get("allergen_warnings", []),
                bbox=ingredient_data.get("bbox"),
                confirmation_status="pending",
                thumbnail_url=to_signed_url(thumbnail_url),
                full_image_url=to_signed_url(image_url),
            ))
        
        # Update scan processing time
        db.table("ingredient_scans").update({
            "processing_time_ms": analysis_result["metadata"]["processing_time_ms"]
        }).eq("id", scan_id).execute()

        # Telemetry: pantry.delta_detected (summary + per-item change types; no images)
        try:
            changes = []
            for d in (analysis_result.get("ingredients") or []):
                if not isinstance(d, dict):
                    continue
                nm = d.get("canonical_name") or d.get("detected_name")
                cs = d.get("change_status")
                if nm and cs:
                    changes.append({"name": nm, "change_type": cs})
                if len(changes) >= 50:
                    break
            event_rows.append(
                {
                    "event_type": "pantry.delta_detected",
                    "event_ts": now_iso,
                    "user_id": user_id,
                    "household_id": None,
                    "session_id": session_id,
                    "model_version": model_version,
                    "release_version": release_version,
                    "app_version": app_version,
                    "payload": {
                        "scan_id": scan_id,
                        "delta": delta,
                        "changes": changes,
                        **({"correlation_id": correlation_id} if correlation_id else {}),
                    },
                }
            )
        except Exception:
            pass

        emit_events(event_rows)

        # Auditable scan observations (AI inference); best-effort.
        try:
            log_scan_observations(
                user_id=user_id,
                source="image",
                scan_id=scan_id,
                session_id=session_id,
                correlation_id=correlation_id,
                storage_location=_scan_type_to_storage_location(scan_type),
                model_provider=model_provider,
                model_version=model_version,
                release_version=release_version,
                app_version=app_version,
                observations=obs_rows,
                observed_at=now_iso,
            )
        except Exception:
            pass
        
        # Build response
        message = None
        if requires_confirmation:
            message = "Some ingredients detected with lower confidence. Please review and confirm."
        else:
            message = "All ingredients detected with high confidence!"

        # UI hints: keep detected vs confirmed separation explicit for clients.
        try:
            high_conf = 0
            low_conf = 0
            for ing in detected_ingredients:
                try:
                    if float(ing.confidence) >= 0.80:
                        high_conf += 1
                    else:
                        low_conf += 1
                except Exception:
                    continue

            md = analysis_result.get("metadata") if isinstance(analysis_result, dict) else None
            if not isinstance(md, dict):
                md = {}
            md = dict(md)
            md.update(
                {
                    "ui_state": "review_required" if requires_confirmation else "review_optional",
                    "next_action": "review_and_confirm" if requires_confirmation else "confirm_all",
                    "detected_count": len(detected_ingredients),
                    "high_confidence_count": high_conf,
                    "low_confidence_count": low_conf,
                    "truth_note": "Detected items are not added to pantry until confirmed.",
                }
            )
            analysis_result["metadata"] = md
        except Exception:
            pass
        
        return AnalyzeImageResponse(
            success=True,
            scan_id=scan_id,
            ingredients=detected_ingredients,
            metadata=analysis_result["metadata"],
            requires_confirmation=requires_confirmation,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/analyze-barcode", response_model=AnalyzeImageResponse)
async def analyze_barcode(
    barcode: str = Form(..., description="UPC/EAN value"),
    scan_type: str = Form(default="pantry"),
    location_hint: Optional[str] = Form(default=None),
    session_id: Optional[str] = Form(default=None),
    barcode_name_hint: Optional[str] = Form(default=None, description="Fallback product name when barcode DB has no match"),
    barcode_quantity_hint: Optional[float] = Form(default=None),
    barcode_unit_hint: Optional[str] = Form(default=None),
    x_app_version: Optional[str] = Header(default=None, alias="X-App-Version"),
    user_id: str = Depends(get_current_user),
):
    """Barcode-first scan.

    World-class end-user UX goal: packaged items can be captured via barcode in <1s,
    then the user confirms quantity/name (same confirmation flow as vision scans).

    - Uses `product_barcodes` when available.
    - Falls back to client-provided name hints.
    - Never requires an image upload.
    """
    try:
        db = get_db_client()
        normalizer = get_normalizer()

        now_iso = datetime.now(timezone.utc).isoformat()

        bc = (barcode or "").strip()
        if not bc:
            raise HTTPException(status_code=400, detail="Barcode is required")
        if len(bc) < 6 or len(bc) > 32:
            raise HTTPException(status_code=400, detail="Barcode length is invalid")

        correlation_id: Optional[str] = None
        if session_id:
            try:
                sres = (
                    db.table("scan_sessions")
                    .select("correlation_id")
                    .eq("id", session_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                if sres.data and isinstance(sres.data[0], dict):
                    correlation_id = (sres.data[0].get("correlation_id") or None)
            except Exception:
                correlation_id = None

        release_version = (os.getenv("SAVO_RELEASE_VERSION") or os.getenv("SAVO_RELEASE") or "").strip() or None
        app_version = (x_app_version or "").strip() or None

        # Lookup product metadata (best-effort)
        product_name = None
        brand = None
        quantity_value = None
        quantity_unit = None
        package_image_url = None
        data_source = None
        confidence = None
        try:
            pres = (
                db.table("product_barcodes")
                .select(
                    "upc_ean,product_name,brand,quantity_value,quantity_unit,image_url,data_source,confidence"
                )
                .eq("upc_ean", bc)
                .limit(1)
                .execute()
            )
            if pres.data and isinstance(pres.data[0], dict):
                prow = pres.data[0]
                product_name = (prow.get("product_name") or None)
                brand = (prow.get("brand") or None)
                quantity_value = prow.get("quantity_value")
                quantity_unit = prow.get("quantity_unit")
                package_image_url = (prow.get("image_url") or None)
                data_source = (prow.get("data_source") or None)
                confidence = prow.get("confidence")
        except Exception:
            pass

        hint_name = (barcode_name_hint or "").strip() or None
        final_display_name = (product_name or hint_name)
        if not final_display_name:
            raise HTTPException(
                status_code=404,
                detail={
                    "code": "barcode_not_found",
                    "message": "Barcode not recognized. Try photo scan or provide product name hint.",
                    "barcode": bc,
                },
            )

        # Derive quantity (barcode DB preferred, then client hints)
        final_qty = None
        final_unit = None
        try:
            if quantity_value is not None:
                final_qty = float(quantity_value)
                final_unit = _normalize_unit(str(quantity_unit or ""))
        except Exception:
            final_qty = None
            final_unit = None

        if final_qty is None and barcode_quantity_hint is not None:
            try:
                final_qty = float(barcode_quantity_hint)
            except Exception:
                final_qty = None
        if final_unit is None and (barcode_unit_hint or "").strip():
            final_unit = _normalize_unit(barcode_unit_hint)

        canonical_name = normalizer.normalize_name(final_display_name)

        # Record a barcode scan history row (best-effort) and keep id for later linking.
        barcode_scan_id = None
        try:
            ins = (
                db.table("barcode_scans")
                .insert(
                    {
                        "user_id": user_id,
                        "barcode": bc,
                        "barcode_type": None,
                        "product_barcode": bc,
                        "product_name": final_display_name,
                        "brand": brand,
                        "quantity_value": final_qty,
                        "quantity_unit": final_unit,
                        "package_image_url": package_image_url,
                        "confidence": float(confidence) if confidence is not None else None,
                        "data_source": data_source,
                        "added_to_inventory": False,
                        "created_at": now_iso,
                    }
                )
                .execute()
            )
            if getattr(ins, "data", None) and isinstance(ins.data[0], dict):
                barcode_scan_id = ins.data[0].get("id")
        except Exception:
            barcode_scan_id = None

        # Create scan + detected ingredient rows
        scan_id = str(uuid4())
        previous_quantities = _load_previous_scan_quantities(db, user_id)

        det_dict = {
            "detected_name": final_display_name,
            "canonical_name": canonical_name,
            "confidence": Decimal("0.60"),
            "quantity": final_qty,
            "unit": final_unit,
            "bbox": None,
        }
        delta = _apply_scan_delta([det_dict], previous_quantities)

        scan_payload = {
            "id": scan_id,
            "user_id": user_id,
            "image_url": package_image_url,
            "image_hash": None,
            "image_metadata": {
                "scan_method": "barcode",
                "barcode": bc,
                **({"barcode_scan_id": barcode_scan_id} if barcode_scan_id else {}),
                **({"brand": brand} if brand else {}),
                **({"data_source": data_source} if data_source else {}),
                **({"confidence": float(confidence)} if confidence is not None else {}),
                **({"release_version": release_version} if release_version else {}),
                **({"app_version": app_version} if app_version else {}),
                **({"session_id": session_id} if session_id else {}),
                **({"correlation_id": correlation_id} if correlation_id else {}),
                "delta": delta,
            },
            "scan_type": scan_type,
            "location_hint": location_hint,
            "status": "completed",
            "vision_provider": "barcode",
            "api_cost_cents": 0,
            **({"session_id": session_id} if session_id else {}),
            **({"correlation_id": correlation_id} if correlation_id else {}),
            "model_provider": "barcode",
            "analysis_ms": 0,
            **({"release_version": release_version} if release_version else {}),
            **({"app_version": app_version} if app_version else {}),
        }
        _retry_without_missing_column(db, "ingredient_scans", "insert", scan_payload)

        detected_id = str(uuid4())
        detected_payload = {
            "id": detected_id,
            "scan_id": scan_id,
            "user_id": user_id,
            **({"session_id": session_id} if session_id else {}),
            **({"correlation_id": correlation_id} if correlation_id else {}),
            "detected_name": final_display_name,
            "canonical_name": canonical_name,
            "confidence": float(det_dict["confidence"]),
            "detected_quantity": final_qty,
            "detected_unit": final_unit,
            "quantity_confidence": float(confidence) if confidence is not None else 0.75,
            "bbox": None,
            "close_alternatives": [],
            "visual_similarity_group": None,
            "allergen_warnings": [],
            "thumbnail_url": None,
            "full_image_url": package_image_url,
            "confirmation_status": "pending",
            "metadata": {
                "scan_method": "barcode",
                "barcode": bc,
                **({"barcode_scan_id": barcode_scan_id} if barcode_scan_id else {}),
                **({"brand": brand} if brand else {}),
                **({"data_source": data_source} if data_source else {}),
                **({"correlation_id": correlation_id} if correlation_id else {}),
                **({"session_id": session_id} if session_id else {}),
            },
            "model_provider": "barcode",
        }
        _retry_without_missing_column(db, "detected_ingredients", "insert", detected_payload)

        # Auditable scan observation (barcode inference); best-effort.
        try:
            log_scan_observations(
                user_id=user_id,
                source="barcode",
                scan_id=scan_id,
                session_id=session_id,
                correlation_id=correlation_id,
                storage_location=_scan_type_to_storage_location(scan_type),
                model_provider="barcode",
                model_version=None,
                release_version=release_version,
                app_version=app_version,
                observations=[
                    {
                        "observed_entity_type": "scan_summary",
                        "observed_entity_id": None,
                        "crop_url": None,
                        "metadata": {
                            "scan_type": scan_type,
                            "location_hint": location_hint,
                            "delta": delta,
                            "barcode": bc,
                            **({"barcode_scan_id": barcode_scan_id} if barcode_scan_id else {}),
                            **({"correlation_id": correlation_id} if correlation_id else {}),
                            **({"session_id": session_id} if session_id else {}),
                        },
                        "raw": {"method": "barcode"},
                    },
                    {
                        "observed_entity_id": detected_id,
                        "detected_name": final_display_name,
                        "canonical_name": canonical_name,
                        "confidence": float(det_dict["confidence"]),
                        "quantity": final_qty,
                        "unit": final_unit,
                        "bbox": None,
                        "crop_url": None,
                        "metadata": {
                            "scan_type": scan_type,
                            "location_hint": location_hint,
                            "barcode": bc,
                            **({"barcode_scan_id": barcode_scan_id} if barcode_scan_id else {}),
                            **({"correlation_id": correlation_id} if correlation_id else {}),
                            **({"session_id": session_id} if session_id else {}),
                        },
                        "raw": {
                            "barcode": bc,
                            "product_name": final_display_name,
                            "brand": brand,
                            "quantity": final_qty,
                            "unit": final_unit,
                            "data_source": data_source,
                            "confidence": float(confidence) if confidence is not None else None,
                        },
                    }
                ],
                observed_at=now_iso,
            )
        except Exception:
            pass

        # Emit events (best-effort)
        try:
            changes = []
            for d in [det_dict]:
                nm = d.get("canonical_name") or d.get("detected_name")
                cs = d.get("change_status")
                if nm and cs:
                    changes.append({"name": nm, "change_type": cs})

            emit_events(
                [
                    {
                        "event_type": "vision.item_detected",
                        "event_ts": now_iso,
                        "user_id": user_id,
                        "household_id": None,
                        "session_id": session_id,
                        "model_version": None,
                        "release_version": release_version,
                        "app_version": app_version,
                        "payload": {
                            "scan_id": scan_id,
                            "detected_id": detected_id,
                            "detected_name": final_display_name,
                            "canonical_ingredient": canonical_name,
                            "confidence": float(det_dict["confidence"]),
                            "bbox": None,
                            "method": "barcode",
                            "barcode": bc,
                            **({"correlation_id": correlation_id} if correlation_id else {}),
                        },
                    },
                    {
                        "event_type": "pantry.delta_detected",
                        "event_ts": now_iso,
                        "user_id": user_id,
                        "household_id": None,
                        "session_id": session_id,
                        "model_version": None,
                        "release_version": release_version,
                        "app_version": app_version,
                        "payload": {
                            "scan_id": scan_id,
                            "delta": delta,
                            "changes": changes,
                            "method": "barcode",
                            "barcode": bc,
                            **({"correlation_id": correlation_id} if correlation_id else {}),
                        },
                    },
                ]
            )
        except Exception:
            pass

        detected_ingredients = [
            DetectedIngredient(
                id=detected_id,
                detected_name=final_display_name,
                canonical_name=canonical_name,
                confidence=Decimal("0.60"),
                confidence_category="low",
                category="other",
                item_form="packaged",
                quantity=final_qty,
                unit=final_unit,
                quantity_confidence=float(confidence) if confidence is not None else 0.75,
                quantity_source=(data_source or "barcode"),
                change_status=det_dict.get("change_status"),
                previous_quantity=det_dict.get("previous_quantity"),
                previous_unit=det_dict.get("previous_unit"),
                close_alternatives=[],
                visual_similarity_group=None,
                allergen_warnings=[],
                bbox=None,
                confirmation_status="pending",
                thumbnail_url=None,
                full_image_url=package_image_url,
            )
        ]

        return AnalyzeImageResponse(
            success=True,
            scan_id=scan_id,
            ingredients=detected_ingredients,
            metadata={
                "scan_method": "barcode",
                "barcode": bc,
                "product": {
                    "product_name": final_display_name,
                    "brand": brand,
                    "quantity_value": final_qty,
                    "quantity_unit": final_unit,
                    "image_url": package_image_url,
                    "data_source": data_source,
                    "confidence": float(confidence) if confidence is not None else None,
                },
                "delta": delta,
                **({"barcode_scan_id": barcode_scan_id} if barcode_scan_id else {}),
                "ui_state": "review_required",
                "next_action": "review_and_confirm",
                "detected_count": 1,
                "high_confidence_count": 0,
                "low_confidence_count": 1,
                "truth_note": "Detected items are not added to pantry until confirmed.",
            },
            requires_confirmation=True,
            message="Review and confirm this barcode item.",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Barcode analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Barcode analysis failed: {str(e)}")


@router.get("/barcode/lookup", response_model=BarcodeLookupResponse)
async def barcode_lookup(
    barcode: str,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Instant barcode product preview (read-only).

    Does not create scans, detected_ingredients, or inventory.
    Intended for a fast UX: show product name/brand/size immediately.
    """
    try:
        db = get_db_client()
        bc = (barcode or "").strip()
        if not bc:
            raise HTTPException(status_code=400, detail="Barcode is required")
        if len(bc) < 6 or len(bc) > 32:
            raise HTTPException(status_code=400, detail="Barcode length is invalid")

        try:
            res = (
                db.table("product_barcodes")
                .select("upc_ean,product_name,brand,quantity_value,quantity_unit,image_url,data_source,confidence")
                .eq("upc_ean", bc)
                .limit(1)
                .execute()
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Barcode lookup failed: {e}")

        if not res.data or not isinstance(res.data[0], dict):
            return {
                "success": True,
                "found": False,
                "barcode": bc,
                "product": None,
                "message": "Barcode not found",
            }

        row = res.data[0]
        product = {
            "product_name": row.get("product_name"),
            "brand": row.get("brand"),
            "quantity_value": row.get("quantity_value"),
            "quantity_unit": row.get("quantity_unit"),
            "image_url": row.get("image_url"),
            "data_source": row.get("data_source"),
            "confidence": float(row.get("confidence")) if row.get("confidence") is not None else None,
        }

        return {"success": True, "found": True, "barcode": bc, "product": product, "message": None}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Barcode lookup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Barcode lookup failed: {str(e)}")


@router.post("/analyze-frames")
async def analyze_frames(
    images: List[UploadFile] = File(..., description="Multiple image frames (JPEG/PNG)"),
    scan_type: str = Form(default="pantry"),
    location_hint: Optional[str] = Form(default=None),
    session_id: Optional[str] = Form(default=None),
    barcode: Optional[str] = Form(default=None),
    barcode_name_hint: Optional[str] = Form(default=None),
    barcode_quantity_hint: Optional[float] = Form(default=None),
    barcode_unit_hint: Optional[str] = Form(default=None),
    x_app_version: Optional[str] = Header(default=None, alias="X-App-Version"),
    user_id: str = Depends(get_current_user),
):
    """Analyze multiple frames (sampled during a guided scan) and deduplicate detections.

    This endpoint is designed for mobile guided scanning where the client captures
    several still frames over ~10–20 seconds. It avoids video processing dependencies
    (ffmpeg) while improving loose-item and shelf coverage.

    Returns the same shape as /analyze-image for compatibility.
    """
    try:
        started = time.perf_counter()
        # Basic validation
        if not isinstance(images, list) or not images:
            raise HTTPException(status_code=400, detail="No images provided")

        # Cap to keep latency bounded.
        if len(images) > 20:
            images = images[:20]

        from collections import defaultdict

        def _dedupe(all_detections: List[Dict]) -> List[Dict]:
            grouped: Dict[str, List[Dict]] = defaultdict(list)
            for det in all_detections:
                if not isinstance(det, dict):
                    continue
                key = (det.get("canonical_name") or det.get("detected_name") or "").strip().lower()
                if not key:
                    continue
                grouped[key].append(det)

            out: List[Dict] = []
            for _k, dets in grouped.items():
                best = max(dets, key=lambda d: float(d.get("confidence") or 0))
                quantities = []
                for d in dets:
                    q = d.get("quantity")
                    if isinstance(q, (int, float)):
                        quantities.append(float(q))
                if quantities:
                    best = {**best, "quantity": sum(quantities) / len(quantities)}

                # Merge close alternatives (unique by name)
                alts: List[Dict] = []
                seen = set()
                for d in dets:
                    for a in d.get("close_alternatives", []) or []:
                        if not isinstance(a, dict):
                            continue
                        nm = (a.get("name") or "").strip()
                        if not nm:
                            continue
                        nk = nm.lower()
                        if nk in seen:
                            continue
                        seen.add(nk)
                        alts.append(a)
                if alts:
                    best = {**best, "close_alternatives": alts[:5]}

                best = {**best, "detection_count": len(dets)}
                out.append(best)
            return out

        # Get user profile for context
        profile = await get_full_profile(user_id)
        vision_client = get_vision_client()
        model_version = getattr(vision_client, "model", None)
        model_provider = "openai"
        db = get_db_client()
        scan_id = str(uuid4())

        correlation_id: Optional[str] = None
        if session_id:
            try:
                sres = (
                    db.table("scan_sessions")
                    .select("correlation_id")
                    .eq("id", session_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                if sres.data and isinstance(sres.data[0], dict):
                    correlation_id = (sres.data[0].get("correlation_id") or None)
            except Exception:
                correlation_id = None

        now_iso = datetime.now(timezone.utc).isoformat()

        event_rows: List[Dict[str, Any]] = []

        # Best-effort: session bookkeeping (received N frames)
        if session_id:
            try:
                sess = (
                    db.table("scan_sessions")
                    .select("frames_received,frames_usable")
                    .eq("id", session_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                if sess.data:
                    fr = int(sess.data[0].get("frames_received") or 0) + int(len(images))
                    fu = int(sess.data[0].get("frames_usable") or 0)
                    db.table("scan_sessions").update(
                        {
                            "frames_received": fr,
                            "frames_usable": fu,
                            "stage": "processing",
                            "updated_at": now_iso,
                        }
                    ).eq("id", session_id).eq("user_id", user_id).execute()
            except Exception:
                pass

        release_version = (os.getenv("SAVO_RELEASE_VERSION") or os.getenv("SAVO_RELEASE") or "").strip() or None
        app_version = (x_app_version or "").strip() or None

        representative_image_url = None
        all_detections: List[Dict] = []
        usable_frame_bytes: Dict[int, bytes] = {}
        any_ok_frame = False
        aggregated_issues: set[str] = set()
        last_metrics: Dict[str, Any] = {}

        # If all frames fail the quality gate (common when the user moves near the end),
        # fall back to the best-available frame so the scan can still progress.
        best_fallback: Optional[Dict[str, Any]] = None  # {idx, bytes, metrics, issues}

        for idx, image in enumerate(images):
            if image.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
                aggregated_issues.add("invalid_format")
                continue

            image_data = await image.read()
            if not image_data:
                aggregated_issues.add("empty")
                continue
            if len(image_data) > 10 * 1024 * 1024:
                aggregated_issues.add("too_large")
                continue

            quality = _assess_image_quality(image_data)
            if not quality.get("ok"):
                for it in (quality.get("issues") or []):
                    if isinstance(it, str) and it:
                        aggregated_issues.add(it)
                metrics = quality.get("metrics")
                if isinstance(metrics, dict):
                    last_metrics = metrics

                # Track best fallback candidate (maximize sharpness proxy / contrast).
                try:
                    m = metrics if isinstance(metrics, dict) else {}
                    # Use whatever proxy is available; default to 0.
                    score = float(m.get("sharpness") or m.get("variance") or m.get("contrast") or 0.0)
                except Exception:
                    score = 0.0
                if best_fallback is None or score > float(best_fallback.get("score") or 0.0):
                    best_fallback = {
                        "idx": idx,
                        "bytes": image_data,
                        "metrics": metrics if isinstance(metrics, dict) else {},
                        "issues": list(quality.get("issues") or []),
                        "score": score,
                        "content_type": image.content_type,
                    }
                continue

            any_ok_frame = True
            usable_frame_bytes[idx] = image_data

            if representative_image_url is None:
                try:
                    expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
                    representative_image_url = upload_inventory_image(
                        user_id=user_id,
                        content=image_data,
                        content_type=image.content_type,
                        asset_type="scan_frame_reference",
                        source="frames",
                        expires_at=expires_at,
                        links={"scan_id": scan_id, "session_id": session_id},
                    )
                except Exception:
                    representative_image_url = None

            try:
                analysis_result = await vision_client.analyze_image(
                    image_data=image_data,
                    scan_type=scan_type,
                    location_hint=location_hint,
                    user_preferences=profile,
                    barcode=(barcode or None),
                    barcode_name_hint=(barcode_name_hint or None),
                    barcode_quantity_hint=barcode_quantity_hint,
                    barcode_unit_hint=_normalize_unit(barcode_unit_hint) if barcode_unit_hint else None,
                )
                if isinstance(analysis_result, dict) and analysis_result.get("success") and analysis_result.get("ingredients"):
                    for det in analysis_result.get("ingredients") or []:
                        if isinstance(det, dict):
                            det["_frame_idx"] = idx
                            all_detections.append(det)
            except Exception as e:
                logger.warning("Frame %s analysis failed: %s", idx, e)
                continue

        # Best-effort: session bookkeeping (usable frames + issues)
        if session_id:
            try:
                sess = (
                    db.table("scan_sessions")
                    .select("frames_received,frames_usable,metadata")
                    .eq("id", session_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                if sess.data:
                    fr0 = int(sess.data[0].get("frames_received") or 0)
                    fu0 = int(sess.data[0].get("frames_usable") or 0)
                    stage = "processing" if any_ok_frame else "collecting_frames"
                    db.table("scan_sessions").update(
                        {
                            "frames_received": fr0,
                            "frames_usable": fu0 + int(len(usable_frame_bytes)),
                            "last_quality_issues": sorted(list(aggregated_issues)),
                            "updated_at": now_iso,
                            "stage": stage,
                        }
                    ).eq("id", session_id).eq("user_id", user_id).execute()
            except Exception:
                pass

        if not any_ok_frame:
            # Fallback: proceed with the best available frame to avoid blocking the UX.
            if best_fallback and isinstance(best_fallback.get("bytes"), (bytes, bytearray)):
                fb_bytes = bytes(best_fallback["bytes"])
                try:
                    expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
                    representative_image_url = upload_inventory_image(
                        user_id=user_id,
                        content=fb_bytes,
                        content_type=str(best_fallback.get("content_type") or "image/jpeg"),
                        asset_type="scan_frame_reference",
                        source="frames",
                        expires_at=expires_at,
                        links={"scan_id": scan_id, "session_id": session_id},
                        metadata={"fallback": True},
                    )
                except Exception:
                    representative_image_url = None

                try:
                    analysis_result = await vision_client.analyze_image(
                        image_data=fb_bytes,
                        scan_type=scan_type,
                        location_hint=location_hint,
                        user_preferences=profile,
                        barcode=(barcode or None),
                        barcode_name_hint=(barcode_name_hint or None),
                        barcode_quantity_hint=barcode_quantity_hint,
                        barcode_unit_hint=_normalize_unit(barcode_unit_hint) if barcode_unit_hint else None,
                    )
                    if isinstance(analysis_result, dict) and analysis_result.get("success") and analysis_result.get("ingredients"):
                        any_ok_frame = True
                        usable_frame_bytes[int(best_fallback.get("idx") or 0)] = fb_bytes
                        for det in analysis_result.get("ingredients") or []:
                            if isinstance(det, dict):
                                det["_frame_idx"] = int(best_fallback.get("idx") or 0)
                                all_detections.append(det)
                except Exception:
                    pass

            if not any_ok_frame:
                # Mirror /analyze-image quality error structure so clients can show guidance.
                issues = sorted(list(aggregated_issues))
                if "too_dark" in issues:
                    msg = "Too dark — turn on lights and retake."
                elif "too_blurry" in issues:
                    msg = "Too blurry — hold steady and retake."
                elif "too_bright" in issues:
                    msg = "Too bright/glare — adjust angle and retake."
                else:
                    msg = "Image quality too low — please retake."
                raise HTTPException(
                    status_code=400,
                    detail={
                        "code": "image_quality",
                        "message": msg,
                        "issues": issues,
                        "metrics": last_metrics,
                    },
                )

        if not all_detections:
            raise HTTPException(status_code=400, detail="No ingredients detected. Try scanning again with better coverage.")

        unique_detections = _dedupe(all_detections)

        # If barcode hints were provided, apply them only when unambiguous.
        _apply_barcode_hints_to_detections(
            unique_detections,
            barcode_name_hint=barcode_name_hint,
            barcode_quantity_hint=barcode_quantity_hint,
            barcode_unit_hint=barcode_unit_hint,
        )

        previous_quantities = _load_previous_scan_quantities(db, user_id)

        # Apply container fingerprint + learned priors using the best source frame.
        for det in unique_detections:
            frame_idx = det.get("_frame_idx")
            if not isinstance(frame_idx, int):
                continue
            frame_bytes = usable_frame_bytes.get(frame_idx)
            if not frame_bytes:
                continue
            container_hash = _compute_container_hash(frame_bytes, det.get("bbox"))
            if container_hash:
                det["container_hash"] = container_hash
                prior = _get_container_quantity_prior(db, user_id, container_hash)
                if prior is not None:
                    qc = det.get("quantity_confidence")
                    try:
                        qc_val = float(qc) if qc is not None else None
                    except Exception:
                        qc_val = None
                    if det.get("quantity") is None or qc_val is None or qc_val < 0.65:
                        det["quantity"] = prior.get("quantity")
                        det["unit"] = prior.get("unit")
                        det["quantity_source"] = "container_history"
                        det["quantity_confidence"] = float(prior.get("confidence") or 0.75)
                        det["container_match_count"] = int(prior.get("sample_count") or 0)

        delta = _apply_scan_delta(unique_detections, previous_quantities)

        analysis_ms = int(max(0.0, (time.perf_counter() - started) * 1000.0))

        # Insert scan record
        scan_payload = {
            "id": scan_id,
            "user_id": user_id,
            "image_url": representative_image_url,
            "image_hash": None,
            "image_metadata": {
                "frames_received": len(images),
                "frames_usable": True,
                **({"barcode": (barcode or "").strip()} if (barcode or "").strip() else {}),
                **({"barcode_name_hint": (barcode_name_hint or "").strip()} if (barcode_name_hint or "").strip() else {}),
                **({"barcode_quantity_hint": barcode_quantity_hint} if barcode_quantity_hint is not None else {}),
                **({"barcode_unit_hint": _normalize_unit(barcode_unit_hint)} if (barcode_unit_hint or "").strip() else {}),
                **({"model_version": model_version} if model_version else {}),
                "model_provider": model_provider,
                "analysis_ms": analysis_ms,
                **({"release_version": release_version} if release_version else {}),
                **({"app_version": app_version} if app_version else {}),
            },
            "scan_type": f"frames_{scan_type}",
            "location_hint": location_hint,
            "status": "processing",
            "vision_provider": "openai",
            "api_cost_cents": 0,
            **({"session_id": session_id} if session_id else {}),
            **({"correlation_id": correlation_id} if correlation_id else {}),
            **({"model_version": model_version} if model_version else {}),
            "model_provider": model_provider,
            "analysis_ms": analysis_ms,
            **({"release_version": release_version} if release_version else {}),
            **({"app_version": app_version} if app_version else {}),
        }
        _retry_without_missing_column(db, "ingredient_scans", "insert", scan_payload)

        if session_id:
            try:
                sess = (
                    db.table("scan_sessions")
                    .select("metadata")
                    .eq("id", session_id)
                    .eq("user_id", user_id)
                    .limit(1)
                    .execute()
                )
                md = {}
                if sess.data and isinstance(sess.data[0].get("metadata"), dict):
                    md = sess.data[0].get("metadata")
                md = dict(md)
                md["last_scan_id"] = scan_id
                db.table("scan_sessions").update(
                    {
                        "stage": "completed",
                        "last_quality_issues": [],
                        "metadata": md,
                        "updated_at": now_iso,
                    }
                ).eq("id", session_id).eq("user_id", user_id).execute()
            except Exception:
                pass

        detected_ingredients = []
        requires_confirmation = False
        obs_rows: List[Dict[str, Any]] = []

        # Always include a scan_summary observation for auditability.
        try:
            obs_rows.append(
                {
                    "observed_entity_type": "scan_summary",
                    "observed_entity_id": None,
                    "crop_url": None,
                    "metadata": {
                        "scan_type": f"frames_{scan_type}",
                        "location_hint": location_hint,
                        "analysis_ms": analysis_ms,
                        "frames_received": len(images),
                        "frames_usable": int(len(usable_frame_bytes)),
                        "delta": delta,
                        **({"barcode": (barcode or "").strip()} if (barcode or "").strip() else {}),
                        **({"correlation_id": correlation_id} if correlation_id else {}),
                        **({"session_id": session_id} if session_id else {}),
                    },
                    "raw": {
                        "vision_provider": "openai",
                        "model_provider": model_provider,
                        "model_version": model_version,
                    },
                }
            )
        except Exception:
            pass

        for det in unique_detections:
            detected_id = str(uuid4())
            confidence = det.get("confidence")
            try:
                conf_val = float(confidence) if confidence is not None else 0.0
            except Exception:
                conf_val = 0.0

            if conf_val < 0.80:
                requires_confirmation = True

            # Best-effort: create a crop thumbnail from the source frame (no raw video storage).
            thumbnail_url = None
            try:
                frame_idx = det.get("_frame_idx")
                if isinstance(frame_idx, int):
                    frame_bytes = usable_frame_bytes.get(frame_idx)
                else:
                    frame_bytes = None
                if frame_bytes:
                    from app.core.image_processor import upload_ingredient_thumbnail

                    thumbnail_url = await upload_ingredient_thumbnail(
                        user_id=user_id,
                        scan_id=scan_id,
                        detected_id=detected_id,
                        image_data=frame_bytes,
                        bbox=det.get("bbox"),
                        confidence=float(conf_val),
                        confidence_category=vision_client.get_confidence_category(Decimal(str(conf_val))),
                    )
            except Exception as e:
                logger.warning("Failed to create frame thumbnail for %s: %s", detected_id, e)

            det_payload = {
                "id": detected_id,
                "scan_id": scan_id,
                "user_id": user_id,
                **({"session_id": session_id} if session_id else {}),
                **({"correlation_id": correlation_id} if correlation_id else {}),
                "detected_name": det.get("detected_name"),
                "canonical_name": det.get("canonical_name"),
                "confidence": conf_val,
                "detected_quantity": det.get("quantity"),
                "detected_unit": det.get("unit"),
                "quantity_confidence": det.get("quantity_confidence"),
                "bbox": det.get("bbox"),
                "close_alternatives": det.get("close_alternatives", []),
                "visual_similarity_group": det.get("visual_similarity_group"),
                "allergen_warnings": det.get("allergen_warnings", []),
                "thumbnail_url": thumbnail_url,
                "full_image_url": representative_image_url,
                "confirmation_status": "pending",
                "metadata": {
                    "detection_count": det.get("detection_count", 1),
                    "container_hash": det.get("container_hash"),
                    "container_match_count": det.get("container_match_count"),
                    **({"barcode": (barcode or "").strip()} if (barcode or "").strip() else {}),
                    **({"model_version": model_version} if model_version else {}),
                    "model_provider": model_provider,
                    **({"session_id": session_id} if session_id else {}),
                    **({"correlation_id": correlation_id} if correlation_id else {}),
                },
                **({"model_version": model_version} if model_version else {}),
                "model_provider": model_provider,
            }
            _retry_without_missing_column(db, "detected_ingredients", "insert", det_payload)

            # Auditable observation row (best-effort; no images)
            try:
                obs_rows.append(
                    {
                        "observed_entity_id": detected_id,
                        "detected_name": det.get("detected_name"),
                        "canonical_name": det.get("canonical_name"),
                        "confidence": conf_val,
                        "quantity": det.get("quantity"),
                        "unit": det.get("unit"),
                        "bbox": det.get("bbox"),
                        "crop_url": thumbnail_url,
                        "metadata": {
                            "scan_type": f"frames_{scan_type}",
                            "location_hint": location_hint,
                            "detection_count": det.get("detection_count", 1),
                            **({"barcode": (barcode or "").strip()} if (barcode or "").strip() else {}),
                            **({"correlation_id": correlation_id} if correlation_id else {}),
                            **({"session_id": session_id} if session_id else {}),
                        },
                        "raw": {
                            "detected_name": det.get("detected_name"),
                            "canonical_name": det.get("canonical_name"),
                            "confidence": conf_val,
                            "quantity": det.get("quantity"),
                            "unit": det.get("unit"),
                            "quantity_confidence": det.get("quantity_confidence"),
                            "quantity_source": det.get("quantity_source"),
                            "close_alternatives": det.get("close_alternatives", []),
                            "allergen_warnings": det.get("allergen_warnings", []),
                            "bbox": det.get("bbox"),
                            "detection_count": det.get("detection_count", 1),
                        },
                    }
                )
            except Exception:
                pass

            # Telemetry: vision.item_detected
            try:
                event_rows.append(
                    {
                        "event_type": "vision.item_detected",
                        "event_ts": now_iso,
                        "user_id": user_id,
                        "household_id": None,
                        "session_id": session_id,
                        "model_version": model_version,
                        "release_version": release_version,
                        "app_version": app_version,
                        "payload": {
                            "scan_id": scan_id,
                            "detected_id": detected_id,
                            "detected_name": det.get("detected_name"),
                            "canonical_ingredient": det.get("canonical_name"),
                            "confidence": conf_val,
                            "bbox": det.get("bbox"),
                            **({"correlation_id": correlation_id} if correlation_id else {}),
                        },
                    }
                )
            except Exception:
                pass

            detected_ingredients.append(DetectedIngredient(
                id=detected_id,
                detected_name=det.get("detected_name"),
                canonical_name=det.get("canonical_name"),
                confidence=Decimal(str(conf_val)),
                confidence_category=vision_client.get_confidence_category(Decimal(str(conf_val))),
                category=det.get("category", "other"),
                item_form=det.get("item_form"),
                quantity=det.get("quantity"),
                unit=det.get("unit"),
                quantity_confidence=det.get("quantity_confidence"),
                quantity_source=det.get("quantity_source"),
                change_status=det.get("change_status"),
                previous_quantity=det.get("previous_quantity"),
                previous_unit=det.get("previous_unit"),
                close_alternatives=det.get("close_alternatives", []),
                visual_similarity_group=det.get("visual_similarity_group"),
                allergen_warnings=det.get("allergen_warnings", []),
                bbox=det.get("bbox"),
                confirmation_status="pending",
                thumbnail_url=to_signed_url(thumbnail_url),
                full_image_url=to_signed_url(representative_image_url),
            ))

        db.table("ingredient_scans").update({
            "status": "completed",
            "total_detections": len(detected_ingredients),
            "processing_time_ms": None,
        }).eq("id", scan_id).execute()

        # Telemetry: pantry.delta_detected (summary + per-item change types)
        try:
            changes = []
            for d in (unique_detections or []):
                if not isinstance(d, dict):
                    continue
                nm = d.get("canonical_name") or d.get("detected_name")
                cs = d.get("change_status")
                if nm and cs:
                    changes.append({"name": nm, "change_type": cs})
                if len(changes) >= 50:
                    break
            event_rows.append(
                {
                    "event_type": "pantry.delta_detected",
                    "event_ts": now_iso,
                    "user_id": user_id,
                    "household_id": None,
                    "session_id": session_id,
                    "model_version": model_version,
                    "release_version": release_version,
                    "app_version": app_version,
                    "payload": {
                        "scan_id": scan_id,
                        "delta": delta,
                        "changes": changes,
                        **({"correlation_id": correlation_id} if correlation_id else {}),
                    },
                }
            )
        except Exception:
            pass

        emit_events(event_rows)

        # Auditable scan observations (AI inference); best-effort.
        try:
            log_scan_observations(
                user_id=user_id,
                source="frames",
                scan_id=scan_id,
                session_id=session_id,
                correlation_id=correlation_id,
                storage_location=_scan_type_to_storage_location(scan_type),
                model_provider=model_provider,
                model_version=model_version,
                release_version=release_version,
                app_version=app_version,
                observations=obs_rows,
                observed_at=now_iso,
            )
        except Exception:
            pass

        message = "Some ingredients detected with lower confidence. Please review and confirm." if requires_confirmation else "All ingredients detected with high confidence!"

        high_conf = 0
        low_conf = 0
        try:
            for ing in detected_ingredients:
                try:
                    if float(ing.confidence) >= 0.80:
                        high_conf += 1
                    else:
                        low_conf += 1
                except Exception:
                    continue
        except Exception:
            high_conf = 0
            low_conf = 0

        return AnalyzeImageResponse(
            success=True,
            scan_id=scan_id,
            ingredients=detected_ingredients,
            metadata={
                "frames_received": len(images),
                "total_raw_detections": len(all_detections),
                "unique_ingredients": len(detected_ingredients),
                "delta": delta,
                "ui_state": "review_required" if requires_confirmation else "review_optional",
                "next_action": "review_and_confirm" if requires_confirmation else "confirm_all",
                "detected_count": len(detected_ingredients),
                "high_confidence_count": high_conf,
                "low_confidence_count": low_conf,
                "truth_note": "Detected items are not added to pantry until confirmed.",
            },
            requires_confirmation=requires_confirmation,
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Frame analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Frame analysis failed: {str(e)}")


@router.post("/confirm-ingredients", response_model=ConfirmIngredientsResponse)
async def confirm_ingredients(
    request: ConfirmIngredientsRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Confirm, reject, or modify detected ingredients
    
    - **scan_id**: ID of the scan
    - **confirmations**: List of confirmation actions
    
    Confirmed ingredients are automatically added to user's pantry
    """
    try:
        from app.core.unit_converter import UnitConverter

        db = get_db_client()
        normalizer = get_normalizer()
        
        # Verify scan belongs to user
        scan = db.table("ingredient_scans").select("*").eq("id", request.scan_id).eq("user_id", user_id).execute()
        if not scan.data:
            raise HTTPException(status_code=404, detail="Scan not found")

        scan_record = scan.data[0]
        storage_location = _scan_type_to_storage_location(scan_record.get("scan_type"))
        item_state = "raw"
        scan_image_url = scan_record.get("image_url")

        scan_session_id = scan_record.get("session_id")
        scan_correlation_id = scan_record.get("correlation_id")
        scan_model_version = scan_record.get("model_version")
        scan_release_version = scan_record.get("release_version")
        scan_app_version = scan_record.get("app_version")

        scan_created_at = scan_record.get("created_at")

        taxonomy_version = os.getenv("SAVO_TAXONOMY_VERSION")

        # Track scan time early for consistent last_seen_* stamps.
        now_iso = datetime.utcnow().isoformat()

        # Training consent + retention (best-effort)
        training_opt_in = False
        retention_days = 0
        try:
            hp = (
                db.table("household_profiles")
                .select("scan_training_opt_in, scan_training_retention_days")
                .eq("user_id", user_id)
                .limit(1)
                .execute()
            )
            if hp.data:
                training_opt_in = bool(hp.data[0].get("scan_training_opt_in"))
                retention_days = int(hp.data[0].get("scan_training_retention_days") or 0)
        except Exception as e:
            logger.warning(f"Failed to read training consent settings: {e}")
        
        confirmed_count = 0
        rejected_count = 0
        modified_count = 0
        pantry_items_added = []
        
        # Process each confirmation
        for confirmation in request.confirmations:
            detected_id = confirmation["detected_id"]
            action = confirmation["action"]
            confirmed_name = confirmation.get("confirmed_name")
            quantity = confirmation.get("quantity")
            unit = confirmation.get("unit")

            # Optional per-item barcode context (client may attach this only for modified items).
            confirmation_barcode = (confirmation.get("barcode") or "").strip()
            confirmation_barcode_name_hint = (confirmation.get("barcode_name_hint") or "").strip()
            confirmation_barcode_unit_hint = (confirmation.get("barcode_unit_hint") or "").strip()
            confirmation_barcode_quantity_hint = confirmation.get("barcode_quantity_hint")
            
            # Verify detected ingredient exists
            detected = db.table("detected_ingredients").select("*").eq("id", detected_id).eq("user_id", user_id).execute()
            if not detected.data:
                logger.warning(f"Detected ingredient {detected_id} not found for user {user_id}")
                continue
            
            detected_item = detected.data[0]

            md0 = detected_item.get("metadata")
            if not isinstance(md0, dict):
                md0 = {}
            container_hash = md0.get("container_hash")
            item_signature = _anonymized_item_signature(user_id, detected_item)

            # Snapshot before-values for opt-in learning logs.
            before_snapshot = {
                "detected_name": detected_item.get("detected_name"),
                "canonical_name": detected_item.get("canonical_name"),
                "detected_quantity": detected_item.get("detected_quantity"),
                "detected_unit": detected_item.get("detected_unit"),
                "confirmed_name": detected_item.get("confirmed_name"),
                "confirmation_status": detected_item.get("confirmation_status"),
            }
            
            # Update confirmation status
            update_data = {
                "confirmation_status": action,
                "confirmed_at": datetime.utcnow().isoformat()
            }

            # If barcode info is provided, persist it onto the detected ingredient for audit/learning.
            if confirmation_barcode or confirmation_barcode_name_hint or confirmation_barcode_quantity_hint is not None:
                try:
                    md = detected_item.get("metadata")
                    if not isinstance(md, dict):
                        md = {}
                    if confirmation_barcode:
                        md["barcode"] = confirmation_barcode
                    if confirmation_barcode_name_hint:
                        md["barcode_name_hint"] = confirmation_barcode_name_hint
                    if confirmation_barcode_quantity_hint is not None:
                        md["barcode_quantity_hint"] = confirmation_barcode_quantity_hint
                    if confirmation_barcode_unit_hint:
                        md["barcode_unit_hint"] = _normalize_unit(confirmation_barcode_unit_hint)
                    update_data["metadata"] = md
                except Exception as e:
                    logger.warning(f"Failed to merge barcode metadata for detected_ingredient {detected_id}: {e}")
            
            if action in ["confirmed", "modified"]:
                # Determine final confirmed name
                final_name = None
                if action == "modified" and confirmed_name:
                    final_name = confirmed_name
                    modified_count += 1
                else:
                    final_name = detected_item.get("canonical_name") or detected_item.get("detected_name")
                    confirmed_count += 1

                canonical_name = normalizer.normalize_name(final_name or "")
                update_data["confirmed_name"] = canonical_name

                # Resolve stable canonical ingredient ID (best-effort)
                resolved_ingredient_id: Optional[str] = None
                try:
                    resolved_ingredient_id = _resolve_master_ingredient_id(db, canonical_name)
                except Exception:
                    resolved_ingredient_id = None

                # Resolve taxonomy for consistent inventory classification.
                inv_category: Optional[str] = None
                inv_subcategory: Optional[str] = None
                inv_cuisine: Optional[str] = None
                try:
                    inv_category, inv_subcategory, inv_cuisine = _resolve_inventory_taxonomy(
                        db,
                        canonical_name=canonical_name,
                        ingredient_id=resolved_ingredient_id,
                    )
                except Exception:
                    inv_category, inv_subcategory, inv_cuisine = None, None, None

                # Fallback: some scan paths attach taxonomy hints to detected_ingredients.metadata.
                # Normalize to our inventory taxonomy keys (lower snake-ish strings).
                try:
                    if (not inv_category) or (not inv_subcategory) or (not inv_cuisine):
                        md = detected_item.get("metadata")
                        if isinstance(md, dict):
                            def _norm(s: Any) -> Optional[str]:
                                if s is None:
                                    return None
                                txt = str(s).strip().lower()
                                if not txt:
                                    return None
                                txt = txt.replace(" ", "_")
                                txt = txt.replace("-", "_")
                                while "__" in txt:
                                    txt = txt.replace("__", "_")
                                return txt

                            if not inv_category:
                                inv_category = _norm(md.get("category"))
                            if not inv_subcategory:
                                inv_subcategory = _norm(md.get("subcategory"))
                            if not inv_cuisine:
                                inv_cuisine = _norm(md.get("cuisine"))

                        # Additional fallback: the analyzer response includes category/subcategory fields
                        # directly on detected items. Use those if present.
                        def _norm2(s: Any) -> Optional[str]:
                            if s is None:
                                return None
                            txt = str(s).strip().lower()
                            if not txt:
                                return None
                            txt = txt.replace(" ", "_")
                            txt = txt.replace("-", "_")
                            while "__" in txt:
                                txt = txt.replace("__", "_")
                            return txt

                        if not inv_category:
                            inv_category = _norm2(detected_item.get("category"))
                        if not inv_subcategory:
                            inv_subcategory = _norm2(detected_item.get("subcategory"))
                        if not inv_cuisine:
                            inv_cuisine = _norm2(detected_item.get("cuisine"))
                except Exception:
                    pass

                # Telemetry: pantry.item_corrected (modified items only)
                if action == "modified":
                    try:
                        original_name = normalizer.normalize_name(
                            (detected_item.get("canonical_name") or detected_item.get("detected_name") or "")
                        )
                        correction_type = "rename" if (canonical_name and original_name and canonical_name != original_name) else "edit"

                        emit_event(
                            event_type="pantry.item_corrected",
                            event_ts=now_iso,
                            user_id=user_id,
                            household_id=None,
                            session_id=scan_session_id,
                            model_version=scan_model_version,
                            release_version=scan_release_version,
                            app_version=scan_app_version,
                            payload={
                                "scan_id": request.scan_id,
                                "detected_id": detected_id,
                                "correction_type": correction_type,
                                "confidence_at_decision": float(detected_item.get("confidence") or 0),
                                "before": before_snapshot,
                                "after": {
                                    "confirmation_status": action,
                                    "confirmed_name": canonical_name,
                                    "detected_quantity": update_data.get("detected_quantity", detected_item.get("detected_quantity")),
                                    "detected_unit": update_data.get("detected_unit", detected_item.get("detected_unit")),
                                },
                                **({"correlation_id": scan_correlation_id} if scan_correlation_id else {}),
                            },
                        )
                    except Exception:
                        pass

                # Pantry vocabulary learning: record a feedback event when the user changes identity.
                if action == "modified":
                    try:
                        original = normalizer.normalize_name(
                            (detected_item.get("canonical_name") or detected_item.get("detected_name") or "")
                        )
                        if canonical_name and original and canonical_name != original:
                            db.table("learning_feedback").insert(
                                {
                                    "user_id": user_id,
                                    "feedback_type": "pantry_vocab_correction",
                                    "source_entity_type": "detected_ingredient",
                                    "source_entity_id": str(detected_id),
                                    "was_correct": True,
                                    "confidence_at_decision": float(detected_item.get("confidence") or 0),
                                    "correction_data": {
                                        "scan_id": request.scan_id,
                                        "original_detected_name": detected_item.get("detected_name"),
                                        "original_canonical_name": detected_item.get("canonical_name"),
                                        "corrected_canonical_name": canonical_name,
                                        **({"barcode": confirmation_barcode} if confirmation_barcode else {}),
                                        **({"barcode_name_hint": confirmation_barcode_name_hint} if confirmation_barcode_name_hint else {}),
                                        **({"barcode_quantity_hint": confirmation_barcode_quantity_hint} if confirmation_barcode_quantity_hint is not None else {}),
                                        **({"barcode_unit_hint": _normalize_unit(confirmation_barcode_unit_hint)} if confirmation_barcode_unit_hint else {}),
                                    },
                                }
                            ).execute()
                    except Exception as e:
                        logger.warning(f"Failed to store pantry vocab feedback: {e}")

                # Store ground-truth training label (only if explicitly opted-in)
                if training_opt_in and retention_days > 0:
                    try:
                        expires_at = (datetime.utcnow() + timedelta(days=retention_days)).isoformat()
                        # Prefer per-item crop (privacy) over full scan reference.
                        training_image_url = detected_item.get("thumbnail_url") or scan_image_url
                        db.table("scan_training_labels").insert(
                            {
                                "user_id": user_id,
                                "scan_id": request.scan_id,
                                "detected_id": detected_id,
                                "confirmed_name": canonical_name,
                                "original_detected_name": detected_item.get("detected_name"),
                                "bbox": detected_item.get("bbox"),
                                "image_url": training_image_url,
                                "expires_at": expires_at,
                                # Extra privacy/version fields (best-effort; schema may lag)
                                "item_signature": item_signature,
                                "anon_user_signature": hashlib.sha256((str(user_id) + "|" + item_signature).encode("utf-8")).hexdigest(),
                                "model_version": scan_model_version,
                                "release_version": scan_release_version,
                                "app_version": scan_app_version,
                                "taxonomy_version": taxonomy_version,
                            }
                        ).execute()
                    except Exception as e:
                        logger.warning(f"Failed to store training label: {e}")

                # Append-only learning signal: observation -> confirmation delta
                try:
                    observed_qty = detected_item.get("detected_quantity")
                    observed_unit = detected_item.get("detected_unit")
                    confirmed_qty = quantity if quantity is not None else detected_item.get("detected_quantity")
                    confirmed_unit = unit if unit is not None else detected_item.get("detected_unit")
                    identity_was_correct = None
                    quantity_was_correct = None
                    if action in {"confirmed", "modified"}:
                        original_canon = normalizer.normalize_name(
                            (detected_item.get("canonical_name") or detected_item.get("detected_name") or "")
                        )
                        identity_was_correct = bool(original_canon and canonical_name and original_canon == canonical_name)
                        if quantity is not None:
                            try:
                                quantity_was_correct = (float(observed_qty) == float(quantity)) if observed_qty is not None else False
                            except Exception:
                                quantity_was_correct = None

                    db.table("confirmation_deltas").insert(
                        {
                            "user_id": user_id,
                            "scan_id": request.scan_id,
                            "detected_id": detected_id,
                            "action": action,
                            "observed_name": detected_item.get("detected_name"),
                            "observed_canonical_name": detected_item.get("canonical_name"),
                            "observed_ingredient_id": detected_item.get("ingredient_id"),
                            "observed_confidence": float(detected_item.get("confidence") or 0) if detected_item.get("confidence") is not None else None,
                            "observed_quantity": observed_qty,
                            "observed_unit": observed_unit,
                            "confirmed_name": canonical_name if action in {"confirmed", "modified"} else None,
                            "confirmed_ingredient_id": resolved_ingredient_id,
                            "confirmed_quantity": confirmed_qty if action in {"confirmed", "modified"} else None,
                            "confirmed_unit": confirmed_unit if action in {"confirmed", "modified"} else None,
                            "quantity_was_correct": quantity_was_correct,
                            "identity_was_correct": identity_was_correct,
                            "container_hash": container_hash,
                            "item_signature": item_signature,
                            "model_version": scan_model_version,
                            "release_version": scan_release_version,
                            "app_version": scan_app_version,
                            "taxonomy_version": taxonomy_version,
                            "metadata": {
                                "bbox": detected_item.get("bbox"),
                                "barcode": (detected_item.get("metadata") or {}).get("barcode") if isinstance(detected_item.get("metadata"), dict) else None,
                            },
                        }
                    ).execute()
                except Exception:
                    pass
                
                # Update quantity if provided (user-entered)
                if quantity is not None:
                    update_data["detected_quantity"] = quantity
                    update_data["detected_unit"] = unit
                    update_data["quantity_confidence"] = 1.0  # User-entered = 100% confident

                # Upsert into canonical inventory (inventory_items)
                incoming_qty = None
                if quantity is not None:
                    incoming_qty = float(quantity)
                elif detected_item.get("detected_quantity") is not None:
                    incoming_qty = float(detected_item.get("detected_quantity"))
                else:
                    incoming_qty = 1.0

                incoming_unit = _normalize_unit(unit or detected_item.get("detected_unit") or "pieces")

                truth_write_table = inventory_truth_write_table()

                existing = None
                if resolved_ingredient_id:
                    existing = (
                        db.table(truth_write_table)
                        .select("*")
                        .eq("user_id", user_id)
                        .eq("ingredient_id", resolved_ingredient_id)
                        .eq("storage_location", storage_location)
                        .eq("item_state", item_state)
                        .order("updated_at", desc=True)
                        .limit(1)
                        .execute()
                    )

                # Fallback to canonical_name matching for backward compatibility
                if not existing or not getattr(existing, "data", None):
                    existing = (
                        db.table(truth_write_table)
                        .select("*")
                        .eq("user_id", user_id)
                        .eq("canonical_name", canonical_name)
                        .eq("storage_location", storage_location)
                        .eq("item_state", item_state)
                        .order("updated_at", desc=True)
                        .limit(1)
                        .execute()
                    )

                merged_qty = incoming_qty
                merged_unit = incoming_unit

                # Prefer cropped reference image if available.
                reference_image_url = (
                    detected_item.get("thumbnail_url")
                    or detected_item.get("full_image_url")
                    or scan_image_url
                )

                # Model audit fields (best-effort, schema may vary).
                model_version = None
                model_provider = None
                try:
                    md = detected_item.get("metadata")
                    if isinstance(md, dict):
                        model_version = md.get("model_version")
                        model_provider = md.get("model_provider")
                except Exception:
                    model_version = None
                    model_provider = None

                if existing.data:
                    existing_item = existing.data[0]
                    existing_qty = float(existing_item.get("quantity") or 0)
                    existing_unit = _normalize_unit(existing_item.get("unit") or "pieces")

                    if incoming_unit == existing_unit:
                        merged_qty = existing_qty + incoming_qty
                        merged_unit = existing_unit
                        should_set_reference = bool(reference_image_url) and (
                            (not existing_item.get("image_url"))
                            or (str(existing_item.get("image_source") or "").strip().lower() == "scan")
                        )
                        update_payload = {
                            "quantity": merged_qty,
                            "unit": merged_unit,
                            "display_name": existing_item.get("display_name")
                            or _titleize(canonical_name),
                            "source": "scan",
                            "scan_confidence": float(detected_item.get("confidence") or 1.0),
                            **({"ingredient_id": resolved_ingredient_id} if resolved_ingredient_id else {}),
                            **({"category": inv_category} if inv_category else {}),
                            **({"subcategory": inv_subcategory} if inv_subcategory else {}),
                            **({"cuisine": inv_cuisine} if inv_cuisine else {}),
                            "pantry_status": "active",
                            "is_current": True,
                            "last_seen_at": now_iso,
                            "last_seen_scan_id": request.scan_id,
                            "last_confirmed_at": now_iso,
                            **({"model_version": model_version} if model_version else {}),
                            **({"model_provider": model_provider} if model_provider else {}),
                        }
                        if should_set_reference:
                            update_payload["image_url"] = reference_image_url
                            update_payload["image_source"] = "scan"
                            update_payload["reference_detected_id"] = detected_id
                        _dual_write_inventory(
                            db,
                            "update",
                            update_payload,
                            where={"id": existing_item["id"]},
                            user_id=user_id,
                            correlation_id=scan_correlation_id,
                            session_id=scan_session_id,
                            endpoint="POST /api/scanning/confirm-ingredients",
                        )
                    elif UnitConverter.can_convert(incoming_unit, existing_unit):
                        converted = UnitConverter.convert(incoming_qty, incoming_unit, existing_unit)
                        merged_qty = existing_qty + float(converted)
                        merged_unit = existing_unit
                        should_set_reference = bool(reference_image_url) and (
                            (not existing_item.get("image_url"))
                            or (str(existing_item.get("image_source") or "").strip().lower() == "scan")
                        )
                        update_payload = {
                            "quantity": merged_qty,
                            "unit": merged_unit,
                            "display_name": existing_item.get("display_name")
                            or _titleize(canonical_name),
                            "source": "scan",
                            "scan_confidence": float(detected_item.get("confidence") or 1.0),
                            **({"ingredient_id": resolved_ingredient_id} if resolved_ingredient_id else {}),
                            **({"category": inv_category} if inv_category else {}),
                            **({"subcategory": inv_subcategory} if inv_subcategory else {}),
                            **({"cuisine": inv_cuisine} if inv_cuisine else {}),
                            "pantry_status": "active",
                            "is_current": True,
                            "last_seen_at": now_iso,
                            "last_seen_scan_id": request.scan_id,
                            "last_confirmed_at": now_iso,
                            **({"model_version": model_version} if model_version else {}),
                            **({"model_provider": model_provider} if model_provider else {}),
                        }
                        if should_set_reference:
                            update_payload["image_url"] = reference_image_url
                            update_payload["image_source"] = "scan"
                            update_payload["reference_detected_id"] = detected_id
                        _dual_write_inventory(
                            db,
                            "update",
                            update_payload,
                            where={"id": existing_item["id"]},
                            user_id=user_id,
                            correlation_id=scan_correlation_id,
                            session_id=scan_session_id,
                            endpoint="POST /api/scanning/confirm-ingredients",
                        )
                    else:
                        insert_payload = {
                            "user_id": user_id,
                            "canonical_name": canonical_name,
                            "display_name": _titleize(final_name or canonical_name),
                            "quantity": incoming_qty,
                            "unit": incoming_unit,
                            "storage_location": storage_location,
                            "item_state": item_state,
                            "source": "scan",
                            "scan_confidence": float(detected_item.get("confidence") or 1.0),
                            "image_url": reference_image_url,
                            **({"ingredient_id": resolved_ingredient_id} if resolved_ingredient_id else {}),
                            **({"category": inv_category} if inv_category else {}),
                            **({"subcategory": inv_subcategory} if inv_subcategory else {}),
                            **({"cuisine": inv_cuisine} if inv_cuisine else {}),
                            **({"session_id": scan_session_id} if scan_session_id else {}),
                            **({"correlation_id": scan_correlation_id} if scan_correlation_id else {}),
                            "image_source": "scan",
                            "reference_detected_id": detected_id,
                            **({"model_version": model_version} if model_version else {}),
                            **({"model_provider": model_provider} if model_provider else {}),
                            "pantry_status": "active",
                            "is_current": True,
                            "last_seen_at": now_iso,
                            **({"session_id": scan_session_id} if scan_session_id else {}),
                            **({"correlation_id": scan_correlation_id} if scan_correlation_id else {}),
                            "last_seen_scan_id": request.scan_id,
                            "last_confirmed_at": now_iso,
                        }
                        created = _dual_write_inventory(
                            db,
                            "insert",
                            insert_payload,
                            user_id=user_id,
                            correlation_id=scan_correlation_id,
                            session_id=scan_session_id,
                            endpoint="POST /api/scanning/confirm-ingredients",
                        )
                        existing_item = created.data[0] if getattr(created, "data", None) else None
                else:
                    insert_payload = {
                        "user_id": user_id,
                        "canonical_name": canonical_name,
                        "display_name": _titleize(final_name or canonical_name),
                        "quantity": incoming_qty,
                        "unit": incoming_unit,
                        "storage_location": storage_location,
                        "item_state": item_state,
                        "source": "scan",
                        "scan_confidence": float(detected_item.get("confidence") or 1.0),
                        "image_url": reference_image_url,
                        "image_source": "scan",
                        "reference_detected_id": detected_id,
                        **({"ingredient_id": resolved_ingredient_id} if resolved_ingredient_id else {}),
                        **({"category": inv_category} if inv_category else {}),
                        **({"subcategory": inv_subcategory} if inv_subcategory else {}),
                        **({"cuisine": inv_cuisine} if inv_cuisine else {}),
                        **({"model_version": model_version} if model_version else {}),
                        **({"model_provider": model_provider} if model_provider else {}),
                        "pantry_status": "active",
                        "is_current": True,
                        "last_seen_at": now_iso,
                        "last_seen_scan_id": request.scan_id,
                        "last_confirmed_at": now_iso,
                    }
                    created = _dual_write_inventory(
                        db,
                        "insert",
                        insert_payload,
                        user_id=user_id,
                        correlation_id=scan_correlation_id,
                        session_id=scan_session_id,
                        endpoint="POST /api/scanning/confirm-ingredients",
                    )
                    existing_item = created.data[0] if getattr(created, "data", None) else None

                # Telemetry: pantry.item_confirmed (confirmed or modified)
                try:
                    emit_event(
                        event_type="pantry.item_confirmed",
                        event_ts=now_iso,
                        user_id=user_id,
                        household_id=None,
                        session_id=scan_session_id,
                        model_version=scan_model_version,
                        release_version=scan_release_version,
                        app_version=scan_app_version,
                        payload={
                            "scan_id": request.scan_id,
                            "detected_id": detected_id,
                            "inventory_item_id": (existing_item.get("id") if isinstance(existing_item, dict) else None),
                            "action": action,
                            "confidence_at_decision": float(detected_item.get("confidence") or 0),
                            "confirmed_name": canonical_name,
                            "quantity": merged_qty,
                            "unit": merged_unit,
                            "before": before_snapshot,
                            **({"correlation_id": scan_correlation_id} if scan_correlation_id else {}),
                        },
                    )
                except Exception:
                    pass

                # If this item came from a barcode scan, mark it as added_to_inventory.
                try:
                    md = detected_item.get("metadata")
                    if isinstance(md, dict):
                        bsid = md.get("barcode_scan_id")
                        if bsid and existing_item and isinstance(existing_item, dict) and existing_item.get("id"):
                            db.table("barcode_scans").update(
                                {"added_to_inventory": True, "inventory_item_id": existing_item.get("id")}
                            ).eq("id", bsid).eq("user_id", user_id).execute()
                except Exception:
                    pass
                
                # Add to pantry (trigger will handle this automatically)
                # But we'll track for response
                pantry_items_added.append({
                    "name": canonical_name,
                    "display_name": _titleize(final_name or canonical_name),
                    "quantity": merged_qty,
                    "unit": merged_unit,
                    "source": "scan"
                })
                
            elif action == "rejected":
                rejected_count += 1

                # Telemetry: pantry.item_corrected (delete)
                try:
                    emit_event(
                        event_type="pantry.item_corrected",
                        event_ts=now_iso,
                        user_id=user_id,
                        household_id=None,
                        session_id=scan_session_id,
                        model_version=scan_model_version,
                        release_version=scan_release_version,
                        app_version=scan_app_version,
                        payload={
                            "scan_id": request.scan_id,
                            "detected_id": detected_id,
                            "correction_type": "delete",
                            "confidence_at_decision": float(detected_item.get("confidence") or 0),
                            "before": before_snapshot,
                            "after": {"confirmation_status": action},
                            **({"correlation_id": scan_correlation_id} if scan_correlation_id else {}),
                        },
                    )
                except Exception:
                    pass

                # Telemetry: pantry.item_removed
                try:
                    emit_event(
                        event_type="pantry.item_removed",
                        event_ts=now_iso,
                        user_id=user_id,
                        household_id=None,
                        session_id=scan_session_id,
                        model_version=scan_model_version,
                        release_version=scan_release_version,
                        app_version=scan_app_version,
                        payload={
                            "scan_id": request.scan_id,
                            "detected_id": detected_id,
                            "action": "rejected",
                            "confidence_at_decision": float(detected_item.get("confidence") or 0),
                            "before": before_snapshot,
                            **({"correlation_id": scan_correlation_id} if scan_correlation_id else {}),
                        },
                    )
                except Exception:
                    pass
            
            # Update detected ingredient
            try:
                db.table("detected_ingredients").update(update_data).eq("id", detected_id).execute()
            except Exception as e:
                # Some deployments have an older trigger/function that tries to insert
                # `scan_id` into `user_pantry` even though the table schema uses
                # `source_scan_id`. That trigger runs on detected_ingredients updates,
                # and it can block the whole confirmation flow.
                msg = str(e)
                if 'user_pantry' in msg and 'scan_id' in msg and 'does not exist' in msg:
                    logger.warning(
                        "Skipping detected_ingredients update due to legacy pantry trigger schema mismatch: %s",
                        msg,
                    )
                else:
                    raise

            # Opt-in ML correction event logging.
            if training_opt_in:
                try:
                    after_snapshot = {
                        "action": action,
                        "confirmed_name": update_data.get("confirmed_name"),
                        "detected_quantity": update_data.get("detected_quantity", detected_item.get("detected_quantity")),
                        "detected_unit": update_data.get("detected_unit", detected_item.get("detected_unit")),
                    }
                    sig = _anonymized_item_signature(
                        user_id,
                        detected_item,
                        extra={
                            "scan_id": request.scan_id,
                            "after_action": action,
                        },
                    )
                    db.table("learning_feedback").insert(
                        {
                            "user_id": user_id,
                            "feedback_type": f"scan_{action}",
                            "source_entity_type": "detected_ingredient",
                            "source_entity_id": str(detected_id),
                            "was_correct": True,
                            "confidence_at_decision": float(detected_item.get("confidence") or 0),
                            "correction_data": {
                                "scan_id": request.scan_id,
                                "before": before_snapshot,
                                "after": after_snapshot,
                                "item_signature": sig,
                            },
                        }
                    ).execute()
                except Exception as e:
                    logger.warning(f"Failed to store opt-in correction event: {e}")

        # Latest-scan semantics (safer): after upserting the confirmed items for this scan,
        # mark older scan-sourced raw items in the same storage location inactive.
        # This avoids a window where everything is deactivated before the new items are written.
        try:
            primary_table = inventory_truth_write_table()
            (
                db.table(primary_table)
                .update({"is_current": False})
                .eq("user_id", user_id)
                .eq("source", "scan")
                .eq("storage_location", storage_location)
                .eq("item_state", item_state)
                .eq("is_current", True)
                .neq("last_seen_scan_id", request.scan_id)
                .execute()
            )
            if dual_write_enabled() and primary_table == "inventory_items":
                try:
                    (
                        db.table("inventory_items_v2")
                        .update({"is_current": False})
                        .eq("user_id", user_id)
                        .eq("source", "scan")
                        .eq("storage_location", storage_location)
                        .eq("item_state", item_state)
                        .eq("is_current", True)
                        .neq("last_seen_scan_id", request.scan_id)
                        .execute()
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Failed to deactivate previous scan inventory set: {e}")
        
        # Mark scan as completed + store KPI counters (best-effort)
        try:
            confirm_ms = None
            try:
                if scan_created_at:
                    created_dt = datetime.fromisoformat(str(scan_created_at).replace("Z", "+00:00"))
                    if created_dt.tzinfo is not None:
                        created_dt = created_dt.astimezone(timezone.utc).replace(tzinfo=None)
                    confirm_ms = int(max(0.0, (datetime.utcnow() - created_dt).total_seconds() * 1000.0))
            except Exception:
                confirm_ms = None

            detected_count = None
            try:
                det_res = (
                    db.table("detected_ingredients")
                    .select("id")
                    .eq("scan_id", request.scan_id)
                    .eq("user_id", user_id)
                    .limit(5000)
                    .execute()
                )
                detected_count = len(det_res.data or [])
            except Exception:
                detected_count = None

            update_scan = {
                "status": "completed",
                "confirmed_at": now_iso,
                "confirmed_count": int(confirmed_count),
                "modified_count": int(modified_count),
                "rejected_count": int(rejected_count),
            }
            if confirm_ms is not None:
                update_scan["confirm_ms"] = confirm_ms
            if detected_count is not None:
                update_scan["detected_count"] = detected_count

            _retry_without_missing_column(db, "ingredient_scans", "update", update_scan, where={"id": request.scan_id})
        except Exception:
            pass
        
        # Build response message
        message = f"Confirmed {confirmed_count}, modified {modified_count}, rejected {rejected_count} ingredients."
        if pantry_items_added:
            message += f" Added {len(pantry_items_added)} items to your pantry."
        
        return ConfirmIngredientsResponse(
            success=True,
            confirmed_count=confirmed_count,
            rejected_count=rejected_count,
            modified_count=modified_count,
            pantry_items_added=pantry_items_added,
            message=message
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingredient confirmation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Confirmation failed: {str(e)}")


@router.post("/single-item")
async def scan_single_item(
    image: UploadFile = File(..., description="Image file (JPEG/PNG)"),
    scan_type: str = Form(default="pantry"),
    user_id: str = Depends(get_current_user)
):
    """
    Optimized endpoint for continuous single-item scanning
    
    - Faster analysis (targets ONE ingredient)
    - Returns single best match
    - Auto-saves if confidence > 85%
    - Perfect for continuous scanning workflow
    """
    try:
        # Validate image
        if image.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
            raise HTTPException(status_code=400, detail="Invalid image format. Use JPEG or PNG.")
        
        image_data = await image.read()
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large. Maximum 10MB.")
        
        # Get user profile for context
        try:
            profile = await get_full_profile(user_id)
        except Exception:
            profile = None
        
        started = time.perf_counter()
        # Analyze with optimized single-item method
        vision_client = get_vision_client()
        model_version = getattr(vision_client, "model", None)
        model_provider = "openai"
        result = await vision_client.analyze_single_item(
            image_data=image_data,
            scan_type=scan_type,
            user_preferences=profile
        )
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=f"Analysis failed: {result.get('error')}")
        
        ingredient = result["ingredient"]
        detected_name = (ingredient.get("detected_name") if isinstance(ingredient, dict) else None)
        if not isinstance(detected_name, str) or not detected_name.strip() or detected_name.strip().lower() in {"unknown", "n/a", "na"}:
            raise HTTPException(
                status_code=422,
                detail="Couldn't identify the item. Please hold steady, move closer, and try again.",
            )

        confidence = ingredient["confidence"]
        
        analysis_ms = int(max(0.0, (time.perf_counter() - started) * 1000.0))
        release_version = (os.getenv("SAVO_RELEASE_VERSION") or os.getenv("SAVO_RELEASE") or "").strip() or None

        # Auto-save high-confidence items
        auto_saved = False
        if confidence >= 0.85:
            try:
                db = get_db_client()
                normalizer = get_normalizer()
                
                canonical_name = normalizer.normalize_name(ingredient["detected_name"])
                if not canonical_name:
                    raise ValueError("Empty canonical name")
                storage_location = _scan_type_to_storage_location(scan_type)
                now_iso = datetime.utcnow().isoformat()

                # Create a scan record for audit/KPI attribution.
                scan_id = str(uuid4())
                scan_payload = {
                    "id": scan_id,
                    "user_id": user_id,
                    "image_url": None,
                    "image_hash": None,
                    "image_metadata": {
                        "analysis_ms": analysis_ms,
                        "auto_saved": True,
                        **({"release_version": release_version} if release_version else {}),
                        **({"model_version": model_version} if model_version else {}),
                        "model_provider": model_provider,
                    },
                    "scan_type": f"single_{scan_type}",
                    "location_hint": None,
                    "status": "completed",
                    "vision_provider": "openai",
                    "api_cost_cents": 0,
                    **({"model_version": model_version} if model_version else {}),
                    "model_provider": model_provider,
                    "analysis_ms": analysis_ms,
                    **({"release_version": release_version} if release_version else {}),
                    "auto_added_count": 1,
                    "detected_count": 1,
                    "confirmed_count": 1,
                    "confirmed_at": now_iso,
                }
                _retry_without_missing_column(db, "ingredient_scans", "insert", scan_payload)
                
                # Upsert to inventory
                truth_write_table = inventory_truth_write_table()
                existing = (
                    db.table(truth_write_table)
                    .select("*")
                    .eq("user_id", user_id)
                    .eq("canonical_name", canonical_name)
                    .eq("storage_location", storage_location)
                    .eq("item_state", "raw")
                    .eq("is_current", True)
                    .limit(1)
                    .execute()
                )
                
                quantity = ingredient.get("quantity") or 1.0
                unit = _normalize_unit(ingredient.get("unit") or "pieces")
                
                if existing.data:
                    # Update existing
                    item = existing.data[0]
                    new_qty = float(item.get("quantity", 0)) + float(quantity)
                    update_payload = {
                        "quantity": new_qty,
                        "unit": unit,
                        "scan_confidence": float(confidence),
                        "last_seen_at": now_iso,
                        "last_seen_scan_id": scan_id,
                        **({"model_version": model_version} if model_version else {}),
                        "model_provider": model_provider,
                        **({"release_version": release_version} if release_version else {}),
                    }
                    _dual_write_inventory(
                        db,
                        "update",
                        update_payload,
                        where={"id": item["id"]},
                        user_id=user_id,
                        endpoint="POST /api/scanning/<bulk-sync>",
                    )
                else:
                    # Insert new
                    insert_payload = {
                        "user_id": user_id,
                        "canonical_name": canonical_name,
                        "display_name": _titleize(ingredient["detected_name"]),
                        "quantity": quantity,
                        "unit": unit,
                        "storage_location": storage_location,
                        "item_state": "raw",
                        "source": "scan",
                        "scan_confidence": float(confidence),
                        "is_current": True,
                        "last_seen_at": now_iso,
                        "last_seen_scan_id": scan_id,
                        **({"model_version": model_version} if model_version else {}),
                        "model_provider": model_provider,
                        **({"release_version": release_version} if release_version else {}),
                    }
                    _dual_write_inventory(
                        db,
                        "insert",
                        insert_payload,
                        user_id=user_id,
                        endpoint="POST /api/scanning/<bulk-sync>",
                    )
                
                auto_saved = True
            except Exception as e:
                logger.warning(f"Auto-save failed: {e}")
        
        return {
            "success": True,
            "ingredient": ingredient,
            "metadata": result["metadata"],
            "auto_saved": auto_saved,
            "requires_confirmation": confidence < 0.85,
            "message": f"{'Auto-added' if auto_saved else 'Detected'}: {ingredient['detected_name']}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Single-item scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Scan failed: {str(e)}")


@router.post("/confirm-single")
async def confirm_single_ingredient(
    ingredient_name: str = Form(...),
    quantity: float = Form(...),
    unit: str = Form(...),
    scan_type: str = Form(default="pantry"),
    user_id: str = Depends(get_current_user)
):
    """
    Confirm single ingredient immediately (fire-and-forget)
    
    - No scan_id needed
    - Instant confirmation
    - Returns immediately for next scan
    """
    try:
        if not ingredient_name or not ingredient_name.strip():
            raise HTTPException(status_code=400, detail="Missing ingredient name")

        db = get_db_client()
        normalizer = get_normalizer()
        
        canonical_name = normalizer.normalize_name(ingredient_name)
        storage_location = _scan_type_to_storage_location(scan_type)
        normalized_unit = _normalize_unit(unit)
        now_iso = datetime.utcnow().isoformat()
        
        # Upsert to inventory
        existing = (
            db.table(inventory_truth_write_table())
            .select("*")
            .eq("user_id", user_id)
            .eq("canonical_name", canonical_name)
            .eq("storage_location", storage_location)
            .eq("item_state", "raw")
            .eq("is_current", True)
            .limit(1)
            .execute()
        )
        
        if existing.data:
            # Update existing
            item = existing.data[0]
            
            from app.core.unit_converter import UnitConverter
            existing_qty = float(item.get("quantity", 0))
            existing_unit = _normalize_unit(item.get("unit", "pieces"))
            
            if normalized_unit == existing_unit:
                new_qty = existing_qty + quantity
            elif UnitConverter.can_convert(normalized_unit, existing_unit):
                converted = UnitConverter.convert(quantity, normalized_unit, existing_unit)
                new_qty = existing_qty + float(converted)
                normalized_unit = existing_unit
            else:
                new_qty = quantity
            
            _dual_write_inventory(
                db,
                "update",
                {
                    "quantity": new_qty,
                    "unit": normalized_unit,
                    "last_seen_at": now_iso,
                },
                where={"id": item["id"]},
                user_id=user_id,
                endpoint="POST /api/scanning/<quick-add>",
            )
        else:
            # Insert new
            _dual_write_inventory(
                db,
                "insert",
                {
                    "user_id": user_id,
                    "canonical_name": canonical_name,
                    "display_name": _titleize(ingredient_name),
                    "quantity": quantity,
                    "unit": normalized_unit,
                    "storage_location": storage_location,
                    "item_state": "raw",
                    "source": "scan",
                    "scan_confidence": 1.0,  # User confirmed
                    "is_current": True,
                    "last_seen_at": now_iso,
                },
                user_id=user_id,
                endpoint="POST /api/scanning/<quick-add>",
            )
        
        return {
            "success": True,
            "message": f"{ingredient_name} added to {storage_location}"
        }
        
    except Exception as e:
        logger.error(f"Single ingredient confirmation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Confirmation failed: {str(e)}")


@router.post("/scan-receipt", response_model=ScanReceiptResponse)
async def scan_receipt(
    image: UploadFile = File(..., description="Receipt image file (JPEG/PNG)"),
    storage_location: str = Form(default="pantry"),
    user_id: str = Depends(get_current_user),
):
    """Scan a grocery receipt and upsert items into inventory."""
    try:
        if image.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
            raise HTTPException(status_code=400, detail="Invalid image format. Use JPEG or PNG.")

        image_data = await image.read()
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large. Maximum 10MB.")

        db = get_db_client()
        normalizer = get_normalizer()

        # Receipt scan id (persisted to receipt_scans + inventory_items.last_seen_receipt_id).
        receipt_id = str(uuid4())
        now_iso = datetime.utcnow().isoformat()

        # Best-effort upload to storage for traceability (optional).
        image_url = None
        try:
            expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
            image_url = upload_inventory_image(
                user_id=user_id,
                content=image_data,
                content_type=image.content_type,
                asset_type="receipt_image",
                source="receipt_scan",
                expires_at=expires_at,
                links={"receipt_id": receipt_id},
            )
        except Exception as e:
            logger.warning(f"Failed to upload receipt image: {e}")

        # Persist receipt scan event for referential integrity (best-effort until migration is applied).
        try:
            db.table("receipt_scans").insert(
                {
                    "id": receipt_id,
                    "user_id": user_id,
                    "image_url": image_url,
                    "created_at": now_iso,
                }
            ).execute()
        except Exception:
            pass

        # User profile context (optional; can help disambiguate items).
        profile = None
        try:
            profile = await get_full_profile(user_id)
        except Exception:
            profile = None

        vision_client = get_vision_client()
        analysis = await vision_client.analyze_receipt(
            image_data=image_data,
            user_preferences=profile,
        )

        if not analysis.get("success"):
            raise HTTPException(status_code=500, detail=f"Receipt analysis failed: {analysis.get('error')}")

        # Best-effort store analysis for later debugging/training.
        try:
            db.table("receipt_scans").update(
                {
                    "raw_text": analysis.get("raw_text"),
                    "analysis_json": analysis,
                    "status": "parsed",
                }
            ).eq("id", receipt_id).execute()
        except Exception:
            pass

        storage = _scan_type_to_storage_location(storage_location)
        item_state = "raw"

        added_count = 0
        updated_count = 0
        pantry_items: List[Dict] = []

        from app.core.unit_converter import UnitConverter

        truth_write_table = inventory_truth_write_table()

        def _is_source_check_violation(err: Exception) -> bool:
            payload = None
            if getattr(err, "args", None) and isinstance(err.args[0], dict):
                payload = err.args[0]
            if isinstance(payload, dict):
                if payload.get("code") != "23514":
                    return False
                text = f"{payload.get('message', '')} {payload.get('details', '')}"
                return "source_check" in text
            # Fallback string match (covers wrapped exceptions)
            text = str(err)
            return "source_check" in text and "23514" in text

        def _safe_update_inventory(item_id: str, payload: Dict) -> None:
            try:
                db.table(truth_write_table).update(payload).eq("id", item_id).execute()
                if dual_write_enabled() and truth_write_table == "inventory_items":
                    try:
                        db.table("inventory_items_v2").update(payload).eq("id", item_id).execute()
                    except Exception as e:
                        try:
                            emit_migration_incident(
                                user_id=user_id,
                                correlation_id=receipt_id,
                                incident_type="v2_write_failed",
                                operation="update",
                                v2_target="public.inventory_items_v2",
                                error=str(e),
                                entity_id=str(item_id),
                                payload={"endpoint": "POST /api/scanning/scan-receipt"},
                            )
                        except Exception:
                            pass
            except Exception as e:
                if _is_source_check_violation(e) and "source" in payload:
                    payload2 = dict(payload)
                    payload2.pop("source", None)
                    db.table(truth_write_table).update(payload2).eq("id", item_id).execute()
                    if dual_write_enabled() and truth_write_table == "inventory_items":
                        try:
                            db.table("inventory_items_v2").update(payload2).eq("id", item_id).execute()
                        except Exception as e2:
                            try:
                                emit_migration_incident(
                                    user_id=user_id,
                                    correlation_id=receipt_id,
                                    incident_type="v2_write_failed",
                                    operation="update",
                                    v2_target="public.inventory_items_v2",
                                    error=str(e2),
                                    entity_id=str(item_id),
                                    payload={"endpoint": "POST /api/scanning/scan-receipt", "source_downgrade": True},
                                )
                            except Exception:
                                pass
                    return
                raise

        def _safe_insert_inventory(payload: Dict) -> None:
            try:
                if dual_write_enabled() and truth_write_table == "inventory_items" and not payload.get("id"):
                    payload["id"] = str(uuid4())
                db.table(truth_write_table).insert(payload).execute()
                if dual_write_enabled() and truth_write_table == "inventory_items":
                    try:
                        db.table("inventory_items_v2").insert(dict(payload)).execute()
                    except Exception as e:
                        try:
                            emit_migration_incident(
                                user_id=user_id,
                                correlation_id=receipt_id,
                                incident_type="v2_write_failed",
                                operation="insert",
                                v2_target="public.inventory_items_v2",
                                error=str(e),
                                entity_id=str(payload.get("id") or "") or None,
                                payload={"endpoint": "POST /api/scanning/scan-receipt"},
                            )
                        except Exception:
                            pass
            except Exception as e:
                if _is_source_check_violation(e) and payload.get("source") == "receipt":
                    payload2 = dict(payload)
                    payload2["source"] = "import"
                    db.table(truth_write_table).insert(payload2).execute()
                    if dual_write_enabled() and truth_write_table == "inventory_items":
                        try:
                            db.table("inventory_items_v2").insert(dict(payload2)).execute()
                        except Exception as e2:
                            try:
                                emit_migration_incident(
                                    user_id=user_id,
                                    correlation_id=receipt_id,
                                    incident_type="v2_write_failed",
                                    operation="insert",
                                    v2_target="public.inventory_items_v2",
                                    error=str(e2),
                                    entity_id=str(payload2.get("id") or "") or None,
                                    payload={"endpoint": "POST /api/scanning/scan-receipt", "source_downgrade": True},
                                )
                            except Exception:
                                pass
                    return
                raise

        for item in analysis.get("items", []):
            canonical = (item.get("canonical_name") or "").strip()
            if not canonical:
                # Fallback normalize if needed
                canonical = normalizer.normalize_name(item.get("raw_name") or "")
            if not canonical:
                continue

            incoming_qty = item.get("quantity")
            try:
                incoming_qty_f = float(incoming_qty) if incoming_qty is not None else 1.0
            except Exception:
                incoming_qty_f = 1.0

            incoming_unit = _normalize_unit(item.get("unit"))

            existing = (
                db.table(truth_write_table)
                .select("*")
                .eq("user_id", user_id)
                .eq("canonical_name", canonical)
                .eq("storage_location", storage)
                .eq("item_state", item_state)
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )

            merged_qty = incoming_qty_f
            merged_unit = incoming_unit

            confidence = item.get("confidence")
            try:
                confidence_f = float(confidence) if confidence is not None else None
            except Exception:
                confidence_f = None

            if existing.data:
                existing_item = existing.data[0]
                existing_qty = float(existing_item.get("quantity") or 0)
                existing_unit = _normalize_unit(existing_item.get("unit") or "pieces")

                update_payload = {
                    "display_name": existing_item.get("display_name") or _titleize(canonical),
                    "source": "receipt",
                    "is_current": True,
                    "last_seen_at": now_iso,
                    "last_seen_receipt_id": receipt_id,
                }
                if image_url and not existing_item.get("image_url"):
                    update_payload["image_url"] = image_url

                if incoming_unit == existing_unit:
                    merged_qty = existing_qty + incoming_qty_f
                    merged_unit = existing_unit
                    update_payload.update({"quantity": merged_qty, "unit": merged_unit})
                    if confidence_f is not None:
                        update_payload["scan_confidence"] = confidence_f
                    _safe_update_inventory(existing_item["id"], update_payload)
                    updated_count += 1
                elif UnitConverter.can_convert(incoming_unit, existing_unit):
                    converted = UnitConverter.convert(incoming_qty_f, incoming_unit, existing_unit)
                    merged_qty = existing_qty + float(converted)
                    merged_unit = existing_unit
                    update_payload.update({"quantity": merged_qty, "unit": merged_unit})
                    if confidence_f is not None:
                        update_payload["scan_confidence"] = confidence_f
                    _safe_update_inventory(existing_item["id"], update_payload)
                    updated_count += 1
                else:
                    _safe_insert_inventory(
                        {
                            "user_id": user_id,
                            "canonical_name": canonical,
                            "display_name": _titleize(canonical),
                            "quantity": incoming_qty_f,
                            "unit": incoming_unit,
                            "storage_location": storage,
                            "item_state": item_state,
                            "source": "receipt",
                            "scan_confidence": confidence_f,
                            "image_url": image_url,
                            "is_current": True,
                            "last_seen_at": now_iso,
                            "last_seen_receipt_id": receipt_id,
                        }
                    )
                    added_count += 1

            else:
                _safe_insert_inventory(
                    {
                        "user_id": user_id,
                        "canonical_name": canonical,
                        "display_name": _titleize(canonical),
                        "quantity": incoming_qty_f,
                        "unit": incoming_unit,
                        "storage_location": storage,
                        "item_state": item_state,
                        "source": "receipt",
                        "scan_confidence": confidence_f,
                        "image_url": image_url,
                        "is_current": True,
                        "last_seen_at": now_iso,
                        "last_seen_receipt_id": receipt_id,
                    }
                )
                added_count += 1

            pantry_items.append(
                {
                    "name": canonical,
                    "display_name": _titleize(canonical),
                    "quantity": merged_qty,
                    "unit": merged_unit,
                    "source": "receipt",
                }
            )

        message = f"Receipt scanned. Added {added_count}, updated {updated_count} items."

        return ScanReceiptResponse(
            success=True,
            receipt_id=receipt_id,
            added_count=added_count,
            updated_count=updated_count,
            pantry_items=pantry_items,
            metadata=analysis.get("metadata") or {},
            message=message,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Receipt scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Receipt scan failed: {str(e)}")


@router.post("/scan-receipt/preview", response_model=ScanReceiptPreviewResponse)
async def scan_receipt_preview(
    image: UploadFile = File(..., description="Receipt image file (JPEG/PNG)"),
    storage_location: str = Form(default="pantry"),
    user_id: str = Depends(get_current_user),
):
    """Scan a receipt and return detected items. Does NOT modify inventory."""

    try:
        if image.content_type not in ["image/jpeg", "image/jpg", "image/png"]:
            raise HTTPException(status_code=400, detail="Invalid image format. Use JPEG or PNG.")

        image_data = await image.read()
        if len(image_data) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Image too large. Maximum 10MB.")

        db = get_db_client()

        receipt_id = str(uuid4())
        now_iso = datetime.utcnow().isoformat()

        image_url = None
        try:
            expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
            image_url = upload_inventory_image(
                user_id=user_id,
                content=image_data,
                content_type=image.content_type,
                asset_type="receipt_image",
                source="receipt_scan_preview",
                expires_at=expires_at,
                links={"receipt_id": receipt_id},
            )
        except Exception as e:
            logger.warning(f"Failed to upload receipt image: {e}")

        try:
            db.table("receipt_scans").insert(
                {
                    "id": receipt_id,
                    "user_id": user_id,
                    "image_url": image_url,
                    "created_at": now_iso,
                    "status": "parsed",
                }
            ).execute()
        except Exception:
            pass

        profile = None
        try:
            profile = await get_full_profile(user_id)
        except Exception:
            profile = None

        vision_client = get_vision_client()
        analysis = await vision_client.analyze_receipt(
            image_data=image_data,
            user_preferences=profile,
        )

        if not analysis.get("success"):
            raise HTTPException(status_code=500, detail=f"Receipt analysis failed: {analysis.get('error')}")

        try:
            db.table("receipt_scans").update(
                {
                    "raw_text": analysis.get("raw_text"),
                    "analysis_json": analysis,
                    "status": "parsed",
                }
            ).eq("id", receipt_id).execute()
        except Exception:
            pass

        # Return items (no writes to inventory here)
        items = []
        for item in analysis.get("items", []) or []:
            if not isinstance(item, dict):
                continue
            items.append(
                {
                    "raw_name": item.get("raw_name"),
                    "canonical_name": item.get("canonical_name"),
                    "quantity": item.get("quantity"),
                    "unit": item.get("unit"),
                    "confidence": float(item.get("confidence")) if item.get("confidence") is not None else None,
                    "raw_line": item.get("raw_line"),
                }
            )

        return ScanReceiptPreviewResponse(
            success=True,
            receipt_id=receipt_id,
            items=items,
            metadata=analysis.get("metadata") or {},
            requires_confirmation=True,
            message="Receipt scanned. Please confirm items before adding to inventory.",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Receipt preview failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Receipt preview failed: {str(e)}")


@router.post("/scan-receipt/confirm", response_model=ScanReceiptResponse)
async def confirm_receipt_scan(
    request: ConfirmReceiptRequest,
    user_id: str = Depends(get_current_user),
):
    """Apply user-confirmed receipt items to inventory."""

    try:
        db = get_db_client()
        normalizer = get_normalizer()
        now_iso = datetime.utcnow().isoformat()

        storage = _scan_type_to_storage_location(request.storage_location)
        item_state = "raw"

        from app.core.unit_converter import UnitConverter

        added_count = 0
        updated_count = 0
        pantry_items: List[Dict] = []

        truth_write_table = inventory_truth_write_table()

        for item_in in request.items:
            raw_name = (item_in.raw_name or "").strip()
            canonical = (item_in.canonical_name or "").strip()
            display_name = (item_in.display_name or raw_name or canonical).strip()

            if not canonical:
                canonical = normalizer.normalize_name(raw_name or display_name)
            if not canonical:
                continue

            qty = item_in.quantity
            try:
                incoming_qty_f = float(qty) if qty is not None else 1.0
            except Exception:
                incoming_qty_f = 1.0

            incoming_unit = _normalize_unit(item_in.unit)

            existing = (
                db.table(truth_write_table)
                .select("*")
                .eq("user_id", user_id)
                .eq("canonical_name", canonical)
                .eq("storage_location", storage)
                .eq("item_state", item_state)
                .order("updated_at", desc=True)
                .limit(1)
                .execute()
            )

            merged_qty = incoming_qty_f
            merged_unit = incoming_unit

            confidence_f = None
            try:
                confidence_f = float(item_in.confidence) if item_in.confidence is not None else None
            except Exception:
                confidence_f = None

            if existing.data:
                existing_item = existing.data[0]
                existing_qty = float(existing_item.get("quantity") or 0)
                existing_unit = _normalize_unit(existing_item.get("unit") or "pieces")

                update_payload = {
                    "display_name": existing_item.get("display_name") or display_name or _titleize(canonical),
                    "source": "receipt",
                    "is_current": True,
                    "last_seen_at": now_iso,
                    "last_seen_receipt_id": request.receipt_id,
                }

                if incoming_unit == existing_unit:
                    merged_qty = existing_qty + incoming_qty_f
                    merged_unit = existing_unit
                    update_payload.update({"quantity": merged_qty, "unit": merged_unit})
                    if confidence_f is not None:
                        update_payload["scan_confidence"] = confidence_f
                    _dual_write_inventory(
                        db,
                        "update",
                        update_payload,
                        where={"id": existing_item["id"]},
                        user_id=user_id,
                        correlation_id=request.receipt_id,
                        endpoint="POST /api/scanning/scan-receipt/finalize",
                    )
                    updated_count += 1
                elif UnitConverter.can_convert(incoming_unit, existing_unit):
                    converted = UnitConverter.convert(incoming_qty_f, incoming_unit, existing_unit)
                    merged_qty = existing_qty + float(converted)
                    merged_unit = existing_unit
                    update_payload.update({"quantity": merged_qty, "unit": merged_unit})
                    if confidence_f is not None:
                        update_payload["scan_confidence"] = confidence_f
                    _dual_write_inventory(
                        db,
                        "update",
                        update_payload,
                        where={"id": existing_item["id"]},
                        user_id=user_id,
                        correlation_id=request.receipt_id,
                        endpoint="POST /api/scanning/scan-receipt/finalize",
                    )
                    updated_count += 1
                else:
                    _dual_write_inventory(
                        db,
                        "insert",
                        {
                            "user_id": user_id,
                            "canonical_name": canonical,
                            "display_name": display_name or _titleize(canonical),
                            "quantity": incoming_qty_f,
                            "unit": incoming_unit,
                            "storage_location": storage,
                            "item_state": item_state,
                            "source": "receipt",
                            "scan_confidence": confidence_f,
                            "is_current": True,
                            "last_seen_at": now_iso,
                            "last_seen_receipt_id": request.receipt_id,
                        },
                        user_id=user_id,
                        correlation_id=request.receipt_id,
                        endpoint="POST /api/scanning/scan-receipt/finalize",
                    )
                    added_count += 1
            else:
                _dual_write_inventory(
                    db,
                    "insert",
                    {
                        "user_id": user_id,
                        "canonical_name": canonical,
                        "display_name": display_name or _titleize(canonical),
                        "quantity": incoming_qty_f,
                        "unit": incoming_unit,
                        "storage_location": storage,
                        "item_state": item_state,
                        "source": "receipt",
                        "scan_confidence": confidence_f,
                        "is_current": True,
                        "last_seen_at": now_iso,
                        "last_seen_receipt_id": request.receipt_id,
                    },
                    user_id=user_id,
                    correlation_id=request.receipt_id,
                    endpoint="POST /api/scanning/scan-receipt/finalize",
                )
                added_count += 1

            pantry_items.append(
                {
                    "name": canonical,
                    "display_name": display_name or _titleize(canonical),
                    "quantity": merged_qty,
                    "unit": merged_unit,
                    "source": "receipt",
                }
            )

        try:
            db.table("receipt_scans").update(
                {
                    "status": "confirmed",
                    "confirmed_at": now_iso,
                }
            ).eq("id", request.receipt_id).eq("user_id", user_id).execute()
        except Exception:
            pass

        message = f"Receipt confirmed. Added {added_count}, updated {updated_count} items."
        return ScanReceiptResponse(
            success=True,
            receipt_id=request.receipt_id,
            added_count=added_count,
            updated_count=updated_count,
            pantry_items=pantry_items,
            metadata={"confirmed": True},
            message=message,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Receipt confirm failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Receipt confirm failed: {str(e)}")


@router.get("/history", response_model=ScanHistoryResponse)
async def get_scan_history(
    limit: int = 20,
    offset: int = 0,
    user_id: str = Depends(get_current_user)
):
    """
    Get user's scan history with accuracy stats
    
    - **limit**: Number of scans to return
    - **offset**: Pagination offset
    """
    try:
        db = get_db_client()
        
        # Get scans
        scans_result = db.table("ingredient_scans") \
            .select("*, detected_ingredients(*)") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .range(offset, offset + limit - 1) \
            .execute()
        
        # Get total count
        count_result = db.table("ingredient_scans") \
            .select("id", count="exact") \
            .eq("user_id", user_id) \
            .execute()
        
        total_scans = count_result.count if count_result.count else 0
        
        # Get accuracy stats
        accuracy_result = db.rpc("get_user_scanning_accuracy", {"p_user_id": user_id}).execute()
        accuracy_stats = accuracy_result.data[0] if accuracy_result.data else {
            "total_detections": 0,
            "confirmed_count": 0,
            "modified_count": 0,
            "rejected_count": 0,
            "accuracy_pct": 0
        }
        
        return ScanHistoryResponse(
            scans=scans_result.data,
            total_scans=total_scans,
            accuracy_stats=accuracy_stats
        )
        
    except Exception as e:
        logger.error(f"Failed to get scan history: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@router.get("/pantry")
async def get_user_pantry(
    background_tasks: BackgroundTasks,
    include_inactive: bool = False,
    maybe_days: int = 7,
    stale_days: int = 30,
    user_id: str = Depends(get_current_user)
):
    """
    Get user's current pantry inventory
    
    Returns list of confirmed ingredients with expiry tracking
    """
    t0 = time.perf_counter()
    try:
        db = get_db_client()

        now = datetime.now(timezone.utc)

        # Single-read contract with explicit phased flip-read gates.
        read_table = inventory_truth_read_table_for_user(user_id)

        items = (
            db.table(read_table)
            .select("*")
            .eq("user_id", user_id)
            .order("updated_at", desc=True)
            .execute()
        )
        v1_total_count = len(items.data or [])
        v1_qty_sum = 0.0
        pantry = []
        for item in items.data or []:
            if not isinstance(item, dict):
                continue

            status = _inventory_status(item, now=now, maybe_days=maybe_days, stale_days=stale_days)
            if not include_inactive and status in {"inactive", "stale"}:
                continue

            pantry.append(
                {
                    "id": item.get("id"),
                    "ingredient_name": item.get("canonical_name"),
                    "display_name": item.get("display_name") or _titleize(item.get("canonical_name") or ""),
                    "quantity": item.get("quantity"),
                    "unit": item.get("unit"),
                    "storage_location": item.get("storage_location"),
                    "item_state": item.get("item_state"),
                    "source": item.get("source"),
                    "status": status,
                    "notes": item.get("notes"),
                    "expiry_date": item.get("expiry_date"),
                }
            )

            try:
                v1_qty_sum += float(item.get("quantity") or 0.0)
            except Exception:
                pass

        v1_visible_count = len(pantry)

        if v2_shadow_read_enabled() and background_tasks is not None:
            corr = None
            try:
                # Prefer scan/session correlation if available later; fall back to a generated id.
                corr = str(uuid4())
            except Exception:
                corr = None
            background_tasks.add_task(
                _shadow_compare_pantry_v2,
                user_id=user_id,
                include_inactive=include_inactive,
                maybe_days=maybe_days,
                stale_days=stale_days,
                v1_visible_count=v1_visible_count,
                v1_total_count=v1_total_count,
                v1_qty_sum=v1_qty_sum,
                correlation_id=corr,
            )

        return {"success": True, "pantry": pantry, "total_items": v1_visible_count}
        
    except Exception as e:
        logger.error(f"Failed to get pantry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get pantry: {str(e)}")

    finally:
        # Best-effort latency telemetry (for regression dashboards/alerts).
        try:
            ms = int((time.perf_counter() - t0) * 1000)
            emit_event(
                event_type="api.latency",
                event_ts=datetime.now(timezone.utc).isoformat(),
                user_id=user_id,
                payload={"endpoint": "GET /api/scanning/pantry", "ms": ms},
            )
        except Exception:
            pass


@router.post("/pantry/weekly-cleanup", response_model=PantryCleanupResponse)
async def pantry_weekly_cleanup(
    stale_days: int = 30,
    user_id: str = Depends(get_current_user),
):
    """Mark long-unseen scan/receipt items as inactive so the pantry stays manageable.

    Notes:
    - This does NOT delete rows.
    - Only affects scan/receipt sourced raw items.
    """
    try:
        if stale_days <= 0:
            raise HTTPException(status_code=400, detail="stale_days must be > 0")

        db = get_db_client()
        now = datetime.now(timezone.utc)
        cutoff = (now - timedelta(days=stale_days)).isoformat()

        primary_table = inventory_truth_write_table()

        # Best-effort bulk update. Some rows may lack last_seen_at; handle those via a second pass.
        marked = 0
        try:
            res1 = (
                db.table(primary_table)
                .update({"is_current": False})
                .eq("user_id", user_id)
                .eq("item_state", "raw")
                .in_("source", ["scan", "receipt"])
                .eq("is_current", True)
                .lt("last_seen_at", cutoff)
                .execute()
            )
            marked += len(res1.data or [])
        except Exception as e:
            logger.warning(f"Pantry cleanup bulk pass (last_seen_at) failed: {e}")

        if dual_write_enabled() and primary_table == "inventory_items":
            try:
                (
                    db.table("inventory_items_v2")
                    .update({"is_current": False})
                    .eq("user_id", user_id)
                    .eq("item_state", "raw")
                    .in_("source", ["scan", "receipt"])
                    .eq("is_current", True)
                    .lt("last_seen_at", cutoff)
                    .execute()
                )
            except Exception as e:
                try:
                    emit_migration_incident(
                        user_id=user_id,
                        correlation_id=str(uuid4()),
                        incident_type="v2_write_failed",
                        operation="update",
                        v2_target="public.inventory_items_v2",
                        error=str(e),
                        payload={"endpoint": "POST /api/scanning/pantry/weekly-cleanup", "phase": "last_seen_at"},
                    )
                except Exception:
                    pass

        try:
            res2 = (
                db.table(primary_table)
                .update({"is_current": False})
                .eq("user_id", user_id)
                .eq("item_state", "raw")
                .in_("source", ["scan", "receipt"])
                .eq("is_current", True)
                .is_("last_seen_at", "null")
                .lt("updated_at", cutoff)
                .execute()
            )
            marked += len(res2.data or [])
        except Exception as e:
            logger.warning(f"Pantry cleanup bulk pass (updated_at) failed: {e}")

        if dual_write_enabled() and primary_table == "inventory_items":
            try:
                (
                    db.table("inventory_items_v2")
                    .update({"is_current": False})
                    .eq("user_id", user_id)
                    .eq("item_state", "raw")
                    .in_("source", ["scan", "receipt"])
                    .eq("is_current", True)
                    .is_("last_seen_at", "null")
                    .lt("updated_at", cutoff)
                    .execute()
                )
            except Exception as e:
                try:
                    emit_migration_incident(
                        user_id=user_id,
                        correlation_id=str(uuid4()),
                        incident_type="v2_write_failed",
                        operation="update",
                        v2_target="public.inventory_items_v2",
                        error=str(e),
                        payload={"endpoint": "POST /api/scanning/pantry/weekly-cleanup", "phase": "updated_at"},
                    )
                except Exception:
                    pass

        return PantryCleanupResponse(
            success=True,
            marked_inactive_count=marked,
            stale_days=stale_days,
            message=f"Marked {marked} items inactive (not seen in {stale_days} days).",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Pantry cleanup failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pantry cleanup failed: {str(e)}")


@router.get("/pantry/summary", response_model=PantrySummaryResponse)
async def pantry_summary(
    maybe_days: int = 7,
    stale_days: int = 30,
    max_verify: int = 5,
    user_id: str = Depends(get_current_user),
):
    """Return a lightweight pantry summary for planning.

    - **have**: fresh/high-confidence items (status=available)
    - **maybe_have**: older/uncertain items (status=maybe)
    - **verify**: up to max_verify items to ask the user about
    """
    try:
        db = get_db_client()
        now = datetime.now(timezone.utc)

        read_table = inventory_truth_read_table_for_user(user_id)

        items = (
            db.table(read_table)
            .select("id, canonical_name, display_name, quantity, unit, storage_location, item_state, source, is_current, last_seen_at, updated_at")
            .eq("user_id", user_id)
            .eq("item_state", "raw")
            .execute()
        )

        have: List[Dict] = []
        maybe_have: List[Dict] = []
        verify_candidates: List[Dict] = []

        for item in items.data or []:
            if not isinstance(item, dict):
                continue

            status = _inventory_status(item, now=now, maybe_days=maybe_days, stale_days=stale_days)
            if status in {"inactive", "stale"}:
                continue

            entry = {
                "id": item.get("id"),
                "ingredient_name": item.get("canonical_name"),
                "display_name": item.get("display_name") or _titleize(item.get("canonical_name") or ""),
                **({"session_id": session_id} if session_id else {}),
                **({"correlation_id": correlation_id} if correlation_id else {}),
                "quantity": item.get("quantity"),
                "unit": item.get("unit"),
                "storage_location": item.get("storage_location"),
                "source": item.get("source"),
                "status": status,
            }

            if status == "available":
                have.append(entry)
            else:
                maybe_have.append(entry)

                seen_at = _effective_seen_at(item)
                age_days = (now - seen_at).days if seen_at else 9999
                verify_candidates.append({**entry, "age_days": age_days})

        verify_candidates.sort(key=lambda x: x.get("age_days", 9999), reverse=True)
        verify = verify_candidates[: max(0, min(int(max_verify), 10))]
        for v in verify:
            v.pop("age_days", None)

        return PantrySummaryResponse(
            success=True,
            have=have,
            maybe_have=maybe_have,
            verify=verify,
            totals={
                "have": len(have),
                "maybe_have": len(maybe_have),
                "verify": len(verify),
            },
        )
    except Exception as e:
        logger.error(f"Pantry summary failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Pantry summary failed: {str(e)}")


@router.post("/feedback")
async def submit_feedback(
    request: SubmitFeedbackRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Submit feedback on detection quality
    
    - **scan_id**: ID of the scan
    - **feedback_type**: Type of feedback (correction/missing/false_positive/rating/comment)
    - **detected_name**: What AI detected (for corrections)
    - **correct_name**: What it should have been (for corrections)
    - **ratings**: Optional 1-5 star ratings
    - **comment**: Optional text comment
    """
    try:
        db = get_db_client()
        
        # Verify scan belongs to user
        scan = db.table("ingredient_scans").select("id").eq("id", request.scan_id).eq("user_id", user_id).execute()
        if not scan.data:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        # Insert feedback
        feedback_data = {
            "user_id": user_id,
            "scan_id": request.scan_id,
            "feedback_type": request.feedback_type
        }
        
        if request.detected_id:
            feedback_data["detected_id"] = request.detected_id
        if request.detected_name:
            feedback_data["detected_name"] = request.detected_name
        if request.correct_name:
            feedback_data["correct_name"] = request.correct_name
        if request.overall_rating:
            feedback_data["overall_rating"] = request.overall_rating
        if request.accuracy_rating:
            feedback_data["accuracy_rating"] = request.accuracy_rating
        if request.speed_rating:
            feedback_data["speed_rating"] = request.speed_rating
        if request.comment:
            feedback_data["comment"] = request.comment
        
        db.table("scan_feedback").insert(feedback_data).execute()
        
        return {
            "success": True,
            "message": "Thank you for your feedback! It helps improve detection accuracy."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to submit feedback: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to submit feedback: {str(e)}")


@router.delete("/pantry/{ingredient_name}")
async def remove_from_pantry(
    ingredient_name: str,
    user_id: str = Depends(get_current_user)
):
    """
    Remove ingredient from pantry (mark as used/removed)
    """
    try:
        db = get_db_client()

        normalizer = get_normalizer()
        canonical_name = normalizer.normalize_name(ingredient_name)
        
        # Soft-deactivate matching items (do not hard delete).
        primary_table = inventory_truth_write_table()
        update = {
            "is_current": False,
            "pantry_status": "consumed",
            "last_status_changed_at": datetime.utcnow().isoformat(),
        }
        result = (
            db.table(primary_table)
            .update(update)
            .eq("user_id", user_id)
            .eq("canonical_name", canonical_name)
            .execute()
        )

        if dual_write_enabled() and primary_table == "inventory_items":
            try:
                (
                    db.table("inventory_items_v2")
                    .update(update)
                    .eq("user_id", user_id)
                    .eq("canonical_name", canonical_name)
                    .execute()
                )
            except Exception:
                pass
        
        if not result.data:
            raise HTTPException(status_code=404, detail="Ingredient not found in pantry")
        
        return {
            "success": True,
            "message": f"Removed {canonical_name} from pantry"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to remove from pantry: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to remove: {str(e)}")


# ============================================================================
# NEW ENDPOINTS: Manual Entry & Serving Calculator
# ============================================================================

class ManualIngredientRequest(BaseModel):
    """Request to manually add ingredient"""
    ingredient_name: str
    quantity: Optional[float] = None
    unit: Optional[str] = "pieces"
    notes: Optional[str] = None


@router.post("/manual")
async def add_manual_ingredient(
    request: ManualIngredientRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Manually add ingredient to pantry
    
    Allows users to add ingredients without scanning:
    - Quick add from autocomplete
    - Voice input ("Add 2 tomatoes")
    - Bulk import from shopping list
    """
    try:
        from app.core.unit_converter import UnitConverter
        
        db = get_db_client()
        normalizer = get_normalizer()
        
        # Normalize ingredient name
        canonical_name = normalizer.normalize_name(request.ingredient_name)

        incoming_unit = _normalize_unit(request.unit)
        incoming_qty = float(request.quantity) if request.quantity is not None else 1.0
        
        # Validate unit if provided
        if request.unit:
            unit_category = UnitConverter.get_unit_category(request.unit)
            if unit_category == "unknown":
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown unit: {request.unit}. Try: grams, ml, pieces, cups"
                )
        
        # Check if ingredient already exists in canonical inventory
        truth_write_table = inventory_truth_write_table()
        existing = (
            db.table(truth_write_table)
            .select("*")
            .eq("user_id", user_id)
            .eq("canonical_name", canonical_name)
            .eq("storage_location", "pantry")
            .eq("item_state", "raw")
            .order("updated_at", desc=True)
            .limit(1)
            .execute()
        )
        
        if existing.data:
            old_item = existing.data[0]
            old_qty = float(old_item.get("quantity") or 0)
            old_unit = _normalize_unit(old_item.get("unit") or incoming_unit)
            
            # Try to convert and add quantities
            new_qty = old_qty
            if incoming_unit == old_unit:
                new_qty = old_qty + incoming_qty
            elif UnitConverter.can_convert(incoming_unit, old_unit):
                converted_qty = UnitConverter.convert(incoming_qty, incoming_unit, old_unit)
                new_qty = old_qty + float(converted_qty)
            else:
                logger.warning(f"Cannot convert {incoming_unit} to {old_unit} for {canonical_name}")
                new_qty = old_qty

            _dual_write_inventory(
                db,
                "update",
                {
                    "quantity": new_qty,
                    "unit": old_unit,
                    "display_name": old_item.get("display_name") or request.ingredient_name,
                    "source": "manual",
                    "scan_confidence": 1.0,
                    "notes": request.notes,
                },
                where={"id": old_item["id"]},
                user_id=user_id,
                endpoint="POST /api/scanning/manual-add",
            )
            
            return {
                "success": True,
                "action": "updated",
                "ingredient": canonical_name,
                "display_name": request.ingredient_name,
                "quantity": new_qty,
                "unit": old_unit,
                "confidence": 1.0,
                "message": f"Updated {canonical_name} quantity to {new_qty} {old_unit}"
            }
        else:
            result = _dual_write_inventory(
                db,
                "insert",
                {
                    "user_id": user_id,
                    "canonical_name": canonical_name,
                    "display_name": request.ingredient_name,
                    "quantity": incoming_qty,
                    "unit": incoming_unit,
                    "storage_location": "pantry",
                    "item_state": "raw",
                    "source": "manual",
                    "scan_confidence": 1.0,
                    "notes": request.notes,
                },
                user_id=user_id,
                endpoint="POST /api/scanning/manual-add",
            )
            
            return {
                "success": True,
                "action": "added",
                "ingredient": canonical_name,
                "display_name": request.ingredient_name,
                "quantity": incoming_qty,
                "unit": incoming_unit,
                "confidence": 1.0,
                "message": f"Added {canonical_name} to your pantry"
            }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to add manual ingredient: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to add ingredient: {str(e)}")


class CheckSufficiencyRequest(BaseModel):
    """Request to check recipe sufficiency"""
    recipe_id: Optional[str] = None
    recipe_ingredients: Optional[List[Dict[str, Any]]] = None
    recipe_servings: int = Field(default=4, ge=1, le=100)
    servings: int = Field(ge=1, le=100)


class CheckSufficiencyResponse(BaseModel):
    """Response with sufficiency status"""
    success: bool = True
    sufficient: bool
    missing: List[Dict]
    surplus: List[Dict]
    scaling_factor: float
    total_missing: int
    total_sufficient: int
    total_ingredients: int
    shopping_list: Optional[List[Dict]] = None
    message: Optional[str] = None


@router.post("/check-sufficiency", response_model=CheckSufficiencyResponse)
async def check_recipe_sufficiency(
    request: CheckSufficiencyRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Check if user has enough ingredients for recipe
    
    Answers: "Do I have enough to make this recipe for N people?"
    
    Returns:
    - sufficient: True/False
    - missing: List of ingredients to buy with quantities
    - surplus: List of ingredients with excess
    - shopping_list: Practical shopping list with rounded quantities
    """
    try:
        from app.core.serving_calculator import ServingCalculator
        
        db = get_db_client()
        
        normalizer = get_normalizer()

        # Minimal production logging for debugging (avoid logging ingredient names or full payload).
        try:
            uid_suffix = user_id[-6:] if isinstance(user_id, str) else "unknown"
        except Exception:
            uid_suffix = "unknown"

        logger.info(
            "check_sufficiency request uid_suffix=%s has_recipe_id=%s recipe_ingredients=%s recipe_servings=%s servings=%s",
            uid_suffix,
            bool(request.recipe_id),
            len(request.recipe_ingredients) if isinstance(request.recipe_ingredients, list) else 0,
            getattr(request, "recipe_servings", None),
            getattr(request, "servings", None),
        )

        # Resolve recipe ingredients
        recipe_ingredients: List[Dict[str, Any]] = []

        if isinstance(request.recipe_ingredients, list) and request.recipe_ingredients:
            # Accept from client (preferred path for LLM recipes)
            for ing in request.recipe_ingredients:
                if not isinstance(ing, dict):
                    continue
                name_raw = (ing.get("name") or ing.get("ingredient") or ing.get("canonical_name") or "").strip()
                if not name_raw:
                    continue
                try:
                    qty = float(ing.get("quantity") if ing.get("quantity") is not None else ing.get("amount") or 0)
                except Exception:
                    qty = 0.0
                unit = _normalize_unit((ing.get("unit") or "pieces"))
                recipe_ingredients.append(
                    {
                        "name": normalizer.normalize_name(name_raw),
                        "quantity": qty,
                        "unit": unit,
                    }
                )
        elif request.recipe_id:
            # Legacy path: attempt DB lookup
            recipe = (
                db.table("recipes")
                .select("*, recipe_ingredients(ingredient_name, quantity, unit)")
                .eq("id", request.recipe_id)
                .single()
                .execute()
            )
            if not recipe.data:
                raise HTTPException(status_code=404, detail="Recipe not found")
            for ing in recipe.data.get("recipe_ingredients") or []:
                try:
                    recipe_ingredients.append(
                        {
                            "name": normalizer.normalize_name((ing.get("ingredient_name") or "").strip()),
                            "quantity": float(ing.get("quantity") or 0),
                            "unit": _normalize_unit(ing.get("unit") or "pieces"),
                        }
                    )
                except Exception:
                    continue
        else:
            raise HTTPException(status_code=400, detail="Provide recipe_ingredients or recipe_id")

        if not recipe_ingredients:
            raise HTTPException(status_code=400, detail="No valid recipe ingredients provided")

        # Get user's canonical inventory (inventory_items)
        # Prefer current items when the schema supports it.
        read_table = inventory_truth_read_table_for_user(user_id)
        try:
            pantry = (
                db.table(read_table)
                .select("canonical_name, quantity, unit")
                .eq("user_id", user_id)
                .eq("item_state", "raw")
                .in_("storage_location", ["pantry", "fridge", "freezer"])
                .eq("is_current", True)
                .execute()
            )
        except Exception:
            pantry = (
                db.table(read_table)
                .select("canonical_name, quantity, unit")
                .eq("user_id", user_id)
                .eq("item_state", "raw")
                .in_("storage_location", ["pantry", "fridge", "freezer"])
                .execute()
            )

        pantry_dict: Dict[str, Dict[str, Any]] = {}
        for item in pantry.data or []:
            if not isinstance(item, dict):
                continue
            name = (item.get("canonical_name") or "").strip()
            if not name:
                continue
            # Always normalize to ensure stable matching with recipe_ingredients.
            key = normalizer.normalize_name(name)
            if not key:
                continue
            try:
                qty = float(item.get("quantity") or 0)
            except Exception:
                qty = 0.0
            unit = _normalize_unit(item.get("unit") or "pieces")

            existing = pantry_dict.get(key)
            if not isinstance(existing, dict):
                pantry_dict[key] = {"quantity": qty, "unit": unit}
                continue

            # Aggregate quantities for duplicate keys (best-effort).
            try:
                from app.core.unit_converter import UnitConverter

                existing_unit = _normalize_unit(existing.get("unit") or unit)
                existing_qty = float(existing.get("quantity") or 0)

                if existing_unit and unit and existing_unit != unit:
                    if UnitConverter.can_convert(unit, existing_unit):
                        qty = UnitConverter.convert(qty, unit, existing_unit)
                        unit = existing_unit
                    elif UnitConverter.can_convert(existing_unit, unit):
                        existing_qty = UnitConverter.convert(existing_qty, existing_unit, unit)
                        existing_unit = unit
                    else:
                        # Different categories; keep the larger quantity to avoid inflation.
                        existing["quantity"] = max(existing_qty, qty)
                        existing["unit"] = existing_unit
                        continue

                existing["quantity"] = float(existing_qty) + float(qty)
                existing["unit"] = existing_unit
            except Exception:
                # Fallback: last write wins (still normalized).
                pantry_dict[key] = {"quantity": qty, "unit": unit}

        logger.info(
            "check_sufficiency inventory uid_suffix=%s pantry_items=%s",
            uid_suffix,
            len(pantry_dict),
        )
        
        # Calculate sufficiency
        result = ServingCalculator.check_sufficiency(
            pantry_items=pantry_dict,
            recipe_ingredients=recipe_ingredients,
            recipe_servings=request.recipe_servings,
            needed_servings=request.servings
        )
        
        # Generate shopping list if missing ingredients
        shopping_list = None
        if result["missing"]:
            shopping_list = ServingCalculator.generate_shopping_list(result["missing"])
        
        msg = (
            "You have enough ingredients."
            if result.get("sufficient")
            else f"Missing {result.get('total_missing', 0)} ingredient(s)."
        )

        logger.info(
            "check_sufficiency result uid_suffix=%s sufficient=%s missing=%s scaling_factor=%s",
            uid_suffix,
            bool(result.get("sufficient")),
            int(result.get("total_missing") or 0),
            float(result.get("scaling_factor") or 0),
        )

        return CheckSufficiencyResponse(
            sufficient=result["sufficient"],
            missing=result["missing"],
            surplus=result["surplus"],
            scaling_factor=result["scaling_factor"],
            total_missing=result["total_missing"],
            total_sufficient=result["total_sufficient"],
            total_ingredients=result["total_ingredients"],
            shopping_list=shopping_list,
            message=msg,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to check sufficiency: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check sufficiency: {str(e)}")


# ============================================================================
# BARCODE SCANNING
# ============================================================================

class BarcodeScanRequest(BaseModel):
    barcode: str = Field(..., description="UPC/EAN barcode number")
    image_url: Optional[str] = Field(None, description="Optional image of the product")
    add_to_inventory: bool = Field(True, description="Automatically add to inventory")
    quantity: Optional[float] = Field(None, description="Override quantity")
    storage_location: Optional[str] = Field("pantry", description="pantry/fridge/freezer")


class BarcodeScanResponse(BaseModel):
    scan_id: UUID
    barcode: str
    product_name: str
    brand: Optional[str]
    quantity_value: Optional[float]
    quantity_unit: Optional[str]
    expiry_date: Optional[str]
    image_url: Optional[str]
    ingredient_canonical_name: Optional[str]
    confidence: float
    data_source: str
    added_to_inventory: bool


@router.post("/barcode", response_model=BarcodeScanResponse)
async def scan_barcode(
    request: BarcodeScanRequest,
    user = Depends(get_current_user),
    db = Depends(get_db_client)
):
    """
    Scan a barcode (UPC/EAN) and get product information
    Automatically adds to inventory if requested
    """
    from app.integrations.openfoodfacts import get_openfoodfacts_client
    
    try:
        # Look up barcode in our database first
        existing = await db.fetchrow(
            "SELECT * FROM product_barcodes WHERE upc_ean = $1",
            request.barcode
        )
        
        if existing:
            product_data = dict(existing)
            product_data["data_source"] = "cached"
            logger.info(f"Barcode {request.barcode} found in cache")
        else:
            # Look up in OpenFoodFacts
            off_client = get_openfoodfacts_client()
            product_data = await off_client.lookup_barcode(request.barcode)
            
            if not product_data:
                raise HTTPException(status_code=404, detail="Barcode not found")
            
            # Cache the barcode data
            await db.execute(
                """
                INSERT INTO product_barcodes 
                (upc_ean, product_name, brand, manufacturer, quantity_value, quantity_unit,
                 country_code, image_url, nutrition_facts, external_id, data_source)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (upc_ean) DO UPDATE SET
                    product_name = EXCLUDED.product_name,
                    last_scanned_at = NOW(),
                    scan_count = product_barcodes.scan_count + 1
                """,
                product_data["barcode"],
                product_data["product_name"],
                product_data["brand"],
                product_data["manufacturer"],
                product_data["quantity_value"],
                product_data["quantity_unit"],
                product_data["country_code"],
                product_data["image_url"],
                product_data.get("nutrition_facts"),
                product_data.get("external_id"),
                product_data["data_source"],
            )
        
        # Try to match to master ingredient
        ingredient_name = None
        if product_data.get("product_name"):
            # Search master ingredients
            results = await db.fetch(
                "SELECT * FROM search_ingredients_multilang($1, 'en', 5)",
                product_data["product_name"]
            )
            if results:
                ingredient_name = results[0]["canonical_name"]
        
        # Create barcode scan record
        scan_id = uuid4()
        await db.execute(
            """
            INSERT INTO barcode_scans
            (id, user_id, barcode, barcode_type, product_name, brand,
             quantity_value, quantity_unit, image_url, confidence, data_source)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
            """,
            scan_id,
            user["id"],
            request.barcode,
            "EAN13" if len(request.barcode) == 13 else "UPCA",
            product_data["product_name"],
            product_data.get("brand"),
            request.quantity or product_data.get("quantity_value"),
            product_data.get("quantity_unit"),
            request.image_url or product_data.get("image_url"),
            0.95,
            product_data["data_source"],
        )
        
        # Add to inventory if requested
        added_to_inventory = False
        if request.add_to_inventory and ingredient_name:
            quantity_val = request.quantity or product_data.get("quantity_value", 1)
            unit = product_data.get("quantity_unit", "pieces")
            
            await db.execute(
                """
                INSERT INTO inventory_items
                (id, user_id, canonical_name, current_quantity, unit, storage_location,
                 barcode, image_url, image_source, is_current)
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, true)
                """,
                uuid4(),
                user["id"],
                ingredient_name,
                Decimal(str(quantity_val)),
                unit,
                request.storage_location,
                request.barcode,
                request.image_url or product_data.get("image_url"),
                "scan",
            )
            added_to_inventory = True
            
            # Update barcode scan record
            await db.execute(
                "UPDATE barcode_scans SET added_to_inventory = true WHERE id = $1",
                scan_id
            )
        
        return BarcodeScanResponse(
            scan_id=scan_id,
            barcode=request.barcode,
            product_name=product_data["product_name"],
            brand=product_data.get("brand"),
            quantity_value=product_data.get("quantity_value"),
            quantity_unit=product_data.get("quantity_unit"),
            expiry_date=None,  # TODO: Add OCR for expiry date
            image_url=product_data.get("image_url"),
            ingredient_canonical_name=ingredient_name,
            confidence=0.95,
            data_source=product_data["data_source"],
            added_to_inventory=added_to_inventory,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Barcode scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CONTAINER SCANNING
# ============================================================================

class ContainerScanRequest(BaseModel):
    image_url: Optional[str] = None
    scan_type: str = Field("container", description="container/transparent_jar/glass_bottle")
    user_hints: Optional[Dict[str, Any]] = Field(None, description="User hints like expected ingredient")


class ContainerScanResponse(BaseModel):
    scan_id: UUID
    container_type: Optional[str]
    container_material: Optional[str]
    transparency_level: Optional[str]
    detected_ingredient: Optional[str]
    visual_cues: Dict[str, Any]
    estimated_quantity: Optional[float]
    estimated_unit: Optional[str]
    confidence_ingredient: float
    confidence_quantity: float


@router.post("/container", response_model=ContainerScanResponse)
async def scan_container(
    image: UploadFile = File(...),
    scan_type: str = Form("container"),
    expected_ingredient: Optional[str] = Form(None),
    user = Depends(get_current_user),
    db = Depends(get_db_client)
):
    """
    Scan ingredients in containers (jars, bottles, transparent containers)
    Uses enhanced vision model to identify through transparency
    """
    from app.core.vision_api import get_vision_client
    from app.core.media_storage import upload_inventory_image
    from app.core.quantity_estimator import QuantityEstimator, BoundingBox
    
    try:
        # Upload image
        image_bytes = await image.read()
        image_obj = Image.open(io.BytesIO(image_bytes))

        # Create scan id early so we can link media assets.
        scan_id = uuid4()

        image_url = None
        try:
            expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
            image_url = upload_inventory_image(
                user_id=user["id"],
                content=image_bytes,
                content_type=image.content_type,
                asset_type="container_scan",
                source="container_scan",
                expires_at=expires_at,
                links={"container_scan_id": str(scan_id)},
            )
        except Exception:
            image_url = None
        
        # Enhanced vision prompt for container recognition
        vision_client = get_vision_client()
        
        prompt = """Analyze this image of an ingredient in a container.

CONTAINER ANALYSIS:
1. Container type: jar/bottle/plastic_container/glass_jar/ziplock_bag/bowl
2. Material: glass/plastic/metal
3. Transparency: transparent/translucent/opaque

INGREDIENT IDENTIFICATION:
4. Visual cues of the ingredient inside:
   - Color (white, brown, yellow, green, etc.)
   - Texture (grainy, powdery, liquid, solid, chunky)
   - Particle size (fine powder, small grains, large pieces)
5. Ingredient name based on visual characteristics
6. Fill level percentage (0-100%)

REFERENCE OBJECTS:
7. Any reference objects visible (hand, coin, phone, spoon) for size estimation

Return JSON:
{
  "container_type": "glass_jar",
  "container_material": "glass",
  "transparency_level": "transparent",
  "visual_cues": {
    "color": "white",
    "texture": "grainy",
    "particle_size": "small_grains"
  },
  "detected_ingredient": "rice",
  "confidence": 0.85,
  "fill_percentage": 75,
  "reference_objects": [{"type": "hand", "bbox": {...}}],
  "ingredient_bbox": {"x_min": 100, "y_min": 50, "x_max": 300, "y_max": 400}
}"""
        
        if expected_ingredient:
            prompt += f"\n\nUser expects this to be: {expected_ingredient}"
        
        vision_result = await vision_client.analyze_ingredient_image(
            image_bytes, 
            prompt_override=prompt
        )
        
        # Extract detection results
        container_type = vision_result.get("container_type")
        detected_ingredient = vision_result.get("detected_ingredient")
        visual_cues = vision_result.get("visual_cues", {})
        confidence = vision_result.get("confidence", 0.70)
        fill_percentage = vision_result.get("fill_percentage", 75)
        
        # Estimate quantity
        estimator = QuantityEstimator()
        quantity_estimate = None
        quantity_value = None
        quantity_unit = None
        quantity_confidence = 0.0
        
        if vision_result.get("ingredient_bbox"):
            bbox_data = vision_result["ingredient_bbox"]
            ingredient_bbox = BoundingBox(
                x_min=bbox_data["x_min"],
                y_min=bbox_data["y_min"],
                x_max=bbox_data["x_max"],
                y_max=bbox_data["y_max"],
                image_width=image_obj.width,
                image_height=image_obj.height,
            )
            
            # Detect reference objects
            reference_objects = estimator.detect_reference_objects_from_vision(
                vision_result, image_obj.width, image_obj.height
            )
            
            quantity_estimate = estimator.estimate_from_bbox_and_reference(
                ingredient_bbox,
                reference_objects,
                container_type,
                fill_percentage
            )
            
            quantity_value = quantity_estimate.estimated_value
            quantity_unit = quantity_estimate.unit
            quantity_confidence = quantity_estimate.confidence
            
            # Convert to weight if we have density data
            if detected_ingredient:
                density_row = await db.fetchrow(
                    """
                    SELECT density_g_per_ml, confidence
                    FROM ingredient_densities id
                    JOIN master_ingredients mi ON id.ingredient_id = mi.id
                    WHERE mi.canonical_name = $1 AND id.form = 'raw'
                    LIMIT 1
                    """,
                    detected_ingredient
                )
                
                if density_row:
                    weight_estimate = estimator.convert_volume_to_weight(
                        quantity_value,
                        float(density_row["density_g_per_ml"]),
                        float(density_row["confidence"])
                    )
                    quantity_value = weight_estimate.estimated_value
                    quantity_unit = weight_estimate.unit
                    quantity_confidence = weight_estimate.confidence
        
        # Save container scan
        await db.execute(
            """
            INSERT INTO container_scans
            (id, user_id, image_url, scan_type, container_type, container_material,
             transparency_level, detected_ingredient_name, visual_cues,
             estimated_quantity, estimated_unit, confidence_ingredient, confidence_quantity)
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
            """,
            scan_id,
            user["id"],
            image_url,
            scan_type,
            container_type,
            vision_result.get("container_material"),
            vision_result.get("transparency_level"),
            detected_ingredient,
            visual_cues,
            quantity_value,
            quantity_unit,
            confidence,
            quantity_confidence,
        )
        
        return ContainerScanResponse(
            scan_id=scan_id,
            container_type=container_type,
            container_material=vision_result.get("container_material"),
            transparency_level=vision_result.get("transparency_level"),
            detected_ingredient=detected_ingredient,
            visual_cues=visual_cues,
            estimated_quantity=quantity_value,
            estimated_unit=quantity_unit,
            confidence_ingredient=confidence,
            confidence_quantity=quantity_confidence,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Container scan failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# GLOBAL INGREDIENTS SEARCH
# ============================================================================

class IngredientSearchResponse(BaseModel):
    id: UUID
    canonical_name: str
    matched_name: str
    match_language: str
    category: str
    default_image_url: Optional[str]
    relevance: float


@router.get("/ingredients/search-global", response_model=List[IngredientSearchResponse])
async def search_global_ingredients(
    query: str,
    lang: str = "en",
    limit: int = 20,
    db = Depends(get_db_client)
):
    """
    Search ingredients in multiple languages
    Supported languages: en, hi, ta, es, zh, ar
    """
    try:
        results = await db.fetch(
            "SELECT * FROM search_ingredients_multilang($1, $2, $3)",
            query, lang, limit
        )
        
        return [
            IngredientSearchResponse(
                id=row["id"],
                canonical_name=row["canonical_name"],
                matched_name=row["matched_name"],
                match_language=row["match_language"],
                category=row["category"] or "other",
                default_image_url=row["default_image_url"],
                relevance=float(row["relevance"]),
            )
            for row in results
        ]
        
    except Exception as e:
        logger.error(f"Ingredient search failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
