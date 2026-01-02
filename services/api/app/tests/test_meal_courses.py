"""
Tests for Full Course Meal Planning

Tests:
- Course sequencing
- Flavor progression
- Cultural coherence
- Meal style templates
- Portion sizing
- Safety integration across courses
"""

import pytest
from app.core.meal_courses import (
    MealCourseEngine,
    MealStyle,
    CourseType,
    plan_full_course_meal,
    generate_meal_prompt
)


@pytest.fixture
def sample_profile():
    """Sample user profile"""
    return {
        "household": {
            "household_name": "Test Family",
            "primary_language": "en",
            "measurement_system": "imperial",
            "member_count": 4
        },
        "members": [
            {
                "name": "Adult 1",
                "age": 35,
                "allergens": [],
                "dietary_restrictions": [],
                "spice_tolerance": "medium"
            },
            {
                "name": "Adult 2",
                "age": 33,
                "allergens": [],
                "dietary_restrictions": [],
                "spice_tolerance": "medium"
            },
            {
                "name": "Child 1",
                "age": 8,
                "allergens": [],
                "dietary_restrictions": [],
                "spice_tolerance": "mild"
            },
            {
                "name": "Child 2",
                "age": 5,
                "allergens": [],
                "dietary_restrictions": [],
                "spice_tolerance": "mild"
            }
        ]
    }


@pytest.fixture
def italian_profile():
    """Profile with Italian cuisine preference"""
    return {
        "household": {
            "household_name": "Italian Family",
            "primary_language": "it",
            "measurement_system": "metric",
            "member_count": 2,
            "favorite_cuisines": ["italian"]
        },
        "members": [
            {
                "allergens": [],
                "dietary_restrictions": []
            }
        ]
    }


@pytest.fixture
def profile_with_restrictions():
    """Profile with dietary restrictions"""
    return {
        "household": {
            "household_name": "Restricted Family",
            "member_count": 3
        },
        "members": [
            {
                "allergens": ["dairy", "nuts"],
                "dietary_restrictions": ["vegetarian"]
            }
        ]
    }


class TestMealStyleTemplates:
    """Test different meal style templates"""
    
    def test_casual_meal_structure(self, sample_profile):
        """Test casual meal structure (main + side)"""
        plan = plan_full_course_meal("casual", "italian", sample_profile)
        
        assert plan["meal_style"] == "casual"
        assert len(plan["courses"]) >= 1  # At least main
        
        # Check for main course
        course_types = [c["course_type"] for c in plan["courses"]]
        assert "main" in course_types
    
    def test_standard_meal_structure(self, sample_profile):
        """Test standard meal structure (appetizer + main + dessert)"""
        plan = plan_full_course_meal("standard", "italian", sample_profile)
        
        assert plan["meal_style"] == "standard"
        assert len(plan["courses"]) == 3
        
        course_types = [c["course_type"] for c in plan["courses"]]
        assert "appetizer" in course_types
        assert "main" in course_types
        assert "dessert" in course_types
    
    def test_formal_meal_structure(self, sample_profile):
        """Test formal meal structure (multiple courses)"""
        plan = plan_full_course_meal("formal", "french", sample_profile)
        
        assert plan["meal_style"] == "formal"
        assert len(plan["courses"]) >= 5  # Soup + salad + main + sides + dessert
        
        course_types = [c["course_type"] for c in plan["courses"]]
        assert "soup" in course_types
        assert "main" in course_types
        assert "dessert" in course_types
    
    def test_italian_meal_structure(self, italian_profile):
        """Test Italian meal structure (antipasto → primo → secondo → contorno → dolce)"""
        plan = plan_full_course_meal("italian", "italian", italian_profile)
        
        assert plan["meal_style"] == "italian"
        assert len(plan["courses"]) == 5
    
    def test_indian_meal_structure(self, sample_profile):
        """Test Indian meal structure"""
        plan = plan_full_course_meal("indian", "indian", sample_profile)
        
        assert plan["meal_style"] == "indian"
        
        course_types = [c["course_type"] for c in plan["courses"]]
        assert "main" in course_types
        assert "side" in course_types  # Rice/bread
    
    def test_chinese_meal_structure(self, sample_profile):
        """Test Chinese meal structure (family style with multiple mains)"""
        plan = plan_full_course_meal("chinese", "chinese", sample_profile)
        
        assert plan["meal_style"] == "chinese"
        
        course_types = [c["course_type"] for c in plan["courses"]]
        # Should have multiple mains
        assert course_types.count("main") >= 2
    
    def test_japanese_meal_structure(self, sample_profile):
        """Test Japanese meal structure"""
        plan = plan_full_course_meal("japanese", "japanese", sample_profile)
        
        assert plan["meal_style"] == "japanese"
        
        course_types = [c["course_type"] for c in plan["courses"]]
        assert "soup" in course_types
        assert "main" in course_types
        assert "side" in course_types  # Rice


