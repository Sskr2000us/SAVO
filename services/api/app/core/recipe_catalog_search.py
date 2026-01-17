from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple


_RE_NON_ALNUM = re.compile(r"[^a-z0-9_\s-]+")


_STOPWORDS = {
    "and",
    "or",
    "the",
    "a",
    "an",
    "with",
    "for",
    "to",
    "of",
    "in",
    "on",
    "style",
    "recipe",
    "dish",
}


def _normalize_space(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip())


def _tokenize(text: str) -> List[str]:
    s = (text or "").lower()
    s = s.replace("/", " ")
    s = _RE_NON_ALNUM.sub(" ", s)
    s = re.sub(r"\s+", " ", s).strip()
    if not s:
        return []
    toks = [t for t in s.split(" ") if t and t not in _STOPWORDS and len(t) >= 2]
    return toks


def _safe_title(entry: dict[str, Any]) -> str:
    rn = entry.get("recipe_name")
    if isinstance(rn, dict):
        v = rn.get("en")
        if isinstance(v, str) and v.strip():
            return _normalize_space(v)
        for vv in rn.values():
            if isinstance(vv, str) and vv.strip():
                return _normalize_space(vv)
        return ""
    if isinstance(rn, str):
        return _normalize_space(rn)
    return ""


def _iter_ingredient_items(entry: dict[str, Any]) -> Iterable[str]:
    # Catalog convention: ingredients is a list of {"item": "...", "amount": ..., "unit": ...}
    ing = entry.get("ingredients")
    if isinstance(ing, list):
        for it in ing:
            if isinstance(it, dict):
                item = it.get("item")
                if isinstance(item, str) and item.strip():
                    yield item
            elif isinstance(it, str) and it.strip():
                # tolerate string lists
                yield it


def _course_matches(*, title_key: str, course_hint: str) -> bool:
    h = (course_hint or "").strip().lower()
    if not h:
        return True

    dessert_kw = {
        "dessert",
        "kheer",
        "payasam",
        "halwa",
        "pudding",
        "gulab",
        "jamun",
        "laddu",
        "ladoo",
        "barfi",
        "burfi",
        "rasgulla",
        "kulfi",
        "sweet",
        "cake",
        "cookie",
    }
    side_kw = {
        "raita",
        "salad",
        "chutney",
        "pickle",
        "papad",
        "papadam",
        "naan",
        "roti",
        "paratha",
        "bread",
        "rice",
        "pulao",
        "jeera",
        "dal",
        "dahi",
        "yogurt",
        "soup",
    }

    has_dessert = any(k in title_key for k in dessert_kw)
    has_side = any(k in title_key for k in side_kw)

    if h == "dessert":
        return has_dessert
    if h == "side":
        return has_side and not has_dessert
    if h == "main":
        return (not has_dessert) and (not has_side)
    return True


def _title_requires_core_pantry(*, title_key: str, pantry_join: str) -> bool:
    if not title_key:
        return True
    if not pantry_join:
        return True

    core = {
        "paneer": ["paneer"],
        "chicken": ["chicken"],
        "mutton": ["mutton", "lamb"],
        "lamb": ["lamb", "mutton"],
        "beef": ["beef"],
        "pork": ["pork"],
        "fish": ["fish", "salmon", "tuna", "cod"],
        "shrimp": ["shrimp", "prawn"],
        "prawn": ["shrimp", "prawn"],
        "egg": ["egg"],
        "tofu": ["tofu"],
    }

    required: list[str] = []
    for k, subs in core.items():
        if k in title_key:
            required.extend(subs)

    if not required:
        return True

    for needle in required:
        if needle and needle in pantry_join:
            return True
    return False


def _is_assumed_staple(nm: str) -> bool:
    s = (nm or "").strip().lower()
    if not s:
        return False
    if s in {"salt", "pepper", "black_pepper", "oil", "olive_oil", "vegetable_oil", "butter", "ghee", "sugar", "water"}:
        return True
    if s.endswith("_powder") or s.endswith("_masala"):
        return True
    if any(k in s for k in ["cumin", "coriander", "turmeric", "paprika", "chili", "cinnamon", "cardamom", "clove", "ginger", "garlic"]):
        return True
    return False


def _major_group(nm: str) -> str:
    s = (nm or "").strip().lower()
    if not s:
        return ""
    if any(k in s for k in ["pasta", "rotini", "penne", "spaghetti", "noodle", "macaroni", "rigatoni", "fusilli", "farfalle", "orzo"]):
        return "pasta"
    if "rice" in s:
        return "rice"
    return s


@dataclass(frozen=True)
class _Bm25Index:
    # doc_id -> (length, term_freq)
    docs: Dict[str, Tuple[int, Dict[str, int]]]
    df: Dict[str, int]
    avgdl: float


