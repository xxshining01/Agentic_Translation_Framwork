import httpx
import asyncio

async def main():
    try:
        resp = await httpx.AsyncClient().post(
            'http://127.0.0.1:1234/v1/chat/completions',
            json={
                'model': 'local-model',
                'messages': [{'role': 'user', 'content': 'test ' * 5000}]
            },
            timeout=10
        )
        print(f"5000 tokens response: {resp.status_code} {resp.text[:100]}")
    except Exception as e:
        print(f"5000 tokens error: {e}")

asyncio.run(main())
