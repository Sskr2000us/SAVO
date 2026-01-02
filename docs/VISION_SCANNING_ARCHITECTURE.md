# SAVO Vision Scanning Architecture
## Foundation: Pantry/Refrigerator → Confirmed Ingredients List

**Date:** January 2, 2026  
**Status:** Architecture Design  
**Priority:** CRITICAL - Foundation for all recipe generation

---

## Problem Statement

**Current Gap**: SAVO has no reliable way to convert a photo of a pantry/refrigerator into a **confirmed, actionable** list of ingredients.

**Why This Matters**:
- Recipe generation is only as good as ingredient detection
- Mis-identified allergens = safety risk
- Poor accuracy = user abandons feature
- No confirmation flow = user doesn't trust system

**Goal**: Build a vision scanning pipeline where:
1. User takes photo of pantry/fridge
2. SAVO detects ingredients with confidence scores
3. User **confirms, edits, removes** detected items
4. System learns from corrections
5. Confirmed list feeds into recipe generation

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    VISION SCANNING PIPELINE                 │
└─────────────────────────────────────────────────────────────┘

[1. CAPTURE]
    User takes photo
    ↓
[2. VISION API]
    Extract objects + text
    ↓
[3. INGREDIENT INTELLIGENCE]
    Map objects → ingredient names
    Normalize to standard format
    ↓
[4. CONFIDENCE SCORING]
    High confidence (>0.8) → Auto-add
    Medium (0.5-0.8) → Show for confirmation
    Low (<0.5) → Flag as uncertain
    ↓
[5. USER CONFIRMATION UI]
    ✅ Confirmed items (green)
    ⚠️ Uncertain items (yellow - needs review)
    ❌ Incorrect detections (red - user can remove)
    ➕ Add missing items manually
    ↓
[6. FEEDBACK LOOP]
    User corrections → Training data
    Improve model over time
    ↓
[7. INGREDIENT STORAGE]
    Save to DB: ingredient_scans table
    Link to user profile
    ↓
[8. RECIPE GENERATION]
    Use confirmed ingredients
    Check against allergens
    Generate recipes
```

---

## Component 1: Vision API Integration

### Option A: OpenAI Vision API (GPT-4 Vision)

**Pros**:
- Already using OpenAI for text generation
- Excellent at understanding context
- Can describe "a carton of milk" vs. just "white box"

**Implementation**:
```python
import base64
from openai import OpenAI

async def scan_pantry_openai(image_bytes: bytes, user_id: str) -> dict:
    """
    Use GPT-4 Vision to detect ingredients from photo.
    
    Returns:
        {
            "detected_items": [
                {
                    "name": "milk",
                    "category": "dairy",
                    "confidence": 0.95,
                    "context": "whole milk carton",
                    "quantity_visible": "1 carton"
                },
                ...
            ],
            "ambiguous_items": [
                {
                    "name": "unknown_vegetable",
                    "description": "green leafy vegetable",
                    "confidence": 0.4,
                    "suggestions": ["spinach", "kale", "lettuce"]
                }
            ]
        }
    """
    
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    
    # Encode image
    base64_image = base64.b64encode(image_bytes).decode('utf-8')
    
    # Build prompt
    prompt = """
You are SAVO, an AI cooking assistant analyzing a pantry or refrigerator photo.

TASK: Identify ALL visible food ingredients and products.

OUTPUT FORMAT (JSON):
{
  "detected_items": [
    {
      "name": "standard_ingredient_name",
      "category": "dairy|protein|vegetable|fruit|grain|spice|condiment|canned|frozen",
      "confidence": 0.0-1.0,
      "context": "brief description of what you see",
      "quantity_visible": "approximate quantity if visible"
    }
  ],
  "ambiguous_items": [
    {
      "description": "what you see but can't identify confidently",
      "confidence": 0.0-1.0,
      "suggestions": ["possible_item1", "possible_item2"]
    }
  ]
}

CRITICAL RULES:
1. Use STANDARD ingredient names (not brand names)
   - "milk" not "Horizon Organic Whole Milk"
   - "soy_sauce" not "Kikkoman"
   
2. Confidence scores:
   - 0.9-1.0: Clear, unambiguous (milk carton with label visible)
   - 0.7-0.9: Reasonably certain (egg carton shape)
   - 0.5-0.7: Uncertain but educated guess (green vegetable, probably spinach)
   - <0.5: Cannot identify reliably (put in ambiguous_items)

3. Include quantity if visible:
   - "3 eggs visible"
   - "half-full milk carton"
   - "1 head of broccoli"

4. Flag allergens with HIGH confidence only:
   - If you see peanuts, be 95%+ sure before including

5. Skip non-food items (plates, containers without visible contents)

Analyze the image now:
"""
    
    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }
                    }
                ]
            }
        ],
        max_tokens=2000
    )
    
    # Parse response
    result = json.loads(response.choices[0].message.content)
    
    return result
```

### Option B: Google Cloud Vision API + Custom Logic

**Pros**:
- Specialized for object/label detection
- Can extract text from packaging (ingredients lists)
- Potentially more accurate for common items

**Implementation**:
```python
from google.cloud import vision

async def scan_pantry_google(image_bytes: bytes) -> dict:
    """
    Use Google Cloud Vision for object/label detection.
    Then map to ingredient names.
    """
    
    client = vision.ImageAnnotatorClient()
    image = vision.Image(content=image_bytes)
    
    # Object detection
    objects = client.object_localization(image=image).localized_object_annotations
    
    # Label detection (backup)
    labels = client.label_detection(image=image).label_annotations
    
    # Text detection (read packaging)
    texts = client.text_detection(image=image).text_annotations
    
    # Map to ingredients
    ingredients = []
    
    for obj in objects:
        ingredient = map_object_to_ingredient(obj.name, obj.score)
        if ingredient:
            ingredients.append({
                "name": ingredient,
                "confidence": obj.score,
                "source": "object_detection",
                "bounding_box": {
                    "x": obj.bounding_poly.normalized_vertices[0].x,
                    "y": obj.bounding_poly.normalized_vertices[0].y
                }
            })
    
    return {
        "detected_items": ingredients,
        "raw_objects": [obj.name for obj in objects],
        "raw_labels": [label.description for label in labels],
        "text_found": texts[0].description if texts else None
    }

def map_object_to_ingredient(object_name: str, confidence: float) -> Optional[str]:
    """
    Map Google Vision object names to standard ingredient names.
    
    Examples:
    - "Carton" + high confidence near "Milk" text → "milk"
    - "Vegetable" + green color → ambiguous, needs confirmation
    """
    
    # Object name mapping
    object_map = {
        "milk": "milk",
        "egg": "eggs",
        "cheese": "cheese",
        "butter": "butter",
        "chicken": "chicken",
        "tomato": "tomato",
        "broccoli": "broccoli",
        # ... extensive mapping
    }
    
    object_lower = object_name.lower()
    
    for key, ingredient in object_map.items():
        if key in object_lower:
            return ingredient
    
    return None
