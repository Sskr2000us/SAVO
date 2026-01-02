# SAVO Cultural Intelligence System

## Overview

SAVO generates culturally-aware, nutritionally-informed recipes by combining **AI capability** with **curated cultural knowledge**. This document explains how SAVO answers questions like "Why This Combination is Beloved" without explicit user input.

## How It Works

### Two-Mode Approach

SAVO operates in two modes depending on whether the ingredient combination is well-known:

#### Mode 1: Known Traditional Combinations
For classic pairings like **black channa + tamarind + eggplant** (South Indian), SAVO uses pre-loaded cultural knowledge:

```python
# Example: South Indian Classic
{
    "region": "South India",
    "why_beloved": [
        "Protein Powerhouse: Black channa provides vegetarian protein traditionally gotten from dal",
        "Digestive Aid: Tamarind's acidity helps digest the heavy chickpeas and reduces gas",
        "Texture Balance: Eggplant's soft, silky texture complements chickpea's firm, nutty bite",
        "Flavor Complexity: Sour (tamarind) + earthy (channa) + umami (eggplant) = layered taste",
        "Economic: All three ingredients are affordable and widely available",
        "Seasonal: Works year-round with different eggplant varieties",
        "Festive: Can be dressed up for special occasions or kept simple for daily meals",
        "Ayurvedic: Balances vata and kapha doshas when cooked with warming spices"
    ],
    "nutritional_wisdom": {
        "protein_fiber": "Black channa provides 15g protein + 12g fiber per cup - complete vegetarian meal",
        "vitamin_c": "Tamarind's vitamin C helps absorb iron from chickpeas (critical for vegetarians)",
        "antioxidants": "Eggplant's nasunin (anthocyanin) protects brain cells",
        "low_calorie": "Eggplant is 95% water - adds bulk without calories"
    },
    "flavor_science": {
        "sour_umami": "Tamarind's tartaric acid enhances umami perception in eggplant",
        "maillard": "Roasting eggplant creates melanoidins that complement chickpea's nuttiness",
        "tempering": "Mustard seeds + curry leaves release sulfur compounds that tie flavors together",
        "heat_balance": "Chili heat is mellowed by eggplant's cooling properties"
    },
    "regional_variations": {
        "andhra": "Very spicy with red chili powder, served with rice",
        "karnataka": "Sambar-style with more liquid, eaten with rice or dosa",
        "tamil_nadu": "One-pot rice dish (Vangi Bath style) with dry-roasted spices",
        "kerala": "Coconut-based curry with fresh curry leaves and coconut oil"
    }
}
```

#### Mode 2: Novel Combinations
For unfamiliar pairings like **chicken + lemon + oregano** (Greek), SAVO instructs the AI to research:

```
CULTURAL INTELLIGENCE TASK:

The user wants to cook with: chicken, lemon, oregano

Your task is to:
1. Identify which cuisine(s) traditionally pair these ingredients
2. Explain WHY this combination works:
   - Nutritional synergies (e.g., vitamin C aids iron absorption)
   - Texture balance (soft vs. crunchy, creamy vs. light)
   - Flavor complexity (sweet + sour + umami layers)
   - Economic/seasonal factors (why it became traditional)
3. Include traditional wisdom in Greek cuisine
4. Explain flavor science behind the pairing
5. Provide cooking techniques that honor the tradition

Generate a "cultural_context" object in your response with:
{
  "why_this_combo": ["reason 1", "reason 2", ...],
  "nutritional_benefits": ["benefit 1", "benefit 2", ...],
  "flavor_science": ["science point 1", "science point 2", ...],
  "traditional_wisdom": "paragraph explaining cultural significance",
  "cooking_tips": ["tip 1", "tip 2", ...]
}

Use authentic culinary knowledge. Do not make assumptions.
```

## Architecture

### Core Components

1. **Cultural Knowledge Base** (`cultural_intelligence.py`)
   - Pre-loaded wisdom for 4+ classic combinations
   - Structured data: region, why_beloved, nutritional_wisdom, flavor_science, cooking_techniques, regional_variations
   - Easily expandable with more combinations

2. **Ingredient Combination Engine** (`ingredient_combinations.py`)
   - Analyzes ingredient synergy and balance
   - Integrates with cultural intelligence
   - Validates safety constraints (Section 11)

3. **Enhanced AI Prompts**
   - Explicitly request cultural context in responses
   - Provide traditional knowledge when available
   - Guide AI to research when knowledge is not pre-loaded

### Data Flow

