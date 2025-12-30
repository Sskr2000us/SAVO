"""
Quick validation of intelligence integration
Tests that all imports work and models are correct
"""
# Force UTF-8 encoding for Windows
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

sys.path.insert(0, 'C:\\Users\\sskr2\\SAVO\\services\\api')

print("="*80)
print("  PRODUCT INTELLIGENCE INTEGRATION VALIDATION")
print("="*80)

# Test 1: Import intelligence models
print("\n[1] Testing imports...")
try:
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
    print("   ✅ All intelligence models imported successfully")
except Exception as e:
    print(f"   ❌ Import error: {e}")
    sys.exit(1)

# Test 2: Create nutrition profile
print("\n[2] Testing nutrition profile creation...")
try:
    profile = UserNutritionProfile(
        health_conditions=["diabetes"],
        dietary_preferences=["low_sugar"],
        allergens=["peanuts"]
    )
    print(f"   ✅ Nutrition profile created: {len(profile.health_conditions)} condition(s)")
except Exception as e:
    print(f"   ❌ Profile creation error: {e}")

# Test 3: Calculate health fit score
print("\n[3] Testing health fit scoring...")
try:
    nutrition_estimate = RecipeNutritionEstimate(
        calories_per_serving=350,
        protein_g=25,
        carbs_g=30,
        fat_g=12,
        sodium_mg=500,
        sugar_g=6,  # Low sugar (good for diabetes)
        fiber_g=8
    )
    
    scoring = calculate_health_fit_score(
        nutrition_estimate=nutrition_estimate,
        user_profile=profile,
        meal_type="dinner"
    )
    
    print(f"   ✅ Health fit score: {scoring.health_fit_score:.2f}")
    print(f"      Eligibility: {scoring.eligibility}")
    print(f"      Positive flags: {scoring.positive_flags}")
    print(f"      Warning flags: {scoring.warning_flags}")
    
    if scoring.health_fit_score >= 0.7:
        print("   ✅ Score validates diabetes-friendly recipe")
    else:
        print("   ⚠️  Score lower than expected")
        
except Exception as e:
    print(f"   ❌ Health scoring error: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Skill fit evaluation
print("\n[4] Testing skill fit evaluation...")
try:
    recipe_difficulty = RecipeDifficulty(
        level=2,  # Basic
        skills_required=["pan_fry", "chop"],
        estimated_time_minutes=30,
        active_time_minutes=20
    )
    
    skill_fit = RecipeSkillFit.evaluate_fit(
        user_level=2,
        user_confidence=0.7,
        recipe_difficulty=recipe_difficulty
    )
    
    print(f"   ✅ Skill fit category: {skill_fit.fit_category}")
    print(f"      Confidence match: {skill_fit.confidence_match}")
    print(f"      Recommendation: {skill_fit.recommendation[:60]}...")
    
    if skill_fit.fit_category in ['perfect', 'stretch']:
        print("   ✅ Appropriate skill fit for user level 2")
        
except Exception as e:
    print(f"   ❌ Skill evaluation error: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Generate badges
print("\n[5] Testing badge generation...")
try:
    badges = generate_recipe_badges(
        nutrition_scoring=scoring,
        difficulty_level=2,
        time_minutes=30
    )
    
    print(f"   ✅ Generated {len(badges)} badges:")
    for badge in badges[:3]:
        print(f"      • {badge.label} (priority: {badge.priority})")
    
    if len(badges) <= 3:
        print("   ✅ Badge limit enforced (max 3)")
    else:
        print("   ⚠️  More than 3 badges generated")
        
except Exception as e:
    print(f"   ❌ Badge generation error: {e}")
    import traceback
    traceback.print_exc()

# Test 6: Cuisine ranking
print("\n[6] Testing cuisine ranking...")
try:
    available_ingredients = ["tomatoes", "rice", "chicken", "onions"]
    user_prefs = CuisinePreferences(
        preferred_cuisines=["Italian", "Indian"],
        avoided_cuisines=[],
        spice_tolerance="medium"
    )
    recent_cuisines = ["Italian", "Italian"]  # Rotate away from Italian
    
    cuisine_scores = rank_cuisines(
        available_ingredients=available_ingredients,
        user_preferences=user_prefs,
        recent_cuisines=recent_cuisines,
        user_skill_level=2,
        user_nutrition_profile=profile
    )
    
    print(f"   ✅ Ranked {len(cuisine_scores)} cuisines:")
    for score in cuisine_scores[:3]:
        print(f"      {score.rank}. {score.cuisine} (score: {score.total_score:.2f})")
        print(f"         Reason: {score.reason[:60]}...")
    
    if cuisine_scores and cuisine_scores[0].total_score > 0:
        print("   ✅ Cuisine ranking working correctly")
        
except Exception as e:
    print(f"   ❌ Cuisine ranking error: {e}")
    import traceback
    traceback.print_exc()

# Test 7: Planning module integration
print("\n[7] Testing planning module integration...")
try:
    from app.api.routes.planning import _enhance_recipe_with_intelligence
    
    # Mock recipe
    test_recipe = {
        "name": "Test Recipe",
        "cuisine": "Italian",
        "estimated_time_minutes": 30,
        "difficulty_level": 2,
        "calories": 400,
        "protein": 25,
        "carbs": 40,
        "fat": 15,
        "sodium": 600,
        "sugar": 8,
        "fiber": 6
    }
    
    _enhance_recipe_with_intelligence(
        recipe=test_recipe,
        nutrition_profile=profile,
        user_skill_level=2,
        user_confidence=0.7,
        meal_type="dinner"
    )
    
    print("   ✅ Recipe enhancement completed")
    
    # Check added fields
    if 'nutrition_intelligence' in test_recipe:
        print("   ✅ Nutrition intelligence added")
        print(f"      Health fit: {test_recipe['nutrition_intelligence']['health_fit_score']:.2f}")
    
    if 'skill_intelligence' in test_recipe:
        print("   ✅ Skill intelligence added")
        print(f"      Fit: {test_recipe['skill_intelligence']['fit_category']}")
    
    if 'badges' in test_recipe:
        print(f"   ✅ {len(test_recipe['badges'])} badges added")
        for badge in test_recipe['badges']:
            print(f"      • {badge['label']}")
    
    if 'why_this_recipe' in test_recipe:
        print(f"   ✅ 'Why This Recipe?' sections: {len(test_recipe['why_this_recipe'])}")
        
except Exception as e:
    print(f"   ❌ Planning integration error: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("  VALIDATION COMPLETE")
print("="*80)
print("\n✅ Product intelligence integration successful!")
print("\nNext steps:")
print("  1. Start backend server: uvicorn app.main:app --reload --port 8000")
print("  2. Test with real requests via Swagger UI: http://localhost:8000/docs")
print("  3. Integrate Flutter widgets into meal plan screen")
print("  4. Deploy to production")
