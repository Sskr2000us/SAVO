from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db_client():
    # Allow running from repo root.
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    services_root = os.path.join(repo_root, "services", "api")
    if services_root not in sys.path:
        sys.path.insert(0, services_root)

    from app.core.database import get_db_client  # type: ignore

    return get_db_client()


def _best_effort_text(payload: Dict[str, Any]) -> str:
    # Keep deterministic and minimal.
    if not isinstance(payload, dict):
        return ""
    item = payload.get("item")
    if isinstance(item, dict):
        for k in ("canonical_name", "display_name", "name"):
            v = item.get(k)
            if isinstance(v, str) and v.strip():
                return v.strip()
    # Fallback: common keys
    for k in ("canonical_name", "name", "query"):
        v = payload.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description="Process vector_sync_queue jobs (manual runner; no cron)")
    ap.add_argument("--max", type=int, default=50, help="Max queued jobs to process")
    ap.add_argument("--user-id", default=None, help="Optional user UUID filter")
    ap.add_argument("--dry-run", action="store_true", help="Do not update DB status")
    args = ap.parse_args()

    db = _get_db_client()

    q = db.table("vector_sync_queue").select("*").eq("status", "queued").order("queued_at", desc=False).limit(int(args.max))
    if args.user_id:
        q = q.eq("user_id", args.user_id)

    res = q.execute()
    jobs: List[Dict[str, Any]] = [j for j in (res.data or []) if isinstance(j, dict)]

    if not jobs:
        print("No queued vector jobs")
        return 0

    # Load providers (currently noop by default).
    from app.core.vector.runtime import get_embedding_provider, get_vector_index  # type: ignore

    embedder = get_embedding_provider()
    index = get_vector_index()

    processed = 0
    failed = 0

    for job in jobs:
        job_id = str(job.get("id") or "")
        user_id = str(job.get("user_id") or "") or None
        entity_id = str(job.get("entity_id") or "") or None
        embedding_version = str(job.get("embedding_version") or "v0")
        payload = job.get("payload") if isinstance(job.get("payload"), dict) else {}

        namespace = f"user:{user_id}" if user_id else "global"
        vector_id = entity_id or job_id
        text = _best_effort_text(payload)

        try:
            if not args.dry_run:
                db.table("vector_sync_queue").update(
                    {
                        "status": "processing",
                        "attempts": int(job.get("attempts") or 0) + 1,
                        "last_error": None,
                    }
                ).eq("id", job_id).execute()

            emb = embedder.embed_text(text=text or vector_id, embedding_version=embedding_version)
            index.upsert(namespace=namespace, vectors=[(vector_id, emb)], metadata_by_id={vector_id: {"user_id": user_id}})

            if not args.dry_run:
                db.table("vector_sync_queue").update(
                    {"status": "done", "processed_at": _now_iso(), "last_error": None}
                ).eq("id", job_id).execute()

            processed += 1
        except Exception as e:
            failed += 1
            if not args.dry_run:
                db.table("vector_sync_queue").update(
                    {"status": "failed", "processed_at": _now_iso(), "last_error": str(e)[:500]}
                ).eq("id", job_id).execute()

    print(f"processed={processed} failed={failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
