"""
YouTube ranking endpoint - POST /youtube/rank
YouTube summary endpoint - POST /youtube/summary
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import re
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled, NoTranscriptFound

from app.models.youtube import YouTubeRankRequest, YouTubeRankResponse
from app.core.orchestrator import youtube_rank
from app.core.llm_client import get_llm_client

router = APIRouter()


class YouTubeSummaryRequest(BaseModel):
    video_id: str
    recipe_name: str
    output_language: str = "en"


class YouTubeSummaryResponse(BaseModel):
    video_id: str
    summary: str
    key_techniques: list[str]
    timestamp_highlights: list[dict[str, str]]  # [{"time": "2:30", "description": "..."}]
    watch_time_estimate: str


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
        value = re.sub(r"[^a-z0-9\s]", " ", value)
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
        # Fetch transcript
        transcript_list = YouTubeTranscriptApi.get_transcript(req.video_id)
        
        # Combine transcript into full text
        full_transcript = " ".join([entry['text'] for entry in transcript_list])
        
        # Use LLM to generate summary
        llm_client = get_llm_client()
        
        prompt = f"""You are a cooking video analyst. Summarize this YouTube cooking video transcript in under 1 minute of reading time.

Recipe: {req.recipe_name}

Transcript:
{full_transcript[:8000]}

Provide a JSON response with:
1. "summary": A concise 2-3 sentence summary of what the video teaches
2. "key_techniques": Array of 3-5 key cooking techniques shown
3. "timestamp_highlights": Array of 2-4 important moments with approximate timestamps and descriptions
4. "watch_time_estimate": How long to watch (e.g., "Full video (12 min)", "First 5 minutes", "Skip to 3:20")

Focus on practical cooking tips and techniques relevant to making {req.recipe_name}."""

        summary_json = await llm_client.generate_json(
            prompt=prompt,
            temperature=0.3,
            max_tokens=800
        )
        
        return YouTubeSummaryResponse(
            video_id=req.video_id,
            summary=summary_json.get("summary", "Summary not available"),
            key_techniques=summary_json.get("key_techniques", []),
            timestamp_highlights=summary_json.get("timestamp_highlights", []),
            watch_time_estimate=summary_json.get("watch_time_estimate", "Full video")
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
