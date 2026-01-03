"""
Profile Management API Routes
Handles household profiles and family member management
"""

from fastapi import APIRouter, HTTPException, Header, Depends, Request
from typing import Optional, List
from pydantic import BaseModel, Field
from datetime import datetime

from app.core.database import (
    get_household_profile,
    create_household_profile,
    update_household_profile,
    get_family_members,
    create_family_member,
    update_family_member,
    delete_family_member,
    get_or_create_user,
    log_audit_event,
    get_audit_log,
    mark_onboarding_complete,
    get_onboarding_status,
    get_full_profile
)
from app.middleware.auth import get_current_user

router = APIRouter(prefix="/profile", tags=["profile"])


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class HouseholdProfileCreate(BaseModel):
    """Request model for creating household profile"""
    region: str = Field(default="US", description="Region code (US, UK, etc)")
    culture: str = Field(default="western", description="Cultural preference")
    primary_language: str = Field(default="en-US", description="Primary language")
    measurement_system: str = Field(default="imperial", description="metric or imperial")
    timezone: str = Field(default="UTC", description="Timezone")
    
    meal_times: Optional[dict] = Field(default=None, description="Meal time preferences")
    breakfast_preferences: List[str] = Field(default_factory=list)
    lunch_preferences: List[str] = Field(default_factory=list)
    dinner_preferences: List[str] = Field(default_factory=list)
    
    favorite_cuisines: List[str] = Field(default_factory=lambda: ["Italian", "American"])
    avoided_cuisines: List[str] = Field(default_factory=list)
    
    nutrition_targets: Optional[dict] = Field(default=None, description="Daily nutrition targets")
    skill_level: int = Field(default=2, ge=1, le=5, description="Cooking skill level (1-5)")
    dinner_courses: int = Field(default=2, ge=1, le=5, description="Number of dinner courses (1-5)")


class HouseholdProfileUpdate(BaseModel):
    """Request model for updating household profile"""
    region: Optional[str] = None
    culture: Optional[str] = None
    primary_language: Optional[str] = None
    measurement_system: Optional[str] = None
    timezone: Optional[str] = None
    
    meal_times: Optional[dict] = None
    breakfast_preferences: Optional[List[str]] = None
    lunch_preferences: Optional[List[str]] = None
    dinner_preferences: Optional[List[str]] = None
    
    favorite_cuisines: Optional[List[str]] = None
    avoided_cuisines: Optional[List[str]] = None
    
    nutrition_targets: Optional[dict] = None
    skill_level: Optional[int] = Field(None, ge=1, le=5)
    dinner_courses: Optional[int] = Field(None, ge=1, le=5)


class FamilyMemberCreate(BaseModel):
    """Request model for creating family member"""
    name: str = Field(..., description="Family member name")
    age: int = Field(..., ge=0, le=120, description="Age")
    
    dietary_restrictions: List[str] = Field(default_factory=list)
    allergens: List[str] = Field(default_factory=list)
    food_preferences: List[str] = Field(default_factory=list)
    food_dislikes: List[str] = Field(default_factory=list)
    
    health_conditions: List[str] = Field(default_factory=list)
    medical_dietary_needs: List[str] = Field(default_factory=list)
    
    spice_tolerance: str = Field(default="medium", description="none|mild|medium|high|very_high")
    display_order: int = Field(default=0, description="Display order")


class FamilyMemberUpdate(BaseModel):
    """Request model for updating family member"""
    name: Optional[str] = None
    age: Optional[int] = Field(None, ge=0, le=120)
    
    dietary_restrictions: Optional[List[str]] = None
    allergens: Optional[List[str]] = None
    food_preferences: Optional[List[str]] = None
    food_dislikes: Optional[List[str]] = None
    
    health_conditions: Optional[List[str]] = None
    medical_dietary_needs: Optional[List[str]] = None
    
    spice_tolerance: Optional[str] = None
    display_order: Optional[int] = None


