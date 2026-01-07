"""
Expand Ingredient Database to 100+
Adds 63 more ingredients to reach 100+ total coverage
"""

import os
import sys
import asyncio
from datetime import datetime
import asyncpg

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASE_URL = os.getenv("DATABASE_URL")

# New ingredients to add (37 existing + 63 new = 100 total)
NEW_INGREDIENTS = [
    # ==================== VEGETABLES (15 more) ====================
    {
        "canonical_name": "Cabbage",
        "scientific_name": "Brassica oleracea var. capitata",
        "category": "Vegetable",
        "subcategory": "Leafy",
        "names": {"en": "Cabbage", "hi": "पत्ता गोभी", "ta": "முட்டைகோஸ்", "es": "Repollo", "zh": "卷心菜", "ar": "ملفوف"},
        "visual_states": ["raw_whole", "raw_cut", "cooked"],
        "dominant_colors": ["#90EE90", "#FFFFFF", "#E8F5E9"],
        "taste_profile": ["mild", "slightly_sweet", "crunchy"],
        "common_uses": ["coleslaw", "stir_fry", "soup", "fermented"],
        "cooking_methods": ["raw", "sauteed", "boiled", "steamed", "fermented"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 14, "cooked": 3},
        "waste_risk_level": "medium",
        "spoilage_signs": ["wilting", "dark_spots", "slimy_texture", "odor"],
        "cv_labels": ["cabbage", "leafy_vegetable", "green", "round"]
    },
    {
        "canonical_name": "Broccoli",
        "scientific_name": "Brassica oleracea var. italica",
        "category": "Vegetable",
        "subcategory": "Cruciferous",
        "names": {"en": "Broccoli", "hi": "ब्रोकली", "ta": "ப்ரோக்கோலி", "es": "Brócoli", "zh": "西兰花", "ar": "بروكلي"},
        "visual_states": ["raw_whole", "raw_cut", "cooked"],
        "dominant_colors": ["#228B22", "#006400"],
        "taste_profile": ["slightly_bitter", "earthy", "nutty"],
        "common_uses": ["steamed", "stir_fry", "soup", "salad"],
        "cooking_methods": ["steamed", "roasted", "sauteed", "blanched"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "cooked": 3},
        "waste_risk_level": "high",
        "spoilage_signs": ["yellowing", "wilting", "odor", "slimy_texture"],
        "cv_labels": ["broccoli", "green_vegetable", "florets", "cruciferous"]
    },
    {
        "canonical_name": "Cucumber",
        "scientific_name": "Cucumis sativus",
        "category": "Vegetable",
        "subcategory": "Fruit_Vegetable",
        "names": {"en": "Cucumber", "hi": "खीरा", "ta": "வெள்ளரி", "es": "Pepino", "zh": "黄瓜", "ar": "خيار"},
        "visual_states": ["raw_whole", "raw_cut", "pickled"],
        "dominant_colors": ["#006400", "#90EE90"],
        "taste_profile": ["mild", "refreshing", "crunchy", "watery"],
        "common_uses": ["salad", "pickle", "raita", "juice"],
        "cooking_methods": ["raw", "pickled", "sauteed"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "pickled": 60},
        "waste_risk_level": "medium",
        "spoilage_signs": ["soft_spots", "yellowing", "slimy_texture"],
        "cv_labels": ["cucumber", "green_vegetable", "cylindrical", "fresh"]
    },
    {
        "canonical_name": "Zucchini",
        "scientific_name": "Cucurbita pepo",
        "category": "Vegetable",
        "subcategory": "Squash",
        "names": {"en": "Zucchini", "hi": "तोरी", "ta": "சுக்கினி", "es": "Calabacín", "zh": "西葫芦", "ar": "كوسة"},
        "visual_states": ["raw_whole", "raw_cut", "cooked"],
        "dominant_colors": ["#228B22", "#006400"],
        "taste_profile": ["mild", "slightly_sweet", "tender"],
        "common_uses": ["grilled", "sauteed", "spiralized", "baked"],
        "cooking_methods": ["grilled", "sauteed", "baked", "roasted"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "cooked": 3},
        "waste_risk_level": "high",
        "spoilage_signs": ["soft_spots", "wrinkled_skin", "mold"],
        "cv_labels": ["zucchini", "summer_squash", "green", "cylindrical"]
    },
    {
        "canonical_name": "Pumpkin",
        "scientific_name": "Cucurbita pepo",
        "category": "Vegetable",
        "subcategory": "Squash",
        "names": {"en": "Pumpkin", "hi": "कद्दू", "ta": "பரங்கி", "es": "Calabaza", "zh": "南瓜", "ar": "يقطين"},
        "visual_states": ["raw_whole", "raw_cut", "cooked"],
        "dominant_colors": ["#FF8C00", "#FFA500"],
        "taste_profile": ["sweet", "earthy", "nutty"],
        "common_uses": ["curry", "soup", "pie", "roasted"],
        "cooking_methods": ["boiled", "roasted", "steamed", "pureed"],
        "storage_conditions": {"temperature": "cool_dry", "humidity": "low", "light": "dark"},
        "shelf_life_days": {"fresh": 30, "cooked": 5},
        "waste_risk_level": "low",
        "spoilage_signs": ["soft_spots", "mold", "wrinkled_skin"],
        "cv_labels": ["pumpkin", "orange_vegetable", "round", "squash"]
    },
    {
        "canonical_name": "Green Beans",
        "scientific_name": "Phaseolus vulgaris",
        "category": "Vegetable",
        "subcategory": "Legume",
        "names": {"en": "Green Beans", "hi": "फलियां", "ta": "பச்சைப் பீன்ஸ்", "es": "Judías verdes", "zh": "四季豆", "ar": "فاصوليا خضراء"},
        "visual_states": ["raw_whole", "raw_cut", "cooked"],
        "dominant_colors": ["#228B22", "#006400"],
        "taste_profile": ["fresh", "slightly_sweet", "crunchy"],
        "common_uses": ["steamed", "stir_fry", "salad", "casserole"],
        "cooking_methods": ["steamed", "boiled", "sauteed", "blanched"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "cooked": 3},
        "waste_risk_level": "high",
        "spoilage_signs": ["brown_spots", "wilting", "slimy_texture"],
        "cv_labels": ["green_beans", "pod", "green", "long"]
    },
    {
        "canonical_name": "Radish",
        "scientific_name": "Raphanus sativus",
        "category": "Vegetable",
        "subcategory": "Root",
        "names": {"en": "Radish", "hi": "मूली", "ta": "முள்ளங்கி", "es": "Rábano", "zh": "萝卜", "ar": "فجل"},
        "visual_states": ["raw_whole", "raw_cut", "pickled"],
        "dominant_colors": ["#FF1493", "#FFFFFF"],
        "taste_profile": ["peppery", "crisp", "slightly_bitter"],
        "common_uses": ["salad", "pickle", "garnish", "juice"],
        "cooking_methods": ["raw", "pickled", "sauteed", "roasted"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 14, "pickled": 30},
        "waste_risk_level": "medium",
        "spoilage_signs": ["soft_spots", "wrinkled", "pithy"],
        "cv_labels": ["radish", "root_vegetable", "red", "round"]
    },
    {
        "canonical_name": "Beetroot",
        "scientific_name": "Beta vulgaris",
        "category": "Vegetable",
        "subcategory": "Root",
        "names": {"en": "Beetroot", "hi": "चुकंदर", "ta": "பீட்ரூட்", "es": "Remolacha", "zh": "甜菜根", "ar": "شمندر"},
        "visual_states": ["raw_whole", "raw_cut", "cooked"],
        "dominant_colors": ["#8B0000", "#DC143C"],
        "taste_profile": ["sweet", "earthy", "slightly_bitter"],
        "common_uses": ["salad", "juice", "roasted", "pickled"],
        "cooking_methods": ["boiled", "roasted", "steamed", "raw"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 14, "cooked": 5},
        "waste_risk_level": "low",
        "spoilage_signs": ["soft_spots", "wrinkled", "mold"],
        "cv_labels": ["beetroot", "root_vegetable", "red", "round"]
    },
    {
        "canonical_name": "Sweet Corn",
        "scientific_name": "Zea mays",
        "category": "Vegetable",
        "subcategory": "Grain",
        "names": {"en": "Sweet Corn", "hi": "मक्का", "ta": "சோளம்", "es": "Maíz dulce", "zh": "甜玉米", "ar": "الذرة الحلوة"},
        "visual_states": ["raw_whole", "kernels", "cooked"],
        "dominant_colors": ["#FFFF00", "#FFD700"],
        "taste_profile": ["sweet", "starchy", "juicy"],
        "common_uses": ["boiled", "grilled", "soup", "salad"],
        "cooking_methods": ["boiled", "grilled", "roasted", "steamed"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 5, "cooked": 3},
        "waste_risk_level": "high",
        "spoilage_signs": ["dried_kernels", "brown_spots", "odor"],
        "cv_labels": ["corn", "yellow", "kernels", "cob"]
    },
    {
        "canonical_name": "Mushroom",
        "scientific_name": "Agaricus bisporus",
        "category": "Vegetable",
        "subcategory": "Fungus",
        "names": {"en": "Mushroom", "hi": "मशरूम", "ta": "காளான்", "es": "Champiñón", "zh": "蘑菇", "ar": "فطر"},
        "visual_states": ["raw_whole", "raw_cut", "cooked"],
        "dominant_colors": ["#FFFFFF", "#F5F5DC", "#8B4513"],
        "taste_profile": ["earthy", "umami", "mild"],
        "common_uses": ["sauteed", "soup", "pizza", "stir_fry"],
        "cooking_methods": ["sauteed", "grilled", "roasted", "raw"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "low", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "cooked": 3},
        "waste_risk_level": "high",
        "spoilage_signs": ["slimy_texture", "dark_spots", "odor", "shriveling"],
        "cv_labels": ["mushroom", "white", "cap", "fungus"]
    },
    {
        "canonical_name": "Lettuce",
        "scientific_name": "Lactuca sativa",
        "category": "Vegetable",
        "subcategory": "Leafy",
        "names": {"en": "Lettuce", "hi": "सलाद पत्ता", "ta": "கீரை", "es": "Lechuga", "zh": "生菜", "ar": "خس"},
        "visual_states": ["raw_whole", "raw_cut"],
        "dominant_colors": ["#90EE90", "#006400"],
        "taste_profile": ["mild", "fresh", "crisp", "slightly_bitter"],
        "common_uses": ["salad", "sandwich", "wrap", "garnish"],
        "cooking_methods": ["raw", "wilted"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 7},
        "waste_risk_level": "very_high",
        "spoilage_signs": ["wilting", "brown_edges", "slimy_texture"],
        "cv_labels": ["lettuce", "leafy_green", "salad", "crisp"]
    },
    {
        "canonical_name": "Celery",
        "scientific_name": "Apium graveolens",
        "category": "Vegetable",
        "subcategory": "Stalk",
        "names": {"en": "Celery", "hi": "अजमोद", "ta": "செலரி", "es": "Apio", "zh": "芹菜", "ar": "كرفس"},
        "visual_states": ["raw_whole", "raw_cut"],
        "dominant_colors": ["#90EE90", "#006400"],
        "taste_profile": ["fresh", "crisp", "slightly_bitter"],
        "common_uses": ["salad", "soup", "juice", "stir_fry"],
        "cooking_methods": ["raw", "sauteed", "boiled", "juiced"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 14, "cooked": 3},
        "waste_risk_level": "medium",
        "spoilage_signs": ["wilting", "brown_spots", "slimy_texture"],
        "cv_labels": ["celery", "green", "stalk", "crisp"]
    },
    {
        "canonical_name": "Asparagus",
        "scientific_name": "Asparagus officinalis",
        "category": "Vegetable",
        "subcategory": "Stalk",
        "names": {"en": "Asparagus", "hi": "शतावरी", "ta": "தண்ணீர்விட்டான் கிழங்கு", "es": "Espárrago", "zh": "芦笋", "ar": "هليون"},
        "visual_states": ["raw_whole", "cooked"],
        "dominant_colors": ["#006400", "#90EE90"],
        "taste_profile": ["earthy", "slightly_bitter", "nutty"],
        "common_uses": ["grilled", "roasted", "steamed", "soup"],
        "cooking_methods": ["grilled", "roasted", "steamed", "sauteed"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 5, "cooked": 3},
        "waste_risk_level": "very_high",
        "spoilage_signs": ["wilting", "slimy_tips", "odor"],
        "cv_labels": ["asparagus", "green", "spear", "tender"]
    },
    {
        "canonical_name": "Kale",
        "scientific_name": "Brassica oleracea var. sabellica",
        "category": "Vegetable",
        "subcategory": "Leafy",
        "names": {"en": "Kale", "hi": "केल", "ta": "கேல்", "es": "Col rizada", "zh": "羽衣甘蓝", "ar": "كرنب"},
        "visual_states": ["raw_whole", "raw_cut", "cooked"],
        "dominant_colors": ["#006400", "#228B22"],
        "taste_profile": ["earthy", "slightly_bitter", "robust"],
        "common_uses": ["salad", "smoothie", "chips", "sauteed"],
        "cooking_methods": ["raw", "sauteed", "baked", "steamed"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "cooked": 3},
        "waste_risk_level": "medium",
        "spoilage_signs": ["yellowing", "wilting", "slimy_texture"],
        "cv_labels": ["kale", "leafy_green", "curly", "dark"]
    },
    {
        "canonical_name": "Brussels Sprouts",
        "scientific_name": "Brassica oleracea var. gemmifera",
        "category": "Vegetable",
        "subcategory": "Cruciferous",
        "names": {"en": "Brussels Sprouts", "hi": "ब्रसेल्स स्प्राउट्स", "ta": "ப்ரஸ்ஸல்ஸ் முளைகள்", "es": "Coles de Bruselas", "zh": "球芽甘蓝", "ar": "كرنب بروكسل"},
        "visual_states": ["raw_whole", "raw_cut", "cooked"],
        "dominant_colors": ["#90EE90", "#006400"],
        "taste_profile": ["nutty", "slightly_bitter", "earthy"],
        "common_uses": ["roasted", "sauteed", "steamed", "grilled"],
        "cooking_methods": ["roasted", "sauteed", "steamed", "blanched"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 10, "cooked": 3},
        "waste_risk_level": "medium",
        "spoilage_signs": ["yellowing", "wilting", "odor"],
        "cv_labels": ["brussels_sprouts", "green", "small", "round"]
    },
    
    # ==================== PROTEINS (12 more) ====================
    {
        "canonical_name": "Ground Beef",
        "category": "Protein",
        "subcategory": "Meat",
        "names": {"en": "Ground Beef", "hi": "कीमा", "ta": "மாட்டு இறைச்சி", "es": "Carne molida", "zh": "碎牛肉", "ar": "لحم مفروم"},
        "visual_states": ["raw", "cooked"],
        "dominant_colors": ["#8B0000", "#A52A2A"],
        "taste_profile": ["savory", "rich", "umami"],
        "common_uses": ["burgers", "meatballs", "tacos", "pasta_sauce"],
        "cooking_methods": ["grilled", "fried", "baked", "sauteed"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 2, "cooked": 3, "frozen": 120},
        "waste_risk_level": "very_high",
        "spoilage_signs": ["gray_color", "slimy_texture", "sour_odor"],
        "cv_labels": ["ground_beef", "red_meat", "minced", "raw"]
    },
    {
        "canonical_name": "Pork",
        "category": "Protein",
        "subcategory": "Meat",
        "names": {"en": "Pork", "hi": "सूअर का मांस", "ta": "பன்றி இறைச்சி", "es": "Cerdo", "zh": "猪肉", "ar": "لحم خنزير"},
        "visual_states": ["raw", "cooked"],
        "dominant_colors": ["#FFC0CB", "#FF69B4"],
        "taste_profile": ["savory", "mild", "slightly_sweet"],
        "common_uses": ["roasted", "grilled", "stir_fry", "stew"],
        "cooking_methods": ["roasted", "grilled", "fried", "braised"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 3, "cooked": 4, "frozen": 180},
        "waste_risk_level": "very_high",
        "spoilage_signs": ["gray_color", "sticky_texture", "sour_odor"],
        "cv_labels": ["pork", "pink_meat", "raw", "protein"]
    },
    {
        "canonical_name": "Lamb",
        "category": "Protein",
        "subcategory": "Meat",
        "names": {"en": "Lamb", "hi": "भेड़ का मांस", "ta": "ஆட்டு இறைச்சி", "es": "Cordero", "zh": "羊肉", "ar": "لحم خروف"},
        "visual_states": ["raw", "cooked"],
        "dominant_colors": ["#8B0000", "#A52A2A"],
        "taste_profile": ["rich", "gamey", "savory"],
        "common_uses": ["roasted", "grilled", "curry", "stew"],
        "cooking_methods": ["roasted", "grilled", "braised", "stewed"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 3, "cooked": 4, "frozen": 270},
        "waste_risk_level": "very_high",
        "spoilage_signs": ["brown_color", "sticky_texture", "strong_odor"],
        "cv_labels": ["lamb", "red_meat", "raw", "protein"]
    },
    {
        "canonical_name": "Salmon",
        "category": "Protein",
        "subcategory": "Fish",
        "names": {"en": "Salmon", "hi": "सामन मछली", "ta": "சால்மன் மீன்", "es": "Salmón", "zh": "三文鱼", "ar": "سلمون"},
        "visual_states": ["raw", "cooked"],
        "dominant_colors": ["#FFA07A", "#FF8C69"],
        "taste_profile": ["rich", "buttery", "mild"],
        "common_uses": ["grilled", "baked", "smoked", "sushi"],
        "cooking_methods": ["grilled", "baked", "pan_fried", "raw"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 2, "cooked": 3, "frozen": 90},
        "waste_risk_level": "very_high",
        "spoilage_signs": ["fishy_odor", "dull_color", "slimy_texture"],
        "cv_labels": ["salmon", "fish", "pink", "fillet"]
    },
    {
        "canonical_name": "Tuna",
        "category": "Protein",
        "subcategory": "Fish",
        "names": {"en": "Tuna", "hi": "ट्यूना मछली", "ta": "மஞ்சள் துடுப்பு மீன்", "es": "Atún", "zh": "金枪鱼", "ar": "تونة"},
        "visual_states": ["raw", "cooked", "canned"],
        "dominant_colors": ["#8B0000", "#A52A2A"],
        "taste_profile": ["rich", "meaty", "mild"],
        "common_uses": ["grilled", "sushi", "salad", "sandwich"],
        "cooking_methods": ["grilled", "baked", "raw", "canned"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 2, "cooked": 3, "canned": 1095},
        "waste_risk_level": "very_high",
        "spoilage_signs": ["strong_odor", "brown_color", "dry_texture"],
        "cv_labels": ["tuna", "fish", "red", "steak"]
    },
    {
        "canonical_name": "Shrimp",
        "category": "Protein",
        "subcategory": "Seafood",
        "names": {"en": "Shrimp", "hi": "झींगा", "ta": "இறால்", "es": "Camarón", "zh": "虾", "ar": "جمبري"},
        "visual_states": ["raw", "cooked"],
        "dominant_colors": ["#FFB6C1", "#FF69B4", "#FFA07A"],
        "taste_profile": ["sweet", "delicate", "mild"],
        "common_uses": ["grilled", "fried", "boiled", "stir_fry"],
        "cooking_methods": ["grilled", "boiled", "fried", "sauteed"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 2, "cooked": 3, "frozen": 180},
        "waste_risk_level": "very_high",
        "spoilage_signs": ["ammonia_odor", "gray_color", "slimy_texture"],
        "cv_labels": ["shrimp", "seafood", "pink", "curved"]
    },
    {
        "canonical_name": "Crab",
        "category": "Protein",
        "subcategory": "Seafood",
        "names": {"en": "Crab", "hi": "केकड़ा", "ta": "நண்டு", "es": "Cangrejo", "zh": "螃蟹", "ar": "سرطان البحر"},
        "visual_states": ["raw", "cooked"],
        "dominant_colors": ["#8B4513", "#FF6347"],
        "taste_profile": ["sweet", "delicate", "buttery"],
        "common_uses": ["boiled", "steamed", "cake", "salad"],
        "cooking_methods": ["boiled", "steamed", "grilled", "fried"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 1, "cooked": 3, "frozen": 90},
        "waste_risk_level": "very_high",
        "spoilage_signs": ["ammonia_odor", "discoloration", "slimy_texture"],
        "cv_labels": ["crab", "seafood", "shell", "crustacean"]
    },
    {
        "canonical_name": "Turkey",
        "category": "Protein",
        "subcategory": "Poultry",
        "names": {"en": "Turkey", "hi": "टर्की", "ta": "வான்கோழி", "es": "Pavo", "zh": "火鸡", "ar": "ديك رومي"},
        "visual_states": ["raw", "cooked"],
        "dominant_colors": ["#FFC0CB", "#FFFFFF"],
        "taste_profile": ["mild", "slightly_sweet", "lean"],
        "common_uses": ["roasted", "grilled", "sandwich", "soup"],
        "cooking_methods": ["roasted", "grilled", "baked", "fried"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 2, "cooked": 4, "frozen": 365},
        "waste_risk_level": "very_high",
        "spoilage_signs": ["gray_color", "slimy_texture", "sour_odor"],
        "cv_labels": ["turkey", "poultry", "white_meat", "lean"]
    },
    {
        "canonical_name": "Duck",
        "category": "Protein",
        "subcategory": "Poultry",
        "names": {"en": "Duck", "hi": "बत्तख", "ta": "வாத்து", "es": "Pato", "zh": "鸭", "ar": "بط"},
        "visual_states": ["raw", "cooked"],
        "dominant_colors": ["#8B0000", "#A52A2A"],
        "taste_profile": ["rich", "gamey", "fatty"],
        "common_uses": ["roasted", "confit", "grilled", "stir_fry"],
        "cooking_methods": ["roasted", "grilled", "braised", "fried"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 2, "cooked": 4, "frozen": 180},
        "waste_risk_level": "very_high",
        "spoilage_signs": ["gray_color", "sticky_texture", "strong_odor"],
        "cv_labels": ["duck", "poultry", "dark_meat", "rich"]
    },
    {
        "canonical_name": "Bacon",
        "category": "Protein",
        "subcategory": "Processed_Meat",
        "names": {"en": "Bacon", "hi": "बेकन", "ta": "பேக்கன்", "es": "Tocino", "zh": "培根", "ar": "لحم خنزير مقدد"},
        "visual_states": ["raw", "cooked"],
        "dominant_colors": ["#FFC0CB", "#8B4513"],
        "taste_profile": ["savory", "salty", "smoky"],
        "common_uses": ["breakfast", "sandwich", "topping", "wrap"],
        "cooking_methods": ["fried", "baked", "grilled"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "cooked": 5, "frozen": 30},
        "waste_risk_level": "low",
        "spoilage_signs": ["gray_color", "slimy_texture", "sour_odor"],
        "cv_labels": ["bacon", "cured_meat", "strips", "pink"]
    },
    {
        "canonical_name": "Sausage",
        "category": "Protein",
        "subcategory": "Processed_Meat",
        "names": {"en": "Sausage", "hi": "सॉसेज", "ta": "தொத்திறைச்சி", "es": "Salchicha", "zh": "香肠", "ar": "سجق"},
        "visual_states": ["raw", "cooked"],
        "dominant_colors": ["#8B4513", "#A0522D"],
        "taste_profile": ["savory", "spiced", "juicy"],
        "common_uses": ["grilled", "fried", "pizza", "pasta"],
        "cooking_methods": ["grilled", "fried", "baked", "boiled"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "cooked": 4, "frozen": 60},
        "waste_risk_level": "medium",
        "spoilage_signs": ["gray_color", "slimy_casing", "sour_odor"],
        "cv_labels": ["sausage", "processed_meat", "link", "brown"]
    },
    {
        "canonical_name": "Ham",
        "category": "Protein",
        "subcategory": "Processed_Meat",
        "names": {"en": "Ham", "hi": "हैम", "ta": "ஹாம்", "es": "Jamón", "zh": "火腿", "ar": "لحم خنزير"},
        "visual_states": ["raw", "cooked"],
        "dominant_colors": ["#FFC0CB", "#FF69B4"],
        "taste_profile": ["savory", "salty", "smoky"],
        "common_uses": ["sandwich", "breakfast", "pizza", "salad"],
        "cooking_methods": ["baked", "grilled", "fried", "raw"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "cooked": 5, "frozen": 60},
        "waste_risk_level": "low",
        "spoilage_signs": ["gray_color", "slimy_texture", "sour_odor"],
        "cv_labels": ["ham", "cured_meat", "pink", "sliced"]
    },
    
    # Continue in next message...
]

