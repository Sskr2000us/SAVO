import json
import asyncio

import httpx

from app.main import app


async def main() -> None:
    transport = httpx.ASGITransport(app=app)

    png_bytes = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
        b"\x00\x00\x00\x0bIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
    )

    files = {"image": ("test.png", png_bytes, "image/png")}
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/inventory/scan", files=files)
        print("status", r.status_code)
        print(json.dumps(r.json(), indent=2)[:1000])


if __name__ == "__main__":
    asyncio.run(main())
