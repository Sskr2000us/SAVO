"""
Test script to verify LLM provider fallback behavior
"""
import asyncio
import os
import sys

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from app.core.orchestrator import run_task
from app.core.settings import settings


async def test_daily_plan():
    """Test daily planning with fallback"""
    print(f"Primary provider: {settings.llm_provider}")
    print(f"Fallback provider: {settings.llm_fallback_provider or 'None'}")
    print("\n" + "="*80)
    
    context = {
        "app_configuration": {
            "household_profile": {"num_members": 2},
            "timezone": "America/Los_Angeles",
            "measurement_system": "metric",
            "output_language": "English"
        },
        "inventory": [],
        "session_request": {
            "time_available_minutes": 30,
            "servings": 2,
            "selected_cuisine": "Italian"
        }
    }
    
    try:
        print("Testing daily planning...")
        result = await run_task(
            task_name="plan_daily_menu",
            output_schema_name="MENU_PLAN_SCHEMA",
            context=context
        )
        
        print(f"\nStatus: {result.get('status')}")
        print(f"Selected Cuisine: {result.get('selected_cuisine')}")
        print(f"Number of menus: {len(result.get('menus', []))}")
        
        if result.get('status') == 'ok':
            print("\n✓ Daily planning succeeded!")
            if result.get('menus'):
                first_menu = result['menus'][0]
                print(f"  First menu has {len(first_menu.get('courses', []))} courses")
        elif result.get('status') == 'error':
            print(f"\n✗ Planning failed: {result.get('error_message')}")
        
        return result
        
    except Exception as e:
        print(f"\n✗ Exception occurred: {str(e)}")
        raise


async def test_weekly_plan():
    """Test weekly planning with fallback"""
    print("\n" + "="*80)
    print("Testing weekly planning...")
    
    context = {
        "app_configuration": {
            "household_profile": {"num_members": 2},
            "timezone": "America/Los_Angeles",
            "measurement_system": "metric",
            "output_language": "English"
        },
        "inventory": [],
        "session_request": {
            "time_available_minutes": 30,
            "servings": 2,
            "start_date": "2025-12-30",
            "num_days": 3
        }
    }
    
    try:
        result = await run_task(
            task_name="plan_weekly_menu",
            output_schema_name="MENU_PLAN_SCHEMA",
            context=context
        )
        
        print(f"\nStatus: {result.get('status')}")
        print(f"Number of menus (should be 3): {len(result.get('menus', []))}")
        
        if result.get('status') == 'ok':
            print("\n✓ Weekly planning succeeded!")
            for i, menu in enumerate(result.get('menus', [])):
                print(f"  Day {i+1}: {menu.get('date')} - {len(menu.get('courses', []))} courses")
        elif result.get('status') == 'error':
            print(f"\n✗ Planning failed: {result.get('error_message')}")
        
        return result
        
    except Exception as e:
        print(f"\n✗ Exception occurred: {str(e)}")
        raise


async def main():
    print("SAVO LLM Provider Fallback Test")
    print("="*80)
    
    # Test daily planning
    await test_daily_plan()
    
    # Test weekly planning (3-day horizon)
    await test_weekly_plan()
    
    print("\n" + "="*80)
    print("All tests completed!")


if __name__ == "__main__":
    asyncio.run(main())
