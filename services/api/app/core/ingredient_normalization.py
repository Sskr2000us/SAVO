"""
Ingredient Normalization and Similarity Detection
Handles canonical name mapping, fuzzy matching, and close ingredient suggestions
"""

from typing import List, Dict, Optional, Set
from difflib import SequenceMatcher
from decimal import Decimal
import re


class IngredientNormalizer:
    """Normalize ingredient names and find similar ingredients"""
    
    # Visual similarity groups (from VISION_SCANNING_ARCHITECTURE.md)
    VISUAL_SIMILARITY_GROUPS = {
        "leafy_greens": {
            "ingredients": ["spinach", "kale", "lettuce", "arugula", "chard", "collard_greens", "mustard_greens"],
            "description": "Dark leafy vegetables that look similar"
        },
        "root_vegetables": {
            "ingredients": ["potato", "sweet_potato", "yam", "carrot", "parsnip", "turnip", "rutabaga"],
            "description": "Underground vegetables with similar shapes"
        },
        "alliums": {
            "ingredients": ["onion", "shallot", "leek", "scallion", "green_onion", "spring_onion"],
            "description": "Onion family members"
        },
        "bell_peppers": {
            "ingredients": ["red_pepper", "green_pepper", "yellow_pepper", "orange_pepper"],
            "description": "Different colored bell peppers"
        },
        "dairy_liquids": {
            "ingredients": ["whole_milk", "2%_milk", "skim_milk", "buttermilk", "half_and_half", "heavy_cream"],
            "description": "Liquid dairy products"
        },
        "cooking_oils": {
            "ingredients": ["vegetable_oil", "canola_oil", "olive_oil", "sunflower_oil", "avocado_oil"],
            "description": "Liquid cooking oils"
        },
        "beans_legumes": {
            "ingredients": ["black_beans", "pinto_beans", "kidney_beans", "chickpeas", "lentils"],
            "description": "Dried or canned legumes"
        },
        "cheese_blocks": {
            "ingredients": ["cheddar", "mozzarella", "monterey_jack", "swiss", "provolone"],
            "description": "Block or sliced cheeses"
        },
        "berries": {
            "ingredients": ["strawberry", "blueberry", "raspberry", "blackberry"],
            "description": "Small soft fruits"
        },
        "citrus": {
            "ingredients": ["lemon", "lime", "orange", "grapefruit"],
            "description": "Citrus fruits"
        }
    }
    
    # Canonical name mapping (normalize variations)
    CANONICAL_NAMES = {
        # Dairy variations
        "whole milk": "milk",
        "2% milk": "milk",
        "skim milk": "milk",
        "fat-free milk": "milk",
        
        # Onion variations
        "yellow onion": "onion",
        "white onion": "onion",
        "red onion": "onion",
        "green onion": "scallion",
        "spring onion": "scallion",
        
        # Pepper variations
        "red bell pepper": "bell_pepper",
        "green bell pepper": "bell_pepper",
        "yellow bell pepper": "bell_pepper",
        "orange bell pepper": "bell_pepper",
        
        # Herb variations
        "cilantro": "coriander_leaves",
        "coriander": "coriander_leaves",
        "fresh cilantro": "coriander_leaves",
        
        # Tomato variations
        "roma tomato": "tomato",
        "cherry tomato": "cherry_tomatoes",
        "grape tomato": "cherry_tomatoes",
        "plum tomato": "tomato",
        
        # Potato variations
        "russet potato": "potato",
        "yukon gold potato": "potato",
        "red potato": "potato",
        
        # Oil variations
        "extra virgin olive oil": "olive_oil",
        "evoo": "olive_oil",
        
        # Common substitutions
        "zucchini": "zucchini",
        "courgette": "zucchini",
        "eggplant": "eggplant",
        "aubergine": "eggplant",
    }
    
    # Category mapping for nutritional balance
    INGREDIENT_CATEGORIES = {
        "protein": [
            "chicken", "beef", "pork", "lamb", "fish", "salmon", "tuna", "shrimp",
            "tofu", "tempeh", "eggs", "paneer", "chickpeas", "lentils", "beans"
        ],
        "vegetable": [
            "spinach", "broccoli", "carrot", "tomato", "onion", "garlic", "bell_pepper",
            "zucchini", "eggplant", "cauliflower", "cabbage", "kale", "lettuce"
        ],
        "fruit": [
            "apple", "banana", "orange", "lemon", "lime", "mango", "strawberry",
            "blueberry", "avocado", "tomato"
        ],
        "grain": [
            "rice", "pasta", "bread", "quinoa", "couscous", "oats", "wheat", "flour"
        ],
        "dairy": [
            "milk", "cheese", "butter", "yogurt", "cream", "paneer", "ghee"
        ],
        "spice": [
            "salt", "pepper", "cumin", "coriander", "turmeric", "paprika", "chili",
            "garam_masala", "curry_powder", "garlic_powder", "onion_powder"
        ],
        "condiment": [
            "soy_sauce", "ketchup", "mustard", "mayo", "vinegar", "hot_sauce",
            "worcestershire", "sriracha"
        ],
        "oil": [
            "olive_oil", "vegetable_oil", "coconut_oil", "sesame_oil", "butter", "ghee"
        ]
    }
    
    def normalize_name(self, ingredient_name: str) -> str:
        """
        Normalize ingredient name to canonical form
        
        Args:
            ingredient_name: Raw ingredient name
            
        Returns:
            Canonical name (lowercase, underscored)
        """
        # Clean up name
        name = ingredient_name.lower().strip()
        
        # Remove common descriptors
        descriptors = [
            "fresh", "frozen", "canned", "dried", "raw", "cooked",
            "sliced", "diced", "chopped", "minced", "whole",
            "large", "small", "medium"
        ]
        for descriptor in descriptors:
            name = re.sub(rf'\b{descriptor}\b', '', name).strip()
        
        # Check if we have a canonical mapping
        if name in self.CANONICAL_NAMES:
            return self.CANONICAL_NAMES[name]
        
        # Convert spaces and hyphens to underscores
        name = name.replace(" ", "_").replace("-", "_")
        
        # Remove special characters except underscores
        name = re.sub(r'[^a-z0-9_]', '', name)
        
        return name
    
    def get_visual_similarity_group(self, ingredient_name: str) -> Optional[str]:
        """
        Get the visual similarity group for an ingredient
        
        Args:
            ingredient_name: Normalized ingredient name
            
        Returns:
            Group name or None
        """
        ingredient_lower = ingredient_name.lower().replace("_", " ")
        
        for group_name, group_data in self.VISUAL_SIMILARITY_GROUPS.items():
            for item in group_data["ingredients"]:
                if item.replace("_", " ") in ingredient_lower or ingredient_lower in item.replace("_", " "):
                    return group_name
        
        return None
    
    def get_close_ingredients(
        self,
        ingredient_name: str,
        user_preferences: Optional[Dict] = None,
        limit: int = 5
    ) -> List[Dict]:
        """
        Get close/similar ingredients for user selection
        
        Args:
            ingredient_name: Detected ingredient name
            user_preferences: User profile for context-aware filtering
            limit: Maximum number of suggestions
            
        Returns:
            List of {name, display_name, likelihood, reason, allergen_safe}
        """
        suggestions = []
        
        # Strategy 1: Same visual similarity group
        similarity_group = self.get_visual_similarity_group(ingredient_name)
        if similarity_group:
            group_data = self.VISUAL_SIMILARITY_GROUPS[similarity_group]
            for item in group_data["ingredients"]:
                if item != ingredient_name:
                    suggestions.append({
                        "name": item,
                        "display_name": item.replace("_", " ").title(),
                        "likelihood": "high",
                        "reason": f"Visually similar ({group_data['description'].lower()})",
                        "strategy": "visual_group"
                    })
        
        # Strategy 2: Fuzzy text matching
        fuzzy_matches = self._fuzzy_match_ingredients(ingredient_name, limit=10)
        for match in fuzzy_matches:
            # Avoid duplicates
            if not any(s["name"] == match["name"] for s in suggestions):
                suggestions.append({
                    **match,
                    "strategy": "fuzzy_match"
                })
        
        # Strategy 3: Category-based suggestions
        category = self.get_ingredient_category(ingredient_name)
        if category:
            category_items = self.INGREDIENT_CATEGORIES.get(category, [])
            for item in category_items:
                if item != ingredient_name and not any(s["name"] == item for s in suggestions):
                    suggestions.append({
                        "name": item,
                        "display_name": item.replace("_", " ").title(),
                        "likelihood": "medium",
                        "reason": f"Same category ({category})",
                        "strategy": "category"
                    })
        
        # Filter by user preferences if provided
        if user_preferences:
            suggestions = self._filter_by_preferences(suggestions, user_preferences)
        
        # Rank suggestions
        ranked = self._rank_suggestions(
            suggestions,
            ingredient_name,
            user_preferences
        )
        
        return ranked[:limit]
    
    def _fuzzy_match_ingredients(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Find ingredients with similar names using fuzzy matching
        """
        matches = []
        
        # Get all known ingredients
        all_ingredients = set()
        for category, items in self.INGREDIENT_CATEGORIES.items():
            all_ingredients.update(items)
        for group_data in self.VISUAL_SIMILARITY_GROUPS.values():
            all_ingredients.update(group_data["ingredients"])
        
        # Calculate similarity scores
        for ingredient in all_ingredients:
            if ingredient == query:
                continue
            
            # Use SequenceMatcher for fuzzy matching
            similarity = SequenceMatcher(None, query.lower(), ingredient.lower()).ratio()
            
            if similarity > 0.5:  # Threshold for relevance
                matches.append({
                    "name": ingredient,
                    "display_name": ingredient.replace("_", " ").title(),
                    "likelihood": "high" if similarity > 0.75 else "medium",
                    "reason": f"Name similarity ({int(similarity * 100)}% match)",
                    "similarity_score": similarity
                })
        
        # Sort by similarity
        matches.sort(key=lambda x: x["similarity_score"], reverse=True)
        
        return matches[:limit]
    
    def get_ingredient_category(self, ingredient_name: str) -> Optional[str]:
        """
        Get the category for an ingredient
        """
        ingredient_lower = ingredient_name.lower().replace("_", " ")
        
        for category, items in self.INGREDIENT_CATEGORIES.items():
            for item in items:
                if item.replace("_", " ") in ingredient_lower or ingredient_lower in item.replace("_", " "):
                    return category
        
        return None
    
    def _filter_by_preferences(
        self,
        suggestions: List[Dict],
        user_preferences: Dict
    ) -> List[Dict]:
        """
        Filter suggestions by allergens, dietary restrictions, etc.
        """
        filtered = []
        
        # Get all allergens
        all_allergens = set()
        for member in user_preferences.get("members", []):
            allergens = member.get("allergens", [])
            all_allergens.update(a.lower() for a in allergens)
        
        # Get dietary restrictions
        all_restrictions = set()
        for member in user_preferences.get("members", []):
            restrictions = member.get("dietary_restrictions", [])
            all_restrictions.update(r.lower() for r in restrictions)
        
        # Allergen keyword mapping
        allergen_keywords = {
            "dairy": ["milk", "cheese", "butter", "cream", "yogurt"],
            "eggs": ["egg"],
            "peanuts": ["peanut"],
            "tree_nuts": ["almond", "walnut", "cashew", "pistachio", "pecan"],
            "soy": ["soy", "tofu"],
            "wheat": ["wheat", "flour", "bread"],
            "fish": ["fish", "salmon", "tuna"],
            "shellfish": ["shrimp", "crab", "lobster"],
        }
        
        for suggestion in suggestions:
            name_lower = suggestion["name"].lower()
            
            # Check allergens
            is_allergen = False
            for allergen in all_allergens:
                keywords = allergen_keywords.get(allergen, [allergen])
                if any(kw in name_lower for kw in keywords):
                    is_allergen = True
                    break
            
            if is_allergen:
                continue  # Skip allergens
            
            # Check dietary restrictions
            violates_diet = False
            if "vegetarian" in all_restrictions or "vegan" in all_restrictions:
                meat_keywords = ["chicken", "beef", "pork", "fish", "shrimp", "meat"]
                if any(kw in name_lower for kw in meat_keywords):
                    violates_diet = True
            
            if "vegan" in all_restrictions:
                animal_keywords = ["milk", "cheese", "butter", "egg", "yogurt", "cream", "honey"]
                if any(kw in name_lower for kw in animal_keywords):
                    violates_diet = True
            
            if violates_diet:
                continue  # Skip restricted items
            
            suggestion["allergen_safe"] = True
            filtered.append(suggestion)
        
        return filtered
    
    def _rank_suggestions(
        self,
        suggestions: List[Dict],
        original_query: str,
        user_preferences: Optional[Dict]
    ) -> List[Dict]:
        """
        Rank suggestions by likelihood and user context
        """
        # Scoring system
        for suggestion in suggestions:
            score = 0
            
            # Base likelihood score
            if suggestion["likelihood"] == "high":
                score += 100
            elif suggestion["likelihood"] == "medium":
                score += 50
            else:
                score += 25
            
            # Strategy bonus
            if suggestion.get("strategy") == "visual_group":
                score += 50  # Visual similarity most relevant
            elif suggestion.get("strategy") == "fuzzy_match":
                score += 30
            
            # Similarity score bonus
            if "similarity_score" in suggestion:
                score += int(suggestion["similarity_score"] * 100)
            
            # User history bonus (if available)
            if user_preferences:
                # TODO: Check user history for frequently used ingredients
                pass
            
            # Cuisine preference bonus
            if user_preferences:
                favorite_cuisines = user_preferences.get("household", {}).get("favorite_cuisines", [])
                # TODO: Boost ingredients common in user's favorite cuisines
            
            suggestion["score"] = score
        
        # Sort by score
        suggestions.sort(key=lambda x: x["score"], reverse=True)
        
        return suggestions
    
    def is_common_in_cuisine(self, ingredient_name: str, cuisine: str) -> bool:
        """
        Check if ingredient is commonly used in a cuisine
        """
        cuisine_ingredients = {
            "indian": [
                "cumin", "coriander", "turmeric", "garam_masala", "curry_leaves",
                "mustard_seeds", "paneer", "ghee", "rice", "lentils", "chickpeas"
            ],
            "italian": [
                "olive_oil", "garlic", "basil", "tomato", "mozzarella", "parmesan",
                "pasta", "oregano", "pine_nuts"
            ],
            "mexican": [
                "cumin", "cilantro", "lime", "chili", "corn", "beans", "avocado",
                "tomato", "onion", "tortilla"
            ],
            "chinese": [
                "soy_sauce", "ginger", "garlic", "scallion", "rice", "sesame_oil",
                "rice_vinegar", "bok_choy", "tofu"
            ],
            "japanese": [
                "soy_sauce", "mirin", "sake", "dashi", "seaweed", "rice", "miso",
                "ginger", "wasabi", "sesame"
            ]
        }
        
        cuisine_lower = cuisine.lower()
        ingredient_lower = ingredient_name.lower().replace("_", " ")
        
        if cuisine_lower in cuisine_ingredients:
            cuisine_items = cuisine_ingredients[cuisine_lower]
            return any(item.replace("_", " ") in ingredient_lower for item in cuisine_items)
        
        return False


# Singleton instance
_normalizer = None

def get_normalizer() -> IngredientNormalizer:
    """Get or create normalizer singleton"""
    global _normalizer
    if _normalizer is None:
        _normalizer = IngredientNormalizer()
    return _normalizer
