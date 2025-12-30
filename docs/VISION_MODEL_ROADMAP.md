# Phase 2 Roadmap: Custom Vision Model for Ingredient Detection

**Status:** Planning Phase  
**Goal:** Replace Google Vision API with SAVO-owned ingredient detection model  
**Impact:** 99% cost reduction ($1.50 → $0.01 per scan) + data ownership  
**Timeline:** 3-6 months  

---

## Executive Summary

**Current State (Phase 1):**
- Using Google Gemini Vision API for ingredient scanning
- Cost: ~$1.50 per image scan
- Data: User corrections stored but not used for training

**Target State (Phase 2):**
- Custom YOLO v8 or EfficientNet model for ingredient detection
- Cost: ~$0.01 per scan (150x cheaper)
- Moat: Proprietary ingredient detection trained on SAVO user data

**Why This Matters:**
- **Cost:** $150K/year → $1K/year at 100K users
- **Control:** Own the model, no API limits
- **Quality:** Optimized for pantry/fridge scenarios
- **Speed:** Edge deployment possible (on-device detection)
- **Moat:** Defensible IP that improves with usage

---

## Phase 2.1: Data Collection Pipeline (Month 1-2)

### Objective
Collect 50K+ labeled ingredient images from production users

### What You're Already Collecting ✅
Your current [inventory.py](../services/api/app/api/routes/inventory.py) scan flow:
1. User uploads image → Google Vision detects ingredients
2. User reviews and corrects → **This is training data!**
3. User confirms → Ingredients saved

### Implementation Steps

#### 1. Add Training Data Collection Endpoint

**File:** `services/api/app/api/routes/training.py` (new)

```python
"""
Training data collection for custom vision model
"""
import base64
import hashlib
from datetime import datetime
from fastapi import APIRouter, UploadFile, File
from pydantic import BaseModel

router = APIRouter()

class TrainingDataSubmission(BaseModel):
    image_hash: str
    scan_id: str
    original_detections: list[dict]  # From Google Vision
    user_corrections: list[dict]     # After user review
    storage_location: str            # pantry/fridge/freezer
    timestamp: str

@router.post("/training/submit")
async def submit_training_data(data: TrainingDataSubmission):
    """
    Collect training data from user corrections
    Stores: image + labels for future model training
    """
    # Store in blob storage (S3/CloudFlare R2)
    # Format: images/{date}/{hash}.jpg
    #         labels/{date}/{hash}.json
    pass
```

#### 2. Update Scan Endpoint to Collect Data