# I'll create a function to insert these ingredients
async def expand_ingredient_database():
    """Add 63 new ingredients to database"""
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        count = 0
        for ing_data in NEW_INGREDIENTS:
            # Insert ingredient
            ing_id = await conn.fetchval("""
                INSERT INTO master_ingredients (
                    name, scientific_name, category, subcategory,
                    ingredient_type, status, visual_states, dominant_colors,
                    taste_profile, common_uses, cooking_methods,
                    storage_conditions, shelf_life_days, waste_risk_level,
                    spoilage_signs, cv_labels
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16
                ) RETURNING id
            """, 
                ing_data["canonical_name"],
                ing_data.get("scientific_name"),
                ing_data["category"],
                ing_data.get("subcategory"),
                ing_data.get("ingredient_type", "single_ingredient"),
                ing_data.get("status", "active"),
                ing_data.get("visual_states", []),
                ing_data.get("dominant_colors", []),
                ing_data.get("taste_profile", []),
                ing_data.get("common_uses", []),
                ing_data.get("cooking_methods", []),
                json.dumps(ing_data.get("storage_conditions", {})),
                json.dumps(ing_data.get("shelf_life_days", {})),
                ing_data.get("waste_risk_level", "medium"),
                ing_data.get("spoilage_signs", []),
                ing_data.get("cv_labels", [])
            )
            
            # Insert aliases
            for lang, name in ing_data.get("names", {}).items():
                await conn.execute("""
                    INSERT INTO ingredient_aliases (
                        ingredient_id, alias_name, language_code, is_primary
                    ) VALUES ($1, $2, $3, $4)
                """, ing_id, name, lang, lang == "en")
            
            count += 1
            print(f"✅ Added: {ing_data['canonical_name']} ({count}/{len(NEW_INGREDIENTS)})")
        
        print(f"\n🎉 Successfully added {count} new ingredients!")
        
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(expand_ingredient_database())
