from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Tuple

from app.core.database import get_db_client


_threshold_cache: Dict[str, Tuple[float, bool]] = {}


def _thresholds_met_cached(user_id: str) -> bool:
    """Best-effort threshold check with a short in-process cache.

    Avoids counting on every event emission.
    """
    now = datetime.now(timezone.utc).timestamp()
    cached = _threshold_cache.get(user_id)
    if cached is not None:
        ts, ok = cached
        if (now - ts) <= 300:  # 5 minutes
            return ok

    ok = thresholds_met(user_id=user_id)
    _threshold_cache[user_id] = (now, ok)
    return ok


def thresholds_met(*, user_id: str) -> bool:
    """Check vector entry thresholds.

    Thresholds are configured via env vars in settings:
    - SAVO_VECTOR_MIN_ACTIVE_PANTRY_ITEMS
    - SAVO_VECTOR_MIN_RECIPES
    """
    try:
        min_items = int(os.getenv("SAVO_VECTOR_MIN_ACTIVE_PANTRY_ITEMS") or "0")
    except Exception:
        min_items = 0
    try:
        min_recipes = int(os.getenv("SAVO_VECTOR_MIN_RECIPES") or "0")
    except Exception:
        min_recipes = 0

    if min_items <= 0 and min_recipes <= 0:
        return True

    db = get_db_client()

    # Pantry count (best-effort). Prefer the current truth view if available.
    pantry_count = 0
    try:
        from app.core.schema_migration import inventory_truth_read_table_for_user

        read_table = inventory_truth_read_table_for_user(user_id)
    except Exception:
        read_table = "inventory_items"

    try:
        q = db.table(read_table).select("id", count="exact").eq("user_id", user_id)
        # Prefer current items when schema supports.
        q = q.eq("is_current", True)
        res = q.execute()
        pantry_count = int(getattr(res, "count", 0) or 0)
    except Exception:
        pantry_count = 0

    recipe_count = 0
    if min_recipes > 0:
        try:
            res = db.table("recipes").select("id", count="exact").execute()
            recipe_count = int(getattr(res, "count", 0) or 0)
        except Exception:
            recipe_count = 0

    if min_items > 0 and pantry_count < min_items:
        return False
    if min_recipes > 0 and recipe_count < min_recipes:
        return False
    return True


def enqueue_vector_sync(
    *,
    user_id: Optional[str],
    event_type: str,
    event_ts: Optional[str],
    entity_type: Optional[str],
    entity_id: Optional[str],
    payload: Optional[Dict[str, Any]],
) -> None:
    """Event-driven vector sync enqueue (best-effort).

    This function MUST NOT raise.
    """
    try:
        embedding_version = (os.getenv("SAVO_EMBEDDING_VERSION") or "v0").strip() or "v0"
        embedding_provider = (os.getenv("SAVO_EMBEDDING_PROVIDER") or "noop").strip() or "noop"

        db = get_db_client()
        db.table("vector_sync_queue").insert(
            {
                "user_id": user_id,
                "event_type": event_type,
                "event_ts": event_ts,
                "entity_type": entity_type,
                "entity_id": entity_id,
                "embedding_provider": embedding_provider,
                "embedding_version": embedding_version,
                "payload": payload or {},
                "status": "queued",
                "attempts": 0,
                "processed_at": None,
                "last_error": None,
            }
        ).execute()
    except Exception:
        return


def vector_enabled() -> bool:
    return (os.getenv("SAVO_VECTOR_ENABLED") or "false").strip().lower() == "true"


def should_enqueue_event(event_type: str) -> bool:
    # Strict allowlist: only event-driven updates; no cron jobs.
    return event_type in {
        "inventory.item_upserted",
        "inventory.item_deactivated",
        "recipe.saved",
        "recipe.updated",
    }


def maybe_enqueue_from_event(
    *,
    user_id: Optional[str],
    event_type: str,
    entity_type: Optional[str],
    entity_id: Optional[str],
    payload: Optional[Dict[str, Any]],
    event_ts: Optional[str] = None,
) -> None:
    try:
        if not vector_enabled():
            return
        if not should_enqueue_event(event_type):
            return
        if user_id and not _thresholds_met_cached(str(user_id)):
            return
        enqueue_vector_sync(
            user_id=user_id,
            event_type=event_type,
            event_ts=event_ts or datetime.now(timezone.utc).isoformat(),
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
        )
    except Exception:
        return
