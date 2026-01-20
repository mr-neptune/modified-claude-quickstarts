import asyncio
import httpx

BASE = "http://127.0.0.1:8000"

async def create_session(client):
    r = await client.post(f"{BASE}/sessions")
    r.raise_for_status()
    return r.json()["id"]

async def add_messages(client, session_id, n=20):
    for i in range(n):
        await client.post(
            f"{BASE}/sessions/{session_id}/messages",
            json={"role": "user", "content": f"msg {i}"},
        )

async def main():
    async with httpx.AsyncClient() as client:
        session_ids = await asyncio.gather(*(create_session(client) for _ in range(5)))
        await asyncio.gather(*(add_messages(client, sid) for sid in session_ids))
    print("done")

asyncio.run(main())
