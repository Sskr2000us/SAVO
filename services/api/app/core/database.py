"""
Supabase Database Client for SAVO
Handles all database operations with connection pooling and error handling
"""

from typing import Optional, Dict, Any, List
import os
from datetime import datetime, date
import re
from supabase import create_client, Client
from postgrest.exceptions import APIError
import asyncpg
import logging

logger = logging.getLogger(__name__)

# NOTE: Do not import app.core.media_storage at module import time.
# media_storage imports get_db_client from this module; importing it here creates
# a circular import that breaks startup (e.g., on Render).


class SupabaseDB:
    """Singleton database client for Supabase operations"""
    
    _instance: Optional['SupabaseDB'] = None
    _client: Optional[Client] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Lazy initialization: do not hard-fail module import when env vars
        # are not present (e.g., local unit tests, CI lint steps).
        # The client will be created on first access to .client.
        pass

    def _ensure_client(self) -> None:
        if self._client is not None:
            return

        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for backend

        if not url or not key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_KEY must be set in environment variables"
            )

        try:
            self._client = create_client(url, key)
            logger.info("Supabase client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Supabase client: {e}")
            raise
    
    @property
    def client(self) -> Client:
        """Get the Supabase client instance"""
        if self._client is None:
            self._ensure_client()
        if self._client is None:
            raise RuntimeError("Supabase client not initialized")
        return self._client


# Singleton instance
db = SupabaseDB()


def get_db_client() -> Client:
    """Get the Supabase client instance for direct database operations"""
    return db.client


async def get_db_connection() -> asyncpg.Connection:
    """
    Get a direct asyncpg connection to the PostgreSQL database.
    Used by routers that need raw SQL access (search, graph, regional, waste).
    
    Returns a connection that should be closed after use.
    For use with FastAPI Depends(), it will be automatically closed.
    """
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is required for direct database connections")
    
    try:
        conn = await asyncpg.connect(database_url)
        return conn
    except Exception as e:
        logger.error(f"Failed to create database connection: {e}")
        raise


_MISSING_COLUMN_RE = re.compile(r"Could not find the '([^']+)' column")


def _extract_missing_column_name(err: Exception) -> Optional[str]:
    text = str(err)
    match = _MISSING_COLUMN_RE.search(text)
    if match:
        return match.group(1)
    return None


def _drop_none_values(data: Dict[str, Any]) -> Dict[str, Any]:
    """Drop None values so older schemas don't choke on optional fields."""
    return {k: v for k, v in data.items() if v is not None}


def _drop_none_values_except(data: Dict[str, Any], keep_null_keys: set[str]) -> Dict[str, Any]:
    """Drop None values but keep explicit nulls for selected keys.

    This allows PATCH semantics to clear nullable columns (e.g., expiry_date) when
    the client intentionally sends null.
    """
    return {k: v for k, v in data.items() if v is not None or k in keep_null_keys}


# ============================================================================
# USER PROFILE OPERATIONS
# ============================================================================

async def get_or_create_user(user_id: str, email: Optional[str] = None, full_name: Optional[str] = None) -> Dict[str, Any]:
    """Get or create user profile"""
    try:
        # Try to get existing user
        result = db.client.table("users").select("*").eq("id", user_id).execute()
        
        if result.data:
            return result.data[0]
        
        # Create new user (email is optional, may be set later)
        user_data = {
            "id": user_id,
            "email": email or f"{user_id}@temp.savo.app",  # Temporary email if not provided
            "full_name": full_name,
            "last_login_at": datetime.utcnow().isoformat()
        }
        
        result = db.client.table("users").insert(user_data).execute()
        return result.data[0]
        
    except APIError as e:
        logger.error(f"Error getting/creating user: {e}")
        raise


async def update_user_login(user_id: str) -> None:
    """Update user's last login timestamp"""
    try:
        db.client.table("users").update({
            "last_login_at": datetime.utcnow().isoformat()
        }).eq("id", user_id).execute()
    except APIError as e:
        logger.error(f"Error updating user login: {e}")


# ============================================================================
# HOUSEHOLD PROFILE OPERATIONS
# ============================================================================

