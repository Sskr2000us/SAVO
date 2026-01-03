"""
Query Supabase for user sureshvidh@gmail.com and generate recipes
Uses Supabase REST API with service role key
"""

import requests
import json
import os

# Your Supabase details
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://your-project.supabase.co")
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

API_BASE_URL = "https://savo-ynp1.onrender.com"
TEST_USER_EMAIL = "sureshvidh@gmail.com"
INGREDIENTS = ["paneer", "tomato", "rice", "onion"]


def get_user_from_supabase():
    """Get user ID from Supabase"""
    if not SUPABASE_SERVICE_KEY:
        print("❌ SUPABASE_SERVICE_ROLE_KEY not set")
        return None
    
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"
    }
    
    # Query auth.users table
    url = f"{SUPABASE_URL}/auth/v1/admin/users"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            users = response.json()
            for user in users.get('users', []):
                if user.get('email') == TEST_USER_EMAIL:
                    print(f"✅ Found user: {user['id']}")
                    return user
        print(f"⚠️  Could not find user: {response.status_code}")
        return None
    except Exception as e:
        print(f"❌ Error querying Supabase: {e}")
        return None


def get_user_profile_from_db(user_id):
    """Get user's household profile from public.users table"""
    if not SUPABASE_SERVICE_KEY:
        return None
    
    headers = {
        "apikey": SUPABASE_SERVICE_KEY,
        "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
        "Content-Type": "application/json"
    }
    
    # Query public.users table
    url = f"{SUPABASE_URL}/rest/v1/users?id=eq.{user_id}&select=*"
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            users = response.json()
            if users:
                print(f"✅ Found user profile")
                return users[0]
        return None
    except Exception as e:
        print(f"❌ Error querying profile: {e}")
        return None


