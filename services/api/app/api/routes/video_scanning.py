"""Video scanning support for batch ingredient detection.

Note:
- Video scanning can be slow (multiple frames + model calls) and will exceed
    typical mobile/proxy HTTP timeouts.
- This router supports async processing: upload returns quickly with a scan_id,
    then the client polls `/api/scanning/video/status/{scan_id}`.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from typing import Any, List, Dict, Optional, Tuple
from uuid import uuid4
from datetime import datetime, timedelta
import logging
import base64
import asyncio
from io import BytesIO

logger = logging.getLogger(__name__)

from app.middleware.auth import get_current_user
from app.core.media_storage import upload_inventory_image, upload_scan_video
from app.api.routes.profile import get_full_profile


router = APIRouter(prefix="/api/scanning/video", tags=["video-scanning"])


_ALLOWED_SCAN_TYPES = {"pantry", "fridge", "counter", "shopping", "other"}


def _normalize_scan_type(value: Optional[str]) -> str:
    s = (value or "").strip().lower()
    return s if s in _ALLOWED_SCAN_TYPES else "pantry"


async def _try_fetch_barcode_image(user_id: str, barcode: str) -> Tuple[Optional[str], Optional[Dict]]:
    """Best-effort: look up barcode image on OpenFoodFacts, download, store in Supabase Storage.

    Returns (stored_ref, product_metadata)
    """
    code = (barcode or "").strip()
    if not code:
        return None, None

    try:
        from app.integrations.openfoodfacts import get_openfoodfacts_client
        import httpx

        off = get_openfoodfacts_client()
        product = await off.lookup_barcode(code)
        if not product or not product.get("image_url"):
            return None, product

        image_url = str(product.get("image_url") or "").strip()
        if not image_url:
            return None, product

        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
            res = await client.get(image_url)
        if res.status_code != 200:
            return None, product

        content_type = (res.headers.get("content-type") or "").split(";")[0].strip().lower()
        if content_type not in {"image/jpeg", "image/jpg", "image/png", "image/webp"}:
            # Still upload; storage helper will default to .jpg, but mark original ct.
            content_type = content_type or "image/jpeg"

        stored_ref = upload_inventory_image(
            user_id=user_id,
            content=res.content,
            content_type=content_type,
            asset_type="barcode",
            source="openfoodfacts",
            metadata={"barcode": code, "image_url": image_url},
        )
        return stored_ref, product
    except Exception:
        return None, None


def _safe_crop_by_bbox(image_data: bytes, bbox: Optional[Dict]) -> Optional[bytes]:
    """Crop a JPEG bytes image using normalized bbox {x,y,width,height}.

    Returns cropped JPEG bytes, or None if bbox is missing/invalid.
    """
    if not bbox or not isinstance(bbox, dict):
        return None
    if not all(k in bbox for k in ["x", "y", "width", "height"]):
        return None

    try:
        from PIL import Image
        import io

        img = Image.open(io.BytesIO(image_data)).convert("RGB")
        w, h = img.size
        x = max(0.0, min(1.0, float(bbox.get("x"))))
        y = max(0.0, min(1.0, float(bbox.get("y"))))
        bw = max(0.0, min(1.0, float(bbox.get("width"))))
        bh = max(0.0, min(1.0, float(bbox.get("height"))))
        if bw <= 0 or bh <= 0 or w <= 1 or h <= 1:
            return None

        left = int(x * w)
        top = int(y * h)
        right = int((x + bw) * w)
        bottom = int((y + bh) * h)

        pad_x = int(max(2, (right - left) * 0.08))
        pad_y = int(max(2, (bottom - top) * 0.08))
        left = max(0, left - pad_x)
        top = max(0, top - pad_y)
        right = min(w, right + pad_x)
        bottom = min(h, bottom + pad_y)
        if right <= left or bottom <= top:
            return None

        crop = img.crop((left, top, right, bottom))
        out = io.BytesIO()
        crop.save(out, format="JPEG", quality=85, optimize=True)
        return out.getvalue()
    except Exception:
        return None


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


async def _process_video_scan(
    *,
    scan_id: str,
    user_id: str,
    video_data: bytes,
    scan_type: str,
    location_hint: Optional[str],
    max_frames: int,
    duration_seconds: Optional[int],
    video_filename: Optional[str],
    video_size_mb: float,
    barcode: Optional[str],
    barcode_name_hint: Optional[str],
    barcode_quantity_hint: Optional[float],
    barcode_unit_hint: Optional[str],
    barcode_ref: Optional[str],
    barcode_product: Optional[Dict],
) -> None:
    """Long-running analysis task.

    Never raises; writes failure to ingredient_scans.status.
    """
    try:
        from app.core.database import get_db_client
        from app.core.vision_api import get_vision_client

        db = get_db_client()

        fps = 1.0
        try:
            if duration_seconds and duration_seconds > 0:
                fps = max(0.2, min(1.0, float(max_frames) / float(duration_seconds)))
        except Exception:
            fps = 1.0

        frames = await extract_frames_from_video(video_data, max_frames=max_frames, fps=fps)
        if not frames:
            raise ValueError("No frames could be extracted from video")

        representative_frame = frames[0]
        representative_image_ref = None
        try:
            representative_image_ref = upload_inventory_image(
                user_id=user_id,
                content=representative_frame,
                content_type="image/jpeg",
                asset_type="video_frame",
                source="video_scanning",
                expires_at=(datetime.utcnow() + timedelta(days=7)).isoformat(),
                links={"scan_id": scan_id},
                metadata={"kind": "representative_video_frame"},
            )
        except Exception:
            representative_image_ref = None

        # Update scan metadata with frame counts and representative image.
        try:
            db.table("ingredient_scans").update(
                {
                    "image_url": representative_image_ref,
                    "image_metadata": {
                        "source": "video_scan",
                        "duration_seconds": duration_seconds,
                        "video_filename": video_filename,
                        "video_size_mb": video_size_mb,
                        "frames_extracted": len(frames),
                        "frames_total": len(frames),
                        "frames_done": 0,
                        "fps": fps,
                        "representative_frame_image_url": representative_image_ref,
                        "barcode": (barcode or "").strip() or None,
                        "barcode_name_hint": (barcode_name_hint or "").strip() or None,
                        "barcode_quantity_hint": barcode_quantity_hint,
                        "barcode_unit_hint": (barcode_unit_hint or "").strip() or None,
                        "barcode_product": barcode_product,
                        "barcode_image_url": barcode_ref,
                        "started_processing_at": datetime.utcnow().isoformat(),
                    },
                }
            ).eq("id", scan_id).eq("user_id", user_id).execute()
        except Exception:
            pass

        vision_client = get_vision_client()
        all_detections: List[Dict[str, Any]] = []

        profile = None
        try:
            profile = await get_full_profile(user_id)
        except Exception:
            profile = None

        sem = asyncio.Semaphore(3)

        async def _analyze_one(idx: int, frame_data: bytes) -> List[Dict[str, Any]]:
            async with sem:
                try:
                    result = await vision_client.analyze_image(
                        image_data=frame_data,
                        scan_type=scan_type,
                        location_hint=location_hint,
                        user_preferences=profile,
                    )
                    if result.get("success") and result.get("ingredients"):
                        return list(result["ingredients"])
                except Exception as e:
                    logger.error(f"Frame {idx + 1} analysis failed: {e}")
                return []

        tasks = [_analyze_one(i, fr) for i, fr in enumerate(frames)]
        done = 0
        for coro in asyncio.as_completed(tasks):
            res = await coro
            if res:
                all_detections.extend(res)
            done += 1
            try:
                db.table("ingredient_scans").update(
                    {
                        "image_metadata": {
                            "source": "video_scan",
                            "duration_seconds": duration_seconds,
                            "video_filename": video_filename,
                            "video_size_mb": video_size_mb,
                            "frames_extracted": len(frames),
                            "frames_total": len(frames),
                            "frames_done": done,
                            "fps": fps,
                            "representative_frame_image_url": representative_image_ref,
                            "barcode": (barcode or "").strip() or None,
                            "barcode_name_hint": (barcode_name_hint or "").strip() or None,
                            "barcode_quantity_hint": barcode_quantity_hint,
                            "barcode_unit_hint": (barcode_unit_hint or "").strip() or None,
                            "barcode_product": barcode_product,
                            "barcode_image_url": barcode_ref,
                        }
                    }
                ).eq("id", scan_id).eq("user_id", user_id).execute()
            except Exception:
                pass

        if not all_detections:
            raise ValueError("No ingredients detected in video")

        unique_detections = await deduplicate_detections(all_detections)

        for detection in unique_detections:
            detected_id = str(uuid4())

            thumbnail_url = None
            try:
                if representative_frame and isinstance(detection, dict) and detection.get("bbox"):
                    cropped = _safe_crop_by_bbox(representative_frame, detection.get("bbox"))
                    if cropped:
                        expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
                        thumbnail_url = upload_inventory_image(
                            user_id=user_id,
                            content=cropped,
                            content_type="image/jpeg",
                            asset_type="crop",
                            source="video_scanning",
                            expires_at=expires_at,
                            links={"scan_id": scan_id, "detected_id": detected_id},
                            metadata={"kind": "video_frame_crop"},
                        )
            except Exception:
                thumbnail_url = None

            db.table("detected_ingredients").insert(
                {
                    "id": detected_id,
                    "scan_id": scan_id,
                    "user_id": user_id,
                    "detected_name": detection.get("detected_name"),
                    "canonical_name": detection.get("canonical_name"),
                    "confidence": float(detection.get("confidence", 0) or 0),
                    "detected_quantity": detection.get("quantity"),
                    "detected_unit": detection.get("unit"),
                    "quantity_confidence": detection.get("quantity_confidence"),
                    "close_alternatives": detection.get("close_alternatives", []),
                    "visual_similarity_group": detection.get("visual_similarity_group"),
                    "confirmation_status": "pending",
                    "thumbnail_url": thumbnail_url,
                    "full_image_url": None,
                }
            ).execute()

        # Some deployments use KPI fields like `detected_count` (migration 016).
        # Older clients/code used `total_detections`; avoid writing unknown columns.
        completed_update = {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
        }
        try:
            completed_update["detected_count"] = int(len(unique_detections))
            db.table("ingredient_scans").update(completed_update).eq("id", scan_id).eq("user_id", user_id).execute()
        except Exception:
            # Best-effort fallback: store counts in image_metadata.
            try:
                db.table("ingredient_scans").update(
                    {
                        "status": "completed",
                        "completed_at": datetime.utcnow().isoformat(),
                        "image_metadata": {
                            "source": "video_scan",
                            "total_detections": int(len(unique_detections)),
                            "completed_at": datetime.utcnow().isoformat(),
                        },
                    }
                ).eq("id", scan_id).eq("user_id", user_id).execute()
            except Exception:
                pass

    except Exception as e:
        try:
            from app.core.database import get_db_client

            db = get_db_client()
            db.table("ingredient_scans").update(
                {
                    "status": "failed",
                    "completed_at": datetime.utcnow().isoformat(),
                    "image_metadata": {
                        "source": "video_scan",
                        "error": str(e)[:500],
                    },
                }
            ).eq("id", scan_id).eq("user_id", user_id).execute()
        except Exception:
            pass


# ============================================================================
# Video Upload Endpoint
# ============================================================================

@router.post("/analyze")
async def analyze_video(
    video: UploadFile = File(...),
    scan_type: str = Form("pantry"),
    location_hint: Optional[str] = Form(None),
    max_frames: int = Form(10),
    duration_seconds: Optional[int] = Form(None),
    async_mode: bool = Form(True),
    barcode: Optional[str] = Form(None),
    barcode_name_hint: Optional[str] = Form(None),
    barcode_quantity_hint: Optional[float] = Form(None),
    barcode_unit_hint: Optional[str] = Form(None),
    user: dict = Depends(get_current_user),
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

        user_id = (user or {}).get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        # Validate video file
        if not video.content_type.startswith('video/'):
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {video.content_type}. Must be a video file."
            )
        
        scan_type = _normalize_scan_type(scan_type)

        if duration_seconds is not None:
            duration_seconds = int(duration_seconds)
            duration_seconds = min(max(1, duration_seconds), 60)

        # Limit max frames (optimize for 30s scans)
        max_frames = min(max(1, max_frames), 20)
        if duration_seconds is not None and duration_seconds >= 25:
            max_frames = min(max_frames, 12)
        
        # Read video data
        video_data = await video.read()
        video_size_mb = len(video_data) / (1024 * 1024)
        
        if video_size_mb > 100:  # 100MB limit
            raise HTTPException(
                status_code=413,
                detail=f"Video too large: {video_size_mb:.1f}MB. Maximum is 100MB."
            )
        
        logger.info(f"Processing video: {video.filename}, size: {video_size_mb:.1f}MB")

        # Create database entry for video scan
        db = get_db_client()
        scan_id = str(uuid4())

        # Persist video to storage so processing can be resumed by a worker.
        video_ref: Optional[str] = None
        try:
            expires_at = (datetime.utcnow() + timedelta(days=7)).isoformat()
            video_ref = upload_scan_video(
                user_id=user_id,
                content=video_data,
                content_type=video.content_type,
                asset_type="scan_video",
                source="video_scanning",
                expires_at=expires_at,
                links={"scan_id": scan_id},
                metadata={
                    "scan_type": scan_type,
                    "duration_seconds": duration_seconds,
                    "video_filename": video.filename,
                    "video_size_mb": round(video_size_mb, 3),
                },
                filename=video.filename,
            )
        except Exception as e:
            logger.warning(f"Failed to upload scan video to storage: {e}")

        # Representative frame is extracted + uploaded by the background worker.
        representative_image_ref = None

        barcode_ref = None
        barcode_product = None
        try:
            if barcode and barcode.strip():
                barcode_ref, barcode_product = await _try_fetch_barcode_image(user_id, barcode)
        except Exception:
            barcode_ref, barcode_product = None, None
        
        # NOTE: ingredient_scans schema defines image_metadata (not metadata).
        # Also, scan_type has a CHECK constraint and must be one of: pantry|fridge|counter|shopping|other.
        db.table("ingredient_scans").insert({
            "id": scan_id,
            "user_id": user_id,
            "scan_type": scan_type,
            "location_hint": location_hint,
            "status": "processing",
            "image_url": representative_image_ref,
            "created_at": datetime.utcnow().isoformat(),
            "image_metadata": {
                "source": "video_scan",
                "duration_seconds": duration_seconds,
                "video_filename": video.filename,
                "video_size_mb": video_size_mb,
                "video_ref": video_ref,
                "max_frames": max_frames,
                "frames_extracted": 0,
                "frames_total": None,
                "frames_done": 0,
                "representative_frame_image_url": representative_image_ref,
                "barcode": (barcode or "").strip() or None,
                "barcode_name_hint": (barcode_name_hint or "").strip() or None,
                "barcode_quantity_hint": barcode_quantity_hint,
                "barcode_unit_hint": (barcode_unit_hint or "").strip() or None,
                "barcode_product": barcode_product,
                "barcode_image_url": barcode_ref,
            },
        }).execute()

        # Best-effort: enqueue a durable job record so a worker can resume processing.
        try:
            db.table("scan_jobs").insert(
                {
                    "scan_id": scan_id,
                    "user_id": user_id,
                    "job_type": "video_scan",
                    "status": "pending",
                    "attempts": 0,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat(),
                }
            ).execute()
        except Exception:
            pass

        async def _process_with_job_lock() -> None:
            # Mark job running (best-effort). This prevents duplicate processing if a worker exists.
            try:
                db.table("scan_jobs").update(
                    {
                        "status": "running",
                        "locked_at": datetime.utcnow().isoformat(),
                        "locked_by": "web",
                        "attempts": 1,
                        "updated_at": datetime.utcnow().isoformat(),
                    }
                ).eq("scan_id", scan_id).eq("job_type", "video_scan").execute()
            except Exception:
                pass

            try:
                await _process_video_scan(
                    scan_id=scan_id,
                    user_id=user_id,
                    video_data=video_data,
                    scan_type=scan_type,
                    location_hint=location_hint,
                    max_frames=max_frames,
                    duration_seconds=duration_seconds,
                    video_filename=video.filename,
                    video_size_mb=video_size_mb,
                    barcode=barcode,
                    barcode_name_hint=barcode_name_hint,
                    barcode_quantity_hint=barcode_quantity_hint,
                    barcode_unit_hint=barcode_unit_hint,
                    barcode_ref=barcode_ref,
                    barcode_product=barcode_product,
                )
                try:
                    db.table("scan_jobs").update(
                        {"status": "completed", "updated_at": datetime.utcnow().isoformat()}
                    ).eq("scan_id", scan_id).eq("job_type", "video_scan").execute()
                except Exception:
                    pass
            except Exception as e:
                try:
                    db.table("scan_jobs").update(
                        {
                            "status": "failed",
                            "last_error": str(e)[:500],
                            "updated_at": datetime.utcnow().isoformat(),
                        }
                    ).eq("scan_id", scan_id).eq("job_type", "video_scan").execute()
                except Exception:
                    pass
                raise

        if async_mode:
            asyncio.create_task(_process_with_job_lock())
            return {
                "success": True,
                "scan_id": scan_id,
                "status": "processing",
                "message": "Video uploaded. Processing started.",
                "next_step": "Poll /api/scanning/video/status/{scan_id} until completed",
            }

        # Sync fallback: wait for processing and return detections via status.
        await _process_with_job_lock()

        # Return completed payload by reusing status endpoint logic.
        return {
            "success": True,
            "scan_id": scan_id,
            "status": "completed",
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Video analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Video analysis failed: {str(e)}")


@router.get("/status/{scan_id}")
async def get_video_scan_status(
    scan_id: str,
    user: dict = Depends(get_current_user),
):
    """
    Get status of video scan (for progress tracking)
    """
    try:
        from app.core.database import get_db_client

        user_id = (user or {}).get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Not authenticated")
        
        db = get_db_client()
        
        scan = db.table("ingredient_scans") \
            .select("*") \
            .eq("id", scan_id) \
            .eq("user_id", user_id) \
            .single() \
            .execute()
        
        if not scan.data:
            raise HTTPException(status_code=404, detail="Scan not found")
        
        payload = {
            "scan_id": scan_id,
            "status": scan.data["status"],
            "scan_type": scan.data["scan_type"],
            "created_at": scan.data["created_at"],
            "completed_at": scan.data.get("completed_at"),
            "total_detections": scan.data.get("detected_count")
            or scan.data.get("total_detections")
            or (scan.data.get("image_metadata") or {}).get("total_detections")
            or 0,
            "metadata": scan.data.get("image_metadata", {})
        }

        if scan.data.get("status") == "completed":
            det = (
                db.table("detected_ingredients")
                .select("*")
                .eq("scan_id", scan_id)
                .eq("user_id", user_id)
                .order("confidence", desc=True)
                .limit(200)
                .execute()
            ).data or []

            # Map DB column names to the client JSON contract used by ScanIngredientsScreen.
            mapped: List[Dict[str, Any]] = []
            for r in det:
                if not isinstance(r, dict):
                    continue
                mapped.append(
                    {
                        "id": r.get("id"),
                        "detected_name": r.get("detected_name"),
                        "canonical_name": r.get("canonical_name"),
                        "confidence": r.get("confidence"),
                        "quantity": r.get("detected_quantity"),
                        "unit": r.get("detected_unit"),
                        "quantity_confidence": r.get("quantity_confidence"),
                        "quantity_source": r.get("quantity_source"),
                        "item_form": r.get("item_form"),
                        "change_status": r.get("change_status"),
                        "previous_quantity": r.get("previous_quantity"),
                        "previous_unit": r.get("previous_unit"),
                        "thumbnail_url": r.get("thumbnail_url"),
                    }
                )
            payload["detections"] = mapped

        return payload
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get scan status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get status: {str(e)}")
