"""Inventory models.

Includes:
- E2 inventory management
- ingredient scan (pantry/fridge) candidates
"""
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from datetime import datetime


class InventoryItemBase(BaseModel):
    """Base inventory item fields"""
    canonical_name: str = Field(..., description="Canonical ingredient name")
    display_name: Optional[str] = Field(None, description="User-friendly display name")
    quantity: float = Field(..., ge=0, description="Quantity available")
    unit: str = Field(..., description="Unit of measurement (g, kg, pcs, cups, etc.)")
    state: Literal["raw", "cooked", "leftover", "frozen"] = Field(default="raw")
    storage: Literal["pantry", "refrigerator", "freezer"] = Field(default="pantry")
    freshness_days_remaining: Optional[int] = Field(None, ge=0, description="Days until expiry")
    added_date: Optional[datetime] = Field(None, description="When item was added")
    notes: Optional[str] = Field(None, description="User notes")


class InventoryItem(InventoryItemBase):
    """Complete inventory item with ID"""
    inventory_id: str = Field(..., description="Unique inventory item ID")


class InventoryItemCreate(InventoryItemBase):
    """Request model for creating inventory items"""
    pass


class InventoryItemUpdate(BaseModel):
    """Request model for updating inventory items (all fields optional)"""
    canonical_name: Optional[str] = None
    display_name: Optional[str] = None
    quantity: Optional[float] = Field(None, ge=0)
    unit: Optional[str] = None
    state: Optional[Literal["raw", "cooked", "leftover", "frozen"]] = None
    storage: Optional[Literal["pantry", "refrigerator", "freezer"]] = None
    freshness_days_remaining: Optional[int] = Field(None, ge=0)
    notes: Optional[str] = None


class NormalizeInventoryRequest(BaseModel):
    """Request to normalize raw inventory input"""
    raw_items: List[dict] = Field(..., description="Raw inventory items to normalize")
    measurement_system: Literal["metric", "imperial"] = Field(default="metric")
    output_language: str = Field(default="en", pattern="^[a-z]{2}(-[A-Z]{2})?$")


class StaplesPolicyApplied(BaseModel):
    """Staples policy information"""
    enabled: bool
    staples_included: List[str] = Field(default_factory=list)
    staples_excluded: List[str] = Field(default_factory=list)


class NormalizedInventoryItem(BaseModel):
    """Normalized inventory item from LLM"""
    inventory_id: str
    canonical_ingredient_id: str
    canonical_name: str
    display_name: str
    quantity: float
    unit: str
    state: Literal["raw", "cooked", "leftover", "frozen"]
    storage: Literal["pantry", "refrigerator", "freezer"]
    freshness_days_remaining: int
    confidence: float = Field(ge=0.0, le=1.0)


class NormalizeInventoryResponse(BaseModel):
    """Response from inventory normalization (NORMALIZATION_OUTPUT_SCHEMA)"""
    normalized_inventory: List[NormalizedInventoryItem]
    staples_policy_applied: StaplesPolicyApplied


class ScannedIngredientCandidate(BaseModel):
    """Single ingredient candidate detected from an image."""

    ingredient: str = Field(..., description="Detected ingredient name")
    quantity_estimate: Optional[str] = Field(
        None, description="Rough quantity estimate, as a user-editable string"
    )
    confidence: float = Field(..., ge=0.0, le=1.0, description="Detection confidence")
    storage_hint: Optional[Literal["pantry", "refrigerator", "freezer"]] = Field(
        None, description="Optional storage hint based on context"
    )


class ScanIngredientsResponse(BaseModel):
    """Response from ingredient scanning."""

    status: Literal["ok", "error"] = "ok"
    scanned_items: List[ScannedIngredientCandidate] = Field(default_factory=list)
    error_message: Optional[str] = None
