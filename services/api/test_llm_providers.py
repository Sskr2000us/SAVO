"""
Test script to verify LLM providers work correctly with retry logic.
Run this to test each provider independently.

Usage:
    python test_llm_providers.py mock
    python test_llm_providers.py openai
    python test_llm_providers.py anthropic
"""

import asyncio
import json
import sys
from app.core.llm_client import get_llm_client


async def test_provider(provider_name: str):
    print(f"\n{'='*60}")
    print(f"Testing {provider_name.upper()} Provider")
    print(f"{'='*60}\n")
    
    try:
        client = get_llm_client(provider_name)
        print(f"✓ Client created successfully: {type(client).__name__}")
    except Exception as e:
        print(f"✗ Failed to create client: {e}")
        return False
    
    # Test 1: Simple JSON generation
    print("\nTest 1: Simple JSON Generation")
    print("-" * 40)
    
    messages = [
        {
            "role": "system",
            "content": "You are a helpful assistant that responds in JSON format."
        },
        {
            "role": "user",
            "content": "Generate a simple menu with 2 items. Return JSON with 'items' array containing objects with 'name' and 'price' fields."
        }
    ]
    
    schema = {
        "type": "object",
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "price": {"type": "number"}
                    },
                    "required": ["name", "price"]
                }
            }
        },
        "required": ["items"]
    }
    
    try:
        result = await client.generate_json(messages=messages, schema=schema)
        print(f"✓ Response received")
        print(f"✓ Response is valid JSON")
        print(f"✓ Response structure: {json.dumps(result, indent=2)}")
        
        # Validate structure
        if "items" in result and isinstance(result["items"], list):
            print(f"✓ Schema validation passed: found {len(result['items'])} items")
        else:
            print(f"✗ Schema validation failed: 'items' field missing or invalid")
            return False
            
    except Exception as e:
        print(f"✗ Test failed: {e}")
        return False
    
    # Test 2: Menu plan generation (closer to real use case)
    print("\nTest 2: Menu Plan Generation")
    print("-" * 40)
    
    menu_messages = [
        {
            "role": "system",
            "content": "You are a meal planning assistant. Always respond with valid JSON."
        },
        {
            "role": "user",
            "content": """Generate a daily menu plan. Return JSON with:
{
  "status": "ok",
  "selected_cuisine": "italian",
  "menus": [
    {
      "menu_type": "daily",
      "courses": [
        {
          "course_header": "Main",
          "recipe_options": [
            {
              "recipe_id": "pasta_001",
              "recipe_name": {"en": "Spaghetti Carbonara"}
            }
          ]
        }
      ]
    }
  ]
}"""
        }
    ]
    
    menu_schema = {
        "type": "object",
        "properties": {
            "status": {"type": "string"},
            "selected_cuisine": {"type": "string"},
            "menus": {"type": "array"}
        },
        "required": ["status", "selected_cuisine", "menus"]
    }
    
    try:
        result = await client.generate_json(messages=menu_messages, schema=menu_schema)
        print(f"✓ Menu plan received")
        
        if result.get("status") == "ok":
            print(f"✓ Status: OK")
        
        if result.get("selected_cuisine"):
            print(f"✓ Cuisine: {result['selected_cuisine']}")
        
        if result.get("menus"):
            print(f"✓ Menus: {len(result['menus'])} menu(s) generated")
        
        print(f"\nFull response:")
        print(json.dumps(result, indent=2))
        
    except Exception as e:
        print(f"✗ Menu plan test failed: {e}")
        return False
    
    print(f"\n{'='*60}")
    print(f"✓ All tests passed for {provider_name.upper()}")
    print(f"{'='*60}\n")
    
    return True


async def main():
    if len(sys.argv) < 2:
        print("Usage: python test_llm_providers.py <provider>")
        print("Providers: mock, openai, anthropic")
        sys.exit(1)
    
    provider = sys.argv[1].lower()
    
    if provider not in ["mock", "openai", "anthropic"]:
        print(f"Invalid provider: {provider}")
        print("Valid providers: mock, openai, anthropic")
        sys.exit(1)
    
    success = await test_provider(provider)
    
    if success:
        print("\n✅ Provider test successful!")
        sys.exit(0)
    else:
        print("\n❌ Provider test failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
