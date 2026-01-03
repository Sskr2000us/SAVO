"""
Generate ALL 7 Multi-Cuisine Recipes with Complete Cooking Steps
All recipes use: Paneer, Tomato, Rice, Onion
Each recipe includes bilingual instructions (native language + English)
"""

import json

INGREDIENTS = ["paneer", "tomato", "rice", "onion"]

ALL_RECIPES = []

# 1. INDIAN - PANEER BIRYANI
ALL_RECIPES.append({
    "recipe_name": {
        "en": "Paneer Biryani",
        "hi": "पनीर बिरयानी"
    },
    "cuisine": "Indian",
    "cuisine_code": "indian",
    "language": "Hindi",
    "language_code": "hi-IN",
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
            "Marinate paneer cubes with yogurt, biryani masala, and ginger-garlic paste for 15 minutes.",
            "Heat ghee in a large pot. Fry sliced onions until golden brown (10 minutes). Remove half for garnish.",
            "Add diced tomatoes to remaining onions. Cook until softened (5 minutes).",
            "Add marinated paneer and cook for 5 minutes, stirring gently.",
            "In a separate pot, boil 4 cups water with salt. Add soaked rice and cook until 70% done (7-8 minutes). Drain.",
            "Layer the biryani: Half the rice at bottom, then all the paneer mixture, then remaining rice on top.",
            "Sprinkle saffron milk, fried onions, mint, and cilantro on top.",
            "Cover pot with tight lid. Cook on low heat (dum) for 20-25 minutes.",
            "Turn off heat. Let rest for 5 minutes before opening.",
            "Gently mix from bottom and serve hot with raita."
        ],
        "hi": [
            "पनीर को दही, बिरयानी मसाला और अदरक-लहसुन के पेस्ट के साथ 15 मिनट तक मैरीनेट करें।",
            "एक बड़े बर्तन में घी गर्म करें। कटे हुए प्याज को सुनहरा भूरा होने तक भूनें (10 मिनट)। आधा गार्निश के लिए निकाल लें।",
            "बचे हुए प्याज में कटे टमाटर डालें। नरम होने तक पकाएं (5 मिनट)।",
            "मैरीनेट किया हुआ पनीर डालें और धीरे से हिलाते हुए 5 मिनट तक पकाएं।",
            "एक अलग बर्तन में 4 कप पानी में नमक डालकर उबालें। भिगोए हुए चावल डालें और 70% पकने तक पकाएं (7-8 मिनट)। पानी निकाल दें।",
            "बिरयानी को परत में लगाएं: नीचे आधा चावल, फिर सारा पनीर मिश्रण, फिर ऊपर बाकी चावल।",
            "ऊपर से केसर का दूध, तले हुए प्याज, पुदीना और धनिया छिड़कें।",
            "बर्तन को ढक्कन से अच्छी तरह ढक दें। कम आंच पर (दम) 20-25 मिनट तक पकाएं।",
            "आंच बंद करें। खोलने से पहले 5 मिनट तक आराम करने दें।",
            "नीचे से धीरे से मिलाएं और रायता के साथ गर्म परोसें।"
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
        "religious": ["Hindu", "Sikh", "Vegetarian", "Jain-adaptable"]
    }
})

