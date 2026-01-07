"""
Expand Ingredient Database to 100+
Adds 53 more ingredients to reach 90+ total coverage
(37 existing + 53 new = 90 total)
"""

import os
import sys
import asyncio
import json
from datetime import datetime
import asyncpg

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

DATABASE_URL = os.getenv("DATABASE_URL")

# New ingredients to add (37 existing + 53 new = 90 total)
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
    
    # ==================== FRUITS (10 more) ====================
    {
        "canonical_name": "Apple",
        "scientific_name": "Malus domestica",
        "category": "Fruit",
        "subcategory": "Pome",
        "names": {"en": "Apple", "hi": "सेब", "ta": "ஆப்பிள்", "es": "Manzana", "zh": "苹果", "ar": "تفاحة"},
        "visual_states": ["raw_whole", "raw_cut", "cooked"],
        "dominant_colors": ["#FF0000", "#00FF00", "#FFFF00"],
        "taste_profile": ["sweet", "tart", "crisp", "juicy"],
        "common_uses": ["snack", "pie", "juice", "salad"],
        "cooking_methods": ["raw", "baked", "stewed", "juiced"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 30, "cooked": 5},
        "waste_risk_level": "low",
        "spoilage_signs": ["soft_spots", "bruising", "wrinkled_skin"],
        "cv_labels": ["apple", "fruit", "red", "round"]
    },
    {
        "canonical_name": "Banana",
        "scientific_name": "Musa",
        "category": "Fruit",
        "subcategory": "Berry",
        "names": {"en": "Banana", "hi": "केला", "ta": "வாழைப்பழம்", "es": "Plátano", "zh": "香蕉", "ar": "موز"},
        "visual_states": ["raw_whole", "peeled"],
        "dominant_colors": ["#FFFF00", "#8B4513"],
        "taste_profile": ["sweet", "creamy", "mild"],
        "common_uses": ["snack", "smoothie", "dessert", "bread"],
        "cooking_methods": ["raw", "baked", "fried", "blended"],
        "storage_conditions": {"temperature": "room_temp", "humidity": "medium", "light": "indirect"},
        "shelf_life_days": {"fresh": 7},
        "waste_risk_level": "high",
        "spoilage_signs": ["brown_spots", "mushy_texture", "odor"],
        "cv_labels": ["banana", "yellow", "curved", "fruit"]
    },
    {
        "canonical_name": "Orange",
        "scientific_name": "Citrus sinensis",
        "category": "Fruit",
        "subcategory": "Citrus",
        "names": {"en": "Orange", "hi": "संतरा", "ta": "ஆரஞ்சு", "es": "Naranja", "zh": "橙子", "ar": "برتقال"},
        "visual_states": ["raw_whole", "peeled", "juiced"],
        "dominant_colors": ["#FFA500", "#FF8C00"],
        "taste_profile": ["sweet", "tangy", "citrusy", "juicy"],
        "common_uses": ["snack", "juice", "salad", "dessert"],
        "cooking_methods": ["raw", "juiced", "zested"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 14},
        "waste_risk_level": "low",
        "spoilage_signs": ["soft_spots", "mold", "dried_out"],
        "cv_labels": ["orange", "citrus", "round", "bright"]
    },
    {
        "canonical_name": "Strawberry",
        "scientific_name": "Fragaria × ananassa",
        "category": "Fruit",
        "subcategory": "Berry",
        "names": {"en": "Strawberry", "hi": "स्ट्रॉबेरी", "ta": "ஸ்ட்ராபெரி", "es": "Fresa", "zh": "草莓", "ar": "فراولة"},
        "visual_states": ["raw_whole", "sliced"],
        "dominant_colors": ["#FF0000", "#FFC0CB"],
        "taste_profile": ["sweet", "tart", "juicy"],
        "common_uses": ["snack", "dessert", "smoothie", "salad"],
        "cooking_methods": ["raw", "baked", "blended", "preserved"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 5},
        "waste_risk_level": "very_high",
        "spoilage_signs": ["mold", "mushy_texture", "odor"],
        "cv_labels": ["strawberry", "red", "berry", "seeds"]
    },
    {
        "canonical_name": "Grapes",
        "scientific_name": "Vitis vinifera",
        "category": "Fruit",
        "subcategory": "Berry",
        "names": {"en": "Grapes", "hi": "अंगूर", "ta": "திராட்சை", "es": "Uvas", "zh": "葡萄", "ar": "عنب"},
        "visual_states": ["raw_whole"],
        "dominant_colors": ["#800080", "#00FF00", "#8B0000"],
        "taste_profile": ["sweet", "tart", "juicy"],
        "common_uses": ["snack", "wine", "juice", "raisins"],
        "cooking_methods": ["raw", "dried", "juiced"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 7},
        "waste_risk_level": "medium",
        "spoilage_signs": ["shriveling", "mold", "sour_taste"],
        "cv_labels": ["grapes", "cluster", "round", "small"]
    },
    {
        "canonical_name": "Watermelon",
        "scientific_name": "Citrullus lanatus",
        "category": "Fruit",
        "subcategory": "Melon",
        "names": {"en": "Watermelon", "hi": "तरबूज", "ta": "தர்பூசணி", "es": "Sandía", "zh": "西瓜", "ar": "بطيخ"},
        "visual_states": ["raw_whole", "raw_cut"],
        "dominant_colors": ["#008000", "#FF0000", "#FFC0CB"],
        "taste_profile": ["sweet", "refreshing", "watery"],
        "common_uses": ["snack", "juice", "salad", "dessert"],
        "cooking_methods": ["raw", "juiced", "grilled"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 14, "cut": 3},
        "waste_risk_level": "medium",
        "spoilage_signs": ["soft_spots", "fermented_smell", "slimy_texture"],
        "cv_labels": ["watermelon", "green", "large", "striped"]
    },
    {
        "canonical_name": "Pineapple",
        "scientific_name": "Ananas comosus",
        "category": "Fruit",
        "subcategory": "Tropical",
        "names": {"en": "Pineapple", "hi": "अनानास", "ta": "அன்னாசி", "es": "Piña", "zh": "菠萝", "ar": "أناناس"},
        "visual_states": ["raw_whole", "peeled", "cut"],
        "dominant_colors": ["#FFD700", "#8B4513", "#00FF00"],
        "taste_profile": ["sweet", "tangy", "tropical"],
        "common_uses": ["snack", "juice", "dessert", "pizza"],
        "cooking_methods": ["raw", "grilled", "juiced", "baked"],
        "storage_conditions": {"temperature": "room_temp", "humidity": "medium", "light": "indirect"},
        "shelf_life_days": {"fresh": 5, "cut": 3},
        "waste_risk_level": "medium",
        "spoilage_signs": ["brown_spots", "fermented_smell", "soft_texture"],
        "cv_labels": ["pineapple", "yellow", "spiky", "tropical"]
    },
    {
        "canonical_name": "Mango",
        "scientific_name": "Mangifera indica",
        "category": "Fruit",
        "subcategory": "Drupe",
        "names": {"en": "Mango", "hi": "आम", "ta": "மாம்பழம்", "es": "Mango", "zh": "芒果", "ar": "مانجو"},
        "visual_states": ["raw_whole", "peeled", "sliced"],
        "dominant_colors": ["#FFA500", "#FFD700", "#FF0000"],
        "taste_profile": ["sweet", "tropical", "juicy"],
        "common_uses": ["snack", "smoothie", "dessert", "salad"],
        "cooking_methods": ["raw", "blended", "dried", "grilled"],
        "storage_conditions": {"temperature": "room_temp", "humidity": "medium", "light": "indirect"},
        "shelf_life_days": {"fresh": 5},
        "waste_risk_level": "medium",
        "spoilage_signs": ["soft_spots", "fermented_smell", "dark_spots"],
        "cv_labels": ["mango", "orange", "oval", "tropical"]
    },
    {
        "canonical_name": "Blueberry",
        "scientific_name": "Vaccinium corymbosum",
        "category": "Fruit",
        "subcategory": "Berry",
        "names": {"en": "Blueberry", "hi": "ब्लूबेरी", "ta": "நீலப்பெர்ரி", "es": "Arándano", "zh": "蓝莓", "ar": "توت أزرق"},
        "visual_states": ["raw_whole"],
        "dominant_colors": ["#0000FF", "#4B0082"],
        "taste_profile": ["sweet", "tart", "juicy"],
        "common_uses": ["snack", "dessert", "smoothie", "pancakes"],
        "cooking_methods": ["raw", "baked", "blended", "preserved"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 10},
        "waste_risk_level": "high",
        "spoilage_signs": ["mold", "shriveling", "mushy_texture"],
        "cv_labels": ["blueberry", "blue", "small", "round"]
    },
    {
        "canonical_name": "Avocado",
        "scientific_name": "Persea americana",
        "category": "Fruit",
        "subcategory": "Drupe",
        "names": {"en": "Avocado", "hi": "एवोकाडो", "ta": "வெண்ணெய் பழம்", "es": "Aguacate", "zh": "鳄梨", "ar": "أفوكادو"},
        "visual_states": ["raw_whole", "raw_cut"],
        "dominant_colors": ["#006400", "#90EE90", "#FFFF00"],
        "taste_profile": ["creamy", "mild", "buttery"],
        "common_uses": ["guacamole", "toast", "salad", "smoothie"],
        "cooking_methods": ["raw", "mashed", "blended"],
        "storage_conditions": {"temperature": "room_temp", "humidity": "medium", "light": "indirect"},
        "shelf_life_days": {"fresh": 5, "cut": 1},
        "waste_risk_level": "high",
        "spoilage_signs": ["brown_flesh", "rancid_smell", "overly_soft"],
        "cv_labels": ["avocado", "green", "oval", "creamy"]
    },
    
    # ==================== GRAINS & STAPLES (8 more) ====================
    {
        "canonical_name": "Quinoa",
        "scientific_name": "Chenopodium quinoa",
        "category": "Grain",
        "subcategory": "Pseudocereal",
        "names": {"en": "Quinoa", "hi": "क्विनोआ", "ta": "கினோவா", "es": "Quinua", "zh": "藜麦", "ar": "كينوا"},
        "visual_states": ["raw_grains", "cooked"],
        "dominant_colors": ["#F5DEB3", "#FFFFFF"],
        "taste_profile": ["nutty", "mild", "slightly_earthy"],
        "common_uses": ["salad", "bowl", "side_dish", "breakfast"],
        "cooking_methods": ["boiled", "steamed"],
        "storage_conditions": {"temperature": "cool_dry", "humidity": "low", "light": "dark"},
        "shelf_life_days": {"fresh": 730, "cooked": 5},
        "waste_risk_level": "low",
        "spoilage_signs": ["rancid_smell", "mold", "insects"],
        "cv_labels": ["quinoa", "grains", "tiny", "beige"]
    },
    {
        "canonical_name": "Oats",
        "scientific_name": "Avena sativa",
        "category": "Grain",
        "subcategory": "Cereal",
        "names": {"en": "Oats", "hi": "जई", "ta": "ஓட்ஸ்", "es": "Avena", "zh": "燕麦", "ar": "شوفان"},
        "visual_states": ["raw_grains", "cooked"],
        "dominant_colors": ["#F5DEB3", "#D2B48C"],
        "taste_profile": ["mild", "nutty", "slightly_sweet"],
        "common_uses": ["porridge", "granola", "cookies", "smoothie"],
        "cooking_methods": ["boiled", "baked", "soaked"],
        "storage_conditions": {"temperature": "cool_dry", "humidity": "low", "light": "dark"},
        "shelf_life_days": {"fresh": 365, "cooked": 5},
        "waste_risk_level": "low",
        "spoilage_signs": ["rancid_smell", "insects", "mold"],
        "cv_labels": ["oats", "grains", "flakes", "beige"]
    },
    {
        "canonical_name": "Pasta",
        "category": "Grain",
        "subcategory": "Processed",
        "names": {"en": "Pasta", "hi": "पास्ता", "ta": "பாஸ்தா", "es": "Pasta", "zh": "意大利面", "ar": "معكرونة"},
        "visual_states": ["raw_dry", "cooked"],
        "dominant_colors": ["#F5DEB3", "#FFD700"],
        "taste_profile": ["mild", "starchy"],
        "common_uses": ["main_dish", "side_dish", "salad"],
        "cooking_methods": ["boiled", "baked"],
        "storage_conditions": {"temperature": "cool_dry", "humidity": "low", "light": "dark"},
        "shelf_life_days": {"fresh": 730, "cooked": 3},
        "waste_risk_level": "low",
        "spoilage_signs": ["mold", "insects", "moisture"],
        "cv_labels": ["pasta", "noodles", "dried", "yellow"]
    },
    {
        "canonical_name": "Bread",
        "category": "Grain",
        "subcategory": "Baked",
        "names": {"en": "Bread", "hi": "रोटी", "ta": "ரொட்டி", "es": "Pan", "zh": "面包", "ar": "خبز"},
        "visual_states": ["whole_loaf", "sliced"],
        "dominant_colors": ["#8B4513", "#F5DEB3"],
        "taste_profile": ["mild", "yeasty", "starchy"],
        "common_uses": ["sandwich", "toast", "side", "crumbs"],
        "cooking_methods": ["toasted", "grilled", "raw"],
        "storage_conditions": {"temperature": "room_temp", "humidity": "low", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "frozen": 90},
        "waste_risk_level": "high",
        "spoilage_signs": ["mold", "stale", "hard_texture"],
        "cv_labels": ["bread", "loaf", "sliced", "brown"]
    },
    {
        "canonical_name": "Noodles",
        "category": "Grain",
        "subcategory": "Processed",
        "names": {"en": "Noodles", "hi": "नूडल्स", "ta": "நூடுல்ஸ்", "es": "Fideos", "zh": "面条", "ar": "نودلز"},
        "visual_states": ["raw_dry", "cooked"],
        "dominant_colors": ["#F5DEB3", "#FFFFFF"],
        "taste_profile": ["mild", "starchy"],
        "common_uses": ["soup", "stir_fry", "main_dish"],
        "cooking_methods": ["boiled", "fried", "steamed"],
        "storage_conditions": {"temperature": "cool_dry", "humidity": "low", "light": "dark"},
        "shelf_life_days": {"fresh": 365, "cooked": 3},
        "waste_risk_level": "low",
        "spoilage_signs": ["mold", "rancid_smell", "insects"],
        "cv_labels": ["noodles", "thin", "long", "dried"]
    },
    {
        "canonical_name": "Couscous",
        "scientific_name": "Triticum durum",
        "category": "Grain",
        "subcategory": "Semolina",
        "names": {"en": "Couscous", "hi": "कूसकूस", "ta": "கூஸ்கூஸ்", "es": "Cuscús", "zh": "库斯库斯", "ar": "كسكس"},
        "visual_states": ["raw_grains", "cooked"],
        "dominant_colors": ["#F5DEB3", "#FFE4B5"],
        "taste_profile": ["mild", "nutty", "fluffy"],
        "common_uses": ["side_dish", "salad", "main_dish"],
        "cooking_methods": ["steamed", "boiled"],
        "storage_conditions": {"temperature": "cool_dry", "humidity": "low", "light": "dark"},
        "shelf_life_days": {"fresh": 730, "cooked": 5},
        "waste_risk_level": "low",
        "spoilage_signs": ["rancid_smell", "insects", "mold"],
        "cv_labels": ["couscous", "grains", "tiny", "beige"]
    },
    {
        "canonical_name": "Barley",
        "scientific_name": "Hordeum vulgare",
        "category": "Grain",
        "subcategory": "Cereal",
        "names": {"en": "Barley", "hi": "जौ", "ta": "வாற்கோதுமை", "es": "Cebada", "zh": "大麦", "ar": "شعير"},
        "visual_states": ["raw_grains", "cooked"],
        "dominant_colors": ["#D2B48C", "#8B7355"],
        "taste_profile": ["nutty", "chewy", "earthy"],
        "common_uses": ["soup", "stew", "salad", "side_dish"],
        "cooking_methods": ["boiled", "steamed"],
        "storage_conditions": {"temperature": "cool_dry", "humidity": "low", "light": "dark"},
        "shelf_life_days": {"fresh": 730, "cooked": 5},
        "waste_risk_level": "low",
        "spoilage_signs": ["rancid_smell", "insects", "mold"],
        "cv_labels": ["barley", "grains", "oval", "tan"]
    },
    {
        "canonical_name": "Cornmeal",
        "scientific_name": "Zea mays",
        "category": "Grain",
        "subcategory": "Flour",
        "names": {"en": "Cornmeal", "hi": "मक्के का आटा", "ta": "சோள மாவு", "es": "Harina de maíz", "zh": "玉米粉", "ar": "دقيق الذرة"},
        "visual_states": ["powder"],
        "dominant_colors": ["#FFD700", "#FFA500"],
        "taste_profile": ["sweet", "corny", "grainy"],
        "common_uses": ["cornbread", "polenta", "coating", "porridge"],
        "cooking_methods": ["baked", "boiled", "fried"],
        "storage_conditions": {"temperature": "cool_dry", "humidity": "low", "light": "dark"},
        "shelf_life_days": {"fresh": 365},
        "waste_risk_level": "low",
        "spoilage_signs": ["rancid_smell", "insects", "clumping"],
        "cv_labels": ["cornmeal", "yellow", "powder", "grainy"]
    },
    
    # ==================== DAIRY & ALTERNATIVES (8 more) ====================
    {
        "canonical_name": "Cheese",
        "category": "Dairy",
        "subcategory": "Fermented",
        "names": {"en": "Cheese", "hi": "पनीर", "ta": "சீஸ்", "es": "Queso", "zh": "奶酪", "ar": "جبن"},
        "visual_states": ["whole", "sliced", "shredded"],
        "dominant_colors": ["#FFFF00", "#FFFFFF", "#FFA500"],
        "taste_profile": ["savory", "tangy", "creamy", "sharp"],
        "common_uses": ["sandwich", "pizza", "pasta", "snack"],
        "cooking_methods": ["melted", "grilled", "raw"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 30, "opened": 14},
        "waste_risk_level": "medium",
        "spoilage_signs": ["mold", "slimy_texture", "sour_smell"],
        "cv_labels": ["cheese", "yellow", "block", "dairy"]
    },
    {
        "canonical_name": "Yogurt",
        "category": "Dairy",
        "subcategory": "Fermented",
        "names": {"en": "Yogurt", "hi": "दही", "ta": "தயிர்", "es": "Yogur", "zh": "酸奶", "ar": "زبادي"},
        "visual_states": ["liquid"],
        "dominant_colors": ["#FFFFFF", "#FFFAF0"],
        "taste_profile": ["tangy", "creamy", "slightly_sour"],
        "common_uses": ["breakfast", "smoothie", "marinade", "sauce"],
        "cooking_methods": ["raw", "mixed"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 14, "opened": 7},
        "waste_risk_level": "medium",
        "spoilage_signs": ["mold", "separation", "sour_smell"],
        "cv_labels": ["yogurt", "white", "creamy", "dairy"]
    },
    {
        "canonical_name": "Butter",
        "category": "Dairy",
        "subcategory": "Fat",
        "names": {"en": "Butter", "hi": "मक्खन", "ta": "வெண்ணெய்", "es": "Mantequilla", "zh": "黄油", "ar": "زبدة"},
        "visual_states": ["solid", "melted"],
        "dominant_colors": ["#FFD700", "#FFF8DC"],
        "taste_profile": ["rich", "creamy", "mild"],
        "common_uses": ["cooking", "baking", "spread", "sauce"],
        "cooking_methods": ["melted", "raw", "clarified"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "low", "light": "dark"},
        "shelf_life_days": {"fresh": 30, "frozen": 180},
        "waste_risk_level": "low",
        "spoilage_signs": ["rancid_smell", "discoloration", "mold"],
        "cv_labels": ["butter", "yellow", "block", "dairy"]
    },
    {
        "canonical_name": "Cream",
        "category": "Dairy",
        "subcategory": "Liquid",
        "names": {"en": "Cream", "hi": "क्रीम", "ta": "கிரீம்", "es": "Crema", "zh": "奶油", "ar": "كريمة"},
        "visual_states": ["liquid", "whipped"],
        "dominant_colors": ["#FFFAF0", "#FFFFFF"],
        "taste_profile": ["rich", "creamy", "mild"],
        "common_uses": ["coffee", "dessert", "sauce", "soup"],
        "cooking_methods": ["whipped", "heated", "raw"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "opened": 3},
        "waste_risk_level": "high",
        "spoilage_signs": ["curdling", "sour_smell", "separation"],
        "cv_labels": ["cream", "white", "liquid", "dairy"]
    },
    {
        "canonical_name": "Sour Cream",
        "category": "Dairy",
        "subcategory": "Fermented",
        "names": {"en": "Sour Cream", "hi": "खट्टी क्रीम", "ta": "புளிப்பு கிரீம்", "es": "Crema agria", "zh": "酸奶油", "ar": "كريمة حامضة"},
        "visual_states": ["thick_liquid"],
        "dominant_colors": ["#FFFAF0", "#FFFFFF"],
        "taste_profile": ["tangy", "creamy", "rich"],
        "common_uses": ["topping", "dip", "sauce", "baking"],
        "cooking_methods": ["raw", "mixed"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 14, "opened": 7},
        "waste_risk_level": "medium",
        "spoilage_signs": ["mold", "separation", "very_sour_smell"],
        "cv_labels": ["sour_cream", "white", "thick", "dairy"]
    },
    {
        "canonical_name": "Almond Milk",
        "category": "Dairy_Alternative",
        "subcategory": "Plant_Based",
        "names": {"en": "Almond Milk", "hi": "बादाम का दूध", "ta": "பாதாம் பால்", "es": "Leche de almendra", "zh": "杏仁奶", "ar": "حليب اللوز"},
        "visual_states": ["liquid"],
        "dominant_colors": ["#F5F5DC", "#FFFFFF"],
        "taste_profile": ["nutty", "mild", "slightly_sweet"],
        "common_uses": ["drinking", "cereal", "smoothie", "baking"],
        "cooking_methods": ["raw", "heated"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "unopened": 30},
        "waste_risk_level": "medium",
        "spoilage_signs": ["separation", "sour_smell", "clumping"],
        "cv_labels": ["almond_milk", "beige", "liquid", "plant_based"]
    },
    {
        "canonical_name": "Coconut Milk",
        "scientific_name": "Cocos nucifera",
        "category": "Dairy_Alternative",
        "subcategory": "Plant_Based",
        "names": {"en": "Coconut Milk", "hi": "नारियल का दूध", "ta": "தேங்காய் பால்", "es": "Leche de coco", "zh": "椰奶", "ar": "حليب جوز الهند"},
        "visual_states": ["liquid", "thick"],
        "dominant_colors": ["#FFFFFF", "#FFFAF0"],
        "taste_profile": ["coconutty", "creamy", "rich"],
        "common_uses": ["curry", "smoothie", "dessert", "soup"],
        "cooking_methods": ["heated", "raw"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "medium", "light": "dark"},
        "shelf_life_days": {"fresh": 5, "unopened": 365},
        "waste_risk_level": "medium",
        "spoilage_signs": ["separation", "sour_smell", "mold"],
        "cv_labels": ["coconut_milk", "white", "liquid", "plant_based"]
    },
    {
        "canonical_name": "Tofu",
        "scientific_name": "Glycine max",
        "category": "Protein",
        "subcategory": "Plant_Based",
        "names": {"en": "Tofu", "hi": "टोफू", "ta": "டோஃபு", "es": "Tofu", "zh": "豆腐", "ar": "توفو"},
        "visual_states": ["block", "cubed", "crumbled"],
        "dominant_colors": ["#FFFAF0", "#FFFFFF"],
        "taste_profile": ["mild", "neutral", "slightly_nutty"],
        "common_uses": ["stir_fry", "soup", "grilled", "scramble"],
        "cooking_methods": ["fried", "grilled", "baked", "raw"],
        "storage_conditions": {"temperature": "refrigerated", "humidity": "high", "light": "dark"},
        "shelf_life_days": {"fresh": 7, "opened": 3},
        "waste_risk_level": "high",
        "spoilage_signs": ["sour_smell", "slimy_texture", "discoloration"],
        "cv_labels": ["tofu", "white", "block", "soy"]
    }
]

