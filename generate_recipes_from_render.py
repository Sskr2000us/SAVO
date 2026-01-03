"""
Generate Multi-Cuisine, Multilingual Recipes using SAVO Render API
Uses your deployed backend at https://savo-ynp1.onrender.com
"""

import requests
import json
from datetime import datetime

# Your deployed SAVO API
API_BASE_URL = "https://savo-ynp1.onrender.com"

# Ingredients
INGREDIENTS = ["paneer", "tomato", "rice", "onion"]

# Recipe requests for different cuisines with bilingual requirements
RECIPE_REQUESTS = [
    {
        "cuisine": "Indian",
        "dish_type": "Main Course",
        "language": "Hindi",
        "language_code": "hi-IN",
        "recipe_name": "Paneer Biryani (पनीर बिरयानी)",
        "religious": ["Vegetarian", "Hindu", "Sikh", "Jain-friendly (no onion variant)"]
    },
    {
        "cuisine": "Mediterranean",
        "dish_type": "Main Course",
        "language": "Greek",
        "language_code": "el-GR",
        "recipe_name": "Gemista (Ντομάτες Γεμιστές)",
        "religious": ["Vegetarian", "Kosher-friendly", "Halal-friendly"]
    },
    {
        "cuisine": "Spanish",
        "dish_type": "Main Course",
        "language": "Spanish",
        "language_code": "es-ES",
        "recipe_name": "Paella Vegetariana",
        "religious": ["Vegetarian", "Universal"]
    },
    {
        "cuisine": "Persian",
        "dish_type": "Main Course",
        "language": "Farsi",
        "language_code": "fa-IR",
        "recipe_name": "Morasa Polo (مرصع پلو)",
        "religious": ["Vegetarian", "Halal"]
    },
    {
        "cuisine": "Mexican",
        "dish_type": "Main Course",
        "language": "Spanish",
        "language_code": "es-MX",
        "recipe_name": "Arroz Rojo con Paneer",
        "religious": ["Vegetarian", "Universal"]
    },
    {
        "cuisine": "Korean",
        "dish_type": "Main Course",
        "language": "Korean",
        "language_code": "ko-KR",
        "recipe_name": "Paneer Kimchi Bokkeum-bap (파니르 김치 볶음밥)",
        "religious": ["Vegetarian", "Buddhist-friendly"]
    },
    {
        "cuisine": "Italian",
        "dish_type": "Main Course",
        "language": "Italian",
        "language_code": "it-IT",
        "recipe_name": "Risotto al Pomodoro con Paneer",
        "religious": ["Vegetarian", "Universal"]
    }
]


def test_api_health():
    """Test if SAVO API is responsive"""
    print("\n🔍 Checking SAVO API health...")
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if response.status_code == 200:
            print("✅ SAVO API is online and healthy")
            return True
        else:
            print(f"⚠️  API returned status {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Cannot reach SAVO API: {str(e)}")
        return False


def generate_recipe_with_savo(recipe_config):
    """
    Call SAVO API /plan/daily to generate a detailed recipe
    Uses the actual SAVO planning endpoint
    """
    
    # Map cuisine names to SAVO cuisine IDs
    cuisine_map = {
        "Indian": "indian",
        "Mediterranean": "mediterranean",
        "Spanish": "spanish",
        "Persian": "persian",
        "Mexican": "mexican",
        "Korean": "korean",
        "Italian": "italian"
    }
    
    cuisine_id = cuisine_map.get(recipe_config['cuisine'], "indian")
    
    # Use SAVO's /plan/daily endpoint
    endpoint = f"{API_BASE_URL}/plan/daily"
    
    payload = {
        "time_available_minutes": 60,  # Intermediate+ recipes
        "servings": 4,
        "meal_type": "dinner",
        "selected_cuisine": cuisine_id,
        "output_language": recipe_config['language_code'],
        "measurement_system": "metric",
        "inventory": {
            "available_ingredients": INGREDIENTS
        },
        "family_profile": {
            "members": [
                {
                    "name": "User",
                    "age": 30,
                    "dietary_restrictions": ["vegetarian"],
                    "allergens": [],  # No allergens
                    "health_conditions": [],
                    "spice_tolerance": "medium"
                }
            ],
            "household_allergens": [],  # No household allergens
            "dietary_restrictions": ["vegetarian"],
            "skill_level": 3  # Intermediate
        }
    }
    
    try:
        response = requests.post(endpoint, json=payload, timeout=120)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"   ⚠️  API returned {response.status_code}: {response.text[:500]}")
            return None
            
    except Exception as e:
        print(f"   ❌ Error calling API: {str(e)}")
        return None


