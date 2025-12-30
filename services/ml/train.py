"""
YOLO v8 Training Script for SAVO Ingredient Detection
Phase 2: Custom Vision Model

Usage:
    python train.py --data ./datasets/savo_v1/dataset.yaml --epochs 100
"""
import argparse
from pathlib import Path
from ultralytics import YOLO
import torch


def train_savo_model(
    data_yaml: Path,
    model_name: str = "yolov8n.pt",
    epochs: int = 100,
    batch_size: int = 16,
    img_size: int = 640,
    device: str = "0",
    project: str = "runs/train",
    name: str = "savo_v1"
):
    """
    Train YOLO v8 model on SAVO ingredient data
    
    Args:
        data_yaml: Path to dataset YAML file
        model_name: Base model (yolov8n, yolov8s, yolov8m, yolov8l, yolov8x)
        epochs: Number of training epochs
        batch_size: Batch size for training
        img_size: Input image size
        device: GPU device (0, 1, 2, etc.) or 'cpu'
        project: Project directory
        name: Experiment name
    
    Returns:
        Path to best model weights
    """
    print(f"🚀 Starting SAVO Vision Model Training")
    print(f"   Model: {model_name}")
    print(f"   Data: {data_yaml}")
    print(f"   Epochs: {epochs}")
    print(f"   Batch Size: {batch_size}")
    print(f"   Device: {device}")
    print()
    
    # Check GPU availability
    if device != "cpu" and not torch.cuda.is_available():
        print("⚠️  GPU not available, falling back to CPU")
        device = "cpu"
    
    # Load base model
    model = YOLO(model_name)
    
    # Train
    results = model.train(
        data=str(data_yaml),
        epochs=epochs,
        imgsz=img_size,
        batch=batch_size,
        device=device,
        project=project,
        name=name,
        
        # Optimization settings
        optimizer="AdamW",
        lr0=0.001,
        lrf=0.01,
        momentum=0.9,
        weight_decay=0.0005,
        
        # Augmentation
        hsv_h=0.015,
        hsv_s=0.7,
        hsv_v=0.4,
        degrees=10.0,
        translate=0.1,
        scale=0.5,
        shear=0.0,
        perspective=0.0,
        flipud=0.0,
        fliplr=0.5,
        mosaic=1.0,
        mixup=0.0,
        
        # Early stopping
        patience=20,
        
        # Saving
        save=True,
        save_period=10,
        
        # Validation
        val=True,
        
        # Plots
        plots=True,
        
        # Logging
        verbose=True
    )
    
    # Get best model path
    best_model_path = Path(project) / name / "weights" / "best.pt"
    
    print()
    print(f"✅ Training complete!")
    print(f"   Best model: {best_model_path}")
    print(f"   mAP@0.5: {results.box.map50:.3f}")
    print(f"   mAP@0.5:0.95: {results.box.map:.3f}")
    print()
    
    return best_model_path


def main():
    parser = argparse.ArgumentParser(description="Train SAVO YOLO v8 model")
    
    parser.add_argument(
        "--data",
        type=str,
        required=True,
        help="Path to dataset YAML file"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8n.pt",
        choices=["yolov8n.pt", "yolov8s.pt", "yolov8m.pt", "yolov8l.pt", "yolov8x.pt"],
        help="Base model to start from (n=nano, s=small, m=medium, l=large, x=xlarge)"
    )
    
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="Number of training epochs"
    )
    
    parser.add_argument(
        "--batch",
        type=int,
        default=16,
        help="Batch size"
    )
    
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="Input image size"
    )
    
    parser.add_argument(
        "--device",
        type=str,
        default="0",
        help="GPU device (0, 1, 2, etc.) or 'cpu'"
    )
    
    parser.add_argument(
        "--project",
        type=str,
        default="runs/train",
        help="Project directory"
    )
    
    parser.add_argument(
        "--name",
        type=str,
        default="savo_v1",
        help="Experiment name"
    )
    
    args = parser.parse_args()
    
    # Train model
    best_model = train_savo_model(
        data_yaml=Path(args.data),
        model_name=args.model,
        epochs=args.epochs,
        batch_size=args.batch,
        img_size=args.imgsz,
        device=args.device,
        project=args.project,
        name=args.name
    )
    
    print(f"🎉 Model ready for deployment: {best_model}")
    print()
    print("Next steps:")
    print(f"  1. Evaluate: python evaluate.py --model {best_model} --data {args.data}")
    print(f"  2. Export: python export.py --model {best_model} --format onnx")
    print(f"  3. Deploy to API: cp {best_model} ../api/models/savo_yolo_v8.pt")


if __name__ == "__main__":
    main()
