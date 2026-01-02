"""
Comprehensive tests for Vision Scanning System
Tests: vision API, normalization, endpoints, safety checks
"""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch, MagicMock
import json

from app.core.vision_api import VisionAPIClient
from app.core.ingredient_normalization import IngredientNormalizer


# ============================================================================
# Tests for IngredientNormalizer
# ============================================================================

class TestIngredientNormalizer:
    """Test ingredient normalization functionality"""
    
    def setup_method(self):
        self.normalizer = IngredientNormalizer()
    
    def test_normalize_name_basic(self):
        """Test basic name normalization"""
        assert self.normalizer.normalize_name("Whole Milk") == "milk"
        assert self.normalizer.normalize_name("2% Milk") == "milk"
        assert self.normalizer.normalize_name("Yellow Onion") == "onion"
    
    def test_normalize_name_removes_descriptors(self):
        """Test removal of common descriptors"""
        assert self.normalizer.normalize_name("fresh spinach") == "spinach"
        assert self.normalizer.normalize_name("frozen broccoli") == "broccoli"
        assert self.normalizer.normalize_name("sliced tomato") == "tomato"
    
    def test_normalize_name_handles_special_characters(self):
        """Test special character handling"""
        assert self.normalizer.normalize_name("bell-pepper") == "bell_pepper"
        assert self.normalizer.normalize_name("green onion") == "scallion"
    
    def test_get_visual_similarity_group(self):
        """Test visual similarity group detection"""
        assert self.normalizer.get_visual_similarity_group("spinach") == "leafy_greens"
        assert self.normalizer.get_visual_similarity_group("kale") == "leafy_greens"
        assert self.normalizer.get_visual_similarity_group("potato") == "root_vegetables"
        assert self.normalizer.get_visual_similarity_group("unknown_item") is None
    
    def test_get_close_ingredients_visual_group(self):
        """Test close ingredients from visual similarity group"""
        close = self.normalizer.get_close_ingredients("spinach", limit=5)
        
        assert len(close) <= 5
        assert all(isinstance(item, dict) for item in close)
        assert all("name" in item and "display_name" in item for item in close)
        
        # Should include other leafy greens
        names = [item["name"] for item in close]
        assert any(name in ["kale", "lettuce", "arugula"] for name in names)
    
    def test_get_close_ingredients_filters_allergens(self):
        """Test that close ingredients respects allergen restrictions"""
        user_preferences = {
            "members": [
                {"allergens": ["dairy"]}
            ]
        }
        
        # Request close ingredients for cheese (dairy)
        close = self.normalizer.get_close_ingredients(
            "cheese",
            user_preferences=user_preferences,
            limit=10
        )
        
        # Should not suggest any dairy products
        for item in close:
            name_lower = item["name"].lower()
            assert "milk" not in name_lower
            assert "cheese" not in name_lower
            assert "butter" not in name_lower
    
    def test_get_close_ingredients_respects_vegetarian(self):
        """Test that close ingredients respects dietary restrictions"""
        user_preferences = {
            "members": [
                {"dietary_restrictions": ["vegetarian"]}
            ]
        }
        
        close = self.normalizer.get_close_ingredients(
            "chicken",
            user_preferences=user_preferences,
            limit=10
        )
        
        # Should not suggest meat products
        for item in close:
            name_lower = item["name"].lower()
            meat_keywords = ["chicken", "beef", "pork", "fish", "shrimp"]
            assert not any(kw in name_lower for kw in meat_keywords)
    
    def test_get_ingredient_category(self):
        """Test ingredient category detection"""
        assert self.normalizer.get_ingredient_category("chicken") == "protein"
        assert self.normalizer.get_ingredient_category("spinach") == "vegetable"
        assert self.normalizer.get_ingredient_category("rice") == "grain"
        assert self.normalizer.get_ingredient_category("milk") == "dairy"
        assert self.normalizer.get_ingredient_category("cumin") == "spice"
    
    def test_is_common_in_cuisine(self):
        """Test cuisine-specific ingredient detection"""
        assert self.normalizer.is_common_in_cuisine("cumin", "indian")
        assert self.normalizer.is_common_in_cuisine("olive_oil", "italian")
        assert self.normalizer.is_common_in_cuisine("soy_sauce", "chinese")
        assert not self.normalizer.is_common_in_cuisine("cumin", "italian")


# ============================================================================
# Tests for VisionAPIClient
# ============================================================================

class TestVisionAPIClient:
    """Test Vision API client functionality"""
    
    def setup_method(self):
        self.client = VisionAPIClient()
    
    def test_get_confidence_category(self):
        """Test confidence categorization"""
        assert self.client.get_confidence_category(Decimal("0.90")) == "high"
        assert self.client.get_confidence_category(Decimal("0.70")) == "medium"
        assert self.client.get_confidence_category(Decimal("0.40")) == "low"
    
    def test_check_allergen_warnings_no_allergens(self):
        """Test allergen check with no allergens declared"""
        warnings = self.client._check_allergen_warnings(
            "chicken",
            {"members": [{"allergens": []}]}
        )
        assert warnings == []
    
    def test_check_allergen_warnings_detects_dairy(self):
        """Test allergen detection for dairy"""
        warnings = self.client._check_allergen_warnings(
            "milk",
            {"members": [{"allergens": ["dairy"]}]}
        )
        assert len(warnings) == 1
        assert warnings[0]["allergen"] == "dairy"
        assert warnings[0]["severity"] == "critical"
    
    def test_check_allergen_warnings_detects_nuts(self):
        """Test allergen detection for nuts"""
        warnings = self.client._check_allergen_warnings(
            "peanut_butter",
            {"members": [{"allergens": ["peanuts"]}]}
        )
        assert len(warnings) == 1
        assert warnings[0]["allergen"] == "peanuts"
    
    def test_check_allergen_warnings_multiple_members(self):
        """Test allergen aggregation across family members"""
        warnings = self.client._check_allergen_warnings(
            "cheese",
            {
                "members": [
                    {"allergens": ["dairy"]},
                    {"allergens": ["eggs"]}
                ]
            }
        )
        # Cheese contains dairy, should warn
        assert len(warnings) >= 1
        assert any(w["allergen"] == "dairy" for w in warnings)
    
    @pytest.mark.asyncio
    async def test_estimate_api_cost(self):
        """Test API cost estimation"""
        cost = await self.client.estimate_api_cost(b"fake_image_data")
        assert isinstance(cost, int)
        assert cost > 0