```

### Recommended Approach: Hybrid

```python
async def scan_pantry_hybrid(image_bytes: bytes, user_id: str) -> dict:
    """
    Use both OpenAI Vision (for context) and Google Vision (for precision).
    Merge results with confidence weighting.
    """
    
    # Run both in parallel
    openai_result, google_result = await asyncio.gather(
        scan_pantry_openai(image_bytes, user_id),
        scan_pantry_google(image_bytes)
    )
    
    # Merge results
    merged = merge_detection_results(openai_result, google_result)
    
    return merged

def merge_detection_results(openai_result: dict, google_result: dict) -> dict:
    """
    Merge two detection results, taking best confidence for each ingredient.
    """
    
    ingredient_map = {}
    
    # Add OpenAI detections
    for item in openai_result.get("detected_items", []):
        name = item["name"]
        ingredient_map[name] = {
            "name": name,
            "confidence": item["confidence"],
            "sources": ["openai"],
            "context": item.get("context"),
            "category": item.get("category")
        }
    
    # Merge Google detections
    for item in google_result.get("detected_items", []):
        name = item["name"]
        if name in ingredient_map:
            # Ingredient detected by both - boost confidence
            existing = ingredient_map[name]
            existing["confidence"] = min(1.0, 
                (existing["confidence"] + item["confidence"]) / 2 + 0.1)
            existing["sources"].append("google")
        else:
            # New ingredient from Google
            ingredient_map[name] = {
                "name": name,
                "confidence": item["confidence"],
                "sources": ["google"],
                "bounding_box": item.get("bounding_box")
            }
    
    # Sort by confidence
    detected_items = sorted(
        ingredient_map.values(),
        key=lambda x: x["confidence"],
        reverse=True
    )
    
    return {
        "detected_items": detected_items,
        "total_items": len(detected_items),
        "high_confidence": [i for i in detected_items if i["confidence"] > 0.8],
        "needs_confirmation": [i for i in detected_items if 0.5 <= i["confidence"] <= 0.8],
        "low_confidence": [i for i in detected_items if i["confidence"] < 0.5]
    }
```

---

## Component 2: Ingredient Normalization

**Challenge**: Vision APIs return varied names. Need to normalize to standard format.

### Ingredient Name Canonicalization

```python
# Standard ingredient database
INGREDIENT_CANONICAL_NAMES = {
    # Variations → Canonical name
    "milk": ["milk", "whole milk", "2% milk", "skim milk", "dairy milk"],
    "eggs": ["egg", "eggs", "chicken eggs", "large eggs"],
    "chicken": ["chicken", "chicken breast", "chicken thigh", "poultry"],
    "tomato": ["tomato", "tomatoes", "roma tomato", "cherry tomato"],
    "onion": ["onion", "onions", "yellow onion", "red onion", "white onion"],
    # ... extensive database
}

def normalize_ingredient_name(detected_name: str) -> str:
    """
    Convert varied ingredient names to canonical standard.
    
    Examples:
    - "whole milk" → "milk"
    - "roma tomatoes" → "tomato"
    - "chicken breast" → "chicken"
    """
    
    detected_lower = detected_name.lower().strip()
    
    # Direct match
    for canonical, variations in INGREDIENT_CANONICAL_NAMES.items():
        if detected_lower in [v.lower() for v in variations]:
            return canonical
    
    # Fuzzy match (Levenshtein distance)
    from fuzzywuzzy import process
    
    all_variations = []
    for canonical, variations in INGREDIENT_CANONICAL_NAMES.items():
        all_variations.extend([(v, canonical) for v in variations])
    
    match, score = process.extractOne(
        detected_lower,
        [v[0] for v in all_variations]
    )
    
    if score > 85:  # High similarity threshold
        # Find canonical name for this match
        for variation, canonical in all_variations:
            if variation == match:
                return canonical
    
    # No match found - return original (will be flagged for user review)
    return detected_name
```

### Category Assignment

```python
INGREDIENT_CATEGORIES = {
    "dairy": ["milk", "cheese", "butter", "yogurt", "cream"],
    "protein": ["chicken", "beef", "pork", "fish", "tofu", "eggs"],
    "vegetable": ["tomato", "onion", "broccoli", "spinach", "carrot"],
    "fruit": ["apple", "banana", "orange", "lemon"],
    "grain": ["rice", "pasta", "bread", "oats"],
    "spice": ["salt", "pepper", "cumin", "paprika"],
    "condiment": ["soy_sauce", "ketchup", "mustard"],
    "canned": ["beans", "tomato_paste", "coconut_milk"],
    "frozen": ["frozen_vegetables", "ice_cream"]
}

def assign_category(ingredient_name: str) -> str:
    """Assign category to normalized ingredient."""
    
    for category, ingredients in INGREDIENT_CATEGORIES.items():
        if ingredient_name in ingredients:
            return category
    
    return "other"
```

---

## Component 3: Confidence Scoring & Ambiguity Handling

### Three-Tier Confidence System

```python
class ConfidenceLevel(Enum):
    HIGH = "high"        # 0.8-1.0 - Auto-add to list
    MEDIUM = "medium"    # 0.5-0.8 - Show for confirmation
    LOW = "low"          # 0.0-0.5 - Flag as uncertain

def classify_confidence(score: float) -> ConfidenceLevel:
    if score >= 0.8:
        return ConfidenceLevel.HIGH
    elif score >= 0.5:
        return ConfidenceLevel.MEDIUM
    else:
        return ConfidenceLevel.LOW

def handle_ambiguous_detection(
    detected_name: str,
    confidence: float,
    context: dict
) -> dict:
    """
    Handle low-confidence or ambiguous detections.
    
    Returns suggestions for user to choose from.
    """
    
    if confidence < 0.5:
        # Use context clues to generate suggestions
        suggestions = generate_suggestions(detected_name, context)
        
        return {
            "status": "ambiguous",
            "detected": detected_name,
            "confidence": confidence,
            "suggestions": suggestions,
            "user_action_required": True
        }
    else:
        return {
            "status": "confirmed",
            "name": detected_name,
            "confidence": confidence
        }

def generate_suggestions(detected_name: str, context: dict) -> list[str]:
    """
    Generate plausible ingredient suggestions based on context.
    
    Example:
    - Detected: "green leafy vegetable"
    - Context: {"color": "green", "shape": "leafy"}
    - Suggestions: ["spinach", "kale", "lettuce", "chard"]
    """
    
    # Color-based suggestions
    if "green" in detected_name.lower():
        green_vegetables = ["spinach", "kale", "lettuce", "broccoli", "green_beans"]
        return green_vegetables[:3]
    
    elif "red" in detected_name.lower():
        red_items = ["tomato", "bell_pepper", "strawberry", "apple"]
        return red_items[:3]
    
    # Shape-based suggestions
    if "leafy" in detected_name.lower():
        return ["spinach", "lettuce", "kale", "cabbage"]
    
    # Category-based fallback
    category = context.get("category", "food")
    if category == "vegetable":
        return ["carrot", "broccoli", "potato"]
    elif category == "fruit":
        return ["apple", "banana", "orange"]
    
    return []


---

## Component 3A: Close Ingredients Suggestion Engine

