"""
Training data collection endpoints
Phase 2: Custom vision model data pipeline
"""
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from typing import Optional

from app.models.training import (
    TrainingDataSubmission,
    TrainingDataResponse,
    TrainingStats
)

router = APIRouter()
logger = logging.getLogger(__name__)

# Storage directory for training data
# In production, this should be S3/CloudFlare R2
TRAINING_DATA_DIR = Path("training_data")
IMAGES_DIR = TRAINING_DATA_DIR / "images"
LABELS_DIR = TRAINING_DATA_DIR / "labels"
METADATA_DIR = TRAINING_DATA_DIR / "metadata"

# Ensure directories exist
for dir_path in [IMAGES_DIR, LABELS_DIR, METADATA_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)


def _get_date_subdir() -> str:
    """Get date-based subdirectory for organizing data"""
    return datetime.utcnow().strftime("%Y-%m")


@router.post("/submit", response_model=TrainingDataResponse)
async def submit_training_data(data: TrainingDataSubmission):
    """
    Submit training data from user-confirmed ingredient scan
    
    This endpoint stores:
    1. Image hash (reference to original image)
    2. Original detections (from Google Vision or custom model)
    3. User corrections (ground truth labels)
    4. Metadata (storage location, timestamp, device info)
    
    Data is stored in YOLO format for training:
    - images/{date}/{hash}.jpg
    - labels/{date}/{hash}.json
    """
    try:
        date_subdir = _get_date_subdir()
        
        # Create date subdirectories
        images_date_dir = IMAGES_DIR / date_subdir
        labels_date_dir = LABELS_DIR / date_subdir
        images_date_dir.mkdir(parents=True, exist_ok=True)
        labels_date_dir.mkdir(parents=True, exist_ok=True)
        
        # Store labels in YOLO-compatible format
        label_data = {
            "scan_id": data.scan_id,
            "image_hash": data.image_hash,
            "image_width": data.image_width,
            "image_height": data.image_height,
            "annotations": [
                {
                    "class": ing.ingredient,
                    "confidence": ing.confidence,
                    "bbox": ing.bbox.dict() if ing.bbox else None,
                    "quantity": ing.quantity_estimate,
                    "storage": ing.storage_hint,
                    "source": ing.source
                }
                for ing in data.user_corrections
            ],
            "original_detections": [
                {
                    "class": ing.ingredient,
                    "confidence": ing.confidence,
                    "source": ing.source
                }
                for ing in data.original_detections
            ],
            "metadata": {
                "storage_location": data.storage_location,
                "timestamp": data.timestamp,
                "user_id": data.user_id,
                "device_info": data.device_info
            }
        }
        
        # Save label file
        label_path = labels_date_dir / f"{data.image_hash}.json"
        with open(label_path, "w") as f:
            json.dump(label_data, f, indent=2)
        
        # Update statistics
        await _update_training_stats(data)
        
        logger.info(
            f"Training data stored: scan_id={data.scan_id}, "
            f"labels={len(data.user_corrections)}, "
            f"corrections={len(data.original_detections) - len(data.user_corrections)}"
        )
        
        return TrainingDataResponse(
            status="ok",
            scan_id=data.scan_id,
            stored=True,
            message=f"Training data stored successfully. {len(data.user_corrections)} labels saved."
        )
        
    except Exception as e:
        logger.error(f"Failed to store training data: {e}")
        return TrainingDataResponse(
            status="error",
            scan_id=data.scan_id,
            stored=False,
            message=f"Failed to store training data: {str(e)}"
        )


@router.post("/upload-image")
async def upload_training_image(
    image: UploadFile = File(...),
    scan_id: Optional[str] = None
):
    """
    Upload image for training data
    Returns image hash for reference in submit endpoint
    
    In production, this should upload to S3/CloudFlare R2
    """
    try:
        # Read image
        contents = await image.read()
        
        # Compute hash
        image_hash = hashlib.sha256(contents).hexdigest()
        
        # Store image
        date_subdir = _get_date_subdir()
        images_date_dir = IMAGES_DIR / date_subdir
        images_date_dir.mkdir(parents=True, exist_ok=True)
        
        # Save with hash as filename
        image_path = images_date_dir / f"{image_hash}.jpg"
        with open(image_path, "wb") as f:
            f.write(contents)
        
        logger.info(f"Training image uploaded: hash={image_hash}, size={len(contents)} bytes")
        
        return {
            "status": "ok",
            "image_hash": image_hash,
            "scan_id": scan_id,
            "path": str(image_path.relative_to(TRAINING_DATA_DIR))
        }
        
    except Exception as e:
        logger.error(f"Failed to upload training image: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")


@router.get("/stats", response_model=TrainingStats)
async def get_training_stats():
    """
    Get statistics about collected training data
    
    Returns:
    - Total images collected
    - Total labels
    - Unique ingredient classes
    - Collection rate
    """
    try:
        # Count label files
        label_files = list(LABELS_DIR.rglob("*.json"))
        total_images = len(label_files)
        
        # Analyze labels
        all_ingredients = set()
        total_labels = 0
        storage_breakdown = {"pantry": 0, "fridge": 0, "freezer": 0, "unknown": 0}
        
        for label_file in label_files:
            with open(label_file) as f:
                label_data = json.load(f)
                annotations = label_data.get("annotations", [])
                total_labels += len(annotations)
                
                for ann in annotations:
                    all_ingredients.add(ann.get("class", "unknown"))
                
                storage = label_data.get("metadata", {}).get("storage_location", "unknown")
                if storage in storage_breakdown:
                    storage_breakdown[storage] += 1
                else:
                    storage_breakdown["unknown"] += 1
        
        # Calculate collection rate (simplified)
        collection_rate = f"{total_images} total" if total_images > 0 else "No data yet"
        
        return TrainingStats(
            total_images=total_images,
            total_labels=total_labels,
            unique_ingredients=len(all_ingredients),
            storage_locations=storage_breakdown,
            collection_rate=collection_rate,
            last_updated=datetime.utcnow().isoformat()
        )
        
    except Exception as e:
        logger.error(f"Failed to get training stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")


async def _update_training_stats(data: TrainingDataSubmission):
    """Update aggregate training statistics"""
    stats_file = METADATA_DIR / "stats.json"
    
    try:
        # Load existing stats
        if stats_file.exists():
            with open(stats_file) as f:
                stats = json.load(f)
        else:
            stats = {
                "total_scans": 0,
                "total_labels": 0,
                "ingredients": {},
                "last_updated": None
            }
        
        # Update stats
        stats["total_scans"] += 1
        stats["total_labels"] += len(data.user_corrections)
        stats["last_updated"] = datetime.utcnow().isoformat()
        
        for ing in data.user_corrections:
            ingredient_name = ing.ingredient
            if ingredient_name not in stats["ingredients"]:
                stats["ingredients"][ingredient_name] = 0
            stats["ingredients"][ingredient_name] += 1
        
        # Save updated stats
        with open(stats_file, "w") as f:
            json.dump(stats, f, indent=2)
            
    except Exception as e:
        logger.warning(f"Failed to update training stats: {e}")
