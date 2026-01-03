"""Temporary debug endpoints to diagnose planning issues."""

from fastapi import APIRouter, Depends
from app.core.database import get_full_profile
from app.core.safety_constraints import SAVOGoldenRule
from app.middleware.auth import get_current_user
from typing import Any, Dict, List

router = APIRouter()


@router.get("/profile-check")
async def debug_profile_check(user_id: str = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Debug endpoint: check what Golden Rule sees in the profile.
    Returns the exact profile dict + Golden Rule result.
    """
    try:
        full_profile = await get_full_profile(user_id)
    except Exception as e:
        return {
            "error": "Failed to load profile",
            "detail": str(e),
            "user_id": user_id,
        }

    household = full_profile.get("household") or full_profile.get("profile") or {}
    members = full_profile.get("members") or []
    
    # Normalize members (add allergens key if missing)
    normalized_members: List[Dict[str, Any]] = []
    for m in members:
        if not isinstance(m, dict):
            continue
        if "allergens" not in m:
            m = {**m, "allergens": []}
        normalized_members.append(m)
    
    profile_dict = {"household": household, "members": normalized_members}
    
    # Run Golden Rule check
    golden_check = SAVOGoldenRule.check_before_generate(profile_dict)
    
    # Return detailed diagnosis
    return {
        "user_id": user_id,
        "household_exists": bool(household),
        "household_keys": list(household.keys()) if household else [],
        "members_count": len(normalized_members),
        "members_summary": [
            {
                "id": m.get("id"),
                "name": m.get("name"),
                "has_allergens_key": "allergens" in m,
                "allergens_value": m.get("allergens"),
                "allergens_type": type(m.get("allergens")).__name__,
            }
            for m in normalized_members
        ],
        "golden_rule_result": golden_check,
        "profile_dict_structure": {
            "has_household": "household" in profile_dict,
            "has_members": "members" in profile_dict,
            "members_is_list": isinstance(profile_dict.get("members"), list),
        },
    }
