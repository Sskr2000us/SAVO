"""
YouTube ranking endpoint - POST /youtube/rank
YouTube summary endpoint - POST /youtube/summary
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
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
    result = await youtube_rank(context)
    return YouTubeRankResponse(**result)


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