# I'll create a function to insert these ingredients
async def expand_ingredient_database():
    """Add 63 new ingredients to database"""
    
    conn = await asyncpg.connect(DATABASE_URL)
    
    try:
        count = 0
        skipped = 0
        for ing_data in NEW_INGREDIENTS:
            try:
                # Check if ingredient already exists
                existing = await conn.fetchval("""
                    SELECT id FROM master_ingredients WHERE name = $1
                """, ing_data["canonical_name"])
                
                if existing:
                    print(f"⏭️  Skipped (exists): {ing_data['canonical_name']}")
                    skipped += 1
                    continue
                
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
                        ON CONFLICT (ingredient_id, alias_name, language_code) DO NOTHING
                    """, ing_id, name, lang, lang == "en")
                
                count += 1
                print(f"✅ Added: {ing_data['canonical_name']} ({count}/{len(NEW_INGREDIENTS) - skipped})")
            
            except Exception as e:
                print(f"❌ Error adding {ing_data.get('canonical_name', 'unknown')}: {e}")
                continue
        
        # Get total count
        total = await conn.fetchval("SELECT COUNT(*) FROM master_ingredients")
        
        print(f"\n{'='*60}")
        print(f"🎉 Successfully added {count} new ingredients!")
        print(f"⏭️  Skipped {skipped} existing ingredients")
        print(f"📊 Total ingredients in database: {total}")
        print(f"{'='*60}")
        
    finally:
        await conn.close()


if __name__ == "__main__":
    print("="*60)
    print("EXPANDING INGREDIENT DATABASE")
    print("="*60)
    print(f"Adding {len(NEW_INGREDIENTS)} ingredients...")
    print()
    
    asyncio.run(expand_ingredient_database())