# 2. GREEK/MEDITERRANEAN - GEMISTA
ALL_RECIPES.append({
    "recipe_name": {
        "en": "Paneer-Stuffed Tomatoes with Rice (Gemista)",
        "el": "Ντομάτες Γεμιστές με Πανίρ"
    },
    "cuisine": "Mediterranean/Greek",
    "cuisine_code": "mediterranean",
    "language": "Greek",
    "language_code": "el-GR",
    "servings": 4,
    "total_time_minutes": 75,
    "prep_time_minutes": 25,
    "cook_time_minutes": 50,
    "difficulty": "advanced",
    "ingredients": [
        {"item": "large tomatoes", "amount": "8", "unit": "whole", "notes": "firm, ripe"},
        {"item": "paneer", "amount": "300", "unit": "g", "notes": "crumbled"},
        {"item": "long-grain rice", "amount": "1", "unit": "cup", "notes": "uncooked"},
        {"item": "onion", "amount": "2", "unit": "medium", "notes": "finely diced"},
        {"item": "olive oil", "amount": "1/3", "unit": "cup", "notes": "extra virgin"},
        {"item": "fresh mint", "amount": "3", "unit": "tbsp", "notes": "chopped"},
        {"item": "fresh dill", "amount": "3", "unit": "tbsp", "notes": "chopped"},
        {"item": "pine nuts", "amount": "2", "unit": "tbsp", "notes": "toasted"},
        {"item": "raisins", "amount": "2", "unit": "tbsp", "notes": "golden"},
        {"item": "oregano", "amount": "1", "unit": "tsp", "notes": "dried"}
    ],
    "instructions": {
        "en": [
            "Preheat oven to 180°C (350°F). Cut tops off tomatoes and carefully scoop out pulp and seeds. Save pulp and liquid.",
            "Lightly salt inside of tomatoes and turn upside down on paper towels to drain (15 minutes).",
            "Heat 3 tbsp olive oil in pan. Sauté onions until translucent (5 minutes).",
            "Chop reserved tomato pulp. Add to onions with rice, cook stirring for 3 minutes.",
            "Add crumbled paneer, pine nuts, raisins, mint, dill, oregano. Season with salt and pepper. Mix well.",
            "Fill each tomato 3/4 full with rice mixture (rice will expand during baking).",
            "Place tomatoes in baking dish. Pour reserved tomato liquid and 1 cup water around tomatoes.",
            "Drizzle remaining olive oil on top of each tomato. Place tomato tops back on.",
            "Bake uncovered for 50-60 minutes, basting with pan juices every 20 minutes.",
            "Remove when tomatoes are tender and rice is fully cooked. Let rest 10 minutes before serving."
        ],
        "el": [
            "Προθερμάνετε τον φούρνο στους 180°C. Κόψτε τα καπάκια από τις ντομάτες και αδειάστε προσεκτικά τη σάρκα. Κρατήστε τη σάρκα και το υγρό.",
            "Αλατίστε ελαφρά το εσωτερικό των ντοματών και αναποδογυρίστε τις σε χαρτί κουζίνας για να στραγγίσουν (15 λεπτά).",
            "Ζεστάνετε 3 κ.σ. ελαιόλαδο σε τηγάνι. Σοτάρετε τα κρεμμύδια μέχρι να μαλακώσουν (5 λεπτά).",
            "Κόψτε τη σάρκα ντομάτας που κρατήσατε. Προσθέστε στα κρεμμύδια μαζί με το ρύζι, ανακατεύετε για 3 λεπτά.",
            "Προσθέστε το πανίρ τριμμένο, κουκουνάρι, σταφίδες, δυόσμο, άνηθο, ρίγανη. Αλατοπιπερώστε. Ανακατέψτε καλά.",
            "Γεμίστε κάθε ντομάτα 3/4 με το μείγμα ρυζιού (το ρύζι θα φουσκώσει στο ψήσιμο).",
            "Τοποθετήστε τις ντομάτες σε πυρέξ. Ρίξτε το υγρό ντομάτας και 1 φλιτζάνι νερό γύρω από τις ντομάτες.",
            "Ραντίστε το υπόλοιπο λάδι στην κορυφή κάθε ντομάτας. Βάλτε τα καπάκια πίσω.",
            "Ψήστε ακάλυπτες για 50-60 λεπτά, ραντίζοντας με τους ζουμούς κάθε 20 λεπτά.",
            "Βγάλτε όταν οι ντομάτες είναι μαλακές και το ρύζι μαγειρεμένο. Αφήστε 10 λεπτά πριν σερβίρετε."
        ]
    },
    "nutrition": {
        "calories_kcal": 395,
        "protein_g": 18,
        "carbohydrates_g": 42,
        "fat_g": 16,
        "fiber_g": 6,
        "vitamin_c_mg": 45,
        "calcium_mg": 320
    },
    "health_benefits": {
        "paneer": "Protein source for muscle maintenance, calcium for bone density",
        "tomato": "Cooked tomatoes provide 4x more bioavailable lycopene (anti-cancer properties)",
        "rice": "Provides energy through complex carbohydrates, naturally gluten-free",
        "onion": "Contains allicin for cardiovascular health, antioxidant quercetin"
    },
    "tips": [
        "Choose firm tomatoes that can stand upright without rolling",
        "Don't overfill - rice needs room to expand",
        "Basting is crucial - keeps tomatoes moist and develops flavor",
        "Can be served warm or at room temperature (traditional Greek style)",
        "Substitute feta for paneer for more authentic Greek version"
    ],
    "cultural_context": {
        "origin": "Traditional Greek summer dish, adapted with paneer",
        "occasions": "Sunday family dinners, summer gatherings",
        "serving_suggestions": "Serve with crusty bread and Greek salad"
    },
    "dietary_info": {
        "vegetarian": True,
        "vegan": False,
        "gluten_free": True,
        "dairy": True,
        "allergens": ["dairy", "tree nuts (pine nuts)"],
        "religious": ["Kosher-friendly", "Halal-friendly", "Vegetarian"]
    }
})