async def get_household_profile(user_id: str) -> Optional[Dict[str, Any]]:
    """Get household profile for user"""
    try:
        result = db.client.table("household_profiles").select("*").eq("user_id", user_id).execute()
        return result.data[0] if result.data else None
    except APIError as e:
        logger.error(f"Error getting household profile: {e}")
        raise


async def create_household_profile(user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new household profile"""
    try:
        profile_data = dict(profile_data)
        profile_data["user_id"] = user_id
        profile_data = _drop_none_values(profile_data)

        try:
            result = db.client.table("household_profiles").insert(profile_data).execute()
            return result.data[0]
        except APIError as e:
            missing = _extract_missing_column_name(e)
            if missing and missing in profile_data:
                logger.warning(f"Dropping unknown household_profiles column '{missing}' and retrying insert")
                profile_data.pop(missing, None)
                result = db.client.table("household_profiles").insert(profile_data).execute()
                return result.data[0]
            raise
    except APIError as e:
        logger.error(f"Error creating household profile for user {user_id}: {e}")
        logger.error(f"Profile data: {profile_data}")
        raise


async def update_household_profile(user_id: str, profile_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update existing household profile"""
    try:
        profile_data = _drop_none_values(dict(profile_data))

        try:
            result = db.client.table("household_profiles").update(profile_data).eq("user_id", user_id).execute()
            return result.data[0] if result.data else None
        except APIError as e:
            missing = _extract_missing_column_name(e)
            if missing and missing in profile_data:
                logger.warning(f"Dropping unknown household_profiles column '{missing}' and retrying update")
                profile_data.pop(missing, None)
                result = db.client.table("household_profiles").update(profile_data).eq("user_id", user_id).execute()
                return result.data[0] if result.data else None
            raise
    except APIError as e:
        logger.error(f"Error updating household profile: {e}")
        raise


async def update_skill_level(user_id: str, recipes_completed: int) -> None:
    """Update skill level based on completed recipes"""
    try:
        # Calculate new skill level based on progression rules
        skill_level = 1
        if recipes_completed >= 12:
            skill_level = 5
        elif recipes_completed >= 8:
            skill_level = 4
        elif recipes_completed >= 5:
            skill_level = 3
        elif recipes_completed >= 3:
            skill_level = 2
        
        # Calculate confidence score
        confidence_score = min(0.95, 0.40 + (recipes_completed * 0.05))
        
        db.client.table("household_profiles").update({
            "skill_level": skill_level,
            "confidence_score": confidence_score,
            "recipes_completed": recipes_completed
        }).eq("user_id", user_id).execute()
        
    except APIError as e:
        logger.error(f"Error updating skill level: {e}")


# ============================================================================
# FAMILY MEMBER OPERATIONS
# ============================================================================

async def get_family_members(user_id: str) -> List[Dict[str, Any]]:
    """Get all family members for user"""
    try:
        # First get household_id
        household = await get_household_profile(user_id)
        if not household:
            return []
        
        result = db.client.table("family_members").select("*").eq(
            "household_id", household["id"]
        ).order("display_order").execute()
        
        return result.data or []
    except APIError as e:
        logger.error(f"Error getting family members: {e}")
        raise


async def create_family_member(user_id: str, member_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new family member"""
    try:
        household = await get_household_profile(user_id)
        if not household:
            raise ValueError("Household profile not found")
        
        member_data["household_id"] = household["id"]
        
        # Don't manually set ID - let database generate UUID
        # Remove 'id' if it exists in member_data
        member_data.pop("id", None)
        
        # Determine age category based on age
        age = member_data.get("age", 0)
        if age < 13:
            member_data["age_category"] = "child"
        elif age < 18:
            member_data["age_category"] = "teen"
        elif age < 65:
            member_data["age_category"] = "adult"
        else:
            member_data["age_category"] = "senior"
        
        logger.info(f"Creating family member for household {household['id']}: {member_data}")
        result = db.client.table("family_members").insert(member_data).execute()
        logger.info(f"Successfully created family member: {result.data[0]['id']}")
        return result.data[0]
    except APIError as e:
        logger.error(f"Database error creating family member: {e}")
        logger.error(f"Member data: {member_data}")
        raise
    except Exception as e:
        logger.error(f"Error creating family member: {e}")
        logger.error(f"Member data: {member_data}")
        raise


async def update_family_member(member_id: str, member_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update existing family member"""
    try:
        # Update age category if age changed
        if "age" in member_data:
            age = member_data["age"]
            if age < 13:
                member_data["age_category"] = "child"
            elif age < 18:
                member_data["age_category"] = "teen"
            elif age < 65:
                member_data["age_category"] = "adult"
            else:
                member_data["age_category"] = "senior"
        
        result = db.client.table("family_members").update(member_data).eq("id", member_id).execute()
        return result.data[0] if result.data else None
    except APIError as e:
        logger.error(f"Error updating family member: {e}")
        raise


async def delete_family_member(member_id: str) -> None:
    """Delete family member"""
    try:
        db.client.table("family_members").delete().eq("id", member_id).execute()
    except APIError as e:
        logger.error(f"Error deleting family member: {e}")
        raise


# ============================================================================
# INVENTORY OPERATIONS
# ============================================================================

async def get_inventory(
    user_id: str,
    include_low_stock_only: bool = False,
    include_inactive: bool = False,
) -> List[Dict[str, Any]]:
    """Get user's inventory items.

    By default, returns only current items. Pass include_inactive=True to include items
    from previous scan sets that were marked inactive.
    """
    try:
        from app.core.media_storage import to_signed_url

        query = db.client.table("inventory_items").select("*").eq("user_id", user_id)

        if not include_inactive:
            query = query.eq("is_current", True)
        
        if include_low_stock_only:
            query = query.eq("is_low_stock", True)
        
        result = query.order("updated_at", desc=True).execute()
        items = result.data or []
        for item in items:
            if isinstance(item, dict) and item.get("image_url"):
                item["image_url"] = to_signed_url(item.get("image_url"))
        return items
    except APIError as e:
        logger.error(f"Error getting inventory: {e}")
        raise


async def get_inventory_by_category(
    user_id: str,
    category: str,
    include_inactive: bool = False,
) -> List[Dict[str, Any]]:
    """Get inventory items by category."""
    try:
        from app.core.media_storage import to_signed_url

        query = (
            db.client.table("inventory_items")
            .select("*")
            .eq("user_id", user_id)
            .eq("category", category)
        )
        if not include_inactive:
            query = query.eq("is_current", True)

        result = query.execute()

        items = result.data or []
        for item in items:
            if isinstance(item, dict) and item.get("image_url"):
                item["image_url"] = to_signed_url(item.get("image_url"))
        return items
    except APIError as e:
        logger.error(f"Error getting inventory by category: {e}")
        raise


async def add_inventory_item(user_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add new inventory item"""
    try:
        from app.core.media_storage import to_signed_url
        from app.core.inventory_cuisine import lookup_cuisine

        item_data = dict(item_data or {})
        item_data["user_id"] = user_id

        # Best-effort cuisine auto-fill (especially for scan/normalize flows).
        raw_cuisine = item_data.get("cuisine")
        if not (isinstance(raw_cuisine, str) and raw_cuisine.strip()):
            cuisine = lookup_cuisine(item_data.get("canonical_name"), item_data.get("display_name"))
            if cuisine:
                item_data["cuisine"] = cuisine

        item_data = _drop_none_values(item_data)
        
        # Set default low stock threshold if not provided
        if "low_stock_threshold" not in item_data:
            item_data["low_stock_threshold"] = 1.0
        
        # PostgREST can fail if DB migrations haven't been applied yet or schema cache is stale.
        # Retry by removing the missing column and re-attempting the insert.
        for _ in range(5):
            try:
                result = db.client.table("inventory_items").insert(item_data).execute()
                break
            except APIError as e:
                missing = _extract_missing_column_name(e)
                if missing == "expiry_date":
                    logger.error(
                        "Database schema is missing inventory_items.expiry_date. "
                        "Apply migrations before using expiry date features."
                    )
                    raise
                if missing and missing in item_data:
                    item_data.pop(missing, None)
                    continue
                raise
        created = result.data[0]
        if isinstance(created, dict) and created.get("image_url"):
            created["image_url"] = to_signed_url(created.get("image_url"))
        return created
    except APIError as e:
        logger.error(f"Error adding inventory item: {e}")
        raise


async def update_inventory_item(item_id: str, item_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update existing inventory item"""
    try:
        from app.core.media_storage import to_signed_url
        from app.core.inventory_cuisine import lookup_cuisine

        item_data = dict(item_data or {})

        raw_cuisine = item_data.get("cuisine")
        if not (isinstance(raw_cuisine, str) and raw_cuisine.strip()):
            cuisine = lookup_cuisine(item_data.get("canonical_name"), item_data.get("display_name"))
            if cuisine:
                item_data["cuisine"] = cuisine

        # Preserve explicit nulls for nullable columns so clients can clear them.
        item_data = _drop_none_values_except(
            item_data,
            {
                "purchase_date",
                "expiry_date",
                "notes",
                "category",
                "subcategory",
                "cuisine",
                "barcode",
                "product_name",
                "brand",
                "image_url",
                "package_size_text",
            },
        )

        for _ in range(5):
            try:
                result = db.client.table("inventory_items").update(item_data).eq("id", item_id).execute()
                break
            except APIError as e:
                missing = _extract_missing_column_name(e)
                if missing == "expiry_date":
                    logger.error(
                        "Database schema is missing inventory_items.expiry_date. "
                        "Apply migrations before using expiry date features."
                    )
                    raise
                if missing and missing in item_data:
                    item_data.pop(missing, None)
                    continue
                raise
        updated = result.data[0] if result.data else None
        if isinstance(updated, dict) and updated.get("image_url"):
            updated["image_url"] = to_signed_url(updated.get("image_url"))
        return updated
    except APIError as e:
        logger.error(f"Error updating inventory item: {e}")
        raise


async def delete_inventory_item(item_id: str) -> None:
    """Delete inventory item"""
    try:
        db.client.table("inventory_items").delete().eq("id", item_id).execute()
    except APIError as e:
        logger.error(f"Error deleting inventory item: {e}")
        raise


async def activate_inventory_items_for_location(
    user_id: str,
    storage_location: str,
) -> Dict[str, Any]:
    """Mark all items in a storage location as current.

    This is a bulk convenience action for users who want to use everything in a
    given location for planning.
    """
    try:
        result = (
            db.client.table("inventory_items")
            .update({"is_current": True, "last_seen_at": datetime.utcnow().isoformat()})
            .eq("user_id", user_id)
            .eq("storage_location", storage_location)
            .execute()
        )
        return {"updated_count": len(result.data or []), "storage_location": storage_location}
    except APIError as e:
        logger.error(f"Error bulk-activating inventory for location: {e}")
        raise


async def activate_inventory_items_for_scan_set(
    user_id: str,
    scan_id: str,
    mode: str = "replace",
) -> Dict[str, Any]:
    """Bulk-activate items belonging to a previous scan set.

    Modes:
    - replace: activates this scan set and deactivates other scan-sourced items
      in the same storage location(s) (keeps manual items unchanged).
    - merge: activates this scan set without deactivating anything else.
    """
    if mode not in {"replace", "merge"}:
        raise ValueError("mode must be 'replace' or 'merge'")

    try:
        # Find which storage locations this scan set touches.
        scan_items_result = (
            db.client.table("inventory_items")
            .select("storage_location")
            .eq("user_id", user_id)
            .eq("last_seen_scan_id", scan_id)
            .execute()
        )
        scan_items = scan_items_result.data or []
        storage_locations = sorted(
            {
                item.get("storage_location")
                for item in scan_items
                if isinstance(item, dict) and item.get("storage_location")
            }
        )

        if not storage_locations:
            return {"updated_count": 0, "scan_id": scan_id, "mode": mode, "storage_locations": []}

        if mode == "replace":
            # Deactivate other scan-sourced items in the same location(s).
            (
                db.client.table("inventory_items")
                .update({"is_current": False})
                .eq("user_id", user_id)
                .eq("source", "scan")
                .in_("storage_location", storage_locations)
                .neq("last_seen_scan_id", scan_id)
                .execute()
            )

        # Activate items from this scan set.
        activated = (
            db.client.table("inventory_items")
            .update({"is_current": True, "last_seen_at": datetime.utcnow().isoformat()})
            .eq("user_id", user_id)
            .eq("last_seen_scan_id", scan_id)
            .execute()
        )

        return {
            "updated_count": len(activated.data or []),
            "scan_id": scan_id,
            "mode": mode,
            "storage_locations": storage_locations,
        }
    except APIError as e:
        logger.error(f"Error bulk-activating inventory for scan set: {e}")
        raise


async def get_low_stock_items(user_id: str) -> List[Dict[str, Any]]:
    """Get low stock items using database function"""
    try:
        result = db.client.rpc("get_low_stock_items", {"p_user_id": user_id}).execute()
        return result.data or []
    except APIError as e:
        logger.error(f"Error getting low stock items: {e}")
        raise


async def get_expiring_items(user_id: str, days: int = 3) -> List[Dict[str, Any]]:
    """Get items expiring within specified days"""
    try:
        result = db.client.rpc("get_expiring_items", {
            "p_user_id": user_id,
            "p_days": days
        }).execute()
        return result.data or []
    except APIError as e:
        logger.error(f"Error getting expiring items: {e}")
        raise


async def deduct_inventory_for_recipe(
    user_id: str,
    meal_plan_id: str,
    ingredients: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Deduct inventory items after recipe selection
    Returns: {success: bool, message: str, insufficient_items: list}
    """
    try:
        result = db.client.rpc("deduct_inventory_for_recipe", {
            "p_user_id": user_id,
            "p_meal_plan_id": meal_plan_id,
            "p_ingredients": ingredients
        }).execute()
        
        return result.data[0] if result.data else {
            "success": False,
            "message": "Unknown error",
            "insufficient_items": []
        }
    except APIError as e:
        logger.error(f"Error deducting inventory: {e}")
        raise


# ============================================================================
# MEAL PLAN OPERATIONS
# ============================================================================

async def create_meal_plan(user_id: str, plan_data: Dict[str, Any]) -> Dict[str, Any]:
    """Create new meal plan"""
    try:
        plan_data["user_id"] = user_id
        
        # Get household_id if available
        household = await get_household_profile(user_id)
        if household:
            plan_data["household_id"] = household["id"]
        
        result = db.client.table("meal_plans").insert(plan_data).execute()
        return result.data[0]
    except APIError as e:
        logger.error(f"Error creating meal plan: {e}")
        raise


async def get_meal_plans(
    user_id: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    plan_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get meal plans with optional filters"""
    try:
        query = db.client.table("meal_plans").select("*").eq("user_id", user_id)
        
        if start_date:
            query = query.gte("plan_date", start_date.isoformat())
        
        if end_date:
            query = query.lte("plan_date", end_date.isoformat())
        
        if plan_type:
            query = query.eq("plan_type", plan_type)
        
        result = query.order("plan_date", desc=True).execute()
        return result.data or []
    except APIError as e:
        logger.error(f"Error getting meal plans: {e}")
        raise


async def get_meal_plan_for_date(
    user_id: str,
    *,
    plan_date: date,
    plan_type: str,
    meal_type: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get the most recent meal plan for a specific date/type (optionally meal_type)."""
    try:
        query = (
            db.client.table("meal_plans")
            .select("*")
            .eq("user_id", user_id)
            .eq("plan_type", plan_type)
            .eq("plan_date", plan_date.isoformat())
        )

        if meal_type:
            query = query.eq("meal_type", meal_type)

        result = query.order("planned_at", desc=True).limit(1).execute()
        if result.data:
            return result.data[0]
        return None
    except APIError as e:
        logger.error(f"Error getting meal plan for date: {e}")
        raise


async def update_meal_plan(meal_plan_id: str, plan_data: Dict[str, Any]) -> Dict[str, Any]:
    """Update meal plan"""
    try:
        result = db.client.table("meal_plans").update(plan_data).eq("id", meal_plan_id).execute()
        return result.data[0] if result.data else None
    except APIError as e:
        logger.error(f"Error updating meal plan: {e}")
        raise


async def delete_latest_meal_plan(
    user_id: str,
    *,
    plan_type: str,
    plan_date: Optional[date] = None,
) -> bool:
    """Delete the most recent saved meal plan for a user/type (optionally restricted to a date)."""
    try:
        query = (
            db.client.table("meal_plans")
            .select("id")
            .eq("user_id", user_id)
            .eq("plan_type", plan_type)
        )

        if plan_date:
            query = query.eq("plan_date", plan_date.isoformat())

        latest = query.order("planned_at", desc=True).limit(1).execute()
        if not latest.data:
            return False

        meal_plan_id = latest.data[0].get("id")
        if not meal_plan_id:
            return False

        db.client.table("meal_plans").delete().eq("id", meal_plan_id).execute()
        return True
    except APIError as e:
        logger.error(f"Error deleting meal plan: {e}")
        raise


async def complete_meal_plan(
    meal_plan_id: str,
    rating: Optional[int] = None,
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Mark meal plan as completed"""
    try:
        update_data = {
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat()
        }
        
        if rating:
            update_data["completion_rating"] = rating
        
        if notes:
            update_data["completion_notes"] = notes
        
        result = db.client.table("meal_plans").update(update_data).eq("id", meal_plan_id).execute()
        return result.data[0] if result.data else None
    except APIError as e:
        logger.error(f"Error completing meal plan: {e}")
        raise


# ============================================================================
# SHOPPING LIST OPERATIONS
# ============================================================================

def _shopping_item_key(item: Dict[str, Any]) -> str:
    """Match the Flutter shopping list key format: '{name}|{amount unit}'."""
    if not isinstance(item, dict):
        return ""

    name = (
        item.get("canonical_name")
        or item.get("ingredient")
        or item.get("name")
        or ""
    )
    name_s = str(name).strip().lower()
    if not name_s:
        return ""

    amount = item.get("amount")
    if amount is None:
        amount = item.get("quantity")
    unit = item.get("unit")

    parts: List[str] = []
    if amount is not None and str(amount).strip() != "":
        parts.append(str(amount).strip())
    if unit is not None and str(unit).strip() != "":
        parts.append(str(unit).strip())
    qty_s = " ".join(parts).strip().lower()

    return f"{name_s}|{qty_s}"


async def upsert_household_shopping_items(
    household_id: str,
    items: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Upsert shopping items into `household_shopping_items`.

    - Uses UNIQUE (household_id, item_key) for upsert.
    - Preserves existing `checked` state when present.
    """
    household_id = (household_id or "").strip()
    if not household_id or not isinstance(items, list) or not items:
        return {"upserted": 0}

    now = datetime.utcnow().isoformat()

    normalized: Dict[str, Dict[str, Any]] = {}
    for raw in items:
        if not isinstance(raw, dict):
            continue

        name = (
            raw.get("canonical_name")
            or raw.get("ingredient")
            or raw.get("name")
            or ""
        )
        canonical_name = str(name).strip()
        if not canonical_name:
            continue

        unit = str(raw.get("unit") or "").strip()
        quantity_val: Any = raw.get("quantity")
        if quantity_val is None:
            quantity_val = raw.get("amount")
        try:
            if quantity_val is not None and str(quantity_val).strip() != "":
                quantity_val = float(quantity_val)
        except Exception:
            pass

        item_json: Dict[str, Any] = {
            "canonical_name": canonical_name,
            "quantity": quantity_val,
            "unit": unit,
            "reason": raw.get("reason"),
            "optional": raw.get("optional"),
        }
        item_key = _shopping_item_key(item_json)
        if not item_key:
            continue

        # Deduplicate by key; keep the last JSON (most recent values) and sum numeric quantities.
        if item_key in normalized:
            prev = normalized[item_key]
            try:
                prev_q = prev.get("quantity")
                if isinstance(prev_q, (int, float)) and isinstance(quantity_val, (int, float)):
                    prev["quantity"] = float(prev_q) + float(quantity_val)
            except Exception:
                pass
            # Prefer a non-empty reason if available.
            if not prev.get("reason") and item_json.get("reason"):
                prev["reason"] = item_json.get("reason")
            # If any entry is required, mark required.
            if prev.get("optional") is True and item_json.get("optional") is False:
                prev["optional"] = False
        else:
            normalized[item_key] = item_json

    if not normalized:
        return {"upserted": 0}

    keys = list(normalized.keys())

    # Preserve checked state for existing items.
    checked_by_key: Dict[str, bool] = {}
    try:
        existing = (
            db.client.table("household_shopping_items")
            .select("item_key,checked")
            .eq("household_id", household_id)
            .in_("item_key", keys)
            .execute()
        )
        for r in existing.data or []:
            if isinstance(r, dict) and r.get("item_key"):
                checked_by_key[str(r.get("item_key"))] = r.get("checked") is True
    except Exception:
        # Best-effort: if we can't read existing rows (RLS, missing table, etc.),
        # still attempt an upsert with checked=False.
        checked_by_key = {}

    rows: List[Dict[str, Any]] = []
    for item_key, item_json in normalized.items():
        rows.append(
            {
                "household_id": household_id,
                "item_key": item_key,
                "item_json": _drop_none_values(item_json),
                "checked": checked_by_key.get(item_key, False),
                "updated_at": now,
            }
        )

    try:
        db.client.table("household_shopping_items").upsert(
            rows,
            on_conflict="household_id,item_key",
        ).execute()
        return {"upserted": len(rows)}
    except APIError as e:
        logger.error(f"Error upserting household shopping items: {e}")
        raise


# ============================================================================
# RECIPE HISTORY OPERATIONS
# ============================================================================

async def add_recipe_to_history(user_id: str, recipe_data: Dict[str, Any]) -> Dict[str, Any]:
    """Add completed recipe to history"""
    try:
        recipe_data["user_id"] = user_id
        recipe_data["completed_at"] = datetime.utcnow().isoformat()
        
        result = db.client.table("recipe_history").insert(recipe_data).execute()
        
        # Update household skill level if recipe was successful
        if recipe_data.get("was_successful", True):
            household = await get_household_profile(user_id)
            if household:
                new_count = household.get("recipes_completed", 0) + 1
                await update_skill_level(user_id, new_count)
        
        return result.data[0]
    except APIError as e:
        logger.error(f"Error adding recipe to history: {e}")
        raise


async def get_recipe_history(
    user_id: str,
    limit: int = 50,
    cuisine: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Get recipe history with optional filters"""
    try:
        query = db.client.table("recipe_history").select("*").eq("user_id", user_id)
        
        if cuisine:
            query = query.eq("cuisine", cuisine)
        
        result = query.order("completed_at", desc=True).limit(limit).execute()
        return result.data or []
    except APIError as e:
        logger.error(f"Error getting recipe history: {e}")
        raise


async def get_recent_recipes(user_id: str, days: int = 14) -> List[str]:
    """Get list of recently cooked recipe names for variety scoring"""
    try:
        cutoff_date = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_date = cutoff_date.isoformat()
        
        result = db.client.table("recipe_history").select("recipe_name").eq(
            "user_id", user_id
        ).gte("completed_at", cutoff_date).execute()
        
        return [r["recipe_name"] for r in result.data] if result.data else []
    except APIError as e:
        logger.error(f"Error getting recent recipes: {e}")
        return []


# ============================================================================
# AUDIT LOG OPERATIONS
# ============================================================================

async def log_audit_event(
    user_id: str,
    event_type: str,
    route: str,
    entity_type: str,
    entity_id: Optional[str],
    old_value: Dict[str, Any],
    new_value: Dict[str, Any],
    device_info: Optional[Dict[str, Any]] = None,
    ip_address: Optional[str] = None
) -> None:
    """Log audit event for tracking profile changes"""
    try:
        audit_data = {
            "user_id": user_id,
            "event_type": event_type,
            "route": route,
            "entity_type": entity_type,
            "entity_id": entity_id,
            "old_value": old_value,
            "new_value": new_value,
            "device_info": device_info or {},
            "ip_address": ip_address
        }
        db.client.table("audit_log").insert(audit_data).execute()
        logger.info(f"Audit log: {event_type} for user {user_id}")
    except APIError as e:
        logger.error(f"Error logging audit event: {e}")
        # Don't raise - audit logging shouldn't break user flow


async def get_audit_log(user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Get audit log for user"""
    try:
        result = db.client.table("audit_log").select("*").eq(
            "user_id", user_id
        ).order("created_at", desc=True).limit(limit).execute()
        return result.data or []
    except APIError as e:
        logger.error(f"Error getting audit log: {e}")
        raise


# ============================================================================
# ONBOARDING OPERATIONS
# ============================================================================

async def mark_onboarding_complete(user_id: str) -> None:
    """Mark onboarding as completed"""
    try:
        db.client.table("household_profiles").update({
            "onboarding_completed_at": datetime.utcnow().isoformat()
        }).eq("user_id", user_id).execute()
        logger.info(f"Onboarding completed for user {user_id}")
    except APIError as e:
        logger.error(f"Error marking onboarding complete: {e}")
        raise


async def get_onboarding_status(user_id: str) -> Dict[str, Any]:
    """Check onboarding completion status and determine resume step"""
    try:
        # Get household profile
        profile = await get_household_profile(user_id)
        
        if not profile:
            return {
                "completed": False,
                "resume_step": "HOUSEHOLD",
                "missing_fields": ["household_profile"]
            }
        
        # Check if explicitly marked complete
        if profile.get("onboarding_completed_at"):
            return {
                "completed": True,
                "resume_step": "COMPLETE",
                "missing_fields": [],
                "completed_at": profile["onboarding_completed_at"]
            }
        
        # Check what's missing
        missing_fields = []
        
        # Check family members
        members = await get_family_members(user_id)
        if not members:
            missing_fields.append("household_members")
        else:
            # Check if allergens are declared (even empty array counts as declared)
            allergens_declared = any("allergens" in m for m in members)
            if not allergens_declared:
                missing_fields.append("allergens")
            
            # Check if dietary restrictions are declared
            dietary_declared = any("dietary_restrictions" in m for m in members)
            if not dietary_declared:
                missing_fields.append("dietary")
            
            # Check spice tolerance (optional)
            spice_declared = any(m.get("spice_tolerance") for m in members)
            if not spice_declared:
                missing_fields.append("spice")
        
        # Check basic spices availability (optional)
        if not profile.get("basic_spices_available"):
            missing_fields.append("pantry")
        
        # Check language
        if not profile.get("primary_language"):
            missing_fields.append("language")
        
        # Determine resume step
        if "household_members" in missing_fields:
            resume_step = "HOUSEHOLD"
        elif "allergens" in missing_fields:
            resume_step = "ALLERGIES"
        elif "dietary" in missing_fields:
            resume_step = "DIETARY"
        elif "spice" in missing_fields:
            resume_step = "SPICE"
        elif "pantry" in missing_fields:
            resume_step = "PANTRY"
        elif "language" in missing_fields:
            resume_step = "LANGUAGE"
        else:
            resume_step = "COMPLETE"
        
        return {
            "completed": False,
            "resume_step": resume_step,
            "missing_fields": missing_fields
        }
        
    except Exception as e:
        logger.error(f"Error getting onboarding status: {e}")
        raise


# ============================================================================
# FULL PROFILE AGGREGATION
# ============================================================================

async def get_full_profile(user_id: str) -> Dict[str, Any]:
    """Get complete user profile including all related data"""
    try:
        # Get user record
        user_result = db.client.table("users").select("*").eq("id", user_id).execute()
        user = user_result.data[0] if user_result.data else None
        
        # Get household profile
        profile = await get_household_profile(user_id)
        
        # Get family members
        members = await get_family_members(user_id)
        
        # Aggregate allergens from all members
        all_allergens = set()
        for member in members:
            all_allergens.update(member.get("allergens", []))
        
        # Aggregate dietary restrictions
        all_dietary = set()
        dietary_booleans = {
            "vegetarian": False,
            "vegan": False,
            "no_beef": False,
            "no_pork": False,
            "no_alcohol": False
        }
        
        for member in members:
            restrictions = member.get("dietary_restrictions", [])
            all_dietary.update(restrictions)
            
            # Map to booleans
            if "vegetarian" in restrictions:
                dietary_booleans["vegetarian"] = True
            if "vegan" in restrictions:
                dietary_booleans["vegan"] = True
            if "no_beef" in restrictions or "no beef" in restrictions:
                dietary_booleans["no_beef"] = True
            if "no_pork" in restrictions or "no pork" in restrictions:
                dietary_booleans["no_pork"] = True
            if "no_alcohol" in restrictions or "no alcohol" in restrictions:
                dietary_booleans["no_alcohol"] = True
        
        return {
            "user": user,
            "profile": profile,
            "household": profile,  # Same as profile in current schema
            "members": members,
            "allergens": {
                "declared_allergens": list(all_allergens),
                "enforcement_level": "strict"
            },
            "dietary": dietary_booleans
        }
        
    except Exception as e:
        logger.error(f"Error getting full profile: {e}")
        raise
