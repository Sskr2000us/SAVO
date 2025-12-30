# SAVO Product Intelligence API Specification

## Overview
This document specifies the complete API for SAVO's product intelligence system, including:
- Nutrition intelligence and health fit scoring
- Skill progression and recipe difficulty
- Global cuisine ranking and multi-cuisine mixing
- Enhanced planning with all intelligence layers

## API Base URL
- Production: `https://savo-ynp1.onrender.com`
- Local: `http://localhost:8000`

---

## 1. Nutrition Intelligence API

### POST /nutrition/evaluate
Evaluate nutrition fit of a recipe for a user profile.

**Request Body:**
```json
{
  "recipe_id": "REC_123",
  "servings": 3,
  "nutrition_estimate": {
    "calories": 420,
    "protein_g": 10,
    "carbs_g": 55,
    "fat_g": 14,
    "fiber_g": 8,
    "sodium_mg": 420,
    "sugar_g": 6,
    "confidence_score": 0.9
  },
  "nutrition_profile": {
    "daily_targets": {
      "calories": 2200,
      "protein_g": 120,
      "carbs_g": 250,
      "fat_g": 70
    },
    "health_conditions": ["diabetes", "hypertension"],
    "dietary_preferences": ["vegetarian"],
    "nutrition_focus": ["low_sugar", "high_fiber"]
  },
  "meal_type": "lunch"
}
```

**Response:**
```json
{
  "per_serving": {
    "calories": 420,
    "protein_g": 10,
    "carbs_g": 55,
    "fat_g": 14,
    "fiber_g": 8,
    "sodium_mg": 420,
    "sugar_g": 6,
    "confidence_score": 0.9
  },
  "health_fit_score": 0.85,
  "warnings": [],
  "positive_flags": ["low_sugar", "high_fiber"],
  "eligibility": "recommended",
  "explanation": "Good: low_sugar, high_fiber. Diabetes-friendly"
}
```

### POST /nutrition/badges
Generate visual badges for recipe card (max 3).

**Request Body:**
```json
{
  "nutrition_scoring": {
    "health_fit_score": 0.85,
    "positive_flags": ["high_protein", "high_fiber"],
    "warning_flags": [],
    "eligibility": "recommended"
  },
  "difficulty_level": 2,
  "time_minutes": 30
}
```

**Response:**
```json
{
  "badges": [
    {
      "icon": "🟢",
      "label": "Balanced",
      "color": "green",
      "tooltip": "Great nutritional fit for your profile"
    },
    {
      "icon": "⭐⭐",
      "label": "Medium",
      "color": "yellow",
      "tooltip": "Basic cooking skills required"
    },
    {
      "icon": "⏱",
      "label": "30 min",
      "color": "green",
      "tooltip": "Quick meal"
    }
  ]
}
```

### GET /nutrition/focus-options
Get available nutrition focus options for settings UI.

**Response:**
```json
{
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
    }
  ]
}
```

---

## 2. Enhanced Planning API

### POST /plan/daily
Generate daily meal plan with nutrition, skill, and cuisine intelligence.