**Purpose**: When SAVO can't confidently identify an ingredient, provide a curated list of "close" ingredients for user to select from.

### Why This Matters

```
❌ WITHOUT Close Suggestions:
User scans pantry
  → "Unknown green vegetable detected"
  → User must manually type "spinach"
  → High friction, potential typos

✅ WITH Close Suggestions:
User scans pantry
  → "Detected: Green leafy vegetable (60% confidence)"
  → Shows: [Spinach] [Kale] [Lettuce] [Chard]
  → User taps "Spinach"
  → Low friction, confirmed correct
```

### Similarity Database

```python
# Database of visually similar ingredients
VISUAL_SIMILARITY_GROUPS = {
    "leafy_greens": {
        "members": ["spinach", "kale", "lettuce", "chard", "collard_greens", "arugula"],
        "visual_cues": ["green", "leafy", "bunch"],
        "confusion_pairs": [
            ("spinach", "kale"),
            ("lettuce", "cabbage"),
            ("chard", "collard_greens")
        ]
    },
    
    "root_vegetables": {
        "members": ["carrot", "parsnip", "turnip", "radish", "beet"],
        "visual_cues": ["elongated", "root", "orange", "white", "red"],
        "confusion_pairs": [
            ("carrot", "parsnip"),  # Both orange/white elongated
            ("turnip", "radish"),   # Both white/red round
        ]
    },
    
    "alliums": {
        "members": ["onion", "red_onion", "yellow_onion", "white_onion", "shallot", "garlic"],
        "visual_cues": ["bulb", "layered", "papery_skin"],
        "confusion_pairs": [
            ("red_onion", "yellow_onion"),
            ("shallot", "small_onion"),
            ("garlic", "shallot")
        ]
    },
    
    "bell_peppers": {
        "members": ["green_bell_pepper", "red_bell_pepper", "yellow_bell_pepper", "orange_bell_pepper"],
        "visual_cues": ["bell_shaped", "glossy", "hollow"],
        "confusion_pairs": [
            ("green_bell_pepper", "red_bell_pepper"),
            ("yellow_bell_pepper", "orange_bell_pepper")
        ]
    },
    
    "dairy_liquids": {
        "members": ["milk", "cream", "half_and_half", "buttermilk", "almond_milk", "oat_milk"],
        "visual_cues": ["white_liquid", "carton", "bottle"],
        "confusion_pairs": [
            ("milk", "cream"),
            ("milk", "almond_milk"),
            ("cream", "half_and_half")
        ]
    },
    
    "cooking_oils": {
        "members": ["vegetable_oil", "canola_oil", "olive_oil", "coconut_oil", "avocado_oil"],
        "visual_cues": ["clear_liquid", "bottle", "yellow"],
        "confusion_pairs": [
            ("vegetable_oil", "canola_oil"),
            ("olive_oil", "avocado_oil")
        ]
    },
    
    "beans_legumes": {
        "members": ["black_beans", "kidney_beans", "chickpeas", "lentils", "pinto_beans"],
        "visual_cues": ["small", "round", "dried", "canned"],
        "confusion_pairs": [
            ("black_beans", "kidney_beans"),
            ("chickpeas", "lentils")
        ]
    },
    
    "cheese_blocks": {
        "members": ["cheddar", "mozzarella", "monterey_jack", "swiss", "gouda"],
        "visual_cues": ["block", "yellow", "white", "wrapped"],
        "confusion_pairs": [
            ("cheddar", "monterey_jack"),
            ("mozzarella", "monterey_jack"),
            ("swiss", "provolone")
        ]
    },
    
    "berries": {
        "members": ["strawberry", "raspberry", "blackberry", "blueberry", "cranberry"],
        "visual_cues": ["small", "red", "blue", "purple", "clustered"],
        "confusion_pairs": [
            ("raspberry", "blackberry"),
            ("blueberry", "blackberry")
        ]
    },
    
    "citrus": {
        "members": ["lemon", "lime", "orange", "grapefruit", "tangerine"],
        "visual_cues": ["round", "yellow", "green", "orange", "citrus"],
        "confusion_pairs": [
            ("lemon", "lime"),
            ("orange", "tangerine"),
            ("orange", "grapefruit")
        ]
    }
}


def get_close_ingredients(
    detected_name: str,
    confidence: float,
    context: dict
) -> list[dict]:
    """
    Generate a list of close/similar ingredients for user confirmation.
    
    Args:
        detected_name: What the vision model detected (e.g., "green leafy vegetable")
        confidence: Detection confidence (0.0-1.0)
        context: Additional context (color, shape, category, etc.)
    
    Returns:
        List of close ingredient suggestions with metadata:
        [
            {
                "name": "spinach",
                "display_name": "Spinach",
                "likelihood": 0.8,
                "reason": "Most common leafy green",
                "image_url": "/assets/ingredients/spinach.jpg"
            },
            ...
        ]
    """
    
    suggestions = []
    
    # Strategy 1: Find matching similarity group
    for group_name, group_data in VISUAL_SIMILARITY_GROUPS.items():
        # Check if detected name or context matches this group
        if any(cue in detected_name.lower() for cue in group_data["visual_cues"]):
            # Return all members of this group
            for member in group_data["members"]:
                suggestions.append({
                    "name": member,
                    "display_name": member.replace("_", " ").title(),
                    "likelihood": 1.0 / len(group_data["members"]),  # Equal likelihood
                    "reason": f"Similar to {group_name.replace('_', ' ')}",
                    "group": group_name
                })
            break
    
    # Strategy 2: Use fuzzy matching if no group found
    if not suggestions:
        suggestions = fuzzy_match_ingredients(detected_name, context)
    
    # Strategy 3: Add "Other" option for manual entry
    suggestions.append({
        "name": "other",
        "display_name": "Other (type manually)",
        "likelihood": 0.0,
        "reason": "If none of these match",
        "manual_entry": True
    })
    
    # Rank by likelihood and limit to top 5
    suggestions = sorted(suggestions, key=lambda x: x["likelihood"], reverse=True)[:5]
    
    return suggestions


def fuzzy_match_ingredients(detected_name: str, context: dict) -> list[dict]:
    """
    Use fuzzy string matching to find close ingredients.
    """
    from fuzzywuzzy import process
    
    # Get all known ingredients from database
    all_ingredients = get_all_known_ingredients()
    
    # Find close matches
    matches = process.extract(detected_name, all_ingredients, limit=4)
    
    suggestions = []
    for match_name, score in matches:
        if score > 60:  # Minimum similarity threshold
            suggestions.append({
                "name": match_name,
                "display_name": match_name.replace("_", " ").title(),
                "likelihood": score / 100.0,
                "reason": f"{score}% text match",
                "source": "fuzzy_match"
            })
    
    return suggestions


def rank_suggestions_by_user_history(
    suggestions: list[dict],
    user_id: str
) -> list[dict]:
    """
    Boost suggestions based on user's past ingredient usage.
    
    If user frequently uses spinach but rarely uses kale,
    put spinach first in suggestions.
    """
    
    # Get user's ingredient usage frequency
    usage_counts = get_user_ingredient_usage(user_id)
    
    for suggestion in suggestions:
        ingredient_name = suggestion["name"]
        usage_count = usage_counts.get(ingredient_name, 0)
        
        # Boost likelihood based on usage
        if usage_count > 0:
            suggestion["likelihood"] *= (1 + min(usage_count / 10, 0.5))  # Up to 50% boost
            suggestion["reason"] += f" (You've used this {usage_count} times)"
    
    # Re-rank
    suggestions = sorted(suggestions, key=lambda x: x["likelihood"], reverse=True)
    
    return suggestions
```