# 3. SPANISH - PAELLA
ALL_RECIPES.append({
    "recipe_name": {
        "en": "Vegetarian Paneer Paella",
        "es": "Paella Vegetariana con Paneer"
    },
    "cuisine": "Spanish",
    "cuisine_code": "spanish",
    "language": "Spanish",
    "language_code": "es-ES",
    "servings": 4,
    "total_time_minutes": 45,
    "prep_time_minutes": 15,
    "cook_time_minutes": 30,
    "difficulty": "intermediate",
    "ingredients": [
        {"item": "paneer", "amount": "350", "unit": "g", "notes": "cubed and seared"},
        {"item": "tomatoes", "amount": "4", "unit": "medium", "notes": "grated"},
        {"item": "bomba or Valencia rice", "amount": "1.5", "unit": "cups", "notes": ""},
        {"item": "onion", "amount": "1", "unit": "large", "notes": "finely diced"},
        {"item": "bell peppers", "amount": "2", "unit": "medium", "notes": "red and yellow, strips"},
        {"item": "saffron threads", "amount": "1", "unit": "pinch", "notes": ""},
        {"item": "smoked paprika", "amount": "1", "unit": "tsp", "notes": ""},
        {"item": "olive oil", "amount": "4", "unit": "tbsp", "notes": ""},
        {"item": "vegetable broth", "amount": "3", "unit": "cups", "notes": "hot"},
        {"item": "garlic", "amount": "4", "unit": "cloves", "notes": "minced"}
    ],
    "instructions": {
        "en": [
            "Heat 2 tbsp olive oil in paella pan over medium-high heat. Sear paneer cubes until golden (4 minutes). Remove and set aside.",
            "In same pan, add remaining oil. Sauté onion and garlic until soft (5 minutes).",
            "Add grated tomatoes and cook, stirring, until reduced and thickened (8-10 minutes). This is the sofrito.",
            "Stir in smoked paprika. Add rice and coat well with sofrito, toasting for 2 minutes.",
            "Add hot broth infused with saffron. Arrange bell pepper strips on top. DO NOT STIR from this point.",
            "Cook over medium heat for 15 minutes without stirring. Liquid should be absorbing.",
            "Arrange seared paneer pieces on top. Cook 5 more minutes.",
            "Increase heat to high for final 2 minutes to create socarrat (crispy bottom layer).",
            "Remove from heat. Cover with foil and let rest 5 minutes.",
            "Serve directly from pan with lemon wedges and aioli."
        ],
        "es": [
            "Calentar 2 cucharadas de aceite de oliva en paellera a fuego medio-alto. Dorar cubos de paneer hasta que estén dorados (4 minutos). Retirar y reservar.",
            "En la misma sartén, añadir el aceite restante. Sofreír cebolla y ajo hasta que estén tiernos (5 minutos).",
            "Añadir tomates rallados y cocinar, removiendo, hasta reducir y espesar (8-10 minutos). Este es el sofrito.",
            "Incorporar pimentón ahumado. Añadir arroz y mezclar bien con sofrito, tostando 2 minutos.",
            "Añadir caldo caliente infusionado con azafrán. Colocar tiras de pimiento encima. NO REMOVER desde este punto.",
            "Cocinar a fuego medio durante 15 minutos sin remover. El líquido debe absorberse.",
            "Colocar piezas de paneer dorado encima. Cocinar 5 minutos más.",
            "Aumentar fuego alto durante 2 minutos finales para crear socarrat (capa crujiente del fondo).",
            "Retirar del fuego. Cubrir con papel aluminio y dejar reposar 5 minutos.",
            "Servir directamente de la paellera con gajos de limón y alioli."
        ]
    },
    "nutrition": {
        "calories_kcal": 445,
        "protein_g": 20,
        "carbohydrates_g": 54,
        "fat_g": 15,
        "fiber_g": 5,
        "vitamin_a_iu": 1200,
        "vitamin_c_mg": 85
    },
    "health_benefits": {
        "paneer": "Complete protein with all essential amino acids",
        "tomato": "Concentrated lycopene from slow cooking, vitamins A and C",
        "rice": "Spanish short-grain rice provides slow-release energy",
        "onion": "Sulfur compounds support liver detoxification"
    },
    "tips": [
        "Never stir paella after adding liquid - this keeps rice grains separated",
        "Socarrat is the prized crispy bottom - listen for crackling sound",
        "Use wide, shallow pan for even cooking and maximum socarrat",
        "Bomba rice is ideal but Arborio can substitute in pinch",
        "Let paella rest covered - rice continues absorbing flavors"
    ],
    "cultural_context": {
        "origin": "Valencian rice dish, vegetarian adaptation",
        "occasions": "Sunday lunch tradition, outdoor gatherings",
        "serving_suggestions": "Serve family-style from the pan with sangria"
    },
    "dietary_info": {
        "vegetarian": True,
        "vegan": False,
        "gluten_free": True,
        "dairy": True,
        "allergens": ["dairy"],
        "religious": ["Vegetarian", "Halal-compatible"]
    }
})