_INDEX_CACHE: dict[Tuple[int, int], _Bm25Index] = {}
_EMB_CACHE: dict[str, List[float]] = {}


def _build_bm25_index(*, entries: Sequence[dict[str, Any]], doc_ids: Sequence[str], doc_texts: Sequence[str]) -> _Bm25Index:
    docs: Dict[str, Tuple[int, Dict[str, int]]] = {}
    df: Dict[str, int] = {}

    for rid, text in zip(doc_ids, doc_texts):
        toks = _tokenize(text)
        tf: Dict[str, int] = {}
        for t in toks:
            tf[t] = tf.get(t, 0) + 1
        dl = len(toks)
        docs[rid] = (dl, tf)
        for t in set(toks):
            df[t] = df.get(t, 0) + 1

    avgdl = float(sum(dl for dl, _tf in docs.values()) / max(1, len(docs)))
    return _Bm25Index(docs=docs, df=df, avgdl=avgdl)


def _bm25_score(index: _Bm25Index, *, query_tokens: Sequence[str], doc_id: str, k1: float = 1.4, b: float = 0.75) -> float:
    doc = index.docs.get(doc_id)
    if not doc:
        return 0.0
    dl, tf = doc
    N = max(1, len(index.docs))

    score = 0.0
    for t in query_tokens:
        f = tf.get(t)
        if not f:
            continue
        n_q = index.df.get(t, 0)
        # IDF (Okapi BM25)
        idf = math.log(1.0 + (N - n_q + 0.5) / (n_q + 0.5))
        denom = f + k1 * (1.0 - b + b * (float(dl) / max(1.0, index.avgdl)))
        score += idf * (f * (k1 + 1.0) / max(1e-9, denom))
    return float(score)


def rank_catalog_entries(
    entries: Sequence[dict[str, Any]],
    *,
    query_text: str,
    pantry_set: set[str],
    like_tokens: Optional[set[str]] = None,
    dislike_tokens: Optional[set[str]] = None,
    course_hint: str = "",
    exclude_title_keys: Optional[set[str]] = None,
    limit: int = 5,
    normalize_title_key: Callable[[str], str],
    canonicalize_ingredient: Callable[[str], str],
    prefer_embeddings: bool = True,
) -> List[dict[str, Any]]:
    if limit <= 0:
        return []

    like_tokens = like_tokens or set()
    dislike_tokens = dislike_tokens or set()

    pantry_join = " | ".join(sorted(pantry_set or set()))
    pantry_groups = {g for g in [_major_group(x) for x in (pantry_set or set())] if g}

    # Build doc ids/texts
    doc_ids: List[str] = []
    doc_texts: List[str] = []
    filtered_entries: List[dict[str, Any]] = []

    for e in entries:
        if not isinstance(e, dict):
            continue
        title = _safe_title(e)
        title_k = normalize_title_key(title)
        if exclude_title_keys and title_k and title_k in exclude_title_keys:
            continue
        if title_k and not _course_matches(title_key=title_k, course_hint=course_hint):
            continue
        if title_k and not _title_requires_core_pantry(title_key=title_k, pantry_join=pantry_join):
            continue

        rid = str(e.get("id") or "").strip()
        if not rid:
            # stable-enough fallback
            rid = f"{normalize_title_key(title)}::{str(e.get('cuisine') or '').strip().lower()}"[:160]

        parts: List[str] = []
        if title:
            parts.append(title)
        c = e.get("cuisine") or e.get("cuisine_code") or ""
        if c:
            parts.append(str(c))
        tags = e.get("tags")
        if isinstance(tags, list):
            parts.extend([str(x) for x in tags if isinstance(x, str) and x.strip()])

        # Ingredients
        for raw_item in _iter_ingredient_items(e):
            nm = canonicalize_ingredient(raw_item)
            if nm:
                parts.append(nm)

        filtered_entries.append(e)
        doc_ids.append(rid)
        doc_texts.append(" ".join(parts))

    if not filtered_entries:
        return []

    # BM25 index cache by (entries_id, doc_count)
    cache_key = (id(entries), len(filtered_entries))
    index = _INDEX_CACHE.get(cache_key)
    if index is None:
        index = _build_bm25_index(entries=filtered_entries, doc_ids=doc_ids, doc_texts=doc_texts)
        _INDEX_CACHE[cache_key] = index

    q_tokens = _tokenize(query_text)
    # Add likes as extra query intent
    for t in like_tokens:
        if isinstance(t, str):
            q_tokens.extend(_tokenize(t))

    scored: List[Tuple[float, str, dict[str, Any]]] = []

    for e, rid, text in zip(filtered_entries, doc_ids, doc_texts):
        title_k = normalize_title_key(_safe_title(e))

        bm25 = _bm25_score(index, query_tokens=q_tokens, doc_id=rid)

        # Pantry coverage/overlap
        total_ing = 0
        matched = 0
        soft = 0
        for raw_item in _iter_ingredient_items(e):
            nm = canonicalize_ingredient(raw_item)
            if not nm:
                continue
            total_ing += 1
            if nm in pantry_set or _is_assumed_staple(nm):
                matched += 1
                continue
            g = _major_group(nm)
            if g and g in pantry_groups:
                soft += 1

        coverage = (float(matched) / float(max(1, total_ing))) if total_ing else 0.0
        overlap = float(matched) + 0.25 * float(soft)

        # Preference boost/penalty
        pref = 0.0
        if title_k:
            if like_tokens and any(t in title_k for t in like_tokens):
                pref += 1.0
            if dislike_tokens and any(t in title_k for t in dislike_tokens):
                pref -= 2.0

        # Ingredient-level preference
        if like_tokens or dislike_tokens:
            for raw_item in _iter_ingredient_items(e):
                nm = canonicalize_ingredient(raw_item)
                if not nm:
                    continue
                if like_tokens and any(t in nm for t in like_tokens):
                    pref += 0.15
                if dislike_tokens and any(t in nm for t in dislike_tokens):
                    pref -= 0.35

        # Combined score
        score = 1.0 * bm25 + 3.0 * coverage + 0.12 * overlap + 1.2 * pref

        # Tiebreakers: stable order by title
        scored.append((score, title_k or rid, e))

    scored.sort(key=lambda x: (x[0], x[1]), reverse=True)

    picked: List[dict[str, Any]] = []
    seen_titles: set[str] = set()
    for score, tkey, e in scored:
        if len(picked) >= limit:
            break
        if tkey and tkey in seen_titles:
            continue
        if tkey:
            seen_titles.add(tkey)
        picked.append(e)

    return picked