### Enhanced UI for Close Ingredients

```dart
// Flutter: Show close ingredient suggestions
class IngredientSuggestionCard extends StatelessWidget {
  final DetectedItem item;
  final Function(String) onSelect;
  
  @override
  Widget build(BuildContext context) {
    return Card(
      margin: EdgeInsets.symmetric(vertical: 8, horizontal: 16),
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            // Header: What was detected
            Row(
              children: [
                Icon(Icons.help_outline, color: Colors.orange),
                SizedBox(width: 8),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Detected: ${item.name}',
                        style: TextStyle(fontWeight: FontWeight.bold),
                      ),
                      Text(
                        '${(item.confidence * 100).toInt()}% confident',
                        style: TextStyle(fontSize: 12, color: Colors.grey),
                      ),
                    ],
                  ),
                ),
              ],
            ),
            
            SizedBox(height: 12),
            
            // Question
            Text(
              'Which ingredient is this?',
              style: TextStyle(fontSize: 14),
            ),
            
            SizedBox(height: 12),
            
            // Close ingredient suggestions
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: item.closeSuggestions.map((suggestion) {
                return _buildSuggestionChip(suggestion);
              }).toList(),
            ),
            
            SizedBox(height: 12),
            
            // Manual entry option
            TextButton.icon(
              icon: Icon(Icons.edit),
              label: Text('Type ingredient name'),
              onPressed: () => _showManualEntry(context),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildSuggestionChip(IngredientSuggestion suggestion) {
    return InkWell(
      onTap: () => onSelect(suggestion.name),
      child: Container(
        padding: EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        decoration: BoxDecoration(
          color: Colors.blue.shade50,
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: Colors.blue.shade200),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            // Ingredient image (if available)
            if (suggestion.imageUrl != null)
              ClipRRect(
                borderRadius: BorderRadius.circular(12),
                child: Image.network(
                  suggestion.imageUrl!,
                  width: 24,
                  height: 24,
                  fit: BoxFit.cover,
                ),
              ),
            if (suggestion.imageUrl != null)
              SizedBox(width: 8),
            
            // Ingredient name
            Text(
              suggestion.displayName,
              style: TextStyle(
                fontWeight: FontWeight.w500,
                color: Colors.blue.shade900,
              ),
            ),
            
            // Likelihood indicator
            if (suggestion.likelihood > 0.7)
              Padding(
                padding: EdgeInsets.only(left: 4),
                child: Icon(
                  Icons.star,
                  size: 14,
                  color: Colors.amber,
                ),
              ),
          ],
        ),
      ),
    );
  }
  
  void _showManualEntry(BuildContext context) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: Text('Enter Ingredient Name'),
        content: TextField(
          autofocus: true,
          decoration: InputDecoration(
            hintText: 'Type ingredient name...',
            prefixIcon: Icon(Icons.search),
          ),
          onSubmitted: (value) {
            if (value.isNotEmpty) {
              Navigator.pop(context);
              onSelect(value);
            }
          },
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: Text('Cancel'),
          ),
        ],
      ),
    );
  }
}
```

### Example User Flow

```
┌─────────────────────────────────────────┐
│  Photo Scanned                          │
└─────────────────────────────────────────┘
            ↓
┌─────────────────────────────────────────┐
│  ⚠️  Needs Confirmation (2 items)       │
├─────────────────────────────────────────┤
│                                         │
│  🥬 Detected: Green leafy vegetable     │
│     60% confident                       │
│                                         │
│  Which ingredient is this?              │
│                                         │
│  [Spinach ⭐] [Kale] [Lettuce] [Chard] │
│                                         │
│  📝 Type ingredient name                │
│                                         │
├─────────────────────────────────────────┤
│                                         │
│  🧀 Detected: White cheese block        │
│     55% confident                       │
│                                         │
│  Which ingredient is this?              │
│                                         │
│  [Mozzarella ⭐] [Monterey Jack]        │
│  [Feta] [Queso Fresco]                  │
│                                         │
│  📝 Type ingredient name                │
│                                         │
└─────────────────────────────────────────┘
```

### Context-Aware Suggestions

```python
def get_contextual_suggestions(
    detected_name: str,
    context: dict,
    user_profile: dict
) -> list[dict]:
    """
    Provide context-aware suggestions based on:
    1. Visual similarity
    2. User's dietary restrictions (don't suggest dairy to vegan)
    3. User's cuisine preferences
    4. User's past usage patterns
    """
    
    # Get base suggestions
    suggestions = get_close_ingredients(detected_name, context.get("confidence", 0), context)
    
    # Filter out allergens
    user_allergens = set()
    for member in user_profile.get("members", []):
        user_allergens.update(member.get("allergens", []))
    
    if user_allergens:
        suggestions = [
            s for s in suggestions
            if not is_allergen(s["name"], user_allergens)
        ]
    
    # Filter by dietary restrictions
    dietary_restrictions = set()
    for member in user_profile.get("members", []):
        dietary_restrictions.update(member.get("dietary_restrictions", []))
    
    if "vegan" in dietary_restrictions:
        # Remove all animal products
        suggestions = [
            s for s in suggestions
            if s["name"] not in ["milk", "butter", "cheese", "cream", "eggs"]
        ]
    
    if "vegetarian" in dietary_restrictions:
        # Remove meat
        suggestions = [
            s for s in suggestions
            if s["name"] not in ["chicken", "beef", "pork", "fish"]
        ]
    
    # Boost by cuisine preferences
    favorite_cuisines = user_profile.get("household", {}).get("favorite_cuisines", [])
    if favorite_cuisines:
        for suggestion in suggestions:
            if is_common_in_cuisine(suggestion["name"], favorite_cuisines):
                suggestion["likelihood"] *= 1.3  # 30% boost
                suggestion["reason"] += f" (Common in {favorite_cuisines[0]})"
    
    # Rank by user history
    suggestions = rank_suggestions_by_user_history(suggestions, user_profile["user_id"])
    
    return suggestions


def is_common_in_cuisine(ingredient: str, cuisines: list[str]) -> bool:
    """Check if ingredient is commonly used in specified cuisines."""
    
    CUISINE_COMMON_INGREDIENTS = {
        "italian": ["tomato", "basil", "mozzarella", "parmesan", "olive_oil", "garlic"],
        "indian": ["onion", "tomato", "ginger", "garlic", "turmeric", "cumin", "coriander"],
        "chinese": ["soy_sauce", "ginger", "garlic", "green_onion", "rice", "noodles"],
        "mexican": ["tomato", "onion", "cilantro", "lime", "jalapeño", "cumin"],
        "japanese": ["soy_sauce", "mirin", "rice", "nori", "miso", "tofu"],
    }
    
    for cuisine in cuisines:
        if ingredient in CUISINE_COMMON_INGREDIENTS.get(cuisine.lower(), []):
            return True
    
    return False
```