Add to [inventory.py](../services/api/app/api/routes/inventory.py#L91):

```python
# After user confirms scan results
if user_confirmed:
    # Store for training
    await submit_training_data({
        "image_hash": hash_image(raw),
        "scan_id": str(uuid.uuid4()),
        "original_detections": google_vision_result,
        "user_corrections": user_confirmed_items,
        "storage_location": storage_hint,
        "timestamp": datetime.utcnow().isoformat()
    })
```

#### 3. Data Storage Strategy

**Storage Options:**
- **CloudFlare R2:** $0.015/GB, free egress (recommended)
- **AWS S3:** $0.023/GB, egress charges
- **Render Disk:** Limited, not scalable

**Directory Structure:**
```
training-data/
  images/
    2025-12/
      {hash1}.jpg
      {hash2}.jpg
  labels/
    2025-12/
      {hash1}.json  # YOLO format or COCO format
      {hash2}.json
  metadata/
    stats.json      # Collection metrics
```

#### 4. Label Format (YOLO v8)

```json
{
  "image_id": "abc123",
  "width": 1920,
  "height": 1080,
  "annotations": [
    {
      "class": "tomato",
      "bbox": [x, y, width, height],
      "confidence": 0.91,
      "source": "user_confirmed"
    }
  ]
}
```

### Success Metrics
- ✅ 10K images collected (Month 1)
- ✅ 50K images collected (Month 2)
- ✅ 100+ ingredient classes labeled
- ✅ User corrections < 20% (data quality indicator)

---

## Phase 2.2: Model Selection & Training (Month 2-3)

### Model Architecture Options

#### Option 1: YOLO v8 (Recommended)
**Pros:**
- Best real-time object detection
- Excellent for mobile/edge deployment
- Active community, great documentation
- Pre-trained on COCO dataset (includes food)

**Cons:**
- Requires GPU for training
- Needs bounding box annotations

**Use Case:** Best for "detect all visible ingredients"

**Training:**
```bash
# Install ultralytics
pip install ultralytics

# Train custom YOLO model
yolo detect train \
  data=savo_ingredients.yaml \
  model=yolov8n.pt \
  epochs=100 \
  imgsz=640 \
  batch=16
```

#### Option 2: EfficientNet + Classification
**Pros:**
- Simpler (classification only)
- Faster training
- Smaller model size
- Good for mobile

**Cons:**
- Can't detect multiple items per image (requires cropping)
- Less spatial awareness

**Use Case:** Best for "what's the main ingredient in this image?"

#### Option 3: Detectron2 (Facebook)
**Pros:**
- State-of-the-art accuracy
- Instance segmentation (exact boundaries)
- Research-grade quality

**Cons:**
- Slower inference
- Heavier model
- More complex deployment

**Use Case:** Best for production quality after YOLO v8 proves concept

### Recommended Path: YOLO v8 → Detectron2

**Phase 2.2a:** Start with YOLO v8 (faster iteration)  
**Phase 2.2b:** Upgrade to Detectron2 for production quality

### Training Infrastructure

#### Cloud Options

**1. AWS SageMaker**
- **Cost:** ~$3/hour (ml.p3.2xlarge with GPU)
- **Training Time:** 50K images = ~20 hours = $60
- **Pros:** Managed, scalable
- **Cons:** AWS lock-in

**2. Render.com + GPU**
- **Cost:** Not available (Render doesn't offer GPU workers)
- **Verdict:** Use for inference only

**3. Lambda Labs / RunPod**
- **Cost:** ~$0.50/hour (RTX 3090)
- **Training Time:** 50K images = ~15 hours = $7.50
- **Pros:** Cheapest, flexible
- **Cons:** Manual setup

**4. Google Colab Pro**
- **Cost:** $10/month (unlimited)
- **Training Time:** Can train entire model for $10
- **Pros:** Cheapest for experimentation
- **Cons:** Session limits, not production

### Recommended Training Stack

**Experimentation:** Google Colab Pro ($10/month)  
**Production Training:** Lambda Labs ($0.50/hr)  
**Deployment:** Render.com (CPU inference)

### Training Pipeline

```python
# services/ml/train_vision_model.py

import ultralytics
from pathlib import Path

def train_savo_vision_model(
    data_dir: Path,
    model_name: str = "yolov8n.pt",
    epochs: int = 100,
    batch_size: int = 16
):
    """
    Train custom YOLO model on SAVO ingredient data
    """
    
    # Load pre-trained weights
    model = ultralytics.YOLO(model_name)
    
    # Train on SAVO data
    results = model.train(
        data=data_dir / "savo_ingredients.yaml",
        epochs=epochs,
        imgsz=640,
        batch=batch_size,
        device=0,  # GPU
        workers=8,
        patience=20,  # Early stopping
        save=True,
        plots=True
    )
    
    # Validate
    metrics = model.val()
    
    return {
        "model_path": results.save_dir / "weights/best.pt",
        "mAP50": metrics.box.map50,
        "mAP50-95": metrics.box.map
    }
```

### Success Metrics
- ✅ mAP@0.5 > 0.75 (75% accuracy at 50% IoU)
- ✅ Inference < 100ms per image
- ✅ Model size < 50MB (for mobile deployment)
- ✅ Detects top 50 ingredients with 90%+ accuracy

---

## Phase 2.3: API Integration (Month 3-4)

### Model Deployment Architecture

```
┌─────────────────────────────────────────┐
│  User uploads image                     │
└─────────────────┬───────────────────────┘
                  │
        ┌─────────▼──────────┐
        │ Feature Flag Check │
        └─────────┬──────────┘
                  │
        ┌─────────▼──────────────────┐
        │ Use Custom Model?          │
        │ (Based on confidence/user) │
        └─────┬──────────────┬───────┘
              │              │
      ┌───────▼────┐    ┌───▼──────────┐
      │ SAVO YOLO  │    │ Google Vision│
      │ v8 Model   │    │ (Fallback)   │
      └───────┬────┘    └───┬──────────┘
              │              │
              └──────┬───────┘
                     │
        ┌────────────▼──────────────┐
        │ Merge & Normalize Results │
        └────────────┬──────────────┘
                     │
        ┌────────────▼──────────────┐
        │ User Confirmation UI      │
        └───────────────────────────┘
```

### Implementation

#### 1. Add Custom Vision Client

**File:** `services/api/app/core/vision_client.py` (new)

```python
"""
Custom SAVO vision model client
"""
import torch
from ultralytics import YOLO
from pathlib import Path
import numpy as np
from typing import List, Dict

class SavoVisionModel:
    """Custom ingredient detection model"""
    
    def __init__(self, model_path: Path):
        self.model = YOLO(model_path)
        self.confidence_threshold = 0.5
    
    async def detect_ingredients(
        self, 
        image_bytes: bytes
    ) -> List[Dict]:
        """
        Detect ingredients from image
        
        Returns:
        [
            {
                "ingredient": "tomato",
                "confidence": 0.91,
                "bbox": [x, y, w, h],
                "quantity_estimate": "3 pcs"
            }
        ]
        """
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        # Run inference
        results = self.model(img, conf=self.confidence_threshold)
        
        # Parse results
        detections = []
        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls = int(box.cls[0])
                conf = float(box.conf[0])
                bbox = box.xyxy[0].tolist()
                
                detections.append({
                    "ingredient": self.model.names[cls],
                    "confidence": conf,
                    "bbox": bbox,
                    "quantity_estimate": self._estimate_quantity(bbox)
                })
        
        return detections
    
    def _estimate_quantity(self, bbox: List[float]) -> str:
        """Estimate quantity from bounding box size"""
        # Simple heuristic: larger bbox = more items
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        if area > 10000:
            return "many"
        elif area > 5000:
            return "several"
        else:
            return "1-2"
```

#### 2. Update Inventory Scan Endpoint

**File:** `services/api/app/api/routes/inventory.py`

```python
from app.core.vision_client import SavoVisionModel
from app.core.settings import settings

# Initialize at startup
SAVO_MODEL = None
if settings.use_custom_vision_model:
    model_path = Path(settings.custom_vision_model_path)
    SAVO_MODEL = SavoVisionModel(model_path)

@router.post("/scan", response_model=ScanIngredientsResponse)
async def scan_ingredients(
    image: UploadFile = File(...),
    storage_hint: str = None,
    use_custom_model: bool = True  # Feature flag
):
    """Scan ingredients with hybrid approach"""
    
    raw = await image.read()
    
    # Try custom model first
    if use_custom_model and SAVO_MODEL:
        try:
            detections = await SAVO_MODEL.detect_ingredients(raw)
            
            # Fall back to Google if confidence too low
            avg_confidence = np.mean([d['confidence'] for d in detections])
            if avg_confidence < 0.6:
                logger.info("Low confidence, falling back to Google Vision")
                detections = await _google_vision_fallback(raw)
            
            return ScanIngredientsResponse(
                status="ok",
                scanned_items=detections,
                model_used="savo-yolo-v8"
            )
        except Exception as e:
            logger.error(f"Custom model failed: {e}, falling back")
            # Fall through to Google Vision
    
    # Google Vision fallback
    return await _google_vision_scan(raw, storage_hint)
```

#### 3. Add Settings

**File:** `services/api/app/core/settings.py`

```python
class Settings(BaseModel):
    # ... existing settings
    
    # Custom vision model settings
    use_custom_vision_model: bool = os.getenv(
        "SAVO_USE_CUSTOM_VISION", 
        "false"
    ).lower() == "true"
    
    custom_vision_model_path: str = os.getenv(
        "SAVO_VISION_MODEL_PATH",
        "./models/savo_yolo_v8.pt"
    )
    
    vision_confidence_threshold: float = float(
        os.getenv("SAVO_VISION_CONFIDENCE", "0.5")
    )
```

### Deployment Strategy

#### Gradual Rollout (A/B Testing)

**Week 1:** 5% of users use custom model  
**Week 2:** 25% if success metrics met  
**Week 3:** 50% if success metrics met  
**Week 4:** 100% if success metrics met  

**Success Metrics:**
- User correction rate < 30%
- Average confidence > 0.7
- Inference time < 200ms
- No increase in error reports

### Success Metrics
- ✅ Custom model serves 100% of requests
- ✅ Google Vision fallback < 10% of scans
- ✅ User satisfaction maintained (corrections < 30%)
- ✅ Inference cost < $0.01 per scan

---

## Phase 2.4: Cost Optimization (Month 4-5)

### Current Architecture (Phase 1)
```
User → Render API → Google Vision API → Response
Cost: $1.50/scan
```

### Target Architecture (Phase 2)
```
User → Render API → SAVO YOLO Model (CPU) → Response
Cost: $0.01/scan (compute only)
```

### Deployment Options

#### Option 1: CPU Inference on Render
**Pros:** Simple, no changes needed  
**Cons:** Slower (100-200ms)  
**Cost:** Free tier covers it  

#### Option 2: GPU Worker on Render
**Pros:** Faster (10-20ms)  
**Cons:** Render doesn't offer GPU workers  
**Cost:** N/A  

#### Option 3: Dedicated ML Service (Banana.dev, Replicate)
**Pros:** Optimized for ML inference  
**Cons:** Additional service to manage  
**Cost:** ~$0.001/inference  

#### Option 4: Edge Deployment (Future)
**Pros:** Zero server cost, instant results  
**Cons:** Requires mobile app integration  
**Cost:** $0 (runs on user's device)  

### Recommended: Start with CPU on Render

### Model Optimization for CPU

```python
# Convert to ONNX for faster CPU inference
from ultralytics import YOLO

model = YOLO("savo_yolo_v8.pt")
model.export(format="onnx", optimize=True)

# Use ONNX Runtime for inference
import onnxruntime as ort

session = ort.InferenceSession(
    "savo_yolo_v8.onnx",
    providers=['CPUExecutionProvider']
)
```

### Cost Comparison (100K Users, 2 Scans/Month)

| Approach | Cost/Scan | Monthly Cost (200K scans) | Annual Cost |
|----------|-----------|---------------------------|-------------|
| **Google Vision** | $1.50 | $300,000 | $3.6M |
| **Custom CPU** | $0.01 | $2,000 | $24K |
| **Custom GPU** | $0.005 | $1,000 | $12K |
| **Edge (Mobile)** | $0.00 | $0 | $0 |

**Savings: $3.576M/year at scale**

---

## Phase 2.5: Continuous Improvement (Month 5-6)

### Active Learning Pipeline

```
User Scans → Model Predicts → User Corrects → Retrain Monthly
```

#### 1. Identify Low-Confidence Cases

```python
# Flag scans that need human review
if avg_confidence < 0.7:
    # Send to human reviewer (internal or MTurk)
    await queue_for_review(scan_id, detections)
```

#### 2. Monthly Retraining

```python
# Automated retraining pipeline
def monthly_retrain():
    # 1. Collect new labeled data from past month
    new_data = collect_training_data(
        start_date=last_month,
        min_confidence=0.9  # Only high-quality corrections
    )
    
    # 2. Merge with existing dataset
    full_dataset = merge_datasets(existing_data, new_data)
    
    # 3. Retrain model
    new_model = train_savo_vision_model(
        data_dir=full_dataset,
        epochs=50,  # Fine-tuning
        pretrained=current_model_path
    )
    
    # 4. Validate improvement
    metrics = validate_model(new_model, test_set)
    
    # 5. Deploy if better
    if metrics.mAP > current_metrics.mAP:
        deploy_model(new_model)
```

### Success Metrics
- ✅ Model improves 5% per quarter (mAP)
- ✅ New ingredient classes added monthly
- ✅ User correction rate decreases over time
- ✅ Long-tail ingredients detected (rare items)

---

## Timeline & Milestones

### Month 1-2: Data Collection
- ✅ Deploy training data collection endpoint
- ✅ Collect 50K labeled images
- ✅ Build data pipeline (CloudFlare R2)

### Month 2-3: Model Training
- ✅ Train YOLO v8 on SAVO data
- ✅ Achieve mAP@0.5 > 0.75
- ✅ Optimize for CPU inference

### Month 3-4: Integration
- ✅ Deploy custom model to Render
- ✅ Implement hybrid fallback (custom + Google)
- ✅ A/B test with 5% → 100% users

### Month 4-5: Optimization
- ✅ Reduce inference time < 100ms
- ✅ Convert to ONNX for CPU efficiency
- ✅ Monitor cost savings

### Month 5-6: Continuous Improvement
- ✅ Set up monthly retraining pipeline
- ✅ Active learning for edge cases
- ✅ Add new ingredient classes

---

## Resource Requirements

### Team
- **1 ML Engineer** (3-6 months)
- **1 Backend Engineer** (1 month for integration)
- **Optional:** Contract labelers (if human review needed)

### Infrastructure
- **Training:** Google Colab Pro ($10/mo) or Lambda Labs ($50/mo)
- **Storage:** CloudFlare R2 (50K images = ~10GB = $0.15/mo)
- **Deployment:** Render.com (free tier → $25/mo for optimized)

### Total Cost (Phase 2)
- **One-time:** $5K-$10K (ML engineering + training)
- **Monthly:** $35/mo (infrastructure)
- **Savings:** $3.5M+/year at scale

**ROI:** 350x return in first year

---

## Risk Mitigation

### Risk 1: Model Accuracy Lower Than Google
**Mitigation:** Hybrid approach with Google fallback  
**Fallback:** Keep Google for 6 more months  

### Risk 2: Training Data Insufficient
**Mitigation:** Start with 10K images, supplement with public datasets  
**Fallback:** Use Food-101, Open Images for pre-training  

### Risk 3: Inference Too Slow
**Mitigation:** Start with CPU, optimize with ONNX  
**Fallback:** Use GPU service (Banana.dev) temporarily  

### Risk 4: User Satisfaction Drops
**Mitigation:** A/B test, monitor correction rates  
**Fallback:** Roll back to Google if metrics degrade  

---

## Success Criteria (Phase 2 Complete)

✅ **Cost:** < $0.01 per scan (150x reduction)  
✅ **Quality:** User correction rate < 30% (same as Google)  
✅ **Speed:** Inference < 200ms (acceptable UX)  
✅ **Coverage:** Top 100 ingredients detected with 85%+ accuracy  
✅ **Moat:** Proprietary model improving monthly with user data  

---

## Next Steps (Immediate)

### This Week
1. Add training data collection to [inventory.py](../services/api/app/api/routes/inventory.py)
2. Set up CloudFlare R2 bucket for image storage
3. Create `services/ml/` directory for training code

### Next Month
1. Collect 10K+ labeled images
2. Set up Google Colab training notebook
3. Train first YOLO v8 prototype

### Month 2
1. Integrate custom model into API
2. Deploy with 5% A/B test
3. Monitor metrics

---

## References & Resources

### Datasets
- [Food-101](https://data.vision.ee.ethz.ch/cvl/datasets_extra/food-101/) - 101K food images
- [Open Images](https://storage.googleapis.com/openimages/web/index.html) - Food category subset
- [COCO](https://cocodataset.org/) - General objects (includes some food)

### Tutorials
- [Ultralytics YOLO v8 Training](https://docs.ultralytics.com/modes/train/)
- [Custom Object Detection](https://blog.roboflow.com/how-to-train-yolov8-on-a-custom-dataset/)
- [ONNX Conversion](https://docs.ultralytics.com/integrations/onnx/)

### Tools
- [Roboflow](https://roboflow.com/) - Data labeling and augmentation
- [Label Studio](https://labelstud.io/) - Open-source annotation
- [Weights & Biases](https://wandb.ai/) - Training monitoring

---

**Document Status:** Planning Phase  
**Last Updated:** 2025-12-29  
**Owner:** Engineering Team  
**Review Cycle:** Monthly during Phase 2 execution
