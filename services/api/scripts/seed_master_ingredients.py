"""
Seed Master Ingredients Database
Populates master_ingredients with common Indian, Western, and Asian ingredients
"""
import asyncio
import asyncpg
from decimal import Decimal
import json
import os

# Common ingredients with multi-language names and properties
MASTER_INGREDIENTS = [
    # GRAINS & RICE
    {
        "canonical_name": "rice",
        "names": {"en": "Rice", "hi": "चावल", "ta": "அரிசி", "es": "Arroz", "zh": "米饭", "ar": "أرز"},
        "category": "grains",
        "subcategory": "rice",
        "typical_containers": ["bag", "jar", "package"],
        "color_hints": ["white", "brown"],
        "texture_hints": ["grainy", "small_grains"],
        "density_g_per_ml": 0.75,
        "typical_package_sizes": [500, 1000, 2000, 5000],
        "nutrition_per_100g": {"energy_kcal": 365, "protein_g": 7.1, "carbs_g": 79.0, "fat_g": 0.9},
    },
    {
        "canonical_name": "basmati_rice",
        "names": {"en": "Basmati Rice", "hi": "बासमती चावल", "ta": "பாஸ்மதி அரிசி", "es": "Arroz Basmati"},
        "category": "grains",
        "subcategory": "rice",
        "typical_containers": ["bag", "package"],
        "color_hints": ["white", "cream"],
        "texture_hints": ["long_grains"],
        "density_g_per_ml": 0.72,
        "typical_package_sizes": [1000, 5000],
        "nutrition_per_100g": {"energy_kcal": 350, "protein_g": 7.0, "carbs_g": 78.0, "fat_g": 0.5},
    },
    {
        "canonical_name": "wheat_flour",
        "names": {"en": "Wheat Flour", "hi": "गेहूं का आटा", "ta": "கோதுமை மாவு", "es": "Harina de Trigo", "zh": "小麦粉"},
        "category": "grains",
        "subcategory": "flour",
        "typical_containers": ["bag", "package", "jar"],
        "color_hints": ["white", "off_white"],
        "texture_hints": ["powdery", "fine"],
        "density_g_per_ml": 0.6,
        "typical_package_sizes": [500, 1000, 2000],
        "nutrition_per_100g": {"energy_kcal": 364, "protein_g": 10.0, "carbs_g": 76.0, "fat_g": 1.0},
    },
    
    # LENTILS & PULSES
    {
        "canonical_name": "lentils_red",
        "names": {"en": "Red Lentils", "hi": "मसूर दाल", "ta": "சிவப்பு பருப்பு", "es": "Lentejas Rojas"},
        "category": "pulses",
        "subcategory": "lentils",
        "typical_containers": ["bag", "jar", "package"],
        "color_hints": ["red", "orange"],
        "texture_hints": ["small_round", "grainy"],
        "density_g_per_ml": 0.8,
        "typical_package_sizes": [500, 1000],
        "nutrition_per_100g": {"energy_kcal": 352, "protein_g": 25.8, "carbs_g": 63.0, "fat_g": 1.1},
    },
    {
        "canonical_name": "chickpeas",
        "names": {"en": "Chickpeas", "hi": "चना", "ta": "கொண்டைக்கடலை", "es": "Garbanzos", "zh": "鹰嘴豆"},
        "category": "pulses",
        "subcategory": "beans",
        "typical_containers": ["bag", "jar", "can"],
        "color_hints": ["beige", "tan"],
        "texture_hints": ["round", "medium_size"],
        "density_g_per_ml": 0.75,
        "typical_package_sizes": [500, 1000],
        "nutrition_per_100g": {"energy_kcal": 364, "protein_g": 19.0, "carbs_g": 61.0, "fat_g": 6.0},
    },
    {
        "canonical_name": "black_lentils",
        "names": {"en": "Black Lentils", "hi": "उड़द दाल", "ta": "உளுத்தம் பருப்பு", "es": "Lentejas Negras"},
        "category": "pulses",
        "subcategory": "lentils",
        "typical_containers": ["bag", "jar"],
        "color_hints": ["black", "dark_brown"],
        "texture_hints": ["small_round"],
        "density_g_per_ml": 0.82,
        "typical_package_sizes": [500, 1000],
    },
    
    # DAIRY
    {
        "canonical_name": "milk",
        "names": {"en": "Milk", "hi": "दूध", "ta": "பால்", "es": "Leche", "zh": "牛奶", "ar": "حليب"},
        "category": "dairy",
        "subcategory": "milk",
        "typical_containers": ["bottle", "carton", "bag"],
        "color_hints": ["white"],
        "texture_hints": ["liquid"],
        "density_g_per_ml": 1.03,
        "typical_package_sizes": [500, 1000],
        "nutrition_per_100g": {"energy_kcal": 61, "protein_g": 3.2, "carbs_g": 4.8, "fat_g": 3.3},
    },
    {
        "canonical_name": "paneer",
        "names": {"en": "Paneer", "hi": "पनीर", "ta": "பன்னீர்", "es": "Queso Paneer"},
        "category": "dairy",
        "subcategory": "cheese",
        "typical_containers": ["package", "container"],
        "color_hints": ["white", "cream"],
        "texture_hints": ["solid", "block"],
        "density_g_per_ml": 1.05,
        "typical_package_sizes": [200, 500],
        "nutrition_per_100g": {"energy_kcal": 265, "protein_g": 18.3, "carbs_g": 1.2, "fat_g": 20.8},
    },
    {
        "canonical_name": "yogurt",
        "names": {"en": "Yogurt", "hi": "दही", "ta": "தயிர்", "es": "Yogur", "zh": "酸奶", "ar": "زبادي"},
        "category": "dairy",
        "subcategory": "yogurt",
        "typical_containers": ["container", "cup", "bottle"],
        "color_hints": ["white", "cream"],
        "texture_hints": ["creamy", "liquid"],
        "density_g_per_ml": 1.05,
        "typical_package_sizes": [200, 500, 1000],
    },
    
    # VEGETABLES
    {
        "canonical_name": "tomato",
        "names": {"en": "Tomato", "hi": "टमाटर", "ta": "தக்காளி", "es": "Tomate", "zh": "番茄", "ar": "طماطم"},
        "category": "vegetables",
        "subcategory": "fruit_vegetables",
        "typical_containers": ["loose", "bag"],
        "color_hints": ["red", "green"],
        "texture_hints": ["round", "smooth"],
        "density_g_per_ml": 0.95,
        "typical_package_sizes": [250, 500, 1000],
        "nutrition_per_100g": {"energy_kcal": 18, "protein_g": 0.9, "carbs_g": 3.9, "fat_g": 0.2},
    },
    {
        "canonical_name": "onion",
        "names": {"en": "Onion", "hi": "प्याज", "ta": "வெங்காயம்", "es": "Cebolla", "zh": "洋葱", "ar": "بصل"},
        "category": "vegetables",
        "subcategory": "root_vegetables",
        "typical_containers": ["loose", "bag", "net"],
        "color_hints": ["brown", "red", "white"],
        "texture_hints": ["round", "layered"],
        "density_g_per_ml": 0.55,
        "typical_package_sizes": [500, 1000],
        "nutrition_per_100g": {"energy_kcal": 40, "protein_g": 1.1, "carbs_g": 9.3, "fat_g": 0.1},
    },
    {
        "canonical_name": "potato",
        "names": {"en": "Potato", "hi": "आलू", "ta": "உருளைக்கிழங்கு", "es": "Patata", "zh": "土豆", "ar": "بطاطس"},
        "category": "vegetables",
        "subcategory": "root_vegetables",
        "typical_containers": ["loose", "bag"],
        "color_hints": ["brown", "yellow"],
        "texture_hints": ["oval", "solid"],
        "density_g_per_ml": 0.7,
        "typical_package_sizes": [500, 1000, 2000],
        "nutrition_per_100g": {"energy_kcal": 77, "protein_g": 2.0, "carbs_g": 17.0, "fat_g": 0.1},
    },
    {
        "canonical_name": "spinach",
        "names": {"en": "Spinach", "hi": "पालक", "ta": "கீரை", "es": "Espinaca", "zh": "菠菜", "ar": "سبانخ"},
        "category": "vegetables",
        "subcategory": "leafy_greens",
        "typical_containers": ["loose", "bag", "bunch"],
        "color_hints": ["green", "dark_green"],
        "texture_hints": ["leafy", "soft"],
        "density_g_per_ml": 0.25,
        "typical_package_sizes": [250, 500],
    },
    
    # SPICES
    {
        "canonical_name": "turmeric",
        "names": {"en": "Turmeric", "hi": "हल्दी", "ta": "மஞ்சள்", "es": "Cúrcuma", "zh": "姜黄"},
        "category": "spices",
        "subcategory": "ground_spices",
        "typical_containers": ["jar", "bottle", "package"],
        "color_hints": ["yellow", "orange"],
        "texture_hints": ["powdery", "fine"],
        "density_g_per_ml": 0.55,
        "typical_package_sizes": [50, 100, 200],
    },
    {
        "canonical_name": "cumin",
        "names": {"en": "Cumin", "hi": "जीरा", "ta": "சீரகம்", "es": "Comino", "zh": "孜然"},
        "category": "spices",
        "subcategory": "seeds",
        "typical_containers": ["jar", "bottle", "package"],
        "color_hints": ["brown", "dark_brown"],
        "texture_hints": ["small_seeds"],
        "density_g_per_ml": 0.45,
        "typical_package_sizes": [50, 100],
    },
    {
        "canonical_name": "coriander_powder",
        "names": {"en": "Coriander Powder", "hi": "धनिया पाउडर", "ta": "கொத்தமல்லி தூள்", "es": "Cilantro en Polvo"},
        "category": "spices",
        "subcategory": "ground_spices",
        "typical_containers": ["jar", "bottle"],
        "color_hints": ["brown", "light_brown"],
        "texture_hints": ["powdery"],
        "density_g_per_ml": 0.5,
        "typical_package_sizes": [50, 100, 200],
    },
    {
        "canonical_name": "chili_powder",
        "names": {"en": "Chili Powder", "hi": "लाल मिर्च पाउडर", "ta": "மிளகாய் தூள்", "es": "Chile en Polvo", "zh": "辣椒粉"},
        "category": "spices",
        "subcategory": "ground_spices",
        "typical_containers": ["jar", "bottle", "package"],
        "color_hints": ["red", "dark_red"],
        "texture_hints": ["powdery", "fine"],
        "density_g_per_ml": 0.48,
        "typical_package_sizes": [50, 100, 200],
    },
    
    # OILS & CONDIMENTS
    {
        "canonical_name": "vegetable_oil",
        "names": {"en": "Vegetable Oil", "hi": "तेल", "ta": "எண்ணெய்", "es": "Aceite Vegetal", "zh": "植物油"},
        "category": "oils",
        "subcategory": "cooking_oil",
        "typical_containers": ["bottle", "can"],
        "color_hints": ["yellow", "clear"],
        "texture_hints": ["liquid"],
        "density_g_per_ml": 0.92,
        "typical_package_sizes": [500, 1000, 5000],
    },
    {
        "canonical_name": "ghee",
        "names": {"en": "Ghee", "hi": "घी", "ta": "நெய்", "es": "Ghee"},
        "category": "oils",
        "subcategory": "clarified_butter",
        "typical_containers": ["jar", "can", "bottle"],
        "color_hints": ["yellow", "golden"],
        "texture_hints": ["liquid", "semi_solid"],
        "density_g_per_ml": 0.91,
        "typical_package_sizes": [200, 500, 1000],
    },
    {
        "canonical_name": "salt",
        "names": {"en": "Salt", "hi": "नमक", "ta": "உப்பு", "es": "Sal", "zh": "盐", "ar": "ملح"},
        "category": "condiments",
        "subcategory": "salt",
        "typical_containers": ["jar", "package", "box"],
        "color_hints": ["white"],
        "texture_hints": ["crystalline", "fine"],
        "density_g_per_ml": 1.2,
        "typical_package_sizes": [500, 1000],
    },
    {
        "canonical_name": "sugar",
        "names": {"en": "Sugar", "hi": "चीनी", "ta": "சர்க்கரை", "es": "Azúcar", "zh": "糖", "ar": "سكر"},
        "category": "sweeteners",
        "subcategory": "sugar",
        "typical_containers": ["bag", "jar", "package"],
        "color_hints": ["white"],
        "texture_hints": ["crystalline", "granular"],
        "density_g_per_ml": 0.85,
        "typical_package_sizes": [500, 1000, 5000],
    },
    
    # PROTEINS
    {
        "canonical_name": "chicken",
        "names": {"en": "Chicken", "hi": "चिकन", "ta": "கோழி", "es": "Pollo", "zh": "鸡肉", "ar": "دجاج"},
        "category": "meat",
        "subcategory": "poultry",
        "typical_containers": ["package", "tray"],
        "color_hints": ["pink", "white"],
        "texture_hints": ["solid", "meat"],
        "density_g_per_ml": 1.05,
        "typical_package_sizes": [500, 1000],
    },
    {
        "canonical_name": "eggs",
        "names": {"en": "Eggs", "hi": "अंडे", "ta": "முட்டை", "es": "Huevos", "zh": "鸡蛋", "ar": "بيض"},
        "category": "proteins",
        "subcategory": "eggs",
        "typical_containers": ["carton", "tray"],
        "color_hints": ["white", "brown"],
        "texture_hints": ["oval", "smooth"],
        "density_g_per_ml": 1.03,
        "typical_package_sizes": [6, 12, 30],  # pieces
    },
]


