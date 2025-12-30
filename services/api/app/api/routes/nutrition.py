"""
Nutrition Evaluation API Routes
Endpoints for nutrition intelligence and health fit scoring
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.models.nutrition import (
    NutritionEvaluationRequest,
    NutritionEvaluationResponse,
    RecipeNutritionEstimate,
    calculate_health_fit_score,
    generate_recipe_badges
)

router = APIRouter(prefix="/nutrition", tags=["nutrition"])


@router.post("/evaluate", response_model=NutritionEvaluationResponse)
async def evaluate_nutrition(req: NutritionEvaluationRequest):
    """
    Evaluate nutrition fit of a recipe for a user profile
    
    This endpoint:
    1. Calculates health fit score based on user's health conditions
    2. Flags positive nutritional aspects and warnings
    3. Determines eligibility (recommended / allowed / avoid)
    4. Generates simple explanation
    
    Example use case:
    - User with diabetes wants to know if a recipe is suitable
    - System scores recipe based on sugar content and other factors
    - Returns 0.85 health fit score with "low_sugar" flag
    """
    try:
        # Calculate health fit score
        scoring = calculate_health_fit_score(
            nutrition=req.nutrition_estimate,
            profile=req.nutrition_profile,
            meal_type=req.meal_type
        )
        
        return NutritionEvaluationResponse(
            per_serving=req.nutrition_estimate,
            health_fit_score=scoring.health_fit_score,
            warnings=scoring.warning_flags,
            positive_flags=scoring.positive_flags,
            eligibility=scoring.eligibility,
            explanation=scoring.explanation
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Nutrition evaluation failed: {str(e)}"
        )


@router.post("/badges")
async def generate_badges(
    nutrition_scoring: Dict[str, Any],
    difficulty_level: int,
    time_minutes: int
):
    """
    Generate up to 3 visual badges for a recipe card
    
    Priority: Nutrition > Skill > Time
    
    Returns badges with:
    - icon (emoji)
    - label (short text)
    - color (green/yellow/red/blue)
    - tooltip (expandable explanation)
    """
    from app.models.nutrition import NutritionScoring
    
    try:
        scoring = NutritionScoring(**nutrition_scoring)
        badges = generate_recipe_badges(scoring, difficulty_level, time_minutes)
        
        return {"badges": [badge.dict() for badge in badges]}
    
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Badge generation failed: {str(e)}"
        )


@router.get("/focus-options")
async def get_nutrition_focus_options():
    """
    Get available nutrition focus options
    Used to populate settings/preferences UI
    """
    return {
        "options": [
            {
                "value": "high_protein",
                "label": "High Protein",
                "description": "Prioritize protein-rich recipes (>30g per serving)"
            },
            {
                "value": "low_sugar",
                "label": "Low Sugar",
                "description": "Minimize added sugars (<8g per serving)"
            },
            {
                "value": "low_sodium",
                "label": "Low Sodium",
                "description": "Reduce sodium for heart health (<400mg per serving)"
            },
            {
                "value": "low_fat",
                "label": "Low Fat",
                "description": "Lower fat content (<10g per serving)"
            },
            {
                "value": "high_fiber",
                "label": "High Fiber",
                "description": "Fiber-rich for digestive health (>8g per serving)"
            },
            {
                "value": "balanced",
                "label": "Balanced",
                "description": "Well-rounded macros with no specific focus"
            }
        ]
    }


@router.get("/health-conditions")
async def get_health_conditions():
    """
    Get supported health conditions for nutrition profiling
    """
    return {
        "conditions": [
            {
                "value": "diabetes",
                "label": "Diabetes",
                "dietary_impact": "Prioritizes low sugar and high fiber recipes"
            },
            {
                "value": "hypertension",
                "label": "High Blood Pressure",
                "dietary_impact": "Focuses on low sodium options"
            },
            {
                "value": "high_cholesterol",
                "label": "High Cholesterol",
                "dietary_impact": "Emphasizes low fat and high fiber"
            },
            {
                "value": "kidney_disease",
                "label": "Kidney Disease",
                "dietary_impact": "Limits protein and sodium"
            },
            {
                "value": "heart_disease",
                "label": "Heart Disease",
                "dietary_impact": "Reduces sodium and saturated fats"
            }
        ]
    }
