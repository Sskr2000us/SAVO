"""
Decision Intelligence Service
Provides auto-action engine, confidence thresholds, and decision rule evaluation
"""

from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta
from dataclasses import dataclass
from supabase import Client

@dataclass
class DecisionResult:
    """Result of a decision evaluation"""
    ingredient_id: UUID
    ingredient_name: str
    recommended_action: str  # cook_now, store_better, substitute, buy, do_not_buy, discard, monitor
    confidence: float
    reason: str
    auto_apply: bool
    decision_rule_id: Optional[UUID] = None
    decision_context: Optional[Dict[str, Any]] = None
    urgency_score: float = 0.0  # 0-100, higher = more urgent
    
    def to_dict(self) -> dict:
        return {
            "ingredient_id": str(self.ingredient_id),
            "ingredient_name": self.ingredient_name,
            "recommended_action": self.recommended_action,
            "confidence": self.confidence,
            "reason": self.reason,
            "auto_apply": self.auto_apply,
            "decision_rule_id": str(self.decision_rule_id) if self.decision_rule_id else None,
            "decision_context": self.decision_context,
            "urgency_score": self.urgency_score
        }


@dataclass
class ActionFeedback:
    """User feedback on a recommended action"""
    action_id: UUID
    user_response: str  # accepted, rejected, ignored, modified
    user_final_action: Optional[str] = None
    feedback_notes: Optional[str] = None