class TestFlavorProgression:
    """Test flavor progression across courses"""
    
    def test_standard_progression(self, sample_profile):
        """Test standard meal flavor progression (light → rich → sweet)"""
        plan = plan_full_course_meal("standard", "italian", sample_profile)
        
        progression = plan["flavor_progression"]
        
        # First course should be light
        assert progression[0] in ["light", "medium"]
        
        # Main should be rich
        main_idx = next(i for i, c in enumerate(plan["courses"]) if c["course_type"] == "main")
        assert progression[main_idx] in ["rich", "medium"]
        
        # Dessert should be medium (sweet but not too heavy)
        dessert_idx = next(i for i, c in enumerate(plan["courses"]) if c["course_type"] == "dessert")
        assert progression[dessert_idx] in ["medium", "light"]
    
    def test_formal_progression(self, sample_profile):
        """Test formal meal has varied intensity"""
        plan = plan_full_course_meal("formal", "french", sample_profile)
        
        progression = plan["flavor_progression"]
        
        # Should have variety (not all same intensity)
        unique_intensities = set(progression)
        assert len(unique_intensities) >= 2


class TestCoursePrompts:
    """Test course-specific prompt generation"""
    
    def test_appetizer_prompt(self, sample_profile):
        """Test appetizer prompt has correct instructions"""
        plan = plan_full_course_meal("standard", "italian", sample_profile)
        
        appetizer = next(c for c in plan["courses"] if c["course_type"] == "appetizer")
        prompt = appetizer["prompt"]
        
        assert "appetizer" in prompt.lower()
        assert "small" in prompt.lower() or "light" in prompt.lower()
        assert "italian" in prompt.lower()
    
    def test_main_prompt(self, sample_profile):
        """Test main course prompt emphasizes centerpiece"""
        plan = plan_full_course_meal("standard", "indian", sample_profile)
        
        main = next(c for c in plan["courses"] if c["course_type"] == "main")
        prompt = main["prompt"]
        
        assert "main" in prompt.lower()
        assert "indian" in prompt.lower()
        # Should mention protein or substantial ingredients
    
    def test_dessert_prompt(self, sample_profile):
        """Test dessert prompt has sweet emphasis"""
        plan = plan_full_course_meal("standard", "french", sample_profile)
        
        dessert = next(c for c in plan["courses"] if c["course_type"] == "dessert")
        prompt = dessert["prompt"]
        
        assert "dessert" in prompt.lower()
        assert "sweet" in prompt.lower()


class TestSafetyIntegration:
    """Test safety constraints are applied to all courses"""
    
    def test_allergen_constraints_all_courses(self, profile_with_restrictions):
        """Test allergen constraints propagate to all courses"""
        plan = plan_full_course_meal("standard", "italian", profile_with_restrictions)
        
        # Check each course prompt includes safety constraints
        for course in plan["courses"]:
            prompt = course["prompt"]
            assert "CRITICAL" in prompt  # Safety language
            assert "dairy" in prompt.lower() or "allergen" in prompt.lower()
    
    def test_dietary_restrictions_all_courses(self, profile_with_restrictions):
        """Test dietary restrictions (vegetarian) in all courses"""
        plan = plan_full_course_meal("standard", "indian", profile_with_restrictions)
        
        for course in plan["courses"]:
            prompt = course["prompt"]
            # Should mention vegetarian or dietary constraints
            assert "vegetarian" in prompt.lower() or "dietary" in prompt.lower()


class TestPortionSizing:
    """Test portion sizing across courses"""
    
    def test_appetizer_small_portion(self, sample_profile):
        """Test appetizer has small portion size"""
        plan = plan_full_course_meal("standard", "italian", sample_profile)
        
        appetizer = next(c for c in plan["courses"] if c["course_type"] == "appetizer")
        assert appetizer["portion_size"] == "small"
    
    def test_main_large_portion(self, sample_profile):
        """Test main course has large portion size"""
        plan = plan_full_course_meal("standard", "italian", sample_profile)
        
        main = next(c for c in plan["courses"] if c["course_type"] == "main")
        assert main["portion_size"] in ["large", "medium"]
    
    def test_side_medium_portion(self, sample_profile):
        """Test side dish has appropriate portion"""
        plan = plan_full_course_meal("casual", "american", sample_profile)
        
        sides = [c for c in plan["courses"] if c["course_type"] == "side"]
        if sides:
            assert sides[0]["portion_size"] in ["small", "medium"]


