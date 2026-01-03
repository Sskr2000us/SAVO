"""
Generate recipes using authenticated SAVO user
User: sureshvidh@gmail.com
"""

import requests
import json
from datetime import datetime

API_BASE_URL = "https://savo-ynp1.onrender.com"
TEST_USER_EMAIL = "sureshvidh@gmail.com"

# Ingredients
INGREDIENTS = ["paneer", "tomato", "rice", "onion"]

# Get JWT token from Supabase (you may need to provide this manually)
# For testing, we'll try to call the endpoint with the user_id directly

def get_user_profile():
    """Get user profile and ID"""
    # This would normally require authentication
    # For now, let's try calling the planning endpoint directly
    print(f"🔍 Looking up user: {TEST_USER_EMAIL}")
    print("   Note: This requires the user to be logged in via the Flutter app")
    return None


def generate_recipe_with_auth(cuisine_config, user_token=None):
    """Generate recipe with authentication"""
    
    cuisine_map = {
        "Indian": "indian",
        "Mediterranean": "mediterranean", 
        "Spanish": "spanish",
        "Persian": "persian",
        "Mexican": "mexican",
        "Korean": "korean",
        "Italian": "italian"
    }
    
    cuisine_id = cuisine_map.get(cuisine_config['cuisine'], "indian")
    endpoint = f"{API_BASE_URL}/plan/daily"
    
    payload = {
        "time_available_minutes": 60,
        "servings": 4,
        "meal_type": "dinner",
        "selected_cuisine": cuisine_id,
        "output_language": cuisine_config['language_code'],
        "measurement_system": "metric",
        "inventory": {
            "available_ingredients": INGREDIENTS
        }
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Add auth header if token provided
    if user_token:
        headers["Authorization"] = f"Bearer {user_token}"
    
    try:
        print(f"   Calling {endpoint}")
        print(f"   Cuisine: {cuisine_id}")
        print(f"   Language: {cuisine_config['language_code']}")
        
        response = requests.post(endpoint, json=payload, headers=headers, timeout=120)
        
        if response.status_code == 200:
            data = response.json()
            # Check if we got actual recipes
            if data.get('status') == 'ok' and data.get('menus'):
                return data
            else:
                print(f"   ⚠️  Status: {data.get('status')}, Message: {data.get('error_message', 'No recipes')}")
                return data
        else:
            print(f"   ⚠️  HTTP {response.status_code}: {response.text[:300]}")
            return None
            
    except Exception as e:
        print(f"   ❌ Error: {str(e)}")
        return None


def main():
    print("="*80)
    print("SAVO Recipe Generator (Authenticated User)")
    print("="*80)
    print(f"User: {TEST_USER_EMAIL}")
    print(f"API: {API_BASE_URL}")
    print(f"Ingredients: {', '.join(INGREDIENTS)}")
    print("="*80)
    
    # Test health
    try:
        health = requests.get(f"{API_BASE_URL}/health", timeout=10)
        if health.status_code == 200:
            print("✅ API is healthy")
        else:
            print(f"⚠️  API returned {health.status_code}")
    except:
        print("❌ Cannot reach API")
        return
    
    print("\n" + "="*80)
    print("AUTHENTICATION REQUIRED")
    print("="*80)
    print("\nTo get full recipes with cooking steps, you need to:")
    print("1. Log in to SAVO app with: sureshvidh@gmail.com")
    print("2. Get the JWT token from the app")
    print("3. Or provide the Supabase service role key")
    print("\nWithout authentication, SAVO blocks recipe generation for safety.")
    print("\n" + "="*80)
    
    # Ask for token
    print("\nOptions:")
    print("1. Enter JWT token (from logged-in Flutter app)")
    print("2. Skip and show what data is available")
    
    choice = input("\nEnter choice (1 or 2): ").strip()
    
    user_token = None
    if choice == "1":
        user_token = input("Paste JWT token: ").strip()
        if not user_token:
            print("❌ No token provided")
            return
    
    # Generate one sample recipe
    print("\n🚀 Generating sample Indian recipe...")
    
    recipe_config = {
        "cuisine": "Indian",
        "dish_type": "Main Course",
        "language": "Hindi",
        "language_code": "hi-IN",
        "recipe_name": "Paneer Biryani",
        "religious": ["Vegetarian"]
    }
    
    result = generate_recipe_with_auth(recipe_config, user_token)
    
    if result and result.get('menus'):
        print("\n✅ SUCCESS! Got recipe with steps!")
        
        # Save to file
        output_file = "SAVO_AUTHENTICATED_RECIPE.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        print(f"📄 Saved to: {output_file}")
        
        # Show summary
        menu = result['menus'][0]
        if 'recipes' in menu:
            recipe = menu['recipes'][0]
            print(f"\n📖 Recipe: {recipe.get('recipe_name', 'Unknown')}")
            
            if 'instructions' in recipe:
                instructions = recipe['instructions']
                if isinstance(instructions, dict):
                    print(f"\n📝 Instructions available in languages: {list(instructions.keys())}")
                elif isinstance(instructions, list):
                    print(f"\n📝 {len(instructions)} cooking steps")
    else:
        print("\n⚠️  Could not generate full recipe")
        print("\nThis is expected without authentication.")
        print("SAVO requires knowing family members and allergens for safety.")


if __name__ == "__main__":
    main()