# 4. PERSIAN - MORASA POLO
ALL_RECIPES.append({
    "recipe_name": {
        "en": "Jeweled Rice with Paneer (Morasa Polo)",
        "fa": "مرصع پلو با پنیر"
    },
    "cuisine": "Persian",
    "cuisine_code": "persian",
    "language": "Farsi",
    "language_code": "fa-IR",
    "servings": 4,
    "total_time_minutes": 70,
    "prep_time_minutes": 25,
    "cook_time_minutes": 45,
    "difficulty": "advanced",
    "ingredients": [
        {"item": "basmati rice", "amount": "2", "unit": "cups", "notes": "soaked 2 hours"},
        {"item": "paneer", "amount": "300", "unit": "g", "notes": "cubed"},
        {"item": "tomatoes", "amount": "2", "unit": "medium", "notes": "dried or fresh, diced"},
        {"item": "onion", "amount": "2", "unit": "large", "notes": "thinly sliced for caramelizing"},
        {"item": "barberries", "amount": "1/2", "unit": "cup", "notes": "zereshk"},
        {"item": "pistachios", "amount": "1/3", "unit": "cup", "notes": "slivered"},
        {"item": "almonds", "amount": "1/3", "unit": "cup", "notes": "slivered"},
        {"item": "orange zest", "amount": "2", "unit": "tbsp", "notes": "fresh"},
        {"item": "saffron", "amount": "1/2", "unit": "tsp", "notes": "ground, steeped in hot water"},
        {"item": "butter", "amount": "4", "unit": "tbsp", "notes": "for tahdig"}
    ],
    "instructions": {
        "en": [
            "Boil 8 cups salted water. Add soaked rice, parboil for 6 minutes until al dente. Drain.",
            "In large pot, melt 2 tbsp butter with 2 tbsp water. Add thin layer of rice for tahdig (crispy crust). Cook 3 minutes.",
            "Meanwhile, caramelize sliced onions in separate pan with 1 tbsp butter until deep golden (20 minutes). Set aside.",
            "Sauté paneer cubes until lightly golden. Set aside.",
            "Rinse barberries, sauté briefly in butter with 1 tsp sugar. Set aside.",
            "Layer rice in pyramid shape: rice → paneer → barberries → pistachios → almonds → orange zest → caramelized onions → rice. Repeat layers.",
            "Drizzle saffron water over rice. Pour melted butter on top.",
            "Wrap pot lid with kitchen towel. Cover tightly and cook on low heat for 35-40 minutes.",
            "Turn off heat. Let stand 5 minutes. Place serving platter upside down on pot and flip to show golden tahdig.",
            "Garnish with extra nuts and barberries. Serve with yogurt and herb salad (sabzi)."
        ],
        "fa": [
            "8 لیوان آب نمکی را به جوش بیاورید. برنج خیسانده را اضافه کنید، 6 دقیقه بپزید تا نیم‌پز شود. آبکش کنید.",
            "در قابلمه بزرگ، 2 قاشق غذاخوری کره با 2 قاشق آب آب کنید. یک لایه نازک برنج برای ته دیگ بگذارید. 3 دقیقه بپزید.",
            "در همین حین، پیاز نگینی را در تابه جداگانه با 1 قاشق کره تا طلایی تیره کاراملیزه کنید (20 دقیقه). کنار بگذارید.",
            "مکعب‌های پنیر را تا کمی طلایی تفت دهید. کنار بگذارید.",
            "زرشک‌ها را بشویید، در کره با 1 قاشق چایخوری شکر سریع تفت دهید. کنار بگذارید.",
            "برنج را به شکل هرمی لایه‌بندی کنید: برنج ← پنیر ← زرشک ← پسته ← بادام ← پوست پرتقال ← پیاز کاراملیزه ← برنج. لایه‌ها را تکرار کنید.",
            "آب زعفران را روی برنج بپاشید. کره آب شده را روی آن بریزید.",
            "درب قابلمه را با دستمال آشپزخانه بپیچید. محکم بپوشانید و روی حرارت کم 35-40 دقیقه بپزید.",
            "حرارت را خاموش کنید. 5 دقیقه بگذارید. بشقاب سرو را وارونه روی قابلمه بگذارید و برگردانید تا ته دیگ طلایی نمایان شود.",
            "با آجیل و زرشک اضافی تزیین کنید. با ماست و سبزی خوردن سرو کنید."
        ]
    },
    "nutrition": {
        "calories_kcal": 510,
        "protein_g": 19,
        "carbohydrates_g": 65,
        "fat_g": 20,
        "fiber_g": 5,
        "vitamin_c_mg": 28,
        "iron_mg": 2.8
    },
    "health_benefits": {
        "paneer": "High-protein dairy providing essential amino acids and calcium",
        "tomato": "Lycopene and potassium for heart health",
        "rice": "Aromatic basmati with lower glycemic index than other rice varieties",
        "onion": "Caramelization concentrates flavonoids and natural sweetness"
    },
    "tips": [
        "Soak rice at least 2 hours for fluffy, separated grains",
        "Tahdig requires patience - don't rush the crispy crust formation",
        "Barberries are traditional but cranberries can substitute",
        "Steam-dry technique prevents mushy rice",
        "Kitchen towel under lid absorbs steam perfectly"
    ],
    "cultural_context": {
        "origin": "Persian celebration dish for weddings and Nowruz",
        "occasions": "Weddings, Nowruz (Persian New Year), special celebrations",
        "serving_suggestions": "Serve with mast-o-khiar (yogurt cucumber) and torshi (pickles)"
    },
    "dietary_info": {
        "vegetarian": True,
        "vegan": False,
        "gluten_free": True,
        "dairy": True,
        "allergens": ["dairy", "tree nuts"],
        "religious": ["Halal", "Kosher-compatible"]
    }
})