### API Response Format

```python
# Enhanced API response with close suggestions
{
    "scan_id": "uuid",
    "detected_items": [
        {
            "name": "milk",
            "confidence": 0.95,
            "status": "confirmed",
            "needs_review": false
        }
    ],
    "needs_confirmation": [
        {
            "name": "leafy_green_vegetable",
            "confidence": 0.60,
            "status": "ambiguous",
            "needs_review": true,
            "close_suggestions": [
                {
                    "name": "spinach",
                    "display_name": "Spinach",
                    "likelihood": 0.85,
                    "reason": "Most common leafy green (You've used this 12 times)",
                    "image_url": "/assets/ingredients/spinach.jpg",
                    "nutrition_preview": "High in iron, vitamin K"
                },
                {
                    "name": "kale",
                    "display_name": "Kale",
                    "likelihood": 0.70,
                    "reason": "Similar leafy green",
                    "image_url": "/assets/ingredients/kale.jpg",
                    "nutrition_preview": "High in vitamin C, K"
                },
                {
                    "name": "lettuce",
                    "display_name": "Lettuce",
                    "likelihood": 0.60,
                    "reason": "Common salad green",
                    "image_url": "/assets/ingredients/lettuce.jpg"
                },
                {
                    "name": "chard",
                    "display_name": "Swiss Chard",
                    "likelihood": 0.40,
                    "reason": "Less common leafy green",
                    "image_url": "/assets/ingredients/chard.jpg"
                },
                {
                    "name": "other",
                    "display_name": "Other (type manually)",
                    "likelihood": 0.0,
                    "reason": "If none of these match",
                    "manual_entry": true
                }
            ],
            "context": {
                "visual_cues": ["green", "leafy", "bunch"],
                "similarity_group": "leafy_greens"
            }
        }
    ]
}
```

---

## Component 4: User Confirmation UI Flow

### Mobile UI Screens

**Screen 1: Scan Camera**
```
┌─────────────────────────────────┐
│   📷 Scan Your Pantry           │
├─────────────────────────────────┤
│                                 │
│   [  Camera Viewfinder  ]       │
│                                 │
│   Tips:                         │
│   • Good lighting               │
│   • Clear view of items         │
│   • Multiple photos OK          │
│                                 │
│   [Capture Photo] [Gallery]    │
└─────────────────────────────────┘
```

**Screen 2: Detection Results (Confirmation)**
```
┌─────────────────────────────────┐
│   ✓ Items Detected (8)          │
├─────────────────────────────────┤
│                                 │
│ ✅ Confirmed (5)                │
│   • Milk (95% confident) ✓      │
│   • Eggs (92% confident) ✓      │
│   • Tomato (88% confident) ✓    │
│   • Chicken (85% confident) ✓   │
│   • Rice (90% confident) ✓      │
│                                 │
│ ⚠️  Please Review (2)            │
│   • Leafy vegetable (65%)       │
│     [Spinach] [Kale] [Lettuce]  │
│     [Other: _______]            │
│   • White cheese (60%)          │
│     [Mozzarella] [Feta] [Remove]│
│                                 │
│ ❌ Low Confidence (1)            │
│   • Unknown jar (35%)           │
│     [Describe...] [Remove]      │
│                                 │
│ ➕ Add Missing Items             │
│   [+ Add Ingredient]            │
│                                 │
│   [Scan Another] [Confirm All] │
└─────────────────────────────────┘
```

**Screen 3: Edit/Add Item**
```
┌─────────────────────────────────┐
│   Edit Item: Leafy Vegetable    │
├─────────────────────────────────┤
│                                 │
│ Detected as: Leafy vegetable    │
│ Confidence: 65%                 │
│                                 │
│ Select correct item:            │
│ ○ Spinach                       │
│ ○ Kale                          │
│ ○ Lettuce                       │
│ ○ Swiss chard                   │
│ ○ Other (type below)            │
│                                 │
│ Or search: [________🔍]         │
│                                 │
│ Quantity (optional):            │
│ [1 bunch ▼]                     │
│                                 │
│   [Cancel]  [Save]              │
└─────────────────────────────────┘
```

### Flutter Implementation

