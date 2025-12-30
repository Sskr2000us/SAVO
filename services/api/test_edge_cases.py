"""
Edge Case Testing for Product Intelligence System

Tests critical scenarios:
1. Kids + Diabetes + Mixed Cuisine
2. Conflicting Preferences (Vegan + Keto + Indian)
3. Low Skill + New Experience
"""

import httpx
import json
from typing import Dict, Any

API_BASE = "http://localhost:8000"

def print_section(title: str):
    """Print formatted section header"""
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")


def print_recipe_intelligence(recipe: Dict[str, Any]):
    """Print intelligence data from recipe"""
    print(f"\n🍽  Recipe: {recipe.get('name', 'Unknown')}")
    print(f"   Cuisine: {recipe.get('cuisine', 'Unknown')}")
    print(f"   Time: {recipe.get('estimated_time_minutes', 0)} minutes")
    
    # Badges
    if 'badges' in recipe:
        print(f"\n   📛 Badges:")
        for badge in recipe['badges'][:3]:
            print(f"      • {badge['label']} ({badge['type']})")
    
    # Nutrition Intelligence
    if 'nutrition_intelligence' in recipe:
        ni = recipe['nutrition_intelligence']
        print(f"\n   ✅ Nutrition Intelligence:")
        print(f"      Health Fit Score: {ni['health_fit_score']:.2f}")
        print(f"      Eligibility: {ni['eligibility']}")
        print(f"      Explanation: {ni['explanation']}")
        if ni.get('positive_flags'):
            print(f"      Positive: {', '.join(ni['positive_flags'])}")
        if ni.get('warning_flags'):
            print(f"      Warnings: {', '.join(ni['warning_flags'])}")
    
    # Skill Intelligence
    if 'skill_intelligence' in recipe:
        si = recipe['skill_intelligence']
        print(f"\n   🍳 Skill Intelligence:")
        print(f"      Fit Category: {si['fit_category']}")
        print(f"      Recommendation: {si['recommendation']}")
        if si.get('encouragement'):
            print(f"      Encouragement: {si['encouragement']}")
    
    # Why This Recipe?
    if 'why_this_recipe' in recipe:
        print(f"\n   💡 Why This Recipe:")
        for section in recipe['why_this_recipe']:
            print(f"      {section['icon']} {section['title']}: {section['content'][:60]}...")


async def test_edge_case_1_kids_diabetes_mixed():
    """
    Edge Case 1: Kids + Diabetes + Mixed Cuisine
    
    Expected: 
    - Low sugar recipes (diabetes)
    - Mild spice (kids present)
    - Compatible cuisine mixing if needed
    - Clear health warnings
    """
    print_section("Edge Case 1: Kids + Diabetes + Mixed Cuisine")
    
    request_data = {
        "time_available_minutes": 45,
        "servings": 4,
        "meal_type": "dinner",
        "meal_time": "18:30",
        "inventory": {
            "available_ingredients": [
                "chicken breast",
                "rice",
                "tomatoes",
                "onions",
                "yogurt",
                "mild curry powder",
                "olive oil",
                "garlic",
                "carrots",
                "peas"
            ]
        },
        "family_profile": {
            "members": [
                {
                    "name": "Dad",
                    "age": 38,
                    "age_category": "adult",
                    "health_conditions": ["diabetes"],
                    "medical_dietary_needs": ["low_sugar", "low_carb"],
                    "spice_tolerance": "medium",
                    "dietary_restrictions": [],
                    "allergens": []
                },
                {
                    "name": "Emma",
                    "age": 7,
                    "age_category": "child",
                    "health_conditions": [],
                    "spice_tolerance": "none",
                    "dietary_restrictions": [],
                    "allergens": []
                },
                {
                    "name": "Luke",
                    "age": 10,
                    "age_category": "child",
                    "health_conditions": [],
                    "spice_tolerance": "mild",
                    "dietary_restrictions": [],
                    "allergens": []
                }
            ]
        },
        "cuisine_preferences": ["Indian", "Mediterranean"],
        "selected_cuisine": "auto"
    }
    
    print("📤 Request:")
    print(f"   Family: Dad (diabetes), 2 kids (ages 7, 10)")
    print(f"   Spice Tolerance: None (Emma), Mild (Luke), Medium (Dad)")
    print(f"   Health: Diabetes (low sugar needed)")
    print(f"   Cuisines Preferred: Indian, Mediterranean")
    print(f"   Ingredients: Chicken, rice, tomatoes, yogurt, etc.")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE}/plan/daily",
                json=request_data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            print("\n✅ Response Status:", result.get('status'))
            print(f"   Selected Cuisine: {result.get('selected_cuisine')}")
            
            if 'recipes' in result:
                for recipe in result['recipes'][:2]:  # Show first 2
                    print_recipe_intelligence(recipe)
            
            # Validation
            print("\n🔍 Validation:")
            recipes = result.get('recipes', [])
            if recipes:
                recipe = recipes[0]
                ni = recipe.get('nutrition_intelligence', {})
                
                # Check diabetes-friendly
                if ni.get('health_fit_score', 0) >= 0.7:
                    print("   ✅ Diabetes-friendly (health_fit_score >= 0.7)")
                else:
                    print(f"   ⚠️  Health fit score low: {ni.get('health_fit_score')}")
                
                # Check low sugar warning
                warnings = ni.get('warning_flags', [])
                if 'high_sugar' not in warnings:
                    print("   ✅ No high sugar warnings")
                else:
                    print("   ⚠️  High sugar warning present")
                
                # Check spice level
                if recipe.get('spice_level') in ['none', 'mild']:
                    print("   ✅ Kid-friendly spice level")
                else:
                    print(f"   ⚠️  Spice level may be too high: {recipe.get('spice_level')}")
            
        except httpx.HTTPError as e:
            print(f"\n❌ Error: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   Response: {e.response.text}")