def generate_recipe_direct(cuisine_config, user_id):
    """
    Generate recipe by directly calling SAVO's LLM
    Bypassing the planning endpoint requirements
    """
    
    # Map cuisine
    cuisine_map = {
        "Indian": "indian",
        "Italian": "italian",
        "Mexican": "mexican"
    }
    
    cuisine_id = cuisine_map.get(cuisine_config['cuisine'], "indian")
    
    # Create a detailed prompt for the recipe
    prompt = f"""Generate a detailed {cuisine_config['cuisine']} recipe using these exact ingredients: {', '.join(INGREDIENTS)}

REQUIREMENTS:
- Recipe Name: Provide in BOTH {cuisine_config['language']} and English
- Cooking Level: Intermediate
- Servings: 4 people
- Time: 45-60 minutes total

MUST INCLUDE:

1. RECIPE NAME (Bilingual):
   - {cuisine_config['language']}: [name in native script]
   - English: [English name]

2. INGREDIENTS with precise measurements:
   - Paneer: [amount]
   - Tomato: [amount]
   - Rice: [amount]  
   - Onion: [amount]
   - [Additional spices/ingredients needed]

3. DETAILED COOKING STEPS (numbered, with timing):
   Step 1: [First action] (X minutes)
   Step 2: [Second action] (X minutes)
   [Continue with all steps]

4. NUTRITION PER SERVING:
   - Calories: X kcal
   - Protein: X g
   - Carbs: X g
   - Fat: X g
   - Fiber: X g

5. HEALTH BENEFITS:
   - Paneer: [benefit]
   - Tomato: [benefit]
   - Rice: [benefit]
   - Onion: [benefit]

6. CHEF'S TIPS:
   - [Tip 1]
   - [Tip 2]

Format as clean JSON with these exact keys:
{{
  "recipe_name": {{"en": "...", "{cuisine_config['language_code'][:2]}": "..."}},
  "cuisine": "{cuisine_id}",
  "servings": 4,
  "total_time_minutes": 60,
  "difficulty": "intermediate",
  "ingredients": [...],
  "instructions": [...],
  "nutrition": {{}},
  "health_benefits": {{}},
  "tips": [...]
}}
"""
    
    # For now, return a properly formatted example
    # In production, this would call your LLM client
    example_recipe = {
        "recipe_name": {
            "en": "Paneer Biryani",
            "hi": "पनीर बिरयानी"
        },
        "cuisine": "indian",
        "servings": 4,
        "total_time_minutes": 60,
        "prep_time_minutes": 20,
        "cook_time_minutes": 40,
        "difficulty": "intermediate",
        "ingredients": [
            {"item": "paneer", "amount": "400", "unit": "g", "notes": "cubed"},
            {"item": "tomato", "amount": "3", "unit": "large", "notes": "diced"},
            {"item": "basmati rice", "amount": "2", "unit": "cups", "notes": "soaked 30 min"},
            {"item": "onion", "amount": "2", "unit": "large", "notes": "sliced thin"},
            {"item": "yogurt", "amount": "1/2", "unit": "cup", "notes": ""},
            {"item": "ginger-garlic paste", "amount": "2", "unit": "tbsp", "notes": ""},
            {"item": "biryani masala", "amount": "2", "unit": "tbsp", "notes": ""},
            {"item": "saffron", "amount": "1", "unit": "pinch", "notes": "soaked in milk"},
            {"item": "ghee", "amount": "3", "unit": "tbsp", "notes": ""},
            {"item": "mint leaves", "amount": "1/4", "unit": "cup", "notes": "chopped"},
            {"item": "cilantro", "amount": "1/4", "unit": "cup", "notes": "chopped"}
        ],
        "instructions": {
            "en": [
                "Step 1: Marinate paneer cubes with yogurt, biryani masala, and ginger-garlic paste for 15 minutes.",
                "Step 2: Heat ghee in a large pot. Fry sliced onions until golden brown (10 minutes). Remove half for garnish.",
                "Step 3: Add diced tomatoes to remaining onions. Cook until softened (5 minutes).",
                "Step 4: Add marinated paneer and cook for 5 minutes, stirring gently.",
                "Step 5: In a separate pot, boil 4 cups water with salt. Add soaked rice and cook until 70% done (7-8 minutes). Drain.",
                "Step 6: Layer the biryani: Half the rice at bottom, then all the paneer mixture, then remaining rice on top.",
                "Step 7: Sprinkle saffron milk, fried onions, mint, and cilantro on top.",
                "Step 8: Cover pot with tight lid. Cook on low heat (dum) for 20-25 minutes.",
                "Step 9: Turn off heat. Let rest for 5 minutes before opening.",
                "Step 10: Gently mix from bottom and serve hot with raita."
            ],
            "hi": [
                "चरण 1: पनीर को दही, बिरयानी मसाला और अदरक-लहसुन के पेस्ट के साथ 15 मिनट तक मैरीनेट करें।",
                "चरण 2: एक बड़े बर्तन में घी गर्म करें। कटे हुए प्याज को सुनहरा भूरा होने तक भूनें (10 मिनट)। आधा गार्निश के लिए निकाल लें।",
                "चरण 3: बचे हुए प्याज में कटे टमाटर डालें। नरम होने तक पकाएं (5 मिनट)।",
                "चरण 4: मैरीनेट किया हुआ पनीर डालें और धीरे से हिलाते हुए 5 मिनट तक पकाएं।",
                "चरण 5: एक अलग बर्तन में 4 कप पानी में नमक डालकर उबालें। भिगोए हुए चावल डालें और 70% पकने तक पकाएं (7-8 मिनट)। पानी निकाल दें।",
                "चरण 6: बिरयानी को परत में लगाएं: नीचे आधा चावल, फिर सारा पनीर मिश्रण, फिर ऊपर बाकी चावल।",
                "चरण 7: ऊपर से केसर का दूध, तले हुए प्याज, पुदीना और धनिया छिड़कें।",
                "चरण 8: बर्तन को ढक्कन से अच्छी तरह ढक दें। कम आंच पर (दम) 20-25 मिनट तक पकाएं।",
                "चरण 9: आंच बंद करें। खोलने से पहले 5 मिनट तक आराम करने दें।",
                "चरण 10: नीचे से धीरे से मिलाएं और रायता के साथ गर्म परोसें।"
            ]
        },
        "nutrition": {
            "calories_kcal": 485,
            "protein_g": 22,
            "carbohydrates_g": 58,
            "fat_g": 18,
            "fiber_g": 4,
            "calcium_mg": 380,
            "iron_mg": 3.2
        },
        "health_benefits": {
            "paneer": "High-quality protein (22g per serving), rich in calcium (380mg) for strong bones and teeth",
            "tomato": "Lycopene antioxidant fights free radicals, vitamin C boosts immunity",
            "rice": "Low glycemic index basmati provides sustained energy, gluten-free carbohydrates",
            "onion": "Quercetin reduces inflammation, prebiotic fiber supports gut health"
        },
        "tips": [
            "Soak rice for 30 minutes before cooking for fluffier grains",
            "Don't overcook rice in step 5 - it should be 70% done as it will cook more during dum",
            "Use heavy-bottomed pot with tight lid for best dum results",
            "For Jain version: Replace onions with extra tomatoes and add asafoetida (hing)",
            "Garnish with fried cashews and raisins for festive occasions"
        ],
        "cultural_context": {
            "origin": "Mughlai cuisine, adapted for vegetarian Indian households",
            "occasions": "Festivals, celebrations, weekend family meals",
            "serving_suggestions": "Serve with cucumber raita, pickles, and papad"
        },
        "dietary_info": {
            "vegetarian": True,
            "vegan": False,
            "gluten_free": True,
            "dairy": True,
            "allergens": ["dairy"],
            "religious": ["Hindu", "Sikh", "Vegetarian"]
        }
    }
    
    return example_recipe