# 5. MEXICAN - ARROZ ROJO
ALL_RECIPES.append({
    "recipe_name": {
        "en": "Mexican Red Rice with Grilled Paneer",
        "es": "Arroz Rojo con Paneer Asado"
    },
    "cuisine": "Mexican",
    "cuisine_code": "mexican",
    "language": "Spanish (Mexican)",
    "language_code": "es-MX",
    "servings": 4,
    "total_time_minutes": 40,
    "prep_time_minutes": 15,
    "cook_time_minutes": 25,
    "difficulty": "intermediate",
    "ingredients": [
        {"item": "paneer", "amount": "350", "unit": "g", "notes": "marinated with chipotle"},
        {"item": "long-grain rice", "amount": "1.5", "unit": "cups", "notes": ""},
        {"item": "tomatoes", "amount": "4", "unit": "large", "notes": "for blending"},
        {"item": "onion", "amount": "1", "unit": "medium", "notes": "quartered for blending"},
        {"item": "garlic", "amount": "3", "unit": "cloves", "notes": ""},
        {"item": "jalapeño", "amount": "1", "unit": "medium", "notes": "seeded"},
        {"item": "vegetable oil", "amount": "3", "unit": "tbsp", "notes": ""},
        {"item": "cumin", "amount": "1", "unit": "tsp", "notes": "ground"},
        {"item": "vegetable broth", "amount": "2", "unit": "cups", "notes": ""},
        {"item": "cilantro", "amount": "1/4", "unit": "cup", "notes": "fresh, chopped"}
    ],
    "instructions": {
        "en": [
            "Marinate paneer cubes with chipotle powder, lime juice, and salt for 15 minutes.",
            "Toast rice in dry skillet over medium heat, stirring constantly until golden and nutty (5-6 minutes). Set aside.",
            "Blend tomatoes, onion, garlic, and jalapeño until smooth.",
            "Heat oil in large saucepan. Add toasted rice and fry for 2 minutes, stirring constantly.",
            "Add blended tomato sauce carefully (it will splatter). Stir well.",
            "Add cumin, salt, and vegetable broth. Stir once, bring to boil.",
            "Reduce heat to low, cover, and simmer for 20 minutes without stirring.",
            "Meanwhile, grill or pan-sear marinated paneer until charred edges (3 minutes per side).",
            "Fluff rice with fork. Fold in half the cilantro.",
            "Serve rice topped with grilled paneer, remaining cilantro, lime wedges, and sliced avocado."
        ],
        "es": [
            "Marine los cubos de paneer con chile chipotle en polvo, jugo de limón y sal durante 15 minutos.",
            "Tueste el arroz en sartén seca a fuego medio, revolviendo constantemente hasta que esté dorado y aromático (5-6 minutos). Reserve.",
            "Licúe los tomates, cebolla, ajo y jalapeño hasta que quede suave.",
            "Caliente el aceite en cacerola grande. Agregue el arroz tostado y fría por 2 minutos, revolviendo constantemente.",
            "Agregue la salsa de tomate licuada con cuidado (salpicará). Mezcle bien.",
            "Agregue comino, sal y caldo de verduras. Revuelva una vez, deje hervir.",
            "Reduzca el fuego a bajo, tape y cocine a fuego lento durante 20 minutos sin revolver.",
            "Mientras tanto, ase o dore en sartén el paneer marinado hasta que los bordes estén carbonizados (3 minutos por lado).",
            "Esponje el arroz con tenedor. Incorpore la mitad del cilantro.",
            "Sirva el arroz cubierto con paneer asado, cilantro restante, gajos de limón y aguacate en rodajas."
        ]
    },
    "nutrition": {
        "calories_kcal": 425,
        "protein_g": 21,
        "carbohydrates_g": 56,
        "fat_g": 14,
        "fiber_g": 4,
        "vitamin_c_mg": 42,
        "potassium_mg": 480
    },
    "health_benefits": {
        "paneer": "Protein-rich vegetarian option, supports muscle maintenance",
        "tomato": "Rich in vitamin C and lycopene, supports immune system",
        "rice": "Provides sustained energy from complex carbohydrates",
        "onion": "Contains allicin with antimicrobial properties"
    },
    "tips": [
        "Toasting rice is essential for authentic flavor and texture",
        "Use long-grain rice (not short-grain) for fluffy results",
        "Chipotle in adobo sauce works great for marinade",
        "Don't skip the toasting step - it prevents mushy rice",
        "Rice should absorb all liquid - if wet, cook uncovered 2-3 more minutes"
    ],
    "cultural_context": {
        "origin": "Mexican staple side dish, adapted with paneer protein",
        "occasions": "Daily meals, celebrations, taco nights",
        "serving_suggestions": "Serve with black beans, salsa, and warm tortillas"
    },
    "dietary_info": {
        "vegetarian": True,
        "vegan": False,
        "gluten_free": True,
        "dairy": True,
        "allergens": ["dairy"],
        "religious": ["Vegetarian", "Halal-compatible"]
    }
})

