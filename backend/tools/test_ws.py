import asyncio
import json
import requests
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws"


def login(username: str, password: str) -> str:
    resp = requests.post(
        f"{BASE}/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def run():
    token = login("trader1", "test123")
    url = f"{WS}?token={token}"
    print("Connecting to:", url)
    async with websockets.connect(url) as websocket:
        print("Connected. Waiting for messages... (Ctrl+C to exit)")
        # send a ping to keep alive
        await websocket.send(json.dumps({"type": "ping"}))
        while True:
            msg = await websocket.recv()
            print("[WS]", msg)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
