"""
Test /youtube/rank endpoint with mock provider
"""
import asyncio
import json

import httpx

from app.main import app


async def main() -> None:
    transport = httpx.ASGITransport(app=app)

    # Sample request: rank YouTube videos for "Risotto al Pomodoro"
    request_body = {
        "recipe_name": "Risotto al Pomodoro",
        "recipe_cuisine": "Italian",
        "recipe_techniques": ["sautéing", "risotto technique", "stirring"],
        "candidates": [
            {
                "video_id": "abc123",
                "title": "Perfect Risotto al Pomodoro - Italian Chef",
                "channel": "Italian Cooking Academy",
                "language": "en",
                "transcript": "Today we make authentic risotto with tomatoes...",
                "metadata": {"duration": "12:45", "views": 500000}
            },
            {
                "video_id": "xyz789",
                "title": "Quick Tomato Rice Recipe",
                "channel": "Fast Food Channel",
                "language": "en",
                "transcript": "This is a quick tomato rice dish...",
                "metadata": {"duration": "5:30", "views": 100000}
            },
            {
                "video_id": "def456",
                "title": "Risotto Master Class - Step by Step",
                "channel": "Culinary Institute",
                "language": "en",
                "transcript": "Welcome to our risotto master class. We'll cover all the techniques...",
                "metadata": {"duration": "25:00", "views": 1000000}
            }
        ],
        "output_language": "en"
    }

    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/youtube/rank", json=request_body)
        
        print(f"Status: {response.status_code}")
        print("\nResponse:")
        result = response.json()
        print(json.dumps(result, indent=2))
        
        if response.status_code == 200:
            print("\n✅ YouTube ranking endpoint working!")
            print(f"Ranked {len(result['ranked_videos'])} videos")
            if result['ranked_videos']:
                top_video = result['ranked_videos'][0]
                print(f"\nTop video: {top_video['title']}")
                print(f"Channel: {top_video['channel']}")
                print(f"Trust score: {top_video['trust_score']}")
                print(f"Match score: {top_video['match_score']}")


if __name__ == "__main__":
    asyncio.run(main())