async def seed_master_ingredients():
    """Seed the master_ingredients table"""
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("Error: DATABASE_URL environment variable not set")
        return
    
    conn = await asyncpg.connect(database_url)
    
    try:
        inserted = 0
        skipped = 0
        
        for ingredient in MASTER_INGREDIENTS:
            try:
                # Check if already exists
                existing = await conn.fetchrow(
                    "SELECT id FROM master_ingredients WHERE canonical_name = $1",
                    ingredient["canonical_name"]
                )
                
                if existing:
                    print(f"Skipping {ingredient['canonical_name']} - already exists")
                    skipped += 1
                    continue
                
                # Insert new ingredient
                await conn.execute(
                    """
                    INSERT INTO master_ingredients
                    (canonical_name, names, category, subcategory, typical_containers,
                     color_hints, texture_hints, density_g_per_ml, typical_package_sizes,
                     nutrition_per_100g, is_verified)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, true)
                    """,
                    ingredient["canonical_name"],
                    json.dumps(ingredient["names"]),
                    ingredient["category"],
                    ingredient.get("subcategory"),
                    ingredient["typical_containers"],
                    ingredient.get("color_hints", []),
                    ingredient.get("texture_hints", []),
                    Decimal(str(ingredient.get("density_g_per_ml", 0.8))),
                    ingredient.get("typical_package_sizes", []),
                    json.dumps(ingredient.get("nutrition_per_100g")) if ingredient.get("nutrition_per_100g") else None,
                )
                
                print(f"✓ Inserted {ingredient['canonical_name']}")
                inserted += 1
                
            except Exception as e:
                print(f"✗ Error inserting {ingredient['canonical_name']}: {e}")
        
        print(f"\n=== Seed Complete ===")
        print(f"Inserted: {inserted}")
        print(f"Skipped: {skipped}")
        print(f"Total: {len(MASTER_INGREDIENTS)}")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed_master_ingredients())
