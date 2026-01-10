from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, Header, UploadFile

from app.middleware.auth import get_current_user
from app.api.routes.scanning import analyze_image

router = APIRouter(prefix="/vision", tags=["vision"])


@router.post("/detect")
async def vision_detect(
    image: UploadFile = File(..., description="Image file (JPEG/PNG)"),
    scan_type: str = Form(default="pantry"),
    location_hint: Optional[str] = Form(default=None),
    session_id: Optional[str] = Form(default=None),
    barcode: Optional[str] = Form(default=None),
    barcode_name_hint: Optional[str] = Form(default=None),
    barcode_quantity_hint: Optional[float] = Form(default=None),
    barcode_unit_hint: Optional[str] = Form(default=None),
    x_app_version: Optional[str] = Header(default=None, alias="X-App-Version"),
    user_id: str = Depends(get_current_user),
) -> Dict[str, Any]:
    """Story wrapper: POST /vision/detect.

    Delegates to the existing scan analyzer for detection + normalization,
    then adapts the response to the story shape.
    """
    result = await analyze_image(
        image=image,
        scan_type=scan_type,
        location_hint=location_hint,
        session_id=session_id,
        barcode=barcode,
        barcode_name_hint=barcode_name_hint,
        barcode_quantity_hint=barcode_quantity_hint,
        barcode_unit_hint=barcode_unit_hint,
        x_app_version=x_app_version,
        user_id=user_id,
    )

    items: List[Dict[str, Any]] = []
    for ing in getattr(result, "ingredients", []) or []:
        bbox = getattr(ing, "bbox", None)
        conf = getattr(ing, "confidence", None)
        if isinstance(conf, Decimal):
            conf_val = float(conf)
        else:
            conf_val = float(conf) if conf is not None else None

        items.append(
            {
                "ingredient": getattr(ing, "canonical_name", None) or getattr(ing, "detected_name", None),
                "brand": None,
                "confidence": conf_val,
                "bounding_box": bbox,
                "raw_label": getattr(ing, "detected_name", None),
                "canonical_ingredient": getattr(ing, "canonical_name", None),
                "quantity": getattr(ing, "quantity", None),
                "unit": getattr(ing, "unit", None),
                "quantity_confidence": getattr(ing, "quantity_confidence", None),
                "quantity_method": getattr(ing, "quantity_source", None),
            }
        )

    return {
        "success": True,
        "scan_id": getattr(result, "scan_id", None),
        "session_id": session_id,
        "items": items,
        "metadata": getattr(result, "metadata", None),
    }