```dart
// lib/screens/scanning/scan_confirmation_screen.dart

class ScanConfirmationScreen extends StatefulWidget {
  final ScanResult scanResult;
  
  @override
  _ScanConfirmationScreenState createState() => _ScanConfirmationScreenState();
}

class _ScanConfirmationScreenState extends State<ScanConfirmationScreen> {
  late List<DetectedItem> confirmedItems;
  late List<DetectedItem> needsReview;
  late List<DetectedItem> lowConfidence;
  
  @override
  void initState() {
    super.initState();
    _categorizeItems();
  }
  
  void _categorizeItems() {
    confirmedItems = widget.scanResult.detectedItems
        .where((item) => item.confidence >= 0.8)
        .toList();
    
    needsReview = widget.scanResult.detectedItems
        .where((item) => item.confidence >= 0.5 && item.confidence < 0.8)
        .toList();
    
    lowConfidence = widget.scanResult.detectedItems
        .where((item) => item.confidence < 0.5)
        .toList();
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: Text('Confirm Scanned Items'),
        actions: [
          TextButton(
            onPressed: _scanAnother,
            child: Text('Scan Another'),
          )
        ],
      ),
      body: ListView(
        children: [
          // Confirmed items
          _buildSection(
            '✅ Confirmed (${confirmedItems.length})',
            confirmedItems,
            Colors.green.shade50,
            isConfirmed: true,
          ),
          
          // Needs review
          if (needsReview.isNotEmpty)
            _buildSection(
              '⚠️ Please Review (${needsReview.length})',
              needsReview,
              Colors.orange.shade50,
              needsReview: true,
            ),
          
          // Low confidence
          if (lowConfidence.isNotEmpty)
            _buildSection(
              '❌ Uncertain (${lowConfidence.length})',
              lowConfidence,
              Colors.red.shade50,
              lowConfidence: true,
            ),
          
          // Add missing button
          Padding(
            padding: EdgeInsets.all(16),
            child: OutlinedButton.icon(
              icon: Icon(Icons.add),
              label: Text('Add Missing Item'),
              onPressed: _addMissingItem,
            ),
          ),
        ],
      ),
      bottomNavigationBar: SafeArea(
        child: Padding(
          padding: EdgeInsets.all(16),
          child: ElevatedButton(
            onPressed: _confirmAll,
            child: Text('Confirm All (${_getTotalConfirmed()})'),
            style: ElevatedButton.styleFrom(
              minimumSize: Size.fromHeight(50),
            ),
          ),
        ),
      ),
    );
  }
  
  Widget _buildSection(
    String title,
    List<DetectedItem> items,
    Color backgroundColor,
    {bool isConfirmed = false,
     bool needsReview = false,
     bool lowConfidence = false}
  ) {
    return Container(
      color: backgroundColor,
      padding: EdgeInsets.all(16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            title,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.bold,
            ),
          ),
          SizedBox(height: 12),
          ...items.map((item) => _buildItemCard(
            item,
            isConfirmed: isConfirmed,
            needsReview: needsReview,
            lowConfidence: lowConfidence,
          )),
        ],
      ),
    );
  }
  
  Widget _buildItemCard(
    DetectedItem item,
    {bool isConfirmed = false,
     bool needsReview = false,
     bool lowConfidence = false}
  ) {
    return Card(
      child: ListTile(
        leading: Icon(
          isConfirmed ? Icons.check_circle : Icons.help_outline,
          color: isConfirmed ? Colors.green : Colors.orange,
        ),
        title: Text(item.name),
        subtitle: needsReview
            ? _buildSuggestions(item)
            : Text('${(item.confidence * 100).toInt()}% confident'),
        trailing: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            if (isConfirmed)
              IconButton(
                icon: Icon(Icons.edit),
                onPressed: () => _editItem(item),
              ),
            IconButton(
              icon: Icon(Icons.delete),
              onPressed: () => _removeItem(item),
            ),
          ],
        ),
      ),
    );
  }
  
  Widget _buildSuggestions(DetectedItem item) {
    if (item.suggestions == null || item.suggestions!.isEmpty) {
      return TextField(
        decoration: InputDecoration(
          hintText: 'Type ingredient name...',
          dense: true,
        ),
        onSubmitted: (value) => _setSuggestion(item, value),
      );
    }
    
    return Wrap(
      spacing: 8,
      children: item.suggestions!.map((suggestion) {
        return ChoiceChip(
          label: Text(suggestion),
          selected: item.selectedSuggestion == suggestion,
          onSelected: (selected) {
            if (selected) {
              setState(() => item.selectedSuggestion = suggestion);
            }
          },
        );
      }).toList(),
    );
  }
  
  void _editItem(DetectedItem item) {
    // Navigate to edit screen
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => EditItemScreen(item: item),
      ),
    ).then((edited) {
      if (edited != null) {
        setState(() {
          // Update item
        });
      }
    });
  }
  
  void _removeItem(DetectedItem item) {
    setState(() {
      confirmedItems.remove(item);
      needsReview.remove(item);
      lowConfidence.remove(item);
    });
  }
  
  void _addMissingItem() {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (_) => AddItemScreen(),
      ),
    ).then((newItem) {
      if (newItem != null) {
        setState(() {
          confirmedItems.add(newItem);
        });
      }
    });
  }
  
  void _scanAnother() {
    Navigator.pop(context);
  }
  
  Future<void> _confirmAll() async {
    // Collect all confirmed items
    final allConfirmed = [
      ...confirmedItems,
      ...needsReview.where((i) => i.selectedSuggestion != null),
    ];
    
    // Save to backend
    final apiClient = ApiClient();
    await apiClient.saveScannedIngredients(
      userId: UserSession.currentUserId,
      ingredients: allConfirmed.map((i) => {
        'name': i.selectedSuggestion ?? i.name,
        'confidence': i.confidence,
        'confirmed_by_user': true,
      }).toList(),
    );
    
    // Navigate to recipe suggestions
    Navigator.pushReplacement(
      context,
      MaterialPageRoute(
        builder: (_) => RecipeSuggestionsScreen(
          ingredients: allConfirmed,
        ),
      ),
    );
  }
  
  int _getTotalConfirmed() {
    return confirmedItems.length +
           needsReview.where((i) => i.selectedSuggestion != null).length;
  }
  
  void _setSuggestion(DetectedItem item, String suggestion) {
    setState(() {
      item.selectedSuggestion = suggestion;
    });
  }
}
```

---

## Component 5: Backend API Endpoints

### POST /api/scanning/analyze-image

```python
@router.post("/scanning/analyze-image")
async def analyze_pantry_image(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    """
    Analyze uploaded pantry/fridge photo and return detected ingredients.
    
    Returns:
        {
            "scan_id": "uuid",
            "detected_items": [...],
            "needs_confirmation": [...],
            "low_confidence": [...]
        }
    """
    
    # Read image
    image_bytes = await file.read()
    
    # Validate image
    if len(image_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(400, "Image too large")
    
    # Run vision detection
    result = await scan_pantry_hybrid(image_bytes, user_id)
    
    # Save scan to DB for audit
    scan_id = await save_scan_record(
        user_id=user_id,
        image_bytes=image_bytes,
        detection_result=result
    )
    
    return {
        "scan_id": scan_id,
        "detected_items": result["high_confidence"],
        "needs_confirmation": result["needs_confirmation"],
        "low_confidence": result["low_confidence"],
        "total_detected": result["total_items"]
    }
```

### POST /api/scanning/confirm-ingredients

```python
@router.post("/scanning/confirm-ingredients")
async def confirm_scanned_ingredients(
    request: ConfirmIngredientsRequest,
    user_id: str = Depends(get_current_user)
):
    """
    Save user-confirmed ingredients from scan.
    
    Request:
        {
            "scan_id": "uuid",
            "confirmed_items": [
                {
                    "name": "milk",
                    "original_detection": "whole milk",
                    "confidence": 0.95,
                    "user_confirmed": true
                },
                {
                    "name": "spinach",
                    "original_detection": "leafy vegetable",
                    "confidence": 0.65,
                    "user_corrected": true,  # User picked from suggestions
                    "correction_from": ["spinach", "kale", "lettuce"]
                }
            ],
            "rejected_items": ["unknown_jar"],
            "added_items": ["garlic", "onion"]  # User manually added
        }
    
    Returns:
        {
            "success": true,
            "ingredient_count": 12,
            "feedback_recorded": true
        }
    """
    
    # Save confirmed ingredients to user's pantry
    await db.execute("""
        INSERT INTO user_pantry (user_id, ingredient_name, scan_id, confidence, 
                                 user_confirmed, added_at)
        VALUES ($1, $2, $3, $4, $5, NOW())
    """, [(
        user_id,
        item["name"],
        request.scan_id,
        item["confidence"],
        item.get("user_confirmed", True)
    ) for item in request.confirmed_items])
    
    # Record feedback for ML training
    await record_scan_feedback(
        scan_id=request.scan_id,
        user_id=user_id,
        confirmed=request.confirmed_items,
        rejected=request.rejected_items,
        corrections=[item for item in request.confirmed_items 
                    if item.get("user_corrected")]
    )
    
    # Check against allergens (CRITICAL)
    profile = await get_full_profile(user_id)
    allergen_warnings = []
    
    for item in request.confirmed_items:
        if is_allergen(item["name"], profile):
            allergen_warnings.append({
                "ingredient": item["name"],
                "allergen": get_allergen_match(item["name"], profile),
                "severity": "critical"
            })
    
    if allergen_warnings:
        # Alert user
        return {
            "success": False,
            "error": "allergen_detected",
            "warnings": allergen_warnings,
            "message": f"Warning: {allergen_warnings[0]['ingredient']} contains {allergen_warnings[0]['allergen']} (your declared allergen)"
        }
    
    return {
        "success": True,
        "ingredient_count": len(request.confirmed_items),
        "feedback_recorded": True
    }
```

