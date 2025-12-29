"""
YouTube ranking models (E7)
"""
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional


class YouTubeVideoCandidate(BaseModel):
    """Input candidate video for ranking"""
    video_id: str
    title: str
    channel: str
    language: str
    transcript: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class YouTubeRankRequest(BaseModel):
    """Request to rank YouTube videos for a recipe"""
    recipe_name: str = Field(..., description="Recipe name to find videos for")
    recipe_cuisine: Optional[str] = None
    recipe_techniques: List[str] = Field(default_factory=list, description="Key techniques in the recipe")
    candidates: List[YouTubeVideoCandidate] = Field(..., min_length=1, description="Candidate videos to rank")
    output_language: str = Field(default="en", pattern="^[a-z]{2}(-[A-Z]{2})?$")


class RankedVideo(BaseModel):
    """Single ranked video result (YOUTUBE_RANK_SCHEMA item)"""
    video_id: str
    title: str
    channel: str
    trust_score: float = Field(ge=0.0, le=1.0, description="Trust/quality score")
    match_score: float = Field(ge=0.0, le=1.0, description="Match with recipe")
    reasons: List[str] = Field(default_factory=list, description="Ranking reasons")


class YouTubeRankResponse(BaseModel):
    """Response from YouTube ranking (YOUTUBE_RANK_SCHEMA)"""
    ranked_videos: List[RankedVideo] = Field(..., description="Videos ranked by trust and match scores")
