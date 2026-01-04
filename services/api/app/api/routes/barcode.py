"""Barcode lookup endpoints.

Goal: provide a high-precision path for packaged goods by resolving UPC/EAN
into a product name, image, and pack size when available.

We still keep a human-in-the-loop confirmation step on the client because no
single mechanism is truly 100% foolproof across all food types (e.g. loose
produce, leftovers).
"""

from __future__ import annotations

import re
from typing import Any, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.middleware.auth import get_current_user

router = APIRouter()


class BarcodeLookupResponse(BaseModel):
    success: bool
    barcode: str

    product_name: Optional[str] = None
    brand: Optional[str] = None
    image_url: Optional[str] = None

    # e.g. "500 g" or "1 L" (raw text from the product DB)
    package_size_text: Optional[str] = None

    # Best-effort parsed package size
    package_quantity: Optional[float] = Field(default=None, ge=0)
    package_unit: Optional[str] = None

    source: str = "openfoodfacts"


_QUANTITY_RE = re.compile(
    r"(?P<qty>\d+(?:[\.,]\d+)?)\s*(?P<unit>kg|g|mg|l|ml|oz|lb|lbs)\b",
    flags=re.IGNORECASE,
)


def _parse_package_size(text: Optional[str]) -> tuple[Optional[float], Optional[str]]:
    if not text:
        return None, None
    m = _QUANTITY_RE.search(text)
    if not m:
        return None, None

    raw_qty = (m.group("qty") or "").replace(",", ".").strip()
    try:
        qty = float(raw_qty)
    except Exception:
        return None, None

    unit = (m.group("unit") or "").strip().lower()
    if unit == "lbs":
        unit = "lb"
    if unit == "l":
        unit = "liters"
    if unit == "ml":
        unit = "ml"
    if unit == "g":
        unit = "grams"
    if unit == "kg":
        unit = "kg"
    if unit == "mg":
        unit = "mg"

    return qty, unit


@router.get("/lookup/{barcode}", response_model=BarcodeLookupResponse)
async def lookup_barcode(
    barcode: str,
    _user_id: str = Depends(get_current_user),
):
    """Resolve a UPC/EAN barcode to product metadata.

    Uses Open Food Facts as a free global product DB.
    """

    b = (barcode or "").strip()
    if not b:
        raise HTTPException(status_code=400, detail="Barcode is required")

    # Keep digits only; many scanners include formatting.
    digits = re.sub(r"\D", "", b)
    if len(digits) < 8:
        raise HTTPException(status_code=400, detail="Barcode looks invalid")

    url = f"https://world.openfoodfacts.org/api/v2/product/{digits}.json"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Barcode lookup failed: {e}")

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Barcode lookup failed")

    data: dict[str, Any]
    try:
        data = resp.json()
    except Exception:
        raise HTTPException(status_code=502, detail="Barcode lookup returned invalid JSON")

    product = data.get("product") or {}
    if not isinstance(product, dict) or not product:
        return BarcodeLookupResponse(success=False, barcode=digits)

    product_name = (
        product.get("product_name")
        or product.get("product_name_en")
        or product.get("generic_name")
    )
    if isinstance(product_name, str):
        product_name = product_name.strip() or None
    else:
        product_name = None

    brand = product.get("brands")
    if isinstance(brand, str):
        # Often a comma-separated list.
        brand = brand.split(",")[0].strip() or None
    else:
        brand = None

    image_url = product.get("image_url")
    if isinstance(image_url, str):
        image_url = image_url.strip() or None
    else:
        image_url = None

    package_text = product.get("quantity")
    if isinstance(package_text, str):
        package_text = package_text.strip() or None
    else:
        package_text = None

    pkg_qty, pkg_unit = _parse_package_size(package_text)

    return BarcodeLookupResponse(
        success=True,
        barcode=digits,
        product_name=product_name,
        brand=brand,
        image_url=image_url,
        package_size_text=package_text,
        package_quantity=pkg_qty,
        package_unit=pkg_unit,
    )
