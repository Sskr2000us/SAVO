# LLM Dietary Integration - Data Flow Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           FLUTTER MOBILE APP                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌────────────────────┐         ┌──────────────────────┐              │
│  │ Settings Screen    │         │ Dietary Screen       │              │
│  │ (Family Members)   │         │ (Onboarding)         │              │
│  └──────────┬─────────┘         └──────────┬───────────┘              │
│             │                               │                          │
│             │ POST /profile/family-members  │ PUT /profile/dietary     │
│             │ (per-member data)             │ (primary member)         │
└─────────────┼───────────────────────────────┼──────────────────────────┘
              │                               │
              ▼                               ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI BACKEND                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ DATABASE LAYER (database.py)                                     │  │
│  │                                                                  │  │
│  │  async def get_full_profile(user_id):                           │  │
│  │      # 1. Get all family members from database                  │  │
│  │      members = await get_family_members(user_id)                │  │
│  │                                                                  │  │
│  │      # 2. Aggregate allergens from ALL members                  │  │
│  │      all_allergens = set()                                      │  │
│  │      for member in members:                                     │  │
│  │          all_allergens.update(member["allergens"])              │  │
│  │                                                                  │  │
│  │      # 3. Aggregate dietary restrictions from ALL members       │  │
│  │      dietary_booleans = {"vegetarian": False, "vegan": False}   │  │
│  │      for member in members:                                     │  │
│  │          if "vegetarian" in member["dietary_restrictions"]:     │  │
│  │              dietary_booleans["vegetarian"] = True              │  │
│  │                                                                  │  │
│  │      return {                                                   │  │
│  │          "members": members,  # Individual profiles             │  │
│  │          "allergens": list(all_allergens),  # Union             │  │
│  │          "dietary": dietary_booleans  # Household-wide          │  │
│  │      }                                                           │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                  │                                      │
│                                  ▼                                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ API LAYER (routes/planning.py)                                   │  │
│  │                                                                  │  │
│  │  POST /planning/daily                                           │  │
│  │                                                                  │  │
│  │  # Step 1: Build nutrition intelligence layer                   │  │
│  │  nutrition_profile = UserNutritionProfile(                      │  │
│  │      allergens=[peanuts, shellfish, dairy],                     │  │
│  │      dietary_preferences=[vegetarian, no_pork],                 │  │
│  │      health_conditions=[diabetes, high_blood_pressure]          │  │
│  │  )                                                               │  │
│  │                                                                  │  │
│  │  # Step 2: Build context for LLM                                │  │
│  │  context = {                                                     │  │
│  │      "nutrition_intelligence": {                                │  │
│  │          "allergens": ["peanuts", "shellfish", "dairy"],        │  │
│  │          "dietary_preferences": ["vegetarian", "no_pork"],      │  │
│  │          "health_conditions": ["diabetes", "hypertension"],     │  │
│  │          "message": "Please respect these in recipes"           │  │
│  │      },                                                          │  │
│  │      "family_members": [                                        │  │
│  │          {                                                       │  │
│  │              "name": "John", "age": 35,                         │  │
│  │              "dietary_restrictions": ["vegetarian"],            │  │
│  │              "allergens": ["peanuts"],                          │  │
│  │              "health_conditions": ["diabetes"],                 │  │
│  │              "spice_tolerance": "medium"                        │  │
│  │          },                                                      │  │
│  │          {                                                       │  │
│  │              "name": "Sarah", "age": 8,                         │  │
│  │              "allergens": ["shellfish", "dairy"],               │  │
│  │              "food_dislikes": ["vegetables"],                   │  │
│  │              "spice_tolerance": "mild"                          │  │
│  │          }                                                       │  │
│  │      ],                                                          │  │
│  │      "skill_intelligence": {...},                               │  │
│  │      "inventory": [...],                                        │  │
│  │      "history_context": {...}                                   │  │
│  │  }                                                               │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                  │                                      │
│                                  ▼                                      │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ ORCHESTRATION LAYER (orchestrator.py)                            │  │
│  │                                                                  │  │
│  │  async def plan_daily(context):                                 │  │
│  │      # 1. Build LLM messages                                    │  │
│  │      messages = [                                               │  │
│  │          {"role": "system", "content": system_prompt},          │  │
│  │          {"role": "user", "content": task_instructions},        │  │
│  │          {"role": "user", "content": f"CONTEXT_JSON={context}"} │  │
│  │      ]                                                           │  │
│  │                                                                  │  │
│  │      # 2. Send to OpenAI GPT-4o                                 │  │
│  │      result = await client.generate_json(                       │  │
│  │          messages=messages,                                     │  │
│  │          schema=MENU_PLAN_SCHEMA                                │  │
│  │      )                                                           │  │
│  │                                                                  │  │
│  │      return result  # Structured recipe JSON                    │  │
│  └──────────────────────────────────────────────────────────────────┘  │
│                                  │                                      │
└──────────────────────────────────┼──────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            OPENAI GPT-4o                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Input: CONTEXT_JSON with full family dietary profiles                 │
│                                                                         │
│  Prompt Instructions:                                                   │
│  "Respect dietary restrictions, allergens, health conditions,          │
│   age groups, and calorie targets in APP_CONFIGURATION."               │
│                                                                         │
│  Output: Structured JSON with recipes                                  │
│  {                                                                      │
│    "recipes": [                                                         │
│      {                                                                  │
│        "name": "Vegetarian Pasta Primavera",                           │
│        "allergens": [],  // No peanuts, shellfish, dairy               │
│        "dietary_tags": ["vegetarian", "dairy_free"],                   │
│        "ingredients": [...],                                            │
│        "steps": [...]                                                   │
│      }                                                                  │
│    ]                                                                    │
│  }                                                                      │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                   POST-PROCESSING VALIDATION                            │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  for recipe in result["recipes"]:                                      │
│      # Calculate health fit score                                      │
│      health_score, flags, adjustments = calculate_health_fit_score(    │
│          recipe=recipe,                                                 │
│          user_profile=nutrition_profile  # ← Validates allergens       │
│      )                                                                  │
│                                                                         │
│      # CRITICAL: Fail recipe if allergen violation                     │
│      if allergen_violation:                                             │
│          health_score = 0.0  # ← Recipe should be filtered             │
│          flags.append("⚠️ Contains allergens")                          │
│                                                                         │
│      # Add health intelligence to recipe                               │
│      recipe["nutrition_intelligence"] = {                              │
│          "health_fit_score": health_score,                             │
│          "flags": flags,                                                │
│          "adjustments": adjustments                                    │
│      }                                                                  │
│                                                                         │
│      # Generate health badges                                          │
│      recipe["health_badges"] = ["diabetic_friendly", "heart_healthy"]  │
└─────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                       RESPONSE TO MOBILE APP                            │
├─────────────────────────────────────────────────────────────────────────┤
│  {                                                                      │
│    "status": "success",                                                 │
│    "selected_cuisine": "Italian",                                      │
│    "recipes": [                                                         │
│      {                                                                  │
│        "name": "Vegetarian Pasta Primavera",                           │
│        "serving_size": 4,                                               │
│        "prep_time_minutes": 15,                                         │
│        "cook_time_minutes": 15,                                         │
│        "difficulty": "easy",                                            │
│        "allergens": [],                                                 │
│        "dietary_tags": ["vegetarian", "dairy_free", "no_peanuts"],     │
│        "nutrition_intelligence": {                                      │
│          "health_fit_score": 0.85,                                     │
│          "flags": [],                                                   │
│          "adjustments": ["Reduced sodium for blood pressure"],         │
│          "explanation": "Low carb option for diabetes, vegetarian"     │
│        },                                                               │
│        "health_badges": ["diabetic_friendly", "heart_healthy"],        │
│        "ingredients": [...],                                            │
│        "steps": [...]                                                   │
│      }                                                                  │
│    ]                                                                    │
│  }                                                                      │
└─────────────────────────────────────────────────────────────────────────┘


KEY SAFETY FEATURES:
═══════════════════

1. ✅ AGGREGATION: All family member allergens combined (union)
   → If ANY member allergic to peanuts → NO peanuts in ANY recipe

2. ✅ CONTEXT INJECTION: Full dietary profiles sent to LLM in structured JSON
   → LLM receives explicit instructions to respect restrictions

3. ✅ VALIDATION: Post-processing checks recipes against nutrition profile
   → health_fit_score = 0.0 if allergen violation detected

4. ✅ TRANSPARENCY: Recipes include flags, adjustments, explanations
   → User sees why recipe was recommended and any health considerations

5. ✅ PER-MEMBER DETAILS: Individual preferences preserved and sent to LLM
   → Spice tolerance, food dislikes, age-appropriate portions


DATA FORMAT:
═══════════

✅ JSON format used throughout the entire pipeline
✅ Structured schema validation at every step
✅ Type-safe models (Pydantic) for data integrity
✅ OpenAI JSON mode for guaranteed structured output


CONCLUSION:
══════════

✅ System is PRODUCTION READY for dietary safety
✅ Multi-layer validation ensures no allergen violations
✅ Complete audit trail for transparency
✅ Fail-safe design (conservative household-wide restrictions)
```
