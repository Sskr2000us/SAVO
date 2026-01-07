"""
Waste Prevention Service
Handles spoilage prediction, expiry tracking, storage alerts, and waste analytics
"""

from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict
import asyncpg
from decimal import Decimal


class WastePreventionService:
    """Service for waste prevention and smart expiry management"""
    
    def __init__(self):
        """Initialize waste prevention service"""
        # Spoilage risk factors by category
        self.category_risk_levels = {
            "Vegetable": "high",
            "Fruit": "high",
            "Dairy": "high",
            "Protein": "high",
            "Herb": "very_high",
            "Spice": "low",
            "Grain": "low",
            "Oil": "medium",
            "Condiment": "medium"
        }
        
        # Storage condition requirements
        self.storage_requirements = {
            "Vegetable": {"temp_min": 1, "temp_max": 10, "humidity": "high", "light": "dark"},
            "Fruit": {"temp_min": 1, "temp_max": 15, "humidity": "medium", "light": "dark"},
            "Dairy": {"temp_min": 1, "temp_max": 4, "humidity": "low", "light": "dark"},
            "Protein": {"temp_min": -2, "temp_max": 4, "humidity": "low", "light": "dark"},
            "Herb": {"temp_min": 1, "temp_max": 7, "humidity": "high", "light": "dark"},
            "Spice": {"temp_min": 15, "temp_max": 25, "humidity": "low", "light": "dark"},
            "Grain": {"temp_min": 15, "temp_max": 25, "humidity": "low", "light": "dark"},
            "Oil": {"temp_min": 15, "temp_max": 25, "humidity": "low", "light": "dark"}
        }
    
    async def predict_spoilage(
        self,
        conn,
        inventory_item_id: str,
        current_storage_conditions: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Predict when an inventory item will spoil
        
        Args:
            conn: Database connection
            inventory_item_id: Inventory item UUID
            current_storage_conditions: Optional current storage temp/humidity
            
        Returns:
            Spoilage prediction with confidence and recommendations
        """
        try:
            # Get inventory item with ingredient details
            item = await conn.fetchrow("""
                SELECT 
                    ii.id,
                    ii.ingredient_id,
                    ii.quantity,
                    ii.unit,
                    ii.expiry_date,
                    ii.purchase_date,
                    ii.added_date,
                    ii.storage_location,
                    ii.notes,
                    mi.canonical_name,
                    mi.category,
                    mi.subcategory,
                    mi.storage_conditions,
                    mi.waste_risk_level,
                    mi.spoilage_signs
                FROM user_inventory ii
                JOIN master_ingredients mi ON ii.ingredient_id = mi.id
                WHERE ii.id = $1
            """, inventory_item_id)
            
            if not item:
                return {"error": "Inventory item not found"}
            
            # Calculate age
            purchase_date = item["purchase_date"] or item["added_date"]
            age_days = (datetime.now().date() - purchase_date).days
            
            # Get category risk level
            category = item["category"]
            base_risk = self.category_risk_levels.get(category, "medium")
            
            # Calculate days until expiry
            days_until_expiry = None
            if item["expiry_date"]:
                days_until_expiry = (item["expiry_date"] - datetime.now().date()).days
            
            # Determine spoilage prediction
            prediction = self._calculate_spoilage_prediction(
                category=category,
                subcategory=item["subcategory"],
                age_days=age_days,
                days_until_expiry=days_until_expiry,
                storage_location=item["storage_location"],
                current_conditions=current_storage_conditions,
                ideal_conditions=item["storage_conditions"]
            )
            
            return {
                "inventory_item_id": str(item["id"]),
                "ingredient_name": item["canonical_name"],
                "category": category,
                "age_days": age_days,
                "days_until_expiry": days_until_expiry,
                "spoilage_risk": prediction["risk_level"],
                "confidence": prediction["confidence"],
                "predicted_spoilage_date": prediction["predicted_date"],
                "days_until_spoilage": prediction["days_until_spoilage"],
                "storage_quality": prediction["storage_quality"],
                "recommendations": prediction["recommendations"],
                "warning_signs": item["spoilage_signs"] or [],
                "should_use_soon": prediction["urgent"]
            }
            
        except Exception as e:
            print(f"Error predicting spoilage: {e}")
            return {"error": str(e)}
    
    def _calculate_spoilage_prediction(
        self,
        category: str,
        subcategory: Optional[str],
        age_days: int,
        days_until_expiry: Optional[int],
        storage_location: Optional[str],
        current_conditions: Optional[Dict],
        ideal_conditions: Optional[Dict]
    ) -> Dict[str, Any]:
        """Calculate spoilage prediction based on multiple factors"""
        
        # Base shelf life by category (days from purchase)
        base_shelf_life = {
            "Vegetable": 7,
            "Fruit": 7,
            "Dairy": 7,
            "Protein": 3,
            "Herb": 5,
            "Spice": 365,
            "Grain": 180,
            "Oil": 90,
            "Condiment": 90
        }
        
        # Get base shelf life
        shelf_life = base_shelf_life.get(category, 14)
        
        # Adjust for subcategory
        if subcategory:
            if "potato" in subcategory.lower() or "onion" in subcategory.lower():
                shelf_life = 30  # Root vegetables last longer
            elif "leafy" in subcategory.lower() or "herb" in subcategory.lower():
                shelf_life = 5  # Leafy greens spoil faster
            elif "powder" in subcategory.lower() or "dried" in subcategory.lower():
                shelf_life = 180  # Dried forms last much longer
        
        # Use expiry date if available and shorter than predicted
        if days_until_expiry is not None:
            predicted_days = min(shelf_life - age_days, days_until_expiry)
        else:
            predicted_days = shelf_life - age_days
        
        # Assess storage conditions
        storage_quality = self._assess_storage_conditions(
            category, storage_location, current_conditions, ideal_conditions
        )
        
        # Adjust prediction based on storage quality
        if storage_quality["score"] < 0.5:
            predicted_days = int(predicted_days * 0.7)  # Poor storage = faster spoilage
        elif storage_quality["score"] > 0.8:
            predicted_days = int(predicted_days * 1.2)  # Good storage = slower spoilage
        
        # Ensure minimum of 0 days
        predicted_days = max(0, predicted_days)
        
        # Calculate risk level
        if predicted_days <= 0:
            risk_level = "critical"
            confidence = 0.95
        elif predicted_days <= 2:
            risk_level = "high"
            confidence = 0.90
        elif predicted_days <= 5:
            risk_level = "medium"
            confidence = 0.80
        elif predicted_days <= 10:
            risk_level = "low"
            confidence = 0.70
        else:
            risk_level = "very_low"
            confidence = 0.60
        
        # Generate recommendations
        recommendations = []
        if predicted_days <= 2:
            recommendations.append("🚨 Use immediately or freeze")
            recommendations.append("Consider making a meal today")
        elif predicted_days <= 5:
            recommendations.append("⚠️ Plan to use within this week")
            recommendations.append("Good candidate for batch cooking")
        elif predicted_days <= 10:
            recommendations.append("📅 Use within 10 days")
        
        if storage_quality["score"] < 0.7:
            recommendations.extend(storage_quality["issues"])
        
        # Calculate predicted spoilage date
        predicted_date = datetime.now().date() + timedelta(days=predicted_days)
        
        return {
            "risk_level": risk_level,
            "confidence": confidence,
            "predicted_date": predicted_date.isoformat(),
            "days_until_spoilage": predicted_days,
            "storage_quality": storage_quality,
            "recommendations": recommendations,
            "urgent": predicted_days <= 3
        }
    
    def _assess_storage_conditions(
        self,
        category: str,
        storage_location: Optional[str],
        current_conditions: Optional[Dict],
        ideal_conditions: Optional[Dict]
    ) -> Dict[str, Any]:
        """Assess storage condition quality"""
        
        score = 0.75  # Default neutral score
        issues = []
        
        # Check storage location
        if storage_location:
            location_lower = storage_location.lower()
            
            # Category-specific location checks
            if category in ["Vegetable", "Fruit", "Dairy", "Protein"]:
                if "refrigerator" in location_lower or "fridge" in location_lower:
                    score += 0.15
                elif "counter" in location_lower or "pantry" in location_lower:
                    score -= 0.20
                    issues.append("❄️ Should be refrigerated")
            
            elif category in ["Spice", "Grain", "Oil"]:
                if "pantry" in location_lower or "cupboard" in location_lower:
                    score += 0.15
                elif "refrigerator" in location_lower:
                    score -= 0.05  # Not harmful but unnecessary
        
        # Check current conditions if provided
        if current_conditions and ideal_conditions:
            temp = current_conditions.get("temperature")
            
            if temp is not None and isinstance(ideal_conditions, dict):
                temp_min = ideal_conditions.get("temp_min", 0)
                temp_max = ideal_conditions.get("temp_max", 25)
                
                if temp < temp_min:
                    score -= 0.15
                    issues.append(f"🌡️ Too cold (< {temp_min}°C)")
                elif temp > temp_max:
                    score -= 0.20
                    issues.append(f"🌡️ Too warm (> {temp_max}°C)")
                else:
                    score += 0.10
        
        # Ensure score is between 0 and 1
        score = max(0.0, min(1.0, score))
        
        return {
            "score": score,
            "rating": self._score_to_rating(score),
            "issues": issues
        }
    
    def _score_to_rating(self, score: float) -> str:
        """Convert score to rating"""
        if score >= 0.9:
            return "excellent"
        elif score >= 0.75:
            return "good"
        elif score >= 0.5:
            return "fair"
        elif score >= 0.3:
            return "poor"
        else:
            return "critical"
    
    async def get_expiring_items(
        self,
        conn,
        user_id: str,
        days_threshold: int = 7,
        include_predictions: bool = True
    ) -> Dict[str, Any]:
        """
        Get inventory items expiring soon
        
        Args:
            conn: Database connection
            user_id: User UUID
            days_threshold: Number of days to look ahead
            include_predictions: Include spoilage predictions
            
        Returns:
            List of expiring items with urgency levels
        """
        try:
            # Get user inventory with expiry dates
            items = await conn.fetch("""
                SELECT 
                    ii.id,
                    ii.ingredient_id,
                    ii.quantity,
                    ii.unit,
                    ii.expiry_date,
                    ii.purchase_date,
                    ii.added_date,
                    ii.storage_location,
                    mi.canonical_name,
                    mi.category,
                    mi.subcategory,
                    mi.names
                FROM user_inventory ii
                JOIN master_ingredients mi ON ii.ingredient_id = mi.id
                WHERE ii.user_id = $1
                AND ii.expiry_date IS NOT NULL
                AND ii.expiry_date <= $2
                ORDER BY ii.expiry_date ASC
            """, user_id, datetime.now().date() + timedelta(days=days_threshold))
            
            # Categorize by urgency
            critical = []  # Expired or expiring today
            urgent = []    # Expiring in 1-2 days
            warning = []   # Expiring in 3-5 days
            caution = []   # Expiring in 6-7 days
            
            for item in items:
                days_until_expiry = (item["expiry_date"] - datetime.now().date()).days
                
                item_data = {
                    "id": str(item["id"]),
                    "ingredient_id": str(item["ingredient_id"]),
                    "ingredient_name": item["canonical_name"],
                    "category": item["category"],
                    "quantity": float(item["quantity"]),
                    "unit": item["unit"],
                    "expiry_date": item["expiry_date"].isoformat(),
                    "days_until_expiry": days_until_expiry,
                    "multi_language_names": item["names"]
                }
                
                # Add spoilage prediction if requested
                if include_predictions:
                    prediction = await self.predict_spoilage(conn, str(item["id"]))
                    if "error" not in prediction:
                        item_data["spoilage_prediction"] = prediction
                
                # Categorize by urgency
                if days_until_expiry <= 0:
                    item_data["urgency"] = "critical"
                    critical.append(item_data)
                elif days_until_expiry <= 2:
                    item_data["urgency"] = "urgent"
                    urgent.append(item_data)
                elif days_until_expiry <= 5:
                    item_data["urgency"] = "warning"
                    warning.append(item_data)
                else:
                    item_data["urgency"] = "caution"
                    caution.append(item_data)
            
            return {
                "critical": critical,
                "urgent": urgent,
                "warning": warning,
                "caution": caution,
                "total_expiring": len(items),
                "summary": {
                    "critical_count": len(critical),
                    "urgent_count": len(urgent),
                    "warning_count": len(warning),
                    "caution_count": len(caution)
                },
                "recommendations": self._generate_expiry_recommendations(
                    len(critical), len(urgent), len(warning)
                )
            }
            
        except Exception as e:
            print(f"Error getting expiring items: {e}")
            return {"error": str(e)}
    
    def _generate_expiry_recommendations(
        self,
        critical_count: int,
        urgent_count: int,
        warning_count: int
    ) -> List[str]:
        """Generate recommendations based on expiring items"""
        recommendations = []
        
        if critical_count > 0:
            recommendations.append(f"🚨 {critical_count} item(s) expired or expiring today - use immediately!")
        
        if urgent_count > 0:
            recommendations.append(f"⚠️ {urgent_count} item(s) expiring in 1-2 days - plan meals now")
        
        if warning_count > 0:
            recommendations.append(f"📅 {warning_count} item(s) expiring this week - schedule usage")
        
        if critical_count + urgent_count > 5:
            recommendations.append("💡 Consider batch cooking or freezing to prevent waste")
        
        return recommendations
    
    async def get_storage_alerts(
        self,
        conn,
        user_id: str
    ) -> Dict[str, Any]:
        """
        Get storage condition alerts for user's inventory
        
        Args:
            conn: Database connection
            user_id: User UUID
            
        Returns:
            List of items with storage issues
        """
        try:
            # Get all inventory items
            items = await conn.fetch("""
                SELECT 
                    ii.id,
                    ii.ingredient_id,
                    ii.storage_location,
                    ii.quantity,
                    ii.unit,
                    mi.canonical_name,
                    mi.category,
                    mi.storage_conditions
                FROM user_inventory ii
                JOIN master_ingredients mi ON ii.ingredient_id = mi.id
                WHERE ii.user_id = $1
            """, user_id)
            
            alerts = []
            
            for item in items:
                category = item["category"]
                storage_location = item["storage_location"]
                
                # Check storage requirements
                required = self.storage_requirements.get(category, {})
                
                if not required:
                    continue
                
                alert_messages = []
                severity = "info"
                
                # Check storage location
                if storage_location:
                    location_lower = storage_location.lower()
                    
                    # High-risk categories that need refrigeration
                    if category in ["Vegetable", "Fruit", "Dairy", "Protein", "Herb"]:
                        if not ("refrigerator" in location_lower or "fridge" in location_lower or "freezer" in location_lower):
                            alert_messages.append(f"Should be refrigerated (currently in {storage_location})")
                            severity = "high"
                    
                    # Dry storage categories
                    elif category in ["Spice", "Grain", "Oil"]:
                        if "refrigerator" in location_lower or "fridge" in location_lower:
                            alert_messages.append(f"Better suited for pantry/cupboard storage")
                            severity = "low"
                
                # Generate alerts if issues found
                if alert_messages:
                    alerts.append({
                        "inventory_item_id": str(item["id"]),
                        "ingredient_id": str(item["ingredient_id"]),
                        "ingredient_name": item["canonical_name"],
                        "category": category,
                        "current_storage": storage_location,
                        "severity": severity,
                        "alerts": alert_messages,
                        "recommended_storage": self._get_storage_recommendation(category),
                        "ideal_conditions": required
                    })
            
            # Sort by severity
            severity_order = {"high": 0, "medium": 1, "low": 2, "info": 3}
            alerts.sort(key=lambda x: severity_order.get(x["severity"], 4))
            
            return {
                "alerts": alerts,
                "total_alerts": len(alerts),
                "high_severity_count": len([a for a in alerts if a["severity"] == "high"]),
                "summary": self._generate_storage_alert_summary(alerts)
            }
            
        except Exception as e:
            print(f"Error getting storage alerts: {e}")
            return {"error": str(e)}
    
    def _get_storage_recommendation(self, category: str) -> str:
        """Get storage recommendation for category"""
        recommendations = {
            "Vegetable": "Store in refrigerator crisper drawer",
            "Fruit": "Store in refrigerator or cool, dry place",
            "Dairy": "Store in refrigerator at 1-4°C",
            "Protein": "Store in refrigerator at 0-4°C, use within 3 days",
            "Herb": "Wrap in damp paper towel, store in refrigerator",
            "Spice": "Store in airtight container in cool, dark pantry",
            "Grain": "Store in airtight container in cool, dry pantry",
            "Oil": "Store in cool, dark place away from heat"
        }
        return recommendations.get(category, "Store in appropriate conditions")
    
    def _generate_storage_alert_summary(self, alerts: List[Dict]) -> List[str]:
        """Generate summary of storage alerts"""
        if not alerts:
            return ["✅ All items properly stored"]
        
        summary = []
        high_count = len([a for a in alerts if a["severity"] == "high"])
        
        if high_count > 0:
            summary.append(f"⚠️ {high_count} item(s) need immediate storage correction")
        
        if len(alerts) > 3:
            summary.append("💡 Review storage locations to prevent spoilage")
        
        return summary
    
    async def suggest_recipes_by_expiry(
        self,
        conn,
        user_id: str,
        days_threshold: int = 5
    ) -> Dict[str, Any]:
        """
        Suggest recipes using expiring ingredients
        
        Args:
            conn: Database connection
            user_id: User UUID
            days_threshold: Look for items expiring within N days
            
        Returns:
            Recipe suggestions prioritized by expiring ingredients
        """
        try:
            # Get expiring items
            expiring = await self.get_expiring_items(conn, user_id, days_threshold, False)
            
            if "error" in expiring:
                return expiring
            
            # Collect expiring ingredient IDs
            expiring_ingredient_ids = []
            for urgency in ["critical", "urgent", "warning"]:
                for item in expiring.get(urgency, []):
                    expiring_ingredient_ids.append(item["ingredient_id"])
            
            if not expiring_ingredient_ids:
                return {
                    "recipes": [],
                    "message": "No expiring ingredients found",
                    "total_recipes": 0
                }
            
            # Get recipes that use these ingredients
            # Note: This requires a recipes table with ingredient relationships
            # For now, return ingredient-based suggestions
            
            suggestions = []
            
            for ingredient_id in expiring_ingredient_ids[:10]:  # Limit to top 10
                ingredient = await conn.fetchrow("""
                    SELECT canonical_name, category, common_uses
                    FROM master_ingredients
                    WHERE id = $1
                """, ingredient_id)
                
                if ingredient:
                    suggestions.append({
                        "ingredient_id": ingredient_id,
                        "ingredient_name": ingredient["canonical_name"],
                        "category": ingredient["category"],
                        "suggested_uses": ingredient["common_uses"] or [],
                        "urgency": "high" if ingredient_id in [
                            item["ingredient_id"] for item in expiring.get("critical", [])
                        ] else "medium"
                    })
            
            return {
                "suggestions": suggestions,
                "total_suggestions": len(suggestions),
                "expiring_summary": expiring["summary"],
                "recommendations": [
                    "🍳 Use expiring ingredients in tonight's meal",
                    "🥘 Consider batch cooking to preserve ingredients",
                    "❄️ Freeze items you can't use immediately"
                ]
            }
            
        except Exception as e:
            print(f"Error suggesting recipes: {e}")
            return {"error": str(e)}
    
    async def get_waste_analytics(
        self,
        conn,
        user_id: str,
        days_lookback: int = 30
    ) -> Dict[str, Any]:
        """
        Generate waste analytics dashboard data
        
        Args:
            conn: Database connection
            user_id: User UUID
            days_lookback: Number of days to analyze
            
        Returns:
            Waste analytics with trends and insights
        """
        try:
            start_date = datetime.now().date() - timedelta(days=days_lookback)
            
            # Get items that expired (removed from inventory past expiry)
            # Note: This requires tracking removal reasons
            # For now, we'll analyze current inventory status
            
            # Get all inventory items
            all_items = await conn.fetch("""
                SELECT 
                    ii.id,
                    ii.ingredient_id,
                    ii.quantity,
                    ii.unit,
                    ii.expiry_date,
                    ii.added_date,
                    mi.canonical_name,
                    mi.category,
                    mi.waste_risk_level
                FROM user_inventory ii
                JOIN master_ingredients mi ON ii.ingredient_id = mi.id
                WHERE ii.user_id = $1
            """, user_id)
            
            # Analyze waste risk
            high_risk_items = []
            medium_risk_items = []
            low_risk_items = []
            
            total_items = len(all_items)
            expired_count = 0
            expiring_soon_count = 0
            
            for item in all_items:
                # Check if expired
                if item["expiry_date"] and item["expiry_date"] < datetime.now().date():
                    expired_count += 1
                    high_risk_items.append(item)
                # Check if expiring soon (within 3 days)
                elif item["expiry_date"] and (item["expiry_date"] - datetime.now().date()).days <= 3:
                    expiring_soon_count += 1
                    high_risk_items.append(item)
                # Check waste risk level
                elif item["waste_risk_level"] == "high":
                    high_risk_items.append(item)
                elif item["waste_risk_level"] == "medium":
                    medium_risk_items.append(item)
                else:
                    low_risk_items.append(item)
            
            # Calculate waste statistics
            waste_risk_percentage = (len(high_risk_items) / total_items * 100) if total_items > 0 else 0
            
            # Category breakdown
            category_waste = defaultdict(int)
            for item in high_risk_items:
                category_waste[item["category"]] += 1
            
            # Generate insights
            insights = []
            
            if expired_count > 0:
                insights.append(f"⚠️ {expired_count} item(s) have expired")
            
            if expiring_soon_count > 0:
                insights.append(f"🚨 {expiring_soon_count} item(s) expiring in 3 days")
            
            if waste_risk_percentage > 30:
                insights.append(f"📊 {waste_risk_percentage:.1f}% of inventory at risk")
                insights.append("💡 Consider meal planning to reduce waste")
            
            # Top waste categories
            if category_waste:
                top_category = max(category_waste.items(), key=lambda x: x[1])
                insights.append(f"🥬 Most waste risk in {top_category[0]} category")
            
            return {
                "period_days": days_lookback,
                "total_items": total_items,
                "waste_statistics": {
                    "expired_count": expired_count,
                    "expiring_soon_count": expiring_soon_count,
                    "high_risk_count": len(high_risk_items),
                    "medium_risk_count": len(medium_risk_items),
                    "low_risk_count": len(low_risk_items),
                    "waste_risk_percentage": round(waste_risk_percentage, 1)
                },
                "category_breakdown": dict(category_waste),
                "insights": insights,
                "recommendations": [
                    "✅ Check inventory regularly (2-3 times per week)",
                    "📝 Plan meals around expiring ingredients",
                    "❄️ Freeze items you can't use immediately",
                    "🛒 Buy only what you'll use within the week"
                ],
                "health_score": self._calculate_waste_health_score(
                    expired_count, expiring_soon_count, total_items
                )
            }
            
        except Exception as e:
            print(f"Error generating waste analytics: {e}")
            return {"error": str(e)}
    
    def _calculate_waste_health_score(
        self,
        expired_count: int,
        expiring_soon_count: int,
        total_items: int
    ) -> Dict[str, Any]:
        """Calculate waste prevention health score"""
        
        if total_items == 0:
            return {"score": 100, "rating": "excellent", "message": "No inventory to track"}
        
        # Calculate penalty points
        penalties = (expired_count * 10) + (expiring_soon_count * 5)
        
        # Base score is 100, subtract penalties
        score = max(0, 100 - penalties)
        
        # Determine rating
        if score >= 90:
            rating = "excellent"
            message = "Great job preventing waste! 🌟"
        elif score >= 75:
            rating = "good"
            message = "Good waste management 👍"
        elif score >= 60:
            rating = "fair"
            message = "Room for improvement 📈"
        elif score >= 40:
            rating = "poor"
            message = "Focus on reducing waste ⚠️"
        else:
            rating = "critical"
            message = "Urgent action needed 🚨"
        
        return {
            "score": score,
            "rating": rating,
            "message": message
        }