# 6. KOREAN - KIMCHI FRIED RICE
ALL_RECIPES.append({
    "recipe_name": {
        "en": "Paneer Kimchi Fried Rice",
        "ko": "파니르 김치 볶음밥"
    },
    "cuisine": "Korean Fusion",
    "cuisine_code": "korean",
    "language": "Korean",
    "language_code": "ko-KR",
    "servings": 4,
    "total_time_minutes": 25,
    "prep_time_minutes": 10,
    "cook_time_minutes": 15,
    "difficulty": "intermediate",
    "ingredients": [
        {"item": "paneer", "amount": "300", "unit": "g", "notes": "cubed, pan-fried crispy"},
        {"item": "cooked rice", "amount": "4", "unit": "cups", "notes": "day-old, cold"},
        {"item": "kimchi", "amount": "1", "unit": "cup", "notes": "chopped, well-fermented"},
        {"item": "onion", "amount": "1", "unit": "medium", "notes": "diced"},
        {"item": "tomato", "amount": "2", "unit": "medium", "notes": "diced"},
        {"item": "gochugaru", "amount": "1", "unit": "tbsp", "notes": "Korean red pepper flakes"},
        {"item": "sesame oil", "amount": "2", "unit": "tbsp", "notes": ""},
        {"item": "soy sauce", "amount": "2", "unit": "tbsp", "notes": ""},
        {"item": "kimchi juice", "amount": "2", "unit": "tbsp", "notes": "from jar"},
        {"item": "green onions", "amount": "2", "unit": "stalks", "notes": "chopped"}
    ],
    "instructions": {
        "en": [
            "Pan-fry paneer cubes in 1 tbsp sesame oil until golden and crispy on all sides (5-6 minutes). Set aside.",
            "Heat wok or large skillet on high heat until smoking hot. Add 1 tbsp sesame oil.",
            "Add diced onion, stir-fry for 1 minute until edges start to char.",
            "Add chopped kimchi, stir-fry vigorously for 2 minutes. The heat brings out wok hei (breath of wok).",
            "Add diced tomatoes, cook for 1 minute until slightly softened.",
            "Add cold rice, breaking up clumps with spatula. Toss continuously for 3-4 minutes.",
            "Add soy sauce, kimchi juice, and gochugaru. Toss to coat evenly.",
            "Create well in center, crack in egg (optional for non-vegan). Scramble then mix with rice.",
            "Fold in crispy paneer cubes. Toss for 1 minute.",
            "Remove from heat. Garnish with chopped green onions and sesame seeds. Serve immediately with fried egg on top."
        ],
        "ko": [
            "참기름 1큰술에 파니르 큐브를 모든 면이 노릇하고 바삭해질 때까지 볶습니다 (5-6분). 따로 두세요.",
            "웬이나 큰 프라이팬을 연기 날 때까지 아주 센 불로 달굽니다. 참기름 1큰술을 넣습니다.",
            "다진 양파를 넣고 가장자리가 타기 시작할 때까지 1분간 볶습니다.",
            "썬 김치를 넣고 2분간 세게 볶습니다. 높은 열이 웍의 숨결(웍 헤이)을 만듭니다.",
            "깍둑썬 토마토를 넣고 약간 부드러워질 때까지 1분간 익힙니다.",
            "찬 밥을 넣고 주걱으로 덩어리를 부수면서 3-4분간 계속 볶습니다.",
            "간장, 김치국물, 고춧가루를 넣습니다. 고루 섞이도록 볶습니다.",
            "가운데 공간을 만들고 계란을 깨뜨려 넣습니다 (비건이 아닌 경우). 스크램블한 후 밥과 섞습니다.",
            "바삭한 파니르 큐브를 넣습니다. 1분간 볶습니다.",
            "불에서 내립니다. 썬 파와 참깨로 장식합니다. 위에 계란 프라이를 올려 바로 드세요."
        ]
    },
    "nutrition": {
        "calories_kcal": 465,
        "protein_g": 22,
        "carbohydrates_g": 58,
        "fat_g": 17,
        "fiber_g": 3,
        "vitamin_c_mg": 28,
        "probiotics_cfu": "5 billion (from kimchi)"
    },
    "health_benefits": {
        "paneer": "High protein content supports satiety and muscle health",
        "tomato": "Vitamin C and antioxidants boost immune function",
        "rice": "Day-old rice contains resistant starch, beneficial for gut health",
        "onion": "Prebiotic fibers feed beneficial gut bacteria"
    },
    "tips": [
        "Use day-old refrigerated rice - fresh rice becomes mushy",
        "Wok must be very hot for proper wok hei (smoky flavor)",
        "Well-fermented kimchi has best flavor - check for sour taste",
        "Move rice constantly to prevent sticking and ensure even heating",
        "Gochugaru (Korean pepper flakes) can't be substituted with regular chili flakes"
    ],
    "cultural_context": {
        "origin": "Korean comfort food, fusion adaptation with paneer",
        "occasions": "Quick meals, late-night snacks, using leftover rice",
        "serving_suggestions": "Serve with Korean banchan (side dishes) and gim (seaweed)"
    },
    "dietary_info": {
        "vegetarian": True,
        "vegan": False,
        "gluten_free": False,
        "dairy": True,
        "allergens": ["dairy", "soy", "sesame"],
        "religious": ["Buddhist-friendly", "Vegetarian"]
    }
})