```
User Input (Ingredients)
    ↓
Check Cultural Knowledge Base
    ↓
┌─────────────────────┬──────────────────────┐
│ Known Combination   │ Unknown Combination  │
│ (Mode 1)            │ (Mode 2)             │
├─────────────────────┼──────────────────────┤
│ Use pre-loaded      │ Instruct AI to       │
│ cultural wisdom     │ research + explain   │
└─────────────────────┴──────────────────────┘
    ↓
Build Enhanced Prompt
    ↓
LLM Generation (GPT-4o)
    ↓
Recipe with Cultural Context
```

## Current Knowledge Base

### 1. South Indian: Black Channa + Tamarind + Eggplant
- **Region**: South India
- **Traditional Names**: Guthi Vankaya Kura (Telugu), Vangi Pulusu (Tamil), Kaala Chana Huli (Kannada)
- **Why Beloved**: 8 reasons including protein source, digestive aid, texture balance, flavor complexity, economic viability
- **Nutritional Wisdom**: Vitamin C aids iron absorption, complete vegetarian meal, antioxidants
- **Flavor Science**: Sour-umami balance, Maillard reactions, tempering chemistry
- **Regional Variations**: Andhra (spicy), Karnataka (sambar-style), Tamil Nadu (rice dish), Kerala (coconut-based)

### 2. Italian: Tomato + Mozzarella + Basil (Caprese)
- **Region**: Southern Italy (Campania)
- **Traditional Name**: Insalata Caprese
- **Why Beloved**: Colors of Italian flag, summer tradition, no-cook freshness, lycopene-fat synergy
- **Nutritional Wisdom**: Lycopene absorption enhanced by fat, hydration, protein + calcium
- **Flavor Science**: Umami-fat balance, temperature critical, aromatic compounds
- **Cooking Techniques**: Never refrigerate tomatoes, hand-torn basil, best quality ingredients

### 3. North Indian: Paneer + Spinach + Cream (Palak Paneer)
- **Region**: North India (Punjab)
- **Traditional Name**: Palak Paneer
- **Why Beloved**: Comfort food, iron source for vegetarians, protein-fiber balance
- **Nutritional Wisdom**: Iron absorption enhanced by protein, calcium considerations, complete meal
- **Flavor Science**: Cream masks bitter notes, Maillard on paneer, warming spices
- **Cooking Techniques**: Blanch spinach for color, fry paneer first, kasuri methi for aroma

### 4. Chinese: Soy Sauce + Ginger + Garlic
- **Region**: China (Universal)
- **Traditional Name**: 三香 (Sān xiāng - Three Aromas)
- **Why Beloved**: Foundation of Chinese stir-fries, umami base, medicinal properties, preservation
- **Nutritional Wisdom**: Anti-inflammatory, digestive aid, immune boost
- **Flavor Science**: Umami synergy (glutamate + guanylate), wok hei, aromatic compounds
- **Cooking Techniques**: High heat stir-fry, order matters, soy sauce varieties

## API Integration

### Endpoint: `/recipes/combination`

**Request:**
```json
{
  "ingredients": ["black_channa", "tamarind", "eggplant"],
  "user_id": "user123",
  "cuisine": "South Indian"
}
```

**Response includes:**
```json
{
  "recipe": {
    "title": "Guthi Vankaya Kura",
    "cultural_context": {
      "why_this_combo": [
        "Protein Powerhouse: Black channa provides vegetarian protein",
        "Digestive Aid: Tamarind's acidity helps digest chickpeas",
        "Texture Balance: Soft eggplant + firm chickpeas",
        ...
      ],
      "nutritional_benefits": [
        "Vitamin C aids iron absorption from chickpeas",
        "Complete vegetarian meal with 15g protein + 12g fiber",
        ...
      ],
      "flavor_science": [
        "Tamarind's tartaric acid enhances umami in eggplant",
        "Maillard reactions create depth",
        ...
      ],
      "traditional_wisdom": "In South Indian cuisine, this combination has been beloved for centuries...",
      "cooking_tips": [
        "Temper with mustard seeds first",
        "Pressure cook channa to save time",
        ...
      ]
    }
  }
}
```

## Why This Approach Works

### 1. Authenticity
- Pre-loaded knowledge comes from authentic cultural sources
- Regional variations preserve diversity
- Traditional cooking techniques honored

### 2. Scalability
- Known combinations: Instant, accurate cultural context
- Unknown combinations: AI researches and explains
- Easy to expand knowledge base over time

### 3. Educational Value
- Users learn **why** combinations work, not just recipes
- Nutritional science explained (e.g., "vitamin C aids iron absorption")
- Cultural significance preserved and celebrated

### 4. Safety Integration
- Cultural intelligence respects dietary constraints (Section 11)
- Allergen awareness maintained
- Nutritional wisdom helps users make informed choices

## Testing

The cultural intelligence system has 17 comprehensive tests covering:

