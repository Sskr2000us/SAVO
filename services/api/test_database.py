"""
Test Database Integration End-to-End
Tests all database operations with Supabase
"""

import asyncio
import os
from datetime import date
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import database functions
from app.core.database import (
    get_or_create_user,
    create_household_profile,
    get_household_profile,
    create_family_member,
    get_family_members,
    add_inventory_item,
    get_inventory,
    get_low_stock_items,
    deduct_inventory_for_recipe,
    create_meal_plan,
    add_recipe_to_history
)


async def test_database_flow():
    """Test complete database flow"""
    
    print("=" * 80)
    print("SAVO Database Integration Test")
    print("=" * 80)
    
    # Test user
    test_user_id = "test-user-12345"
    test_user_email = "test@savo.app"
    
    try:
        # ============================================================================
        # TEST 1: Create/Get User
        # ============================================================================
        print("\n📋 TEST 1: Create User Profile")
        print("-" * 80)
        
        user = await get_or_create_user(test_user_id, test_user_email, "Test User")
        print(f"✅ User created: {user['email']}")
        
        # ============================================================================
        # TEST 2: Create Household Profile
        # ============================================================================
        print("\n🏠 TEST 2: Create Household Profile")
        print("-" * 80)
        
        household_data = {
            "region": "US",
            "culture": "western",
            "primary_language": "en-US",
            "measurement_system": "imperial",
            "favorite_cuisines": ["Italian", "Mexican", "Indian"],
            "nutrition_targets": {
                "daily_calories": 2200,
                "protein_g": 120,
                "carbs_g": 250,
                "fat_g": 70
            },
            "skill_level": 2
        }
        
        household = await create_household_profile(test_user_id, household_data)
        print(f"✅ Household created: {household['id']}")
        print(f"   Region: {household['region']}")
        print(f"   Cuisines: {household['favorite_cuisines']}")
        print(f"   Skill Level: {household['skill_level']}")
        
        # ============================================================================
        # TEST 3: Add Family Members
        # ============================================================================
        print("\n👨‍👩‍👧‍👦 TEST 3: Add Family Members")
        print("-" * 80)
        
        members_data = [
            {
                "name": "John Doe",
                "age": 35,
                "dietary_restrictions": ["vegetarian"],
                "allergens": ["peanuts"],
                "health_conditions": ["diabetes"],
                "spice_tolerance": "medium"
            },
            {
                "name": "Jane Doe",
                "age": 32,
                "dietary_restrictions": [],
                "allergens": ["shellfish"],
                "health_conditions": [],
                "spice_tolerance": "high"
            },
            {
                "name": "Little Timmy",
                "age": 8,
                "dietary_restrictions": [],
                "allergens": [],
                "health_conditions": [],
                "spice_tolerance": "none"
            }
        ]
        
        for member_data in members_data:
            member = await create_family_member(test_user_id, member_data)
            print(f"✅ Added: {member['name']} (age {member['age']}, {member['age_category']})")
        
        all_members = await get_family_members(test_user_id)
        print(f"\n   Total family members: {len(all_members)}")
        
        # ============================================================================
        # TEST 4: Add Inventory Items
        # ============================================================================
        print("\n🥕 TEST 4: Add Inventory Items")
        print("-" * 80)
        
        inventory_items = [
            {
                "canonical_name": "tomato",
                "display_name": "Fresh Tomatoes",
                "category": "vegetables",
                "quantity": 5,
                "unit": "pcs",
                "storage_location": "counter",
                "low_stock_threshold": 2,
                "expiry_date": "2025-01-05"
            },
            {
                "canonical_name": "pasta",
                "display_name": "Spaghetti Pasta",
                "category": "grains",
                "quantity": 500,
                "unit": "g",
                "storage_location": "pantry",
                "low_stock_threshold": 200
            },
            {
                "canonical_name": "olive_oil",
                "display_name": "Extra Virgin Olive Oil",
                "category": "oils",
                "quantity": 750,
                "unit": "ml",
                "storage_location": "pantry",
                "low_stock_threshold": 100
            },
            {
                "canonical_name": "garlic",
                "display_name": "Fresh Garlic",
                "category": "vegetables",
                "quantity": 2,
                "unit": "pcs",
                "storage_location": "pantry",
                "low_stock_threshold": 3  # Will trigger low stock!
            }
        ]
        
        for item_data in inventory_items:
            item = await add_inventory_item(test_user_id, item_data)
            low_stock_marker = "⚠️ LOW" if item.get("is_low_stock") else "✅"
            print(f"{low_stock_marker} Added: {item['display_name']} ({item['quantity']} {item['unit']})")
        
        inventory = await get_inventory(test_user_id)
        print(f"\n   Total inventory items: {len(inventory)}")
        
        # ============================================================================
        # TEST 5: Check Low Stock Alerts
        # ============================================================================
        print("\n⚠️  TEST 5: Check Low Stock Alerts")
        print("-" * 80)
        
        low_stock = await get_low_stock_items(test_user_id)
        
        if low_stock:
            print(f"Found {len(low_stock)} low stock item(s):")
            for item in low_stock:
                print(f"   • {item['display_name']}: {item['quantity']} {item['unit']} (threshold: {item['low_stock_threshold']})")
        else:
            print("✅ All items are well stocked!")
        
        # ============================================================================
        # TEST 6: Create Meal Plan
        # ============================================================================
        print("\n🍝 TEST 6: Create Meal Plan")
        print("-" * 80)
        
        meal_plan_data = {
            "plan_type": "daily",
            "plan_date": date.today().isoformat(),
            "meal_type": "dinner",
            "selected_cuisine": "Italian",
            "servings": 4,
            "recipes": [
                {
                    "name": "Spaghetti Aglio e Olio",
                    "id": "recipe-123",
                    "ingredients": [
                        {"name": "pasta", "quantity": 400, "unit": "g"},
                        {"name": "garlic", "quantity": 1, "unit": "pcs"},
                        {"name": "olive_oil", "quantity": 50, "unit": "ml"}
                    ]
                }
            ]
        }
        
        meal_plan = await create_meal_plan(test_user_id, meal_plan_data)
        print(f"✅ Meal plan created: {meal_plan['id']}")
        print(f"   Date: {meal_plan['plan_date']}")
        print(f"   Meal: {meal_plan['meal_type']}")
        print(f"   Cuisine: {meal_plan['selected_cuisine']}")
        
        # ============================================================================
        # TEST 7: Deduct Inventory After Recipe Selection
        # ============================================================================
        print("\n📉 TEST 7: Deduct Inventory for Recipe")
        print("-" * 80)
        
        ingredients_to_deduct = [
            {"name": "pasta", "quantity": 400, "unit": "g"},
            {"name": "garlic", "quantity": 1, "unit": "pcs"},
            {"name": "olive_oil", "quantity": 50, "unit": "ml"}
        ]
        
        print("Deducting ingredients:")
        for ing in ingredients_to_deduct:
            print(f"   • {ing['name']}: {ing['quantity']} {ing['unit']}")
        
        result = await deduct_inventory_for_recipe(
            test_user_id,
            meal_plan['id'],
            ingredients_to_deduct
        )
        
        if result["success"]:
            print(f"\n✅ {result['message']}")
            
            # Check updated inventory
            updated_inventory = await get_inventory(test_user_id)
            print("\nUpdated inventory:")
            for item in updated_inventory:
                if item["canonical_name"] in ["pasta", "garlic", "olive_oil"]:
                    low_marker = "⚠️" if item["is_low_stock"] else "  "
                    print(f"   {low_marker} {item['display_name']}: {item['quantity']} {item['unit']}")
        else:
            print(f"\n❌ {result['message']}")
            if result.get("insufficient_items"):
                print("Insufficient items:")
                for item in result["insufficient_items"]:
                    print(f"   • {item}")
        
        # Check low stock again
        low_stock_after = await get_low_stock_items(test_user_id)
        if low_stock_after:
            print(f"\n⚠️  New low stock alerts: {len(low_stock_after)}")
            for item in low_stock_after:
                print(f"   • {item['display_name']}: {item['quantity']} {item['unit']}")
        
        # ============================================================================
        # TEST 8: Add Recipe to History
        # ============================================================================
        print("\n📜 TEST 8: Add Recipe to History")
        print("-" * 80)
        
        recipe_history_data = {
            "meal_plan_id": meal_plan['id'],
            "recipe_name": "Spaghetti Aglio e Olio",
            "cuisine": "Italian",
            "difficulty_level": 2,
            "estimated_time_minutes": 20,
            "was_successful": True,
            "user_rating": 5,
            "user_notes": "Delicious and easy!",
            "health_fit_score": 0.85,
            "skill_fit_category": "perfect"
        }
        
        history = await add_recipe_to_history(test_user_id, recipe_history_data)
        print(f"✅ Recipe added to history")
        print(f"   Rating: {'⭐' * history['user_rating']}")
        print(f"   Health fit: {history['health_fit_score']:.0%}")
        print(f"   Skill fit: {history['skill_fit_category']}")
        
        # Check updated skill level
        updated_household = await get_household_profile(test_user_id)
        print(f"\n🎓 Skill progression:")
        print(f"   Recipes completed: {updated_household['recipes_completed']}")
        print(f"   Skill level: {updated_household['skill_level']}/5")
        print(f"   Confidence: {updated_household['confidence_score']:.0%}")
        
        # ============================================================================
        # SUMMARY
        # ============================================================================
        print("\n" + "=" * 80)
        print("✅ ALL TESTS PASSED!")
        print("=" * 80)
        print(f"\nDatabase Summary:")
        print(f"  • User: {user['email']}")
        print(f"  • Household ID: {household['id']}")
        print(f"  • Family members: {len(all_members)}")
        print(f"  • Inventory items: {len(updated_inventory)}")
        print(f"  • Low stock alerts: {len(low_stock_after)}")
        print(f"  • Meal plans: 1")
        print(f"  • Recipes completed: {updated_household['recipes_completed']}")
        print(f"\n🎉 Database integration working perfectly!")
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    
    return True


if __name__ == "__main__":
    print("\n" + "=" * 80)
    print("IMPORTANT: Make sure you have:")
    print("  1. ✅ Run the migration in Supabase SQL Editor")
    print("  2. ✅ Set SUPABASE_URL in environment")
    print("  3. ✅ Set SUPABASE_SERVICE_KEY in environment")
    print("=" * 80 + "\n")
    
    # Check environment variables
    if not os.getenv("SUPABASE_URL"):
        print("❌ ERROR: SUPABASE_URL not set!")
        print("   Set it: $env:SUPABASE_URL='https://xxxxx.supabase.co'")
        exit(1)
    
    if not os.getenv("SUPABASE_SERVICE_KEY"):
        print("❌ ERROR: SUPABASE_SERVICE_KEY not set!")
        print("   Set it: $env:SUPABASE_SERVICE_KEY='your-service-key'")
        exit(1)
    
    print("✅ Environment variables found\n")
    print("Starting test...\n")
    
    # Run tests
    success = asyncio.run(test_database_flow())
    
    if success:
        print("\n✅ All database operations working!")
        print("Ready to integrate with Flutter app.")
    else:
        print("\n❌ Some tests failed. Check error messages above.")
        exit(1)