**Request Body (Enhanced):**
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "session_type": "daily",
  "time_available_minutes": 45,
  "servings": 4,
  "meal_type": "dinner",
  "meal_time": "19:30",
  "current_date": "2025-12-30",
  
  "inventory": {
    "available_ingredients": ["tomato", "rice", "onion", "yogurt", "spices"]
  },
  
  "family_profile": {
    "members": [
      {
        "role": "child",
        "age": 8,
        "spice_tolerance": "none"
      },
      {
        "role": "adult",
        "age": 40,
        "health_conditions": ["diabetes"],
        "dietary_restrictions": ["vegetarian"]
      },
      {
        "role": "senior",
        "age": 70,
        "health_conditions": ["hypertension"],
        "allergens": ["peanuts"]
      }
    ]
  },
  
  "nutrition_profile": {
    "daily_targets": {
      "calories": 2200
    },
    "health_conditions": ["diabetes", "hypertension"],
    "dietary_preferences": ["vegetarian"],
    "nutrition_focus": ["low_sugar", "low_sodium"]
  },
  
  "skill_profile": {
    "current_level": 2,
    "confidence_score": 0.75
  },
  
  "cuisine_preferences": {
    "allowed": ["Indian", "Italian", "Mediterranean"],
    "recent_cuisines": ["Italian", "Chinese"],
    "allow_multi_cuisine": true
  }
}
```

**Response (Enhanced):**
```json
{
  "status": "ok",
  "plan_type": "daily",
  "selected_cuisine_strategy": "mixed_cuisine",
  
  "menu": [
    {
      "course": "starter",
      "cuisine": "Mediterranean",
      "recipe": {
        "recipe_id": "MED_001",
        "name": "Tomato & Yogurt Salad",
        "difficulty": {
          "level": 1,
          "level_name": "Assembly / No-Skill",
          "skills_required": [],
          "estimated_time_minutes": 10,
          "active_time_minutes": 10
        },
        "nutrition": {
          "per_serving": {
            "calories": 120,
            "protein_g": 6,
            "carbs_g": 15,
            "fat_g": 4,
            "fiber_g": 3,
            "sodium_mg": 150,
            "sugar_g": 4
          },
          "health_fit_score": 0.9,
          "positive_flags": ["low_sodium", "low_sugar"],
          "warnings": [],
          "eligibility": "recommended"
        },
        "badges": [
          {
            "icon": "🟢",
            "label": "Balanced",
            "color": "green",
            "tooltip": "Great nutritional fit"
          },
          {
            "icon": "⭐",
            "label": "Easy",
            "color": "green",
            "tooltip": "Simple assembly"
          }
        ],
        "ingredients": [...],
        "steps": [...]
      }
    },
    {
      "course": "main",
      "cuisine": "Indian",
      "recipe": {
        "recipe_id": "IND_042",
        "name": "Low-Sodium Tomato Rice",
        "difficulty": {
          "level": 2,
          "level_name": "Basic Cooking",
          "skills_required": ["saute", "simmer"],
          "estimated_time_minutes": 35,
          "active_time_minutes": 15
        },
        "nutrition": {
          "per_serving": {
            "calories": 420,
            "protein_g": 10,
            "carbs_g": 75,
            "fat_g": 8,
            "fiber_g": 6,
            "sodium_mg": 350,
            "sugar_g": 6
          },
          "health_fit_score": 0.85,
          "positive_flags": ["low_sodium", "low_sugar", "high_fiber"],
          "warnings": [],
          "eligibility": "recommended"
        },
        "badges": [
          {
            "icon": "💪",
            "label": "High Fiber",
            "color": "blue"
          },
          {
            "icon": "⭐⭐",
            "label": "Medium",
            "color": "yellow"
          },
          {
            "icon": "⏱",
            "label": "35 min",
            "color": "yellow"
          }
        ],
        "ingredients": [...],
        "steps": [...]
      }
    }
  ],
  
  "cuisine_decision": {
    "selected_cuisines": ["Mediterranean", "Indian"],
    "cuisine_scores": [
      {
        "cuisine": "Indian",
        "score": 0.82,
        "reason": "Strong ingredient match and matches your skill",
        "ingredient_match": 0.85,
        "user_preference": 1.0,
        "recent_rotation_penalty": 1.0,
        "skill_fit": 0.90,
        "nutrition_fit": 0.85
      },
      {
        "cuisine": "Mediterranean",
        "score": 0.78,
        "reason": "Good ingredient match",
        "ingredient_match": 0.75,
        "user_preference": 1.0,
        "recent_rotation_penalty": 1.0,
        "skill_fit": 1.0,
        "nutrition_fit": 0.90
      }
    ],
    "multi_cuisine_strategy": {
      "mode": "mixed_cuisine",
      "compatibility_check": {
        "compatible": true,
        "reason": "Compatible cuisines"
      },
      "explanation": "Different cuisines chosen to match health, effort, and ingredients."
    }
  },
  
  "skill_nudge": {
    "show_nudge": false,
    "message": "",
    "alternative_recipe_id": null,
    "buttons": []
  },
  
  "explanations": [
    "Chosen for diabetic-friendly sugar levels",
    "Low sodium for blood pressure management",
    "Skill level matches your comfort",
    "No peanuts (allergen excluded)",
    "Mild spice for child",
    "Vegetarian options throughout"
  ],
  
  "total_nutrition": {
    "calories": 540,
    "protein_g": 16,
    "carbs_g": 90,
    "fat_g": 12,
    "meets_daily_target": true,
    "pct_of_daily": 24.5
  }
}
```

---

## 3. Cuisine Intelligence API

### POST /cuisine/rank
Rank cuisines based on ingredients, preferences, and constraints.

**Request Body:**
```json
{
  "available_ingredients": ["tomato", "rice", "onion", "cheese"],
  "user_preferences": ["Italian", "Indian"],
  "recent_cuisines": ["Chinese", "Mexican"],
  "user_skill_level": 2,
  "nutrition_focus": ["low_fat"],
  "health_conditions": ["diabetes"]
}
```

**Response:**
```json
{
  "candidate_cuisines": ["Italian", "Indian", "Mediterranean", "Thai"],
  "scores": [
    {
      "cuisine": "Italian",
      "score": 0.82,
      "reason": "Strong ingredient match and your favorite",
      "ingredient_match": 0.85,
      "user_preference": 1.0,
      "recent_rotation_penalty": 1.0,
      "skill_fit": 0.90,
      "nutrition_fit": 0.75
    },
    {
      "cuisine": "Indian",
      "score": 0.74,
      "reason": "Good ingredient match and your favorite",
      "ingredient_match": 0.70,
      "user_preference": 1.0,
      "recent_rotation_penalty": 1.0,
      "skill_fit": 0.80,
      "nutrition_fit": 0.85
    }
  ],
  "selected_cuisine": "Italian",
  "explanation": "Italian works well today because you have tomatoes and cheese, and it matches your skill level."
}
```

### GET /cuisine/database
Get all supported cuisines with metadata.

**Response:**
```json
{
  "cuisines": [
    {
      "name": "Italian",
      "structure": ["antipasto", "primo", "secondo", "contorno"],
      "techniques": ["saute", "simmer", "bake", "boil"],
      "flavor_profile": ["savory", "umami", "herbaceous"],
      "staple_ingredients": ["tomato", "pasta", "cheese", "olive_oil"],
      "typical_spice_level": "mild",
      "typical_difficulty": 2
    }
  ]
}
```

---

## 4. Skill Progression API

### GET /skill/current
Get user's current skill level and progression status.

**Response:**
```json
{
  "current_level": 2,
  "level_name": "Basic Cooking",
  "confidence_score": 0.76,
  "recipes_completed": 18,
  "successful_meals": 15,
  "ready_to_advance": true,
  "advancement_reason": "Your timing is consistent. Want to try technique-based recipes?",
  "skill_signals": {
    "steps_skipped": 2,
    "timing_adjustments": 1,
    "user_edits": 3,
    "repeat_success": true
  }
}
```

### POST /skill/evaluate-fit
Evaluate if a recipe difficulty matches user skill.

**Request Body:**
```json
{
  "user_level": 2,
  "user_confidence": 0.75,
  "recipe_level": 3
}
```

**Response:**
```json
{
  "user_level": 2,
  "recipe_level": 3,
  "fit_category": "stretch",
  "recommendation": "Slightly challenging, but you can do it"
}
```

---

## 5. Edge Cases and Validation

### Edge Case 1: Kids + Diabetes + Mixed Cuisine

**Request:**
```json
{
  "family_profile": {
    "members": [
      {"role": "child", "age": 8},
      {"role": "senior", "age": 70, "health_conditions": ["diabetes"]}
    ]
  },
  "inventory": {"available_ingredients": ["rice", "tomato", "yogurt", "onion"]},
  "cuisine_preferences": {"allow_multi_cuisine": true}
}
```

**Expected Behavior:**
- ✅ Avoid high sugar sauces
- ✅ Avoid spicy-heavy dishes
- ✅ Keep skill level low
- ✅ Allow multi-cuisine only if compatible
- ✅ Clear explanation why dessert is skipped

**Response includes:**
```json
{
  "menu": [
    {
      "course": "starter",
      "cuisine": "Mediterranean",
      "recipe": {...}
    },
    {
      "course": "main",
      "cuisine": "Indian",
      "recipe": {...}
    }
  ],
  "explanations": [
    "Skipped dessert today to better support blood sugar goals.",
    "Mild spice level safe for children",
    "Low sugar content for diabetes management"
  ]
}
```

### Edge Case 2: User Wants "Something New" but Low Skill

**Expected Behavior:**
- Keep difficulty same
- Change cuisine OR technique, not both
- Provide encouraging message

**Response includes:**
```json
{
  "skill_nudge": {
    "show_nudge": true,
    "message": "Trying a new flavor, same easy steps.",
    "buttons": ["Try it", "Keep familiar"]
  }
}
```

### Edge Case 3: Conflicting Preferences (Vegetarian + Keto + Indian)

**Expected Behavior:**
- Flag conflict
- Suggest closest option
- Build trust with honesty

**Response includes:**
```json
{
  "warnings": ["Limited options for vegetarian keto Indian"],
  "explanations": [
    "Indian vegetarian keto options are limited. This is the closest fit."
  ]
}
```

---

## 6. UI Integration Guidelines

### Recipe Card Display

**Data to Show:**
```
- Recipe name
- Recipe image (hero)
- 3 badges maximum (nutrition > skill > time)
- Cuisine indicator
```

**Data to Hide by Default:**
```
- Raw nutrition numbers
- Detailed scores
- Internal IDs
```

### "Why This Recipe?" Expandable Sheet

**Show:**
- Simple sentence explanations
- "Fits your calorie goal"
- "Low sugar – good for diabetes"
- "Matches your cooking level"

**Don't Show:**
- Technical scores
- Raw weights
- Algorithm details

### Skill Nudge (Non-Intrusive)

**Copy Example:**
```
"You've cooked this style confidently. Want to try a slightly new technique?"

