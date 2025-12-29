"""
Orchestration rules for deterministic, backend-owned logic (2.3)
Handles repetition controls, ingredient preference, weekly rules, party scaling, hallucination guards
"""
from typing import List, Dict, Any, Set, Optional
from datetime import datetime, timedelta
from collections import Counter

from app.models.config import AppConfiguration, BehaviorSettings
from app.models.inventory import InventoryItem
from app.models.planning import PartySettings


class OrchestrationRules:
    """Backend-owned orchestration rules for meal planning"""
    
    @staticmethod
    def get_recently_used_identifiers(
        history: List[Dict],
        days: int
    ) -> Dict[str, Set[str]]:
        """
        Get recently used recipes, cuisines, and cooking methods within N days
        Returns: {"recipes": {...}, "cuisines": {...}, "methods": {...}}
        """
        cutoff = datetime.utcnow() - timedelta(days=days)
        recent_recipes = set()
        recent_cuisines = set()
        recent_methods = set()
        
        for entry in history:
            cooked_at = entry.get("cooked_at")
            if isinstance(cooked_at, datetime) and cooked_at >= cutoff:
                if "recipe_id" in entry:
                    recent_recipes.add(entry["recipe_id"])
                if "cuisine" in entry:
                    recent_cuisines.add(entry["cuisine"])
                if "cooking_method" in entry:
                    recent_methods.add(entry["cooking_method"])
        
        return {
            "recipes": recent_recipes,
            "cuisines": recent_cuisines,
            "methods": recent_methods
        }
    
    @staticmethod
    def get_expiring_ingredients(
        inventory: List[InventoryItem],
        priority_threshold_days: int = 3
    ) -> List[str]:
        """
        Get list of ingredient inventory_ids that are expiring within threshold days
        These should be prioritized in planning
        """
        expiring = []
        for item in inventory:
            if item.freshness_days_remaining is not None:
                if item.freshness_days_remaining <= priority_threshold_days:
                    expiring.append(item.inventory_id)
        return expiring
    
    @staticmethod
    def apply_weekly_variety_rules(
        cuisine_counts: Dict[str, int],
        max_repeat_per_week: int = 2
    ) -> List[str]:
        """
        Check weekly cuisine variety and return list of cuisines that should be avoided
        (already appeared max times)
        """
        exceeded = []
        for cuisine, count in cuisine_counts.items():
            if count >= max_repeat_per_week:
                exceeded.append(cuisine)
        return exceeded
    
    @staticmethod
    def calculate_party_scaled_amounts(
        base_servings: int,
        guest_count: int,
        buffer_percent: float = 0.10
    ) -> float:
        """
        Calculate scaling factor for party with buffer
        Example: base recipe is 4 servings, party has 20 guests
        -> scaling_factor = (20 / 4) * 1.10 = 5.5
        """
        base_factor = guest_count / base_servings
        return base_factor * (1.0 + buffer_percent)
    
    @staticmethod
    def validate_ingredients_exist(
        recipe_ingredients: List[Dict[str, Any]],
        inventory: List[InventoryItem]
    ) -> Dict[str, Any]:
        """
        Hallucination guard: verify all recipe ingredients_used[*].inventory_id exist in inventory
        Returns: {
            "valid": bool,
            "missing_ids": List[str],
            "error_message": Optional[str]
        }
        """
        inventory_ids = {item.inventory_id for item in inventory}
        missing = []
        
        for ing in recipe_ingredients:
            inv_id = ing.get("inventory_id")
            if inv_id and inv_id not in inventory_ids:
                missing.append(inv_id)
        
        if missing:
            return {
                "valid": False,
                "missing_ids": missing,
                "error_message": f"Recipe references non-existent inventory IDs: {', '.join(missing)}"
            }
        
        return {"valid": True, "missing_ids": [], "error_message": None}
    
    @staticmethod
    def build_variety_constraints(
        behavior_settings: BehaviorSettings,
        history: List[Dict],
        current_weekly_cuisines: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Build comprehensive variety constraints to pass to LLM context
        Returns dict with:
        - avoid_recipes: List[str] - recipe IDs to avoid
        - avoid_cuisines: List[str] - cuisines to avoid
        - avoid_methods: List[str] - cooking methods to avoid
        - rotate_cuisines: bool
        - rotate_methods: bool
        """
        recent = OrchestrationRules.get_recently_used_identifiers(
            history,
            behavior_settings.avoid_repetition_days
        )
        
        constraints = {
            "avoid_recipes": list(recent["recipes"]),
            "avoid_cuisines": list(recent["cuisines"]),
            "avoid_methods": list(recent["methods"]),
            "rotate_cuisines": behavior_settings.rotate_cuisines,
            "rotate_methods": behavior_settings.rotate_methods,
        }
        
        # Weekly-specific: check if any cuisine exceeded max repeats
        if current_weekly_cuisines:
            cuisine_counts = Counter(current_weekly_cuisines)
            exceeded = OrchestrationRules.apply_weekly_variety_rules(
                cuisine_counts,
                behavior_settings.max_repeat_cuisine_per_week
            )
            # Add to avoid list
            constraints["avoid_cuisines"].extend(exceeded)
            constraints["avoid_cuisines"] = list(set(constraints["avoid_cuisines"]))  # dedupe
        
        return constraints
    
    @staticmethod
    def should_enforce_kid_friendly(party_settings: Optional[PartySettings]) -> bool:
        """Check if kid-friendly constraints should be enforced"""
        if party_settings is None:
            return False
        return party_settings.age_group_counts.child_0_12 > 0
    
    @staticmethod
    def calculate_leftover_reuse_schedule(
        plan_days: int,
        reuse_within_days: int = 2
    ) -> Dict[int, List[int]]:
        """
        Calculate which days can reuse leftovers from which previous days
        Returns: {day_index: [source_day_indices_that_can_be_reused]}
        Example: day 2 can reuse from day 0 and 1 if reuse_within_days=2
        """
        schedule = {}
        for day_idx in range(plan_days):
            reusable_from = []
            for source_day in range(max(0, day_idx - reuse_within_days), day_idx):
                reusable_from.append(source_day)
            schedule[day_idx] = reusable_from
        return schedule


def build_orchestration_context(
    config: AppConfiguration,
    inventory: List[InventoryItem],
    history: List[Dict],
    plan_type: str,
    party_settings: Optional[PartySettings] = None,
    weekly_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Build complete orchestration context to inject into LLM prompts
    
    Args:
        config: App configuration
        inventory: Current inventory items
        history: Recipe history
        plan_type: "daily", "party", or "weekly"
        party_settings: Party settings if plan_type == "party"
        weekly_context: Additional weekly planning context (current cuisines, day index, etc.)
    
    Returns:
        Dict with orchestration rules and context
    """
    rules = OrchestrationRules()
    behavior = config.behavior_settings
    
    # Get expiring ingredients
    expiring_ids = rules.get_expiring_ingredients(inventory)
    
    # Get variety constraints
    current_weekly_cuisines = weekly_context.get("current_cuisines", []) if weekly_context else None
    variety = rules.build_variety_constraints(behavior, history, current_weekly_cuisines)
    
    context = {
        "orchestration_rules": {
            "prefer_expiring_ingredients": behavior.prefer_expiring_ingredients,
            "expiring_inventory_ids": expiring_ids,
            "variety_constraints": variety,
        },
        "plan_type": plan_type,
    }
    
    # Party-specific rules
    if plan_type == "party" and party_settings:
        context["party_rules"] = {
            "enforce_kid_friendly": rules.should_enforce_kid_friendly(party_settings),
            "guest_count": party_settings.guest_count,
            "age_distribution": party_settings.age_group_counts.model_dump(),
            "scaling_buffer_percent": 10.0,  # 10% buffer
        }
    
    # Weekly-specific rules
    if plan_type == "weekly" and weekly_context:
        context["weekly_rules"] = {
            "max_repeat_cuisine_per_week": behavior.max_repeat_cuisine_per_week,
            "use_leftovers_within_days": behavior.use_leftovers_within_days,
            "leftover_schedule": rules.calculate_leftover_reuse_schedule(
                weekly_context.get("num_days", 4),
                behavior.use_leftovers_within_days
            ),
            "current_day_index": weekly_context.get("day_index", 0),
        }
    
    return context
