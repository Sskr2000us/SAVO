"""
SAVO — Full Course Meal Planning

Handles multi-course meal generation with:
- Course sequencing (appetizer → main → dessert)
- Flavor progression (light → rich → sweet)
- Cultural coherence (all courses from compatible cuisines)
- Nutritional balance across courses
- Portion size adjustment
- Safety constraint integration

Author: SAVO Team
Date: January 2, 2026
"""

from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CourseType(Enum):
    """Types of meal courses"""
    APPETIZER = "appetizer"
    SOUP = "soup"
    SALAD = "salad"
    MAIN = "main"
    SIDE = "side"
    DESSERT = "dessert"
    BEVERAGE = "beverage"


class MealStyle(Enum):
    """Dining styles with different course structures"""
    CASUAL = "casual"  # Main + side
    STANDARD = "standard"  # Appetizer + main + dessert
    FORMAL = "formal"  # Soup + salad + main + sides + dessert
    ITALIAN = "italian"  # Antipasto + primo + secondo + contorno + dolce
    FRENCH = "french"  # Entrée + plat principal + fromage + dessert
    INDIAN = "indian"  # Starter + main + rice/bread + dessert
    CHINESE = "chinese"  # Multiple mains + rice (family style)
    JAPANESE = "japanese"  # Soup + main + pickles + rice


@dataclass
class CourseTemplate:
    """Template for a course in a meal"""
    course_type: CourseType
    required: bool
    portion_size: str  # "small", "medium", "large"
    flavor_profile: List[str]  # Expected flavors
    intensity: str  # "light", "medium", "rich"


# Meal structure templates
MEAL_TEMPLATES = {
    MealStyle.CASUAL: [
        CourseTemplate(CourseType.MAIN, required=True, portion_size="large", 
                      flavor_profile=["savory"], intensity="medium"),
        CourseTemplate(CourseType.SIDE, required=False, portion_size="medium",
                      flavor_profile=["savory", "fresh"], intensity="light"),
    ],
    
    MealStyle.STANDARD: [
        CourseTemplate(CourseType.APPETIZER, required=True, portion_size="small",
                      flavor_profile=["fresh", "light", "savory"], intensity="light"),
        CourseTemplate(CourseType.MAIN, required=True, portion_size="large",
                      flavor_profile=["savory", "rich"], intensity="rich"),
        CourseTemplate(CourseType.DESSERT, required=True, portion_size="medium",
                      flavor_profile=["sweet"], intensity="medium"),
    ],
    
    MealStyle.FORMAL: [
        CourseTemplate(CourseType.SOUP, required=True, portion_size="small",
                      flavor_profile=["savory", "light"], intensity="light"),
        CourseTemplate(CourseType.SALAD, required=True, portion_size="small",
                      flavor_profile=["fresh", "acidic"], intensity="light"),
        CourseTemplate(CourseType.MAIN, required=True, portion_size="large",
                      flavor_profile=["savory", "rich"], intensity="rich"),
        CourseTemplate(CourseType.SIDE, required=True, portion_size="medium",
                      flavor_profile=["savory"], intensity="medium"),
        CourseTemplate(CourseType.SIDE, required=True, portion_size="medium",
                      flavor_profile=["fresh"], intensity="light"),
        CourseTemplate(CourseType.DESSERT, required=True, portion_size="medium",
                      flavor_profile=["sweet"], intensity="medium"),
    ],
    
    MealStyle.ITALIAN: [
        CourseTemplate(CourseType.APPETIZER, required=True, portion_size="small",
                      flavor_profile=["savory", "light"], intensity="light"),
        CourseTemplate(CourseType.MAIN, required=True, portion_size="medium",
                      flavor_profile=["pasta", "risotto"], intensity="medium"),
        CourseTemplate(CourseType.MAIN, required=True, portion_size="large",
                      flavor_profile=["protein", "rich"], intensity="rich"),
        CourseTemplate(CourseType.SIDE, required=True, portion_size="small",
                      flavor_profile=["vegetable"], intensity="light"),
        CourseTemplate(CourseType.DESSERT, required=True, portion_size="small",
                      flavor_profile=["sweet"], intensity="light"),
    ],
    
    MealStyle.INDIAN: [
        CourseTemplate(CourseType.APPETIZER, required=False, portion_size="small",
                      flavor_profile=["savory", "spicy"], intensity="light"),
        CourseTemplate(CourseType.MAIN, required=True, portion_size="large",
                      flavor_profile=["curry", "rich"], intensity="rich"),
        CourseTemplate(CourseType.SIDE, required=True, portion_size="medium",
                      flavor_profile=["rice", "bread"], intensity="medium"),
        CourseTemplate(CourseType.SIDE, required=False, portion_size="small",
                      flavor_profile=["fresh", "yogurt"], intensity="light"),
        CourseTemplate(CourseType.DESSERT, required=False, portion_size="small",
                      flavor_profile=["sweet", "milk"], intensity="medium"),
    ],
    
    MealStyle.CHINESE: [
        CourseTemplate(CourseType.APPETIZER, required=False, portion_size="small",
                      flavor_profile=["savory"], intensity="light"),
        CourseTemplate(CourseType.MAIN, required=True, portion_size="medium",
                      flavor_profile=["savory", "umami"], intensity="medium"),
        CourseTemplate(CourseType.MAIN, required=True, portion_size="medium",
                      flavor_profile=["savory", "varied"], intensity="medium"),
        CourseTemplate(CourseType.SIDE, required=True, portion_size="large",
                      flavor_profile=["rice", "neutral"], intensity="medium"),
        CourseTemplate(CourseType.SOUP, required=False, portion_size="small",
                      flavor_profile=["light"], intensity="light"),
    ],
    
    MealStyle.JAPANESE: [
        CourseTemplate(CourseType.SOUP, required=True, portion_size="small",
                      flavor_profile=["umami", "light"], intensity="light"),
        CourseTemplate(CourseType.MAIN, required=True, portion_size="medium",
                      flavor_profile=["savory", "umami"], intensity="medium"),
        CourseTemplate(CourseType.SIDE, required=True, portion_size="small",
                      flavor_profile=["pickled", "acidic"], intensity="light"),
        CourseTemplate(CourseType.SIDE, required=True, portion_size="medium",
                      flavor_profile=["rice"], intensity="medium"),
    ],
}


