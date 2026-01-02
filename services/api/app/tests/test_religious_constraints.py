"""
Test cases for religious and cultural dietary constraints.
Implements Section 11.11 of user_profile.md - Religious & Cultural Stress Testing.
"""
import pytest
from app.core.safety_constraints import (
    build_religious_constraints,
    validate_recipe_safety,
    SAVOGoldenRule,
    RELIGIOUS_DIETARY_MAPS
)


# ============================================================================
# Test Case 1: Jain Household
# ============================================================================

def test_jain_household_onion_garlic():
    """Test Jain restrictions: no onion, garlic, or root vegetables"""
    profile = {
        "members": [
            {
                "name": "Test User",
                "dietary_restrictions": ["jain"],
                "allergens": []
            }
        ]
    }
    
    # Test recipe with forbidden ingredients
    recipe_with_onion = {
        "ingredients": ["rice", "onion", "tomato"]
    }
    
    is_safe, violations = validate_recipe_safety(recipe_with_onion, profile)
    
    assert not is_safe, "Recipe with onion should fail for Jain household"
    assert len(violations) > 0
    assert any("onion" in v.lower() for v in violations)


def test_jain_household_root_vegetables():
    """Test Jain restrictions: no root vegetables"""
    profile = {
        "members": [
            {
                "dietary_restrictions": ["jain"],
                "allergens": []
            }
        ]
    }
    
    recipe_with_potato = {
        "ingredients": ["potato", "cauliflower", "spices"]
    }
    
    is_safe, violations = validate_recipe_safety(recipe_with_potato, profile)
    
    assert not is_safe
    assert any("potato" in v.lower() for v in violations)


def test_jain_household_safe_recipe():
    """Test safe recipe for Jain household"""
    profile = {
        "members": [
            {
                "dietary_restrictions": ["jain"],
                "allergens": []
            }
        ]
    }
    
    safe_recipe = {
        "ingredients": ["rice", "lentils", "tomato", "cumin", "turmeric"]
    }
    
    is_safe, violations = validate_recipe_safety(safe_recipe, profile)
    
    assert is_safe, f"Safe recipe failed with violations: {violations}"
    assert len(violations) == 0


# ============================================================================
# Test Case 2: Muslim Household (Halal)
# ============================================================================

def test_muslim_household_no_pork():
    """Test Muslim halal restrictions: no pork"""
    profile = {
        "members": [
            {
                "dietary_restrictions": ["halal", "no_pork"],
                "allergens": []
            }
        ]
    }
    
    recipe_with_pork = {
        "ingredients": ["pork chops", "vegetables", "rice"]
    }
    
    is_safe, violations = validate_recipe_safety(recipe_with_pork, profile)
    
    assert not is_safe
    assert any("pork" in v.lower() for v in violations)


def test_muslim_household_no_alcohol():
    """Test Muslim halal restrictions: no alcohol"""
    profile = {
        "members": [
            {
                "dietary_restrictions": ["halal", "no_alcohol"],
                "allergens": []
            }
        ]
    }
    
    recipe_with_wine = {
        "ingredients": ["chicken", "white wine", "herbs"]
    }
    
    is_safe, violations = validate_recipe_safety(recipe_with_wine, profile)
    
    assert not is_safe
    assert any("wine" in v.lower() for v in violations)


def test_muslim_household_safe_recipe():
    """Test safe recipe for Muslim household"""
    profile = {
        "members": [
            {
                "dietary_restrictions": ["halal"],
                "allergens": []
            }
        ]
    }
    
    safe_recipe = {
        "ingredients": ["halal chicken", "rice", "vegetables", "spices"]
    }
    
    is_safe, violations = validate_recipe_safety(safe_recipe, profile)
    
    assert is_safe
    assert len(violations) == 0


# ============================================================================
# Test Case 3: Hindu Household (No Beef)
# ============================================================================

def test_hindu_household_no_beef():
    """Test Hindu restriction: no beef"""
    profile = {
        "members": [
            {
                "dietary_restrictions": ["no_beef"],
                "allergens": []
            }
        ]
    }
    
    recipe_with_beef = {
        "ingredients": ["ground beef", "tomato", "pasta"]
    }
    
    is_safe, violations = validate_recipe_safety(recipe_with_beef, profile)
    
    assert not is_safe
    assert any("beef" in v.lower() for v in violations)


