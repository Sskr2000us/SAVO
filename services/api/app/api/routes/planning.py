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
    weekly_context=None
):
    """Build complete context for LLM including config, inventory, orchestration rules, and intelligence layers"""
    storage = get_storage()
    config = storage.get_config()
    inventory = storage.list_inventory()
    history = storage.get_recent_history()
    
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
        "app_configuration": config.model_dump(mode='json'),
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
async def post_daily(req: DailyPlanRequest):
    """Generate daily meal plan with full family profile and product intelligence"""
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
    
    # Intelligence Layer 2: Build Nutrition Profile from family members
    nutrition_profile = None
    if config and config.household_profile and config.household_profile.members:
        # Aggregate health conditions and dietary needs
        all_health_conditions = []
        all_allergens = []
        all_dietary_restrictions = []
        
        for member in config.household_profile.members:
            if member.health_conditions:
                all_health_conditions.extend(member.health_conditions)
            if member.allergens:
                all_allergens.extend(member.allergens)
            if member.dietary_restrictions:
                all_dietary_restrictions.extend(member.dietary_restrictions)
        
        # Create nutrition profile
        nutrition_profile = UserNutritionProfile(
            daily_targets=config.household_profile.nutrition_targets if hasattr(config.household_profile, "nutrition_targets") else None,
            health_conditions=list(set(all_health_conditions)),  # Unique conditions
            dietary_preferences=list(set(all_dietary_restrictions)),
            allergens=list(set(all_allergens))
        )
        
        # Add to context for LLM
        context["nutrition_intelligence"] = {
            "health_conditions": nutrition_profile.health_conditions,
            "dietary_preferences": nutrition_profile.dietary_preferences,
            "allergens": nutrition_profile.allergens,
            "message": "Please respect these health conditions and allergens in recipe selection and preparation."
        }
        
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
        if hasattr(config.household_profile, "nutrition_targets") and config.household_profile.nutrition_targets:
            context["nutrition_targets"] = config.household_profile.nutrition_targets.model_dump()
    
    # Intelligence Layer 3: Add skill progression context
    user_skill_level = 2  # Default
    user_confidence = 0.7  # Default
    if config and config.household_profile:
        if hasattr(config.household_profile, "skill_level"):
            user_skill_level = config.household_profile.skill_level or 2
        if hasattr(config.household_profile, "confidence_score"):
            user_confidence = config.household_profile.confidence_score or 0.7
    
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
    
    # Generate meal plan
    result = await plan_daily(context)
    
    # Intelligence Layer 4: Post-process recipes with health scores, skill fit, and badges
    if result.get("recipes") and isinstance(result["recipes"], list):
        for recipe in result["recipes"]:
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
