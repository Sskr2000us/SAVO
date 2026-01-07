"""
Quantity Estimation Model
Uses bounding box analysis, reference objects, and density lookup to estimate ingredient quantities
"""
import logging
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass
import math

logger = logging.getLogger(__name__)


@dataclass
class BoundingBox:
    """Represents a bounding box in pixel coordinates"""
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    image_width: int
    image_height: int
    
    @property
    def width(self) -> float:
        return self.x_max - self.x_min
    
    @property
    def height(self) -> float:
        return self.y_max - self.y_min
    
    @property
    def area_pixels(self) -> float:
        return self.width * self.height
    
    @property
    def aspect_ratio(self) -> float:
        return self.width / self.height if self.height > 0 else 1.0


@dataclass
class ReferenceObject:
    """Reference object for size calibration"""
    object_type: str  # hand, coin, credit_card, spoon, etc.
    bbox: BoundingBox
    avg_real_size_cm: float  # Average real-world size in cm
    confidence: float = 0.85


@dataclass
class QuantityEstimate:
    """Result of quantity estimation"""
    estimated_value: float
    unit: str
    confidence: float
    method: str  # bbox_volume, reference_object, ml_model, container_standard
    details: Dict[str, Any]


class QuantityEstimator:
    """Estimate ingredient quantities from images"""
    
    # Standard reference object sizes (in cm)
    REFERENCE_SIZES = {
        "hand": {"length_cm": 18.0, "width_cm": 9.0, "confidence": 0.75},
        "adult_hand": {"length_cm": 18.5, "width_cm": 9.5, "confidence": 0.75},
        "coin": {"diameter_cm": 2.5, "confidence": 0.90},  # Generic coin
        "quarter": {"diameter_cm": 2.426, "confidence": 0.95},  # US Quarter
        "rupee_coin": {"diameter_cm": 2.5, "confidence": 0.95},  # 5 Rupee coin
        "credit_card": {"length_cm": 8.56, "width_cm": 5.398, "confidence": 0.98},
        "phone": {"length_cm": 15.0, "width_cm": 7.0, "confidence": 0.70},
        "spoon": {"length_cm": 15.0, "confidence": 0.65},
        "fork": {"length_cm": 18.0, "confidence": 0.65},
    }
    
    # Standard container sizes (in ml)
    STANDARD_CONTAINERS = {
        "mason_jar": [250, 500, 1000],
        "glass_jar": [200, 500, 750, 1000],
        "plastic_container": [500, 1000, 1500, 2000],
        "spice_jar": [50, 100, 150],
        "bottle": [500, 750, 1000],
        "bowl": [250, 500, 1000],
    }
    
    def __init__(self):
        pass
    
    def estimate_from_bbox_and_reference(
        self,
        ingredient_bbox: BoundingBox,
        reference_objects: List[ReferenceObject],
        container_type: Optional[str] = None,
        fill_percentage: float = 100.0
    ) -> QuantityEstimate:
        """
        Estimate quantity using bounding box and reference objects
        
        Args:
            ingredient_bbox: Bounding box of the ingredient
            reference_objects: Detected reference objects for scale
            container_type: Type of container (if any)
            fill_percentage: Estimated fill level (0-100)
        """
        if not reference_objects:
            return self._estimate_from_bbox_only(ingredient_bbox, container_type, fill_percentage)
        
        # Use the most confident reference object
        best_ref = max(reference_objects, key=lambda r: r.confidence)
        
        # Calculate scale factor (pixels per cm)
        scale_factor = self._calculate_scale_factor(best_ref)
        
        # Estimate real-world dimensions
        width_cm = ingredient_bbox.width / scale_factor
        height_cm = ingredient_bbox.height / scale_factor
        
        # Estimate depth (heuristic based on aspect ratio and container type)
        depth_cm = self._estimate_depth(width_cm, height_cm, container_type)
        
        # Calculate volume
        volume_ml = width_cm * height_cm * depth_cm * (fill_percentage / 100.0)
        
        confidence = best_ref.confidence * 0.9  # Slightly reduce confidence for estimation
        
        return QuantityEstimate(
            estimated_value=round(volume_ml, 1),
            unit="ml",
            confidence=confidence,
            method="reference_object",
            details={
                "reference_object": best_ref.object_type,
                "scale_factor": scale_factor,
                "dimensions_cm": {
                    "width": round(width_cm, 2),
                    "height": round(height_cm, 2),
                    "depth": round(depth_cm, 2),
                },
                "fill_percentage": fill_percentage,
                "container_type": container_type,
            }
        )
    
    def _calculate_scale_factor(self, reference: ReferenceObject) -> float:
        """
        Calculate pixels per cm using reference object
        
        Returns:
            Scale factor (pixels/cm)
        """
        ref_info = self.REFERENCE_SIZES.get(reference.object_type, {})
        
        if "length_cm" in ref_info:
            # Use the longer dimension
            ref_length_cm = ref_info["length_cm"]
            ref_length_pixels = max(reference.bbox.width, reference.bbox.height)
            return ref_length_pixels / ref_length_cm
        elif "diameter_cm" in ref_info:
            # For circular objects, use average of width and height
            ref_diameter_cm = ref_info["diameter_cm"]
            ref_diameter_pixels = (reference.bbox.width + reference.bbox.height) / 2
            return ref_diameter_pixels / ref_diameter_cm
        else:
            # Fallback: assume 1cm = 30 pixels (rough estimate)
            return 30.0
    
    def _estimate_depth(
        self, 
        width_cm: float, 
        height_cm: float, 
        container_type: Optional[str]
    ) -> float:
        """
        Estimate depth from 2D measurements
        
        This is a heuristic - ideally would use ML model trained on depth data
        """
        if container_type == "plate" or container_type == "bowl":
            # Shallow containers
            return min(width_cm, height_cm) * 0.3
        elif container_type in ["jar", "glass_jar", "mason_jar"]:
            # Jars are typically as deep as they are wide
            return width_cm * 0.9
        elif container_type == "bottle":
            # Bottles are typically narrower than they are tall
            return min(width_cm, height_cm) * 0.7
        elif container_type == "plastic_container":
            # Square containers
            return width_cm * 0.8
        else:
            # Generic estimate: depth = geometric mean of width and height
            return math.sqrt(width_cm * height_cm) * 0.7
    
    def _estimate_from_bbox_only(
        self,
        ingredient_bbox: BoundingBox,
        container_type: Optional[str],
        fill_percentage: float
    ) -> QuantityEstimate:
        """
        Estimate quantity without reference objects
        Uses standard container sizes and image heuristics
        """
        # Assume average image resolution and typical object distances
        # This is very rough - confidence will be low
        
        if container_type in self.STANDARD_CONTAINERS:
            # Use typical container size
            standard_sizes = self.STANDARD_CONTAINERS[container_type]
            
            # Pick size based on bbox area
            bbox_area_ratio = ingredient_bbox.area_pixels / (
                ingredient_bbox.image_width * ingredient_bbox.image_height
            )
            
            if bbox_area_ratio < 0.1:
                volume_ml = standard_sizes[0]
            elif bbox_area_ratio < 0.3:
                volume_ml = standard_sizes[min(1, len(standard_sizes) - 1)]
            else:
                volume_ml = standard_sizes[-1]
            
            volume_ml *= (fill_percentage / 100.0)
            
            return QuantityEstimate(
                estimated_value=round(volume_ml, 1),
                unit="ml",
                confidence=0.50,  # Low confidence without reference
                method="container_standard",
                details={
                    "container_type": container_type,
                    "bbox_area_ratio": round(bbox_area_ratio, 3),
                    "fill_percentage": fill_percentage,
                }
            )
        else:
            # Very rough estimate based on bbox area
            # Assume camera at ~50cm distance, typical ingredient
            estimated_volume = ingredient_bbox.area_pixels * 0.01 * (fill_percentage / 100.0)
            
            return QuantityEstimate(
                estimated_value=round(estimated_volume, 1),
                unit="ml",
                confidence=0.30,  # Very low confidence
                method="bbox_area_heuristic",
                details={
                    "bbox_area_pixels": ingredient_bbox.area_pixels,
                    "note": "Low confidence - no reference objects detected",
                }
            )
    
    def convert_volume_to_weight(
        self,
        volume_ml: float,
        density_g_per_ml: float,
        density_confidence: float = 0.80
    ) -> QuantityEstimate:
        """
        Convert volume estimate to weight using density
        
        Args:
            volume_ml: Estimated volume in ml
            density_g_per_ml: Ingredient density
            density_confidence: Confidence in the density value
        """
        weight_g = volume_ml * density_g_per_ml
        
        return QuantityEstimate(
            estimated_value=round(weight_g, 1),
            unit="g",
            confidence=density_confidence,
            method="volume_to_weight",
            details={
                "volume_ml": volume_ml,
                "density_g_per_ml": density_g_per_ml,
            }
        )
    
    def detect_reference_objects_from_vision(
        self,
        vision_result: Dict[str, Any],
        image_width: int,
        image_height: int
    ) -> List[ReferenceObject]:
        """
        Extract reference objects from GPT-4o Vision detection results
        
        Args:
            vision_result: Detection results with reference_objects field
            image_width: Image width in pixels
            image_height: Image height in pixels
        """
        reference_objects = []
        
        detected_refs = vision_result.get("reference_objects", [])
        
        for ref in detected_refs:
            obj_type = ref.get("type", "").lower()
            bbox_data = ref.get("bbox")
            
            if not bbox_data or obj_type not in self.REFERENCE_SIZES:
                continue
            
            bbox = BoundingBox(
                x_min=bbox_data.get("x_min", 0),
                y_min=bbox_data.get("y_min", 0),
                x_max=bbox_data.get("x_max", image_width),
                y_max=bbox_data.get("y_max", image_height),
                image_width=image_width,
                image_height=image_height,
            )
            
            ref_info = self.REFERENCE_SIZES[obj_type]
            avg_size = ref_info.get("length_cm") or ref_info.get("diameter_cm", 10.0)
            
            reference_objects.append(ReferenceObject(
                object_type=obj_type,
                bbox=bbox,
                avg_real_size_cm=avg_size,
                confidence=ref_info.get("confidence", 0.70)
            ))
        
        return reference_objects
    
    def estimate_container_fill_percentage(
        self,
        ingredient_bbox: BoundingBox,
        container_bbox: Optional[BoundingBox] = None,
        visual_cues: Optional[Dict[str, Any]] = None
    ) -> float:
        """
        Estimate how full a container is
        
        Returns:
            Fill percentage (0-100)
        """
        if container_bbox:
            # Calculate ratio of ingredient height to container height
            fill_ratio = ingredient_bbox.height / container_bbox.height
            return min(fill_ratio * 100, 100)
        
        # Use visual cues if available
        if visual_cues and "fill_level" in visual_cues:
            return visual_cues["fill_level"]
        
        # Default assumption: container is 75% full
        return 75.0
