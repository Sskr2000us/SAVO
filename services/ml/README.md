# SAVO ML Infrastructure

This directory contains machine learning infrastructure for Phase 2: Custom Vision Model

## Structure

```
ml/
├── README.md           # This file
├── requirements.txt    # ML-specific dependencies
├── train.py           # Training script for YOLO v8
├── evaluate.py        # Model evaluation and metrics
├── export.py          # Model export (ONNX, TorchScript)
├── data/              # Training data utilities
│   ├── prepare.py     # Data preparation scripts
│   └── augment.py     # Data augmentation
└── models/            # Trained models storage
    └── .gitkeep
```

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Prepare Training Data

```bash
python data/prepare.py \
  --input ../api/training_data \
  --output ./datasets/savo_v1 \
  --split 0.8
```

### 3. Train Model

```bash
python train.py \
  --data ./datasets/savo_v1/dataset.yaml \
  --epochs 100 \
  --batch 16 \
  --imgsz 640
```

### 4. Evaluate

```bash
python evaluate.py \
  --model ./runs/train/exp/weights/best.pt \
  --data ./datasets/savo_v1/dataset.yaml
```

### 5. Export for Production

```bash
python export.py \
  --model ./runs/train/exp/weights/best.pt \
  --format onnx \
  --output ./models/savo_yolo_v8.onnx
```

## Training Data Format

Expected format from `/api/training_data`:

```
training_data/
├── images/
│   └── 2025-12/
│       ├── abc123.jpg
│       └── def456.jpg
└── labels/
    └── 2025-12/
        ├── abc123.json
        └── def456.json
```

Label JSON format:
```json
{
  "scan_id": "...",
  "image_hash": "abc123",
  "image_width": 1920,
  "image_height": 1080,
  "annotations": [
    {
      "class": "tomato",
      "confidence": 0.91,
      "bbox": {"x": 100, "y": 200, "width": 150, "height": 150}
    }
  ]
}
```

## Model Requirements

### Minimum Training Data
- **10K images** for prototype
- **50K images** for production
- **100+ ingredient classes** for comprehensive coverage

### Performance Targets
- **mAP@0.5** > 0.75 (75% accuracy)
- **Inference time** < 100ms (CPU)
- **Model size** < 50MB (mobile deployment)

## Training Infrastructure

### Local Development
- Google Colab Pro ($10/month)
- Free GPU for training
- Suitable for experimentation

### Production Training
- Lambda Labs ($0.50/hour for RTX 3090)
- AWS SageMaker ($3/hour for p3.2xlarge)
- Training time: ~15-20 hours for 50K images

## Deployment

Trained models are deployed to:
1. `../api/models/` - For API inference
2. CloudFlare R2 / S3 - For versioning
3. Mobile apps - For edge deployment (future)

## Monitoring

Track model performance:
- Training metrics in Weights & Biases
- Production metrics via `/training/stats`
- User correction rates in API logs

## Resources

- [YOLO v8 Documentation](https://docs.ultralytics.com/)
- [Roboflow Tutorials](https://blog.roboflow.com/)
- [Phase 2 Roadmap](../docs/VISION_MODEL_ROADMAP.md)