async def test_edge_case_2_conflicting_preferences():
    """
    Edge Case 2: Conflicting Preferences (Vegan + Keto + Indian)
    
    Expected:
    - System flags conflict
    - Suggests closest fit (Indian vegan with low-carb options)
    - Clear explanation of tradeoffs
    """
    print_section("Edge Case 2: Conflicting Preferences (Vegan + Keto + Indian)")
    
    request_data = {
        "time_available_minutes": 40,
        "servings": 2,
        "meal_type": "lunch",
        "meal_time": "13:00",
        "inventory": {
            "available_ingredients": [
                "tofu",
                "cauliflower",
                "spinach",
                "coconut oil",
                "curry leaves",
                "mustard seeds",
                "tomatoes",
                "onions",
                "green beans",
                "turmeric",
                "cumin"
            ]
        },
        "family_profile": {
            "members": [
                {
                    "name": "Sarah",
                    "age": 32,
                    "age_category": "adult",
                    "dietary_restrictions": ["vegan", "keto"],
                    "health_conditions": [],
                    "medical_dietary_needs": ["low_carb", "high_protein"],
                    "allergens": [],
                    "spice_tolerance": "high"
                }
            ]
        },
        "cuisine_preferences": ["Indian"],
        "selected_cuisine": "Indian"
    }
    
    print("📤 Request:")
    print(f"   Dietary: Vegan + Keto (CONFLICT)")
    print(f"   Medical Needs: Low carb + High protein")
    print(f"   Cuisine: Indian")
    print(f"   Ingredients: Tofu, cauliflower, spinach, spices")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE}/plan/daily",
                json=request_data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            print("\n✅ Response Status:", result.get('status'))
            
            if 'recipes' in result:
                for recipe in result['recipes'][:2]:
                    print_recipe_intelligence(recipe)
            
            # Validation
            print("\n🔍 Validation:")
            recipes = result.get('recipes', [])
            if recipes:
                recipe = recipes[0]
                
                # Check vegan
                if 'vegan' in str(recipe.get('dietary_restrictions', [])).lower():
                    print("   ✅ Vegan-friendly")
                
                # Check low carb
                ni = recipe.get('nutrition_intelligence', {})
                if 'low_carb' in ni.get('positive_flags', []):
                    print("   ✅ Low carb (keto-friendly)")
                
                # Check if conflict is acknowledged
                why_sections = recipe.get('why_this_recipe', [])
                has_explanation = any('protein' in s.get('content', '').lower() 
                                    for s in why_sections)
                if has_explanation:
                    print("   ✅ Clear explanation provided")
            
        except httpx.HTTPError as e:
            print(f"\n❌ Error: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   Response: {e.response.text}")


