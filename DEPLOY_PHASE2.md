# Phase 2 Deployment Guide: Training Data Collection

## 🚀 Immediate Deployment Steps (Week 1)

### Step 1: Deploy to Render (5 minutes)

1. **Push Latest Code** (already done ✅)
   - Commit: `a8a2cb2` - Phase 2 foundation complete
   - Training endpoints ready

2. **Go to Render Dashboard**
   - URL: https://dashboard.render.com
   - Select your `savo-api` service

3. **Configure Environment Variables**
   
   Click "Environment" → Add these variables:
   
   ```bash
   # === REQUIRED FOR TRAINING DATA COLLECTION ===
   SAVO_COLLECT_TRAINING_DATA=true
   
   # === DUAL-PROVIDER ARCHITECTURE ===
   SAVO_VISION_PROVIDER=google
   SAVO_REASONING_PROVIDER=openai
   
   # === API KEYS (from your dashboard) ===
   GOOGLE_API_KEY=<your-google-gemini-key>
   OPENAI_API_KEY=<your-openai-key>
   
   # === CUSTOM VISION (initially false, enable after Month 2) ===
   SAVO_USE_CUSTOM_VISION=false
   SAVO_CUSTOM_VISION_MODEL_PATH=/opt/render/project/src/services/ml/models/best.pt
   SAVO_VISION_CONFIDENCE_THRESHOLD=0.6
   ```

4. **Trigger Deployment**
   - Click "Manual Deploy" → "Deploy latest commit"
   - Or: Render auto-deploys on git push (if configured)
   - Wait 3-5 minutes for build

5. **Verify Training Endpoints**
   ```bash
   # Open in browser:
   https://savo-ynp1.onrender.com/docs#/training
   
   # Or test via curl:
   curl https://savo-ynp1.onrender.com/training/stats
   ```

---

## 📊 Step 2: Monitor Data Collection (Daily)

### Check Collection Progress

```bash
# Via Browser:
https://savo-ynp1.onrender.com/training/stats

# Via API:
curl https://savo-ynp1.onrender.com/training/stats

# Expected Response:
{
  "total_samples": 0,
  "samples_today": 0,
  "samples_this_week": 0,
  "average_detections_per_image": 0,
  "correction_rate": 0,
  "storage_size_mb": 0,
  "last_updated": "2025-12-29T..."
}
```

### Metrics to Track

| Metric | Week 1 Goal | Month 1 Goal | Month 2 Goal |
|--------|-------------|--------------|--------------|
| **Total Samples** | 100 | 10,000 | 50,000 |
| **Daily Rate** | 14/day | 330/day | 1,667/day |
| **Correction Rate** | ~50% | ~30% | ~20% |
| **Storage Size** | ~50 MB | ~5 GB | ~25 GB |

### Dashboard (Optional - Build Later)

Create a simple monitoring dashboard:
- Grafana + InfluxDB
- Or: Simple HTML page fetching /training/stats
- Or: Weekly email digest with progress

---

## 🏋️ Step 3: Train First Prototype (After 10K Images - Month 2)

### Prerequisites

```bash
# Check data collection progress
curl https://savo-ynp1.onrender.com/training/stats

# Response should show:
# "total_samples": 10000+
```

### Download Training Data from Production

```bash
# SSH into Render instance or use Render Shell
cd /opt/render/project/src/services/api/training_data

# Compress training data
tar -czf training_data.tar.gz images/ labels/

# Download to local machine (via Render dashboard or scp)
# Or: Sync to CloudFlare R2 for backup
```

### Prepare Dataset

```bash
cd services/ml

# Convert API data to YOLO format
python data/prepare.py \
  --input ../api/training_data \
  --output ./datasets/savo_v1 \
  --split 0.7 0.2 0.1

# Output:
# datasets/savo_v1/
#   images/
#     train/
#     val/
#     test/
#   labels/
#     train/
#     val/
#     test/
#   dataset.yaml
```

### Train YOLO v8 Model

