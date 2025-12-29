"""Direct test of mock weekly plan generation"""
from app.core.llm_client import MockLlmClient
import json
import asyncio

async def test():
    # Create mock client
    client = MockLlmClient()

    # Test context with 3 days
    context = {
        "session_request": {
            "start_date": "2025-12-29",
            "num_days": 3,
            "timezone": "UTC"
        }
    }

    # Call the mock client
    prompt = "Plan weekly menu"
    result_json = await client.generate(prompt=prompt, context=context, schema_name="MENU_PLAN_SCHEMA")
    result = json.loads(result_json)

    print("Mock weekly plan result:")
    print(f"Status: {result.get('status')}")
    print(f"Number of menus: {len(result.get('menus', []))}")
    print(f"Planning window: {result.get('planning_window')}")
    print("\nMenus:")
    for i, menu in enumerate(result.get('menus', [])):
        print(f"  Menu {i}: type={menu.get('menu_type')}, day_index={menu.get('day_index')}, date={menu.get('date')}")

    print("\nFull JSON (first 500 chars):")
    print(json.dumps(result, indent=2)[:500])

asyncio.run(test())