# Cuisine compatibility matrix (which cuisines work well together in multi-course meals)
CUISINE_COMPATIBILITY = {
    "italian": ["mediterranean", "french", "italian"],
    "indian": ["south_asian", "indian", "nepali", "pakistani"],
    "chinese": ["chinese", "asian", "thai", "vietnamese"],
    "japanese": ["japanese", "asian", "korean"],
    "mexican": ["mexican", "latin_american", "spanish"],
    "french": ["french", "european", "italian"],
    "thai": ["thai", "vietnamese", "asian"],
    "mediterranean": ["greek", "italian", "middle_eastern"],
    "middle_eastern": ["lebanese", "turkish", "mediterranean"],
}


class MealCourseEngine:
    """
    Engine for planning full course meals with cultural coherence
    and flavor progression.
    """
    
    def __init__(self):
        self.templates = MEAL_TEMPLATES
        self.compatibility = CUISINE_COMPATIBILITY
    
    def plan_meal(
        self,
        meal_style: MealStyle,
        primary_cuisine: str,
        profile: dict,
        ingredients_available: Optional[List[str]] = None
    ) -> Dict:
        """
        Plan a full course meal.
        
        Args:
            meal_style: Type of meal (CASUAL, STANDARD, FORMAL, etc.)
            primary_cuisine: Primary cuisine for the meal
            profile: User profile with dietary restrictions
            ingredients_available: Optional list of ingredients to use
        
        Returns:
            {
                "meal_style": str,
                "cuisine": str,
                "courses": [
                    {
                        "course_type": str,
                        "required": bool,
                        "prompt": str,  # AI prompt for this course
                        "constraints": dict
                    }
                ],
                "flavor_progression": list,
                "estimated_total_time": int,
                "servings": int,
                "coherence_score": float
            }
        """
        
        # Get template for meal style
        template = self.templates.get(meal_style)
        if not template:
            raise ValueError(f"Unknown meal style: {meal_style}")
        
        # Build courses
        courses = []
        for course_template in template:
            course = self._build_course(
                course_template,
                primary_cuisine,
                profile,
                ingredients_available,
                len(courses)  # Course index for progression
            )
            courses.append(course)
        
        # Calculate flavor progression
        flavor_progression = [
            c["course_template"].intensity 
            for c in courses
        ]
        
        # Calculate coherence score
        coherence_score = self._calculate_coherence(courses, primary_cuisine)
        
        # Estimate total time
        estimated_total_time = self._estimate_total_time(courses)
        
        return {
            "meal_style": meal_style.value,
            "cuisine": primary_cuisine,
            "courses": [
                {
                    "course_type": c["course_type"],
                    "required": c["required"],
                    "prompt": c["prompt"],
                    "constraints": c["constraints"],
                    "portion_size": c["portion_size"]
                }
                for c in courses
            ],
            "flavor_progression": flavor_progression,
            "estimated_total_time": estimated_total_time,
            "servings": profile.get("household", {}).get("member_count", 4),
            "coherence_score": coherence_score
        }
    
    def _build_course(
        self,
        template: CourseTemplate,
        cuisine: str,
        profile: dict,
        ingredients: Optional[List[str]],
        course_index: int
    ) -> Dict:
        """Build a single course with AI prompt"""
        
        from .safety_constraints import build_complete_safety_context
        
        # Get safety constraints
        safety_context = build_complete_safety_context(profile)
        
        # Build course-specific context
        course_context = f"""
COURSE INFORMATION:
- Course type: {template.course_type.value.upper()}
- Position in meal: {course_index + 1} (flavor progression: {template.intensity})
- Portion size: {template.portion_size.upper()}
- Expected flavors: {', '.join(template.flavor_profile)}
- Cuisine: {cuisine}
"""
        
        if ingredients:
            course_context += f"- Available ingredients to use: {', '.join(ingredients)}\n"
        
        # Add course-specific instructions
        course_instructions = self._get_course_instructions(
            template.course_type,
            cuisine,
            template.intensity
        )
        
        prompt = f"""
You are SAVO, an AI cooking assistant creating a {template.course_type.value} for a multi-course meal.

{safety_context}

{course_context}

{course_instructions}

CRITICAL RULES:
1. This is part of a multi-course meal - adjust portions appropriately
2. Match the {cuisine} cuisine style consistently
3. Follow the {template.intensity} intensity level (don't overwhelm or underwhelm)
4. STRICTLY respect all allergen and dietary constraints
5. Consider flavor progression (this course should flow with others)

Format response as JSON with: title, description, ingredients (with quantities),
steps (numbered), prep_time, cook_time, servings, difficulty, serving_suggestions

Generate the {template.course_type.value} recipe now:
"""
        
        return {
            "course_type": template.course_type.value,
            "course_template": template,
            "required": template.required,
            "portion_size": template.portion_size,
            "prompt": prompt,
            "constraints": {
                "intensity": template.intensity,
                "flavor_profile": template.flavor_profile,
                "cuisine": cuisine
            }
        }
    
    def _get_course_instructions(
        self,
        course_type: CourseType,
        cuisine: str,
        intensity: str
    ) -> str:
        """Get course-specific instructions"""
        
        instructions = {
            CourseType.APPETIZER: f"""
APPETIZER INSTRUCTIONS:
- Create a {cuisine} appetizer that awakens the palate
- Keep it {intensity} - don't fill people up
- Focus on fresh, bright flavors
- Serve size: 2-3 bites per person or small plate
- Examples for {cuisine}: {"bruschetta, caprese" if cuisine == "italian" else "samosa, pakora" if cuisine == "indian" else "spring rolls" if cuisine == "chinese" else "edamame" if cuisine == "japanese" else "appropriate starter"}
""",
            CourseType.SOUP: f"""
SOUP INSTRUCTIONS:
- Create a {cuisine} soup that is {intensity} in body
- Clear or light soups work best as starters
- Serve size: 1 cup (8oz) per person
- Should be sippable, not too filling
- Examples: {"minestrone" if cuisine == "italian" else "rasam" if cuisine == "indian" else "wonton soup" if cuisine == "chinese" else "miso soup" if cuisine == "japanese" else "appropriate soup"}
""",
            CourseType.SALAD: f"""
SALAD INSTRUCTIONS:
- Create a fresh {cuisine} salad
- Use crisp, fresh vegetables
- Light dressing that complements but doesn't overpower
- Serve size: side salad portion (1.5 cups)
- Should cleanse the palate
""",
            CourseType.MAIN: f"""
MAIN COURSE INSTRUCTIONS:
- Create a {cuisine} main dish
- This is the centerpiece - make it {intensity} and satisfying
- Include protein and substantial ingredients
- Serve size: Main portion (8-10oz protein equivalent)
- Should showcase the cuisine's signature flavors
- Examples: {"chicken parmigiana, risotto" if cuisine == "italian" else "butter chicken, biryani" if cuisine == "indian" else "kung pao chicken" if cuisine == "chinese" else "teriyaki salmon" if cuisine == "japanese" else "signature main"}
""",
            CourseType.SIDE: f"""
SIDE DISH INSTRUCTIONS:
- Create a {cuisine} side dish
- Complement the main course, don't compete
- Intensity: {intensity}
- Serve size: 1/2 to 1 cup per person
- Examples: {"roasted vegetables" if cuisine == "italian" else "dal, raita" if cuisine == "indian" else "stir-fried vegetables" if cuisine == "chinese" else "pickled vegetables" if cuisine == "japanese" else "complementary side"}
""",
            CourseType.DESSERT: f"""
DESSERT INSTRUCTIONS:
- Create a {cuisine} dessert
- Sweet but not overly heavy after the meal
- Intensity: {intensity}
- Serve size: Small portion (satisfying but not overwhelming)
- Should provide a sweet ending without being too rich
- Examples: {"tiramisu, panna cotta" if cuisine == "italian" else "gulab jamun, kheer" if cuisine == "indian" else "mango pudding" if cuisine == "chinese" else "mochi, matcha ice cream" if cuisine == "japanese" else "traditional dessert"}
""",
            CourseType.BEVERAGE: f"""
BEVERAGE INSTRUCTIONS:
- Suggest a {cuisine} beverage pairing
- Consider meal intensity and flavors
- Can be alcoholic or non-alcoholic (check dietary restrictions)
- Should complement the meal courses
""",
        }
        
        return instructions.get(course_type, f"Create a {course_type.value} for a {cuisine} meal.")
    
    def _calculate_coherence(self, courses: List[Dict], cuisine: str) -> float:
        """
        Calculate how coherent the meal is (do all courses work together?)
        """
        
        # Check if all courses match cuisine compatibility
        compatible_cuisines = self.compatibility.get(cuisine, [cuisine])
        
        coherence_score = 1.0
        
        for course in courses:
            course_cuisine = course["constraints"]["cuisine"]
            if course_cuisine not in compatible_cuisines:
                coherence_score -= 0.2
        
        # Check flavor progression (should build from light to rich to sweet)
        expected_progression = ["light", "medium", "rich", "medium", "light"]
        actual_progression = [c["constraints"]["intensity"] for c in courses]
        
        # Simplified check: just ensure not all same intensity
        if len(set(actual_progression)) < 2:
            coherence_score -= 0.1
        
        return max(coherence_score, 0.0)
    
    def _estimate_total_time(self, courses: List[Dict]) -> int:
        """
        Estimate total time for all courses.
        Assumes some parallel cooking.
        """
        
        # Base times by course type (minutes)
        base_times = {
            "appetizer": 20,
            "soup": 30,
            "salad": 15,
            "main": 45,
            "side": 25,
            "dessert": 30,
        }
        
        total = 0
        for course in courses:
            course_type = course["course_type"]
            total += base_times.get(course_type, 30)
        
        # Apply parallel cooking discount (can make some things simultaneously)
        if len(courses) > 2:
            total = int(total * 0.7)  # 30% time savings from parallel prep
        
        return total
    
    def generate_full_meal_prompt(
        self,
        meal_style: MealStyle,
        cuisine: str,
        profile: dict,
        context: Optional[str] = None
    ) -> str:
        """
        Generate a single comprehensive prompt for entire meal.
        Alternative to course-by-course generation.
        """
        
        from .safety_constraints import build_complete_safety_context
        
        # Get safety context
        safety_context = build_complete_safety_context(profile)
        
        # Get template
        template = self.templates.get(meal_style)
        course_list = [f"- {t.course_type.value.title()}: {t.portion_size} portion, {t.intensity} intensity" 
                      for t in template]
        courses_description = "\n".join(course_list)
        
        prompt = f"""
You are SAVO, an AI cooking assistant planning a complete {meal_style.value} {cuisine} meal.

{safety_context}

MEAL STRUCTURE:
Style: {meal_style.value.upper()}
Cuisine: {cuisine.upper()}
Courses to create:
{courses_description}

{f"ADDITIONAL CONTEXT:\n{context}\n" if context else ""}

MEAL PLANNING INSTRUCTIONS:
1. Create a cohesive {cuisine} meal with all courses working together
2. Ensure flavor progression: light → rich → sweet
3. No ingredient conflicts between courses
4. Adjust portion sizes so meal is satisfying but not overwhelming
5. STRICTLY respect all allergen and dietary constraints
6. Consider prep efficiency (what can be made ahead or in parallel)

Format response as JSON with:
{{
  "meal_name": "descriptive name",
  "cuisine": "{cuisine}",
  "courses": [
    {{
      "course_type": "appetizer/main/dessert/etc",
      "recipe": {{
        "title": "...",
        "description": "...",
        "ingredients": ["..."],
        "steps": ["..."],
        "prep_time": minutes,
        "cook_time": minutes,
        "servings": number,
        "difficulty": "easy/medium/hard"
      }}
    }}
  ],
  "prep_strategy": "which courses to prep first, parallel cooking tips",
  "serving_order": "timing recommendations",
  "total_time": estimated_minutes
}}

Generate the complete meal plan now:
"""
        
        return prompt


