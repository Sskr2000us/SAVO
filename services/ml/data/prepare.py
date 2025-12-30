"""
Data preparation script for SAVO training data
Converts API training_data format to YOLO format

Usage:
    python data/prepare.py \
        --input ../api/training_data \
        --output ./datasets/savo_v1 \
        --split 0.8
"""
import argparse
import json
import shutil
from pathlib import Path
from typing import Dict, List, Tuple
import random


def convert_to_yolo_format(
    label_data: Dict,
    class_names: List[str]
) -> List[str]:
    """
    Convert SAVO label format to YOLO format
    
    YOLO format: <class_id> <x_center> <y_center> <width> <height>
    All values normalized to [0, 1]
    """
    yolo_lines = []
    
    img_width = label_data["image_width"]
    img_height = label_data["image_height"]
    
    for annotation in label_data.get("annotations", []):
        ingredient = annotation["class"]
        
        # Get class ID
        if ingredient not in class_names:
            class_names.append(ingredient)
        class_id = class_names.index(ingredient)
        
        # Get bounding box
        bbox = annotation.get("bbox")
        if not bbox:
            continue
        
        # Convert to YOLO format (normalized center coordinates + dimensions)
        x = bbox["x"]
        y = bbox["y"]
        w = bbox["width"]
        h = bbox["height"]
        
        x_center = (x + w / 2) / img_width
        y_center = (y + h / 2) / img_height
        width_norm = w / img_width
        height_norm = h / img_height
        
        yolo_line = f"{class_id} {x_center:.6f} {y_center:.6f} {width_norm:.6f} {height_norm:.6f}"
        yolo_lines.append(yolo_line)
    
    return yolo_lines


def prepare_dataset(
    input_dir: Path,
    output_dir: Path,
    train_split: float = 0.8,
    val_split: float = 0.1,
    min_labels_per_image: int = 1
):
    """
    Prepare YOLO dataset from SAVO training data
    
    Args:
        input_dir: Path to training_data directory
        output_dir: Path to output YOLO dataset
        train_split: Fraction for training set
        val_split: Fraction for validation set (rest is test)
        min_labels_per_image: Minimum labels required per image
    """
    print(f"📦 Preparing SOLO dataset")
    print(f"   Input: {input_dir}")
    print(f"   Output: {output_dir}")
    print(f"   Train split: {train_split:.1%}")
    print(f"   Val split: {val_split:.1%}")
    print()
    
    # Create output structure
    for split in ["train", "val", "test"]:
        (output_dir / "images" / split).mkdir(parents=True, exist_ok=True)
        (output_dir / "labels" / split).mkdir(parents=True, exist_ok=True)
    
    # Collect all label files
    labels_dir = input_dir / "labels"
    label_files = list(labels_dir.rglob("*.json"))
    
    print(f"Found {len(label_files)} label files")
    
    # Track class names
    class_names = []
    
    # Process each label file
    valid_samples = []
    
    for label_file in label_files:
        with open(label_file) as f:
            label_data = json.load(f)
        
        # Skip if too few labels
        if len(label_data.get("annotations", [])) < min_labels_per_image:
            continue
        
        # Convert to YOLO format
        yolo_lines = convert_to_yolo_format(label_data, class_names)
        
        if len(yolo_lines) == 0:
            continue
        
        valid_samples.append({
            "label_file": label_file,
            "label_data": label_data,
            "yolo_lines": yolo_lines
        })
    
    print(f"Valid samples: {len(valid_samples)}")
    print(f"Unique ingredients: {len(class_names)}")
    print()
    
    # Shuffle and split
    random.shuffle(valid_samples)
    
    n_train = int(len(valid_samples) * train_split)
    n_val = int(len(valid_samples) * val_split)
    
    splits = {
        "train": valid_samples[:n_train],
        "val": valid_samples[n_train:n_train + n_val],
        "test": valid_samples[n_train + n_val:]
    }
    
    # Copy files to output directory
    images_dir = input_dir / "images"
    
    for split_name, samples in splits.items():
        print(f"Processing {split_name}: {len(samples)} samples")
        
        for sample in samples:
            image_hash = sample["label_data"]["image_hash"]
            
            # Find image file
            image_file = list(images_dir.rglob(f"{image_hash}.jpg"))
            if not image_file:
                continue
            image_file = image_file[0]
            
            # Copy image
            output_image = output_dir / "images" / split_name / f"{image_hash}.jpg"
            shutil.copy(image_file, output_image)
            
            # Write YOLO label
            output_label = output_dir / "labels" / split_name / f"{image_hash}.txt"
            with open(output_label, "w") as f:
                f.write("\n".join(sample["yolo_lines"]))
    
    # Create dataset.yaml
    yaml_content = f"""# SAVO Ingredient Detection Dataset
path: {output_dir.absolute()}
train: images/train
val: images/val
test: images/test

# Number of classes
nc: {len(class_names)}

# Class names
names: {class_names}
"""
    
    yaml_file = output_dir / "dataset.yaml"
    with open(yaml_file, "w") as f:
        f.write(yaml_content)
    
    print()
    print(f"✅ Dataset prepared successfully!")
    print(f"   Train: {len(splits['train'])} images")
    print(f"   Val: {len(splits['val'])} images")
    print(f"   Test: {len(splits['test'])} images")
    print(f"   Classes: {len(class_names)}")
    print(f"   Dataset YAML: {yaml_file}")
    print()
    print(f"Ready to train:")
    print(f"  python train.py --data {yaml_file} --epochs 100")


def main():
    parser = argparse.ArgumentParser(description="Prepare SAVO training dataset")
    
    parser.add_argument(
        "--input",
        type=str,
        required=True,
        help="Path to training_data directory from API"
    )
    
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to output YOLO dataset directory"
    )
    
    parser.add_argument(
        "--split",
        type=float,
        default=0.8,
        help="Train split ratio (default: 0.8)"
    )
    
    parser.add_argument(
        "--val-split",
        type=float,
        default=0.1,
        help="Validation split ratio (default: 0.1)"
    )
    
    parser.add_argument(
        "--min-labels",
        type=int,
        default=1,
        help="Minimum labels per image (default: 1)"
    )
    
    args = parser.parse_args()
    
    prepare_dataset(
        input_dir=Path(args.input),
        output_dir=Path(args.output),
        train_split=args.split,
        val_split=args.val_split,
        min_labels_per_image=args.min_labels
    )


if __name__ == "__main__":
    main()
