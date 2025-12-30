"""
Planning endpoints - daily/party/weekly meal planning
"""
from datetime import datetime
from fastapi import APIRouter, HTTPException, status

from app.models.planning import (
    DailyPlanRequest,
    PartyPlanRequest,
    WeeklyPlanRequest,
    MenuPlanResponse,
)
from app.core.storage import get_storage
from app.core.orchestrator import plan_daily, plan_party, plan_weekly
from app.core.orchestration_rules import build_orchestration_context
from app.core.cuisine_metadata import get_cuisine_by_id, CUISINE_METADATA

router = APIRouter()


def _inventory_for_llm(*, storage_inventory, request_inventory) -> list[dict]:
    """Return inventory in the prompt-pack friendly shape.

    The prompt pack expects inventory items like:
    {inventory_id, canonical_name, amount, unit, ...}
    """
    if isinstance(request_inventory, dict):
        available = request_inventory.get("available_ingredients")
        if isinstance(available, list) and available:
            items: list[dict] = []
            for i, name in enumerate(available, start=1):
                if not isinstance(name, str) or not name.strip():
                    continue
                canonical = name.strip()
                items.append(
                    {
                        "inventory_id": f"req_{i}",
                        "canonical_name": canonical,
                        "display_name": canonical,
                        "amount": 1,
                        "unit": "pcs",
                        "state": "raw",
                        "storage": "pantry",
                        "freshness_days_remaining": None,
                        "notes": None,
                    }
                )
            return items

        items_payload = request_inventory.get("items")
        if isinstance(items_payload, list) and items_payload:
            return [i for i in items_payload if isinstance(i, dict)]

    # Default: map storage inventory model -> prompt-pack keys
    mapped: list[dict] = []
    for item in storage_inventory:
        mapped.append(
            {
                "inventory_id": getattr(item, "inventory_id", None),
                "canonical_name": getattr(item, "canonical_name", None),
                "display_name": getattr(item, "display_name", None) or getattr(item, "canonical_name", None),
                "amount": getattr(item, "quantity", None),
                "unit": getattr(item, "unit", None),
                "state": getattr(item, "state", "raw"),
                "storage": getattr(item, "storage", "pantry"),
                "freshness_days_remaining": getattr(item, "freshness_days_remaining", None),
                "notes": getattr(item, "notes", None),
            }
        )
    return mapped


def _build_planning_context(
    request,
    plan_type: str,
    party_settings=None,
    weekly_context=None
):
    """Build complete context for LLM including config, inventory, orchestration rules"""
    storage = get_storage()
    config = storage.get_config()
    inventory = storage.list_inventory()
    history = storage.get_recent_history()
    
    # Get selected cuisine or default to auto
    cuisine = request.selected_cuisine or "auto"
    cuisine_meta = get_cuisine_by_id(cuisine) if cuisine != "auto" else None
    
    # Build orchestration context
    orch_context = build_orchestration_context(
        config=config,
        inventory=inventory,
        history=history,
        plan_type=plan_type,
        party_settings=party_settings,
        weekly_context=weekly_context
    )
    
    # Determine output settings
    output_lang = request.output_language or config.global_settings.primary_language
    measurement = request.measurement_system or config.global_settings.measurement_system
    
    inventory_items = _inventory_for_llm(storage_inventory=inventory, request_inventory=getattr(request, "inventory", None))

    context = {
        "app_configuration": config.model_dump(mode='json'),
        "session_request": request.model_dump(mode='json'),
        "inventory": inventory_items,
        "cuisine_metadata": CUISINE_METADATA,
        "history_context": {
            "recent_recipes": [h for h in history[:20]],
        },
        "output_language": output_lang,
        "measurement_system": measurement,
        "now_utc": datetime.utcnow().isoformat(),
        **orch_context
    }
    
    return context


