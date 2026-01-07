"""
Daily Habit Service
Generates personalized morning/evening digests, tracks streaks, monitors engagement
"""

from typing import List, Dict, Optional
from uuid import UUID
from datetime import datetime, time, timedelta
import asyncio
from collections import defaultdict


class DailyHabitService:
    """Service for managing daily habit loop and user engagement"""
    
    def __init__(self, supabase_client):
        self.db = supabase_client
    
    # ===== MORNING DIGEST =====
    
    async def generate_morning_digest(self, user_id: UUID) -> Dict:
        """
        Generate personalized morning digest
        
        Answers 3 core questions:
        1. What can I cook today?
        2. What will go bad soon?
        3. What did I waste last week?
        
        Returns:
            Dictionary with digest content ready for push notification
        """
        
        # Get expiring ingredients (top 2)
        expiring = await self._get_expiring_ingredients(user_id, limit=2)
        
        # Get recipe recommendations based on expiring items
        recipes = await self._get_recipe_recommendations(user_id, expiring)
        
        # Get waste summary for last 7 days
        waste_summary = await self._get_waste_summary(user_id, days=7)
        
        # Get current streak status
        streak = await self._get_streak(user_id, "no_waste")
        
        # Build digest content
        digest = {
            "greeting": self._get_greeting(),
            "cook_today": [
                {
                    "ingredient": ing["name"],
                    "days_left": ing["days_to_expiry"],
                    "recipe": recipes.get(ing["id"], "Use in your favorite recipe")
                }
                for ing in expiring
            ],
            "expiring_soon": await self._get_expiring_ingredients(user_id, limit=2, skip=2),
            "waste_summary": waste_summary,
            "streak": {
                "type": "no_waste",
                "count": streak["current_count"] if streak else 0,
                "message": self._get_streak_message(streak["current_count"] if streak else 0)
            },
            "tips": await self._get_daily_tip(user_id)
        }
        
        # Save digest to database
        digest_id = await self._save_digest(user_id, "morning", digest)
        digest["digest_id"] = str(digest_id)
        
        return digest
    
    # ===== EVENING DIGEST =====
    
    async def generate_evening_digest(self, user_id: UUID) -> Dict:
        """
        Generate evening check-in digest
        
        Quick questions:
        1. Did you cook today?
        2. Did you waste anything?
        3. Need to update any expiry dates?
        
        Returns:
            Dictionary with check-in content
        """
        
        # Get today's cooking activity
        cooked_today = await self._get_today_cooking_activity(user_id)
        
        # Get ingredients that expired today
        expired_today = await self._get_expired_today(user_id)
        
        # Get inventory items needing attention
        needs_attention = await self._get_items_needing_attention(user_id)
        
        digest = {
            "greeting": self._get_evening_greeting(),
            "cooked_today": cooked_today,
            "expired_today": expired_today,
            "needs_attention": needs_attention,
            "quick_actions": [
                {"action": "log_cooking", "label": "Log what you cooked"},
                {"action": "mark_waste", "label": "Report waste"},
                {"action": "update_expiry", "label": "Update expiry dates"}
            ]
        }
        
        # Save digest
        digest_id = await self._save_digest(user_id, "evening", digest)
        digest["digest_id"] = str(digest_id)
        
        return digest
    
    # ===== STREAK TRACKING =====
    
    async def update_user_streak(
        self,
        user_id: UUID,
        streak_type: str,
        success: bool = True
    ) -> Dict:
        """
        Update user streak
        
        Args:
            user_id: User UUID
            streak_type: no_waste, daily_scan, or daily_cook
            success: Whether user succeeded today
        
        Returns:
            Updated streak data
        """
        
        # Get current streak
        response = self.db.table("user_streaks").select("*").eq(
            "user_id", str(user_id)
        ).eq("streak_type", streak_type).execute()
        
        if not response.data:
            # Create new streak
            streak_data = {
                "user_id": str(user_id),
                "streak_type": streak_type,
                "current_count": 1 if success else 0,
                "longest_count": 1 if success else 0,
                "last_activity_date": datetime.now().date().isoformat()
            }
            
            result = self.db.table("user_streaks").insert(streak_data).execute()
            return result.data[0]
        
        # Update existing streak
        streak = response.data[0]
        last_date = datetime.fromisoformat(streak["last_activity_date"]).date()
        today = datetime.now().date()
        
        # Check if it's a new day
        if last_date < today:
            if success:
                # Increment streak
                new_count = streak["current_count"] + 1
                longest = max(new_count, streak["longest_count"])
                
                update_data = {
                    "current_count": new_count,
                    "longest_count": longest,
                    "last_activity_date": today.isoformat()
                }
            else:
                # Break streak
                update_data = {
                    "current_count": 0,
                    "last_activity_date": today.isoformat()
                }
            
            result = self.db.table("user_streaks").update(update_data).eq(
                "id", streak["id"]
            ).execute()
            
            return result.data[0]
        
        return streak
    
    # ===== PASSIVE LEARNING =====
    
    async def track_passive_signal(
        self,
        user_id: UUID,
        signal_type: str,
        context: Optional[Dict] = None
    ) -> None:
        """
        Track passive learning signal
        
        Signal types:
        - digest_opened: User opened morning/evening digest
        - item_clicked: User clicked on ingredient/recipe
        - recipe_cooked: User marked recipe as cooked
        - waste_reported: User reported food waste
        - scan_completed: User completed ingredient scan
        """
        
        signal_data = {
            "user_id": str(user_id),
            "signal_type": signal_type,
            "context": context or {},
            "timestamp": datetime.now().isoformat()
        }
        
        self.db.table("passive_learning_signals").insert(signal_data).execute()
    
    # ===== DIGEST ENGAGEMENT =====
    
    async def mark_digest_opened(self, digest_id: UUID) -> None:
        """Mark digest as opened by user"""
        
        self.db.table("daily_digests").update({
            "was_opened": True,
            "opened_at": datetime.now().isoformat()
        }).eq("id", str(digest_id)).execute()
    
    async def mark_digest_actioned(
        self,
        digest_id: UUID,
        action_taken: str
    ) -> None:
        """Mark digest as actioned (user took recommended action)"""
        
        self.db.table("daily_digests").update({
            "was_actioned": True,
            "action_taken": action_taken,
            "actioned_at": datetime.now().isoformat()
        }).eq("id", str(digest_id)).execute()
    
    # ===== HELPER METHODS =====
    
    async def _get_expiring_ingredients(
        self,
        user_id: UUID,
        limit: int = 5,
        skip: int = 0
    ) -> List[Dict]:
        """Get ingredients expiring soon"""
        
        # Query inventory for items expiring in next 5 days
        response = self.db.table("user_inventory").select(
            "id, ingredient_id, quantity, expiry_date, master_ingredients(name)"
        ).eq("user_id", str(user_id)).gte(
            "expiry_date", datetime.now().date().isoformat()
        ).lte(
            "expiry_date",
            (datetime.now().date() + timedelta(days=5)).isoformat()
        ).order("expiry_date").range(skip, skip + limit - 1).execute()
        
        ingredients = []
        for item in response.data:
            expiry = datetime.fromisoformat(item["expiry_date"]).date()
            days_left = (expiry - datetime.now().date()).days
            
            ingredients.append({
                "id": item["ingredient_id"],
                "name": item["master_ingredients"]["name"],
                "quantity": item["quantity"],
                "days_to_expiry": days_left
            })
        
        return ingredients
    
    async def _get_recipe_recommendations(
        self,
        user_id: UUID,
        ingredients: List[Dict]
    ) -> Dict[str, str]:
        """Get recipe recommendations for expiring ingredients"""
        
        # Simplified: Return generic suggestions
        # In production, integrate with recipe API
        
        recommendations = {}
        for ing in ingredients:
            ingredient_name = ing["name"].lower()
            
            if any(veg in ingredient_name for veg in ["tomato", "onion", "potato"]):
                recommendations[ing["id"]] = "Make a curry or stir-fry"
            elif any(herb in ingredient_name for herb in ["cilantro", "mint", "basil"]):
                recommendations[ing["id"]] = "Use as garnish or in salad"
            elif "chicken" in ingredient_name:
                recommendations[ing["id"]] = "Grill or make soup"
            else:
                recommendations[ing["id"]] = "Use in your favorite recipe"
        
        return recommendations
    
    async def _get_waste_summary(self, user_id: UUID, days: int = 7) -> Dict:
        """Get waste summary for last N days"""
        
        # Query scanning_history for discarded items
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        response = self.db.table("scanning_history").select(
            "id, ingredient_name, quantity"
        ).eq("user_id", str(user_id)).eq(
            "action_taken", "discarded"
        ).gte("scanned_at", cutoff).execute()
        
        waste_items = response.data
        
        return {
            "items_wasted": len(waste_items),
            "estimated_value": len(waste_items) * 2.5,  # $2.50 per item estimate
            "top_wasted": waste_items[:3] if waste_items else []
        }
    
    async def _get_streak(self, user_id: UUID, streak_type: str) -> Optional[Dict]:
        """Get user's current streak"""
        
        response = self.db.table("user_streaks").select("*").eq(
            "user_id", str(user_id)
        ).eq("streak_type", streak_type).execute()
        
        return response.data[0] if response.data else None
    
    async def _get_daily_tip(self, user_id: UUID) -> str:
        """Get personalized daily tip"""
        
        tips = [
            "Store leafy greens in a damp towel to keep them fresh longer",
            "Check your fridge temperature - it should be between 35-38°F",
            "Use the FIFO method: First In, First Out",
            "Freeze herbs in olive oil for easy cooking",
            "Store onions and potatoes separately to prevent spoilage",
            "Use overripe bananas for smoothies or baking",
            "Label leftovers with dates to track freshness",
            "Store berries unwashed to prevent mold"
        ]
        
        # Return random tip based on day of week
        tip_index = datetime.now().weekday()
        return tips[tip_index % len(tips)]
    
    async def _get_today_cooking_activity(self, user_id: UUID) -> List[Dict]:
        """Get ingredients user cooked with today"""
        
        today_start = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
        
        response = self.db.table("scanning_history").select(
            "ingredient_name, quantity"
        ).eq("user_id", str(user_id)).eq(
            "action_taken", "cooked"
        ).gte("scanned_at", today_start).execute()
        
        return response.data
    
    async def _get_expired_today(self, user_id: UUID) -> List[Dict]:
        """Get ingredients that expired today"""
        
        today = datetime.now().date().isoformat()
        
        response = self.db.table("user_inventory").select(
            "ingredient_id, quantity, master_ingredients(name)"
        ).eq("user_id", str(user_id)).eq("expiry_date", today).execute()
        
        return [
            {
                "name": item["master_ingredients"]["name"],
                "quantity": item["quantity"]
            }
            for item in response.data
        ]
    
    async def _get_items_needing_attention(self, user_id: UUID) -> List[Dict]:
        """Get inventory items needing attention (no expiry date, low quantity)"""
        
        response = self.db.table("user_inventory").select(
            "id, ingredient_id, quantity, expiry_date, master_ingredients(name)"
        ).eq("user_id", str(user_id)).execute()
        
        needs_attention = []
        for item in response.data:
            if not item.get("expiry_date"):
                needs_attention.append({
                    "name": item["master_ingredients"]["name"],
                    "reason": "Missing expiry date",
                    "action": "update_expiry"
                })
            elif item.get("quantity", 0) < 0.1:
                needs_attention.append({
                    "name": item["master_ingredients"]["name"],
                    "reason": "Low quantity",
                    "action": "restock"
                })
        
        return needs_attention[:3]  # Return top 3
    
    async def _save_digest(
        self,
        user_id: UUID,
        digest_type: str,
        content: Dict
    ) -> UUID:
        """Save digest to database"""
        
        digest_data = {
            "user_id": str(user_id),
            "digest_type": digest_type,
            "content": content,
            "sent_at": datetime.now().isoformat()
        }
        
        response = self.db.table("daily_digests").insert(digest_data).execute()
        return UUID(response.data[0]["id"])
    
    @staticmethod
    def _get_greeting() -> str:
        """Get time-appropriate morning greeting"""
        hour = datetime.now().hour
        
        if hour < 12:
            return "Good morning! 🌅"
        elif hour < 17:
            return "Good afternoon! ☀️"
        else:
            return "Good evening! 🌆"
    
    @staticmethod
    def _get_evening_greeting() -> str:
        """Get evening greeting"""
        return "Hey! Quick check-in before bed 🌙"
    
    @staticmethod
    def _get_streak_message(count: int) -> str:
        """Get motivational streak message"""
        if count == 0:
            return "Start your streak today!"
        elif count < 3:
            return f"{count} day{'s' if count > 1 else ''} - Keep going!"
        elif count < 7:
            return f"🔥 {count} days - You're on fire!"
        elif count < 14:
            return f"⭐ {count} days - Impressive!"
        else:
            return f"🏆 {count} days - You're a champion!"


# ===== SCHEDULING HELPER =====

class DigestScheduler:
    """Helper class for scheduling daily digests"""
    
    def __init__(self, supabase_client, notification_service):
        self.habit_service = DailyHabitService(supabase_client)
        self.notification_service = notification_service
    
    async def send_morning_digests(self):
        """Send morning digests to all active users"""
        
        # Get all users who have enabled notifications
        # This is a simplified version - in production, query user preferences
        
        print(f"[{datetime.now()}] Sending morning digests...")
        
        # For now, this would be triggered by APScheduler at 8 AM
        # Implementation would query active users and send notifications
        
    async def send_evening_digests(self):
        """Send evening check-ins to all active users"""
        
        print(f"[{datetime.now()}] Sending evening check-ins...")
        
        # For now, this would be triggered by APScheduler at 6 PM