# Convenience functions for API usage
def plan_full_course_meal(
    meal_style: str,
    cuisine: str,
    profile: dict,
    ingredients: Optional[List[str]] = None
) -> Dict:
    """
    Plan a full course meal.
    
    Args:
        meal_style: "casual", "standard", "formal", "italian", etc.
        cuisine: Primary cuisine
        profile: User profile
        ingredients: Optional ingredients to incorporate
    
    Returns:
        Meal plan with course prompts
    """
    
    # Parse meal style
    try:
        style_enum = MealStyle(meal_style.lower())
    except ValueError:
        style_enum = MealStyle.STANDARD
    
    engine = MealCourseEngine()
    return engine.plan_meal(
        meal_style=style_enum,
        primary_cuisine=cuisine,
        profile=profile,
        ingredients_available=ingredients
    )


def generate_meal_prompt(
    meal_style: str,
    cuisine: str,
    profile: dict,
    context: Optional[str] = None
) -> str:
    """
    Generate single prompt for complete meal.
    
    Args:
        meal_style: "casual", "standard", "formal", etc.
        cuisine: Primary cuisine
        profile: User profile
        context: Additional user context
    
    Returns:
        Complete meal generation prompt
    """
    
    try:
        style_enum = MealStyle(meal_style.lower())
    except ValueError:
        style_enum = MealStyle.STANDARD
    
    engine = MealCourseEngine()
    return engine.generate_full_meal_prompt(
        meal_style=style_enum,
        cuisine=cuisine,
        profile=profile,
        context=context
    )