```bash
# Option A: Local Training (if you have GPU)
python train.py \
  --data ./datasets/savo_v1/dataset.yaml \
  --epochs 100 \
  --batch 16 \
  --device 0

# Option B: Google Colab (free GPU)
# 1. Upload datasets/savo_v1/ to Google Drive
# 2. Open Colab notebook
# 3. Run training script

# Option C: Paperspace / Lambda Labs ($0.50/hour)
# Best option for production training
```

### Training Configuration

```yaml
# services/ml/datasets/savo_v1/dataset.yaml
path: /path/to/savo_v1
train: images/train
val: images/val
test: images/test

nc: 50  # Number of ingredient classes
names: ['tomato', 'onion', 'garlic', ...]  # Auto-generated from labels
```

### Expected Results (First Model)

```
Epoch 100/100:
  mAP@0.5:    0.72  (target: > 0.75)
  mAP@0.5-0.95: 0.45  (industry standard)
  Precision:  0.78
  Recall:     0.68
  
Training time: 2-4 hours on T4 GPU
```

**If mAP < 0.75:** Collect 10K more samples and retrain

---

## 🧪 Step 4: A/B Test Custom Model (Month 3)

### Deploy Custom Model to Render

```bash
# 1. Export trained model
cd services/ml
python -c "
from ultralytics import YOLO
model = YOLO('runs/train/savo_v1/weights/best.pt')
model.export(format='onnx')  # CPU-friendly format
"

# 2. Upload to Render
# Option A: Include in git repo (if < 100MB)
git add services/ml/models/best.onnx
git commit -m "Add custom vision model v1"
git push

# Option B: Use external storage (if > 100MB)
# Upload to CloudFlare R2
# Download in Render start script
```

### Enable Custom Model (Gradual Rollout)

```bash
# Week 1: 5% traffic
SAVO_USE_CUSTOM_VISION=true
SAVO_CUSTOM_VISION_ROLLOUT=0.05

# Week 2: 25% traffic (if metrics good)
SAVO_CUSTOM_VISION_ROLLOUT=0.25

# Week 3: 50% traffic
SAVO_CUSTOM_VISION_ROLLOUT=0.50

# Week 4: 100% traffic
SAVO_CUSTOM_VISION_ROLLOUT=1.0
```

### A/B Test Metrics

Track these metrics for custom vs Google Vision:

| Metric | Google Vision | Custom Model | Target |
|--------|---------------|--------------|--------|
| **Accuracy** | ~85% | ~80%+ | > 80% |
| **Latency (p95)** | 1200ms | < 800ms | < 1000ms |
| **Cost per scan** | $1.50 | $0.01 | < $0.10 |
| **User corrections** | ~30% | < 35% | < 30% |

### Hybrid Fallback Logic

```python
# Implemented in app/services/vision_service.py

async def detect_ingredients(image: bytes) -> List[Ingredient]:
    if settings.use_custom_vision_model:
        # Try custom model first
        result = await custom_vision_detect(image)
        
        if result.confidence >= settings.vision_confidence_threshold:
            return result.ingredients
        else:
            # Fallback to Google Vision if low confidence
            logger.info("Low confidence, falling back to Google Vision")
            return await google_vision_detect(image)
    else:
        # Use Google Vision (current default)
        return await google_vision_detect(image)
```

---

## 🔄 Step 5: Iterate & Improve (Month 4+)

### Monthly Retraining Schedule

```bash
# Every 30 days:
1. Download latest training data (target: +10K new samples/month)
2. Merge with existing dataset
3. Retrain YOLO v8 for 50-100 epochs
4. Evaluate on holdout test set
5. Deploy if mAP improved by > 2%
6. Update version (v1 → v2 → v3...)
```

### Continuous Improvement

**Data Quality:**
- Filter low-quality images (blurry, dark)
- Remove duplicate samples
- Balance class distribution (under-sampled ingredients)

**Model Architecture:**
- Start: YOLOv8n (nano - 3.2M params)
- Month 4: YOLOv8s (small - 11M params) for better accuracy
- Month 6: YOLOv8m (medium - 25M params) if needed

**Augmentation:**
- Expand data augmentation (rotation, brightness, contrast)
- Add hard negative mining (common failure cases)
- Synthetic data generation (if needed)

