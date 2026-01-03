"""
Generate Multi-Cuisine, Multilingual Recipes using SAVO
Ingredients: Paneer, Tomato, Rice, Onion
Requirements:
- Intermediate+ cooking level
- Multiple cuisines (Indian, Mediterranean, Mexican, Korean, etc.)
- Multiple languages (native + English)
- Multiple dish types (main, appetizer, rice dishes)
- Detailed nutrition, health benefits, cooking instructions
"""

import asyncio
import json
from app.core.ingredient_combinations import (
    IngredientCombinationEngine,
    generate_combination_recipe_prompt,
    INGREDIENT_DATABASE
)
from app.core.llm_client import OpenAIClient
import os

# Ingredients requested
INGREDIENTS = ["paneer", "tomato", "rice", "onion"]

# Cuisine configurations with language mappings
CUISINES = [
    {
        "cuisine": "Indian",
        "language": "Hindi",
        "language_code": "hi-IN",
        "dish_types": ["Main Course - Biryani", "Main Course - Curry with Rice"],
        "religious_considerations": ["Hindu", "Sikh", "Jain (no onion variant)"]
    },
    {
        "cuisine": "Mediterranean/Greek",
        "language": "Greek",
        "language_code": "el-GR",
        "dish_types": ["Main Course - Stuffed Vegetables", "Appetizer - Fried Rice Balls"],
        "religious_considerations": ["Kosher-friendly", "Halal-friendly"]
    },
    {
        "cuisine": "Spanish",
        "language": "Spanish",
        "language_code": "es-ES",
        "dish_types": ["Main Course - Paella", "Appetizer - Tapas"],
        "religious_considerations": ["Universal"]
    },
    {
        "cuisine": "Persian",
        "language": "Farsi",
        "language_code": "fa-IR",
        "dish_types": ["Main Course - Jeweled Rice", "Main Course - Rice with Tahdig"],
        "religious_considerations": ["Halal"]
    },
    {
        "cuisine": "Mexican",
        "language": "Spanish",
        "language_code": "es-MX",
        "dish_types": ["Main Course - Arroz Rojo", "Main Course - Burrito Bowl"],
        "religious_considerations": ["Universal"]
    },
    {
        "cuisine": "Korean",
        "language": "Korean",
        "language_code": "ko-KR",
        "dish_types": ["Main Course - Fried Rice", "Side Dish - Paneer Banchan"],
        "religious_considerations": ["Buddhist-friendly"]
    },
    {
        "cuisine": "Italian",
        "language": "Italian",
        "language_code": "it-IT",
        "dish_types": ["Main Course - Risotto", "Appetizer - Arancini"],
        "religious_considerations": ["Universal"]
    }
]


def create_recipe_prompt(cuisine_config, dish_type_idx=0):
    """Create LLM prompt for recipe generation"""
    cuisine = cuisine_config["cuisine"]
    lang = cuisine_config["language"]
    lang_code = cuisine_config["language_code"]
    dish_type = cuisine_config["dish_types"][dish_type_idx]
    religious = ", ".join(cuisine_config["religious_considerations"])
    
    prompt = f"""
Generate a detailed recipe using these ingredients: {', '.join(INGREDIENTS)}

RECIPE REQUIREMENTS:
- Cuisine: {cuisine}
- Dish Type: {dish_type}
- Cooking Level: Intermediate or Advanced
- Religious/Dietary: {religious}

BILINGUAL OUTPUT REQUIRED:
1. Recipe Name: Provide in BOTH {lang} ({lang_code}) AND English
   Example format: "Recipe Name ({lang}): [name in {lang}] | English: [English name]"

2. All section headers should be bilingual

REQUIRED SECTIONS:

### 1. Recipe Name & Overview
- Name in {lang} and English
- Brief description (2-3 sentences)
- Cooking level: Intermediate/Advanced
- Total time, Prep time, Cook time
- Servings

### 2. Ingredients (with measurements)
- List all ingredients with precise measurements
- Include both metric and imperial where relevant
- Specify quality (e.g., "firm paneer", "ripe tomatoes")

### 3. Detailed Cooking Instructions
- Step-by-step with timing for each step
- Include intermediate+ techniques (e.g., "dum cooking", "tahdig", "socarrat", "wok hei")
- Temperature specifications
- Visual cues for doneness

### 4. Nutrition Information (Per Serving)
Provide exact values:
- Total Calories (kcal)
- Protein (g)
- Carbohydrates (g)
- Fat (g)
- Fiber (g)
- Sodium (mg)
- Sugar (g)
- Key vitamins/minerals

### 5. Health Benefits
Explain health benefits of key ingredients:
- Paneer: [benefits]
- Tomato: [benefits]
- Rice: [benefits]
- Onion: [benefits]
- Any added spices/ingredients

### 6. Cultural Context
- Brief history or cultural significance
- Traditional serving suggestions
- Occasions when this dish is typically served

### 7. Chef's Tips
- Pro tips for best results
- Common mistakes to avoid
- Variations possible

### 8. Dietary Information
- Specify: Vegetarian/Vegan/Halal/Kosher status
- Allergens present (dairy from paneer)
- Suitable for: {religious}

IMPORTANT FORMAT RULES:
- Use markdown formatting
- All measurements in both metric AND imperial
- Include {lang} script for recipe name and key terms
- Provide English translation immediately after {lang} text
- Be precise with nutrition values (research-backed)
- Intermediate-level detail in instructions

Generate the complete recipe now:
"""
    return prompt