@router.post("/daily", response_model=MenuPlanResponse)
async def post_daily(req: DailyPlanRequest):
    """Generate daily meal plan with full family profile and preferences"""
    storage = get_storage()
    config = storage.get_config()
    
    context = _build_planning_context(req, "daily")
    context["time_available_minutes"] = req.time_available_minutes
    context["servings"] = req.servings
    
    # Add meal context for better recommendations
    if req.meal_type:
        context["meal_type"] = req.meal_type
    if req.meal_time:
        context["meal_time"] = req.meal_time
    if req.current_date:
        context["current_date"] = req.current_date
    
    # Add family profile with detailed dietary info
    if config and config.household_profile and config.household_profile.members:
        context["family_members"] = [
            {
                "name": m.name,
                "age": m.age,
                "age_category": m.age_category,
                "dietary_restrictions": m.dietary_restrictions,
                "allergens": m.allergens,
                "health_conditions": m.health_conditions,
                "medical_dietary_needs": m.medical_dietary_needs,
                "food_preferences": m.food_preferences,
                "food_dislikes": m.food_dislikes,
                "spice_tolerance": m.spice_tolerance
            }
            for m in config.household_profile.members
        ]
        
        # Add nutrition targets
        if config.household_profile.nutrition_targets:
            context["nutrition_targets"] = config.household_profile.nutrition_targets.model_dump()
    
    # Add cultural and regional preferences
    if config and config.global_settings:
        gs = config.global_settings
        context["region"] = gs.region
        context["culture"] = gs.culture
        context["meal_times"] = gs.meal_times
        
        # Add meal-specific preferences based on meal type
        if req.meal_type == "breakfast" or (req.meal_time and _is_breakfast_time(req.meal_time, gs.meal_times)):
            context["meal_preferences"] = gs.breakfast_preferences
        elif req.meal_type == "lunch" or (req.meal_time and _is_lunch_time(req.meal_time, gs.meal_times)):
            context["meal_preferences"] = gs.lunch_preferences
        elif req.meal_type == "dinner" or (req.meal_time and _is_dinner_time(req.meal_time, gs.meal_times)):
            context["meal_preferences"] = gs.dinner_preferences
    
    result = await plan_daily(context)
    return MenuPlanResponse(**result)


def _is_breakfast_time(time_str: str, meal_times: dict) -> bool:
    """Check if time falls in breakfast range"""
    breakfast_range = meal_times.get("breakfast", "07:00-09:00")
    start, end = breakfast_range.split("-")
    return start <= time_str <= end


def _is_lunch_time(time_str: str, meal_times: dict) -> bool:
    """Check if time falls in lunch range"""
    lunch_range = meal_times.get("lunch", "12:00-14:00")
    start, end = lunch_range.split("-")
    return start <= time_str <= end


def _is_dinner_time(time_str: str, meal_times: dict) -> bool:
    """Check if time falls in dinner range"""
    dinner_range = meal_times.get("dinner", "18:00-21:00")
    start, end = dinner_range.split("-")
    return start <= time_str <= end


@router.post("/party", response_model=MenuPlanResponse)
async def post_party(req: PartyPlanRequest):
    """Generate party meal plan with age-aware constraints"""
    # Validate party settings (Pydantic already validated, but double-check)
    if req.party_settings.guest_count < 2 or req.party_settings.guest_count > 80:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="guest_count must be between 2 and 80"
        )
    
    context = _build_planning_context(
        req,
        "party",
        party_settings=req.party_settings
    )
    context["party_settings"] = req.party_settings.model_dump()
    
    result = await plan_party(context)
    return MenuPlanResponse(**result)


@router.post("/weekly", response_model=MenuPlanResponse)
async def post_weekly(req: WeeklyPlanRequest):
    """Generate weekly meal plan with configurable horizon"""
    storage = get_storage()
    config = storage.get_config()
    
    # Determine timezone with priority: request > config > UTC
    timezone = req.timezone or config.global_settings.timezone or "UTC"
    
    weekly_context = {
        "num_days": req.num_days,
        "start_date": req.start_date.isoformat(),
        "timezone": timezone,
        "current_cuisines": [],  # Will be built up as we plan each day
        "day_index": 0,
    }
    
    context = _build_planning_context(
        req,
        "weekly",
        weekly_context=weekly_context
    )
    
    # Add weekly-specific fields
    context["start_date"] = req.start_date.isoformat()
    context["num_days"] = req.num_days
    context["timezone"] = timezone
    
    if req.time_available_minutes:
        context["time_available_minutes"] = req.time_available_minutes
    if req.servings:
        context["servings"] = req.servings
    
    result = await plan_weekly(context)
    return MenuPlanResponse(**result)