def test_hindu_household_chicken_allowed():
    """Test that chicken is allowed for Hindu household (only beef restricted)"""
    profile = {
        "members": [
            {
                "dietary_restrictions": ["no_beef"],
                "allergens": []
            }
        ]
    }
    
    recipe_with_chicken = {
        "ingredients": ["chicken", "rice", "curry spices"]
    }
    
    is_safe, violations = validate_recipe_safety(recipe_with_chicken, profile)
    
    assert is_safe
    assert len(violations) == 0


# ============================================================================
# Test Case 4: Jewish Household (Kosher-Aware)
# ============================================================================

def test_jewish_household_no_pork():
    """Test Jewish kosher restrictions: no pork"""
    profile = {
        "members": [
            {
                "dietary_restrictions": ["kosher", "no_pork"],
                "allergens": []
            }
        ]
    }
    
    recipe_with_bacon = {
        "ingredients": ["bacon", "eggs", "toast"]
    }
    
    is_safe, violations = validate_recipe_safety(recipe_with_bacon, profile)
    
    assert not is_safe
    assert any("bacon" in v.lower() for v in violations)


def test_jewish_household_no_shellfish():
    """Test Jewish kosher restrictions: no shellfish"""
    profile = {
        "members": [
            {
                "dietary_restrictions": ["kosher"],
                "allergens": []
            }
        ]
    }
    
    recipe_with_shrimp = {
        "ingredients": ["shrimp", "pasta", "garlic"]
    }
    
    is_safe, violations = validate_recipe_safety(recipe_with_shrimp, profile)
    
    assert not is_safe
    assert any("shrimp" in v.lower() for v in violations)


# ============================================================================
# Test Case 5: Vegan Household
# ============================================================================

def test_vegan_household_no_meat():
    """Test vegan restrictions: no meat"""
    profile = {
        "members": [
            {
                "dietary_restrictions": ["vegan"],
                "allergens": []
            }
        ]
    }
    
    recipe_with_chicken = {
        "ingredients": ["chicken breast", "vegetables"]
    }
    
    is_safe, violations = validate_recipe_safety(recipe_with_chicken, profile)
    
    assert not is_safe
    assert any("meat" in v.lower() or "chicken" in v.lower() for v in violations)


def test_vegan_household_no_dairy():
    """Test vegan restrictions: no dairy"""
    profile = {
        "members": [
            {
                "dietary_restrictions": ["vegan"],
                "allergens": []
            }
        ]
    }
    
    recipe_with_cheese = {
        "ingredients": ["pasta", "cheese", "tomato sauce"]
    }
    
    is_safe, violations = validate_recipe_safety(recipe_with_cheese, profile)
    
    assert not is_safe
    assert any("cheese" in v.lower() for v in violations)


def test_vegan_household_safe_recipe():
    """Test safe recipe for vegan household"""
    profile = {
        "members": [
            {
                "dietary_restrictions": ["vegan"],
                "allergens": []
            }
        ]
    }
    
    safe_recipe = {
        "ingredients": ["tofu", "vegetables", "rice", "soy sauce"]
    }
    
    is_safe, violations = validate_recipe_safety(safe_recipe, profile)
    
    assert is_safe
    assert len(violations) == 0


# ============================================================================
# Test Case 6: Mixed Household
# ============================================================================

def test_mixed_household_strictest_wins():
    """Test mixed household: strictest restriction should apply"""
    profile = {
        "members": [
            {
                "name": "Adult",
                "dietary_restrictions": ["vegetarian"],
                "allergens": []
            },
            {
                "name": "Child",
                "dietary_restrictions": [],
                "allergens": []
            }
        ]
    }
    
    recipe_with_chicken = {
        "ingredients": ["chicken", "rice", "vegetables"]
    }
    
    is_safe, violations = validate_recipe_safety(recipe_with_chicken, profile)
    
    # Should fail because one member is vegetarian
    assert not is_safe
    assert any("meat" in v.lower() or "chicken" in v.lower() for v in violations)


# ============================================================================
# Golden Rule Tests
# ============================================================================