async def generate_recipes():
    """Generate all recipes using SAVO's LLM client"""
    
    # Check if OpenAI key is available
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("❌ OPENAI_API_KEY not set. Cannot generate recipes.")
        print("Set it with: $env:OPENAI_API_KEY = 'your-key'")
        return
    
    # Initialize SAVO's OpenAI client
    llm_client = OpenAIClient(api_key=api_key, model="gpt-4o", timeout=120)
    
    print("\n" + "="*80)
    print("SAVO Multi-Cuisine Recipe Generator")
    print("="*80)
    print(f"Ingredients: {', '.join(INGREDIENTS)}")
    print(f"Cooking Level: Intermediate+")
    print(f"Output: Bilingual (Native Language + English)")
    print(f"Total Cuisines: {len(CUISINES)}")
    print("="*80 + "\n")
    
    all_recipes = []
    
    for idx, cuisine_config in enumerate(CUISINES, 1):
        print(f"\n[{idx}/{len(CUISINES)}] Generating {cuisine_config['cuisine']} recipe...")
        print(f"   Language: {cuisine_config['language']}")
        print(f"   Dish: {cuisine_config['dish_types'][0]}")
        
        try:
            # Create prompt
            prompt = create_recipe_prompt(cuisine_config, dish_type_idx=0)
            
            # Call SAVO's LLM
            messages = [
                {"role": "system", "content": "You are SAVO, an expert culinary AI that generates detailed, culturally authentic recipes with precise nutrition information and bilingual output."},
                {"role": "user", "content": prompt}
            ]
            
            # Note: OpenAIClient.generate_json expects schema, but we want text
            # So we'll use a simple schema and extract text
            schema = {
                "type": "object",
                "properties": {
                    "recipe_markdown": {"type": "string"}
                },
                "required": ["recipe_markdown"]
            }
            
            # Generate (with longer timeout for detailed recipes)
            response = await llm_client.generate_json(messages=messages, schema=schema)
            
            recipe_text = response.get("recipe_markdown", "")
            
            if recipe_text:
                print(f"   ✅ Generated successfully ({len(recipe_text)} chars)")
                all_recipes.append({
                    "cuisine": cuisine_config["cuisine"],
                    "language": cuisine_config["language"],
                    "recipe": recipe_text
                })
            else:
                print(f"   ⚠️  Empty recipe returned")
                
        except Exception as e:
            print(f"   ❌ Error: {str(e)}")
            continue
    
    # Save all recipes to markdown file
    if all_recipes:
        output_file = "GENERATED_RECIPES_MULTI_CUISINE.md"
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# SAVO Multi-Cuisine Recipes\n\n")
            f.write("**Ingredients:** Paneer, Tomato, Rice, Onion\n\n")
            f.write("**Cooking Level:** Intermediate to Advanced\n\n")
            f.write("**Generated:** Using SAVO AI Recipe Generation System\n\n")
            f.write("---\n\n")
            
            for idx, recipe_data in enumerate(all_recipes, 1):
                f.write(f"## {idx}. {recipe_data['cuisine']} Cuisine ({recipe_data['language']})\n\n")
                f.write(recipe_data['recipe'])
                f.write("\n\n---\n\n")
        
        print(f"\n\n✅ SUCCESS! Generated {len(all_recipes)} recipes")
        print(f"📄 Saved to: {output_file}")
        print(f"\nRecipes include:")
        for recipe in all_recipes:
            print(f"  - {recipe['cuisine']} ({recipe['language']} + English)")
    else:
        print("\n\n❌ No recipes generated")


if __name__ == "__main__":
    # Run async
    asyncio.run(generate_recipes())