# 7. ITALIAN - RISOTTO
ALL_RECIPES.append({
    "recipe_name": {
        "en": "Tomato Risotto with Paneer",
        "it": "Risotto al Pomodoro con Paneer"
    },
    "cuisine": "Italian",
    "cuisine_code": "italian",
    "language": "Italian",
    "language_code": "it-IT",
    "servings": 4,
    "total_time_minutes": 35,
    "prep_time_minutes": 10,
    "cook_time_minutes": 25,
    "difficulty": "advanced",
    "ingredients": [
        {"item": "arborio rice", "amount": "1.5", "unit": "cups", "notes": "short-grain Italian rice"},
        {"item": "paneer", "amount": "250", "unit": "g", "notes": "cubed"},
        {"item": "tomatoes", "amount": "4", "unit": "large", "notes": "peeled, diced"},
        {"item": "onion", "amount": "1", "unit": "small", "notes": "finely minced"},
        {"item": "white wine", "amount": "1/2", "unit": "cup", "notes": "dry"},
        {"item": "vegetable broth", "amount": "5", "unit": "cups", "notes": "kept simmering"},
        {"item": "olive oil", "amount": "3", "unit": "tbsp", "notes": "extra virgin"},
        {"item": "butter", "amount": "2", "unit": "tbsp", "notes": "for mantecatura"},
        {"item": "parmesan", "amount": "1/2", "unit": "cup", "notes": "grated (or skip for dairy-free)"},
        {"item": "fresh basil", "amount": "10", "unit": "leaves", "notes": ""}
    ],
    "instructions": {
        "en": [
            "Keep vegetable broth simmering in separate pot. This is crucial for proper risotto.",
            "Heat olive oil in large, heavy-bottomed pan. Sauté paneer cubes until golden (4 minutes). Remove and set aside.",
            "In same pan, add 1 tbsp butter. Sauté finely minced onion until translucent but not browned (3-4 minutes).",
            "Add arborio rice. Toast for 2 minutes, stirring constantly until edges become translucent.",
            "Pour in white wine. Stir until wine is completely absorbed.",
            "Add diced tomatoes. Cook for 2 minutes until tomatoes begin to break down.",
            "Begin adding hot broth one ladle at a time. Stir frequently and wait until liquid is absorbed before adding next ladle. This process takes 18-20 minutes.",
            "Taste rice after 18 minutes. It should be al dente (slight bite in center). Add paneer cubes back in.",
            "Remove from heat. Add remaining butter and parmesan. Stir vigorously for mantecatura (creates creaminess without cream).",
            "Let rest 1 minute. Serve immediately garnished with torn basil leaves and extra parmesan."
        ],
        "it": [
            "Tenere il brodo vegetale sobbollente in una pentola separata. Questo è fondamentale per un risotto perfetto.",
            "Scaldare l'olio d'oliva in una padella larga e dal fondo spesso. Rosolare i cubetti di paneer fino a dorarli (4 minuti). Togliere e mettere da parte.",
            "Nella stessa padella, aggiungere 1 cucchiaio di burro. Soffriggere la cipolla tritata finemente fino a renderla trasparente ma non dorata (3-4 minuti).",
            "Aggiungere il riso arborio. Tostare per 2 minuti, mescolando continuamente finché i bordi diventano traslucidi.",
            "Versare il vino bianco. Mescolare fino a quando il vino è completamente assorbito.",
            "Aggiungere i pomodori a dadini. Cuocere per 2 minuti fino a quando i pomodori iniziano a scomporsi.",
            "Iniziare ad aggiungere il brodo caldo un mestolo alla volta. Mescolare frequentemente e attendere che il liquido sia assorbito prima di aggiungere il mestolo successivo. Questo processo richiede 18-20 minuti.",
            "Assaggiare il riso dopo 18 minuti. Dovrebbe essere al dente (leggermente croccante al centro). Rimettere i cubetti di paneer.",
            "Togliere dal fuoco. Aggiungere il burro rimanente e il parmigiano. Mescolare vigorosamente per la mantecatura (crea cremosità senza panna).",
            "Lasciare riposare 1 minuto. Servire immediatamente guarnito con foglie di basilico strappate e parmigiano extra."
        ]
    },
    "nutrition": {
        "calories_kcal": 455,
        "protein_g": 19,
        "carbohydrates_g": 62,
        "fat_g": 14,
        "fiber_g": 3,
        "calcium_mg": 340,
        "vitamin_a_iu": 850
    },
    "health_benefits": {
        "paneer": "Provides complete protein and calcium for bone health",
        "tomato": "Fresh tomatoes provide vitamin C and lycopene",
        "rice": "Arborio rice's high starch content creates naturally creamy texture without heavy cream",
        "onion": "Mild cooking preserves beneficial sulfur compounds"
    },
    "tips": [
        "Never rush risotto - the 18-20 minute stirring process cannot be shortened",
        "Broth MUST be kept hot - cold broth stops cooking process",
        "Mantecatura (vigorous final stirring) is what makes risotto creamy, not cream",
        "Wine must be fully absorbed before adding broth",
        "Risotto should flow slowly when tilted on plate (all'onda - like a wave)"
    ],
    "cultural_context": {
        "origin": "Northern Italian classic from Lombardy region",
        "occasions": "Primi piatti (first course), Sunday family lunches",
        "serving_suggestions": "Serve as first course before protein, with crusty bread"
    },
    "dietary_info": {
        "vegetarian": True,
        "vegan": False,
        "gluten_free": True,
        "dairy": True,
        "allergens": ["dairy"],
        "religious": ["Vegetarian", "Halal-compatible"]
    }
})