[Try it]  [Maybe later]
```

**Never Say:**
- "Level up"
- "Advanced only"
- "You need to..."

### Multi-Cuisine Indicator

**Label:** "Balanced Meal"

**Tooltip:** "Different cuisines chosen to match health, effort, and ingredients."

---

## 7. Response Time Targets

| Endpoint | Target | Max |
|----------|--------|-----|
| GET /nutrition/focus-options | 50ms | 100ms |
| POST /nutrition/evaluate | 100ms | 300ms |
| POST /nutrition/badges | 50ms | 100ms |
| GET /cuisine/database | 50ms | 100ms |
| POST /cuisine/rank | 200ms | 500ms |
| POST /plan/daily | 15s | 30s |

---

## 8. Error Handling

### 400 Bad Request
```json
{
  "error": "validation_error",
  "message": "Invalid nutrition profile: missing daily_targets",
  "field": "nutrition_profile.daily_targets"
}
```

### 500 Internal Server Error
```json
{
  "error": "calculation_error",
  "message": "Nutrition evaluation failed: division by zero",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 9. Testing Examples

### Test Case 1: Indian Family Lunch
```bash
curl -X POST https://savo-ynp1.onrender.com/plan/daily \
  -H "Content-Type: application/json" \
  -d '{
    "meal_time": "13:30",
    "family_profile": {
      "members": [
        {"role": "adult", "age": 45, "health_conditions": ["diabetes", "hypertension"]}
      ]
    },
    "inventory": {
      "available_ingredients": ["rice", "lentils", "tomato", "onion", "spices"]
    }
  }'
```

Expected: Indian lunch recipes, low sodium, low sugar

### Test Case 2: Nutrition Evaluation
```bash
curl -X POST https://savo-ynp1.onrender.com/nutrition/evaluate \
  -H "Content-Type: application/json" \
  -d '{
    "nutrition_estimate": {
      "calories": 420,
      "sugar_g": 5,
      "sodium_mg": 300
    },
    "nutrition_profile": {
      "health_conditions": ["diabetes", "hypertension"]
    }
  }'
```

Expected: health_fit_score ≥ 0.8, eligibility: "recommended"

---

## 10. Migration Plan

### Phase 1: Add Models (Week 1)
- [x] Create nutrition models
- [x] Create skill models
- [x] Create cuisine models

### Phase 2: Add Endpoints (Week 2)
- [ ] POST /nutrition/evaluate
- [ ] POST /nutrition/badges
- [ ] GET /nutrition/focus-options
- [ ] POST /cuisine/rank
- [ ] GET /skill/current

### Phase 3: Enhance Planning (Week 3)
- [ ] Update POST /plan/daily with intelligence layers
- [ ] Add nutrition scoring to recipes
- [ ] Add skill fit evaluation
- [ ] Add cuisine ranking logic

### Phase 4: Flutter Integration (Week 4)
- [ ] Recipe badges UI
- [ ] Expandable nutrition info
- [ ] Skill nudges
- [ ] Multi-cuisine indicators

---

## 11. Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Health fit accuracy | >85% | User feedback on recommendations |
| Skill fit accuracy | >80% | Recipe completion rate |
| Cuisine satisfaction | >75% | User ratings |
| API response time | <500ms | P95 latency |
| Recipe completion rate | >60% | Cook mode completion |

---

## Appendix: Full Example Request/Response

See [examples/full_planning_flow.json](examples/full_planning_flow.json) for complete request/response with all features enabled.
