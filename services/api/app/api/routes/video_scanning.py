"""
Video scanning support for batch ingredient detection
Processes video files frame-by-frame for comprehensive pantry scanning
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import List, Dict, Optional
from uuid import uuid4
from datetime import datetime
import logging
import base64
import asyncio
from io import BytesIO

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scanning/video", tags=["video-scanning"])


# ============================================================================
# Video Processing Helpers
# ============================================================================

async def extract_frames_from_video(
    video_data: bytes,
    max_frames: int = 10,
    fps: float = 1.0
) -> List[bytes]:
    """
    Extract key frames from video for analysis
    
    Args:
        video_data: Raw video bytes
        max_frames: Maximum frames to extract
        fps: Frames per second to extract
        
    Returns:
        List of frame images as bytes
    """
    try:
        from PIL import Image
        import subprocess
        import tempfile
        import os
        
        frames = []
        
        # Save video to temp file
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as temp_video:
            temp_video.write(video_data)
            video_path = temp_video.name
        
        try:
            # Create temp directory for frames
            with tempfile.TemporaryDirectory() as temp_dir:
                # Use ffmpeg to extract frames
                # Note: This requires ffmpeg to be installed
                # For production, consider using python-opencv or moviepy
                output_pattern = os.path.join(temp_dir, 'frame_%04d.jpg')
                
                cmd = [
                    'ffmpeg',
                    '-i', video_path,
                    '-vf', f'fps={fps}',
                    '-frames:v', str(max_frames),
                    '-q:v', '2',  # High quality
                    output_pattern
                ]
                
                # Run ffmpeg (suppress output)
                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=30
                )
                
                if result.returncode != 0:
                    logger.error(f"ffmpeg failed: {result.stderr}")
                    raise ValueError("Video frame extraction failed")
                
                # Read extracted frames
                frame_files = sorted([
                    f for f in os.listdir(temp_dir) 
                    if f.startswith('frame_') and f.endswith('.jpg')
                ])
                
                for frame_file in frame_files[:max_frames]:
                    frame_path = os.path.join(temp_dir, frame_file)
                    with open(frame_path, 'rb') as f:
                        frame_data = f.read()
                        frames.append(frame_data)
                
                logger.info(f"Extracted {len(frames)} frames from video")
                
        finally:
            # Cleanup temp video file
            if os.path.exists(video_path):
                os.remove(video_path)
        
        return frames
        
    except ImportError as e:
        logger.error(f"Missing dependencies for video processing: {e}")
        raise HTTPException(
            status_code=501,
            detail="Video processing not available. Install ffmpeg or use image scanning."
        )
    except Exception as e:
        logger.error(f"Frame extraction failed: {e}", exc_info=True)
        raise ValueError(f"Failed to extract frames: {str(e)}")


async def deduplicate_detections(
    all_detections: List[Dict],
    similarity_threshold: float = 0.85
) -> List[Dict]:
    """
    Deduplicate ingredients detected across multiple frames
    
    Strategy:
    1. Group by canonical_name
    2. Take highest confidence detection
    3. Merge close_alternatives
    4. Average quantity if detected multiple times
    
    Args:
        all_detections: All detections from all frames
        similarity_threshold: Confidence threshold for grouping
        
    Returns:
        Deduplicated list of detections
    """
    from collections import defaultdict
    
    # Group by canonical name
    grouped = defaultdict(list)
    for detection in all_detections:
        canonical_name = detection.get("canonical_name") or detection.get("detected_name")
        grouped[canonical_name].append(detection)
    
    # Deduplicate each group
    deduplicated = []
    for canonical_name, detections in grouped.items():
        # Take highest confidence detection as base
        best = max(detections, key=lambda d: d.get("confidence", 0))
        
        # Average quantities if detected multiple times
        quantities = [d.get("quantity") for d in detections if d.get("quantity")]
        avg_quantity = sum(quantities) / len(quantities) if quantities else None
        
        # Merge close alternatives (unique)
        all_alternatives = []
        seen_names = set()
        for d in detections:
            for alt in d.get("close_alternatives", []):
                alt_name = alt.get("name")
                if alt_name and alt_name not in seen_names:
                    all_alternatives.append(alt)
                    seen_names.add(alt_name)
        
        # Build deduplicated detection
        deduplicated_detection = {
            **best,
            "quantity": avg_quantity,
            "detection_count": len(detections),
            "close_alternatives": all_alternatives[:5],  # Top 5 alternatives
            "deduplication_note": f"Detected in {len(detections)} frames"
        }
        
        deduplicated.append(deduplicated_detection)
    
    logger.info(f"Deduplicated {len(all_detections)} detections to {len(deduplicated)}")
    
    return deduplicated


# ============================================================================
# Video Upload Endpoint
# ============================================================================

@router.post("/analyze")
async def analyze_video(
    video: UploadFile = File(...),
    scan_type: str = Form("pantry"),
    location_hint: Optional[str] = Form(None),
    max_frames: int = Form(10),
    user_id: str = Depends(lambda: "test-user")  # Replace with actual auth
):
    """
    Analyze video for ingredient detection
    
    Process:
    1. Extract key frames from video (1 fps, max 10 frames)
    2. Analyze each frame with Vision API
    3. Deduplicate detections across frames
    4. Return consolidated ingredient list
    
    Args:
        video: Video file (mp4, mov, avi)
        scan_type: Type of scan (pantry/fridge/shopping)
        location_hint: Optional location hint
        max_frames: Maximum frames to process (1-20)
        
    Returns:
        Consolidated detection results
    
    Note: Video processing is slower than image scanning (30-60 seconds)
    Consider using multiple images instead for faster results.
    """
    try:
        from app.core.database import get_db_client
        from app.core.vision_api import get_vision_client
        
        # Validate video file
        if not video.content_type.startswith('video/'):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {video.content_type}. Must be a video file."
            )
        
        # Limit max frames
        max_frames = min(max(1, max_frames), 20)
        
        # Read video data
        video_data = await video.read()
        video_size_mb = len(video_data) / (1024 * 1024)
        
        if video_size_mb > 100:  # 100MB limit
            raise HTTPException(
                status_code=413,
                detail=f"Video too large: {video_size_mb:.1f}MB. Maximum is 100MB."
            )
        
        logger.info(f"Processing video: {video.filename}, size: {video_size_mb:.1f}MB")
        
        # Extract frames
        frames = await extract_frames_from_video(video_data, max_frames=max_frames)
        
        if not frames:
            raise HTTPException(
                status_code=400,
                detail="No frames could be extracted from video"
            )
        
        # Create database entry for video scan
        db = get_db_client()
        scan_id = str(uuid4())
        
        db.table("ingredient_scans").insert({
            "id": scan_id,
            "user_id": user_id,
            "scan_type": "video_" + scan_type,
            "location_hint": location_hint,
            "status": "processing",
            "created_at": datetime.utcnow().isoformat(),
            "metadata": {
                "video_filename": video.filename,
                "video_size_mb": video_size_mb,
                "frames_extracted": len(frames)
            }
        }).execute()
        
        # Analyze each frame
        vision_client = get_vision_client()
        all_detections = []
        
        for idx, frame_data in enumerate(frames):
            logger.info(f"Analyzing frame {idx + 1}/{len(frames)}")
            
            try:
                # Analyze frame
                result = await vision_client.analyze_image(
                    image_data=frame_data,
                    scan_type=scan_type,
                    location_hint=location_hint
                )
                
                if result.get("success") and result.get("ingredients"):
                    all_detections.extend(result["ingredients"])
                
            except Exception as e:
                logger.error(f"Frame {idx + 1} analysis failed: {e}")
                continue  # Skip failed frames
        
        if not all_detections:
            raise HTTPException(
                status_code=400,
                detail="No ingredients detected in video. Try taking clearer photos instead."
            )
        
        # Deduplicate detections
        unique_detections = await deduplicate_detections(all_detections)
        
        # Store detections in database
        for detection in unique_detections:
            detected_id = str(uuid4())
            
            db.table("detected_ingredients").insert({
                "id": detected_id,
                "scan_id": scan_id,
                "user_id": user_id,
                "detected_name": detection["detected_name"],
                "canonical_name": detection.get("canonical_name"),
                "confidence": float(detection.get("confidence", 0)),
                "detected_quantity": detection.get("quantity"),
                "detected_unit": detection.get("unit"),
                "quantity_confidence": detection.get("quantity_confidence"),
                "close_alternatives": detection.get("close_alternatives", []),
                "visual_similarity_group": detection.get("visual_similarity_group"),
                "confirmation_status": "pending",
                "metadata": {
                    "detection_count": detection.get("detection_count", 1),
                    "frames_detected_in": detection.get("detection_count", 1)
                }
            }).execute()
        
        # Update scan status
        db.table("ingredient_scans").update({
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "total_detections": len(unique_detections)
        }).eq("id", scan_id).execute()
        
        return {
            "success": True,
            "scan_id": scan_id,
            "scan_type": "video",
            "frames_processed": len(frames),
            "total_raw_detections": len(all_detections),
            "unique_ingredients": len(unique_detections),
            "detections": unique_detections,
            "message": f"Processed {len(frames)} frames, found {len(unique_detections)} unique ingredients",
            "next_step": "Review and confirm detections"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Video analysis failed: {str(e)}")


@router.get("/status/{scan_id}")
async def get_video_scan_status(
    scan_id: str,
    user_id: str = Depends(lambda: "test-user")
):
    """
    Get status of video scan (for progress tracking)
    """
    try:
        from app.core.database import get_db_client
        
        db = get_db_client()
        
        scan = db.table("ingredient_scans") \
            .select("*") \
            .eq("id", scan_id) \
            .eq("user_id", user_id) \
            .single() \
            .execute()
        
        if not scan.data:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        return {
            "scan_id": scan_id,
            "status": scan.data["status"],
            "scan_type": scan.data["scan_type"],
            "created_at": scan.data["created_at"],
            "completed_at": scan.data.get("completed_at"),
            "total_detections": scan.data.get("total_detections", 0),
            "metadata": scan.data.get("metadata", {})
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scan status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")
