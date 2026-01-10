from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user
from app.core.quantity_estimator import BoundingBox, QuantityEstimator, ReferenceObject

router = APIRouter(prefix="/quantity", tags=["quantity"])


class BBoxIn(BaseModel):
    x_min: float
    y_min: float
    x_max: float
    y_max: float
    image_width: int
    image_height: int


class ReferenceObjectIn(BaseModel):
    object_type: str
    bbox: BBoxIn
    avg_real_size_cm: float
    confidence: float = 0.85


class QuantityEstimateIn(BaseModel):
    bbox: BBoxIn
    reference_objects: List[ReferenceObjectIn] = Field(default_factory=list)
    container_type: Optional[str] = None
    fill_level: Optional[float] = Field(default=100.0, ge=0.0, le=100.0)

    # Optional density conversion
    density_g_per_ml: Optional[float] = None
    density_confidence: float = 0.80


@router.post("/estimate")
async def quantity_estimate(
    payload: QuantityEstimateIn,
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Story wrapper: POST /quantity/estimate.

    Supports container inference + fill level (via QuantityEstimator) and optional
    density conversion from volume -> mass.
    """
    _ = user_id  # reserved for future per-user density tables

    bbox_in = payload.bbox
    bbox = BoundingBox(
        x_min=bbox_in.x_min,
        y_min=bbox_in.y_min,
        x_max=bbox_in.x_max,
        y_max=bbox_in.y_max,
        image_width=bbox_in.image_width,
        image_height=bbox_in.image_height,
    )

    refs: List[ReferenceObject] = []
    for r in payload.reference_objects or []:
        rb = r.bbox
        refs.append(
            ReferenceObject(
                object_type=r.object_type,
                bbox=BoundingBox(
                    x_min=rb.x_min,
                    y_min=rb.y_min,
                    x_max=rb.x_max,
                    y_max=rb.y_max,
                    image_width=rb.image_width,
                    image_height=rb.image_height,
                ),
                avg_real_size_cm=r.avg_real_size_cm,
                confidence=r.confidence,
            )
        )

    estimator = QuantityEstimator()
    estimate = estimator.estimate_from_bbox_and_reference(
        ingredient_bbox=bbox,
        reference_objects=refs,
        container_type=payload.container_type,
        fill_percentage=float(payload.fill_level or 100.0),
    )

    out: Dict[str, Any] = {
        "success": True,
        "quantity": estimate.estimated_value,
        "unit": estimate.unit,
        "confidence": estimate.confidence,
        "method": estimate.method,
        "details": estimate.details,
    }

    if payload.density_g_per_ml is not None and estimate.unit == "ml":
        w = estimator.convert_volume_to_weight(
            volume_ml=float(estimate.estimated_value),
            density_g_per_ml=float(payload.density_g_per_ml),
            density_confidence=float(payload.density_confidence or 0.80),
        )
        out["converted"] = {
            "quantity": w.estimated_value,
            "unit": w.unit,
            "confidence": w.confidence,
            "method": w.method,
            "details": w.details,
        }

    return out
