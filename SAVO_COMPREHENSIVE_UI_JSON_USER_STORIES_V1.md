# SAVO – Comprehensive UI JSON & User Stories (v1)

This document is the **single source of truth** for SAVO v1, combining:

* Complete, structured **UI JSON schema**
* Explicit **workflows**
* Clear **user stories** mapped to screens and actions

It is designed for **product, UX, frontend, backend, and ML teams** to work from the same artifact.

---

## 1. GLOBAL PRINCIPLES

```json
{
  "uiPrinciples": {
    "primaryActionPerScreen": true,
    "maxChoices": 3,
    "mandatoryAIConfirmation": true,
    "designTone": "calm_food_first_trust_driven"
  }
}
```

---

## 2. DESIGN TOKENS & COLOR SYSTEM

```json
{
  "designSystem": {
    "colors": {
      "primary": "#2F6F62",
      "primarySoft": "#E6F1EE",
      "accent": "#E07A3F",
      "background": "#FAFAF7",
      "surface": "#FFFFFF",
      "textPrimary": "#1F2933",
      "textSecondary": "#6B7280",
      "success": "#2E7D32",
      "warning": "#ED6C02",
      "error": "#C62828"
    },
    "spacing": {"xs": 4, "sm": 8, "md": 16, "lg": 24, "xl": 32},
    "radius": {"sm": 8, "md": 12, "lg": 20},
    "animationMs": {"fast": 150, "normal": 250}
  }
}
```

---

## 3. GLOBAL NAVIGATION

```json
{
  "navigation": {
    "tabs": [
      {"id": "today", "label": "Today"},
      {"id": "cook", "label": "Cook"},
      {"id": "plan", "label": "Plan"},
      {"id": "pantry", "label": "Pantry"}
    ]
  }
}
```

---

## 4. FLOW A — TODAY / HOME

### UI JSON

```json
{
  "screen": "TodayHome",
  "purpose": "Immediate direction and confidence",
  "components": [
    {"type": "header", "text": "Good evening, {{userName}}"},
    {
      "type": "heroCard",
      "title": "You can cook something right now",
      "subtitle": "Based on what’s in your pantry",
      "primaryAction": {"label": "See options", "action": "COOK_NOW"}
    },
    {
      "type": "secondaryActions",
      "actions": [
        {"label": "Plan a meal / party", "action": "PLAN_ENTRY"},
        {"label": "Update pantry", "action": "PANTRY_UPDATE"}
      ]
    }
  ]
}
```

### User Stories

* As a **user**, I want to immediately know what I can cook so I don’t feel overwhelmed.
* As a **user**, I want a single clear next step when I open the app.

---

## 5. FLOW B — SNAP PANTRY (INGREDIENT IDENTIFICATION)

### UI JSON

```json
{
  "flow": "SnapPantry",
  "screens": [
    {
      "screen": "PantryUpdateEntry",
      "options": [
        {"label": "Scan pantry shelf", "action": "OPEN_CAMERA"},
        {"label": "Add manually", "action": "MANUAL_ADD"},
        {"label": "Scan receipt", "action": "FUTURE"}
      ]
    },
    {
      "screen": "PantryCamera",
      "camera": {
        "overlay": "shelfGrid",
        "status": ["lighting", "itemDensity"]
      },
      "primaryAction": "CAPTURE_IMAGE"
    },
    {
      "screen": "PantryAISuggestions",
      "items": [
        {
          "ingredient": "GenericName",
          "confidence": "HIGH|MEDIUM|LOW",
          "quantity": "OPTIONAL",
          "actions": ["CONFIRM", "EDIT", "REMOVE"]
        }
      ],
      "primaryAction": "REVIEW_BEFORE_SAVE"
    },
    {
      "screen": "PantryReview",
      "summary": "Adding {{itemCount}} items",
      "actions": ["SAVE_INVENTORY", "GO_BACK"]
    }
  ]
}
```

### User Stories

