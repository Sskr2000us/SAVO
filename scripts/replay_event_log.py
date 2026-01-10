from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _parse_iso(s: str) -> datetime:
    raw = (s or "").strip()
    if not raw:
        raise ValueError("timestamp required")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    dt = datetime.fromisoformat(raw)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


@dataclass(frozen=True)
class Interpreter:
    version: str

    def apply(self, state: Dict[str, Dict[str, Any]], event: Dict[str, Any]) -> None:
        et = str(event.get("event_type") or "")
        payload = event.get("payload")
        if not isinstance(payload, dict):
            payload = {}

        if et == "inventory.item_upserted":
            item = payload.get("item")
            if isinstance(item, dict):
                iid = str(item.get("id") or payload.get("entity_id") or "")
            else:
                iid = str(payload.get("entity_id") or "")
            if not iid:
                return
            if not isinstance(item, dict):
                # Fallback: store payload itself
                item = {"id": iid, **payload}
            state[iid] = item
            return

        if et == "inventory.item_deactivated":
            iid = str(event.get("entity_id") or payload.get("entity_id") or "")
            if not iid:
                return
            cur = state.get(iid) or {"id": iid}
            if not isinstance(cur, dict):
                cur = {"id": iid}
            upd = payload.get("update")
            if isinstance(upd, dict):
                cur.update(upd)
            else:
                cur["is_current"] = False
            state[iid] = cur
            return


def _get_db_client():
    # Allow running from repo root.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    services_root = os.path.join(repo_root, "services", "api")
    if services_root not in sys.path:
        sys.path.insert(0, services_root)

    from app.core.database import get_db_client  # type: ignore

    return get_db_client()


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay event_log into append-only replay outputs")
    ap.add_argument("--user-id", required=True, help="Target user UUID")
    ap.add_argument("--from-ts", required=False, help="Lower bound ISO timestamp")
    ap.add_argument("--to-ts", required=False, help="Upper bound ISO timestamp")
    ap.add_argument(
        "--interpreter-version",
        default="pantry_replay_v1",
        help="Version string for deterministic replay semantics",
    )
    ap.add_argument(
        "--write",
        action="store_true",
        help="Write outputs to replay_runs + replay_inventory_snapshots (append-only)",
    )
    ap.add_argument(
        "--enqueue-vector",
        action="store_true",
        help="Also enqueue vector sync jobs for replayed inventory events (manual/ops; best-effort)",
    )
    ap.add_argument(
        "--max-events",
        type=int,
        default=20000,
        help="Safety limit for fetched events",
    )
    args = ap.parse_args()

    user_id = args.user_id
    from_ts = _parse_iso(args.from_ts) if args.from_ts else None
    to_ts = _parse_iso(args.to_ts) if args.to_ts else None

    db = _get_db_client()

    q = (
        db.table("event_log")
        .select("id,event_type,event_ts,user_id,entity_id,entity_type,payload")
        .eq("user_id", user_id)
        .in_("event_type", ["inventory.item_upserted", "inventory.item_deactivated"])
    )
    if from_ts is not None:
        q = q.gte("event_ts", _iso(from_ts))
    if to_ts is not None:
        q = q.lte("event_ts", _iso(to_ts))

    res = q.order("event_ts", desc=False).limit(int(args.max_events)).execute()
    events: List[Dict[str, Any]] = [e for e in (res.data or []) if isinstance(e, dict)]

    interpreter = Interpreter(version=str(args.interpreter_version))
    state: Dict[str, Dict[str, Any]] = {}

    for ev in events:
        interpreter.apply(state, ev)

    # Optional: enqueue vector work from replayed events (placeholder rebuild).
    if args.enqueue_vector:
        try:
            from app.core.vector.sync import enqueue_vector_sync  # type: ignore

            for ev in events:
                enqueue_vector_sync(
                    user_id=user_id,
                    event_type=str(ev.get("event_type") or ""),
                    event_ts=str(ev.get("event_ts") or "") or None,
                    entity_type=str(ev.get("entity_type") or "") or None,
                    entity_id=str(ev.get("entity_id") or "") or None,
                    payload=ev.get("payload") if isinstance(ev.get("payload"), dict) else {},
                )
        except Exception:
            pass

    # Emit summary.
    summary = {
        "user_id": user_id,
        "interpreter_version": interpreter.version,
        "from_ts": _iso(from_ts) if from_ts else None,
        "to_ts": _iso(to_ts) if to_ts else None,
        "events": len(events),
        "items": len(state),
    }

    if not args.write:
        print(json.dumps({"summary": summary, "items": list(state.values())[:50]}, indent=2, default=str))
        return 0

    # Write append-only outputs.
    run = (
        db.table("replay_runs")
        .insert(
            {
                "user_id": user_id,
                "from_ts": _iso(from_ts) if from_ts else None,
                "to_ts": _iso(to_ts) if to_ts else None,
                "interpreter_version": interpreter.version,
                "metadata": {"events": len(events)},
            }
        )
        .execute()
    )
    run_id = None
    try:
        run_id = (run.data or [{}])[0].get("id")
    except Exception:
        run_id = None

    if not run_id:
        raise RuntimeError("Failed to create replay_runs row")

    rows = []
    for item_id, item in state.items():
        if not isinstance(item, dict):
            continue
        rows.append(
            {
                "run_id": run_id,
                "user_id": user_id,
                "inventory_item_id": item.get("id") or item_id,
                "canonical_name": item.get("canonical_name"),
                "storage_location": item.get("storage_location"),
                "item_state": item.get("item_state"),
                "snapshot": item,
            }
        )

    # Chunk inserts.
    chunk_size = 500
    for i in range(0, len(rows), chunk_size):
        db.table("replay_inventory_snapshots").insert(rows[i : i + chunk_size]).execute()

    print(json.dumps({"summary": summary, "run_id": run_id, "snapshots_written": len(rows)}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
