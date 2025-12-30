"""
Training data collection models and schemas
Phase 2: Building custom vision model
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class BoundingBox(BaseModel):
    """Bounding box coordinates for detected ingredient"""
    x: float = Field(..., description="X coordinate (top-left)")
    y: float = Field(..., description="Y coordinate (top-left)")
    width: float = Field(..., description="Width of bounding box")
    height: float = Field(..., description="Height of bounding box")


class DetectedIngredient(BaseModel):
    """Single ingredient detection with metadata"""
    ingredient: str = Field(..., description="Canonical ingredient name")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    bbox: Optional[BoundingBox] = Field(None, description="Bounding box if available")
    quantity_estimate: Optional[str] = Field(None, description="Estimated quantity")
    storage_hint: Optional[str] = Field(None, description="Storage location hint")
    source: str = Field(..., description="Detection source: google_vision, custom_model, user_confirmed")


class TrainingDataSubmission(BaseModel):
    """Training data submission from user corrections"""
    scan_id: str = Field(..., description="Unique scan ID")
    image_hash: str = Field(..., description="SHA-256 hash of image")
    image_width: int = Field(..., description="Original image width")
    image_height: int = Field(..., description="Original image height")
    
    # Original detections from vision API
    original_detections: List[DetectedIngredient] = Field(
        default_factory=list,
        description="Detections from Google Vision or custom model"
    )
    
    # User-confirmed ingredients (ground truth)
    user_corrections: List[DetectedIngredient] = Field(
        default_factory=list,
        description="User-confirmed ingredients (training labels)"
    )
    
    # Metadata
    storage_location: Optional[str] = Field(None, description="pantry, fridge, or freezer")
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    user_id: Optional[str] = Field(None, description="User ID if available")
    device_info: Optional[str] = Field(None, description="Device/camera info")


class TrainingDataResponse(BaseModel):
    """Response from training data submission"""
    status: str = Field(..., description="ok or error")
    scan_id: str = Field(..., description="Scan ID for reference")
    stored: bool = Field(..., description="Whether data was successfully stored")
    message: Optional[str] = Field(None, description="Success or error message")


class TrainingStats(BaseModel):
    """Statistics about collected training data"""
    total_images: int = Field(..., description="Total images collected")
    total_labels: int = Field(..., description="Total ingredient labels")
    unique_ingredients: int = Field(..., description="Number of unique ingredient classes")
    storage_locations: dict = Field(..., description="Breakdown by storage location")
    collection_rate: str = Field(..., description="Images per day")
    last_updated: str = Field(..., description="Last update timestamp")