---

## Component 6: Feedback Loop & Learning

### Recording User Corrections

```python
async def record_scan_feedback(
    scan_id: str,
    user_id: str,
    confirmed: list,
    rejected: list,
    corrections: list
):
    """
    Record user feedback to improve vision model over time.
    
    This data can be used to:
    1. Fine-tune vision model prompts
    2. Improve ingredient normalization
    3. Expand suggestion database
    4. Track model accuracy metrics
    """
    
    # Save to feedback table
    await db.execute("""
        INSERT INTO scan_feedback (
            scan_id, user_id, confirmed_count, rejected_count, 
            correction_count, created_at
        ) VALUES ($1, $2, $3, $4, $5, NOW())
    """, (scan_id, user_id, len(confirmed), len(rejected), len(corrections)))
    
    # Save individual corrections for training
    for correction in corrections:
        await db.execute("""
            INSERT INTO scan_corrections (
                scan_id, original_detection, user_correction, 
                confidence_score, created_at
            ) VALUES ($1, $2, $3, $4, NOW())
        """, (
            scan_id,
            correction["original_detection"],
            correction["name"],
            correction["confidence"]
        ))
    
    # Update accuracy metrics
    await update_model_accuracy_metrics(scan_id, confirmed, rejected)
```

### Accuracy Tracking

```python
async def calculate_scan_accuracy(scan_id: str) -> dict:
    """
    Calculate accuracy of a scan after user confirmation.
    
    Metrics:
    - Precision: Of detected items, how many were correct?
    - Recall: Of actual items, how many were detected?
    - Correction rate: How many detections needed user correction?
    """
    
    feedback = await db.fetchrow("""
        SELECT confirmed_count, rejected_count, correction_count
        FROM scan_feedback WHERE scan_id = $1
    """, scan_id)
    
    total_detected = feedback["confirmed_count"] + feedback["rejected_count"]
    
    precision = feedback["confirmed_count"] / total_detected if total_detected > 0 else 0
    correction_rate = feedback["correction_count"] / feedback["confirmed_count"] if feedback["confirmed_count"] > 0 else 0
    
    return {
        "scan_id": scan_id,
        "precision": precision,
        "correction_rate": correction_rate,
        "total_confirmed": feedback["confirmed_count"],
        "total_rejected": feedback["rejected_count"]
    }
```

---

## Component 7: Database Schema

```sql
-- Table: ingredient_scans
CREATE TABLE ingredient_scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    image_url TEXT,  -- S3/storage URL
    image_hash TEXT,  -- For deduplication
    detection_model VARCHAR(50),  -- 'openai' | 'google' | 'hybrid'
    raw_result JSONB,  -- Full API response
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_scans_user ON ingredient_scans(user_id, created_at DESC);

-- Table: detected_ingredients (raw detections)
CREATE TABLE detected_ingredients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID REFERENCES ingredient_scans(id) ON DELETE CASCADE,
    ingredient_name TEXT NOT NULL,
    confidence_score FLOAT CHECK (confidence_score BETWEEN 0 AND 1),
    detection_source VARCHAR(50),  -- 'openai' | 'google'
    bounding_box JSONB,  -- Coordinates if available
    context TEXT,  -- Vision model description
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: user_pantry (confirmed ingredients)
CREATE TABLE user_pantry (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    ingredient_name TEXT NOT NULL,
    scan_id UUID REFERENCES ingredient_scans(id),  -- Which scan added this
    confidence FLOAT,
    user_confirmed BOOLEAN DEFAULT FALSE,
    user_corrected BOOLEAN DEFAULT FALSE,
    original_detection TEXT,  -- Before correction
    quantity TEXT,  -- Optional: "1 bunch", "2 lbs"
    added_at TIMESTAMPTZ DEFAULT NOW(),
    last_used TIMESTAMPTZ,  -- Track when used in recipe
    UNIQUE(user_id, ingredient_name)  -- One entry per ingredient per user
);

CREATE INDEX idx_pantry_user ON user_pantry(user_id);
CREATE INDEX idx_pantry_added ON user_pantry(user_id, added_at DESC);

-- Table: scan_feedback (learning data)
CREATE TABLE scan_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID REFERENCES ingredient_scans(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id),
    confirmed_count INT DEFAULT 0,
    rejected_count INT DEFAULT 0,
    correction_count INT DEFAULT 0,
    user_added_count INT DEFAULT 0,  -- Manually added items
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Table: scan_corrections (training data)
CREATE TABLE scan_corrections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID REFERENCES ingredient_scans(id) ON DELETE CASCADE,
    original_detection TEXT NOT NULL,
    user_correction TEXT NOT NULL,
    confidence_score FLOAT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_corrections_detection ON scan_corrections(original_detection);

-- Table: scan_accuracy_metrics (monitoring)
CREATE TABLE scan_accuracy_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID REFERENCES ingredient_scans(id),
    precision FLOAT,  -- Correct / Total detected
    correction_rate FLOAT,  -- Corrections / Confirmed
    avg_confidence FLOAT,
    calculated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Component 8: Safety Integration (CRITICAL)

### Allergen Warning System

```python
async def check_scanned_ingredients_safety(
    ingredients: list[str],
    user_id: str
) -> dict:
    """
    CRITICAL: Check scanned ingredients against user allergens.
    
    This is the LAST line of defense against allergen exposure.
    """
    
    profile = await get_full_profile(user_id)
    
    # Get all declared allergens
    all_allergens = set()
    for member in profile.get("members", []):
        all_allergens.update(member.get("allergens", []))
    
    if not all_allergens:
        return {"safe": True, "warnings": []}
    
    # Check each ingredient
    warnings = []
    
    for ingredient in ingredients:
        # Check direct match
        if ingredient.lower() in [a.lower() for a in all_allergens]:
            warnings.append({
                "ingredient": ingredient,
                "allergen": ingredient,
                "severity": "critical",
                "message": f"🚨 {ingredient} is a declared allergen!"
            })
            continue
        
        # Check derivative matches (e.g., "milk" allergen catches "butter", "cheese")
        allergen_derivatives = {
            "dairy": ["milk", "butter", "cheese", "cream", "yogurt"],
            "nuts": ["almond", "walnut", "cashew", "pecan"],
            "soy": ["soy_sauce", "tofu", "tempeh"],
        }
        
        for allergen in all_allergens:
            if allergen in allergen_derivatives:
                if ingredient.lower() in allergen_derivatives[allergen]:
                    warnings.append({
                        "ingredient": ingredient,
                        "allergen": allergen,
                        "severity": "high",
                        "message": f"⚠️ {ingredient} contains {allergen} (declared allergen)"
                    })
    
    return {
        "safe": len(warnings) == 0,
        "warnings": warnings,
        "allergen_count": len(all_allergens)
    }