- ✅ Knowledge base retrieval for 4 classic combinations
- ✅ Prompt generation for known vs. unknown combinations
- ✅ API-friendly format with cultural context
- ✅ Depth of nutritional wisdom and flavor science
- ✅ Regional variations capture
- ✅ Case-insensitive and order-independent matching
- ✅ Edge cases (empty lists, single ingredients, unknown combos)

**Test Results:** 17/17 passing

## Future Enhancements

### Expand Knowledge Base
Add more classic combinations:
- Mexican: Corn + Beans + Chili (Three Sisters)
- Japanese: Dashi + Miso + Tofu
- Middle Eastern: Chickpeas + Tahini + Lemon (Hummus)
- French: Butter + Garlic + Parsley (Escargot Butter)
- Thai: Lemongrass + Galangal + Lime Leaves (Tom Yum)
- Ethiopian: Berbere + Lentils + Injera

### User Contributions
- Allow users to submit cultural knowledge
- Community validation of traditional wisdom
- Multiple cultural perspectives for same combinations

### Visual Context
- Photos of traditional dishes
- Regional maps showing variations
- Ingredient sourcing guides

### Nutritional Depth
- Micronutrient interactions (e.g., zinc + phytates)
- Bioavailability science
- Traditional medicine principles (Ayurveda, TCM)
- Modern research citations

## Example: How SAVO Generates "Why This Combination is Beloved"

### User Query
"Create a recipe with black channa, tamarind, and eggplant"

### System Process

1. **Ingredient Normalization**
   ```python
   normalized = ["black_channa", "tamarind", "eggplant"]
   ```

2. **Cultural Knowledge Lookup**
   ```python
   context = get_cultural_context(normalized)
   # Returns: South Indian traditional knowledge
   ```

3. **Enhanced Prompt Building**
   ```python
   prompt = build_cultural_intelligence_prompt(
       ingredients=normalized,
       cuisine="South Indian"
   )
   # Includes: why_beloved, nutritional_wisdom, flavor_science
   ```

4. **LLM Generation**
   - GPT-4o receives cultural context
   - Generates recipe honoring tradition
   - Explains why combination works
   - Includes nutritional benefits
   - Provides cooking tips

5. **Response Enrichment**
   ```python
   response = enrich_recipe_with_culture(
       recipe=generated_recipe,
       cultural_context=context
   )
   # Adds: cultural_context field with detailed explanations
   ```

### Result
User receives not just a recipe, but a **cultural education**:
- Why protein + acid + vegetable works nutritionally
- How texture balance creates satisfaction
- Economic and seasonal factors in South India
- Regional variations across 4 states
- Traditional cooking techniques
- Flavor science behind the pairing

## Technical Implementation

### Files
- `services/api/app/core/cultural_intelligence.py` (400+ lines)
- `services/api/app/core/ingredient_combinations.py` (enhanced prompts)
- `services/api/app/tests/test_cultural_intelligence.py` (17 tests)

### Key Functions

```python
# Get cultural knowledge for ingredient combination
context = get_cultural_context(ingredients: List[str]) -> Optional[Dict]

# Build AI prompt with cultural intelligence
prompt = build_cultural_intelligence_prompt(
    ingredients: List[str],
    cuisine: Optional[str] = None
) -> str

# Enrich recipe response with cultural context
enriched = enrich_recipe_with_culture(
    recipe: Dict,
    cultural_context: Dict
) -> Dict

# API-friendly summary
summary = get_cultural_intelligence_for_combination(
    ingredients: List[str]
) -> Optional[Dict]
```

### Integration Points

1. **Recipe Generation** (`/recipes/combination`)
   - Calls `build_cultural_intelligence_prompt()` before LLM
   - Validates cultural authenticity after generation

2. **Meal Course Planning** (`/recipes/full-course`)
   - Uses cultural context for cuisine coherence
   - Ensures cultural consistency across courses

3. **Safety Validation** (Section 11 Integration)
   - Cultural knowledge respects dietary restrictions
   - Nutritional wisdom informs allergen warnings

## Conclusion

SAVO generates "Why This Combination is Beloved" explanations through:

1. **Curated Cultural Knowledge**: Pre-loaded wisdom for classic pairings
2. **AI Research**: GPT-4o investigates novel combinations
3. **Structured Prompts**: Explicit instructions for cultural reasoning
4. **Nutritional Science**: Evidence-based synergy explanations
5. **Regional Diversity**: Multiple perspectives for same ingredients

This hybrid approach ensures **authenticity** (when knowledge exists), **scalability** (AI research for novel combos), and **educational value** (users understand the "why" behind recipes).

---

**Version**: 1.0  
**Date**: 2025-01-XX  
**Author**: SAVO Development Team  
**Related Docs**: IMPLEMENTATION_SUMMARY.md, user_profile.md (Section 12)
