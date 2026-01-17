"""
YouTube ranking endpoint - POST /youtube/rank
YouTube summary endpoint - POST /youtube/summary
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import re
from typing import Optional, Tuple
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

from app.models.youtube import YouTubeRankRequest, YouTubeRankResponse
from app.core.orchestrator import youtube_rank
from app.core.llm_client import get_reasoning_client

router = APIRouter()


def _fetch_transcript(video_id: str, preferred_lang: str = "en") -> list[dict]:
    """Fetch a YouTube transcript in a version-tolerant way.

    Some environments may have older/newer variants of youtube-transcript-api where
    `YouTubeTranscriptApi.get_transcript` is missing. Fall back to list_transcripts().
    """
    vid = (video_id or "").strip()
    if not vid:
        raise ValueError("video_id is required")

    lang = (preferred_lang or "en").strip().lower()
    lang_candidates = [lang] if lang else []
    for l in ["en", "en-US", "en-GB"]:
        if l not in lang_candidates:
            lang_candidates.append(l)

    # Preferred path
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        try:
            return YouTubeTranscriptApi.get_transcript(vid, languages=lang_candidates)
        except TypeError:
            # Some versions don't support languages=...
            return YouTubeTranscriptApi.get_transcript(vid)

    # Fallback path
    if hasattr(YouTubeTranscriptApi, "list_transcripts"):
        transcript_list = YouTubeTranscriptApi.list_transcripts(vid)
        try:
            transcript = transcript_list.find_transcript(lang_candidates)
        except Exception:
            transcript = transcript_list.find_generated_transcript(lang_candidates)
        return transcript.fetch()

    raise RuntimeError("youtube-transcript-api missing transcript methods")


def _fetch_transcript_any_language(video_id: str, preferred_lang: str = "en") -> Tuple[list[dict], str]:
    """Fetch transcript; if preferred language isn't available, fall back to any available transcript.

    Returns (transcript_entries, transcript_language_code).
    """
    vid = (video_id or "").strip()
    if not vid:
        raise ValueError("video_id is required")

    preferred = (preferred_lang or "en").strip().lower()

    # First try: preferred (plus common English variants; plus Tamil/Indian fallbacks when output is English).
    lang_candidates: list[str] = []
    if preferred:
        lang_candidates.append(preferred)
    for l in ["en", "en-US", "en-GB"]:
        if l not in lang_candidates:
            lang_candidates.append(l)
    if preferred in {"en", "en-us", "en-gb"}:
        for l in ["ta", "ta-IN", "hi", "hi-IN"]:
            if l not in lang_candidates:
                lang_candidates.append(l)

    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        try:
            entries = YouTubeTranscriptApi.get_transcript(vid, languages=lang_candidates)
            return entries, preferred or "unknown"
        except Exception:
            # We'll fall back to list_transcripts below.
            pass

    if hasattr(YouTubeTranscriptApi, "list_transcripts"):
        tl = YouTubeTranscriptApi.list_transcripts(vid)

        picked = None
        # Try preferred candidates first
        try:
            picked = tl.find_transcript(lang_candidates)
        except Exception:
            try:
                picked = tl.find_generated_transcript(lang_candidates)
            except Exception:
                picked = None

        # If still none, pick any available transcript (prefer manually created)
        if picked is None:
            try:
                all_tx = [t for t in tl]
            except Exception:
                all_tx = []
            if all_tx:
                manual = [t for t in all_tx if getattr(t, "is_generated", False) is False]
                picked = (manual[0] if manual else all_tx[0])

        if picked is None:
            raise NoTranscriptFound(vid)

        lang_code = str(getattr(picked, "language_code", "") or "unknown")
        return picked.fetch(), lang_code

    raise RuntimeError("youtube-transcript-api missing transcript methods")


class YouTubeSummaryRequest(BaseModel):
    video_id: str
    recipe_name: str
    output_language: str = "en"
    transcript_language: Optional[str] = None


class YouTubeSummaryResponse(BaseModel):
    video_id: str
    summary: str
    condensed_summary: str
    key_techniques: list[str]
    timestamp_highlights: list[dict[str, str]]  # [{"time": "2:30", "description": "..."}]
    watch_time_estimate: str
    recipe_name_en: str = ""
    ingredients: list[str] = []
    steps: list[str] = []
    confidence: str = "low"
    source_language: str = "unknown"


@router.post("/rank", response_model=YouTubeRankResponse)
async def post_rank(req: YouTubeRankRequest):
    """Rank YouTube videos for a recipe"""
    context = {
        "recipe_name": req.recipe_name,
        "recipe_cuisine": req.recipe_cuisine,
        "recipe_techniques": req.recipe_techniques,
        "candidates": [c.model_dump() for c in req.candidates],
        "output_language": req.output_language,
    }

    def _tokenize(value: str) -> set[str]:
        value = (value or "").lower()
        value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
        value = value.replace("_", " ")
        tokens = {t for t in value.split() if t and len(t) > 1}
        return tokens

    def _match_score(recipe_name: str, title: str) -> float:
        q = _tokenize(recipe_name)
        t = _tokenize(title)
        if not q or not t:
            return 0.0
        return len(q & t) / max(1, len(q))

    def _trust_score(channel: str, title: str) -> float:
        text = f"{channel} {title}".lower()
        score = 0.5
        if any(k in text for k in ["official", "kitchen", "chef", "cooking", "recipes"]):
            score += 0.15
        if any(k in text for k in ["shorts", "mukbang", "asmr"]):
            score -= 0.15
        return max(0.0, min(1.0, score))

    async def _fallback() -> YouTubeRankResponse:
        ranked = []
        for c in req.candidates:
            ms = _match_score(req.recipe_name, c.title)
            ts = _trust_score(c.channel, c.title)
            ranked.append(
                {
                    "video_id": c.video_id,
                    "title": c.title,
                    "channel": c.channel,
                    "trust_score": ts,
                    "match_score": ms,
                    "reasons": [
                        "Fallback ranking (keyword match)",
                        f"Match score: {ms:.2f}",
                    ],
                }
            )
        ranked.sort(key=lambda v: (v["match_score"], v["trust_score"]), reverse=True)
        return YouTubeRankResponse(ranked_videos=ranked[: min(5, len(ranked))])

    try:
        result = await youtube_rank(context)
        # If the LLM returns an empty list, fall back to deterministic ranking.
        if not isinstance(result, dict) or not result.get("ranked_videos"):
            return await _fallback()
        return YouTubeRankResponse(**result)
    except Exception:
        return await _fallback()


@router.post("/summary", response_model=YouTubeSummaryResponse)
async def post_summary(req: YouTubeSummaryRequest):
    """Generate AI summary of YouTube video for cooking"""
    try:
        # Fetch transcript (fall back to any available language; Tamil is common)
        preferred_tx_lang = (req.transcript_language or "").strip() or (req.output_language or "en")
        transcript_list, source_language = _fetch_transcript_any_language(req.video_id, preferred_lang=preferred_tx_lang)
        
        # Combine transcript into full text
        full_transcript = " ".join([entry['text'] for entry in transcript_list])
        
        # Use LLM to generate summary + ingredients + steps (schema-enforced)
        llm_client = get_reasoning_client()

        schema = {
            "type": "object",
            "required": [
                "summary",
                "condensed_summary",
                "key_techniques",
                "timestamp_highlights",
                "watch_time_estimate",
                "recipe_name_en",
                "ingredients",
                "steps",
                "confidence",
                "source_language",
            ],
            "properties": {
                "summary": {"type": "string"},
                "condensed_summary": {"type": "string"},
                "key_techniques": {"type": "array", "items": {"type": "string"}},
                "timestamp_highlights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["time", "description"],
                        "properties": {
                            "time": {"type": "string"},
                            "description": {"type": "string"},
                        },
                        "additionalProperties": False,
                    },
                },
                "watch_time_estimate": {"type": "string"},
                "recipe_name_en": {"type": "string"},
                "ingredients": {"type": "array", "items": {"type": "string"}},
                "steps": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                "source_language": {"type": "string"},
            },
            "additionalProperties": False,
        }

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a cooking video analyst. Return JSON only. "
                    "Write all output text in the requested output_language. "
                    "Do NOT guess ingredients or steps. If the transcript does not clearly state them, return empty arrays and confidence='low'."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Recipe: {req.recipe_name}\n"
                    f"output_language: {req.output_language}\n\n"
                    f"transcript_source_language: {source_language}\n\n"
                    "Transcript (may be truncated):\n"
                    f"{full_transcript[:8000]}\n\n"
                    "Instructions:\n"
                    "- summary: 2-3 sentences, practical and specific.\n"
                    "- condensed_summary: EXACTLY 3-4 lines separated by '\\n'. Each line should be a short actionable takeaway.\n"
                    "- key_techniques: 3-5 items.\n"
                    "- timestamp_highlights: 2-4 items, approximate times like '2:30'.\n"
                    "- watch_time_estimate: e.g. 'Full video (12 min)' or 'Skip to 3:20'.\n"
                    "- recipe_name_en: English recipe name (translate if needed).\n"
                    "- ingredients: list only ingredients explicitly mentioned (English if output_language is en).\n"
                    "- steps: concise step-by-step method (only if explicitly stated).\n"
                    "- confidence: high if ingredients+steps are complete, medium if partial, low if missing.\n"
                    "- source_language: echo transcript_source_language."
                ),
            },
        ]

        summary_json = await llm_client.generate_json(messages=messages, schema=schema)
        
        return YouTubeSummaryResponse(
            video_id=req.video_id,
            summary=summary_json.get("summary", "Summary not available"),
            condensed_summary=summary_json.get("condensed_summary", ""),
            key_techniques=summary_json.get("key_techniques", []),
            timestamp_highlights=summary_json.get("timestamp_highlights", []),
            watch_time_estimate=summary_json.get("watch_time_estimate", "Full video"),
            recipe_name_en=summary_json.get("recipe_name_en", ""),
            ingredients=summary_json.get("ingredients", []),
            steps=summary_json.get("steps", []),
            confidence=summary_json.get("confidence", "low"),
            source_language=summary_json.get("source_language", source_language),
        )
        
    except (TranscriptsDisabled, NoTranscriptFound) as e:
        raise HTTPException(
            status_code=404,
            detail=f"No transcript available for video {req.video_id}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate summary: {str(e)}"
        )
