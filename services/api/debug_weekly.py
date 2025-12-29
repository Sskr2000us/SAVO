"""Debug script to test weekly planning with num_days=3"""
import asyncio
import json
from app.core.llm_client import get_llm_client
from app.core.settings import settings

async def test():
    # Build messages like the orchestrator does
    messages = [
        {"role": "system", "content": "You are SAVO meal planning assistant"},
        {"role": "user", "content": "Create a weekly plan"},
        {
            "role": "user", 
            "content": 'CONTEXT_JSON={"session_request": {"start_date": "2025-12-29", "num_days": 3, "timezone": "UTC"}}'
        }
    ]
    
    # Mock schema
    schema = {"required": ["status", "selected_cuisine", "menu_headers", "menus"]}
    
    # Get mock client
    client = get_llm_client("mock")
    
    # Call generate_json
    result = await client.generate_json(messages=messages, schema=schema)
    
    print(f"\n=== RESULT ===")
    print(f"Status: {result.get('status')}")
    print(f"Number of menus: {len(result.get('menus', []))}")
    print(f"Planning window: {result.get('planning_window')}")
    print(f"\nMenus:")
    for i, menu in enumerate(result.get('menus', [])):
        print(f"  [{i}] menu_type={menu.get('menu_type')}, day_index={menu.get('day_index')}, date={menu.get('date')}")
    
    print(f"\nFull response (truncated):")
    print(json.dumps(result, indent=2)[:1000])

if __name__ == "__main__":
    asyncio.run(test())
