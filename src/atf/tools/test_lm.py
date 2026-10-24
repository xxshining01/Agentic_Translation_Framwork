import httpx
import asyncio
import json

async def test():
    payload = {
        "model": "local-model",
        "messages": [
            {"role": "user", "content": "Hello! Are you working?"}
        ]
    }
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "http://127.0.0.1:1234/v1/chat/completions",
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=30.0
            )
            print(f"Status: {response.status_code}")
            print(f"Response: {response.text}")
        except Exception as e:
            print(f"Error: {e}")

asyncio.run(test())
