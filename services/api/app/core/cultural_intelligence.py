"""
SAVO — Cultural Intelligence Engine

Provides deep cultural knowledge about ingredient combinations,
traditional pairings, and culinary wisdom across global cuisines.

This module enriches AI prompts with:
- Traditional ingredient synergies
- Cultural significance of combinations
- Nutritional wisdom from traditional practices
- Flavor science explanations
- Regional variations and adaptations

Author: SAVO Team
Date: January 2, 2026
"""

from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


# Cultural knowledge base for ingredient combinations
CULTURAL_COMBINATIONS = {
    # South Indian Classics
    ("black_channa", "tamarind", "eggplant"): {
        "region": "South India",
        "traditional_name": {
            "tamil": "Karuppu Kondaikadalai Vangi Pulusu",
            "telugu": "Vankaya Kala Chana Pulusu",
            "kannada": "Kaala Chana Badanekayi Huli",
            "malayalam": "Karutha Kadala Vanga Curry"
        },
        "why_beloved": [
            "Protein Powerhouse: Black channa provides vegetarian protein traditionally gotten from dal",
            "Digestive Aid: Tamarind's acidity helps digest the heavy chickpeas and reduces gas",
            "Texture Balance: Eggplant's soft, silky texture complements chickpea's firm, nutty bite",
            "Flavor Complexity: Sour (tamarind) + earthy (channa) + umami (eggplant) = layered taste",
            "Economic: All three ingredients are affordable and widely available across South India",
            "Seasonal: Works year-round with different eggplant varieties (round, long, white)",
            "Festive: Can be dressed up for special occasions (weddings) or kept simple for daily meals",
            "Ayurvedic: Balances vata and kapha doshas when cooked with warming spices"
        ],
        "nutritional_wisdom": {
            "protein_fiber": "Black channa provides 15g protein + 12g fiber per cup - complete vegetarian meal",
            "vitamin_c": "Tamarind's vitamin C helps absorb iron from chickpeas (critical for vegetarians)",
            "antioxidants": "Eggplant's nasunin (anthocyanin) protects brain cells and reduces inflammation",
            "low_calorie": "Eggplant is 95% water - adds bulk and satiety without calories"
        },
        "flavor_science": {
            "sour_umami": "Tamarind's tartaric acid enhances umami perception in eggplant",
            "maillard": "Roasting eggplant creates melanoidins that complement chickpea's nuttiness",
            "tempering": "Mustard seeds + curry leaves release sulfur compounds that tie flavors together",
            "heat_balance": "Chili heat is mellowed by eggplant's cooling properties"
        },
        "cooking_techniques": [
            "Tempering (tadka): Mustard seeds, cumin, curry leaves fried in oil first",
            "Pressure cooking channa: Reduces cooking time from 2hrs to 20min",
            "Charring eggplant: Adds smoky depth (can use stovetop flame or oven broiler)",
            "Tamarind extraction: Soak in warm water, squeeze, strain - never boil (loses flavor)"
        ],
        "regional_variations": {
            "andhra": "Very spicy with red chili powder, served with rice",
            "karnataka": "Sambar-style with more liquid, eaten with rice or dosa",
            "tamil_nadu": "One-pot rice dish (Vangi Bath style) with dry-roasted spices",
            "kerala": "Coconut-based curry with fresh curry leaves and coconut oil"
        },
        "serving_traditions": [
            "Serve hot with steamed rice or roti",
            "Accompaniment: Cucumber raita or yogurt to balance heat",
            "Garnish: Fresh coriander, grated coconut, lime wedges",
            "Temperature: Best served piping hot (flavors meld)"
        ]
    },
    
    # Italian Classic
    ("tomato", "mozzarella", "basil"): {
        "region": "Southern Italy (Campania)",
        "traditional_name": {
            "italian": "Caprese" or "Insalata Caprese"
        },
        "why_beloved": [
            "Simplicity: Only 3 ingredients showcase Italian 'cucina povera' (peasant cooking)",
            "Colors of Flag: Red (tomato) + white (mozzarella) + green (basil) = Italian patriotism",
            "Summer Peak: All ingredients at their best in July-August Mediterranean climate",
            "Buffalo Tradition: Originally made with buffalo mozzarella from Campania",
            "No Cooking: Perfect for hot summers when you don't want to turn on the stove",
            "Versatility: Works as salad, pizza topping, or panini filling"
        ],
        "nutritional_wisdom": {
            "lycopene": "Tomato's lycopene (antioxidant) is fat-soluble - mozzarella's fat aids absorption",
            "protein_calcium": "Mozzarella provides complete protein + calcium (muscle and bone health)",
            "vitamin_k": "Fresh basil is vitamin K powerhouse (blood clotting, bone health)",
            "hydration": "Tomatoes are 94% water - hydrating in Mediterranean heat"
        },
        "flavor_science": {
            "umami_fat": "Tomato's glutamate + mozzarella's fat = umami bomb",
            "aromatic_balance": "Basil's eugenol (clove-like) complements tomato's acidity",
            "temperature": "Room temperature is critical - cold kills tomato flavor",
            "salt_timing": "Salt tomatoes first to draw out juice, creating natural dressing"
        },
        "cooking_techniques": [
            "Never refrigerate tomatoes - kills flavor and texture",
            "Tear basil by hand - cutting with knife causes oxidation (black edges)",
            "Use best quality: San Marzano tomatoes, buffalo mozzarella di bufala",
            "Drizzle: Extra virgin olive oil, aged balsamic vinegar optional"
        ],
        "regional_variations": {
            "neapolitan": "Buffalo mozzarella, no balsamic (purist approach)",
            "sicilian": "Add oregano, capers, olives",
            "modern": "Grilled peaches instead of tomatoes, burrata instead of mozzarella"
        }
    },
    
    # North Indian Classic
    ("paneer", "spinach", "cream"): {
        "region": "North India (Punjab)",
        "traditional_name": {
            "hindi": "Palak Paneer",
            "punjabi": "Palak Paneer"
        },
        "why_beloved": [
            "Vegetarian Protein: Paneer (20g protein per 100g) makes this vegetarian powerhouse",
            "Iron Source: Spinach provides iron critical in vegetarian Indian diets",
            "Comfort Food: Creamy, mild - perfect for kids and spice-sensitive eaters",
            "Restaurant Staple: One of most ordered dishes in Indian restaurants globally",
            "Weeknight Easy: Quick cooking, widely available ingredients",
            "Versatile: Eat with roti, naan, rice, or even as pizza topping"
        ],
        "nutritional_wisdom": {
            "iron_absorption": "Paneer's protein enhances iron absorption from spinach (better than vitamin C alone)",
            "calcium_conflict": "Spinach has oxalates that bind calcium - blanching reduces oxalates",
            "complete_meal": "Protein (paneer) + fiber (spinach) + healthy fats (cream) = balanced",
            "vitamin_a": "Spinach is vitamin A powerhouse (eye health, immunity)"
        },
        "flavor_science": {
            "bitter_cream": "Cream's fat masks spinach's bitter notes (oxalates)",
            "maillard_paneer": "Frying paneer creates golden crust with nutty flavors",
            "garlic_ginger": "Aromatic base cuts through cream's richness",
            "garam_masala": "Warming spices balance spinach's cooling properties"
        },
        "cooking_techniques": [
            "Blanch spinach: Boil 2min, ice bath - preserves bright green color",
            "Don't overcook: Spinach turns khaki-colored if boiled too long",
            "Fry paneer first: Creates texture contrast - soft interior, crispy exterior",
            "Kasuri methi: Dried fenugreek leaves add restaurant-quality aroma"
        ]
    },
    
    # Chinese Classic
    ("soy_sauce", "ginger", "garlic"): {
        "region": "China (Universal)",
        "traditional_name": {
            "chinese": "三香 (Sān xiāng - Three Aromas)"
        },
        "why_beloved": [
            "Holy Trinity: Like French mirepoix, this is the base of most Chinese stir-fries",
            "Umami Foundation: Soy sauce provides glutamate, the base of savory flavors",
            "Medicinal: Traditional Chinese medicine uses ginger-garlic for warming properties",
            "Preservation: All three ingredients preserve food (salt, antimicrobials)",
            "Versatile: Works with vegetables, meat, seafood, tofu",
            "Quick Cooking: Stir-fry technique means dinner in 10 minutes"
        ],
        "nutritional_wisdom": {
            "anti_inflammatory": "Ginger's gingerol + garlic's allicin = powerful anti-inflammatory combo",
            "digestion": "Ginger aids digestion, reduces nausea (morning sickness, motion sickness)",
            "immunity": "Garlic's sulfur compounds boost immune function",
            "sodium_balance": "Soy sauce provides sodium but use low-sodium versions"
        },
        "flavor_science": {
            "umami_trinity": "Soy sauce (glutamate) + shiitake (guanylate) = synergistic umami (8x stronger)",
            "aromatic_compounds": "Ginger-garlic release sulfur compounds when heated (Maillard reaction)",
            "heat_tolerance": "Soy sauce's amino acids caramelize at high heat (wok hei - breath of wok)",
            "order_matters": "Ginger-garlic first, soy sauce last (prevents burning)"
        },
        "cooking_techniques": [
            "Mince ginger-garlic together: Creates paste that distributes evenly",
            "High heat, quick cook: Stir-fry at 400°F+ for 30 seconds max",
            "Soy sauce varieties: Light (saltier), dark (sweeter, thicker), tamari (gluten-free)",
            "Wok shape: Concentrates heat, allows tossing without spilling"
        ]
    }
}


