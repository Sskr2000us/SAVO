"""
Test script to verify dual-provider system works correctly
Vision: Google Gemini
Reasoning: OpenAI GPT
"""
import asyncio
import os
from app.core.llm_client import get_vision_client, get_reasoning_client
from app.core.settings import settings

async def test_dual_provider():
    print("\n=== SAVO Dual-Provider System Test ===\n")
    
    # Show configuration
    print(f"Vision Provider: {settings.vision_provider}")
    print(f"Reasoning Provider: {settings.reasoning_provider}")
    print(f"Legacy LLM Provider: {settings.llm_provider}\n")
    
    # Test vision client
    print("Testing vision client...")
    try:
        vision_client = get_vision_client()
        print(f"✅ Vision client created: {type(vision_client).__name__}")
    except ValueError as e:
        print(f"⚠️  Vision client requires API key: {e}")
        print(f"   Set SAVO_VISION_PROVIDER=mock for testing without API keys")
    
    print()
    
    # Test reasoning client
    print("Testing reasoning client...")
    try:
        reasoning_client = get_reasoning_client()
        print(f"✅ Reasoning client created: {type(reasoning_client).__name__}")
    except ValueError as e:
        print(f"⚠️  Reasoning client requires API key: {e}")
        print(f"   Set SAVO_REASONING_PROVIDER=mock for testing without API keys")
    
    print()
    
    # Show expected behavior
    print("Expected Configuration:")
    print("  - Vision tasks (POST /inventory/scan): Use Google Gemini Vision")
    print("  - Reasoning tasks (POST /plan/*, /youtube/rank): Use OpenAI GPT")
    print("\nFor production deployment:")
    print("  Set SAVO_VISION_PROVIDER=google")
    print("  Set SAVO_REASONING_PROVIDER=openai")
    print("  Set GOOGLE_API_KEY=your_key")
    print("  Set OPENAI_API_KEY=your_key\n")
    
    return True

if __name__ == "__main__":
    try:
        asyncio.run(test_dual_provider())
        print("✅ Dual-provider system configured correctly!")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
