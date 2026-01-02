"""Serving size calculator for recipe sufficiency checks

Determines if user has enough ingredients to make a recipe for N servings.
"""

from typing import Dict, List, Optional, Tuple
from app.core.unit_converter import UnitConverter


class ServingCalculator:
    """Calculate if pantry has enough ingredients for N servings"""
    
    # Standard serving sizes (per person)
    STANDARD_SERVINGS = {
        # Proteins (grams per person)
        "chicken": {"amount": 150, "unit": "grams"},
        "chicken_breast": {"amount": 150, "unit": "grams"},
        "chicken_thigh": {"amount": 150, "unit": "grams"},
        "beef": {"amount": 150, "unit": "grams"},
        "ground_beef": {"amount": 120, "unit": "grams"},
        "fish": {"amount": 120, "unit": "grams"},
        "salmon": {"amount": 120, "unit": "grams"},
        "pork": {"amount": 150, "unit": "grams"},
        "lamb": {"amount": 150, "unit": "grams"},
        "tofu": {"amount": 100, "unit": "grams"},
        "shrimp": {"amount": 100, "unit": "grams"},
        "eggs": {"amount": 2, "unit": "pieces"},
        
        # Vegetables (grams per person)
        "tomato": {"amount": 80, "unit": "grams"},
        "onion": {"amount": 60, "unit": "grams"},
        "carrot": {"amount": 60, "unit": "grams"},
        "potato": {"amount": 150, "unit": "grams"},
        "bell_pepper": {"amount": 75, "unit": "grams"},
        "spinach": {"amount": 60, "unit": "grams"},
        "broccoli": {"amount": 80, "unit": "grams"},
        "cauliflower": {"amount": 80, "unit": "grams"},
        "zucchini": {"amount": 100, "unit": "grams"},
        "eggplant": {"amount": 100, "unit": "grams"},
        "lettuce": {"amount": 50, "unit": "grams"},
        "cucumber": {"amount": 60, "unit": "grams"},
        "mushroom": {"amount": 50, "unit": "grams"},
        
        # Carbs (grams per person - dry weight)
        "rice": {"amount": 60, "unit": "grams"},
        "basmati_rice": {"amount": 60, "unit": "grams"},
        "pasta": {"amount": 80, "unit": "grams"},
        "spaghetti": {"amount": 80, "unit": "grams"},
        "noodles": {"amount": 80, "unit": "grams"},
        "bread": {"amount": 60, "unit": "grams"},
        "quinoa": {"amount": 60, "unit": "grams"},
        "couscous": {"amount": 60, "unit": "grams"},
        
        # Dairy
        "milk": {"amount": 250, "unit": "ml"},
        "yogurt": {"amount": 150, "unit": "grams"},
        "cheese": {"amount": 30, "unit": "grams"},
        "butter": {"amount": 10, "unit": "grams"},
        "cream": {"amount": 50, "unit": "ml"},
        "paneer": {"amount": 75, "unit": "grams"},
        
        # Legumes (dry weight)
        "lentils": {"amount": 60, "unit": "grams"},
        "chickpeas": {"amount": 60, "unit": "grams"},
        "black_beans": {"amount": 60, "unit": "grams"},
        "kidney_beans": {"amount": 60, "unit": "grams"},
    }
    
    @classmethod
    def check_sufficiency(
        cls,
        pantry_items: Dict[str, Dict],  # {ingredient_name: {quantity, unit}}
        recipe_ingredients: List[Dict],  # [{name, quantity, unit}]
        recipe_servings: int,
        needed_servings: int
    ) -> Dict:
        """
        Check if pantry has enough ingredients for recipe
        
        Args:
            pantry_items: Dictionary of available pantry items with quantities
            recipe_ingredients: List of recipe ingredients with quantities
            recipe_servings: Number of servings the recipe makes
            needed_servings: Number of servings needed
            
        Returns:
            {
                "sufficient": bool,
                "missing": [{ingredient, needed, unit, have}],
                "surplus": [{ingredient, extra, unit}],
                "scaling_factor": float,
                "total_missing": int,
                "total_sufficient": int
            }
            
        Examples:
            >>> pantry = {"chicken": {"quantity": 800, "unit": "grams"}}
            >>> recipe = [{"name": "chicken", "quantity": 500, "unit": "grams"}]
            >>> result = ServingCalculator.check_sufficiency(pantry, recipe, 4, 8)
            >>> result["sufficient"]
            False
            >>> result["missing"][0]["needed"]
            200
        """
        scaling_factor = needed_servings / recipe_servings
        missing = []
        surplus = []
        sufficient_count = 0
        
        for ingredient in recipe_ingredients:
            required_qty = ingredient["quantity"] * scaling_factor
            required_unit = ingredient["unit"]
            ingredient_name = ingredient["name"]
            
            # Get pantry quantity
            pantry_item = pantry_items.get(ingredient_name, {})
            available_qty = pantry_item.get("quantity", 0) or 0
            available_unit = pantry_item.get("unit", required_unit)
            
            # Convert to same unit if possible
            if available_unit and required_unit and available_unit != required_unit:
                try:
                    if UnitConverter.can_convert(available_unit, required_unit):
                        available_qty = UnitConverter.convert(
                            available_qty, 
                            available_unit, 
                            required_unit
                        )
                    else:
                        # Can't convert - different categories
                        # Still report shortage
                        pass
                except ValueError:
                    # Conversion failed, keep original quantity
                    pass
            
            # Check sufficiency
            if available_qty < required_qty:
                missing.append({
                    "ingredient": ingredient_name,
                    "needed": round(required_qty - available_qty, 2),
                    "unit": required_unit,
                    "have": round(available_qty, 2),
                    "required": round(required_qty, 2)
                })
            else:
                sufficient_count += 1
                
                # Check if there's significant surplus (>50% extra)
                if available_qty > required_qty * 1.5:
                    surplus.append({
                        "ingredient": ingredient_name,
                        "extra": round(available_qty - required_qty, 2),
                        "unit": required_unit,
                        "available": round(available_qty, 2),
                        "required": round(required_qty, 2)
                    })
        
        return {
            "sufficient": len(missing) == 0,
            "missing": missing,
            "surplus": surplus,
            "scaling_factor": scaling_factor,
            "total_missing": len(missing),
            "total_sufficient": sufficient_count,
            "total_ingredients": len(recipe_ingredients)
        }
    
    @classmethod
    def estimate_servings_possible(
        cls,
        pantry_items: Dict[str, Dict],
        recipe_ingredients: List[Dict],
        recipe_servings: int
    ) -> int:
        """
        Estimate maximum servings possible with current pantry
        
        Args:
            pantry_items: Available pantry items
            recipe_ingredients: Recipe ingredients list
            recipe_servings: Recipe's default servings
            
        Returns:
            Maximum number of servings possible (0 if missing ingredients)
            
        Examples:
            >>> pantry = {"chicken": {"quantity": 600, "unit": "grams"}}
            >>> recipe = [{"name": "chicken", "quantity": 500, "unit": "grams"}]
            >>> ServingCalculator.estimate_servings_possible(pantry, recipe, 4)
            4  # Can make 4 servings (have 600g, need 500g for 4)
        """
        max_servings = float('inf')
        
        for ingredient in recipe_ingredients:
            required_per_serving = ingredient["quantity"] / recipe_servings
            required_unit = ingredient["unit"]
            ingredient_name = ingredient["name"]
            
            # Get pantry quantity
            pantry_item = pantry_items.get(ingredient_name, {})
            available_qty = pantry_item.get("quantity", 0) or 0
            available_unit = pantry_item.get("unit", required_unit)
            
            if available_qty <= 0:
                return 0  # Missing ingredient entirely
            
            # Convert to same unit if possible
            if available_unit and required_unit and available_unit != required_unit:
                try:
                    if UnitConverter.can_convert(available_unit, required_unit):
                        available_qty = UnitConverter.convert(
                            available_qty,
                            available_unit,
                            required_unit
                        )
                except ValueError:
                    # Can't convert, assume insufficient
                    return 0
            
            # Calculate max servings for this ingredient
            servings_for_ingredient = available_qty / required_per_serving
            max_servings = min(max_servings, servings_for_ingredient)
        
        return int(max_servings) if max_servings != float('inf') else 0
    
    @classmethod
    def get_standard_serving(
        cls,
        ingredient_name: str,
        servings: int = 1
    ) -> Tuple[float, str]:
        """
        Get standard serving size for an ingredient
        
        Args:
            ingredient_name: Name of ingredient
            servings: Number of servings
            
        Returns:
            Tuple of (quantity, unit)
            
        Examples:
            >>> ServingCalculator.get_standard_serving("chicken", 4)
            (600, 'grams')
            >>> ServingCalculator.get_standard_serving("rice", 2)
            (120, 'grams')
        """
        ingredient_lower = ingredient_name.lower().strip()
        
        if ingredient_lower in cls.STANDARD_SERVINGS:
            standard = cls.STANDARD_SERVINGS[ingredient_lower]
            return (standard["amount"] * servings, standard["unit"])
        
        # Default fallback
        return (100 * servings, "grams")
    
    @classmethod
    def generate_shopping_list(
        cls,
        missing_ingredients: List[Dict]
    ) -> List[Dict]:
        """
        Generate a shopping list from missing ingredients
        
        Args:
            missing_ingredients: List of missing ingredients from check_sufficiency
            
        Returns:
            Shopping list with rounded quantities for practical shopping
            
        Examples:
            >>> missing = [{"ingredient": "chicken", "needed": 123.45, "unit": "grams"}]
            >>> shopping_list = ServingCalculator.generate_shopping_list(missing)
            >>> shopping_list[0]["quantity"]
            150  # Rounded up to practical amount
        """
        shopping_list = []
        
        for item in missing_ingredients:
            ingredient = item["ingredient"]
            needed = item["needed"]
            unit = item["unit"]
            
            # Round up to practical shopping quantities
            if unit in ["grams", "ml"]:
                # Round to nearest 50
                if needed < 100:
                    quantity = round(needed / 25) * 25  # 25g increments
                elif needed < 500:
                    quantity = round(needed / 50) * 50  # 50g increments
                else:
                    quantity = round(needed / 100) * 100  # 100g increments
            elif unit in ["kg", "liters"]:
                # Round to nearest 0.5
                quantity = round(needed * 2) / 2
            elif unit in ["cups", "tbsp", "tsp"]:
                # Round to nearest 0.5
                quantity = round(needed * 2) / 2
            elif unit in ["pieces", "items", "cloves", "slices"]:
                # Round up to whole number
                quantity = int(needed) + (1 if needed % 1 > 0 else 0)
            else:
                # Default: round to 2 decimal places
                quantity = round(needed, 2)
            
            shopping_list.append({
                "ingredient": ingredient,
                "quantity": quantity,
                "unit": unit,
                "original_needed": needed
            })
        
        return shopping_list
    
    @classmethod
    def calculate_recipe_cost_estimate(
        cls,
        recipe_ingredients: List[Dict],
        price_per_unit: Dict[str, Dict] = None  # {ingredient: {price, unit}}
    ) -> Dict:
        """
        Estimate recipe cost based on ingredient prices (future feature)
        
        Args:
            recipe_ingredients: Recipe ingredients list
            price_per_unit: Optional price database
            
        Returns:
            Cost breakdown
        """
        # Placeholder for future implementation
        return {
            "total_cost": 0,
            "cost_per_serving": 0,
            "breakdown": []
        }
    
    @classmethod
    def adjust_for_batch_cooking(
        cls,
        recipe_ingredients: List[Dict],
        batches: int,
        freeze_portions: bool = False
    ) -> List[Dict]:
        """
        Scale recipe for batch cooking (future feature)
        
        Args:
            recipe_ingredients: Recipe ingredients
            batches: Number of batches to make
            freeze_portions: Whether user plans to freeze
            
        Returns:
            Adjusted ingredient list
        """
        # Placeholder for future implementation
        adjusted = []
        for ingredient in recipe_ingredients:
            adjusted.append({
                **ingredient,
                "quantity": ingredient["quantity"] * batches,
                "batch_info": f"For {batches} batches"
            })
        return adjusted
