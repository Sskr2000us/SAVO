from __future__ import annotations

from typing import Any, Optional, Tuple

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound


def fetch_transcript_any_language(video_id: str, preferred_lang: str = "en") -> Tuple[list[dict], str]:
    """Fetch transcript; fall back to any available language.

    Returns (transcript_entries, transcript_language_code).
    """
    vid = (video_id or "").strip()
    if not vid:
        raise ValueError("video_id is required")

    preferred = (preferred_lang or "en").strip().lower()

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

    # Note: some youtube-transcript-api versions support get_transcript(languages=...)
    if hasattr(YouTubeTranscriptApi, "get_transcript"):
        try:
            entries = YouTubeTranscriptApi.get_transcript(vid, languages=lang_candidates)
            return entries, preferred or "unknown"
        except Exception:
            pass

    if hasattr(YouTubeTranscriptApi, "list_transcripts"):
        tl = YouTubeTranscriptApi.list_transcripts(vid)

        picked = None
        try:
            picked = tl.find_transcript(lang_candidates)
        except Exception:
            try:
                picked = tl.find_generated_transcript(lang_candidates)
            except Exception:
                picked = None

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


async def summarize_youtube_recipe(
    *,
    video_id: str,
    recipe_name: str,
    output_language: str = "en",
    transcript_language: Optional[str] = None,
    llm_client: Any,
) -> dict:
    """Extract a structured cooking summary + ingredients/steps from a YouTube transcript."""

    preferred_tx_lang = (transcript_language or "").strip() or (output_language or "en")
    transcript_list, source_language = fetch_transcript_any_language(video_id, preferred_lang=preferred_tx_lang)

    full_transcript = " ".join([str(entry.get("text") or "") for entry in (transcript_list or [])])

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
                "Do NOT guess ingredients or steps. If the transcript does not clearly state them, "
                "return empty arrays and confidence='low'."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Recipe: {recipe_name}\n"
                f"output_language: {output_language}\n\n"
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
    out = dict(summary_json or {})
    out.setdefault("source_language", source_language)
    return out