def get_cultural_context(ingredients: List[str]) -> Optional[Dict]:
    """
    Retrieve cultural context for ingredient combination.
    
    Args:
        ingredients: List of ingredient names
    
    Returns:
        Cultural context dict or None if no match
    """
    # Normalize ingredients
    normalized = tuple(sorted([ing.lower().strip().replace(" ", "_") for ing in ingredients]))
    
    # Direct match
    if normalized in CULTURAL_COMBINATIONS:
        return CULTURAL_COMBINATIONS[normalized]
    
    # Subset match (e.g., user provided 2 of 3 key ingredients)
    for combo_key, context in CULTURAL_COMBINATIONS.items():
        if len(set(normalized) & set(combo_key)) >= 2:  # At least 2 ingredients match
            return context
    
    return None


def build_cultural_intelligence_prompt(
    ingredients: List[str],
    cuisine: Optional[str] = None
) -> str:
    """
    Build cultural intelligence section for AI prompt.
    
    This provides the LLM with traditional wisdom about ingredient combinations
    so it can generate culturally-aware, nutritionally-informed recipes.
    
    Args:
        ingredients: List of ingredients
        cuisine: Optional cuisine context
    
    Returns:
        Formatted cultural intelligence prompt section
    """
    
    # Check if we have cultural knowledge about this combination
    cultural_context = get_cultural_context(ingredients)
    
    if cultural_context:
        # We have deep knowledge - provide it to LLM
        region = cultural_context.get("region", "")
        why_beloved = cultural_context.get("why_beloved", [])
        nutritional = cultural_context.get("nutritional_wisdom", {})
        flavor = cultural_context.get("flavor_science", {})
        techniques = cultural_context.get("cooking_techniques", [])
        
        prompt = f"""
CULTURAL INTELLIGENCE - {region.upper()} TRADITION:

This ingredient combination is WELL-KNOWN in {region} cuisine.

WHY THIS COMBINATION IS BELOVED:
{chr(10).join(f"- {reason}" for reason in why_beloved)}

NUTRITIONAL WISDOM (Traditional Knowledge):
{chr(10).join(f"- {key.replace('_', ' ').title()}: {value}" for key, value in nutritional.items())}

FLAVOR SCIENCE:
{chr(10).join(f"- {key.replace('_', ' ').title()}: {value}" for key, value in flavor.items())}

TRADITIONAL COOKING TECHNIQUES:
{chr(10).join(f"- {technique}" for technique in techniques)}

INSTRUCTIONS FOR AI:
- Use this cultural knowledge to inform your recipe
- Explain WHY this combination works (refer to above points)
- Include traditional cooking techniques where appropriate
- Maintain authenticity while respecting dietary constraints
- Generate "cultural_context" field in response explaining significance
"""
        
        return prompt
    
    else:
        # No specific knowledge - ask LLM to research and explain
        ingredients_str = ", ".join(ingredients)
        cuisine_str = f"in {cuisine} cuisine" if cuisine else "across global cuisines"
        
        prompt = f"""
CULTURAL INTELLIGENCE TASK:

The user wants to cook with: {ingredients_str}

Your task is to:
1. Identify which cuisine(s) traditionally pair these ingredients
2. Explain WHY this combination works:
   - Nutritional synergies (e.g., vitamin C aids iron absorption)
   - Texture balance (soft vs. crunchy, creamy vs. light)
   - Flavor complexity (sweet + sour + umami layers)
   - Economic/seasonal factors (why it became traditional)
3. Include traditional wisdom {cuisine_str}
4. Explain flavor science behind the pairing
5. Provide cooking techniques that honor the tradition

Generate a "cultural_context" object in your response with:
{{
  "why_this_combo": ["reason 1", "reason 2", ...],
  "nutritional_benefits": ["benefit 1", "benefit 2", ...],
  "flavor_science": ["science point 1", "science point 2", ...],
  "traditional_wisdom": "paragraph explaining cultural significance",
  "cooking_tips": ["tip 1", "tip 2", ...]
}}

Use authentic culinary knowledge. Do not make assumptions.
"""
        
        return prompt