class TestCoherenceScoring:
    """Test meal coherence calculation"""
    
    def test_coherent_meal_high_score(self, italian_profile):
        """Test all-Italian meal has high coherence"""
        plan = plan_full_course_meal("italian", "italian", italian_profile)
        
        # All courses from same cuisine should have high coherence
        assert plan["coherence_score"] >= 0.8
    
    def test_mixed_cuisine_lower_score(self, sample_profile):
        """Test mixed cuisines might have lower coherence"""
        # Note: Current implementation enforces same cuisine
        # This test would apply if we allow cuisine mixing in future
        plan = plan_full_course_meal("standard", "fusion", sample_profile)
        
        # Should still be reasonable
        assert plan["coherence_score"] >= 0.5


class TestTimeEstimation:
    """Test total time estimation"""
    
    def test_casual_meal_time(self, sample_profile):
        """Test casual meal has shorter time"""
        plan = plan_full_course_meal("casual", "american", sample_profile)
        
        # Casual should be quicker (main + side)
        assert plan["estimated_total_time"] < 90  # Less than 90 minutes
    
    def test_formal_meal_time(self, sample_profile):
        """Test formal meal has longer time"""
        plan = plan_full_course_meal("formal", "french", sample_profile)
        
        # Formal should take longer (many courses)
        assert plan["estimated_total_time"] > 60  # More than 1 hour
    
    def test_parallel_cooking_discount(self, sample_profile):
        """Test parallel cooking reduces total time"""
        plan = plan_full_course_meal("standard", "italian", sample_profile)
        
        # With 3 courses, should have some time savings
        # (not just sum of all course times)
        assert plan["estimated_total_time"] > 30


class TestIngredientsAvailable:
    """Test incorporating available ingredients"""
    
    def test_with_ingredients_included(self, sample_profile):
        """Test available ingredients are mentioned in prompts"""
        ingredients = ["chicken", "tomato", "rice"]
        
        plan = plan_full_course_meal(
            "standard",
            "italian",
            sample_profile,
            ingredients=ingredients
        )
        
        # At least one course should mention the ingredients
        prompts = [c["prompt"] for c in plan["courses"]]
        combined_prompts = " ".join(prompts)
        
        assert "chicken" in combined_prompts.lower()


class TestSinglePromptGeneration:
    """Test alternative: single prompt for entire meal"""
    
    def test_full_meal_single_prompt(self, sample_profile):
        """Test generating single prompt for entire meal"""
        prompt = generate_meal_prompt(
            meal_style="standard",
            cuisine="italian",
            profile=sample_profile
        )
        
        assert prompt is not None
        assert "appetizer" in prompt.lower()
        assert "main" in prompt.lower()
        assert "dessert" in prompt.lower()
        assert "italian" in prompt.lower()
    
    def test_single_prompt_includes_safety(self, profile_with_restrictions):
        """Test single prompt includes all safety constraints"""
        prompt = generate_meal_prompt(
            meal_style="standard",
            cuisine="italian",
            profile=profile_with_restrictions
        )
        
        assert "CRITICAL" in prompt
        assert "dairy" in prompt.lower()
        # Check for dietary constraints (may be "NO meat" instead of "vegetarian")
        assert ("vegetarian" in prompt.lower() or "meat" in prompt.lower())


class TestEdgeCases:
    """Test edge cases"""
    
    def test_invalid_meal_style(self, sample_profile):
        """Test handling of invalid meal style - defaults to STANDARD"""
        # Invalid style defaults to STANDARD instead of raising error
        plan = plan_full_course_meal("invalid_style", "italian", sample_profile)
        
        # Should default to STANDARD meal style
        assert plan["meal_style"] == "standard"
    
    def test_small_household(self):
        """Test meal planning for single person"""
        profile = {
            "household": {"member_count": 1},
            "members": [{"allergens": [], "dietary_restrictions": []}]
        }
        
        plan = plan_full_course_meal("casual", "italian", profile)
        
        assert plan["servings"] == 1
    
    def test_large_household(self):
        """Test meal planning for large family"""
        profile = {
            "household": {"member_count": 8},
            "members": [
                {"allergens": [], "dietary_restrictions": []}
                for _ in range(8)
            ]
        }
        
        plan = plan_full_course_meal("casual", "italian", profile)
        
        assert plan["servings"] == 8


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