* As a **user**, I want to confirm ingredients before they are added so I can trust the app.
* As a **user**, I want to quickly correct mistakes without typing too much.
* As a **user**, I want the app to improve as I confirm items over time.

---

## 6. FLOW C — PANTRY OVERVIEW

### UI JSON

```json
{
  "screen": "PantryOverview",
  "tabs": ["UseSoon", "Available", "Missing"],
  "itemDisplay": {
    "showQuantity": false,
    "showFreshnessIndicator": true
  }
}
```

### User Stories

* As a **user**, I want to see what I should use soon to avoid waste.
* As a **user**, I don’t want to manage exact quantities every time.

---

## 7. FLOW D — INVENTORY-BASED RECIPE GENERATION

### UI JSON

```json
{
  "flow": "CookNow",
  "rules": {"avoidRecentRecipes": 3},
  "screens": [
    {"screen": "CookNowEntry", "primaryAction": "GENERATE_RECIPES"},
    {
      "screen": "RecipeOptions",
      "maxCards": 5,
      "cardFields": ["image", "name", "whyItWorks", "difficulty"]
    },
    {
      "screen": "RecipeDetail",
      "sections": ["Ingredients", "Steps", "Meta"],
      "actions": ["START_COOKING", "ADD_TO_PLAN"]
    },
    {
      "screen": "CookMode",
      "stepByStep": true,
      "navigation": "SWIPE",
      "optional": ["VOICE", "TIMER"]
    },
    {
      "screen": "PostCookFeedback",
      "options": ["LovedIt", "Okay", "SkipNextTime"],
      "notesOptional": true
    }
  ]
}
```

### User Stories

* As a **user**, I want recipes that use what I already have.
* As a **user**, I don’t want to see the same recipes repeatedly.
* As a **user**, I want cooking instructions to be simple and distraction-free.

---

## 8. FLOW E — PLANNING & PARTY MODE

### UI JSON

```json
{
  "flow": "Planning",
  "screens": [
    {"screen": "PlanEntry", "options": ["DailyMeal", "DinnerParty", "Festival"]},
    {"screen": "PartySetup", "steps": ["Guests", "MealType", "Diet", "Cuisine"]},
    {
      "screen": "GeneratedMenu",
      "sections": ["Starters", "Mains", "Sides", "Dessert"],
      "actions": ["APPROVE_MENU", "SWAP_ITEMS"]
    },
    {
      "screen": "ShoppingList",
      "groupBy": ["Produce", "Pantry", "Refrigerated"],
      "actions": ["SAVE", "SHARE"]
    }
  ]
}
```

### User Stories

* As a **user**, I want SAVO to plan a complete menu so I feel confident hosting.
* As a **user**, I want a shopping list that only shows what I need to buy.
* As a **user**, I want to reuse this for both small dinners and big parties.

---

## 9. FLOW F — USER PROFILE

### UI JSON

```json
{
  "screen": "UserProfile",
  "fields": ["DietaryPreferences", "CuisineLikes", "CookingSkillLevel"]
}
```

### User Stories

* As a **user**, I want SAVO to learn my preferences so suggestions improve.

---

## 10. SYSTEM WORKFLOWS (END-TO-END)

```json
{
  "workflows": {
    "SnapPantry": ["Capture", "Suggest", "Confirm", "Save"],
    "CookNow": ["CheckInventory", "Generate", "Filter", "Cook", "Learn"],
    "PlanParty": ["CollectInputs", "GenerateMenu", "Approve", "Shop"]
  }
}
```

---

## 11. SUCCESS METRICS

```json
{
  "metrics": [
    "scan_to_confirm_time",
    "open_to_recipe_decision",
    "recipes_cooked_per_week",
    "pantry_scan_repeat_rate"
  ]
}
```

---

### FINAL NOTE

This document is intentionally **trust-first, conservative, and scalable**.
It can be directly used to:

* Build frontend screens
* Define backend APIs
* Align ML confidence thresholds
* Write acceptance criteria
