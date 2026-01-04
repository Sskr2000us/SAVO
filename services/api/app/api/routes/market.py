"""Market configuration endpoints.

Provides country/region-scoped feature flags and (optionally) retailer configuration.

Public endpoints are used by the app to decide which features to show in the UI.
Admin endpoints allow a super-admin to manage rollout by market.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from app.core.database import get_db_client, get_household_profile
from app.middleware.auth import get_current_user


router = APIRouter(prefix="/market", tags=["market"])
admin_router = APIRouter(prefix="/admin/market", tags=["admin", "market"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class RetailerConfig(BaseModel):
    name: str
    url: Optional[str] = None
    enabled: bool = True
    sort_order: int = 0


class FeatureFlagUpsert(BaseModel):
    region: str = Field(..., min_length=1, max_length=16)
    feature_key: str = Field(..., min_length=1, max_length=64)
    enabled: bool
    payload: Optional[Dict[str, Any]] = None


class RetailerUpsert(BaseModel):
    region: str = Field(..., min_length=1, max_length=16)
    name: str = Field(..., min_length=1, max_length=120)
    url: Optional[str] = None
    enabled: bool = True
    sort_order: int = 0


class MarketConfigResponse(BaseModel):
    region: str
    flags: Dict[str, bool]
    is_super_admin: bool = False
    retailers: List[RetailerConfig] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _env_list(name: str) -> List[str]:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return []
    return [x.strip() for x in raw.split(",") if x.strip()]


def _is_super_admin(user_id: str) -> bool:
    # Bootstrap option: allowlist by user id or email.
    allow_user_ids = set(_env_list("SUPER_ADMIN_USER_IDS"))
    if user_id in allow_user_ids:
        return True

    try:
        supabase = get_db_client()
        user_result = supabase.table("users").select("email,is_super_admin").eq("id", user_id).limit(1).execute()
        if user_result.data:
            row = user_result.data[0]
            if row.get("is_super_admin") is True:
                return True
            email = (row.get("email") or "").strip().lower()
            allow_emails = {e.lower() for e in _env_list("SUPER_ADMIN_EMAILS")}
            if email and email in allow_emails:
                return True
    except Exception:
        # If the column doesn't exist yet, the select may fail; fall back to env.
        allow_emails = {e.lower() for e in _env_list("SUPER_ADMIN_EMAILS")}
        if allow_emails:
            # We don't have email without DB; so just false.
            return False

    return False


def _normalize_region(region: Optional[str]) -> str:
    r = (region or "US").strip()
    return r.upper() if r else "US"


def _flags_defaults_for_region(region: str) -> Dict[str, bool]:
    # Conservative defaults: Shopping List is generally useful everywhere.
    # Shopping Cart depends on retailer integrations, so default off.
    return {
        "shopping_list": True,
        "shopping_cart": region in {"US", "CA", "GB", "UK", "AU", "NZ"},
    }


# ---------------------------------------------------------------------------
# Public endpoints
# ---------------------------------------------------------------------------


@router.get("/config", response_model=MarketConfigResponse)
async def get_market_config(user_id: str = Depends(get_current_user)):
    """Return market-scoped feature flags and retailer config for the current user."""

    household = await get_household_profile(user_id)
    region = _normalize_region((household or {}).get("region"))

    supabase = get_db_client()

    flags: Dict[str, bool] = {}
    try:
        rows = (
            supabase.table("app_feature_flags")
            .select("feature_key,enabled")
            .eq("region", region)
            .execute()
        )
        for row in (rows.data or []):
            key = str(row.get("feature_key") or "").strip()
            if not key:
                continue
            flags[key] = row.get("enabled") is True
    except Exception:
        # If table doesn't exist yet, fall back to defaults.
        flags = {}

    defaults = _flags_defaults_for_region(region)
    for k, v in defaults.items():
        flags.setdefault(k, v)

    retailers: List[RetailerConfig] = []
    try:
        rrows = (
            supabase.table("app_retailers")
            .select("name,url,enabled,sort_order")
            .eq("region", region)
            .order("sort_order")
            .execute()
        )
        for row in (rrows.data or []):
            if row.get("enabled") is False:
                continue
            retailers.append(
                RetailerConfig(
                    name=str(row.get("name") or "").strip(),
                    url=row.get("url"),
                    enabled=True,
                    sort_order=int(row.get("sort_order") or 0),
                )
            )
    except Exception:
        retailers = []

    return MarketConfigResponse(
        region=region,
        flags=flags,
        retailers=retailers,
        is_super_admin=_is_super_admin(user_id),
    )


# ---------------------------------------------------------------------------
# Admin endpoints
# ---------------------------------------------------------------------------


@admin_router.get("/feature-flags")
async def admin_list_feature_flags(
    region: Optional[str] = None,
    user_id: str = Depends(get_current_user),
):
    if not _is_super_admin(user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    supabase = get_db_client()
    query = supabase.table("app_feature_flags").select("region,feature_key,enabled,payload,updated_at")
    if region:
        query = query.eq("region", _normalize_region(region))

    result = query.order("region").order("feature_key").execute()
    return {"success": True, "flags": result.data or []}


@admin_router.put("/feature-flags")
async def admin_upsert_feature_flag(
    req: FeatureFlagUpsert,
    user_id: str = Depends(get_current_user),
):
    if not _is_super_admin(user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    supabase = get_db_client()
    region = _normalize_region(req.region)
    now = datetime.utcnow().isoformat()

    payload = {
        "region": region,
        "feature_key": req.feature_key,
        "enabled": req.enabled,
        "payload": req.payload,
        "updated_at": now,
    }

    # Requires unique index on (region, feature_key) for safe upsert.
    result = supabase.table("app_feature_flags").upsert(payload).execute()
    return {"success": True, "flag": (result.data or [payload])[0]}


@admin_router.get("/retailers")
async def admin_list_retailers(
    region: Optional[str] = None,
    user_id: str = Depends(get_current_user),
):
    if not _is_super_admin(user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    supabase = get_db_client()
    query = supabase.table("app_retailers").select("region,name,url,enabled,sort_order")
    if region:
        query = query.eq("region", _normalize_region(region))

    result = query.order("region").order("sort_order").order("name").execute()
    return {"success": True, "retailers": result.data or []}


@admin_router.put("/retailers")
async def admin_upsert_retailer(
    req: RetailerUpsert,
    user_id: str = Depends(get_current_user),
):
    if not _is_super_admin(user_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")

    supabase = get_db_client()
    region = _normalize_region(req.region)

    payload = {
        "region": region,
        "name": req.name,
        "url": req.url,
        "enabled": req.enabled,
        "sort_order": req.sort_order,
        "updated_at": datetime.utcnow().isoformat(),
    }

    result = supabase.table("app_retailers").upsert(payload).execute()
    return {"success": True, "retailer": (result.data or [payload])[0]}