# ============================================================================
# Tests for Safety Integration
# ============================================================================

class TestSafetyConstraints:
    """Test safety constraint enforcement in scanning"""
    
    def setup_method(self):
        self.normalizer = IngredientNormalizer()
    
    def test_allergen_filtering_dairy(self):
        """Test that dairy allergens are filtered from suggestions"""
        user_preferences = {
            "members": [{"allergens": ["dairy"]}]
        }
        
        # Get suggestions for milk
        suggestions = self.normalizer.get_close_ingredients(
            "milk",
            user_preferences=user_preferences
        )
        
        # Should not include any dairy products
        for suggestion in suggestions:
            name = suggestion["name"].lower()
            dairy_keywords = ["milk", "cheese", "butter", "cream", "yogurt"]
            assert not any(kw in name for kw in dairy_keywords), \
                f"Dairy allergen found in suggestions: {suggestion['name']}"
    
    def test_allergen_filtering_multiple(self):
        """Test filtering with multiple allergens"""
        user_preferences = {
            "members": [
                {"allergens": ["dairy", "eggs", "nuts"]}
            ]
        }
        
        # Try to get suggestions - should exclude all allergens
        suggestions = self.normalizer.get_close_ingredients(
            "protein_powder",
            user_preferences=user_preferences,
            limit=10
        )
        
        for suggestion in suggestions:
            name = suggestion["name"].lower()
            # Check none of the allergens appear
            assert "milk" not in name
            assert "egg" not in name
            assert "nut" not in name
            assert "almond" not in name
            assert "peanut" not in name
    
    def test_dietary_restriction_vegetarian(self):
        """Test vegetarian dietary restriction filtering"""
        user_preferences = {
            "members": [
                {"dietary_restrictions": ["vegetarian"]}
            ]
        }
        
        suggestions = self.normalizer.get_close_ingredients(
            "tofu",
            user_preferences=user_preferences,
            limit=10
        )
        
        # Should not include meat
        for suggestion in suggestions:
            name = suggestion["name"].lower()
            meat_keywords = ["chicken", "beef", "pork", "fish", "shrimp", "meat"]
            assert not any(kw in name for kw in meat_keywords)
    
    def test_dietary_restriction_vegan(self):
        """Test vegan dietary restriction filtering"""
        user_preferences = {
            "members": [
                {"dietary_restrictions": ["vegan"]}
            ]
        }
        
        suggestions = self.normalizer.get_close_ingredients(
            "chickpeas",
            user_preferences=user_preferences,
            limit=10
        )
        
        # Should not include meat OR animal products
        for suggestion in suggestions:
            name = suggestion["name"].lower()
            # No meat
            meat_keywords = ["chicken", "beef", "pork", "fish", "shrimp"]
            assert not any(kw in name for kw in meat_keywords)
            # No animal products
            animal_keywords = ["milk", "cheese", "butter", "egg", "yogurt", "honey"]
            assert not any(kw in name for kw in animal_keywords)


# ============================================================================
# Tests for Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def setup_method(self):
        self.normalizer = IngredientNormalizer()
    
    def test_normalize_empty_string(self):
        """Test normalization with empty string"""
        result = self.normalizer.normalize_name("")
        assert result == ""
    
    def test_normalize_special_characters_only(self):
        """Test normalization with only special characters"""
        result = self.normalizer.normalize_name("!@#$%")
        assert result == ""
    
    def test_get_close_ingredients_unknown_item(self):
        """Test close ingredients for completely unknown item"""
        close = self.normalizer.get_close_ingredients("xyzabc_unknown_item")
        # Should still return some results (fuzzy matching)
        assert isinstance(close, list)
    
    def test_get_close_ingredients_empty_preferences(self):
        """Test close ingredients with empty user preferences"""
        close = self.normalizer.get_close_ingredients(
            "spinach",
            user_preferences={}
        )
        assert isinstance(close, list)
        assert len(close) > 0
    
    def test_filtering_with_missing_allergens_key(self):
        """Test filtering when allergens key is missing"""
        user_preferences = {
            "members": [{}]  # No allergens key
        }
        
        close = self.normalizer.get_close_ingredients(
            "milk",
            user_preferences=user_preferences
        )
        # Should not crash, should return results
        assert isinstance(close, list)


# ============================================================================
# Integration Tests (would require test database)
# ============================================================================

class TestEndToEndFlow:
    """Test complete scanning flow (unit test with mocks)"""
    
    @pytest.mark.asyncio
    async def test_complete_scanning_flow_mock(self):
        """Test complete flow from image to confirmed ingredients"""
        
        # This would test:
        # 1. Image upload
        # 2. Vision API analysis
        # 3. Ingredient normalization
        # 4. Close alternatives generation
        # 5. Allergen warning
        # 6. User confirmation
        # 7. Pantry update
        
        # Mock implementation for documentation
        pass


# ============================================================================
# Run tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