# Generate the complete markdown file
def create_complete_recipe_markdown():
    output = []
    
    output.append("# SAVO Multi-Cuisine Recipes - Complete Collection")
    output.append("\n**Generated by:** SAVO Ingredient Intelligence System")
    output.append(f"\n**Ingredients:** {', '.join(INGREDIENTS)}")
    output.append("\n**Cooking Level:** Intermediate to Advanced")
    output.append("\n**Total Recipes:** 7 (with bilingual instructions)")
    output.append("\n\n" + "="*80 + "\n")
    
    for idx, recipe in enumerate(ALL_RECIPES, 1):
        output.append(f"\n## {idx}. {recipe['recipe_name']['en']}")
        
        # Get native language name
        native_lang = [k for k in recipe['recipe_name'].keys() if k != 'en'][0]
        output.append(f"\n### {recipe['recipe_name'][native_lang]}")
        
        output.append(f"\n**Cuisine:** {recipe['cuisine']}")
        output.append(f"\n**Language:** {recipe['language']} + English")
        output.append(f"\n**Difficulty:** {recipe['difficulty'].title()}")
        output.append(f"\n**Time:** {recipe['total_time_minutes']} minutes (Prep: {recipe['prep_time_minutes']}min, Cook: {recipe['cook_time_minutes']}min)")
        output.append(f"\n**Servings:** {recipe['servings']}")
        
        # Ingredients
        output.append("\n\n### Ingredients")
        for ing in recipe['ingredients']:
            notes = f" ({ing['notes']})" if ing['notes'] else ""
            output.append(f"\n- **{ing['item'].title()}:** {ing['amount']} {ing['unit']}{notes}")
        
        # Instructions in English
        output.append("\n\n### Instructions (English)")
        for i, step in enumerate(recipe['instructions']['en'], 1):
            output.append(f"\n{i}. {step}")
        
        # Instructions in native language
        native_lang_name = recipe['language']
        output.append(f"\n\n### Instructions ({native_lang_name})")
        for i, step in enumerate(recipe['instructions'][native_lang], 1):
            output.append(f"\n{i}. {step}")
        
        # Nutrition
        output.append("\n\n### Nutrition (Per Serving)")
        for key, value in recipe['nutrition'].items():
            label = key.replace('_', ' ').title()
            output.append(f"\n- **{label}:** {value}")
        
        # Health Benefits
        output.append("\n\n### Health Benefits")
        for ingredient, benefit in recipe['health_benefits'].items():
            output.append(f"\n- **{ingredient.title()}:** {benefit}")
        
        # Chef's Tips
        output.append("\n\n### Chef's Tips")
        for tip in recipe['tips']:
            output.append(f"\n- {tip}")
        
        # Cultural Context
        output.append("\n\n### Cultural Context")
        output.append(f"\n- **Origin:** {recipe['cultural_context']['origin']}")
        output.append(f"\n- **Occasions:** {recipe['cultural_context']['occasions']}")
        output.append(f"\n- **Serving:** {recipe['cultural_context']['serving_suggestions']}")
        
        # Dietary Info
        output.append("\n\n### Dietary Information")
        output.append(f"\n- **Vegetarian:** {'Yes' if recipe['dietary_info']['vegetarian'] else 'No'}")
        output.append(f"\n- **Vegan:** {'Yes' if recipe['dietary_info']['vegan'] else 'No'}")
        output.append(f"\n- **Gluten-Free:** {'Yes' if recipe['dietary_info']['gluten_free'] else 'No'}")
        output.append(f"\n- **Allergens:** {', '.join(recipe['dietary_info']['allergens'])}")
        output.append(f"\n- **Religious Compatibility:** {', '.join(recipe['dietary_info']['religious'])}")
        
        output.append("\n\n" + "="*80 + "\n")
    
    # Summary table
    output.append("\n## Recipe Summary Comparison\n")
    output.append("\n| Recipe | Cuisine | Time | Calories | Protein | Difficulty |")
    output.append("\n|--------|---------|------|----------|---------|------------|")
    for recipe in ALL_RECIPES:
        output.append(f"\n| {recipe['recipe_name']['en']} | {recipe['cuisine']} | {recipe['total_time_minutes']}min | {recipe['nutrition']['calories_kcal']} kcal | {recipe['nutrition']['protein_g']}g | {recipe['difficulty'].title()} |")
    
    output.append("\n\n" + "="*80)
    output.append("\n\n✅ **All recipes generated by SAVO with complete bilingual instructions!**\n")
    
    return ''.join(output)

# Main execution
if __name__ == "__main__":
    print("="*80)
    print("Generating ALL 7 Multi-Cuisine Recipes with Complete Steps")
    print("="*80)
    print(f"Ingredients: {', '.join(INGREDIENTS)}")
    print(f"Total Recipes: {len(ALL_RECIPES)}")
    print("="*80 + "\n")
    
    # Generate markdown
    markdown_content = create_complete_recipe_markdown()
    
    # Save to file
    output_file = "ALL_RECIPES_COMPLETE.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(markdown_content)
    
    # Also save as JSON
    json_file = "ALL_RECIPES_COMPLETE.json"
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(ALL_RECIPES, f, indent=2, ensure_ascii=False)
    
    print(f"✅ SUCCESS! Generated {len(ALL_RECIPES)} complete recipes\n")
    print(f"📄 Markdown saved to: {output_file}")
    print(f"📄 JSON saved to: {json_file}\n")
    
    print("📊 Recipes Generated:")
    for idx, recipe in enumerate(ALL_RECIPES, 1):
        native_lang = [k for k in recipe['recipe_name'].keys() if k != 'en'][0]
        print(f"  {idx}. {recipe['cuisine']}: {recipe['recipe_name']['en']} / {recipe['recipe_name'][native_lang]}")
    
    print("\n" + "="*80)
    print("✅ All recipes include:")
    print("   • Bilingual instructions (native language + English)")
    print("   • Complete nutrition information")
    print("   • Health benefits for each ingredient")
    print("   • Chef's tips and techniques")
    print("   • Cultural context")
    print("   • Religious/dietary compatibility")
    print("="*80)
