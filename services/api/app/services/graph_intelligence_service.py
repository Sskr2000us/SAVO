"""
Graph Intelligence Service
Handles substitutions, confusion disambiguation, and ingredient pairings
"""

from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import asyncpg
from collections import defaultdict


class GraphIntelligenceService:
    """Service for graph-based ingredient intelligence"""
    
    def __init__(self):
        """Initialize graph intelligence service"""
        pass
    
    async def get_substitutions(
        self,
        conn,
        ingredient_id: str,
        context: Optional[Dict[str, Any]] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Find best substitutes for an ingredient
        
        Args:
            conn: Database connection
            ingredient_id: Source ingredient UUID
            context: Optional context (dish_type, cuisine, dietary_restrictions, form)
            limit: Maximum number of results
            
        Returns:
            List of substitution suggestions with scores and context
        """
        try:
            # Build query with optional context filters
            sql = """
                SELECT 
                    sub.id,
                    sub.target_ingredient_id,
                    mi.canonical_name,
                    mi.category,
                    mi.names,
                    mi.taste_profile,
                    mi.common_uses,
                    sub.substitution_type,
                    sub.similarity_score,
                    sub.applicable_forms,
                    sub.applicable_dishes,
                    sub.notes,
                    sub.user_acceptance_rate,
                    sub.times_suggested,
                    sub.times_accepted
                FROM ingredient_substitutions sub
                JOIN master_ingredients mi ON sub.target_ingredient_id = mi.id
                WHERE sub.source_ingredient_id = $1
            """
            
            params = [ingredient_id]
            param_idx = 2
            
            # Add context filters
            if context:
                # Filter by applicable form (fresh, dried, powdered)
                if context.get("form"):
                    sql += f" AND $2 = ANY(sub.applicable_forms)"
                    params.append(context["form"])
                    param_idx += 1
                
                # Filter by dish type
                if context.get("dish_type"):
                    sql += f" AND ${param_idx} = ANY(sub.applicable_dishes)"
                    params.append(context["dish_type"])
                    param_idx += 1
            
            # Order by similarity and acceptance rate
            sql += """
                ORDER BY 
                    sub.similarity_score DESC,
                    sub.user_acceptance_rate DESC NULLS LAST,
                    sub.times_accepted DESC
                LIMIT $""" + str(param_idx)
            params.append(limit)
            
            results = await conn.fetch(sql, *params)
            
            # Format results
            substitutions = []
            for row in results:
                substitutions.append({
                    "substitution_id": str(row["id"]),
                    "ingredient_id": str(row["target_ingredient_id"]),
                    "canonical_name": row["canonical_name"],
                    "category": row["category"],
                    "names": row["names"],
                    "taste_profile": row["taste_profile"],
                    "common_uses": row["common_uses"],
                    "substitution_type": row["substitution_type"],
                    "similarity_score": float(row["similarity_score"]),
                    "applicable_forms": row["applicable_forms"],
                    "applicable_dishes": row["applicable_dishes"],
                    "notes": row["notes"],
                    "user_acceptance_rate": float(row["user_acceptance_rate"]) if row["user_acceptance_rate"] else None,
                    "usage_stats": {
                        "times_suggested": row["times_suggested"],
                        "times_accepted": row["times_accepted"]
                    }
                })
            
            return substitutions
            
        except Exception as e:
            print(f"Error getting substitutions: {e}")
            return []
    
    async def resolve_confusion(
        self,
        conn,
        detected_ingredients: List[str],
        visual_features: Optional[Dict[str, Any]] = None,
        user_context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Disambiguate between commonly confused ingredients
        
        Args:
            conn: Database connection
            detected_ingredients: List of ingredient IDs that might be confused
            visual_features: Optional visual features from image (colors, texture, etc.)
            user_context: Optional user context (location, cuisine preference)
            
        Returns:
            Disambiguation result with recommendations and differentiating factors
        """
        if len(detected_ingredients) < 2:
            return {
                "needs_disambiguation": False,
                "detected_count": len(detected_ingredients)
            }
        
        try:
            # Find confusion pairs
            confusion_data = []
            
            for i, ing_a in enumerate(detected_ingredients):
                for ing_b in detected_ingredients[i+1:]:
                    # Check if confusion exists
                    result = await conn.fetchrow("""
                        SELECT 
                            conf.id,
                            conf.confusion_reason,
                            conf.confusion_frequency,
                            conf.disambiguation_rules,
                            conf.key_visual_differences,
                            mi_a.canonical_name as ingredient_a_name,
                            mi_b.canonical_name as ingredient_b_name
                        FROM ingredient_confusion conf
                        JOIN master_ingredients mi_a ON conf.ingredient_a_id = mi_a.id
                        JOIN master_ingredients mi_b ON conf.ingredient_b_id = mi_b.id
                        WHERE (conf.ingredient_a_id = $1 AND conf.ingredient_b_id = $2)
                           OR (conf.ingredient_a_id = $2 AND conf.ingredient_b_id = $1)
                    """, ing_a, ing_b)
                    
                    if result:
                        confusion_data.append({
                            "confusion_id": str(result["id"]),
                            "ingredient_a": ing_a,
                            "ingredient_b": ing_b,
                            "ingredient_a_name": result["ingredient_a_name"],
                            "ingredient_b_name": result["ingredient_b_name"],
                            "confusion_reason": result["confusion_reason"],
                            "confusion_frequency": result["confusion_frequency"],
                            "disambiguation_rules": result["disambiguation_rules"],
                            "key_visual_differences": result["key_visual_differences"]
                        })
            
            if not confusion_data:
                return {
                    "needs_disambiguation": False,
                    "detected_count": len(detected_ingredients),
                    "message": "No known confusion patterns between detected ingredients"
                }
            
            # Apply disambiguation rules
            recommendations = []
            
            for confusion in confusion_data:
                recommendation = {
                    "confused_pair": [
                        confusion["ingredient_a_name"],
                        confusion["ingredient_b_name"]
                    ],
                    "reason": confusion["confusion_reason"],
                    "disambiguation_tips": confusion["disambiguation_rules"],
                    "visual_differences": confusion["key_visual_differences"],
                    "confidence": "medium"
                }
                
                # Apply visual feature matching if available
                if visual_features:
                    # Check dominant colors
                    if visual_features.get("dominant_colors"):
                        for diff in confusion["key_visual_differences"]:
                            if any(color in diff.lower() for color in visual_features["dominant_colors"]):
                                recommendation["matched_visual_clue"] = diff
                                recommendation["confidence"] = "high"
                
                recommendations.append(recommendation)
            
            return {
                "needs_disambiguation": True,
                "detected_count": len(detected_ingredients),
                "confusion_patterns": len(confusion_data),
                "recommendations": recommendations
            }
            
        except Exception as e:
            print(f"Error resolving confusion: {e}")
            return {
                "needs_disambiguation": False,
                "error": str(e)
            }
    
    async def get_pairings(
        self,
        conn,
        ingredient_ids: List[str],
        cuisine_type: Optional[str] = None,
        dish_type: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Get complementary ingredient pairing suggestions
        
        Args:
            conn: Database connection
            ingredient_ids: List of ingredient IDs to find pairings for
            cuisine_type: Optional cuisine filter (indian, italian, chinese, etc.)
            dish_type: Optional dish type filter (curry, pasta, stir_fry, etc.)
            limit: Maximum number of suggestions
            
        Returns:
            List of ingredient pairing suggestions
        """
        if not ingredient_ids:
            return []
        
        try:
            # Get pairings for all provided ingredients
            sql = """
                SELECT 
                    pair.id,
                    pair.ingredient_a_id,
                    pair.ingredient_b_id,
                    mi_a.canonical_name as ingredient_a_name,
                    mi_b.canonical_name as ingredient_b_name,
                    mi_b.category as ingredient_b_category,
                    mi_b.names as ingredient_b_names,
                    mi_b.taste_profile,
                    pair.pairing_score,
                    pair.pairing_type,
                    pair.cuisine_types,
                    pair.dish_types,
                    pair.source,
                    pair.times_used_together
                FROM ingredient_pairings pair
                JOIN master_ingredients mi_a ON pair.ingredient_a_id = mi_a.id
                JOIN master_ingredients mi_b ON pair.ingredient_b_id = mi_b.id
                WHERE pair.ingredient_a_id = ANY($1)
                   OR pair.ingredient_b_id = ANY($1)
            """
            
            params = [ingredient_ids]
            param_idx = 2
            
            # Add cuisine filter
            if cuisine_type:
                sql += f" AND ${param_idx} = ANY(pair.cuisine_types)"
                params.append(cuisine_type)
                param_idx += 1
            
            # Add dish type filter
            if dish_type:
                sql += f" AND ${param_idx} = ANY(pair.dish_types)"
                params.append(dish_type)
                param_idx += 1
            
            sql += f"""
                ORDER BY 
                    pair.pairing_score DESC,
                    pair.times_used_together DESC
                LIMIT ${param_idx}
            """
            params.append(limit)
            
            results = await conn.fetch(sql, *params)
            
            # Deduplicate and format results
            seen_ingredients = set(ingredient_ids)
            pairings = []
            
            for row in results:
                # Determine which ingredient is the new suggestion
                if str(row["ingredient_a_id"]) in ingredient_ids:
                    suggested_id = str(row["ingredient_b_id"])
                    suggested_name = row["ingredient_b_name"]
                    suggested_category = row["ingredient_b_category"]
                    suggested_names = row["ingredient_b_names"]
                    suggested_taste = row["taste_profile"]
                else:
                    # Ingredient B is in our list, so A is the suggestion
                    continue  # Skip to avoid duplicates
                
                # Skip if already suggested
                if suggested_id in seen_ingredients:
                    continue
                
                seen_ingredients.add(suggested_id)
                
                pairings.append({
                    "pairing_id": str(row["id"]),
                    "ingredient_id": suggested_id,
                    "canonical_name": suggested_name,
                    "category": suggested_category,
                    "names": suggested_names,
                    "taste_profile": suggested_taste,
                    "pairing_score": float(row["pairing_score"]),
                    "pairing_type": row["pairing_type"],
                    "cuisine_types": row["cuisine_types"],
                    "dish_types": row["dish_types"],
                    "source": row["source"],
                    "times_used_together": row["times_used_together"]
                })
            
            return pairings
            
        except Exception as e:
            print(f"Error getting pairings: {e}")
            return []
    
    async def calculate_recipe_compatibility(
        self,
        conn,
        ingredient_ids: List[str],
        cuisine_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Calculate how well a set of ingredients work together
        
        Args:
            conn: Database connection
            ingredient_ids: List of ingredient IDs in recipe
            cuisine_type: Optional cuisine context
            
        Returns:
            Compatibility score and analysis
        """
        if len(ingredient_ids) < 2:
            return {
                "compatibility_score": 1.0,
                "ingredient_count": len(ingredient_ids),
                "message": "Need at least 2 ingredients for compatibility analysis"
            }
        
        try:
            # Get all pairings between ingredients
            pairing_scores = []
            pairing_details = []
            
            for i, ing_a in enumerate(ingredient_ids):
                for ing_b in ingredient_ids[i+1:]:
                    result = await conn.fetchrow("""
                        SELECT 
                            pair.pairing_score,
                            pair.pairing_type,
                            pair.cuisine_types,
                            mi_a.canonical_name as ingredient_a_name,
                            mi_b.canonical_name as ingredient_b_name
                        FROM ingredient_pairings pair
                        JOIN master_ingredients mi_a ON pair.ingredient_a_id = mi_a.id
                        JOIN master_ingredients mi_b ON pair.ingredient_b_id = mi_b.id
                        WHERE (pair.ingredient_a_id = $1 AND pair.ingredient_b_id = $2)
                           OR (pair.ingredient_a_id = $2 AND pair.ingredient_b_id = $1)
                    """, ing_a, ing_b)
                    
                    if result:
                        score = float(result["pairing_score"])
                        pairing_scores.append(score)
                        pairing_details.append({
                            "ingredients": [
                                result["ingredient_a_name"],
                                result["ingredient_b_name"]
                            ],
                            "score": score,
                            "type": result["pairing_type"],
                            "cuisines": result["cuisine_types"]
                        })
            
            # Calculate overall compatibility
            if not pairing_scores:
                compatibility_score = 0.5  # Neutral if no known pairings
                confidence = "low"
            else:
                # Average pairing score
                compatibility_score = sum(pairing_scores) / len(pairing_scores)
                confidence = "high" if len(pairing_scores) >= len(ingredient_ids) else "medium"
            
            # Determine compatibility level
            if compatibility_score >= 0.8:
                compatibility_level = "excellent"
            elif compatibility_score >= 0.6:
                compatibility_level = "good"
            elif compatibility_score >= 0.4:
                compatibility_level = "fair"
            else:
                compatibility_level = "poor"
            
            return {
                "compatibility_score": round(compatibility_score, 3),
                "compatibility_level": compatibility_level,
                "confidence": confidence,
                "ingredient_count": len(ingredient_ids),
                "known_pairings": len(pairing_scores),
                "pairing_details": pairing_details
            }
            
        except Exception as e:
            print(f"Error calculating recipe compatibility: {e}")
            return {
                "compatibility_score": 0.0,
                "error": str(e)
            }
    
    async def optimize_grocery_list(
        self,
        conn,
        ingredient_ids: List[str],
        user_inventory: Optional[List[str]] = None,
        budget_constraint: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Optimize grocery list by suggesting substitutions and consolidations
        
        Args:
            conn: Database connection
            ingredient_ids: List of ingredients needed
            user_inventory: Optional list of ingredient IDs already owned
            budget_constraint: Optional budget limit
            
        Returns:
            Optimized grocery list with suggestions
        """
        user_inventory = user_inventory or []
        
        try:
            # Identify ingredients already in inventory
            already_have = [ing for ing in ingredient_ids if ing in user_inventory]
            need_to_buy = [ing for ing in ingredient_ids if ing not in user_inventory]
            
            # Get ingredient details for items to buy
            if need_to_buy:
                results = await conn.fetch("""
                    SELECT 
                        id,
                        canonical_name,
                        category,
                        names,
                        common_uses
                    FROM master_ingredients
                    WHERE id = ANY($1)
                """, need_to_buy)
                
                items_to_buy = [dict(row) for row in results]
            else:
                items_to_buy = []
            
            # Find consolidation opportunities (multiple items of same category)
            category_groups = defaultdict(list)
            for item in items_to_buy:
                category_groups[item["category"]].append(item)
            
            consolidation_suggestions = []
            for category, items in category_groups.items():
                if len(items) > 1:
                    consolidation_suggestions.append({
                        "category": category,
                        "items": [item["canonical_name"] for item in items],
                        "suggestion": f"Consider buying these {len(items)} {category.lower()} items together"
                    })
            
            # Find substitution opportunities for expensive/rare items
            substitution_suggestions = []
            for item_id in need_to_buy:
                # Check if cheaper/more available substitutes exist
                substitutes = await self.get_substitutions(
                    conn,
                    item_id,
                    context={"substitution_type": "emergency"},
                    limit=3
                )
                
                if substitutes:
                    substitution_suggestions.append({
                        "ingredient_id": item_id,
                        "alternatives": [
                            {
                                "name": sub["canonical_name"],
                                "similarity": sub["similarity_score"],
                                "type": sub["substitution_type"]
                            }
                            for sub in substitutes[:2]  # Top 2 alternatives
                        ]
                    })
            
            return {
                "total_ingredients": len(ingredient_ids),
                "already_have": len(already_have),
                "need_to_buy": len(need_to_buy),
                "items_to_buy": items_to_buy,
                "optimizations": {
                    "consolidation_opportunities": consolidation_suggestions,
                    "substitution_suggestions": substitution_suggestions
                },
                "estimated_savings": len(substitution_suggestions)  # Placeholder
            }
            
        except Exception as e:
            print(f"Error optimizing grocery list: {e}")
            return {
                "error": str(e)
            }
    
    async def record_substitution_feedback(
        self,
        conn,
        substitution_id: str,
        was_accepted: bool,
        feedback_note: Optional[str] = None
    ) -> bool:
        """
        Record user feedback on substitution suggestion
        
        Args:
            conn: Database connection
            substitution_id: UUID of substitution
            was_accepted: Whether user accepted the substitution
            feedback_note: Optional feedback text
            
        Returns:
            Success boolean
        """
        try:
            if was_accepted:
                await conn.execute("""
                    UPDATE ingredient_substitutions
                    SET times_accepted = times_accepted + 1,
                        times_suggested = times_suggested + 1,
                        user_acceptance_rate = 
                            ROUND((times_accepted + 1.0) / (times_suggested + 1.0), 2)
                    WHERE id = $1
                """, substitution_id)
            else:
                await conn.execute("""
                    UPDATE ingredient_substitutions
                    SET times_suggested = times_suggested + 1,
                        user_acceptance_rate = 
                            ROUND(times_accepted / (times_suggested + 1.0), 2)
                    WHERE id = $1
                """, substitution_id)
            
            return True
            
        except Exception as e:
            print(f"Error recording feedback: {e}")
            return False
