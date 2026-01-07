"""
Decision Intelligence API Router
Provides auto-action recommendations with confidence scoring
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Optional
from uuid import UUID
from pydantic import BaseModel, Field
from datetime import datetime

from ..services.decision_intelligence_service import (
    DecisionIntelligenceService,
    DecisionResult,
    ActionFeedback
)
from ..dependencies import get_supabase_client, get_current_user

router = APIRouter(prefix="/api/decision", tags=["decision"])


# ===== REQUEST/RESPONSE MODELS =====

class EvaluateIngredientRequest(BaseModel):
    """Request to evaluate a single ingredient"""
    ingredient_id: str = Field(..., description="UUID of ingredient to evaluate")
    context: Optional[dict] = Field(None, description="Additional context (meal_plan, dietary_restrictions, etc.)")


class EvaluateInventoryRequest(BaseModel):
    """Request to evaluate entire inventory"""
    limit: int = Field(10, ge=1, le=50, description="Maximum number of results to return")


class ActionFeedbackRequest(BaseModel):
    """User feedback on recommended action"""
    action_id: str = Field(..., description="UUID of the ingredient_action record")
    user_response: str = Field(..., description="User response: accepted, rejected, ignored, modified")
    user_final_action: Optional[str] = Field(None, description="What action user actually took")
    feedback_notes: Optional[str] = Field(None, description="Optional feedback text")


class DecisionRuleCreate(BaseModel):
    """Create new decision rule (admin only)"""
    rule_name: str
    rule_description: str
    conditions: dict
    action: str
    confidence_min: float = Field(ge=0.0, le=1.0)
    auto_apply: bool = False
    priority: int = Field(default=50, ge=1, le=100)
    is_active: bool = True


# ===== ENDPOINTS =====

@router.post("/evaluate-ingredient", response_model=dict, summary="Evaluate single ingredient")
async def evaluate_ingredient(
    request: EvaluateIngredientRequest,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Evaluate a single ingredient and recommend action.
    
    Returns:
        - recommended_action: cook_now, store_better, substitute, buy, do_not_buy, discard, monitor
        - confidence: 0.0 to 1.0
        - reason: Explanation for recommendation
        - auto_apply: Whether action should be automatically applied (confidence >= 0.85)
        - urgency_score: 0-100 prioritization score
    """
    service = DecisionIntelligenceService(supabase)
    
    try:
        result = await service.evaluate_ingredient(
            user_id=UUID(current_user["id"]),
            ingredient_id=UUID(request.ingredient_id),
            context=request.context or {}
        )
        
        return result.to_dict()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate ingredient: {str(e)}"
        )


@router.post("/evaluate-inventory", response_model=List[dict], summary="Evaluate entire inventory")
async def evaluate_inventory(
    request: EvaluateInventoryRequest,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Evaluate all ingredients in user's inventory.
    
    Returns list sorted by urgency_score (highest first).
    Use this to power the "Smart Actions" screen showing prioritized recommendations.
    """
    service = DecisionIntelligenceService(supabase)
    
    try:
        results = await service.evaluate_inventory(
            user_id=UUID(current_user["id"]),
            limit=request.limit
        )
        
        return [r.to_dict() for r in results]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to evaluate inventory: {str(e)}"
        )


@router.get("/recommended-actions", response_model=List[dict], summary="Get action history")
async def get_recommended_actions(
    action_types: Optional[str] = None,
    limit: int = 10,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Get recent recommended actions for user.
    
    Query params:
        - action_types: Comma-separated list (e.g., "cook_now,store_better")
        - limit: Maximum results (default 10)
    
    Returns action history with user responses.
    """
    service = DecisionIntelligenceService(supabase)
    
    try:
        types = action_types.split(",") if action_types else None
        
        actions = await service.get_recommended_actions(
            user_id=UUID(current_user["id"]),
            action_types=types,
            limit=limit
        )
        
        return actions
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve actions: {str(e)}"
        )