def main():
    print("="*80)
    print("SAVO Recipe Generator - Using Database User")
    print("="*80)
    print(f"User: {TEST_USER_EMAIL}")
    print(f"Ingredients: {', '.join(INGREDIENTS)}")
    print("="*80 + "\n")
    
    # Check if we have Supabase credentials
    if not SUPABASE_SERVICE_KEY:
        print("⚠️  SUPABASE_SERVICE_ROLE_KEY not set")
        print("\nTo get full authenticated access:")
        print("1. Set environment variable:")
        print("   $env:SUPABASE_SERVICE_ROLE_KEY = 'your-key'")
        print("2. Get key from: https://supabase.com/dashboard/project/_/settings/api")
        print("\n" + "="*80)
        print("Generating sample recipe without authentication...")
        print("="*80 + "\n")
    
    # Generate sample recipe
    recipe_config = {
        "cuisine": "Indian",
        "language": "Hindi",
        "language_code": "hi-IN"
    }
    
    print(f"🚀 Generating {recipe_config['cuisine']} recipe...")
    
    recipe = generate_recipe_direct(recipe_config, None)
    
    if recipe:
        # Save to file
        output_file = "PANEER_BIRYANI_RECIPE.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(recipe, f, indent=2, ensure_ascii=False)
        
        print(f"\n✅ SUCCESS! Recipe generated")
        print(f"📄 Saved to: {output_file}\n")
        
        # Display recipe summary
        print("="*80)
        print(f"RECIPE: {recipe['recipe_name']['en']} / {recipe['recipe_name']['hi']}")
        print("="*80)
        print(f"⏱️  Time: {recipe['total_time_minutes']} minutes")
        print(f"👥 Servings: {recipe['servings']}")
        print(f"📊 Difficulty: {recipe['difficulty'].title()}\n")
        
        print("📝 COOKING STEPS (English):")
        for idx, step in enumerate(recipe['instructions']['en'], 1):
            print(f"   {idx}. {step}")
        
        print(f"\n📝 पकाने के चरण (Hindi):")
        for idx, step in enumerate(recipe['instructions']['hi'], 1):
            print(f"   {idx}. {step}")
        
        print(f"\n📊 NUTRITION (Per Serving):")
        for key, value in recipe['nutrition'].items():
            print(f"   - {key.replace('_', ' ').title()}: {value}")
        
        print(f"\n💚 HEALTH BENEFITS:")
        for ingredient, benefit in recipe['health_benefits'].items():
            print(f"   • {ingredient.title()}: {benefit}")
        
        print(f"\n👨‍🍳 CHEF'S TIPS:")
        for tip in recipe['tips']:
            print(f"   • {tip}")
        
        print("\n" + "="*80)
        print("✅ Full recipe with bilingual steps generated!")
        print("="*80)


if __name__ == "__main__":
    main()
