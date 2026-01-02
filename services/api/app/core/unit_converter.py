"""Unit conversion service for ingredient quantities

Handles conversion between weight, volume, and count units for recipe scaling
and pantry management.
"""

from typing import Dict, Tuple, Optional
from decimal import Decimal


class UnitConverter:
    """Convert between different units of measurement"""
    
    # Conversion table: {from_unit: {to_unit: factor}}
    # Base units: grams (weight), ml (volume), pieces (count)
    CONVERSIONS = {
        # Weight conversions (base: grams)
        "grams": {
            "kg": 0.001,
            "mg": 1000,
            "oz": 0.035274,
            "lb": 0.00220462
        },
        "kg": {
            "grams": 1000,
            "mg": 1000000,
            "oz": 35.274,
            "lb": 2.20462
        },
        "oz": {
            "grams": 28.3495,
            "kg": 0.0283495,
            "mg": 28349.5,
            "lb": 0.0625
        },
        "lb": {
            "grams": 453.592,
            "kg": 0.453592,
            "mg": 453592,
            "oz": 16
        },
        "mg": {
            "grams": 0.001,
            "kg": 0.000001,
            "oz": 0.000035274,
            "lb": 0.0000022046
        },
        
        # Volume conversions (base: ml)
        "ml": {
            "liters": 0.001,
            "cups": 0.00422675,
            "tbsp": 0.067628,
            "tsp": 0.202884,
            "fl oz": 0.033814,
            "gallon": 0.000264172,
            "pint": 0.00211338,
            "quart": 0.00105669
        },
        "liters": {
            "ml": 1000,
            "cups": 4.22675,
            "tbsp": 67.628,
            "tsp": 202.884,
            "fl oz": 33.814,
            "gallon": 0.264172,
            "pint": 2.11338,
            "quart": 1.05669
        },
        "cups": {
            "ml": 236.588,
            "liters": 0.236588,
            "tbsp": 16,
            "tsp": 48,
            "fl oz": 8,
            "gallon": 0.0625,
            "pint": 0.5,
            "quart": 0.25
        },
        "tbsp": {
            "ml": 14.7868,
            "liters": 0.0147868,
            "cups": 0.0625,
            "tsp": 3,
            "fl oz": 0.5,
            "gallon": 0.00390625,
            "pint": 0.03125,
            "quart": 0.015625
        },
        "tsp": {
            "ml": 4.92892,
            "liters": 0.00492892,
            "cups": 0.0208333,
            "tbsp": 0.333333,
            "fl oz": 0.166667,
            "gallon": 0.00130208,
            "pint": 0.0104167,
            "quart": 0.00520833
        },
        "fl oz": {
            "ml": 29.5735,
            "liters": 0.0295735,
            "cups": 0.125,
            "tbsp": 2,
            "tsp": 6,
            "gallon": 0.0078125,
            "pint": 0.0625,
            "quart": 0.03125
        },
        "gallon": {
            "ml": 3785.41,
            "liters": 3.78541,
            "cups": 16,
            "tbsp": 256,
            "tsp": 768,
            "fl oz": 128,
            "pint": 8,
            "quart": 4
        },
        "pint": {
            "ml": 473.176,
            "liters": 0.473176,
            "cups": 2,
            "tbsp": 32,
            "tsp": 96,
            "fl oz": 16,
            "gallon": 0.125,
            "quart": 0.5
        },
        "quart": {
            "ml": 946.353,
            "liters": 0.946353,
            "cups": 4,
            "tbsp": 64,
            "tsp": 192,
            "fl oz": 32,
            "gallon": 0.25,
            "pint": 2
        },
        
        # Count (no conversion between different count types, all equal 1:1)
        "pieces": {
            "items": 1,
            "cloves": 1,
            "slices": 1,
            "leaves": 1,
            "cans": 1,
            "packages": 1
        },
        "items": {
            "pieces": 1,
            "cloves": 1,
            "slices": 1,
            "leaves": 1,
            "cans": 1,
            "packages": 1
        },
        "cloves": {
            "pieces": 1,
            "items": 1
        },
        "slices": {
            "pieces": 1,
            "items": 1
        },
        "leaves": {
            "pieces": 1,
            "items": 1
        },
        "cans": {
            "pieces": 1,
            "items": 1
        },
        "packages": {
            "pieces": 1,
            "items": 1
        },
    }
    
    # Unit categories for validation
    UNIT_CATEGORIES = {
        "weight": ["grams", "kg", "mg", "oz", "lb"],
        "volume": ["ml", "liters", "cups", "tbsp", "tsp", "fl oz", "gallon", "pint", "quart"],
        "count": ["pieces", "items", "cloves", "slices", "leaves", "cans", "packages"]
    }
    
    @classmethod
    def convert(cls, quantity: float, from_unit: str, to_unit: str) -> float:
        """
        Convert quantity from one unit to another
        
        Args:
            quantity: Amount to convert
            from_unit: Source unit
            to_unit: Target unit
            
        Returns:
            Converted quantity
            
        Raises:
            ValueError: If conversion not supported or units in different categories
            
        Examples:
            >>> UnitConverter.convert(1000, "grams", "kg")
            1.0
            >>> UnitConverter.convert(1, "cups", "ml")
            236.588
            >>> UnitConverter.convert(2, "tbsp", "tsp")
            6.0
        """
        # Normalize unit names (lowercase, strip whitespace)
        from_unit = from_unit.lower().strip()
        to_unit = to_unit.lower().strip()
        
        # Same unit, no conversion needed
        if from_unit == to_unit:
            return quantity
        
        # Check if from_unit exists
        if from_unit not in cls.CONVERSIONS:
            raise ValueError(f"Unknown source unit: {from_unit}")
        
        # Check if to_unit exists in from_unit's conversion table
        if to_unit not in cls.CONVERSIONS[from_unit]:
            # Check if they're in different categories
            from_cat = cls.get_unit_category(from_unit)
            to_cat = cls.get_unit_category(to_unit)
            
            if from_cat != to_cat:
                raise ValueError(
                    f"Cannot convert between different categories: "
                    f"{from_unit} ({from_cat}) to {to_unit} ({to_cat})"
                )
            else:
                raise ValueError(
                    f"Conversion not defined: {from_unit} to {to_unit}"
                )
        
        # Perform conversion
        factor = cls.CONVERSIONS[from_unit][to_unit]
        return round(quantity * factor, 3)  # Round to 3 decimal places
    
    @classmethod
    def get_unit_category(cls, unit: str) -> str:
        """
        Get category of unit (weight, volume, count)
        
        Args:
            unit: Unit name
            
        Returns:
            Category name or "unknown"
            
        Examples:
            >>> UnitConverter.get_unit_category("grams")
            'weight'
            >>> UnitConverter.get_unit_category("cups")
            'volume'
            >>> UnitConverter.get_unit_category("pieces")
            'count'
        """
        unit = unit.lower().strip()
        
        for category, units in cls.UNIT_CATEGORIES.items():
            if unit in units:
                return category
        
        return "unknown"
    
    @classmethod
    def can_convert(cls, from_unit: str, to_unit: str) -> bool:
        """
        Check if conversion is possible between two units
        
        Args:
            from_unit: Source unit
            to_unit: Target unit
            
        Returns:
            True if conversion possible, False otherwise
            
        Examples:
            >>> UnitConverter.can_convert("grams", "oz")
            True
            >>> UnitConverter.can_convert("grams", "ml")
            False
        """
        from_unit = from_unit.lower().strip()
        to_unit = to_unit.lower().strip()
        
        # Same unit
        if from_unit == to_unit:
            return True
        
        # Check if conversion exists
        if from_unit not in cls.CONVERSIONS:
            return False
        
        return to_unit in cls.CONVERSIONS[from_unit]
    
    @classmethod
    def get_compatible_units(cls, unit: str) -> list[str]:
        """
        Get all units compatible with the given unit
        
        Args:
            unit: Unit name
            
        Returns:
            List of compatible unit names (same category)
            
        Examples:
            >>> UnitConverter.get_compatible_units("grams")
            ['kg', 'mg', 'oz', 'lb']
        """
        unit = unit.lower().strip()
        
        if unit not in cls.CONVERSIONS:
            return []
        
        return list(cls.CONVERSIONS[unit].keys())
    
    @classmethod
    def get_display_name(cls, unit: str) -> str:
        """
        Get user-friendly display name for unit
        
        Args:
            unit: Unit name
            
        Returns:
            Display name
            
        Examples:
            >>> UnitConverter.get_display_name("grams")
            'g'
            >>> UnitConverter.get_display_name("tbsp")
            'tbsp'
        """
        display_names = {
            "grams": "g",
            "kg": "kg",
            "mg": "mg",
            "oz": "oz",
            "lb": "lb",
            "ml": "ml",
            "liters": "L",
            "cups": "cup",
            "tbsp": "tbsp",
            "tsp": "tsp",
            "fl oz": "fl oz",
            "gallon": "gal",
            "pint": "pt",
            "quart": "qt",
            "pieces": "pcs",
            "items": "items",
            "cloves": "cloves",
            "slices": "slices",
            "leaves": "leaves",
            "cans": "cans",
            "packages": "pkgs"
        }
        
        return display_names.get(unit.lower().strip(), unit)
    
    @classmethod
    def get_base_unit(cls, category: str) -> str:
        """
        Get base unit for a category
        
        Args:
            category: Category name (weight, volume, count)
            
        Returns:
            Base unit name
            
        Examples:
            >>> UnitConverter.get_base_unit("weight")
            'grams'
            >>> UnitConverter.get_base_unit("volume")
            'ml'
        """
        base_units = {
            "weight": "grams",
            "volume": "ml",
            "count": "pieces"
        }
        
        return base_units.get(category, "unknown")
    
    @classmethod
    def normalize_to_base(cls, quantity: float, unit: str) -> Tuple[float, str]:
        """
        Convert quantity to base unit for its category
        
        Args:
            quantity: Amount
            unit: Current unit
            
        Returns:
            Tuple of (converted_quantity, base_unit)
            
        Examples:
            >>> UnitConverter.normalize_to_base(1, "kg")
            (1000.0, 'grams')
            >>> UnitConverter.normalize_to_base(2, "cups")
            (473.176, 'ml')
        """
        category = cls.get_unit_category(unit)
        base_unit = cls.get_base_unit(category)
        
        if unit.lower() == base_unit:
            return quantity, base_unit
        
        converted = cls.convert(quantity, unit, base_unit)
        return converted, base_unit
    
    @classmethod
    def get_smart_unit_suggestions(cls, ingredient_name: str, category: str = None) -> list[str]:
        """
        Get smart unit suggestions based on ingredient type
        
        Args:
            ingredient_name: Name of ingredient
            category: Optional ingredient category
            
        Returns:
            List of suggested units
            
        Examples:
            >>> UnitConverter.get_smart_unit_suggestions("milk")
            ['ml', 'liters', 'cups']
            >>> UnitConverter.get_smart_unit_suggestions("chicken")
            ['grams', 'kg', 'lb', 'oz']
        """
        ingredient_lower = ingredient_name.lower()
        
        # Liquid ingredients
        if any(word in ingredient_lower for word in [
            "milk", "water", "juice", "oil", "sauce", "broth", "stock", 
            "cream", "yogurt", "buttermilk", "wine", "vinegar"
        ]):
            return ["ml", "liters", "cups", "tbsp", "tsp"]
        
        # Meats and proteins (weight)
        if any(word in ingredient_lower for word in [
            "chicken", "beef", "pork", "fish", "lamb", "meat", "tofu"
        ]):
            return ["grams", "kg", "lb", "oz"]
        
        # Vegetables and fruits (count or weight)
        if category in ["vegetable", "fruit"] or any(word in ingredient_lower for word in [
            "tomato", "onion", "potato", "carrot", "apple", "banana"
        ]):
            return ["pieces", "grams", "kg"]
        
        # Spices and herbs
        if any(word in ingredient_lower for word in [
            "salt", "pepper", "spice", "herb", "cumin", "coriander", 
            "turmeric", "paprika", "oregano", "basil"
        ]):
            return ["grams", "tsp", "tbsp"]
        
        # Grains and pasta
        if any(word in ingredient_lower for word in [
            "rice", "pasta", "noodles", "flour", "quinoa", "couscous"
        ]):
            return ["grams", "cups", "kg"]
        
        # Cheese
        if "cheese" in ingredient_lower:
            return ["grams", "oz", "slices"]
        
        # Default: offer all common units
        return ["pieces", "grams", "ml", "cups"]