@router.post("/apply-action", summary="Record user feedback on action")
async def apply_action(
    request: ActionFeedbackRequest,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Record user feedback on a recommended action.
    
    This updates:
    - ingredient_actions table with user_response
    - decision_rules statistics (acceptance_count, rejection_count)
    - learning_feedback for model improvement
    
    User responses:
        - accepted: User followed recommendation
        - rejected: User dismissed recommendation
        - ignored: User saw but didn't act
        - modified: User took different action
    """
    service = DecisionIntelligenceService(supabase)
    
    try:
        feedback = ActionFeedback(
            action_id=UUID(request.action_id),
            user_response=request.user_response,
            user_final_action=request.user_final_action,
            feedback_notes=request.feedback_notes
        )
        
        success = await service.apply_action_feedback(feedback)
        
        if success:
            return {
                "success": True,
                "message": "Feedback recorded successfully"
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to record feedback"
            )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to apply feedback: {str(e)}"
        )


@router.get("/rules", response_model=List[dict], summary="Get decision rules")
async def get_decision_rules(
    is_active: bool = True,
    action: Optional[str] = None,
    supabase = Depends(get_supabase_client)
):
    """
    Get all decision rules (for debugging/admin).
    
    Query params:
        - is_active: Filter by active status (default true)
        - action: Filter by action type (cook_now, store_better, etc.)
    
    Returns rules with statistics (times_applied, acceptance_rate).
    """
    try:
        query = supabase.table("decision_rules").select("*").eq("is_active", is_active)
        
        if action:
            query = query.eq("action", action)
        
        response = query.order("priority", desc=True).execute()
        
        return response.data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve rules: {str(e)}"
        )


@router.post("/rules", response_model=dict, summary="Create decision rule (admin)")
async def create_decision_rule(
    rule_data: DecisionRuleCreate,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Create new decision rule (admin only).
    
    TODO: Add admin role check
    
    Rule structure:
        - conditions: JSON object defining when rule applies
          Example: {"days_to_expiry": {"$lte": 3}, "category": {"$in": ["vegetables"]}}
        - action: What to recommend (cook_now, store_better, etc.)
        - confidence_min: Minimum confidence to apply this rule
        - auto_apply: Whether to auto-execute (requires confidence >= 0.85)
        - priority: Higher priority rules checked first
    """
    try:
        # TODO: Check if current_user has admin role
        # if not current_user.get("role") == "admin":
        #     raise HTTPException(status_code=403, detail="Admin access required")
        
        rule_dict = {
            "rule_id": f"DI_{rule_data.action.upper()}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "rule_name": rule_data.rule_name,
            "rule_description": rule_data.rule_description,
            "conditions": rule_data.conditions,
            "action": rule_data.action,
            "confidence_min": rule_data.confidence_min,
            "auto_apply": rule_data.auto_apply,
            "priority": rule_data.priority,
            "is_active": rule_data.is_active
        }
        
        response = supabase.table("decision_rules").insert(rule_dict).execute()
        
        return response.data[0]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create rule: {str(e)}"
        )


@router.get("/health", summary="Health check")
async def health_check():
    """Health check endpoint for decision intelligence service"""
    return {
        "status": "healthy",
        "service": "decision_intelligence",
        "timestamp": datetime.now().isoformat()
    }


@router.get("/stats", response_model=dict, summary="Get decision statistics")
async def get_decision_stats(
    days: int = 30,
    current_user: dict = Depends(get_current_user),
    supabase = Depends(get_supabase_client)
):
    """
    Get decision intelligence statistics for user.
    
    Returns:
        - total_recommendations: Total actions recommended
        - acceptance_rate: Percentage of accepted recommendations
        - auto_applied_count: Actions automatically applied
        - by_action_type: Breakdown by action type
    """
    try:
        user_id = UUID(current_user["id"])
        
        # Query ingredient_actions for user
        response = supabase.table("ingredient_actions").select(
            "action, user_response, auto_applied, created_at"
        ).eq("user_id", str(user_id)).gte(
            "created_at", f"now() - interval '{days} days'"
        ).execute()
        
        actions = response.data
        
        # Calculate statistics
        total = len(actions)
        accepted = sum(1 for a in actions if a.get("user_response") == "accepted")
        auto_applied = sum(1 for a in actions if a.get("auto_applied") is True)
        
        # Breakdown by action type
        by_type = {}
        for action in actions:
            action_type = action.get("action", "unknown")
            if action_type not in by_type:
                by_type[action_type] = {"count": 0, "accepted": 0}
            by_type[action_type]["count"] += 1
            if action.get("user_response") == "accepted":
                by_type[action_type]["accepted"] += 1
        
        # Calculate acceptance rates
        for action_type in by_type:
            count = by_type[action_type]["count"]
            accepted_count = by_type[action_type]["accepted"]
            by_type[action_type]["acceptance_rate"] = (
                round(accepted_count / count * 100, 1) if count > 0 else 0.0
            )
        
        return {
            "total_recommendations": total,
            "acceptance_rate": round(accepted / total * 100, 1) if total > 0 else 0.0,
            "auto_applied_count": auto_applied,
            "by_action_type": by_type,
            "period_days": days
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to calculate stats: {str(e)}"
        )