def enrich_recipe_with_culture(recipe: Dict, ingredients: List[str]) -> Dict:
    """
    Enrich a generated recipe with cultural context.
    
    Post-processing step to add cultural intelligence even if
    LLM didn't generate it.
    
    Args:
        recipe: Generated recipe dict
        ingredients: Ingredients used
    
    Returns:
        Enriched recipe with cultural_context field
    """
    
    # Check if LLM already provided cultural context
    if "cultural_context" in recipe:
        return recipe
    
    # Try to add our cultural knowledge
    cultural_context = get_cultural_context(ingredients)
    
    if cultural_context:
        recipe["cultural_context"] = {
            "region": cultural_context["region"],
            "why_this_combo": cultural_context["why_beloved"][:5],  # Top 5 reasons
            "nutritional_benefits": list(cultural_context["nutritional_wisdom"].values())[:3],
            "cooking_tips": cultural_context["cooking_techniques"][:3]
        }
        
        # Add traditional name if available
        if "traditional_name" in cultural_context:
            recipe["traditional_names"] = cultural_context["traditional_name"]
    
    return recipe


# Convenience function for API usage
def get_cultural_intelligence_for_combination(
    ingredients: List[str],
    cuisine: Optional[str] = None
) -> Dict:
    """
    Get cultural intelligence summary for ingredient combination.
    
    Returns:
        {
            "has_traditional_knowledge": bool,
            "region": str,
            "cultural_prompt": str,
            "traditional_names": dict,
            "why_beloved": list
        }
    """
    
    cultural_context = get_cultural_context(ingredients)
    
    if cultural_context:
        return {
            "has_traditional_knowledge": True,
            "region": cultural_context["region"],
            "cultural_prompt": build_cultural_intelligence_prompt(ingredients, cuisine),
            "traditional_names": cultural_context.get("traditional_name", {}),
            "why_beloved": cultural_context["why_beloved"]
        }
    else:
        return {
            "has_traditional_knowledge": False,
            "region": "unknown",
            "cultural_prompt": build_cultural_intelligence_prompt(ingredients, cuisine),
            "traditional_names": {},
            "why_beloved": []
        }