def test_golden_rule_missing_allergen_declaration():
    """Test Golden Rule: must have allergen declarations"""
    profile = {
        "household": {"name": "Test"},
        "members": [
            {
                "name": "User",
                # Missing "allergens" field
            }
        ]
    }
    
    result = SAVOGoldenRule.check_before_generate(profile)
    
    assert not result["can_proceed"]
    assert result["action"] == "ask"
    assert "allergen" in result["message"].lower()


def test_golden_rule_pork_conflict():
    """Test Golden Rule: detect pork conflict with halal"""
    profile = {
        "household": {"name": "Test"},
        "members": [
            {
                "name": "User",
                "dietary_restrictions": ["halal"],
                "allergens": []
            }
        ]
    }
    
    result = SAVOGoldenRule.check_before_generate(profile, request="bacon pasta")
    
    assert not result["can_proceed"]
    assert result["action"] == "refuse"
    assert "halal" in result["message"].lower()


def test_golden_rule_allergen_conflict():
    """Test Golden Rule: detect allergen in request"""
    profile = {
        "household": {"name": "Test"},
        "members": [
            {
                "name": "User",
                "dietary_restrictions": [],
                "allergens": ["peanuts"]
            }
        ]
    }
    
    result = SAVOGoldenRule.check_before_generate(profile, request="peanut butter cookies")
    
    assert not result["can_proceed"]
    assert result["action"] == "refuse"
    assert "peanut" in result["message"].lower()


def test_golden_rule_safe_request():
    """Test Golden Rule: allow safe request"""
    profile = {
        "household": {"name": "Test"},
        "members": [
            {
                "name": "User",
                "dietary_restrictions": ["vegetarian"],
                "allergens": []
            }
        ]
    }
    
    result = SAVOGoldenRule.check_before_generate(profile, request="vegetable curry")
    
    assert result["can_proceed"]
    assert result["action"] == "proceed"


# ============================================================================
# Religious Constraint Builder Tests
# ============================================================================

def test_build_religious_constraints_jain():
    """Test building religious constraints for Jain"""
    profile = {
        "members": [
            {"dietary_restrictions": ["jain"], "allergens": []}
        ]
    }
    
    constraints = build_religious_constraints(profile)
    
    assert "Jain" in constraints or "jain" in constraints.lower()
    assert "onion" in constraints.lower()
    assert "garlic" in constraints.lower()
    assert "HARD constraint" in constraints or "hard constraint" in constraints.lower()


def test_build_religious_constraints_halal():
    """Test building religious constraints for Halal"""
    profile = {
        "members": [
            {"dietary_restrictions": ["halal"], "allergens": []}
        ]
    }
    
    constraints = build_religious_constraints(profile)
    
    assert "halal" in constraints.lower()
    assert "pork" in constraints.lower()
    assert "religious" in constraints.lower()


# ============================================================================
# QA Rejection Criteria Tests
# ============================================================================

def test_no_allergen_inference():
    """Rejection Criterion 1: No allergen inference"""
    profile = {
        "household": {"name": "Test"},
        "members": [
            {
                "name": "User",
                "allergens": []  # Explicitly empty
            }
        ]
    }
    
    # System should accept empty allergen list (user declared "none")
    result = SAVOGoldenRule.check_before_generate(profile)
    
    assert result["can_proceed"]


def test_no_silent_religious_violations():
    """Rejection Criterion 2: No silent religious violations"""
    profile = {
        "members": [
            {"dietary_restrictions": ["halal"], "allergens": []}
        ]
    }
    
    recipe_with_pork = {
        "ingredients": ["pork", "vegetables"]
    }
    
    is_safe, violations = validate_recipe_safety(recipe_with_pork, profile)
    
    # Must have explicit violation message
    assert not is_safe
    assert len(violations) > 0
    assert any("halal" in v.lower() or "pork" in v.lower() for v in violations)


def test_refusal_with_explanation():
    """Rejection Criterion 4: Refusals must have explanation"""
    profile = {
        "household": {"name": "Test"},
        "members": [
            {"dietary_restrictions": ["vegan"], "allergens": ["dairy"]}
        ]
    }
    
    result = SAVOGoldenRule.check_before_generate(profile, request="cheese soufflé")
    
    if not result["can_proceed"]:
        # Must have message explaining why
        assert "message" in result
        assert len(result["message"]) > 20
        assert any(word in result["message"].lower() 
                  for word in ["vegan", "dairy", "allergen"])


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
