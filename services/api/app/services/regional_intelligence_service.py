"""
Regional Intelligence Service
Handles regional variants, cuisine recommendations, cultural context, and seasonal availability
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from collections import defaultdict
import asyncpg


class RegionalIntelligenceService:
    """Service for regional ingredient intelligence"""
    
    def __init__(self):
        """Initialize regional intelligence service"""
        # Define seasons for Northern Hemisphere (can be adjusted per region)
        self.seasons = {
            "winter": [12, 1, 2],
            "spring": [3, 4, 5],
            "summer": [6, 7, 8],
            "fall": [9, 10, 11]
        }
    
    async def get_regional_variants(
        self,
        conn,
        ingredient_id: str,
        user_region: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get regional variants of an ingredient
        
        Args:
            conn: Database connection
            ingredient_id: Ingredient UUID
            user_region: Optional user's region for filtering
            
        Returns:
            List of regional variants with cultural context
        """
        try:
            sql = """
                SELECT 
                    rv.id,
                    rv.region,
                    rv.country_code,
                    rv.variant_notes,
                    rv.flavor_differences,
                    rv.appearance_differences,
                    rv.typical_uses,
                    rv.is_native,
                    rv.availability_level,
                    mi.canonical_name as ingredient_name
                FROM ingredient_regional_variants rv
                JOIN master_ingredients mi ON rv.ingredient_id = mi.id
                WHERE rv.ingredient_id = $1
            """
            
            params = [ingredient_id]
            
            # Prioritize user's region if provided
            if user_region:
                sql += " ORDER BY CASE WHEN rv.region = $2 THEN 0 ELSE 1 END, rv.availability_level"
                params.append(user_region)
            else:
                sql += " ORDER BY rv.availability_level"
            
            results = await conn.fetch(sql, *params)
            
            variants = []
            for row in results:
                variants.append({
                    "variant_id": str(row["id"]),
                    "ingredient_name": row["ingredient_name"],
                    "region": row["region"],
                    "country_code": row["country_code"],
                    "variant_notes": row["variant_notes"],
                    "flavor_differences": row["flavor_differences"],
                    "appearance_differences": row["appearance_differences"],
                    "typical_uses": row["typical_uses"],
                    "is_native": row["is_native"],
                    "availability_level": row["availability_level"]
                })
            
            return variants
            
        except Exception as e:
            print(f"Error getting regional variants: {e}")
            return []
    
    async def get_cuisine_recommendations(
        self,
        conn,
        cuisine_type: str,
        user_region: Optional[str] = None,
        limit: int = 20
    ) -> Dict[str, Any]:
        """
        Get ingredient recommendations for a specific cuisine
        
        Args:
            conn: Database connection
            cuisine_type: Cuisine type (indian, chinese, italian, etc.)
            user_region: Optional user region for availability filtering
            limit: Maximum number of recommendations
            
        Returns:
            Categorized ingredient recommendations for the cuisine
        """
        try:
            # Get ingredients commonly used in this cuisine from pairings
            sql = """
                SELECT DISTINCT
                    mi.id,
                    mi.canonical_name,
                    mi.category,
                    mi.subcategory,
                    mi.names,
                    mi.common_uses,
                    mi.taste_profile,
                    rv.availability_level,
                    rv.is_native,
                    COUNT(*) OVER (PARTITION BY mi.id) as pairing_count
                FROM master_ingredients mi
                LEFT JOIN ingredient_pairings ip ON (mi.id = ip.ingredient_a_id OR mi.id = ip.ingredient_b_id)
                LEFT JOIN ingredient_regional_variants rv ON mi.id = rv.ingredient_id
                WHERE $1 = ANY(ip.cuisine_types)
            """
            
            params = [cuisine_type]
            
            # Filter by user region if provided
            if user_region:
                sql += " AND (rv.region = $2 OR rv.region IS NULL)"
                params.append(user_region)
            
            sql += """
                ORDER BY pairing_count DESC, rv.availability_level
                LIMIT $""" + str(len(params) + 1)
            params.append(limit)
            
            results = await conn.fetch(sql, *params)
            
            # Categorize by ingredient category
            categorized = defaultdict(list)
            
            for row in results:
                category = row["category"]
                categorized[category].append({
                    "id": str(row["id"]),
                    "canonical_name": row["canonical_name"],
                    "subcategory": row["subcategory"],
                    "names": row["names"],
                    "common_uses": row["common_uses"],
                    "taste_profile": row["taste_profile"],
                    "availability": row["availability_level"] or "unknown",
                    "is_native": row["is_native"] or False,
                    "pairing_count": row["pairing_count"]
                })
            
            return {
                "cuisine_type": cuisine_type,
                "user_region": user_region,
                "recommendations_by_category": dict(categorized),
                "total_ingredients": len(results)
            }
            
        except Exception as e:
            print(f"Error getting cuisine recommendations: {e}")
            return {
                "cuisine_type": cuisine_type,
                "recommendations_by_category": {},
                "error": str(e)
            }
    
    async def get_cultural_context(
        self,
        conn,
        ingredient_id: str,
        cuisine_type: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get cultural context for an ingredient
        
        Args:
            conn: Database connection
            ingredient_id: Ingredient UUID
            cuisine_type: Optional cuisine filter
            
        Returns:
            Cultural context including uses, regional significance, pairings
        """
        try:
            # Get ingredient details
            ingredient = await conn.fetchrow("""
                SELECT 
                    id,
                    canonical_name,
                    category,
                    names,
                    common_uses,
                    taste_profile,
                    typical_containers
                FROM master_ingredients
                WHERE id = $1
            """, ingredient_id)
            
            if not ingredient:
                return {"error": "Ingredient not found"}
            
            # Get regional variants
            variants = await self.get_regional_variants(conn, ingredient_id)
            
            # Get cuisine-specific pairings
            pairing_sql = """
                SELECT DISTINCT
                    ip.cuisine_types,
                    ip.dish_types,
                    ip.pairing_type,
                    mi.canonical_name as paired_ingredient
                FROM ingredient_pairings ip
                JOIN master_ingredients mi ON (
                    CASE 
                        WHEN ip.ingredient_a_id = $1 THEN ip.ingredient_b_id
                        ELSE ip.ingredient_a_id
                    END = mi.id
                )
                WHERE (ip.ingredient_a_id = $1 OR ip.ingredient_b_id = $1)
            """
            
            params = [ingredient_id]
            
            if cuisine_type:
                pairing_sql += " AND $2 = ANY(ip.cuisine_types)"
                params.append(cuisine_type)
            
            pairing_sql += " ORDER BY ip.pairing_score DESC LIMIT 10"
            
            pairings = await conn.fetch(pairing_sql, *params)
            
            # Organize cultural context
            cultural_pairings = defaultdict(list)
            for pairing in pairings:
                for cuisine in pairing["cuisine_types"]:
                    cultural_pairings[cuisine].append({
                        "paired_ingredient": pairing["paired_ingredient"],
                        "dish_types": pairing["dish_types"],
                        "pairing_type": pairing["pairing_type"]
                    })
            
            return {
                "ingredient_id": str(ingredient["id"]),
                "ingredient_name": ingredient["canonical_name"],
                "category": ingredient["category"],
                "multi_language_names": ingredient["names"],
                "common_uses": ingredient["common_uses"],
                "taste_profile": ingredient["taste_profile"],
                "regional_variants": variants,
                "cultural_pairings": dict(cultural_pairings),
                "cuisine_filter": cuisine_type
            }
            
        except Exception as e:
            print(f"Error getting cultural context: {e}")
            return {"error": str(e)}
    
    async def check_seasonal_availability(
        self,
        conn,
        ingredient_id: str,
        region: Optional[str] = None,
        month: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Check seasonal availability of ingredient
        
        Args:
            conn: Database connection
            ingredient_id: Ingredient UUID
            region: Optional region filter
            month: Optional month (1-12), defaults to current month
            
        Returns:
            Seasonal availability information
        """
        if month is None:
            month = datetime.now().month
        
        # Determine current season
        current_season = None
        for season, months in self.seasons.items():
            if month in months:
                current_season = season
                break
        
        try:
            # Get ingredient details
            ingredient = await conn.fetchrow("""
                SELECT 
                    canonical_name,
                    category,
                    subcategory
                FROM master_ingredients
                WHERE id = $1
            """, ingredient_id)
            
            if not ingredient:
                return {"error": "Ingredient not found"}
            
            # Get regional availability
            variants_sql = """
                SELECT 
                    region,
                    country_code,
                    availability_level,
                    is_native,
                    variant_notes
                FROM ingredient_regional_variants
                WHERE ingredient_id = $1
            """
            
            params = [ingredient_id]
            
            if region:
                variants_sql += " AND region = $2"
                params.append(region)
            
            variants = await conn.fetch(variants_sql, *params)
            
            # Determine seasonal status
            # For now, use heuristics based on category and regional data
            seasonal_info = self._determine_seasonal_status(
                ingredient["category"],
                ingredient["subcategory"],
                current_season,
                variants
            )
            
            return {
                "ingredient_name": ingredient["canonical_name"],
                "category": ingredient["category"],
                "month": month,
                "season": current_season,
                "availability_status": seasonal_info["status"],
                "availability_notes": seasonal_info["notes"],
                "regional_availability": [
                    {
                        "region": v["region"],
                        "country_code": v["country_code"],
                        "availability_level": v["availability_level"],
                        "is_native": v["is_native"],
                        "notes": v["variant_notes"]
                    }
                    for v in variants
                ],
                "best_season": seasonal_info.get("best_season"),
                "sourcing_recommendation": seasonal_info.get("recommendation")
            }
            
        except Exception as e:
            print(f"Error checking seasonal availability: {e}")
            return {"error": str(e)}
    
    def _determine_seasonal_status(
        self,
        category: str,
        subcategory: Optional[str],
        current_season: str,
        regional_variants: List[Any]
    ) -> Dict[str, Any]:
        """
        Determine seasonal status based on ingredient characteristics
        
        Args:
            category: Ingredient category
            subcategory: Ingredient subcategory
            current_season: Current season
            regional_variants: Regional variant data
            
        Returns:
            Seasonal status information
        """
        # Categorize by perishability and seasonality
        if category == "Vegetable":
            seasonal_vegetables = {
                "spring": ["spinach", "asparagus", "peas"],
                "summer": ["tomato", "bell_pepper", "eggplant", "cucumber"],
                "fall": ["potato", "carrot", "cauliflower", "pumpkin"],
                "winter": ["cabbage", "kale", "broccoli"]
            }
            
            # Check if subcategory matches seasonal vegetables
            if subcategory:
                for season, veggies in seasonal_vegetables.items():
                    if any(v in subcategory.lower() for v in veggies):
                        if season == current_season:
                            return {
                                "status": "in_season",
                                "notes": f"Peak season for {subcategory}",
                                "best_season": season,
                                "recommendation": "Buy fresh from local markets"
                            }
                        else:
                            return {
                                "status": "off_season",
                                "notes": f"Best in {season}, currently imported or stored",
                                "best_season": season,
                                "recommendation": "Consider frozen or wait for peak season"
                            }
            
            return {
                "status": "variable",
                "notes": "Availability depends on local growing conditions",
                "recommendation": "Check local markets for fresh options"
            }
        
        elif category == "Fruit":
            return {
                "status": "seasonal",
                "notes": "Most fruits have peak seasons",
                "recommendation": "Buy in season for best quality and price"
            }
        
        elif category in ["Spice", "Grain", "Oil", "Dairy"]:
            # These are typically available year-round
            has_native = any(v["is_native"] for v in regional_variants)
            
            if has_native:
                return {
                    "status": "year_round",
                    "notes": "Native to region, available year-round",
                    "recommendation": "Look for locally sourced options"
                }
            else:
                return {
                    "status": "year_round",
                    "notes": "Imported, available year-round",
                    "recommendation": "Standard availability in stores"
                }
        
        else:
            return {
                "status": "available",
                "notes": "Generally available",
                "recommendation": "Check local stores"
            }
    
    async def get_local_sourcing_suggestions(
        self,
        conn,
        ingredient_ids: List[str],
        user_region: str,
        current_month: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Get local sourcing suggestions for ingredients
        
        Args:
            conn: Database connection
            ingredient_ids: List of ingredient UUIDs
            user_region: User's region
            current_month: Optional month (1-12), defaults to current
            
        Returns:
            Sourcing suggestions with local/imported classification
        """
        if current_month is None:
            current_month = datetime.now().month
        
        try:
            # Get ingredients with regional data
            sql = """
                SELECT 
                    mi.id,
                    mi.canonical_name,
                    mi.category,
                    mi.names,
                    rv.region,
                    rv.availability_level,
                    rv.is_native,
                    rv.variant_notes
                FROM master_ingredients mi
                LEFT JOIN ingredient_regional_variants rv ON mi.id = rv.ingredient_id AND rv.region = $2
                WHERE mi.id = ANY($1)
            """
            
            results = await conn.fetch(sql, ingredient_ids, user_region)
            
            # Classify ingredients
            local_available = []
            imported_available = []
            seasonal_only = []
            
            for row in results:
                ingredient_data = {
                    "id": str(row["id"]),
                    "name": row["canonical_name"],
                    "category": row["category"],
                    "names": row["names"]
                }
                
                if row["is_native"] and row["availability_level"] in ["abundant", "common"]:
                    ingredient_data["availability"] = row["availability_level"]
                    ingredient_data["notes"] = row["variant_notes"]
                    local_available.append(ingredient_data)
                elif row["region"] == user_region:
                    ingredient_data["availability"] = row["availability_level"]
                    ingredient_data["sourcing"] = "imported"
                    imported_available.append(ingredient_data)
                else:
                    # Check seasonality
                    seasonal_info = await self.check_seasonal_availability(
                        conn, row["id"], user_region, current_month
                    )
                    
                    if seasonal_info.get("availability_status") == "in_season":
                        ingredient_data["availability"] = "seasonal"
                        ingredient_data["season_notes"] = seasonal_info.get("availability_notes")
                        seasonal_only.append(ingredient_data)
                    else:
                        ingredient_data["availability"] = "imported"
                        imported_available.append(ingredient_data)
            
            return {
                "user_region": user_region,
                "month": current_month,
                "local_available": local_available,
                "seasonal_available": seasonal_only,
                "imported_available": imported_available,
                "summary": {
                    "local_count": len(local_available),
                    "seasonal_count": len(seasonal_only),
                    "imported_count": len(imported_available),
                    "total_ingredients": len(ingredient_ids)
                },
                "recommendations": self._generate_sourcing_recommendations(
                    len(local_available),
                    len(seasonal_only),
                    len(imported_available)
                )
            }
            
        except Exception as e:
            print(f"Error getting sourcing suggestions: {e}")
            return {"error": str(e)}
    
    def _generate_sourcing_recommendations(
        self,
        local_count: int,
        seasonal_count: int,
        imported_count: int
    ) -> List[str]:
        """Generate sourcing recommendations based on availability"""
        recommendations = []
        
        if local_count > 0:
            recommendations.append(f"✓ {local_count} ingredients available locally - support local farmers!")
        
        if seasonal_count > 0:
            recommendations.append(f"🌱 {seasonal_count} seasonal ingredients - buy now for best quality!")
        
        if imported_count > 0:
            recommendations.append(f"📦 {imported_count} imported ingredients - check specialty stores")
        
        total = local_count + seasonal_count + imported_count
        local_percentage = (local_count / total * 100) if total > 0 else 0
        
        if local_percentage >= 70:
            recommendations.append("🏆 Excellent local sourcing - very sustainable!")
        elif local_percentage >= 40:
            recommendations.append("👍 Good mix of local and imported ingredients")
        else:
            recommendations.append("💡 Consider local alternatives for better sustainability")
        
        return recommendations
    
    async def compare_regional_cuisines(
        self,
        conn,
        cuisine_types: List[str],
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Compare ingredients across different regional cuisines
        
        Args:
            conn: Database connection
            cuisine_types: List of cuisine types to compare
            limit: Max ingredients per cuisine
            
        Returns:
            Comparison of ingredients across cuisines
        """
        try:
            cuisine_data = {}
            
            for cuisine in cuisine_types:
                # Get top ingredients for this cuisine
                results = await conn.fetch("""
                    SELECT DISTINCT
                        mi.canonical_name,
                        mi.category,
                        COUNT(*) as usage_frequency
                    FROM ingredient_pairings ip
                    JOIN master_ingredients mi ON (mi.id = ip.ingredient_a_id OR mi.id = ip.ingredient_b_id)
                    WHERE $1 = ANY(ip.cuisine_types)
                    GROUP BY mi.canonical_name, mi.category
                    ORDER BY usage_frequency DESC
                    LIMIT $2
                """, cuisine, limit)
                
                cuisine_data[cuisine] = [
                    {
                        "ingredient": row["canonical_name"],
                        "category": row["category"],
                        "frequency": row["usage_frequency"]
                    }
                    for row in results
                ]
            
            # Find common ingredients
            all_ingredients = defaultdict(set)
            for cuisine, ingredients in cuisine_data.items():
                for item in ingredients:
                    all_ingredients[item["ingredient"]].add(cuisine)
            
            common_ingredients = [
                {
                    "ingredient": ing,
                    "cuisines": list(cuisines),
                    "commonality": len(cuisines)
                }
                for ing, cuisines in all_ingredients.items()
                if len(cuisines) > 1
            ]
            
            common_ingredients.sort(key=lambda x: x["commonality"], reverse=True)
            
            return {
                "cuisines_compared": cuisine_types,
                "cuisine_specific_ingredients": cuisine_data,
                "common_ingredients": common_ingredients[:15],
                "total_common": len(common_ingredients)
            }
            
        except Exception as e:
            print(f"Error comparing cuisines: {e}")
            return {"error": str(e)}