class DecisionIntelligenceService:
    """
    Decision Intelligence Service
    
    Evaluates ingredients and makes auto-action recommendations based on:
    - Freshness scores
    - Expiry dates
    - Storage conditions
    - User preferences
    - Decision rules
    """
    
    def __init__(self, supabase_client: Client):
        self.db = supabase_client
        
        # Confidence thresholds
        self.confidence_thresholds = {
            "auto_action": 0.85,      # Execute automatically
            "suggest_action": 0.60,   # Suggest to user
            "ask_user": 0.60          # Request confirmation
        }
    
    async def evaluate_ingredient(
        self,
        user_id: UUID,
        ingredient_id: UUID,
        context: Optional[Dict[str, Any]] = None
    ) -> DecisionResult:
        """
        Evaluate a single ingredient and recommend action
        
        Steps:
        1. Gather ingredient intelligence (freshness, expiry, storage)
        2. Apply decision rules in priority order
        3. Calculate confidence score
        4. Determine if auto-apply or suggest
        5. Log decision for learning
        
        Args:
            user_id: User performing the evaluation
            ingredient_id: Ingredient to evaluate
            context: Optional context (inventory_item, recipe, etc.)
        
        Returns:
            DecisionResult with recommended action
        """
        
        # Get ingredient intelligence
        ingredient_data = await self._gather_ingredient_intelligence(
            user_id, ingredient_id, context
        )
        
        # Get applicable decision rules
        matching_rules = await self._find_matching_rules(ingredient_data)
        
        if not matching_rules:
            # No matching rules = monitor
            return DecisionResult(
                ingredient_id=ingredient_id,
                ingredient_name=ingredient_data.get("name", "Unknown"),
                recommended_action="monitor",
                confidence=0.50,
                reason="Ingredient is in good condition. No immediate action needed.",
                auto_apply=False,
                urgency_score=0.0
            )
        
        # Select best rule (highest priority)
        best_rule = matching_rules[0]
        
        # Calculate confidence
        confidence = self._calculate_confidence(ingredient_data, best_rule)
        
        # Determine auto-apply
        auto_apply = (
            confidence >= self.confidence_thresholds["auto_action"]
            and best_rule["auto_apply"]
        )
        
        # Calculate urgency score
        urgency_score = self._calculate_urgency_score(ingredient_data, best_rule)
        
        # Create decision result
        result = DecisionResult(
            ingredient_id=ingredient_id,
            ingredient_name=ingredient_data.get("name", "Unknown"),
            recommended_action=best_rule["action"],
            confidence=confidence,
            reason=self._format_explanation(best_rule["explanation_template"], ingredient_data),
            auto_apply=auto_apply,
            decision_rule_id=best_rule["id"],
            decision_context=ingredient_data,
            urgency_score=urgency_score
        )
        
        # Log decision
        await self._log_decision(user_id, result)
        
        return result
    
    async def evaluate_inventory(
        self,
        user_id: UUID,
        limit: int = 10
    ) -> List[DecisionResult]:
        """
        Evaluate all ingredients in user's inventory
        
        Args:
            user_id: User ID
            limit: Maximum number of results to return
        
        Returns:
            List of DecisionResult sorted by urgency
        """
        
        # Get user inventory
        inventory = await self._get_user_inventory(user_id, limit)
        
        # Evaluate each item
        decisions = []
        for item in inventory:
            try:
                decision = await self.evaluate_ingredient(
                    user_id,
                    item["ingredient_id"],
                    {"inventory_item": item}
                )
                decisions.append(decision)
            except Exception as e:
                print(f"Error evaluating ingredient {item.get('ingredient_id')}: {e}")
                continue
        
        # Sort by urgency (highest first)
        decisions.sort(key=lambda d: d.urgency_score, reverse=True)
        
        return decisions[:limit]
    
    async def apply_action_feedback(
        self,
        feedback: ActionFeedback
    ) -> bool:
        """
        Record user feedback on a recommended action
        
        Args:
            feedback: ActionFeedback with user response
        
        Returns:
            True if feedback recorded successfully
        """
        
        # Update action record
        await self.db.table("ingredient_actions").update({
            "user_response": feedback.user_response,
            "user_final_action": feedback.user_final_action,
            "feedback_notes": feedback.feedback_notes,
            "responded_at": datetime.utcnow().isoformat()
        }).eq("id", str(feedback.action_id)).execute()
        
        # Update decision rule statistics
        action = await self._get_action(feedback.action_id)
        if action and action["decision_rule_id"]:
            was_accepted = feedback.user_response == "accepted"
            await self._update_rule_statistics(
                action["decision_rule_id"],
                was_accepted
            )
        
        # Create learning feedback
        await self._create_learning_feedback(feedback)
        
        return True
    
    async def get_recommended_actions(
        self,
        user_id: UUID,
        action_types: Optional[List[str]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get recent recommended actions for a user
        
        Args:
            user_id: User ID
            action_types: Optional filter by action types
            limit: Maximum results
        
        Returns:
            List of action records
        """
        
        query = self.db.table("ingredient_actions").select("*").eq("user_id", str(user_id))
        
        if action_types:
            query = query.in_("recommended_action", action_types)
        
        response = query.order("recommended_at", desc=True).limit(limit).execute()
        
        return response.data
    
    # ========================================
    # PRIVATE HELPER METHODS
    # ========================================
    
    async def _gather_ingredient_intelligence(
        self,
        user_id: UUID,
        ingredient_id: UUID,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Gather all relevant ingredient data for decision-making"""
        
        # Get ingredient details
        ingredient = await self.db.table("master_ingredients").select("*").eq("id", str(ingredient_id)).single().execute()
        
        ingredient_data = ingredient.data if ingredient.data else {}
        
        # Get inventory item if available
        inventory_item = None
        if context and "inventory_item" in context:
            inventory_item = context["inventory_item"]
        else:
            # Try to find in user inventory
            inv_response = await self.db.table("user_inventory").select("*").eq(
                "user_id", str(user_id)
            ).eq("ingredient_id", str(ingredient_id)).execute()
            
            if inv_response.data:
                inventory_item = inv_response.data[0]
        
        # Calculate freshness score
        freshness_score = self._calculate_freshness_score(ingredient_data, inventory_item)
        
        # Calculate days to expiry
        days_to_expiry = self._calculate_days_to_expiry(inventory_item)
        
        # Calculate storage quality
        storage_quality = self._calculate_storage_quality(ingredient_data, inventory_item)
        
        return {
            "id": ingredient_id,
            "name": ingredient_data.get("name", "Unknown"),
            "category": ingredient_data.get("category", "unknown"),
            "ingredient_type": ingredient_data.get("ingredient_type", "single_ingredient"),
            "freshness_score": freshness_score,
            "days_to_expiry": days_to_expiry,
            "storage_quality": storage_quality,
            "inventory_item": inventory_item,
            "storage_conditions": ingredient_data.get("storage_conditions", {}),
            "shelf_life_days": ingredient_data.get("shelf_life_days", {}),
            "waste_risk_level": ingredient_data.get("waste_risk_level", "medium"),
            "spoilage_signs": ingredient_data.get("spoilage_signs", [])
        }
    
    async def _find_matching_rules(
        self,
        ingredient_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Find all decision rules that match ingredient data"""
        
        # Get all active rules sorted by priority
        response = await self.db.table("decision_rules").select("*").eq(
            "is_active", True
        ).order("priority", desc=False).execute()
        
        rules = response.data if response.data else []
        
        # Filter rules by conditions
        matching_rules = []
        for rule in rules:
            if self._rule_matches(rule, ingredient_data):
                matching_rules.append(rule)
        
        return matching_rules
    
    def _rule_matches(
        self,
        rule: Dict[str, Any],
        ingredient_data: Dict[str, Any]
    ) -> bool:
        """Check if a rule's conditions match ingredient data"""
        
        conditions = rule.get("conditions", {})
        
        for key, value in conditions.items():
            # Handle min/max conditions
            if key.endswith("_min"):
                data_key = key[:-4]  # Remove _min suffix
                if ingredient_data.get(data_key, 0) < value:
                    return False
            
            elif key.endswith("_max"):
                data_key = key[:-4]  # Remove _max suffix
                if ingredient_data.get(data_key, float('inf')) > value:
                    return False
            
            # Handle exact match conditions
            elif key in ingredient_data:
                if ingredient_data[key] != value:
                    return False
        
        return True
    
    def _calculate_confidence(
        self,
        ingredient_data: Dict[str, Any],
        rule: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for a decision"""
        
        base_confidence = rule.get("confidence_min", 0.85)
        
        # Adjust based on data quality
        adjustments = 0.0
        
        # Boost confidence if we have inventory data
        if ingredient_data.get("inventory_item"):
            adjustments += 0.05
        
        # Boost confidence if freshness score is clear
        freshness = ingredient_data.get("freshness_score", 0.5)
        if freshness > 0.80 or freshness < 0.30:
            adjustments += 0.05
        
        # Reduce confidence if data is uncertain
        if ingredient_data.get("days_to_expiry") is None:
            adjustments -= 0.10
        
        # Calculate final confidence
        confidence = min(1.0, max(0.0, base_confidence + adjustments))
        
        return round(confidence, 2)
    
    def _calculate_urgency_score(
        self,
        ingredient_data: Dict[str, Any],
        rule: Dict[str, Any]
    ) -> float:
        """Calculate urgency score (0-100)"""
        
        urgency = 0.0
        
        # High urgency for near expiry
        days_to_expiry = ingredient_data.get("days_to_expiry", 999)
        if days_to_expiry is not None:
            if days_to_expiry <= 0:
                urgency += 50
            elif days_to_expiry <= 1:
                urgency += 40
            elif days_to_expiry <= 2:
                urgency += 30
            elif days_to_expiry <= 5:
                urgency += 20
        
        # High urgency for low freshness
        freshness = ingredient_data.get("freshness_score", 1.0)
        if freshness < 0.30:
            urgency += 30
        elif freshness < 0.50:
            urgency += 20
        elif freshness < 0.70:
            urgency += 10
        
        # High urgency for discard action
        if rule["action"] == "discard":
            urgency += 20
        elif rule["action"] == "cook_now":
            urgency += 15
        
        return min(100.0, urgency)
    
    def _calculate_freshness_score(
        self,
        ingredient_data: Dict[str, Any],
        inventory_item: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate freshness score (0.0-1.0)"""
        
        if not inventory_item:
            return 0.70  # Default moderate freshness
        
        # Get purchase/scan date
        added_date = inventory_item.get("added_date") or inventory_item.get("created_at")
        if not added_date:
            return 0.70
        
        if isinstance(added_date, str):
            added_date = datetime.fromisoformat(added_date.replace('Z', '+00:00'))
        
        # Get shelf life
        shelf_life_days = ingredient_data.get("shelf_life_days", {}).get("fresh", 7)
        
        # Calculate age in days
        age_days = (datetime.now() - added_date).days
        
        # Calculate freshness (linear decay)
        freshness = max(0.0, 1.0 - (age_days / shelf_life_days))
        
        return round(freshness, 2)
    
    def _calculate_days_to_expiry(
        self,
        inventory_item: Optional[Dict[str, Any]]
    ) -> Optional[int]:
        """Calculate days until expiry"""
        
        if not inventory_item or not inventory_item.get("expiry_date"):
            return None
        
        expiry_date = inventory_item["expiry_date"]
        if isinstance(expiry_date, str):
            expiry_date = datetime.fromisoformat(expiry_date.replace('Z', '+00:00'))
        
        days_to_expiry = (expiry_date - datetime.now()).days
        
        return days_to_expiry
    
    def _calculate_storage_quality(
        self,
        ingredient_data: Dict[str, Any],
        inventory_item: Optional[Dict[str, Any]]
    ) -> float:
        """Calculate storage quality score (0.0-1.0)"""
        
        if not inventory_item:
            return 0.70  # Default moderate quality
        
        storage_conditions = ingredient_data.get("storage_conditions", {})
        current_storage = inventory_item.get("storage_location", "pantry")
        
        # Simple scoring based on storage match
        if current_storage in ["refrigerator", "freezer"]:
            return 0.85
        elif current_storage in ["pantry", "cabinet"]:
            return 0.70
        else:
            return 0.60
    
    def _format_explanation(
        self,
        template: str,
        ingredient_data: Dict[str, Any]
    ) -> str:
        """Format explanation template with ingredient data"""
        
        # Simple template replacement
        explanation = template
        
        # Replace common placeholders
        replacements = {
            "[INGREDIENT]": ingredient_data.get("name", "ingredient"),
            "[DAYS]": str(ingredient_data.get("days_to_expiry", "?")),
            "[FRESHNESS]": f"{ingredient_data.get('freshness_score', 0.5) * 100:.0f}%"
        }
        
        for placeholder, value in replacements.items():
            explanation = explanation.replace(placeholder, value)
        
        return explanation
    
    async def _log_decision(
        self,
        user_id: UUID,
        decision: DecisionResult
    ) -> UUID:
        """Log decision to ingredient_actions table"""
        
        action_data = {
            "user_id": str(user_id),
            "ingredient_id": str(decision.ingredient_id),
            "decision_rule_id": str(decision.decision_rule_id) if decision.decision_rule_id else None,
            "recommended_action": decision.recommended_action,
            "confidence": decision.confidence,
            "reason": decision.reason,
            "decision_context": decision.decision_context,
            "was_auto_applied": decision.auto_apply,
            "recommended_at": datetime.utcnow().isoformat()
        }
        
        response = await self.db.table("ingredient_actions").insert(action_data).execute()
        
        if response.data:
            return UUID(response.data[0]["id"])
        
        return None
    
    async def _get_user_inventory(
        self,
        user_id: UUID,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get user's inventory items"""
        
        response = await self.db.table("user_inventory").select("*").eq(
            "user_id", str(user_id)
        ).limit(limit).execute()
        
        return response.data if response.data else []
    
    async def _get_action(self, action_id: UUID) -> Optional[Dict[str, Any]]:
        """Get action record by ID"""
        
        response = await self.db.table("ingredient_actions").select("*").eq(
            "id", str(action_id)
        ).single().execute()
        
        return response.data if response.data else None
    
    async def _update_rule_statistics(
        self,
        rule_id: UUID,
        was_accepted: bool
    ):
        """Update decision rule statistics"""
        
        # Call database function
        await self.db.rpc("update_decision_rule_stats", {
            "p_rule_id": str(rule_id),
            "p_was_accepted": was_accepted
        }).execute()
    
    async def _create_learning_feedback(
        self,
        feedback: ActionFeedback
    ):
        """Create learning feedback record"""
        
        # Get action details
        action = await self._get_action(feedback.action_id)
        
        if not action:
            return
        
        feedback_data = {
            "user_id": action["user_id"],
            "feedback_type": "decision_accept" if feedback.user_response == "accepted" else "decision_reject",
            "source_entity_type": "ingredient_action",
            "source_entity_id": str(feedback.action_id),
            "was_correct": feedback.user_response == "accepted",
            "confidence_at_decision": action.get("confidence"),
            "correction_data": {
                "user_response": feedback.user_response,
                "user_final_action": feedback.user_final_action,
                "feedback_notes": feedback.feedback_notes
            }
        }
        
        await self.db.table("learning_feedback").insert(feedback_data).execute()