### Success Metrics (6-Month Goals)

| Metric | Month 3 | Month 6 | Target |
|--------|---------|---------|--------|
| **Model mAP@0.5** | 0.75 | 0.85 | > 0.85 |
| **Training samples** | 50K | 200K | 100K+ |
| **Unique ingredients** | 50 | 150 | 100+ |
| **Cost per scan** | $0.50 | $0.01 | < $0.10 |
| **Monthly retraining** | Manual | Automated | Automated |

---

## 📦 Storage & Infrastructure

### CloudFlare R2 Setup (Recommended for Production)

```bash
# 1. Create R2 bucket
# dashboard.cloudflare.com → R2 → Create bucket: "savo-training-data"

# 2. Add to render.yaml env vars:
R2_ACCOUNT_ID=<your-account-id>
R2_ACCESS_KEY_ID=<access-key>
R2_SECRET_ACCESS_KEY=<secret-key>
R2_BUCKET_NAME=savo-training-data

# 3. Update training route to upload to R2
# See: services/api/app/api/routes/training.py
```

### Storage Costs

| Provider | Storage | Bandwidth | Cost (100GB, 1TB transfer) |
|----------|---------|-----------|---------------------------|
| **Render Disk** | $1/GB/mo | Free egress | $100/mo |
| **CloudFlare R2** | $0.015/GB/mo | Free egress | $1.50/mo |
| **AWS S3** | $0.023/GB/mo | $0.09/GB out | $92.30/mo |

**Recommendation:** Use CloudFlare R2 for production training data storage.

---

## 🎯 Week 1 Action Items

### Day 1 (Today): Deploy
- [ ] Set environment variables in Render dashboard
- [ ] Deploy latest commit to production
- [ ] Verify training endpoints work: `/training/stats`
- [ ] Test upload: POST `/training/upload-image` with test image

### Day 2: Monitor
- [ ] Check `/training/stats` in morning and evening
- [ ] Verify data collection from real users
- [ ] Monitor Render logs for errors

### Day 3-7: Iterate
- [ ] Track daily sample collection rate
- [ ] Adjust SAVO_COLLECT_TRAINING_DATA based on storage
- [ ] Document any issues or edge cases
- [ ] Prepare for Month 2 training once 10K samples reached

---

## 🚨 Troubleshooting

### No Data Being Collected

```bash
# Check environment variable
curl https://savo-ynp1.onrender.com/training/stats

# Verify in Render logs:
SAVO_COLLECT_TRAINING_DATA=true

# Check if users are scanning ingredients
# (data only collected when users confirm/correct scans)
```

### Storage Full

```bash
# Check storage usage
du -sh /opt/render/project/src/services/api/training_data

# Solution: Migrate to CloudFlare R2 (see above)
# Or: Upgrade Render plan (free tier = 512MB disk)
```

### Training Too Slow

```bash
# Use cloud GPU instead of local training
# Paperspace: $0.50/hour (P4000 GPU)
# Google Colab Pro: $10/month (V100 GPU)
# Lambda Labs: $0.60/hour (A6000 GPU)
```

---

## 📞 Next Steps

**RIGHT NOW:**
1. Deploy to Render (see Step 1 above)
2. Open https://savo-ynp1.onrender.com/training/stats in browser
3. Share with users to start collecting data

**THIS WEEK:**
- Monitor data collection daily
- Target: 100 samples by end of week

**MONTH 1:**
- Reach 10K samples
- Prepare for first training run

**MONTH 2:**
- Train YOLO v8 prototype
- Achieve mAP@0.5 > 0.75

**MONTH 3:**
- Deploy custom model with A/B testing
- Achieve 99% cost reduction

---

## 🎉 Success!

Once deployed, every ingredient scan by your users will automatically contribute to your training data. The data moat starts building immediately.

**You now have:**
- ✅ Training data collection infrastructure
- ✅ Automatic labeling from user corrections
- ✅ Clear path to custom vision model
- ✅ 99% cost reduction roadmap
- ✅ Defensible competitive advantage

**Deploy now and watch your training data grow!**