```

### UX for Allergen Warnings

```dart
// Flutter: Show allergen warning before proceeding
Future<bool> _showAllergenWarning(List warnings) async {
  return await showDialog<bool>(
    context: context,
    barrierDismissible: false,  // Must respond
    builder: (context) => AlertDialog(
      title: Row(
        children: [
          Icon(Icons.warning, color: Colors.red, size: 32),
          SizedBox(width: 12),
          Text('Allergen Detected'),
        ],
      ),
      content: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'The following items may contain allergens:',
            style: TextStyle(fontWeight: FontWeight.bold),
          ),
          SizedBox(height: 12),
          ...warnings.map((w) => ListTile(
            leading: Icon(Icons.error, color: Colors.red),
            title: Text(w['ingredient']),
            subtitle: Text(w['message']),
          )),
        ],
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context, false),
          child: Text('Remove These Items'),
        ),
        ElevatedButton(
          onPressed: () => Navigator.pop(context, true),
          style: ElevatedButton.styleFrom(backgroundColor: Colors.red),
          child: Text('Keep Anyway (Not Recommended)'),
        ),
      ],
    ),
  ) ?? false;
}
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1-2)
- ✅ Set up OpenAI Vision API integration
- ✅ Build ingredient normalization database
- ✅ Create database schema
- ✅ Implement confidence scoring
- ✅ Test with sample images (pantry, fridge)

### Phase 2: Backend API (Week 2-3)
- ✅ Build `/scanning/analyze-image` endpoint
- ✅ Build `/scanning/confirm-ingredients` endpoint
- ✅ Implement safety checks (allergen warnings)
- ✅ Add feedback recording
- ✅ Write comprehensive tests

### Phase 3: Mobile UI (Week 3-4)
- ✅ Build camera capture screen
- ✅ Build confirmation/review screen
- ✅ Build edit item flow
- ✅ Add allergen warning dialogs
- ✅ Connect to backend APIs

### Phase 4: Feedback Loop (Week 4-5)
- ✅ Implement correction tracking
- ✅ Build accuracy metrics dashboard
- ✅ Set up monitoring/alerts
- ✅ Create admin view for reviewing corrections

### Phase 5: Optimization (Week 5-6)
- ✅ Fine-tune vision prompts based on feedback
- ✅ Expand ingredient database
- ✅ Optimize suggestion algorithm
- ✅ Performance testing
- ✅ A/B test different UI flows

---

## Success Metrics

### Accuracy Metrics
- **Detection Precision**: >85% (items detected are actually present)
- **User Correction Rate**: <20% (most detections don't need correction)
- **Allergen False Positive Rate**: 0% (never miss an allergen)

### UX Metrics
- **Scan-to-Confirm Time**: <2 minutes average
- **User Satisfaction**: >4.0/5.0 rating
- **Feature Completion Rate**: >80% (users who scan complete the flow)

### Business Metrics
- **Scans per User per Week**: Target 2-3
- **Recipe Generation from Scans**: >70% conversion
- **User Retention**: +30% for users who scan regularly

---

## Edge Cases & Error Handling

### 1. Poor Image Quality
```python
def detect_image_quality(image_bytes: bytes) -> dict:
    """Check if image is usable for detection."""
    
    # Use OpenCV or similar
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    
    # Check brightness
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray)
    
    # Check blur
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    
    issues = []
    if brightness < 50:
        issues.append("too_dark")
    elif brightness > 200:
        issues.append("too_bright")
    
    if laplacian_var < 100:
        issues.append("too_blurry")
    
    return {
        "usable": len(issues) == 0,
        "issues": issues,
        "brightness": brightness,
        "sharpness": laplacian_var
    }
```

**UX**: Show tips to retake photo if quality is poor

### 2. No Items Detected
```python
if len(detected_items) == 0:
    return {
        "success": False,
        "error": "no_items_detected",
        "suggestions": [
            "Make sure items are clearly visible",
            "Ensure good lighting",
            "Get closer to items",
            "Try multiple photos from different angles"
        ]
    }
```

### 3. Mis-Identified Allergen (CRITICAL)
```python
# User reports: "This was detected as peanuts but it's actually chickpeas"

async def report_allergen_misidentification(
    scan_id: str,
    ingredient_detected: str,
    actual_ingredient: str,
    user_id: str
):
    """
    CRITICAL: Log allergen misidentification for urgent review.
    """
    
    await db.execute("""
        INSERT INTO allergen_misidentification_reports (
            scan_id, detected, actual, user_id, severity, created_at
        ) VALUES ($1, $2, $3, $4, 'critical', NOW())
    """, (scan_id, ingredient_detected, actual_ingredient, user_id))
    
    # ALERT engineering team immediately
    await send_alert(
        severity="P0",
        message=f"Allergen misidentification: {ingredient_detected} detected, actually {actual_ingredient}",
        scan_id=scan_id
    )
    
    # Review vision model prompt
    # May need to adjust detection thresholds
```

---

## Testing Strategy

### Unit Tests
```python
def test_ingredient_normalization():
    assert normalize_ingredient_name("whole milk") == "milk"
    assert normalize_ingredient_name("roma tomatoes") == "tomato"

def test_confidence_classification():
    assert classify_confidence(0.9) == ConfidenceLevel.HIGH
    assert classify_confidence(0.6) == ConfidenceLevel.MEDIUM
    assert classify_confidence(0.3) == ConfidenceLevel.LOW

def test_allergen_detection():
    profile = {"members": [{"allergens": ["peanuts"]}]}
    safety = check_scanned_ingredients_safety(["peanut_butter"], profile)
    assert not safety["safe"]
    assert len(safety["warnings"]) > 0
```

### Integration Tests
```python
async def test_end_to_end_scan():
    # Upload image
    response = await client.post(
        "/api/scanning/analyze-image",
        files={"file": open("test_pantry.jpg", "rb")}
    )
    assert response.status_code == 200
    
    scan_result = response.json()
    assert "detected_items" in scan_result
    assert len(scan_result["detected_items"]) > 0
    
    # Confirm items
    confirm_response = await client.post(
        "/api/scanning/confirm-ingredients",
        json={
            "scan_id": scan_result["scan_id"],
            "confirmed_items": scan_result["detected_items"]
        }
    )
    assert confirm_response.status_code == 200
```

### User Acceptance Testing
1. Test with 10 different pantry photos
2. Measure detection accuracy
3. Track user correction rate
4. Test allergen warning flow
5. Verify database saves correctly

---

## Summary: Why This is Foundation

**This vision scanning system is foundational because**:

1. **Trust**: Users trust SAVO when they can SEE and CONFIRM what was detected
2. **Safety**: Allergen warnings at scan time prevent dangerous mistakes
3. **Accuracy**: Confirmation flow catches errors before recipe generation
4. **Learning**: Feedback loop continuously improves model
5. **UX**: Fast, transparent, user-controlled = high adoption

**Without this foundation**:
- ❌ Recipe generation is based on wrong ingredients
- ❌ Allergen mis-identification creates liability
- ❌ Users abandon feature due to poor accuracy
- ❌ No way to improve system over time

**With this foundation**:
- ✅ Confirmed ingredient list feeds accurate recipes
- ✅ Safety checks at multiple points
- ✅ User feels in control
- ✅ System learns and improves
- ✅ High user satisfaction and retention

---

**Next Steps**: Implement Phase 1 (Foundation) and test with real pantry images.