def main():
    """Main execution"""
    print("="*80)
    print("SAVO Multi-Cuisine Recipe Generator (Using Render API)")
    print("="*80)
    print(f"API: {API_BASE_URL}")
    print(f"Ingredients: {', '.join(INGREDIENTS)}")
    print(f"Total Recipes: {len(RECIPE_REQUESTS)}")
    print("="*80)
    
    # Test API health
    if not test_api_health():
        print("\n❌ Cannot proceed - SAVO API is not accessible")
        print("\nPlease check:")
        print("1. Is your Render service running?")
        print("2. Is OPENAI_API_KEY set in Render environment variables?")
        print("3. Visit: https://dashboard.render.com")
        return
    
    print(f"\n🚀 Starting recipe generation at {datetime.now().strftime('%H:%M:%S')}")
    
    generated_recipes = []
    
    for idx, config in enumerate(RECIPE_REQUESTS, 1):
        print(f"\n[{idx}/{len(RECIPE_REQUESTS)}] Generating {config['cuisine']} recipe...")
        print(f"   📖 {config['recipe_name']}")
        print(f"   🌍 Language: {config['language']} + English")
        
        result = generate_recipe_with_savo(config)
        
        if result:
            print(f"   ✅ Generated successfully!")
            generated_recipes.append({
                "config": config,
                "recipe": result
            })
        else:
            print(f"   ⚠️  Generation failed")
    
    # Save results
    if generated_recipes:
        output_file = "SAVO_GENERATED_RECIPES.md"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("# SAVO Multi-Cuisine Recipes\n\n")
            f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"**Powered by:** SAVO API (https://savo-ynp1.onrender.com)\n\n")
            f.write(f"**Ingredients:** {', '.join(INGREDIENTS)}\n\n")
            f.write("**Cooking Level:** Intermediate to Advanced\n\n")
            f.write("**Languages:** Bilingual (Native + English)\n\n")
            f.write("---\n\n")
            
            for idx, item in enumerate(generated_recipes, 1):
                config = item['config']
                recipe_data = item['recipe']
                
                f.write(f"## {idx}. {config['recipe_name']}\n\n")
                f.write(f"**Cuisine:** {config['cuisine']}\n\n")
                f.write(f"**Languages:** {config['language']} + English\n\n")
                f.write(f"**Religious Compatibility:** {', '.join(config['religious'])}\n\n")
                
                # Extract the menu/recipe from SAVO response
                if isinstance(recipe_data, dict):
                    # SAVO returns MenuPlanResponse with menus array
                    if 'menus' in recipe_data and recipe_data['menus']:
                        menu = recipe_data['menus'][0]
                        
                        # Write recipe details
                        if 'recipes' in menu and menu['recipes']:
                            recipe = menu['recipes'][0]
                            
                            # Recipe name (bilingual if available)
                            if 'recipe_name' in recipe:
                                names = recipe['recipe_name']
                                if isinstance(names, dict):
                                    for lang, name in names.items():
                                        f.write(f"**{lang.upper()}:** {name}\n\n")
                                else:
                                    f.write(f"**Recipe:** {names}\n\n")
                            
                            # Instructions
                            if 'instructions' in recipe:
                                f.write("### Instructions\n\n")
                                instructions = recipe['instructions']
                                if isinstance(instructions, dict):
                                    for lang, steps in instructions.items():
                                        f.write(f"**{lang.upper()}:**\n")
                                        if isinstance(steps, list):
                                            for i, step in enumerate(steps, 1):
                                                f.write(f"{i}. {step}\n")
                                        f.write("\n")
                                else:
                                    f.write(f"{instructions}\n\n")
                            
                            # Nutrition
                            if 'nutrition' in recipe:
                                f.write("### Nutrition (Per Serving)\n\n")
                                nutrition = recipe['nutrition']
                                for key, value in nutrition.items():
                                    f.write(f"- **{key.replace('_', ' ').title()}:** {value}\n")
                                f.write("\n")
                            
                            # Full recipe JSON for reference
                            f.write("### Full Recipe Data\n\n")
                            f.write(f"```json\n{json.dumps(recipe, indent=2)}\n```\n\n")
                        else:
                            # Fallback: write entire menu
                            f.write(f"```json\n{json.dumps(menu, indent=2)}\n```\n\n")
                    else:
                        # Fallback: write entire response
                        f.write(f"```json\n{json.dumps(recipe_data, indent=2)}\n```\n\n")
                else:
                    f.write(str(recipe_data))
                
                f.write("\n\n---\n\n")
        
        print(f"\n\n✅ SUCCESS! Generated {len(generated_recipes)} recipes")
        print(f"📄 Saved to: {output_file}")
        print(f"\n📊 Summary:")
        for item in generated_recipes:
            config = item['config']
            print(f"  ✓ {config['cuisine']} - {config['recipe_name']}")
    else:
        print("\n\n❌ No recipes were generated")
        print("\nTroubleshooting:")
        print("1. Check Render logs: https://dashboard.render.com")
        print("2. Verify OPENAI_API_KEY is set in environment variables")
        print("3. Try: curl https://savo-ynp1.onrender.com/health")


if __name__ == "__main__":
    main()