class AllergensUpdate(BaseModel):
    """Request model for updating allergens"""
    member_id: str = Field(..., description="Family member ID")
    allergens: List[str] = Field(..., description="List of allergens")
    reason: Optional[str] = Field(None, description="Reason for change (audit)")


class DietaryUpdate(BaseModel):
    """Request model for updating dietary restrictions"""
    member_id: str = Field(..., description="Family member ID")
    dietary_restrictions: List[str] = Field(..., description="List of dietary restrictions")


class PreferencesUpdate(BaseModel):
    """Request model for updating household preferences"""
    favorite_cuisines: Optional[List[str]] = None
    avoided_cuisines: Optional[List[str]] = None
    spice_tolerance: Optional[str] = None
    basic_spices_available: Optional[bool] = None


class LanguageUpdate(BaseModel):
    """Request model for updating language preference"""
    primary_language: str = Field(..., description="Language code (e.g., en-US, es-ES)")


# ============================================================================
# HOUSEHOLD PROFILE ENDPOINTS
# ============================================================================

@router.get("/household")
async def get_household(
    user_id: str = Depends(get_current_user)
):
    """
    Get household profile for authenticated user.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        # Get household profile
        profile = await get_household_profile(user_id)
        
        if not profile:
            return {
                "exists": False,
                "message": "No household profile found. Please create one."
            }
        
        return {
            "exists": True,
            "profile": profile
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/household")
async def create_household(
    profile: HouseholdProfileCreate,
    user_id: str = Depends(get_current_user)
):
    """
    Create household profile for authenticated user.
    This is a one-time setup operation.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        # Ensure user exists in database (creates if not exists)
        await get_or_create_user(user_id)
        
        # Check if profile already exists
        existing = await get_household_profile(user_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Household profile already exists. Use PATCH to update."
            )
        
        # Create profile
        profile_data = profile.model_dump(exclude_unset=True)
        created_profile = await create_household_profile(user_id, profile_data)
        
        return {
            "success": True,
            "message": "Household profile created successfully",
            "profile": created_profile
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/household")
async def update_household(
    profile: HouseholdProfileUpdate,
    request: Request,
    user_id: str = Depends(get_current_user)
):
    """
    Update household profile for authenticated user.
    Only provided fields will be updated.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        # Ensure user exists
        await get_or_create_user(user_id)
        # Check if profile exists
        existing = await get_household_profile(user_id)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Household profile not found. Create one first."
            )
        
        # Update profile
        profile_data = profile.model_dump(exclude_unset=True)
        if not profile_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Get old values for audit
        old_values = {k: existing.get(k) for k in profile_data.keys()}
        
        updated_profile = await update_household_profile(user_id, profile_data)
        
        # Log audit event
        device_info = {
            "user_agent": request.headers.get("user-agent", "unknown")
        }
        
        await log_audit_event(
            user_id=user_id,
            event_type="profile_update",
            route="/profile/household",
            entity_type="household_profile",
            entity_id=user_id,
            old_value=old_values,
            new_value=profile_data,
            device_info=device_info,
            ip_address=request.client.host if request.client else None
        )
        
        return {
            "success": True,
            "message": "Household profile updated successfully",
            "profile": updated_profile
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# FAMILY MEMBER ENDPOINTS
# ============================================================================

@router.get("/family-members")
async def list_family_members(
    user_id: str = Depends(get_current_user)
):
    """
    Get all family members for authenticated user.
    Returns empty list if no members found.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        members = await get_family_members(user_id)
        
        return {
            "count": len(members),
            "members": members
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/family-members")
async def add_family_member(
    member: FamilyMemberCreate,
    user_id: str = Depends(get_current_user)
):
    """
    Add new family member to household.
    Household profile must exist first.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        # Ensure user exists
        await get_or_create_user(user_id)
        
        # Check if household exists
        household = await get_household_profile(user_id)
        if not household:
            raise HTTPException(
                status_code=404,
                detail="Household profile not found. Create one first."
            )
        
        # Create family member
        member_data = member.model_dump()
        created_member = await create_family_member(user_id, member_data)
        
        return {
            "success": True,
            "message": "Family member added successfully",
            "member": created_member
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/family-members/{member_id}")
async def update_family_member_endpoint(
    member_id: str,
    member: FamilyMemberUpdate,
    request: Request,
    user_id: str = Depends(get_current_user)
):
    """
    Update existing family member.
    Only provided fields will be updated.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        # Ensure user exists
        await get_or_create_user(user_id)
        
        # Verify member belongs to user (via household)
        members = await get_family_members(user_id)
        existing_member = next((m for m in members if m["id"] == member_id), None)
        
        if not existing_member:
            raise HTTPException(
                status_code=404,
                detail="Family member not found or access denied"
            )
        
        # Update member
        member_data = member.model_dump(exclude_unset=True)
        if not member_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        # Get old values for audit
        old_values = {k: existing_member.get(k) for k in member_data.keys()}
        
        updated_member = await update_family_member(member_id, member_data)
        
        # Log audit event
        device_info = {
            "user_agent": request.headers.get("user-agent", "unknown")
        }
        
        await log_audit_event(
            user_id=user_id,
            event_type="family_member_update",
            route="/profile/family-members",
            entity_type="family_member",
            entity_id=member_id,
            old_value=old_values,
            new_value=member_data,
            device_info=device_info,
            ip_address=request.client.host if request.client else None
        )
        
        return {
            "success": True,
            "message": "Family member updated successfully",
            "member": updated_member
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/family-members/{member_id}")
async def remove_family_member(
    member_id: str,
    user_id: str = Depends(get_current_user)
):
    """
    Remove family member from household.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        # Ensure user exists
        await get_or_create_user(user_id)
        
        # Verify member belongs to user
        members = await get_family_members(user_id)
        member_ids = [m["id"] for m in members]
        
        if member_id not in member_ids:
            raise HTTPException(
                status_code=404,
                detail="Family member not found or access denied"
            )
        
        # Delete member
        await delete_family_member(member_id)
        
        return {
            "success": True,
            "message": "Family member removed successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# FULL PROFILE ENDPOINT (C1)
# ============================================================================

@router.get("/full")
async def get_full_user_profile(
    user_id: str = Depends(get_current_user)
):
    """
    Get complete user profile with all related data.
    Returns user, household profile, family members, and aggregated allergens/dietary.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        full_profile = await get_full_profile(user_id)
        
        return {
            "success": True,
            "data": full_profile
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SPECIALIZED UPDATE ENDPOINTS (C2)
# ============================================================================

@router.patch("/allergens")
async def update_allergens(
    data: AllergensUpdate,
    request: Request,
    user_id: str = Depends(get_current_user)
):
    """
    Update allergens for a family member with audit logging.
    This is a safety-critical operation that's tracked in audit_log.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        # Ensure user exists
        await get_or_create_user(user_id)
        
        # Verify member belongs to user
        members = await get_family_members(user_id)
        member = next((m for m in members if m["id"] == data.member_id), None)
        
        if not member:
            raise HTTPException(
                status_code=404,
                detail="Family member not found or access denied"
            )
        
        # Get old allergens for audit
        old_allergens = member.get("allergens", [])
        
        # Update member
        updated_member = await update_family_member(
            data.member_id,
            {"allergens": data.allergens}
        )
        
        # Log audit event
        device_info = {
            "user_agent": request.headers.get("user-agent", "unknown"),
            "reason": data.reason
        }
        
        await log_audit_event(
            user_id=user_id,
            event_type="allergen_update",
            route="/profile/allergens",
            entity_type="family_member",
            entity_id=data.member_id,
            old_value={"allergens": old_allergens},
            new_value={"allergens": data.allergens},
            device_info=device_info,
            ip_address=request.client.host if request.client else None
        )
        
        return {
            "success": True,
            "message": "Allergens updated successfully",
            "member": updated_member
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/dietary")
async def update_dietary(
    data: DietaryUpdate,
    request: Request,
    user_id: str = Depends(get_current_user)
):
    """
    Update dietary restrictions for a family member.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        # Ensure user exists
        await get_or_create_user(user_id)
        
        # Verify member belongs to user
        members = await get_family_members(user_id)
        member = next((m for m in members if m["id"] == data.member_id), None)
        
        if not member:
            raise HTTPException(
                status_code=404,
                detail="Family member not found or access denied"
            )
        
        # Get old dietary restrictions for audit
        old_dietary = member.get("dietary_restrictions", [])
        
        # Update member
        updated_member = await update_family_member(
            data.member_id,
            {"dietary_restrictions": data.dietary_restrictions}
        )
        
        # Log audit event
        device_info = {
            "user_agent": request.headers.get("user-agent", "unknown")
        }
        
        await log_audit_event(
            user_id=user_id,
            event_type="dietary_update",
            route="/profile/dietary",
            entity_type="family_member",
            entity_id=data.member_id,
            old_value={"dietary_restrictions": old_dietary},
            new_value={"dietary_restrictions": data.dietary_restrictions},
            device_info=device_info,
            ip_address=request.client.host if request.client else None
        )
        
        return {
            "success": True,
            "message": "Dietary restrictions updated successfully",
            "member": updated_member
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/preferences")
async def update_preferences(
    data: PreferencesUpdate,
    request: Request,
    user_id: str = Depends(get_current_user)
):
    """
    Update household preferences (cuisines, spice tolerance, pantry).
    Requires JWT Bearer token in Authorization header.
    """
    try:        # Ensure user exists
        await get_or_create_user(user_id)        # Get existing profile for audit
        existing = await get_household_profile(user_id)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Household profile not found"
            )
        
        # Build update dict from provided fields
        updates = {}
        
        if data.favorite_cuisines is not None:
            updates["favorite_cuisines"] = data.favorite_cuisines
        
        if data.avoided_cuisines is not None:
            updates["avoided_cuisines"] = data.avoided_cuisines
        
        if data.basic_spices_available is not None:
            updates["basic_spices_available"] = data.basic_spices_available
        
        # Note: spice_tolerance is on family_member, not household_profile
        # If provided, we'll ignore it here or could add validation
        
        if not updates:
            raise HTTPException(
                status_code=400,
                detail="No valid fields provided for update"
            )
        
        # Get old values for audit
        old_values = {k: existing.get(k) for k in updates.keys()}
        
        # Update household profile
        updated_profile = await update_household_profile(user_id, updates)
        
        # Log audit event
        device_info = {
            "user_agent": request.headers.get("user-agent", "unknown")
        }
        
        await log_audit_event(
            user_id=user_id,
            event_type="preferences_update",
            route="/profile/preferences",
            entity_type="household_profile",
            entity_id=user_id,
            old_value=old_values,
            new_value=updates,
            device_info=device_info,
            ip_address=request.client.host if request.client else None
        )
        
        return {
            "success": True,
            "message": "Preferences updated successfully",
            "profile": updated_profile
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/language")
async def update_language(
    data: LanguageUpdate,
    request: Request,
    user_id: str = Depends(get_current_user)
):
    """
    Update primary language for household.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        # Ensure user exists
        await get_or_create_user(user_id)
        
        # Get existing profile for audit
        existing = await get_household_profile(user_id)
        old_language = existing.get("primary_language") if existing else None
        
        updated_profile = await update_household_profile(
            user_id,
            {"primary_language": data.primary_language}
        )
        
        # Log audit event
        device_info = {
            "user_agent": request.headers.get("user-agent", "unknown")
        }
        
        await log_audit_event(
            user_id=user_id,
            event_type="language_update",
            route="/profile/language",
            entity_type="household_profile",
            entity_id=user_id,
            old_value={"primary_language": old_language},
            new_value={"primary_language": data.primary_language},
            device_info=device_info,
            ip_address=request.client.host if request.client else None
        )
        
        return {
            "success": True,
            "message": "Language updated successfully",
            "profile": updated_profile
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ONBOARDING STATUS ENDPOINTS (C3)
# ============================================================================

@router.get("/onboarding-status")
async def get_onboarding_status_endpoint(
    user_id: str = Depends(get_current_user)
):
    """
    Get onboarding completion status and determine resume step.
    Returns completed flag, resume_step (HOUSEHOLD|ALLERGIES|DIETARY|SPICE|PANTRY|LANGUAGE|COMPLETE),
    and list of missing fields.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        status = await get_onboarding_status(user_id)
        
        return {
            "success": True,
            "data": status
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/complete")
async def complete_onboarding(
    request: Request,
    user_id: str = Depends(get_current_user)
):
    """
    Mark onboarding as completed.
    Sets onboarding_completed_at timestamp in household_profiles.
    Requires JWT Bearer token in Authorization header.
    """
    try:
        # Ensure user exists
        await get_or_create_user(user_id)
        
        completed_at = datetime.utcnow()
        await mark_onboarding_complete(user_id)
        
        # Log audit event
        device_info = {
            "user_agent": request.headers.get("user-agent", "unknown")
        }
        
        await log_audit_event(
            user_id=user_id,
            event_type="onboarding_complete",
            route="/profile/complete",
            entity_type="household_profile",
            entity_id=user_id,
            old_value={"onboarding_completed_at": None},
            new_value={"onboarding_completed_at": completed_at.isoformat()},
            device_info=device_info,
            ip_address=request.client.host if request.client else None
        )
        
        return {
            "success": True,
            "message": "Onboarding marked as complete",
            "completed_at": completed_at.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# AUDIT LOG ENDPOINT
# ============================================================================

@router.get("/audit")
async def get_audit_history(
    limit: int = 100,
    user_id: str = Depends(get_current_user)
):
    """
    Get audit log history for the authenticated user.
    Returns list of all profile changes with timestamps and old/new values.
    Requires JWT Bearer token in Authorization header.
    
    Query Parameters:
    - limit: Maximum number of records to return (default 100, max 1000)
    """
    try:
        # Validate limit
        if limit > 1000:
            limit = 1000
        
        audit_log = await get_audit_log(user_id, limit)
        
        return {
            "success": True,
            "count": len(audit_log),
            "audit_log": audit_log
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# SESSION TRACKING ENDPOINTS (Optional - Phase H)
# ============================================================================

class SessionUpdateRequest(BaseModel):
    """Request model for updating session info"""
    device_info: str = Field(..., description="Device information (e.g., 'Android Device', 'iOS Device')")


@router.post("/session/track")
async def track_session_login(
    request: Request,
    session_data: SessionUpdateRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Track session login for multi-device visibility (optional).
    Updates last_login_device and last_login_at in users table.
    This is informational only - Supabase Auth manages actual sessions.
    
    Requires JWT Bearer token in Authorization header.
    """
    try:
        from app.core.database import get_db_client
        supabase = get_db_client()
        
        # Update user's last login info
        result = supabase.table("users").update({
            "last_login_device": session_data.device_info,
            "last_login_at": datetime.utcnow().isoformat(),
        }).eq("id", user_id).execute()
        
        return {
            "success": True,
            "message": "Session tracked",
            "device": session_data.device_info
        }
        
    except Exception as e:
        # Don't fail hard - this is optional tracking
        return {
            "success": False,
            "message": f"Session tracking failed (non-critical): {str(e)}"
        }


@router.get("/session/info")
async def get_session_info(
    user_id: str = Depends(get_current_user)
):
    """
    Get session metadata for the authenticated user (optional).
    Returns last login device and timestamp for display in Active Sessions screen.
    
    Requires JWT Bearer token in Authorization header.
    """
    try:
        from app.core.database import get_db_client
        supabase = get_db_client()
        
        # Get user's session info
        result = supabase.table("users").select(
            "last_login_device, last_login_at, active_sessions_count"
        ).eq("id", user_id).execute()
        
        if not result.data:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_data = result.data[0]
        
        return {
            "success": True,
            "session_info": {
                "last_login_device": user_data.get("last_login_device"),
                "last_login_at": user_data.get("last_login_at"),
                "active_sessions_count": user_data.get("active_sessions_count", 0)
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

