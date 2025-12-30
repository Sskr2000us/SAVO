"""
Profile Management API Routes
Handles household profiles and family member management
"""

from fastapi import APIRouter, HTTPException, Header
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
    get_or_create_user
)

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


# ============================================================================
# HOUSEHOLD PROFILE ENDPOINTS
# ============================================================================

@router.get("/household")
async def get_household(
    x_user_id: str = Header(..., description="User ID from auth"),
    x_user_email: str = Header(..., description="User email from auth")
):
    """
    Get household profile for authenticated user.
    Creates user record if it doesn't exist.
    """
    try:
        # Ensure user exists
        await get_or_create_user(x_user_id, x_user_email)
        
        # Get household profile
        profile = await get_household_profile(x_user_id)
        
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
    x_user_id: str = Header(..., description="User ID from auth"),
    x_user_email: str = Header(..., description="User email from auth")
):
    """
    Create household profile for authenticated user.
    This is a one-time setup operation.
    """
    try:
        # Ensure user exists
        await get_or_create_user(x_user_id, x_user_email)
        
        # Check if profile already exists
        existing = await get_household_profile(x_user_id)
        if existing:
            raise HTTPException(
                status_code=400,
                detail="Household profile already exists. Use PATCH to update."
            )
        
        # Create profile
        profile_data = profile.model_dump(exclude_unset=True)
        created_profile = await create_household_profile(x_user_id, profile_data)
        
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
    x_user_id: str = Header(..., description="User ID from auth")
):
    """
    Update household profile for authenticated user.
    Only provided fields will be updated.
    """
    try:
        # Check if profile exists
        existing = await get_household_profile(x_user_id)
        if not existing:
            raise HTTPException(
                status_code=404,
                detail="Household profile not found. Create one first."
            )
        
        # Update profile
        profile_data = profile.model_dump(exclude_unset=True)
        if not profile_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        updated_profile = await update_household_profile(x_user_id, profile_data)
        
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
    x_user_id: str = Header(..., description="User ID from auth")
):
    """
    Get all family members for authenticated user.
    Returns empty list if no members found.
    """
    try:
        members = await get_family_members(x_user_id)
        
        return {
            "count": len(members),
            "members": members
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/family-members")
async def add_family_member(
    member: FamilyMemberCreate,
    x_user_id: str = Header(..., description="User ID from auth")
):
    """
    Add new family member to household.
    Household profile must exist first.
    """
    try:
        # Check if household exists
        household = await get_household_profile(x_user_id)
        if not household:
            raise HTTPException(
                status_code=404,
                detail="Household profile not found. Create one first."
            )
        
        # Create family member
        member_data = member.model_dump()
        created_member = await create_family_member(x_user_id, member_data)
        
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
    x_user_id: str = Header(..., description="User ID from auth")
):
    """
    Update existing family member.
    Only provided fields will be updated.
    """
    try:
        # Verify member belongs to user (via household)
        members = await get_family_members(x_user_id)
        member_ids = [m["id"] for m in members]
        
        if member_id not in member_ids:
            raise HTTPException(
                status_code=404,
                detail="Family member not found or access denied"
            )
        
        # Update member
        member_data = member.model_dump(exclude_unset=True)
        if not member_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        updated_member = await update_family_member(member_id, member_data)
        
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
    x_user_id: str = Header(..., description="User ID from auth")
):
    """
    Remove family member from household.
    """
    try:
        # Verify member belongs to user
        members = await get_family_members(x_user_id)
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
