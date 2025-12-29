"""
Cuisine metadata - 10 cuisines with daily/party structures
"""

CUISINE_METADATA = {
    "italian": {
        "name": "Italian",
        "daily_structure": ["Antipasto", "Primo (Pasta/Risotto)", "Secondo (Main)", "Contorno (Side)"],
        "party_structure": ["Antipasti", "Primi", "Secondi", "Contorni", "Dolci"],
        "characteristics": ["pasta", "tomato", "olive oil", "basil", "parmesan"]
    },
    "mexican": {
        "name": "Mexican",
        "daily_structure": ["Appetizer", "Main Course", "Side", "Dessert"],
        "party_structure": ["Antojitos", "Platos Fuertes", "Acompañamientos", "Postres"],
        "characteristics": ["tortilla", "beans", "corn", "chili", "cilantro"]
    },
    "chinese": {
        "name": "Chinese",
        "daily_structure": ["Appetizer", "Main Dish", "Rice/Noodles", "Soup"],
        "party_structure": ["Cold Dishes", "Hot Dishes", "Rice/Noodles", "Soup", "Dessert"],
        "characteristics": ["soy sauce", "ginger", "garlic", "rice", "wok-fried"]
    },
    "indian": {
        "name": "Indian",
        "daily_structure": ["Starter", "Main Curry", "Bread/Rice", "Side"],
        "party_structure": ["Appetizers", "Curries", "Breads", "Rice Dishes", "Desserts"],
        "characteristics": ["curry", "spices", "naan", "rice", "lentils"]
    },
    "japanese": {
        "name": "Japanese",
        "daily_structure": ["Starter", "Main", "Rice", "Soup"],
        "party_structure": ["Appetizers", "Sashimi/Sushi", "Grilled", "Noodles", "Dessert"],
        "characteristics": ["soy", "miso", "rice", "fish", "seaweed"]
    },
    "french": {
        "name": "French",
        "daily_structure": ["Entrée", "Plat Principal", "Fromage", "Dessert"],
        "party_structure": ["Hors d'œuvres", "Entrées", "Plats", "Fromages", "Desserts"],
        "characteristics": ["butter", "wine", "cream", "herbs", "pastry"]
    },
    "mediterranean": {
        "name": "Mediterranean",
        "daily_structure": ["Mezze", "Main", "Salad", "Side"],
        "party_structure": ["Mezze Platter", "Mains", "Salads", "Sides", "Sweets"],
        "characteristics": ["olive oil", "lemon", "garlic", "chickpeas", "feta"]
    },
    "thai": {
        "name": "Thai",
        "daily_structure": ["Appetizer", "Curry/Stir-fry", "Rice", "Soup"],
        "party_structure": ["Appetizers", "Salads", "Curries", "Stir-fries", "Desserts"],
        "characteristics": ["fish sauce", "lime", "chili", "coconut", "lemongrass"]
    },
    "american": {
        "name": "American",
        "daily_structure": ["Starter", "Main Course", "Side Dish", "Dessert"],
        "party_structure": ["Appetizers", "Mains", "Sides", "Salads", "Desserts"],
        "characteristics": ["grilled", "bbq", "burgers", "comfort food", "hearty"]
    },
    "middle_eastern": {
        "name": "Middle Eastern",
        "daily_structure": ["Mezze", "Main", "Rice/Bread", "Salad"],
        "party_structure": ["Cold Mezze", "Hot Mezze", "Grilled Mains", "Rice Dishes", "Sweets"],
        "characteristics": ["tahini", "cumin", "pita", "lamb", "yogurt"]
    }
}


def get_all_cuisines():
    """Get all available cuisines with their structures"""
    return {
        "cuisines": [
            {
                "cuisine_id": cuisine_id,
                "name": data["name"],
                "daily_structure": data["daily_structure"],
                "party_structure": data["party_structure"],
                "characteristics": data["characteristics"]
            }
            for cuisine_id, data in CUISINE_METADATA.items()
        ]
    }


def get_cuisine_by_id(cuisine_id: str):
    """Get specific cuisine metadata"""
    return CUISINE_METADATA.get(cuisine_id)
