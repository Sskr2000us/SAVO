"""
Tests for Cultural Intelligence Module
Tests cultural knowledge retrieval and prompt building
"""

import pytest
from app.core.cultural_intelligence import (
    get_cultural_context,
    build_cultural_intelligence_prompt,
    get_cultural_intelligence_for_combination,
    CULTURAL_COMBINATIONS
)


class TestCulturalKnowledge:
    """Test cultural knowledge base retrieval"""
    
    def test_south_indian_combination_exists(self):
        """Test that South Indian black channa + tamarind + eggplant exists"""
        context = get_cultural_context(['black_channa', 'tamarind', 'eggplant'])
        
        assert context is not None
        assert context['region'] == 'South India'
        assert 'why_beloved' in context
        assert len(context['why_beloved']) >= 7
        
    def test_italian_caprese_exists(self):
        """Test Italian tomato + mozzarella + basil"""
        context = get_cultural_context(['tomato', 'mozzarella', 'basil'])
        
        assert context is not None
        assert 'Italy' in context['region']
        assert 'why_beloved' in context
        assert len(context['why_beloved']) >= 4
        
    def test_north_indian_palak_paneer_exists(self):
        """Test North Indian paneer + spinach"""
        context = get_cultural_context(['paneer', 'spinach', 'cream'])
        
        assert context is not None
        assert 'North India' in context['region']
        assert 'why_beloved' in context
        assert len(context['why_beloved']) >= 4
        
    def test_chinese_trinity_exists(self):
        """Test Chinese soy sauce + ginger + garlic"""
        context = get_cultural_context(['soy_sauce', 'ginger', 'garlic'])
        
        assert context is not None
        assert 'China' in context['region']
        assert 'why_beloved' in context
        assert len(context['why_beloved']) >= 4
        
    def test_unknown_combination_returns_none(self):
        """Test that unknown combinations return None"""
        context = get_cultural_context(['chocolate', 'strawberry', 'vanilla'])
        assert context is None


class TestPromptBuilding:
    """Test cultural intelligence prompt generation"""
    
    def test_south_indian_prompt_includes_knowledge(self):
        """Test that prompt includes South Indian cultural knowledge"""
        prompt = build_cultural_intelligence_prompt(
            ['black_channa', 'tamarind', 'eggplant'],
            cuisine='South Indian'
        )
        
        assert 'CULTURAL INTELLIGENCE' in prompt
        assert 'South India' in prompt
        assert 'WHY THIS COMBINATION IS BELOVED' in prompt
        assert 'protein powerhouse' in prompt.lower()
        assert 'digestive aid' in prompt.lower()
        
    def test_unknown_combination_prompt_has_instructions(self):
        """Test that prompt for unknown combos has research instructions"""
        prompt = build_cultural_intelligence_prompt(
            ['chicken', 'lemon', 'oregano'],
            cuisine='Greek'
        )
        
        # Should not have traditional knowledge section
        assert 'WELL-KNOWN' not in prompt
        
        # Should have task instructions
        assert 'TASK' in prompt or 'identify' in prompt.lower()
        
    def test_prompt_always_requests_cultural_context(self):
        """Test that all prompts request cultural context"""
        prompt1 = build_cultural_intelligence_prompt(['tomato', 'mozzarella'], 'Italian')
        prompt2 = build_cultural_intelligence_prompt(['chicken', 'rice'], 'Chinese')
        
        assert 'why this combination is beloved' in prompt1.lower() or 'cultural significance' in prompt1.lower()
        assert 'why this combination is beloved' in prompt2.lower() or 'cultural significance' in prompt2.lower()


class TestAPIFriendlyFormat:
    """Test API-friendly cultural intelligence summaries"""
    
    def test_south_indian_summary(self):
        """Test API summary for South Indian combination"""
        summary = get_cultural_intelligence_for_combination(['black_channa', 'tamarind', 'eggplant'])
        
        assert summary is not None
        assert 'region' in summary
        assert 'why_beloved' in summary
        assert 'has_traditional_knowledge' in summary
        assert summary['has_traditional_knowledge'] == True
        assert len(summary['why_beloved']) >= 7
        
    def test_unknown_combination_returns_data(self):
        """Test that unknown combinations return prompt instructions"""
        summary = get_cultural_intelligence_for_combination(['random', 'ingredients'])
        assert summary is not None
        assert summary['has_traditional_knowledge'] == False
        assert 'cultural_prompt' in summary


class TestCulturalDepth:
    """Test depth and quality of cultural knowledge"""
    
    def test_south_indian_nutritional_wisdom(self):
        """Test nutritional wisdom depth for South Indian combo"""
        context = get_cultural_context(['black_channa', 'tamarind', 'eggplant'])
        
        nutrition = context['nutritional_wisdom']
        assert 'protein_fiber' in nutrition
        assert 'vitamin_c' in nutrition
        assert 'antioxidants' in nutrition
        assert 'low_calorie' in nutrition
        
    def test_south_indian_flavor_science(self):
        """Test flavor science depth"""
        context = get_cultural_context(['black_channa', 'tamarind', 'eggplant'])
        
        flavor = context['flavor_science']
        assert 'sour_umami' in flavor
        assert 'maillard' in flavor
        assert 'tempering' in flavor
        assert 'heat_balance' in flavor
        
    def test_regional_variations_exist(self):
        """Test that regional variations are captured"""
        context = get_cultural_context(['black_channa', 'tamarind', 'eggplant'])
        
        variations = context['regional_variations']
        assert 'andhra' in variations
        assert 'karnataka' in variations
        assert 'tamil_nadu' in variations
        assert 'kerala' in variations
        
        # Each variation should have description
        for region, style_desc in variations.items():
            assert isinstance(style_desc, str)
            assert len(style_desc) > 0


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_ingredients_list(self):
        """Test empty ingredients list"""
        context = get_cultural_context([])
        assert context is None
        
    def test_single_ingredient(self):
        """Test single ingredient (no combination)"""
        context = get_cultural_context(['tomato'])
        assert context is None
        
    def test_ingredient_order_doesnt_matter(self):
        """Test that ingredient order doesn't affect matching"""
        context1 = get_cultural_context(['black_channa', 'tamarind', 'eggplant'])
        context2 = get_cultural_context(['eggplant', 'black_channa', 'tamarind'])
        context3 = get_cultural_context(['tamarind', 'eggplant', 'black_channa'])
        
        assert context1 == context2 == context3
        
    def test_case_insensitive_matching(self):
        """Test that matching is case-insensitive"""
        context1 = get_cultural_context(['black_channa', 'tamarind', 'eggplant'])
        context2 = get_cultural_context(['Black_Channa', 'Tamarind', 'EGGPLANT'])
        
        assert context1 == context2


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
