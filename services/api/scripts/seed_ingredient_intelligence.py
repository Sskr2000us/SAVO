"""
Seed Ingredient Intelligence Database
Seeds 100+ ingredients with full intelligence data:
- Multi-language names (English, Hindi, Tamil, Spanish, Chinese, Arabic)
- Visual intelligence (colors, textures, states)
- Sensory profiles (taste, aroma, mouthfeel)
- Culinary intelligence (uses, cooking methods)
- Storage and waste prevention data
- AI training metadata
"""

import os
import sys
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Any
import asyncpg

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASE_URL = os.getenv("DATABASE_URL")

# ============================================================================
# INGREDIENT DATA DEFINITIONS
# ============================================================================

INGREDIENTS = [
    # ==================== SPICES ====================
    {
        "canonical_name": "Turmeric",
        "scientific_name": "Curcuma longa",
        "category": "Spice",
        "subcategory": "Root",
        "ingredient_type": "single_ingredient",
        "status": "active",
        
        # Multi-language names
        "names": {
            "en": "Turmeric",
            "hi": "हल्दी",
            "ta": "மஞ்சள்",
            "es": "Cúrcuma",
            "zh": "姜黄",
            "ar": "كركم"
        },
        
        # Visual intelligence
        "visual_states": ["raw_whole", "raw_cut", "powdered", "paste"],
        "dominant_colors": ["yellow", "orange", "golden"],
        "shape_features": ["elongated_root", "knobby", "finger-like"],
        "surface_texture": ["rough", "fibrous", "wrinkled"],
        "color_hints": ["bright_yellow", "orange_yellow"],
        "texture_hints": ["powdery", "grainy", "staining"],
        
        # Sensory profile
        "taste_profile": ["earthy", "slightly_bitter", "warm"],
        "aroma_profile": ["warm", "woody", "peppery"],
        "mouthfeel": ["powdery", "slightly_astringent"],
        "intensity_level": "medium",
        "heat_level": "none",
        
        # Culinary intelligence
        "common_uses": ["curries", "rice_dishes", "marinades", "golden_milk", "pickles"],
        "cooking_methods": ["saute", "boil", "infuse", "blend"],
        "typical_containers": ["jar", "bag", "box"],
        
        # Storage and waste
        "storage_conditions": {"fresh": "cool_dry_place", "powder": "airtight_container"},
        "shelf_life_days": {"fresh": 30, "powder": 365},
        "waste_risk_level": "low",
        "spoilage_signs": ["mold", "musty_smell", "loss_of_color"],
        
        # Physical properties
        "density_g_per_ml": 0.65,
        "typical_package_sizes": [50, 100, 200, 500],
        
        # AI metadata
        "cv_labels": ["spice", "root", "yellow_powder", "turmeric_fingers"],
        "embedding_tags": ["indian_spice", "golden", "anti_inflammatory", "curcumin"],
        "llm_prompt_hints": ["Often confused with ginger", "Bright yellow color is distinctive", "Used early in cooking"],
        "confidence_threshold": 0.85
    },
    
    {
        "canonical_name": "Cumin",
        "scientific_name": "Cuminum cyminum",
        "category": "Spice",
        "subcategory": "Seed",
        "ingredient_type": "single_ingredient",
        "status": "active",
        
        "names": {
            "en": "Cumin",
            "hi": "जीरा",
            "ta": "சீரகம்",
            "es": "Comino",
            "zh": "孜然",
            "ar": "كمون"
        },
        
        "visual_states": ["whole_seeds", "powdered"],
        "dominant_colors": ["brown", "tan", "yellowish_brown"],
        "shape_features": ["elongated_seeds", "ridged", "curved"],
        "surface_texture": ["ribbed", "small_seeds"],
        "color_hints": ["earthy_brown"],
        "texture_hints": ["grainy", "aromatic"],
        
        "taste_profile": ["earthy", "nutty", "warm", "slightly_bitter"],
        "aroma_profile": ["strong", "earthy", "warm"],
        "mouthfeel": ["powdery"],
        "intensity_level": "strong",
        "heat_level": "mild",
        
        "common_uses": ["curries", "rice", "bread", "spice_blends", "roasted"],
        "cooking_methods": ["roast", "saute", "grind", "temper"],
        "typical_containers": ["jar", "bag"],
        
        "storage_conditions": {"seeds": "airtight_container", "powder": "airtight_dark_container"},
        "shelf_life_days": {"seeds": 730, "powder": 180},
        "waste_risk_level": "low",
        "spoilage_signs": ["loss_of_aroma", "rancid_smell"],
        
        "density_g_per_ml": 0.55,
        "typical_package_sizes": [50, 100, 200],
        
        "cv_labels": ["spice", "seeds", "brown_seeds", "elongated"],
        "embedding_tags": ["indian_spice", "middle_eastern", "warm_spice"],
        "llm_prompt_hints": ["Similar to caraway seeds", "Essential in Indian cooking", "Toast before grinding"],
        "confidence_threshold": 0.80
    },
    
    {
        "canonical_name": "Coriander",
        "scientific_name": "Coriandrum sativum",
        "category": "Spice",
        "subcategory": "Seed",
        "ingredient_type": "single_ingredient",
        "status": "active",
        
        "names": {
            "en": "Coriander",
            "hi": "धनिया",
            "ta": "கொத்தமல்லி",
            "es": "Cilantro",
            "zh": "香菜",
            "ar": "كزبرة"
        },
        
        "visual_states": ["whole_seeds", "powdered", "fresh_leaves"],
        "dominant_colors": ["brown", "tan", "beige"],
        "shape_features": ["round_seeds", "ribbed"],
        "surface_texture": ["ridged", "spherical"],
        
        "taste_profile": ["citrusy", "slightly_sweet", "warm"],
        "aroma_profile": ["lemony", "floral", "slightly_sweet"],
        "mouthfeel": ["powdery"],
        "intensity_level": "medium",
        "heat_level": "none",
        
        "common_uses": ["curries", "spice_blends", "pickling", "soups"],
        "cooking_methods": ["roast", "grind", "saute"],
        "typical_containers": ["jar", "bag"],
        
        "storage_conditions": {"seeds": "airtight_container", "powder": "airtight_container"},
        "shelf_life_days": {"seeds": 730, "powder": 180},
        "waste_risk_level": "low",
        
        "density_g_per_ml": 0.50,
        "typical_package_sizes": [50, 100, 200, 500],
        
        "cv_labels": ["spice", "seeds", "round_seeds"],
        "embedding_tags": ["indian_spice", "citrus_flavor"],
        "llm_prompt_hints": ["Pairs well with cumin", "Mild citrus flavor"],
        "confidence_threshold": 0.80
    },
    
    # ==================== VEGETABLES ====================
    {
        "canonical_name": "Tomato",
        "scientific_name": "Solanum lycopersicum",
        "category": "Vegetable",
        "subcategory": "Fruit",
        "ingredient_type": "single_ingredient",
        "status": "active",
        
        "names": {
            "en": "Tomato",
            "hi": "टमाटर",
            "ta": "தக்காளி",
            "es": "Tomate",
            "zh": "番茄",
            "ar": "طماطم"
        },
        
        "visual_states": ["raw_whole", "sliced", "diced", "cooked", "pureed"],
        "dominant_colors": ["red", "green", "yellow", "orange"],
        "shape_features": ["round", "oval", "plum_shaped"],
        "surface_texture": ["smooth", "glossy", "firm"],
        
        "taste_profile": ["sweet", "tangy", "umami", "slightly_acidic"],
        "aroma_profile": ["fresh", "earthy", "green_notes"],
        "mouthfeel": ["juicy", "soft", "acidic"],
        "intensity_level": "medium",
        "heat_level": "none",
        
        "common_uses": ["salads", "sauces", "curries", "soups", "sandwiches"],
        "cooking_methods": ["raw", "saute", "roast", "boil", "grill"],
        "typical_containers": ["loose", "basket", "box"],
        
        "storage_conditions": {"fresh": "room_temperature_until_ripe_then_fridge"},
        "shelf_life_days": {"fresh": 7, "canned": 730},
        "waste_risk_level": "medium",
        "spoilage_signs": ["soft_spots", "mold", "wrinkled_skin", "bad_smell"],
        
        "density_g_per_ml": 0.95,
        "typical_package_sizes": [500, 1000, 2000],
        
        "cv_labels": ["vegetable", "red_fruit", "round", "glossy"],
        "embedding_tags": ["versatile", "fresh_produce", "cooking_base"],
        "llm_prompt_hints": ["Available in many varieties", "Key ingredient in many cuisines"],
        "confidence_threshold": 0.90
    },
    
    {
        "canonical_name": "Onion",
        "scientific_name": "Allium cepa",
        "category": "Vegetable",
        "subcategory": "Bulb",
        "ingredient_type": "single_ingredient",
        "status": "active",
        
        "names": {
            "en": "Onion",
            "hi": "प्याज",
            "ta": "வெங்காயம்",
            "es": "Cebolla",
            "zh": "洋葱",
            "ar": "بصل"
        },
        
        "visual_states": ["raw_whole", "peeled", "sliced", "diced", "caramelized"],
        "dominant_colors": ["yellow", "white", "red", "purple"],
        "shape_features": ["round", "layered", "bulbous"],
        "surface_texture": ["papery_skin", "smooth_interior", "layered"],
        
        "taste_profile": ["pungent", "sweet", "sharp"],
        "aroma_profile": ["strong", "pungent", "sulfurous"],
        "mouthfeel": ["crunchy_raw", "soft_cooked"],
        "intensity_level": "strong",
        "heat_level": "none",
        
        "common_uses": ["base_for_curries", "salads", "soups", "stir_fries"],
        "cooking_methods": ["saute", "roast", "raw", "caramelize", "fry"],
        "typical_containers": ["loose", "net_bag"],
        
        "storage_conditions": {"fresh": "cool_dry_dark_place"},
        "shelf_life_days": {"fresh": 30},
        "waste_risk_level": "low",
        "spoilage_signs": ["sprouting", "soft_spots", "mold"],
        
        "density_g_per_ml": 0.95,
        "typical_package_sizes": [500, 1000, 2000],
        
        "cv_labels": ["vegetable", "bulb", "layered", "onion_skin"],
        "embedding_tags": ["aromatic", "base_ingredient", "staple"],
        "llm_prompt_hints": ["Makes you cry when cutting", "Essential in most cuisines"],
        "confidence_threshold": 0.90
    },
    
    {
        "canonical_name": "Garlic",
        "scientific_name": "Allium sativum",
        "category": "Vegetable",
        "subcategory": "Bulb",
        "ingredient_type": "single_ingredient",
        "status": "active",
        
        "names": {
            "en": "Garlic",
            "hi": "लहसुन",
            "ta": "பூண்டு",
            "es": "Ajo",
            "zh": "大蒜",
            "ar": "ثوم"
        },
        
        "visual_states": ["whole_bulb", "cloves", "minced", "paste"],
        "dominant_colors": ["white", "cream", "purple_tinge"],
        "shape_features": ["bulb_with_cloves", "teardrop_cloves"],
        "surface_texture": ["papery_skin", "smooth_cloves"],
        
        "taste_profile": ["pungent", "sharp", "savory"],
        "aroma_profile": ["strong", "pungent", "sulfurous"],
        "mouthfeel": ["crunchy_raw", "soft_cooked"],
        "intensity_level": "strong",
        "heat_level": "mild",
        
        "common_uses": ["curries", "marinades", "stir_fries", "roasted", "pastes"],
        "cooking_methods": ["saute", "roast", "raw", "mince", "crush"],
        "typical_containers": ["loose", "net_bag", "jar"],
        
        "storage_conditions": {"fresh": "cool_dry_place"},
        "shelf_life_days": {"fresh": 90},
        "waste_risk_level": "low",
        "spoilage_signs": ["sprouting", "soft_cloves", "mold"],
        
        "density_g_per_ml": 1.05,
        "typical_package_sizes": [100, 200, 500],
        
        "cv_labels": ["vegetable", "bulb", "white_cloves"],
        "embedding_tags": ["aromatic", "pungent", "flavor_base"],
        "llm_prompt_hints": ["Often paired with ginger", "Essential flavor base"],
        "confidence_threshold": 0.85
    },
    
    {
        "canonical_name": "Ginger",
        "scientific_name": "Zingiber officinale",
        "category": "Spice",
        "subcategory": "Root",
        "ingredient_type": "single_ingredient",
        "status": "active",
        
        "names": {
            "en": "Ginger",
            "hi": "अदरक",
            "ta": "இஞ்சி",
            "es": "Jengibre",
            "zh": "生姜",
            "ar": "زنجبيل"
        },
        
        "visual_states": ["raw_whole", "sliced", "minced", "paste", "dried"],
        "dominant_colors": ["tan", "beige", "yellow_interior"],
        "shape_features": ["knobby_root", "irregular", "branching"],
        "surface_texture": ["rough_skin", "fibrous", "wrinkled"],
        
        "taste_profile": ["spicy", "warm", "slightly_sweet", "pungent"],
        "aroma_profile": ["sharp", "warm", "citrusy"],
        "mouthfeel": ["fibrous", "juicy"],
        "intensity_level": "strong",
        "heat_level": "medium",
        
        "common_uses": ["curries", "tea", "stir_fries", "marinades", "baking"],
        "cooking_methods": ["saute", "boil", "grate", "juice"],
        "typical_containers": ["loose", "bag"],
        
        "storage_conditions": {"fresh": "fridge_or_cool_dry_place"},
        "shelf_life_days": {"fresh": 21},
        "waste_risk_level": "medium",
        "spoilage_signs": ["mold", "soft_spots", "shriveled"],
        
        "density_g_per_ml": 0.90,
        "typical_package_sizes": [100, 200, 500],
        
        "cv_labels": ["spice", "root", "knobby", "tan_root"],
        "embedding_tags": ["asian_spice", "warming", "medicinal"],
        "llm_prompt_hints": ["Often confused with turmeric root", "Smoother skin than turmeric"],
        "confidence_threshold": 0.85
    },
    
    # ==================== GRAINS & LEGUMES ====================
    {
        "canonical_name": "Basmati Rice",
        "scientific_name": "Oryza sativa",
        "category": "Grain",
        "subcategory": "Rice",
        "ingredient_type": "single_ingredient",
        "status": "active",
        
        "names": {
            "en": "Basmati Rice",
            "hi": "बासमती चावल",
            "ta": "பாசுமதி அரிசி",
            "es": "Arroz Basmati",
            "zh": "印度香米",
            "ar": "أرز بسمتي"
        },
        
        "visual_states": ["raw_grains", "soaked", "cooked"],
        "dominant_colors": ["white", "cream"],
        "shape_features": ["long_grain", "slender"],
        "surface_texture": ["smooth", "dry"],
        
        "taste_profile": ["mild", "nutty", "aromatic"],
        "aroma_profile": ["fragrant", "nutty", "popcorn-like"],
        "mouthfeel": ["fluffy", "separate_grains"],
        "intensity_level": "mild",
        "heat_level": "none",
        
        "common_uses": ["biryani", "pulao", "plain_rice", "fried_rice"],
        "cooking_methods": ["boil", "steam", "pressure_cook"],
        "typical_containers": ["bag", "container"],
        
        "storage_conditions": {"raw": "cool_dry_place_airtight"},
        "shelf_life_days": {"raw": 730, "cooked": 3},
        "waste_risk_level": "low",
        "spoilage_signs": ["insects", "rancid_smell", "mold"],
        
        "density_g_per_ml": 0.75,
        "typical_package_sizes": [1000, 2000, 5000, 10000],
        
        "cv_labels": ["grain", "white_rice", "long_grain"],
        "embedding_tags": ["staple", "indian_rice", "aromatic"],
        "llm_prompt_hints": ["Premium rice variety", "Known for aroma"],
        "confidence_threshold": 0.80
    },
    
    {
        "canonical_name": "Red Lentils",
        "scientific_name": "Lens culinaris",
        "category": "Legume",
        "subcategory": "Lentil",
        "ingredient_type": "single_ingredient",
        "status": "active",
        
        "names": {
            "en": "Red Lentils",
            "hi": "मसूर दाल",
            "ta": "சிவப்பு பருப்பு",
            "es": "Lentejas Rojas",
            "zh": "红扁豆",
            "ar": "عدس أحمر"
        },
        
        "visual_states": ["raw_split", "cooked"],
        "dominant_colors": ["orange", "red", "coral"],
        "shape_features": ["small_discs", "split_lentils"],
        "surface_texture": ["smooth", "flat"],
        
        "taste_profile": ["mild", "earthy", "slightly_sweet"],
        "aroma_profile": ["earthy", "mild"],
        "mouthfeel": ["soft_when_cooked", "creamy"],
        "intensity_level": "mild",
        "heat_level": "none",
        
        "common_uses": ["dal", "soups", "curries", "stews"],
        "cooking_methods": ["boil", "pressure_cook", "simmer"],
        "typical_containers": ["bag", "container"],
        
        "storage_conditions": {"raw": "cool_dry_place_airtight"},
        "shelf_life_days": {"raw": 730, "cooked": 3},
        "waste_risk_level": "low",
        "spoilage_signs": ["insects", "moisture", "mold"],
        
        "density_g_per_ml": 0.80,
        "typical_package_sizes": [500, 1000, 2000],
        
        "cv_labels": ["legume", "orange_lentils", "split_dal"],
        "embedding_tags": ["protein", "indian_dal", "quick_cooking"],
        "llm_prompt_hints": ["Cooks quickly", "Turns yellow when cooked"],
        "confidence_threshold": 0.85
    },
    
    # ==================== MORE SPICES ====================
    {
        "canonical_name": "Black Pepper",
        "scientific_name": "Piper nigrum",
        "category": "Spice",
        "subcategory": "Berry",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Black Pepper", "hi": "काली मिर्च", "ta": "கருப்பு மிளகு", "es": "Pimienta Negra", "zh": "黑胡椒", "ar": "فلفل أسود"},
        "visual_states": ["whole_peppercorns", "cracked", "ground"],
        "dominant_colors": ["black", "dark_brown"],
        "shape_features": ["round_berries", "wrinkled"],
        "surface_texture": ["wrinkled", "hard"],
        "taste_profile": ["spicy", "pungent", "sharp"],
        "aroma_profile": ["woody", "piney", "citrus"],
        "mouthfeel": ["sharp", "biting"],
        "intensity_level": "strong",
        "heat_level": "medium",
        "common_uses": ["seasoning", "marinades", "curries", "soups"],
        "cooking_methods": ["grind_fresh", "whole_in_cooking", "temper"],
        "typical_containers": ["jar", "grinder"],
        "storage_conditions": {"whole": "cool_dry_place", "ground": "airtight_container"},
        "shelf_life_days": {"whole": 1095, "ground": 180},
        "waste_risk_level": "low",
        "spoilage_signs": ["loss_of_aroma", "flat_taste"],
        "density_g_per_ml": 0.60,
        "typical_package_sizes": [50, 100, 200],
        "cv_labels": ["spice", "black_peppercorns", "round"],
        "embedding_tags": ["universal_spice", "sharp", "pungent"],
        "llm_prompt_hints": ["Most common spice", "Essential for seasoning"],
        "confidence_threshold": 0.85
    },
    
    {
        "canonical_name": "Cardamom",
        "scientific_name": "Elettaria cardamomum",
        "category": "Spice",
        "subcategory": "Pod",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Cardamom", "hi": "इलायची", "ta": "ஏலக்காய்", "es": "Cardamomo", "zh": "小豆蔻", "ar": "هيل"},
        "visual_states": ["whole_pods", "seeds", "ground"],
        "dominant_colors": ["green", "white", "black"],
        "shape_features": ["oval_pods", "small_seeds"],
        "surface_texture": ["papery_pod", "hard_seeds"],
        "taste_profile": ["sweet", "floral", "slightly_spicy"],
        "aroma_profile": ["intense", "sweet", "eucalyptus"],
        "mouthfeel": ["aromatic", "cooling"],
        "intensity_level": "strong",
        "heat_level": "mild",
        "common_uses": ["chai", "desserts", "biryan", "curries"],
        "cooking_methods": ["whole", "crushed", "ground"],
        "typical_containers": ["jar", "small_box"],
        "storage_conditions": {"pods": "airtight_container", "ground": "airtight_dark"},
        "shelf_life_days": {"pods": 365, "ground": 90},
        "waste_risk_level": "low",
        "density_g_per_ml": 0.40,
        "typical_package_sizes": [25, 50, 100],
        "cv_labels": ["spice", "green_pods", "oval"],
        "embedding_tags": ["aromatic", "sweet_spice", "indian"],
        "llm_prompt_hints": ["Very aromatic", "Used in chai"],
        "confidence_threshold": 0.80
    },
    
    {
        "canonical_name": "Cinnamon",
        "scientific_name": "Cinnamomum verum",
        "category": "Spice",
        "subcategory": "Bark",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Cinnamon", "hi": "दालचीनी", "ta": "பட்டை", "es": "Canela", "zh": "肉桂", "ar": "قرفة"},
        "visual_states": ["sticks", "quills", "ground"],
        "dominant_colors": ["brown", "reddish_brown", "tan"],
        "shape_features": ["curled_bark", "tubular"],
        "surface_texture": ["layered", "rough_outer", "smooth_inner"],
        "taste_profile": ["sweet", "warm", "woody"],
        "aroma_profile": ["sweet", "warm", "spicy"],
        "mouthfeel": ["warming", "slightly_astringent"],
        "intensity_level": "medium",
        "heat_level": "mild",
        "common_uses": ["baking", "chai", "curries", "desserts"],
        "cooking_methods": ["whole", "ground", "infuse"],
        "typical_containers": ["jar", "bag"],
        "storage_conditions": {"sticks": "cool_dry_place", "ground": "airtight"},
        "shelf_life_days": {"sticks": 730, "ground": 180},
        "waste_risk_level": "low",
        "density_g_per_ml": 0.55,
        "typical_package_sizes": [50, 100, 200],
        "cv_labels": ["spice", "brown_sticks", "curled"],
        "embedding_tags": ["sweet_spice", "warming", "baking"],
        "llm_prompt_hints": ["Sweet warm spice", "Common in baking"],
        "confidence_threshold": 0.85
    },
    
    {
        "canonical_name": "Cloves",
        "scientific_name": "Syzygium aromaticum",
        "category": "Spice",
        "subcategory": "Flower_Bud",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Cloves", "hi": "लौंग", "ta": "கிராம்பு", "es": "Clavo de Olor", "zh": "丁香", "ar": "قرنفل"},
        "visual_states": ["whole_buds", "ground"],
        "dominant_colors": ["dark_brown", "reddish_brown"],
        "shape_features": ["nail_shaped", "bulbous_top"],
        "surface_texture": ["hard", "woody"],
        "taste_profile": ["strong", "sweet", "bitter"],
        "aroma_profile": ["intense", "sweet", "medicinal"],
        "mouthfeel": ["numbing", "astringent"],
        "intensity_level": "very_strong",
        "heat_level": "mild",
        "common_uses": ["biryani", "chai", "pickling", "desserts"],
        "cooking_methods": ["whole", "ground", "infuse"],
        "typical_containers": ["jar", "small_bottle"],
        "storage_conditions": {"whole": "airtight_cool", "ground": "airtight_dark"},
        "shelf_life_days": {"whole": 730, "ground": 180},
        "waste_risk_level": "low",
        "density_g_per_ml": 0.45,
        "typical_package_sizes": [25, 50, 100],
        "cv_labels": ["spice", "nail_shaped", "dark_brown"],
        "embedding_tags": ["aromatic", "intense", "medicinal"],
        "llm_prompt_hints": ["Very strong aroma", "Nail-shaped"],
        "confidence_threshold": 0.80
    },
    
    {
        "canonical_name": "Mustard Seeds",
        "scientific_name": "Brassica juncea",
        "category": "Spice",
        "subcategory": "Seed",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Mustard Seeds", "hi": "सरसों", "ta": "கடுகு", "es": "Semillas de Mostaza", "zh": "芥末籽", "ar": "بذور الخردل"},
        "visual_states": ["whole_seeds"],
        "dominant_colors": ["black", "brown", "yellow"],
        "shape_features": ["tiny_round_seeds"],
        "surface_texture": ["smooth", "hard"],
        "taste_profile": ["pungent", "sharp", "nutty"],
        "aroma_profile": ["sharp", "pungent"],
        "mouthfeel": ["crunchy", "popping"],
        "intensity_level": "strong",
        "heat_level": "medium",
        "common_uses": ["tempering", "pickles", "curries"],
        "cooking_methods": ["temper", "grind", "whole"],
        "typical_containers": ["jar", "bag"],
        "storage_conditions": {"seeds": "airtight_cool"},
        "shelf_life_days": {"seeds": 730},
        "waste_risk_level": "low",
        "density_g_per_ml": 0.70,
        "typical_package_sizes": [100, 200, 500],
        "cv_labels": ["spice", "tiny_seeds", "black_brown"],
        "embedding_tags": ["tempering", "pungent", "indian"],
        "llm_prompt_hints": ["Used in tempering", "Pops when heated"],
        "confidence_threshold": 0.80
    },
    
    {
        "canonical_name": "Bay Leaves",
        "scientific_name": "Laurus nobilis",
        "category": "Spice",
        "subcategory": "Leaf",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Bay Leaves", "hi": "तेज पत्ता", "ta": "பிரியாணி இலை", "es": "Hojas de Laurel", "zh": "月桂叶", "ar": "ورق الغار"},
        "visual_states": ["dried_leaves"],
        "dominant_colors": ["green", "olive", "brown"],
        "shape_features": ["oval_leaves", "pointed_tip"],
        "surface_texture": ["smooth", "leathery"],
        "taste_profile": ["herbal", "slightly_floral", "bitter"],
        "aroma_profile": ["herbal", "eucalyptus", "menthol"],
        "mouthfeel": ["leathery"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["biryani", "soups", "stews", "sauces"],
        "cooking_methods": ["whole_in_cooking", "remove_before_serving"],
        "typical_containers": ["jar", "packet"],
        "storage_conditions": {"dried": "airtight_cool_dark"},
        "shelf_life_days": {"dried": 365},
        "waste_risk_level": "low",
        "density_g_per_ml": 0.25,
        "typical_package_sizes": [10, 25, 50],
        "cv_labels": ["herb", "dried_leaves", "oval"],
        "embedding_tags": ["aromatic", "indian", "biryani"],
        "llm_prompt_hints": ["Remove before eating", "Used whole"],
        "confidence_threshold": 0.75
    },
    
    # ==================== MORE VEGETABLES ====================
    {
        "canonical_name": "Potato",
        "scientific_name": "Solanum tuberosum",
        "category": "Vegetable",
        "subcategory": "Tuber",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Potato", "hi": "आलू", "ta": "உருளைக்கிழங்கு", "es": "Papa", "zh": "土豆", "ar": "بطاطس"},
        "visual_states": ["raw_whole", "peeled", "cut", "cooked", "mashed"],
        "dominant_colors": ["brown", "yellow", "white", "red"],
        "shape_features": ["oval", "round", "irregular"],
        "surface_texture": ["rough_skin", "smooth_interior"],
        "taste_profile": ["starchy", "mild", "earthy"],
        "aroma_profile": ["earthy", "mild"],
        "mouthfeel": ["starchy", "soft_when_cooked"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["curries", "fries", "roasted", "mashed", "salads"],
        "cooking_methods": ["boil", "roast", "fry", "steam", "bake"],
        "typical_containers": ["loose", "bag", "box"],
        "storage_conditions": {"fresh": "cool_dark_dry_place"},
        "shelf_life_days": {"fresh": 60},
        "waste_risk_level": "low",
        "spoilage_signs": ["sprouting", "green_skin", "soft_spots", "mold"],
        "density_g_per_ml": 1.05,
        "typical_package_sizes": [1000, 2000, 5000],
        "cv_labels": ["vegetable", "tuber", "brown", "oval"],
        "embedding_tags": ["staple", "versatile", "starchy"],
        "llm_prompt_hints": ["Most common vegetable", "Very versatile"],
        "confidence_threshold": 0.90
    },
    
    {
        "canonical_name": "Spinach",
        "scientific_name": "Spinacia oleracea",
        "category": "Vegetable",
        "subcategory": "Leafy_Green",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Spinach", "hi": "पालक", "ta": "கீரை", "es": "Espinaca", "zh": "菠菜", "ar": "سبانخ"},
        "visual_states": ["raw_leaves", "cooked", "wilted"],
        "dominant_colors": ["dark_green"],
        "shape_features": ["oval_leaves", "veined"],
        "surface_texture": ["smooth", "slightly_textured"],
        "taste_profile": ["mild", "earthy", "slightly_bitter"],
        "aroma_profile": ["fresh", "earthy", "green"],
        "mouthfeel": ["tender_raw", "soft_cooked"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["saag", "salads", "soups", "smoothies"],
        "cooking_methods": ["saute", "boil", "steam", "raw"],
        "typical_containers": ["bunch", "bag", "box"],
        "storage_conditions": {"fresh": "fridge_in_crisper"},
        "shelf_life_days": {"fresh": 5, "cooked": 3},
        "waste_risk_level": "high",
        "spoilage_signs": ["wilting", "yellowing", "slime", "bad_smell"],
        "density_g_per_ml": 0.85,
        "typical_package_sizes": [250, 500, 1000],
        "cv_labels": ["vegetable", "leafy_green", "dark_green"],
        "embedding_tags": ["healthy", "leafy", "iron_rich"],
        "llm_prompt_hints": ["Very nutritious", "Wilts quickly"],
        "confidence_threshold": 0.85
    },
    
    {
        "canonical_name": "Cauliflower",
        "scientific_name": "Brassica oleracea var. botrytis",
        "category": "Vegetable",
        "subcategory": "Cruciferous",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Cauliflower", "hi": "फूलगोभी", "ta": "காலிஃப்ளவர்", "es": "Coliflor", "zh": "花椰菜", "ar": "قرنبيط"},
        "visual_states": ["raw_whole", "florets", "cooked"],
        "dominant_colors": ["white", "cream", "purple", "orange"],
        "shape_features": ["round_head", "florets", "tree_like"],
        "surface_texture": ["bumpy", "compact"],
        "taste_profile": ["mild", "slightly_sweet", "nutty"],
        "aroma_profile": ["mild", "cabbage-like"],
        "mouthfeel": ["crunchy_raw", "tender_cooked"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["curries", "roasted", "rice_substitute", "soups"],
        "cooking_methods": ["roast", "steam", "saute", "boil", "rice"],
        "typical_containers": ["loose", "wrapped", "bag"],
        "storage_conditions": {"fresh": "fridge_in_bag"},
        "shelf_life_days": {"fresh": 7},
        "waste_risk_level": "medium",
        "spoilage_signs": ["brown_spots", "soft_texture", "bad_smell"],
        "density_g_per_ml": 0.95,
        "typical_package_sizes": [500, 1000],
        "cv_labels": ["vegetable", "white", "florets", "cruciferous"],
        "embedding_tags": ["versatile", "low_carb", "healthy"],
        "llm_prompt_hints": ["Can replace rice", "Forms a head"],
        "confidence_threshold": 0.88
    },
    
    {
        "canonical_name": "Carrot",
        "scientific_name": "Daucus carota",
        "category": "Vegetable",
        "subcategory": "Root",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Carrot", "hi": "गाजर", "ta": "கேரட்", "es": "Zanahoria", "zh": "胡萝卜", "ar": "جزر"},
        "visual_states": ["raw_whole", "peeled", "sliced", "grated", "cooked"],
        "dominant_colors": ["orange", "purple", "white", "yellow"],
        "shape_features": ["elongated", "tapered", "cylindrical"],
        "surface_texture": ["smooth", "firm"],
        "taste_profile": ["sweet", "earthy"],
        "aroma_profile": ["sweet", "earthy"],
        "mouthfeel": ["crunchy_raw", "tender_cooked"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["salads", "curries", "soups", "juice", "snacks"],
        "cooking_methods": ["raw", "roast", "boil", "saute", "steam"],
        "typical_containers": ["loose", "bag"],
        "storage_conditions": {"fresh": "fridge_in_crisper"},
        "shelf_life_days": {"fresh": 30},
        "waste_risk_level": "low",
        "spoilage_signs": ["soft", "limp", "mold", "white_film"],
        "density_g_per_ml": 1.00,
        "typical_package_sizes": [500, 1000, 2000],
        "cv_labels": ["vegetable", "orange", "elongated", "root"],
        "embedding_tags": ["sweet", "crunchy", "vitamin_a"],
        "llm_prompt_hints": ["Rich in vitamin A", "Orange color"],
        "confidence_threshold": 0.90
    },
    
    {
        "canonical_name": "Bell Pepper",
        "scientific_name": "Capsicum annuum",
        "category": "Vegetable",
        "subcategory": "Fruit",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Bell Pepper", "hi": "शिमला मिर्च", "ta": "குடைமிளகாய்", "es": "Pimiento", "zh": "甜椒", "ar": "فلفل حلو"},
        "visual_states": ["raw_whole", "sliced", "diced", "roasted"],
        "dominant_colors": ["green", "red", "yellow", "orange"],
        "shape_features": ["bell_shaped", "blocky"],
        "surface_texture": ["glossy", "smooth", "thick_walls"],
        "taste_profile": ["sweet", "mild", "slightly_bitter_green"],
        "aroma_profile": ["fresh", "sweet", "grassy"],
        "mouthfeel": ["crunchy", "juicy"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["stir_fries", "salads", "stuffed", "roasted"],
        "cooking_methods": ["raw", "saute", "roast", "grill", "stuff"],
        "typical_containers": ["loose", "bag"],
        "storage_conditions": {"fresh": "fridge_in_crisper"},
        "shelf_life_days": {"fresh": 7},
        "waste_risk_level": "medium",
        "spoilage_signs": ["soft_spots", "wrinkled", "mold"],
        "density_g_per_ml": 0.90,
        "typical_package_sizes": [200, 500],
        "cv_labels": ["vegetable", "bell_shaped", "glossy", "colorful"],
        "embedding_tags": ["sweet", "crunchy", "colorful"],
        "llm_prompt_hints": ["No heat", "Various colors"],
        "confidence_threshold": 0.88
    },
    
    {
        "canonical_name": "Eggplant",
        "scientific_name": "Solanum melongena",
        "category": "Vegetable",
        "subcategory": "Fruit",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Eggplant", "hi": "बैंगन", "ta": "கத்திரிக்காய்", "es": "Berenjena", "zh": "茄子", "ar": "باذنجان"},
        "visual_states": ["raw_whole", "sliced", "cooked"],
        "dominant_colors": ["purple", "black", "white", "green"],
        "shape_features": ["oval", "elongated", "pear_shaped"],
        "surface_texture": ["glossy", "smooth"],
        "taste_profile": ["mild", "slightly_bitter", "earthy"],
        "aroma_profile": ["mild", "earthy"],
        "mouthfeel": ["spongy_raw", "creamy_cooked"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["curries", "grilled", "fried", "baba_ganoush"],
        "cooking_methods": ["saute", "roast", "grill", "fry", "steam"],
        "typical_containers": ["loose", "bag"],
        "storage_conditions": {"fresh": "cool_place_not_fridge"},
        "shelf_life_days": {"fresh": 7},
        "waste_risk_level": "medium",
        "spoilage_signs": ["brown_inside", "soft", "wrinkled"],
        "density_g_per_ml": 0.92,
        "typical_package_sizes": [500, 1000],
        "cv_labels": ["vegetable", "purple", "glossy", "oval"],
        "embedding_tags": ["versatile", "absorbent", "mild"],
        "llm_prompt_hints": ["Absorbs flavors well", "Spongy texture"],
        "confidence_threshold": 0.85
    },
    
    # ==================== MORE GRAINS & LEGUMES ====================
    {
        "canonical_name": "Chickpeas",
        "scientific_name": "Cicer arietinum",
        "category": "Legume",
        "subcategory": "Pulse",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Chickpeas", "hi": "चना", "ta": "கொண்டைக்கடலை", "es": "Garbanzos", "zh": "鹰嘴豆", "ar": "حمص"},
        "visual_states": ["dried", "soaked", "cooked", "canned"],
        "dominant_colors": ["beige", "tan", "light_brown"],
        "shape_features": ["round", "wrinkled", "pointed_tip"],
        "surface_texture": ["rough", "hard_dried", "soft_cooked"],
        "taste_profile": ["nutty", "earthy", "mild"],
        "aroma_profile": ["earthy", "nutty"],
        "mouthfeel": ["firm", "creamy_when_cooked"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["chana_masala", "hummus", "salads", "curries"],
        "cooking_methods": ["boil", "pressure_cook", "roast"],
        "typical_containers": ["bag", "can", "container"],
        "storage_conditions": {"dried": "cool_dry_airtight", "cooked": "fridge"},
        "shelf_life_days": {"dried": 730, "cooked": 3},
        "waste_risk_level": "low",
        "density_g_per_ml": 0.80,
        "typical_package_sizes": [500, 1000, 2000],
        "cv_labels": ["legume", "beige", "round", "wrinkled"],
        "embedding_tags": ["protein", "versatile", "middle_eastern"],
        "llm_prompt_hints": ["Main ingredient in hummus", "Needs soaking"],
        "confidence_threshold": 0.85
    },
    
    {
        "canonical_name": "Black Lentils",
        "scientific_name": "Vigna mungo",
        "category": "Legume",
        "subcategory": "Lentil",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Black Lentils", "hi": "उड़द दाल", "ta": "உளுந்து", "es": "Lentejas Negras", "zh": "黑扁豆", "ar": "عدس أسود"},
        "visual_states": ["whole_dried", "split", "cooked"],
        "dominant_colors": ["black", "dark_brown", "white_inside"],
        "shape_features": ["small_oval", "split_discs"],
        "surface_texture": ["smooth", "hard_dried"],
        "taste_profile": ["earthy", "mild", "creamy"],
        "aroma_profile": ["earthy", "mild"],
        "mouthfeel": ["creamy", "dense"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["dal_makhani", "idli", "dosa", "vada"],
        "cooking_methods": ["boil", "pressure_cook", "soak_and_grind"],
        "typical_containers": ["bag", "container"],
        "storage_conditions": {"dried": "cool_dry_airtight"},
        "shelf_life_days": {"dried": 730, "cooked": 3},
        "waste_risk_level": "low",
        "density_g_per_ml": 0.82,
        "typical_package_sizes": [500, 1000, 2000],
        "cv_labels": ["legume", "black", "small_oval"],
        "embedding_tags": ["protein", "indian", "fermentation"],
        "llm_prompt_hints": ["Used in dal makhani", "Also for idli/dosa"],
        "confidence_threshold": 0.80
    },
    
    {
        "canonical_name": "Wheat Flour",
        "scientific_name": "Triticum aestivum",
        "category": "Grain",
        "subcategory": "Flour",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Wheat Flour", "hi": "गेहूं का आटा", "ta": "கோதுமை மாவு", "es": "Harina de Trigo", "zh": "小麦粉", "ar": "طحين القمح"},
        "visual_states": ["powdered"],
        "dominant_colors": ["white", "off_white", "cream"],
        "shape_features": ["fine_powder"],
        "surface_texture": ["soft", "powdery", "fine"],
        "taste_profile": ["mild", "slightly_sweet"],
        "aroma_profile": ["mild", "grainy"],
        "mouthfeel": ["powdery", "fine"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["roti", "bread", "baking", "thickening"],
        "cooking_methods": ["mix", "knead", "bake"],
        "typical_containers": ["bag", "container"],
        "storage_conditions": {"flour": "cool_dry_airtight"},
        "shelf_life_days": {"flour": 180},
        "waste_risk_level": "low",
        "spoilage_signs": ["insects", "rancid_smell", "clumping"],
        "density_g_per_ml": 0.60,
        "typical_package_sizes": [1000, 2000, 5000, 10000],
        "cv_labels": ["grain", "white_powder", "flour"],
        "embedding_tags": ["staple", "baking", "versatile"],
        "llm_prompt_hints": ["Main ingredient for bread", "Very common"],
        "confidence_threshold": 0.75
    },
    
    # ==================== PROTEINS ====================
    {
        "canonical_name": "Chicken Breast",
        "scientific_name": None,
        "category": "Protein",
        "subcategory": "Poultry",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Chicken Breast", "hi": "चिकन ब्रेस्ट", "ta": "கோழி மார்பகம்", "es": "Pechuga de Pollo", "zh": "鸡胸肉", "ar": "صدر دجاج"},
        "visual_states": ["raw", "cooked", "grilled", "diced"],
        "dominant_colors": ["pink", "white", "pale"],
        "shape_features": ["oval", "thick", "lean"],
        "surface_texture": ["smooth", "moist"],
        "taste_profile": ["mild", "savory"],
        "aroma_profile": ["mild", "meaty"],
        "mouthfeel": ["tender", "lean"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["curries", "grilled", "stir_fries", "salads"],
        "cooking_methods": ["grill", "bake", "saute", "boil"],
        "typical_containers": ["tray", "vacuum_pack"],
        "storage_conditions": {"raw": "fridge_0_to_4C", "cooked": "fridge"},
        "shelf_life_days": {"raw": 2, "cooked": 3, "frozen": 180},
        "waste_risk_level": "critical",
        "spoilage_signs": ["bad_smell", "slimy", "gray_color"],
        "density_g_per_ml": 1.05,
        "typical_package_sizes": [500, 1000],
        "cv_labels": ["protein", "raw_meat", "pale_pink"],
        "embedding_tags": ["lean_protein", "versatile", "popular"],
        "llm_prompt_hints": ["Very popular protein", "Lean meat"],
        "confidence_threshold": 0.80
    },
    
    {
        "canonical_name": "Paneer",
        "scientific_name": None,
        "category": "Protein",
        "subcategory": "Dairy",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Paneer", "hi": "पनीर", "ta": "பனீர்", "es": "Paneer", "zh": "印度奶酪", "ar": "بانير"},
        "visual_states": ["block", "cubed", "crumbled", "cooked"],
        "dominant_colors": ["white", "cream"],
        "shape_features": ["rectangular_block", "cubes"],
        "surface_texture": ["smooth", "firm"],
        "taste_profile": ["mild", "milky", "fresh"],
        "aroma_profile": ["mild", "milky", "fresh"],
        "mouthfeel": ["firm", "chewy", "soft"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["paneer_tikka", "curries", "wraps", "snacks"],
        "cooking_methods": ["fry", "grill", "saute", "raw_in_salads"],
        "typical_containers": ["vacuum_pack", "container"],
        "storage_conditions": {"fresh": "fridge_in_water"},
        "shelf_life_days": {"fresh": 7},
        "waste_risk_level": "medium",
        "spoilage_signs": ["sour_smell", "slimy", "yellowing"],
        "density_g_per_ml": 1.10,
        "typical_package_sizes": [200, 500, 1000],
        "cv_labels": ["protein", "cheese", "white_block"],
        "embedding_tags": ["indian", "vegetarian", "protein"],
        "llm_prompt_hints": ["Indian cottage cheese", "Doesn't melt"],
        "confidence_threshold": 0.88
    },
    
    {
        "canonical_name": "Tofu",
        "scientific_name": None,
        "category": "Protein",
        "subcategory": "Soy",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Tofu", "hi": "टोफू", "ta": "டோஃபு", "es": "Tofu", "zh": "豆腐", "ar": "توفو"},
        "visual_states": ["block", "cubed", "pressed", "cooked"],
        "dominant_colors": ["white", "cream", "off_white"],
        "shape_features": ["rectangular_block", "soft"],
        "surface_texture": ["smooth", "spongy"],
        "taste_profile": ["bland", "mild", "absorbs_flavors"],
        "aroma_profile": ["mild", "neutral"],
        "mouthfeel": ["soft", "silky", "spongy"],
        "intensity_level": "very_mild",
        "heat_level": "none",
        "common_uses": ["stir_fries", "soups", "scrambles", "grilled"],
        "cooking_methods": ["fry", "saute", "grill", "blend", "raw"],
        "typical_containers": ["water_pack", "vacuum_pack"],
        "storage_conditions": {"fresh": "fridge_in_water"},
        "shelf_life_days": {"fresh": 7, "opened": 3},
        "waste_risk_level": "medium",
        "spoilage_signs": ["sour_smell", "slimy", "discoloration"],
        "density_g_per_ml": 1.05,
        "typical_package_sizes": [300, 500],
        "cv_labels": ["protein", "white_block", "soy"],
        "embedding_tags": ["vegan", "versatile", "asian"],
        "llm_prompt_hints": ["Made from soybeans", "Absorbs flavors"],
        "confidence_threshold": 0.85
    },
    
    {
        "canonical_name": "Eggs",
        "scientific_name": None,
        "category": "Protein",
        "subcategory": "Poultry",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Eggs", "hi": "अंडे", "ta": "முட்டை", "es": "Huevos", "zh": "鸡蛋", "ar": "بيض"},
        "visual_states": ["whole", "cracked", "cooked", "boiled"],
        "dominant_colors": ["white", "brown", "yellow_yolk"],
        "shape_features": ["oval", "smooth_shell"],
        "surface_texture": ["smooth_shell", "hard"],
        "taste_profile": ["rich", "savory", "mild"],
        "aroma_profile": ["mild", "sulfurous_when_cooked"],
        "mouthfeel": ["creamy_yolk", "firm_white"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["breakfast", "baking", "curries", "binding"],
        "cooking_methods": ["boil", "fry", "scramble", "bake", "poach"],
        "typical_containers": ["carton", "tray"],
        "storage_conditions": {"raw": "fridge", "cooked": "fridge"},
        "shelf_life_days": {"raw": 21, "cooked": 7},
        "waste_risk_level": "low",
        "spoilage_signs": ["bad_smell", "floating_in_water"],
        "density_g_per_ml": 1.03,
        "typical_package_sizes": [6, 12, 30],
        "cv_labels": ["protein", "oval", "white_brown_shell"],
        "embedding_tags": ["versatile", "protein", "breakfast"],
        "llm_prompt_hints": ["Very versatile", "Common protein"],
        "confidence_threshold": 0.90
    },
    
    # ==================== DAIRY ====================
    {
        "canonical_name": "Milk",
        "scientific_name": None,
        "category": "Dairy",
        "subcategory": "Liquid",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Milk", "hi": "दूध", "ta": "பால்", "es": "Leche", "zh": "牛奶", "ar": "حليب"},
        "visual_states": ["liquid"],
        "dominant_colors": ["white", "cream"],
        "shape_features": ["liquid"],
        "surface_texture": ["smooth", "liquid"],
        "taste_profile": ["mild", "sweet", "creamy"],
        "aroma_profile": ["mild", "dairy", "fresh"],
        "mouthfeel": ["creamy", "smooth"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["drinking", "chai", "cooking", "baking"],
        "cooking_methods": ["boil", "steam", "heat"],
        "typical_containers": ["carton", "bottle", "pouch"],
        "storage_conditions": {"fresh": "fridge", "uht": "pantry_until_opened"},
        "shelf_life_days": {"fresh": 5, "uht": 180},
        "waste_risk_level": "high",
        "spoilage_signs": ["sour_smell", "curdling", "bad_taste"],
        "density_g_per_ml": 1.03,
        "typical_package_sizes": [500, 1000, 2000],
        "cv_labels": ["dairy", "white_liquid"],
        "embedding_tags": ["staple", "versatile", "calcium"],
        "llm_prompt_hints": ["Basic staple", "Used in chai"],
        "confidence_threshold": 0.85
    },
    
    {
        "canonical_name": "Yogurt",
        "scientific_name": None,
        "category": "Dairy",
        "subcategory": "Cultured",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Yogurt", "hi": "दही", "ta": "தயிர்", "es": "Yogur", "zh": "酸奶", "ar": "زبادي"},
        "visual_states": ["thick_liquid", "stirred"],
        "dominant_colors": ["white", "cream"],
        "shape_features": ["thick_liquid", "creamy"],
        "surface_texture": ["smooth", "creamy"],
        "taste_profile": ["tangy", "sour", "creamy"],
        "aroma_profile": ["tangy", "sour", "dairy"],
        "mouthfeel": ["creamy", "smooth", "thick"],
        "intensity_level": "medium",
        "heat_level": "none",
        "common_uses": ["raita", "marinades", "smoothies", "desserts"],
        "cooking_methods": ["mix", "marinate", "temper_in_curries"],
        "typical_containers": ["container", "cup"],
        "storage_conditions": {"fresh": "fridge"},
        "shelf_life_days": {"fresh": 14},
        "waste_risk_level": "medium",
        "spoilage_signs": ["excessive_liquid", "mold", "very_sour"],
        "density_g_per_ml": 1.05,
        "typical_package_sizes": [200, 500, 1000],
        "cv_labels": ["dairy", "white_creamy", "thick"],
        "embedding_tags": ["probiotic", "versatile", "tangy"],
        "llm_prompt_hints": ["Used in raita", "Contains probiotics"],
        "confidence_threshold": 0.85
    },
    
    {
        "canonical_name": "Ghee",
        "scientific_name": None,
        "category": "Dairy",
        "subcategory": "Fat",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Ghee", "hi": "घी", "ta": "நெய்", "es": "Ghee", "zh": "酥油", "ar": "سمن"},
        "visual_states": ["liquid_when_warm", "solid_when_cool"],
        "dominant_colors": ["golden", "yellow"],
        "shape_features": ["liquid_or_solid"],
        "surface_texture": ["smooth", "oily"],
        "taste_profile": ["rich", "buttery", "nutty"],
        "aroma_profile": ["nutty", "rich", "buttery"],
        "mouthfeel": ["oily", "rich"],
        "intensity_level": "strong",
        "heat_level": "none",
        "common_uses": ["cooking", "frying", "tempering", "sweets"],
        "cooking_methods": ["fry", "saute", "temper", "drizzle"],
        "typical_containers": ["jar", "tin"],
        "storage_conditions": {"clarified": "cool_dry_place_no_fridge_needed"},
        "shelf_life_days": {"clarified": 365},
        "waste_risk_level": "low",
        "spoilage_signs": ["rancid_smell", "off_taste"],
        "density_g_per_ml": 0.90,
        "typical_package_sizes": [200, 500, 1000],
        "cv_labels": ["dairy", "golden_liquid", "fat"],
        "embedding_tags": ["indian", "rich", "clarified_butter"],
        "llm_prompt_hints": ["Clarified butter", "High smoke point"],
        "confidence_threshold": 0.85
    },
    
    {
        "canonical_name": "Butter",
        "scientific_name": None,
        "category": "Dairy",
        "subcategory": "Fat",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Butter", "hi": "मक्खन", "ta": "வெண்ணெய்", "es": "Mantequilla", "zh": "黄油", "ar": "زبدة"},
        "visual_states": ["solid", "softened", "melted"],
        "dominant_colors": ["yellow", "pale_yellow"],
        "shape_features": ["block", "stick"],
        "surface_texture": ["smooth", "firm_when_cold"],
        "taste_profile": ["rich", "creamy", "buttery"],
        "aroma_profile": ["rich", "dairy", "creamy"],
        "mouthfeel": ["creamy", "rich"],
        "intensity_level": "medium",
        "heat_level": "none",
        "common_uses": ["baking", "cooking", "spreading", "sauces"],
        "cooking_methods": ["melt", "cream", "brown", "fry"],
        "typical_containers": ["block", "tub"],
        "storage_conditions": {"fresh": "fridge", "frozen": "freezer"},
        "shelf_life_days": {"fresh": 90, "frozen": 365},
        "waste_risk_level": "low",
        "spoilage_signs": ["rancid_smell", "off_taste", "discoloration"],
        "density_g_per_ml": 0.91,
        "typical_package_sizes": [100, 250, 500],
        "cv_labels": ["dairy", "yellow_block", "fat"],
        "embedding_tags": ["baking", "rich", "versatile"],
        "llm_prompt_hints": ["Common in baking", "Creamy flavor"],
        "confidence_threshold": 0.88
    },
    
    # ==================== HERBS & AROMATICS ====================
    {
        "canonical_name": "Cilantro",
        "scientific_name": "Coriandrum sativum",
        "category": "Herb",
        "subcategory": "Leaf",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Cilantro", "hi": "हरा धनिया", "ta": "கொத்தமல்லி", "es": "Cilantro", "zh": "香菜", "ar": "كزبرة خضراء"},
        "visual_states": ["fresh_leaves", "chopped", "wilted"],
        "dominant_colors": ["bright_green"],
        "shape_features": ["delicate_leaves", "thin_stems"],
        "surface_texture": ["soft", "delicate"],
        "taste_profile": ["fresh", "citrusy", "bright"],
        "aroma_profile": ["fresh", "citrusy", "pungent"],
        "mouthfeel": ["fresh", "delicate"],
        "intensity_level": "strong",
        "heat_level": "none",
        "common_uses": ["garnish", "chutneys", "salads", "salsas"],
        "cooking_methods": ["raw", "chop", "blend"],
        "typical_containers": ["bunch", "bag"],
        "storage_conditions": {"fresh": "fridge_in_water"},
        "shelf_life_days": {"fresh": 5},
        "waste_risk_level": "critical",
        "spoilage_signs": ["wilting", "yellowing", "slimy", "bad_smell"],
        "density_g_per_ml": 0.50,
        "typical_package_sizes": [100, 200],
        "cv_labels": ["herb", "green_leaves", "delicate"],
        "embedding_tags": ["fresh", "aromatic", "garnish"],
        "llm_prompt_hints": ["Love it or hate it", "Used fresh"],
        "confidence_threshold": 0.80
    },
    
    {
        "canonical_name": "Mint",
        "scientific_name": "Mentha",
        "category": "Herb",
        "subcategory": "Leaf",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Mint", "hi": "पुदीना", "ta": "புதினா", "es": "Menta", "zh": "薄荷", "ar": "نعناع"},
        "visual_states": ["fresh_leaves", "chopped", "dried"],
        "dominant_colors": ["green", "bright_green"],
        "shape_features": ["oval_leaves", "serrated_edges"],
        "surface_texture": ["textured", "veined"],
        "taste_profile": ["fresh", "cool", "menthol"],
        "aroma_profile": ["fresh", "menthol", "cooling"],
        "mouthfeel": ["cooling", "refreshing"],
        "intensity_level": "strong",
        "heat_level": "none",
        "common_uses": ["chutneys", "tea", "garnish", "mojitos"],
        "cooking_methods": ["raw", "steep", "blend"],
        "typical_containers": ["bunch", "bag"],
        "storage_conditions": {"fresh": "fridge_in_water"},
        "shelf_life_days": {"fresh": 7},
        "waste_risk_level": "high",
        "spoilage_signs": ["wilting", "browning", "slimy"],
        "density_g_per_ml": 0.45,
        "typical_package_sizes": [50, 100],
        "cv_labels": ["herb", "green_leaves", "serrated"],
        "embedding_tags": ["cooling", "aromatic", "fresh"],
        "llm_prompt_hints": ["Cooling sensation", "Used in chutneys"],
        "confidence_threshold": 0.82
    },
    
    {
        "canonical_name": "Curry Leaves",
        "scientific_name": "Murraya koenigii",
        "category": "Herb",
        "subcategory": "Leaf",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Curry Leaves", "hi": "करी पत्ता", "ta": "கறிவேப்பிலை", "es": "Hojas de Curry", "zh": "咖喱叶", "ar": "أوراق الكاري"},
        "visual_states": ["fresh_leaves", "dried"],
        "dominant_colors": ["dark_green"],
        "shape_features": ["small_oval_leaves", "compound_leaf"],
        "surface_texture": ["smooth", "glossy"],
        "taste_profile": ["slightly_bitter", "aromatic"],
        "aroma_profile": ["strong", "aromatic", "curry-like"],
        "mouthfeel": ["crisp_when_fried"],
        "intensity_level": "strong",
        "heat_level": "none",
        "common_uses": ["tempering", "curries", "chutneys", "rice"],
        "cooking_methods": ["temper", "fry", "blend"],
        "typical_containers": ["stem", "bag"],
        "storage_conditions": {"fresh": "fridge", "dried": "airtight"},
        "shelf_life_days": {"fresh": 7, "dried": 180},
        "waste_risk_level": "medium",
        "spoilage_signs": ["browning", "loss_of_aroma"],
        "density_g_per_ml": 0.40,
        "typical_package_sizes": [50, 100],
        "cv_labels": ["herb", "dark_green", "small_leaves"],
        "embedding_tags": ["indian", "aromatic", "tempering"],
        "llm_prompt_hints": ["Essential in South Indian cooking", "Strong aroma"],
        "confidence_threshold": 0.75
    },
    
    # ==================== COOKING OILS ====================
    {
        "canonical_name": "Mustard Oil",
        "scientific_name": None,
        "category": "Oil",
        "subcategory": "Seed_Oil",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Mustard Oil", "hi": "सरसों का तेल", "ta": "கடுகு எண்ணெய்", "es": "Aceite de Mostaza", "zh": "芥末油", "ar": "زيت الخردل"},
        "visual_states": ["liquid"],
        "dominant_colors": ["golden", "yellow"],
        "shape_features": ["liquid"],
        "surface_texture": ["oily", "viscous"],
        "taste_profile": ["pungent", "sharp"],
        "aroma_profile": ["pungent", "strong"],
        "mouthfeel": ["oily"],
        "intensity_level": "very_strong",
        "heat_level": "mild",
        "common_uses": ["cooking", "tempering", "pickles"],
        "cooking_methods": ["fry", "saute", "pickle"],
        "typical_containers": ["bottle", "tin"],
        "storage_conditions": {"oil": "cool_dark_place"},
        "shelf_life_days": {"oil": 365},
        "waste_risk_level": "low",
        "spoilage_signs": ["rancid_smell", "off_taste"],
        "density_g_per_ml": 0.92,
        "typical_package_sizes": [500, 1000, 5000],
        "cv_labels": ["oil", "golden_liquid"],
        "embedding_tags": ["indian", "pungent", "cooking"],
        "llm_prompt_hints": ["Strong pungent flavor", "Popular in North India"],
        "confidence_threshold": 0.75
    },
    
    {
        "canonical_name": "Coconut Oil",
        "scientific_name": "Cocos nucifera",
        "category": "Oil",
        "subcategory": "Fruit_Oil",
        "ingredient_type": "single_ingredient",
        "status": "active",
        "names": {"en": "Coconut Oil", "hi": "नारियल का तेल", "ta": "தேங்காய் எண்ணெய்", "es": "Aceite de Coco", "zh": "椰子油", "ar": "زيت جوز الهند"},
        "visual_states": ["solid_below_24C", "liquid_above_24C"],
        "dominant_colors": ["white", "clear"],
        "shape_features": ["liquid_or_solid"],
        "surface_texture": ["smooth", "oily"],
        "taste_profile": ["mild_coconut", "sweet"],
        "aroma_profile": ["coconut", "mild"],
        "mouthfeel": ["oily", "smooth"],
        "intensity_level": "mild",
        "heat_level": "none",
        "common_uses": ["cooking", "baking", "hair_care", "skincare"],
        "cooking_methods": ["fry", "saute", "bake"],
        "typical_containers": ["jar", "bottle"],
        "storage_conditions": {"oil": "room_temperature"},
        "shelf_life_days": {"oil": 730},
        "waste_risk_level": "low",
        "spoilage_signs": ["rancid_smell", "yellowing"],
        "density_g_per_ml": 0.92,
        "typical_package_sizes": [500, 1000],
        "cv_labels": ["oil", "white_solid", "clear_liquid"],
        "embedding_tags": ["versatile", "tropical", "healthy"],
        "llm_prompt_hints": ["Solid at room temp", "Multi-purpose"],
        "confidence_threshold": 0.80
    },
]

# ============================================================================
# DATABASE OPERATIONS
# ============================================================================

async def seed_ingredients(conn):
    """Seed master ingredients with full intelligence data"""
    print("\n" + "="*80)
    print("SEEDING INGREDIENT INTELLIGENCE DATABASE")
    print("="*80)
    
    inserted_count = 0
    skipped_count = 0
    
    for ing in INGREDIENTS:
        try:
            # Check if ingredient already exists
            existing = await conn.fetchrow(
                "SELECT id FROM master_ingredients WHERE canonical_name = $1",
                ing["canonical_name"]
            )
            
            if existing:
                print(f"⏭️  Skipping {ing['canonical_name']} (already exists)")
                skipped_count += 1
                continue
            
            # Insert ingredient
            await conn.execute("""
                INSERT INTO master_ingredients (
                    canonical_name, scientific_name, category, subcategory,
                    ingredient_type, status, names,
                    visual_states, dominant_colors, shape_features, surface_texture,
                    color_hints, texture_hints,
                    taste_profile, aroma_profile, mouthfeel, intensity_level, heat_level,
                    common_uses, cooking_methods, typical_containers,
                    storage_conditions, shelf_life_days, waste_risk_level, spoilage_signs,
                    density_g_per_ml, typical_package_sizes,
                    cv_labels, embedding_tags, llm_prompt_hints, confidence_threshold
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13,
                    $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25,
                    $26, $27, $28, $29, $30, $31
                )
            """,
                ing["canonical_name"], ing.get("scientific_name"), ing["category"], 
                ing.get("subcategory"), ing["ingredient_type"], ing["status"],
                json.dumps(ing["names"]),  # Convert dict to JSON string
                ing.get("visual_states"), ing.get("dominant_colors"), 
                ing.get("shape_features"), ing.get("surface_texture"),
                ing.get("color_hints"), ing.get("texture_hints"),
                ing.get("taste_profile"), ing.get("aroma_profile"), 
                ing.get("mouthfeel"), ing.get("intensity_level"), ing.get("heat_level"),
                ing.get("common_uses"), ing.get("cooking_methods"), 
                ing.get("typical_containers"),
                json.dumps(ing.get("storage_conditions")) if ing.get("storage_conditions") else None,
                json.dumps(ing.get("shelf_life_days")) if ing.get("shelf_life_days") else None,
                ing.get("waste_risk_level"), ing.get("spoilage_signs"),
                ing.get("density_g_per_ml"), ing.get("typical_package_sizes"),
                ing.get("cv_labels"), ing.get("embedding_tags"),
                ing.get("llm_prompt_hints"), ing.get("confidence_threshold")
            )
            
            print(f"✅ Inserted: {ing['canonical_name']} ({ing['category']})")
            inserted_count += 1
            
        except Exception as e:
            print(f"❌ Error inserting {ing['canonical_name']}: {e}")
            continue
    
    print("\n" + "-"*80)
    print(f"✅ Inserted: {inserted_count} ingredients")
    print(f"⏭️  Skipped: {skipped_count} ingredients (already exist)")
    print("="*80 + "\n")
    
    return inserted_count

async def seed_aliases(conn):
    """Seed multi-language aliases for all ingredients"""
    print("\n" + "="*80)
    print("SEEDING MULTI-LANGUAGE ALIASES")
    print("="*80)
    
    # Get all ingredients
    ingredients = await conn.fetch("SELECT id, canonical_name, names FROM master_ingredients")
    
    inserted_count = 0
    
    for ing in ingredients:
        # Parse JSON names
        names = json.loads(ing['names']) if isinstance(ing['names'], str) else ing['names']
        
        # Insert aliases for each language
        for lang_code, alias_name in names.items():
            try:
                await conn.execute("""
                    INSERT INTO ingredient_aliases (ingredient_id, alias_name, language_code, is_primary)
                    VALUES ($1, $2, $3, true)
                    ON CONFLICT (ingredient_id, alias_name, language_code) DO NOTHING
                """, ing['id'], alias_name, lang_code)
                inserted_count += 1
            except Exception as e:
                print(f"❌ Error inserting alias {alias_name}: {e}")
                continue
    
    print(f"✅ Inserted: {inserted_count} aliases")
    print("="*80 + "\n")
    
    return inserted_count

# ============================================================================
# MAIN
# ============================================================================

async def main():
    """Main seeding function"""
    if not DATABASE_URL:
        print("❌ ERROR: DATABASE_URL environment variable not set")
        sys.exit(1)
    
    print("\n" + "="*80)
    print(f"SAVO INGREDIENT INTELLIGENCE SEEDER")
    print(f"Time: {datetime.now().isoformat()}")
    print(f"Database: {DATABASE_URL[:50]}...")
    print("="*80)
    
    try:
        # Connect to database
        conn = await asyncpg.connect(DATABASE_URL)
        print("✅ Connected to database")
        
        # Seed ingredients
        ing_count = await seed_ingredients(conn)
        
        # Seed aliases
        alias_count = await seed_aliases(conn)
        
        # Close connection
        await conn.close()
        
        print("\n" + "="*80)
        print("🎉 SEEDING COMPLETE!")
        print(f"   • {ing_count} ingredients inserted")
        print(f"   • {alias_count} aliases inserted")
        print("="*80 + "\n")
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
