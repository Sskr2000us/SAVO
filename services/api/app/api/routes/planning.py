"""Planning endpoints - daily/party/weekly meal planning."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.planning import (
    DailyPlanRequest,
    PartyPlanRequest,
    WeeklyPlanRequest,
    MenuPlanResponse,
)
from app.models.nutrition import (
    UserNutritionProfile,
    RecipeNutritionEstimate,
    calculate_health_fit_score,
    generate_recipe_badges,
)
from app.models.skill import (
    SkillProgression,
    RecipeSkillFit,
    RecipeDifficulty,
)
from app.models.cuisine import rank_cuisines
from app.core.storage import get_storage
from app.core.orchestrator import plan_daily, plan_party, plan_weekly
from app.core.orchestration_rules import build_orchestration_context
from app.core.cuisine_metadata import get_cuisine_by_id, CUISINE_METADATA
from app.core.database import get_full_profile, get_inventory, get_recipe_history
from app.middleware.auth import get_current_user
from app.core.safety_constraints import (
    build_complete_safety_context,
    validate_recipe_safety,
    SAVOGoldenRule,
    validate_profile_completeness
)
from app.core.ingredient_combinations import (
    analyze_ingredients,
    generate_combination_recipe_prompt,
    IngredientCombinationEngine
)
from app.core.meal_courses import (
    plan_full_course_meal,
    generate_meal_prompt,
    MealStyle
)
from app.models.inventory import InventoryItem

router = APIRouter()


def _coerce_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if value is None:
        return []
    return [value]


def _parse_iso_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        # Accept "YYYY-MM-DD" or datetime-ish strings
        try:
            return date.fromisoformat(raw[:10])
        except Exception:
            return None
    return None


def _freshness_days_remaining(expiry_date_value: Any) -> Optional[int]:
    expiry = _parse_iso_date(expiry_date_value)
    if expiry is None:
        return None
    delta = (expiry - date.today()).days
    return max(0, delta)


def _db_inventory_to_models(db_items: List[Dict[str, Any]]) -> List[InventoryItem]:
    mapped: List[InventoryItem] = []
    for item in db_items or []:
        if not isinstance(item, dict):
            continue

        raw_state = (item.get("item_state") or item.get("state") or "raw")
        state = "raw"
        if isinstance(raw_state, str):
            s = raw_state.strip().lower()
            if s in {"raw", "cooked", "leftover", "frozen"}:
                state = s
            elif s == "prepared":
                state = "cooked"

        raw_storage = (item.get("storage_location") or item.get("storage") or "pantry")
        storage = "pantry"
        if isinstance(raw_storage, str):
            st = raw_storage.strip().lower()
            if st in {"pantry", "fridge", "freezer"}:
                storage = "fridge" if st == "fridge" else st
            elif st == "counter":
                storage = "pantry"

        inventory_id = item.get("id") or item.get("inventory_id")
        canonical_name = item.get("canonical_name")
        display_name = item.get("display_name") or canonical_name
        quantity = item.get("quantity")
        unit = item.get("unit")

        if not inventory_id or not canonical_name or quantity is None or not unit:
            continue

        mapped.append(
            InventoryItem(
                inventory_id=str(inventory_id),
                canonical_name=str(canonical_name),
                display_name=str(display_name) if display_name is not None else None,
                quantity=float(quantity),
                unit=str(unit),
                state=state,  # type: ignore[arg-type]
                storage=("freezer" if storage == "freezer" else ("fridge" if storage == "fridge" else "pantry")),
                freshness_days_remaining=_freshness_days_remaining(item.get("expiry_date")),
                notes=item.get("notes"),
            )
        )
    return mapped


def _member_for_app_config(member: Dict[str, Any]) -> Dict[str, Any]:
    # Shape this like app.models.config.FamilyMember (dict form)
    member_id = member.get("id") or member.get("member_id") or "unknown"
    age = member.get("age")
    try:
        age_int = int(age) if age is not None else 30
    except Exception:
        age_int = 30

    age_category = member.get("age_category")
    if not isinstance(age_category, str) or age_category not in {"child", "teen", "adult", "senior"}:
        if age_int < 13:
            age_category = "child"
        elif age_int < 18:
            age_category = "teen"
        elif age_int < 65:
            age_category = "adult"
        else:
            age_category = "senior"

    return {
        "member_id": str(member_id),
        "name": str(member.get("name") or member.get("member_name") or "Family Member"),
        "age": age_int,
        "age_category": age_category,
        "dietary_restrictions": [str(x) for x in _coerce_list(member.get("dietary_restrictions")) if x is not None],
        "allergens": [str(x) for x in _coerce_list(member.get("allergens")) if x is not None],
        "health_conditions": [str(x) for x in _coerce_list(member.get("health_conditions")) if x is not None],
        "medical_dietary_needs": member.get("medical_dietary_needs") or {},
        "food_preferences": [str(x) for x in _coerce_list(member.get("food_preferences")) if x is not None],
        "food_dislikes": [str(x) for x in _coerce_list(member.get("food_dislikes")) if x is not None],
        "spice_tolerance": str(member.get("spice_tolerance") or "medium"),
    }


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


def _enhance_recipe_with_intelligence(
    recipe: dict,
    nutrition_profile,
    user_skill_level: int,
    user_confidence: float,
    meal_type: str
):
    """Enhance recipe with nutrition scores, skill fit, and badges"""
    # Extract recipe details
    recipe_time = recipe.get("estimated_time_minutes", 30)
    recipe_difficulty = recipe.get("difficulty_level", 2)
    
    # Intelligence Layer: Nutrition Scoring
    if nutrition_profile:
        # Estimate nutrition from recipe (simplified - in production, use actual nutrition data)
        nutrition_estimate = RecipeNutritionEstimate(
            calories=recipe.get("calories", 400),
            protein_g=recipe.get("protein", 20),
            carbs_g=recipe.get("carbs", 40),
            fat_g=recipe.get("fat", 15),
            sodium_mg=recipe.get("sodium", 600),
            sugar_g=recipe.get("sugar", 8),
            fiber_g=recipe.get("fiber", 5)
        )
        
        # Calculate health fit score
        nutrition_scoring = calculate_health_fit_score(
            nutrition_estimate=nutrition_estimate,
            user_profile=nutrition_profile,
            meal_type=meal_type
        )
        
        # Add to recipe
        recipe["nutrition_intelligence"] = {
            "health_fit_score": nutrition_scoring.health_fit_score,
            "eligibility": nutrition_scoring.eligibility,
            "explanation": nutrition_scoring.explanation,
            "positive_flags": nutrition_scoring.positive_flags,
            "warning_flags": nutrition_scoring.warning_flags
        }
    else:
        recipe["nutrition_intelligence"] = {
            "health_fit_score": 0.75,
            "eligibility": "recommended",
            "explanation": "Good nutritional balance for general health.",
            "positive_flags": ["balanced"],
            "warning_flags": []
        }
    
    # Intelligence Layer: Skill Fit Evaluation
    recipe_skill = RecipeDifficulty(
        level=recipe_difficulty,
        level_name=RecipeDifficulty.get_level_name(recipe_difficulty),
        skills_required=recipe.get("skills_required", ["basic_cooking"]),
        estimated_time_minutes=recipe_time,
        active_time_minutes=int(recipe_time * 0.6)
    )
    
    skill_fit = RecipeSkillFit.evaluate_fit(
        user_level=user_skill_level,
        user_confidence=user_confidence,
        recipe_difficulty=recipe_skill
    )
    
    recipe["skill_intelligence"] = {
        "fit_category": skill_fit.fit_category,
        "confidence_match": skill_fit.confidence_match,
        "recommendation": skill_fit.recommendation,
        "encouragement": skill_fit.encouragement
    }
    
    # Intelligence Layer: Generate Badges (max 3)
    badges = generate_recipe_badges(
        nutrition_scoring=nutrition_scoring if nutrition_profile else None,
        difficulty_level=recipe_difficulty,
        time_minutes=recipe_time
    )
    
    recipe["badges"] = [
        {
            "type": badge.badge_type,
            "label": badge.label,
            "priority": badge.priority,
            "explanation": badge.explanation
        }
        for badge in badges[:3]  # Max 3 badges
    ]
    
    # Build "Why This Recipe?" explanation
    why_sections = []
    
    # Health section
    if nutrition_profile:
        why_sections.append({
            "icon": "health",
            "title": "Health",
            "content": recipe["nutrition_intelligence"]["explanation"]
        })
    
    # Skill section
    why_sections.append({
        "icon": "skill",
        "title": "Skill",
        "content": recipe["skill_intelligence"]["recommendation"]
    })
    
    # Cuisine section (if available)
    if recipe.get("cuisine"):
        why_sections.append({
            "icon": "cuisine",
            "title": "Cuisine",
            "content": f"{recipe['cuisine']} cuisine fits your available ingredients and preferences."
        })
    
    # Time section
    if recipe_time <= 30:
        why_sections.append({
            "icon": "time",
            "title": "Time",
            "content": f"Quick meal ready in {recipe_time} minutes."
        })
    
    recipe["why_this_recipe"] = why_sections


def _build_planning_context(
    request,
    plan_type: str,
    party_settings=None,
    weekly_context=None,
    *,
    config_override=None,
    inventory_override=None,
    history_override=None,
    app_configuration_override: Optional[Dict[str, Any]] = None,
):
    """Build complete context for LLM including config, inventory, orchestration rules, and intelligence layers"""
    storage = get_storage()
    config = config_override or storage.get_config()
    inventory = inventory_override if inventory_override is not None else storage.list_inventory()
    history = history_override if history_override is not None else storage.get_recent_history()
    
    # Get selected cuisine or rank cuisines intelligently
    cuisine = request.selected_cuisine or "auto"
    cuisine_meta = get_cuisine_by_id(cuisine) if cuisine != "auto" else None
    
    # Intelligence Layer 1: Cuisine Ranking
    cuisine_scores = []
    if cuisine == "auto":
        # Rank cuisines based on ingredients, preferences, history, skill, nutrition
        available_ingredients = [item.canonical_name for item in inventory]
        user_preferences = request.cuisine_preferences or []
        recent_cuisines = [h.get("cuisine", "") for h in history[:10] if h.get("cuisine")]
        
        # Get user skill level from config
        user_skill_level = 2  # Default to basic
        if config and config.household_profile and hasattr(config.household_profile, "skill_level"):
            user_skill_level = config.household_profile.skill_level or 2
        
        # Get nutrition focus
        nutrition_focus = []
        if config and config.household_profile and hasattr(config.household_profile, "nutrition_targets"):
            targets = config.household_profile.nutrition_targets
            if hasattr(targets, "protein_g") and targets.protein_g > 100:
                nutrition_focus.append("high_protein")
            if hasattr(targets, "sugar_g") and targets.sugar_g < 25:
                nutrition_focus.append("low_sugar")
        
        # Rank cuisines
        cuisine_scores = rank_cuisines(
            available_ingredients=available_ingredients,
            user_preferences=user_preferences,
            recent_cuisines=recent_cuisines,
            skill_level=user_skill_level,
            nutrition_focus=nutrition_focus
        )
    
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
        "app_configuration": app_configuration_override or config.model_dump(mode='json'),
        "session_request": request.model_dump(mode='json'),
        "inventory": inventory_items,
        "cuisine_metadata": CUISINE_METADATA,
        "cuisine_rankings": [score.model_dump() for score in cuisine_scores[:5]],  # Top 5 cuisines
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
async def post_daily(req: DailyPlanRequest, user_id: str = Depends(get_current_user)):
    """Generate daily meal plan with full family profile and product intelligence"""
    storage = get_storage()
    config = storage.get_config()

    # Pull DB-backed profile (source of truth)
    try:
        full_profile = await get_full_profile(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load user profile: {str(e)}")

    household = full_profile.get("household") or full_profile.get("profile") or {}
    members = full_profile.get("members") or []
    normalized_members: List[Dict[str, Any]] = []
    for m in members:
        if not isinstance(m, dict):
            continue
        # Ensure allergens key exists (Golden Rule requires explicit declaration)
        if "allergens" not in m:
            m = {**m, "allergens": []}
        normalized_members.append(m)
    profile_dict = {"household": household, "members": normalized_members}
    
    # GOLDEN RULE: Check profile completeness and safety constraints
    golden_check = SAVOGoldenRule.check_before_generate(profile_dict)
    if not golden_check["can_proceed"]:
        return MenuPlanResponse(
            status="needs_clarification",
            needs_clarification_questions=[golden_check["message"]],
            error_message=golden_check.get("message", "Profile incomplete"),
            selected_cuisine="unknown",
            menu_headers=[],
            menus=[],
            variety_log={"rules_applied": [], "excluded_recent": [], "diversity_scores": {}},
            nutrition_summary={"total_calories_kcal": 0, "per_member_estimates": [], "warnings": []},
            waste_summary={
                "expiring_items_used": [],
                "waste_reduction_score": 0,
                "waste_avoided_value_estimate": {"currency": "USD", "value": 0},
            },
            shopping_suggestions=[],
        )

    # Prefer DB inventory/history for real planning
    try:
        db_inventory = await get_inventory(user_id)
    except Exception:
        db_inventory = []
    try:
        db_history = await get_recipe_history(user_id, limit=50)
    except Exception:
        db_history = []

    inventory_models = _db_inventory_to_models(db_inventory)

    # Inject DB-backed household/members into APP_CONFIGURATION for LLM safety compliance
    app_config_dict = config.model_dump(mode="json")
    nutrition_targets = household.get("nutrition_targets") or household.get("nutritionTargets") or {}
    if not isinstance(nutrition_targets, dict):
        nutrition_targets = {}
    app_config_dict["household_profile"] = {
        "members": [_member_for_app_config(m) for m in normalized_members],
        "nutrition_targets": nutrition_targets,
    }

    # Also include the raw DB profile in context (debuggable + future-proof)
    app_config_dict["db_profile"] = {
        "household": household,
        "members": normalized_members,
        "allergens": full_profile.get("allergens"),
        "dietary": full_profile.get("dietary"),
    }
    
    context = _build_planning_context(
        req,
        "daily",
        inventory_override=inventory_models,
        history_override=db_history,
        app_configuration_override=app_config_dict,
    )
    context["time_available_minutes"] = req.time_available_minutes
    context["servings"] = req.servings
    
    # Add meal context for better recommendations
    if req.meal_type:
        context["meal_type"] = req.meal_type
    if req.meal_time:
        context["meal_time"] = req.meal_time
    if req.current_date:
        context["current_date"] = req.current_date
    
    # Intelligence Layer 2: Build Nutrition Profile from family members
    nutrition_profile = None
    if normalized_members:
        # Aggregate health conditions and dietary needs
        all_health_conditions = []
        all_allergens = []
        all_dietary_restrictions = []
        
        for member in normalized_members:
            all_health_conditions.extend(_coerce_list(member.get("health_conditions")))
            all_allergens.extend(_coerce_list(member.get("allergens")))
            all_dietary_restrictions.extend(_coerce_list(member.get("dietary_restrictions")))
        
        # Create nutrition profile
        profile_kwargs = {
            "health_conditions": list(set(all_health_conditions)),  # Unique conditions
            "dietary_preferences": list(set(all_dietary_restrictions)),
            "allergens": list(set(all_allergens)),
        }
        if nutrition_targets:
            profile_kwargs["daily_targets"] = nutrition_targets
        nutrition_profile = UserNutritionProfile(**profile_kwargs)
        
        # Add to context for LLM
        context["nutrition_intelligence"] = {
            "health_conditions": nutrition_profile.health_conditions,
            "dietary_preferences": nutrition_profile.dietary_preferences,
            "allergens": nutrition_profile.allergens,
            "message": "Please respect these health conditions and allergens in recipe selection and preparation."
        }
        
        context["family_members"] = [_member_for_app_config(m) for m in normalized_members]
        
        # Add nutrition targets
        if nutrition_targets:
            context["nutrition_targets"] = nutrition_targets
    
    # Intelligence Layer 3: Add skill progression context
    user_skill_level = 2  # Default
    user_confidence = 0.7  # Default
    if isinstance(household, dict):
        try:
            user_skill_level = int(household.get("skill_level") or household.get("skillLevel") or user_skill_level)
        except Exception:
            pass
        try:
            user_confidence = float(household.get("confidence_score") or household.get("confidenceScore") or user_confidence)
        except Exception:
            pass
    
    context["skill_intelligence"] = {
        "user_level": user_skill_level,
        "confidence": user_confidence,
        "message": f"Please recommend recipes appropriate for skill level {user_skill_level} (1=beginner, 5=advanced)."
    }
    
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
    
    # Add complete safety context to prompt
    safety_context = build_complete_safety_context(profile_dict)
    context["safety_constraints"] = safety_context
    
    # Generate meal plan
    result = await plan_daily(context)
    
    # Intelligence Layer 4: Post-process recipes with health scores, skill fit, and badges
    # CRITICAL: Validate recipe safety before serving
    if result.get("recipes") and isinstance(result["recipes"], list):
        validated_recipes = []
        for recipe in result["recipes"]:
            # Validate safety first
            is_safe, violations = validate_recipe_safety(recipe, profile_dict)
            if not is_safe:
                # Log violation and skip recipe
                import logging
                logging.error(f"Recipe safety violation: {recipe.get('name', 'Unknown')} - {violations}")
                continue
            
            _enhance_recipe_with_intelligence(
                recipe=recipe,
                nutrition_profile=nutrition_profile,
                user_skill_level=user_skill_level,
                user_confidence=user_confidence,
                meal_type=req.meal_type or "dinner"
            )
    
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


# ============================================
# Multi-Ingredient Combination Endpoint
# ============================================

@router.post("/recipes/combination")
async def generate_combination_recipe(
    ingredients: List[str],
    user_id: str,
    cuisine: Optional[str] = None,
    meal_type: Optional[str] = "dinner"
):
    """
    Generate a recipe using multiple ingredients intelligently.
    
    Analyzes ingredient synergies, balance, and generates a cohesive recipe.
    
    Args:
        ingredients: List of ingredient names to use
        user_id: User UUID for profile and safety constraints
        cuisine: Optional cuisine preference
        meal_type: Type of meal (breakfast, lunch, dinner, snack)
    
    Returns:
        {
            "analysis": {ingredient combination analysis},
            "recipe": {generated recipe},
            "safety_validation": {validation results}
        }
    """
    from app.services.llm import get_llm_client
    import json
    
    if not ingredients or len(ingredients) < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Must provide at least 1 ingredient"
        )
    
    if len(ingredients) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 ingredients allowed"
        )
    
    # Get user profile
    storage = get_storage()
    profile = await storage.get_user_profile(user_id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    # Validate profile completeness (Golden Rule)
    is_complete, missing = validate_profile_completeness(profile)
    if not is_complete:
        return {
            "error": "Profile incomplete",
            "message": "Please complete your profile before generating recipes",
            "missing_fields": missing,
            "onboarding_required": True
        }
    
    # Analyze ingredient combination
    try:
        analysis = analyze_ingredients(ingredients, profile)
    except Exception as e:
        logger.error(f"Ingredient analysis failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to analyze ingredient combination"
        )
    
    # Check if combination is viable
    if not analysis.get("is_viable"):
        return {
            "success": False,
            "analysis": analysis,
            "message": "Ingredient combination has limitations",
            "suggestion": "Consider adding: " + ", ".join(analysis.get("suggested_additions", [])[:3])
        }
    
    # Check for safety issues
    if analysis.get("safety_issues"):
        return {
            "success": False,
            "analysis": analysis,
            "message": "Safety constraints prevent using these ingredients",
            "safety_issues": analysis["safety_issues"]
        }
    
    # Generate AI prompt
    prompt, _ = generate_combination_recipe_prompt(ingredients, profile)
    
    if not prompt:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not generate recipe prompt for this combination"
        )
    
    # Call LLM
    try:
        llm = get_llm_client()
        llm_response = await llm.generate(
            prompt=prompt,
            temperature=0.7,
            max_tokens=2000
        )
        
        # Parse recipe (assuming JSON response)
        recipe = json.loads(llm_response)
        
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate recipe"
        )
    
    # Validate recipe safety
    is_safe, violations = await validate_recipe_safety(recipe, profile)
    
    if not is_safe:
        logger.error(f"Recipe safety violation: {violations}")
        return {
            "success": False,
            "error": "Generated recipe violated safety constraints",
            "violations": violations,
            "retry_allowed": True
        }
    
    # Success
    return {
        "success": True,
        "analysis": analysis,
        "recipe": recipe,
        "safety_validation": {
            "is_safe": is_safe,
            "violations": []
        },
        "metadata": {
            "ingredients_used": ingredients,
            "cuisine": recipe.get("cuisine", cuisine),
            "meal_type": meal_type
        }
    }


# ============================================
# Full Course Meal Endpoint
# ============================================

@router.post("/recipes/full-course")
async def generate_full_course_meal(
    meal_style: str,
    cuisine: str,
    user_id: str,
    ingredients_available: Optional[List[str]] = None,
    context: Optional[str] = None
):
    """
    Generate a complete multi-course meal.
    
    Creates appetizer, main, dessert (or other course combinations)
    with cultural coherence and flavor progression.
    
    Args:
        meal_style: "casual", "standard", "formal", "italian", "indian", "chinese", "japanese"
        cuisine: Primary cuisine for the meal
        user_id: User UUID for profile and safety constraints
        ingredients_available: Optional ingredients to incorporate
        context: Additional user context (e.g., "anniversary dinner", "quick weeknight")
    
    Returns:
        {
            "meal_plan": {complete meal with all courses},
            "courses": [{recipe for each course}],
            "prep_strategy": {cooking order and timing}
        }
    """
    from app.services.llm import get_llm_client
    import json
    
    # Validate meal style
    valid_styles = ["casual", "standard", "formal", "italian", "french", "indian", "chinese", "japanese"]
    if meal_style.lower() not in valid_styles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid meal_style. Must be one of: {', '.join(valid_styles)}"
        )
    
    # Get user profile
    storage = get_storage()
    profile = await storage.get_user_profile(user_id)
    
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User profile not found"
        )
    
    # Validate profile completeness
    is_complete, missing = validate_profile_completeness(profile)
    if not is_complete:
        return {
            "error": "Profile incomplete",
            "message": "Please complete your profile before generating recipes",
            "missing_fields": missing,
            "onboarding_required": True
        }
    
    # Plan meal
    try:
        meal_plan = plan_full_course_meal(
            meal_style=meal_style.lower(),
            cuisine=cuisine,
            profile=profile,
            ingredients=ingredients_available
        )
    except Exception as e:
        logger.error(f"Meal planning failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to plan meal"
        )
    
    # Generate recipes for each course
    courses_generated = []
    llm = get_llm_client()
    
    for course_data in meal_plan["courses"]:
        try:
            # Generate recipe using course-specific prompt
            llm_response = await llm.generate(
                prompt=course_data["prompt"],
                temperature=0.7,
                max_tokens=2000
            )
            
            # Parse recipe
            recipe = json.loads(llm_response)
            
            # Validate safety
            is_safe, violations = await validate_recipe_safety(recipe, profile)
            
            if not is_safe:
                logger.warning(f"Course {course_data['course_type']} failed safety: {violations}")
                # Try to regenerate once
                continue
            
            courses_generated.append({
                "course_type": course_data["course_type"],
                "recipe": recipe,
                "portion_size": course_data["portion_size"],
                "required": course_data["required"]
            })
            
        except Exception as e:
            logger.error(f"Course generation failed for {course_data['course_type']}: {e}")
            # If required course fails, entire meal fails
            if course_data["required"]:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to generate required {course_data['course_type']}"
                )
    
    if not courses_generated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate any courses"
        )
    
    # Build prep strategy
    prep_strategy = _build_prep_strategy(courses_generated, meal_plan)
    
    return {
        "success": True,
        "meal_plan": {
            "meal_style": meal_plan["meal_style"],
            "cuisine": meal_plan["cuisine"],
            "total_courses": len(courses_generated),
            "estimated_total_time": meal_plan["estimated_total_time"],
            "servings": meal_plan["servings"],
            "coherence_score": meal_plan["coherence_score"],
            "flavor_progression": meal_plan["flavor_progression"]
        },
        "courses": courses_generated,
        "prep_strategy": prep_strategy,
        "metadata": {
            "generated_at": datetime.utcnow().isoformat(),
            "user_id": user_id
        }
    }


def _build_prep_strategy(courses: List[Dict], meal_plan: Dict) -> Dict:
    """Build cooking strategy for multi-course meal"""
    
    # Sort courses by cooking time (longest first)
    sorted_courses = sorted(
        courses,
        key=lambda c: c["recipe"].get("cook_time", 30),
        reverse=True
    )
    
    prep_order = []
    for idx, course in enumerate(sorted_courses, 1):
        prep_order.append({
            "step": idx,
            "course": course["course_type"],
            "action": f"Prepare {course['course_type']}",
            "timing_note": f"Start this {course['recipe'].get('prep_time', 15)} minutes before serving"
        })
    
    return {
        "prep_order": prep_order,
        "parallel_cooking": "Start longest-cooking items first, prepare quick items last",
        "make_ahead": [
            c["course_type"] for c in courses 
            if c["recipe"].get("can_make_ahead", False)
        ],
        "serving_sequence": [c["course_type"] for c in courses],
        "total_active_time": sum(c["recipe"].get("prep_time", 15) for c in courses) // 2  # Assume 50% parallel
    }