async def async_rank_catalog_entries(
    entries: Sequence[dict[str, Any]],
    *,
    query_text: str,
    pantry_set: set[str],
    like_tokens: Optional[set[str]] = None,
    dislike_tokens: Optional[set[str]] = None,
    course_hint: str = "",
    exclude_title_keys: Optional[set[str]] = None,
    limit: int = 5,
    normalize_title_key: Callable[[str], str],
    canonicalize_ingredient: Callable[[str], str],
    prefer_embeddings: bool = True,
) -> List[dict[str, Any]]:
    """Async variant that can optionally add embedding similarity.

    Planning/catalog-fill uses the sync ranker for determinism and to avoid
    async refactors; other flows may use this to add a small semantic boost.
    """

    base_ranked = rank_catalog_entries(
        entries,
        query_text=query_text,
        pantry_set=pantry_set,
        like_tokens=like_tokens,
        dislike_tokens=dislike_tokens,
        course_hint=course_hint,
        exclude_title_keys=exclude_title_keys,
        limit=max(limit * 5, limit),
        normalize_title_key=normalize_title_key,
        canonicalize_ingredient=canonicalize_ingredient,
        prefer_embeddings=False,
    )
    if not base_ranked:
        return []

    if not (prefer_embeddings and os.getenv("OPENAI_API_KEY")):
        return base_ranked[:limit]

    try:
        from app.services.embedding_service import EmbeddingService  # lazy import

        emb_service = EmbeddingService()
        query_emb = await emb_service.generate_text_embedding((_normalize_space(query_text) or "recipe").strip())
    except Exception:
        return base_ranked[:limit]

    rescored: List[Tuple[float, str, dict[str, Any]]] = []
    for e in base_ranked[: max(30, limit * 5)]:
        title = _safe_title(e)
        rid = str(e.get("id") or "").strip() or f"{normalize_title_key(title)}::{str(e.get('cuisine') or '').strip().lower()}"[:160]
        text = " ".join([title, str(e.get("cuisine") or e.get("cuisine_code") or "")]).strip()
        try:
            doc_emb = _EMB_CACHE.get(rid)
            if doc_emb is None:
                doc_emb = await emb_service.generate_text_embedding(text)
                _EMB_CACHE[rid] = doc_emb
            sim = float(emb_service.calculate_similarity(query_emb, doc_emb))
        except Exception:
            sim = 0.0
        rescored.append((sim, normalize_title_key(title) or rid, e))

    rescored.sort(key=lambda x: (x[0], x[1]), reverse=True)
    out: List[dict[str, Any]] = []
    seen: set[str] = set()
    for sim, tkey, e in rescored:
        if len(out) >= limit:
            break
        if tkey and tkey in seen:
            continue
        if tkey:
            seen.add(tkey)
        out.append(e)
    return out
