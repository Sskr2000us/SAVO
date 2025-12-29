"""Test weekly planning endpoint"""
import asyncio
import httpx

async def test():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "http://localhost:8000/plan/weekly",
            json={
                "start_date": "2025-12-29",
                "num_days": 3
            },
            timeout=30.0
        )
        print(f"Status: {response.status_code}")
        data = response.json()
        print(f"\nPlanning window: {data.get('planning_window')}")
        print(f"Number of menus: {len(data.get('menus', []))}")
        for i, menu in enumerate(data.get('menus', [])):
            print(f"\nMenu {i+1}:")
            print(f"  Type: {menu.get('menu_type')}")
            print(f"  Day index: {menu.get('day_index')}")
            print(f"  Date: {menu.get('date')}")

asyncio.run(test())
