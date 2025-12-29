"""Quick test script for daily planning endpoint"""
import asyncio
import httpx

async def test_daily():
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://localhost:8000/plan/daily",
                json={
                    "time_available_minutes": 60,
                    "servings": 4
                },
                timeout=30.0
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text[:500]}")
        except Exception as e:
            print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_daily())