async def test_edge_case_3_low_skill_new_experience():
    """
    Edge Case 3: Low Skill + New Experience
    
    Expected:
    - Same difficulty level maintained
    - New cuisine OR new technique (not both)
    - Encouraging skill nudge
    - Clear skill fit explanation
    """
    print_section("Edge Case 3: Low Skill + New Experience")
    
    request_data = {
        "time_available_minutes": 35,
        "servings": 2,
        "meal_type": "dinner",
        "meal_time": "19:00",
        "inventory": {
            "available_ingredients": [
                "pasta",
                "tomatoes",
                "basil",
                "garlic",
                "olive oil",
                "mozzarella",
                "parmesan",
                "onions"
            ]
        },
        "family_profile": {
            "members": [
                {
                    "name": "Alex",
                    "age": 26,
                    "age_category": "adult",
                    "dietary_restrictions": [],
                    "health_conditions": [],
                    "allergens": [],
                    "spice_tolerance": "medium"
                }
            ],
            "skill_level": 2,  # Basic level
            "confidence_score": 0.6  # Building confidence
        },
        "cuisine_preferences": ["Italian"],
        "selected_cuisine": "auto"  # Let system suggest exploration
    }
    
    print("📤 Request:")
    print(f"   Skill Level: 2 (Basic)")
    print(f"   Confidence: 0.6 (Building)")
    print(f"   Experience: Mostly Italian")
    print(f"   Ingredients: Italian basics (pasta, tomatoes, cheese)")
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{API_BASE}/plan/daily",
                json=request_data,
                timeout=30.0
            )
            response.raise_for_status()
            result = response.json()
            
            print("\n✅ Response Status:", result.get('status'))
            print(f"   Selected Cuisine: {result.get('selected_cuisine')}")
            
            if 'recipes' in result:
                for recipe in result['recipes'][:2]:
                    print_recipe_intelligence(recipe)
            
            # Validation
            print("\n🔍 Validation:")
            recipes = result.get('recipes', [])
            if recipes:
                recipe = recipes[0]
                si = recipe.get('skill_intelligence', {})
                
                # Check skill fit
                fit = si.get('fit_category')
                if fit in ['perfect', 'stretch']:
                    print(f"   ✅ Appropriate skill fit: {fit}")
                else:
                    print(f"   ⚠️  Skill fit: {fit}")
                
                # Check for encouragement
                if si.get('encouragement'):
                    print(f"   ✅ Encouragement provided: {si['encouragement'][:50]}...")
                
                # Check difficulty
                difficulty = recipe.get('difficulty_level', 1)
                if difficulty <= 3:  # Should be 2 or slightly stretch to 3
                    print(f"   ✅ Difficulty appropriate: Level {difficulty}")
                else:
                    print(f"   ⚠️  Difficulty too high: Level {difficulty}")
                
                # Check recipe recommendation
                recommendation = si.get('recommendation', '')
                if 'confidence' in recommendation.lower() or 'learn' in recommendation.lower():
                    print("   ✅ Confidence-building message present")
            
        except httpx.HTTPError as e:
            print(f"\n❌ Error: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   Response: {e.response.text}")


async def main():
    """Run all edge case tests"""
    print("\n" + "="*80)
    print("  PRODUCT INTELLIGENCE EDGE CASE TESTING")
    print("  Testing critical scenarios for nutrition, skill, and cuisine intelligence")
    print("="*80)
    
    await test_edge_case_1_kids_diabetes_mixed()
    await test_edge_case_2_conflicting_preferences()
    await test_edge_case_3_low_skill_new_experience()
    
    print("\n" + "="*80)
    print("  TESTING COMPLETE")
    print("="*80)
    print("\nReview the validations above to ensure:")
    print("  1. Health conditions are respected (diabetes → low sugar)")
    print("  2. Kids get appropriate spice levels")
    print("  3. Conflicting preferences are handled gracefully")
    print("  4. Low skill users get confidence-building recipes")
    print("  5. All intelligence layers provide clear explanations")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
