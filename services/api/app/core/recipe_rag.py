from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_RAG_CACHE: dict[str, Any] = {
    "path": None,
    "mtime": None,
    "items": None,
    "embeddings": {},  # id -> List[float]
}


def _find_bowl_corpus_path() -> Path:
    here = Path(__file__).resolve()
    # services/api/app/core/recipe_rag.py -> services/api/app/data/indian_pantry_bowl_corpus.json
    candidate = here.parents[1] / "data" / "indian_pantry_bowl_corpus.json"
    return candidate


def _load_bowl_corpus() -> list[dict[str, Any]]:
    path = _find_bowl_corpus_path()
    if not path.exists():
        return []

    try:
        mtime = path.stat().st_mtime
    except Exception:
        mtime = None

    if _RAG_CACHE.get("items") is not None and _RAG_CACHE.get("path") == str(path) and _RAG_CACHE.get("mtime") == mtime:
        return list(_RAG_CACHE.get("items") or [])

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            return []
        items = [x for x in data if isinstance(x, dict)]
        _RAG_CACHE.update({"path": str(path), "mtime": mtime, "items": items})
        return list(items)
    except Exception:
        return []


def _tokenize(text: str) -> set[str]:
    t = (text or "").lower()
    out: set[str] = set()
    cur: list[str] = []
    for ch in t:
        if ch.isalnum() or ch in {"-", "+"}:
            cur.append(ch)
        else:
            if cur:
                out.add("".join(cur))
                cur = []
    if cur:
        out.add("".join(cur))
    # lightweight stopwords
    out -= {"and", "with", "the", "a", "an", "style", "bowl", "recipe"}
    return out


def _corpus_item_text(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for k in ("title", "cuisine", "region"):
        if item.get(k):
            parts.append(str(item.get(k)))
    ki = item.get("key_ingredients")
    if isinstance(ki, list):
        parts.extend([str(x) for x in ki if x is not None])
    tags = item.get("tags")
    if isinstance(tags, list):
        parts.extend([str(x) for x in tags if x is not None])
    return " ".join(parts)


async def pick_pantry_bowl_exemplars(
    *,
    pantry_names: List[str],
    request_text: str,
    cuisine: Optional[str],
    limit: int = 4,
    prefer_embeddings: bool = True,
) -> List[Dict[str, Any]]:
    """Return small, safe exemplars for pantry-bowl composition.

    Uses a tiny curated JSON corpus (non-copyrighted, internal). If OPENAI embeddings are
    available, ranks by semantic similarity; otherwise, ranks by ingredient/token overlap.
    """

    items = _load_bowl_corpus()
    if not items:
        return []

    c = (cuisine or "").strip().lower()
    if c:
        # Broad matching: keep Indian variants even if user says Tamil/South Indian/etc.
        if "ind" in c or "tamil" in c or "south" in c or "north" in c:
            items = [it for it in items if (str(it.get("cuisine") or "").lower().find("ind") >= 0)]

    pantry_set = set((p or "").strip().lower() for p in (pantry_names or []) if (p or "").strip())
    req_tokens = _tokenize(request_text or "")

    scored: list[tuple[float, dict[str, Any]]] = []

    use_embeddings = bool(prefer_embeddings and os.getenv("OPENAI_API_KEY"))
    emb_service = None
    query_emb = None

    if use_embeddings:
        try:
            from app.services.embedding_service import EmbeddingService  # lazy import

            emb_service = EmbeddingService()
            query_emb = await emb_service.generate_text_embedding((request_text or "").strip() or "indian pantry bowl")
        except Exception:
            emb_service = None
            query_emb = None

    for it in items:
        ki = it.get("key_ingredients")
        key_ing = set(str(x).strip().lower() for x in ki if x is not None) if isinstance(ki, list) else set()
        overlap = len([x for x in key_ing if x in pantry_set])
        token_overlap = len(_tokenize(_corpus_item_text(it)) & req_tokens)

        base_score = float(overlap) * 1.5 + float(token_overlap) * 0.5

        if emb_service is not None and query_emb is not None:
            try:
                it_id = str(it.get("id") or "").strip() or None
                doc_emb = None
                if it_id and it_id in (_RAG_CACHE.get("embeddings") or {}):
                    doc_emb = (_RAG_CACHE.get("embeddings") or {}).get(it_id)
                if doc_emb is None:
                    doc_emb = await emb_service.generate_text_embedding(_corpus_item_text(it))
                    if it_id:
                        _RAG_CACHE.setdefault("embeddings", {})[it_id] = doc_emb
                sim = emb_service.calculate_similarity(query_emb, doc_emb)
                base_score += float(sim) * 3.0
            except Exception:
                pass

        scored.append((base_score, it))

    scored.sort(key=lambda x: x[0], reverse=True)

    top: list[dict[str, Any]] = []
    seen: set[str] = set()
    for score, it in scored:
        if len(top) >= int(max(1, limit)):
            break
        it_id = str(it.get("id") or "").strip() or str(it.get("title") or "").strip()
        if not it_id or it_id in seen:
            continue
        seen.add(it_id)
        top.append(
            {
                "id": str(it.get("id") or ""),
                "title": str(it.get("title") or ""),
                "region": str(it.get("region") or ""),
                "tags": list(it.get("tags") or []) if isinstance(it.get("tags"), list) else [],
                "key_ingredients": list(it.get("key_ingredients") or []) if isinstance(it.get("key_ingredients"), list) else [],
                "components": it.get("components") if isinstance(it.get("components"), dict) else {},
                "flavor_logic": str(it.get("flavor_logic") or ""),
                "score": float(score),
            }
        )

    return top
