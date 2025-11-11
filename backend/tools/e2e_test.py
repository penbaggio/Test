import asyncio
import json
import time
import requests
import websockets

BASE = "http://127.0.0.1:8000"
WS = "ws://127.0.0.1:8000/ws"


def login(username: str, password: str) -> str:
    resp = requests.post(
        f"{BASE}/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


async def main():
    trader_token = login("trader1", "test123")
    im_token = login("im1", "test123")

    async with websockets.connect(f"{WS}?token={trader_token}") as websocket:
        print("[WS] connected as trader, waiting for push...")
        # Prime receive task
        recv_task = asyncio.create_task(websocket.recv())
        # Create instruction
        payload = {
            "title": "e2e测试-买入",
            "asset_code": "600000.SH",
            "side": "BUY",
            "qty": 100,
            "price_type": "MKT",
            "limit_price": None,
        }
        r = requests.post(
            f"{BASE}/instructions",
            json=payload,
            headers={"Authorization": f"Bearer {im_token}"},
            timeout=10,
        )
        print("[HTTP] create instruction:", r.status_code)
        r.raise_for_status()
        created = r.json()
        # Wait for WS message
        msg = await asyncio.wait_for(recv_task, timeout=10)
        print("[WS] received:", msg)

        # ACK as trader
        r2 = requests.post(
            f"{BASE}/instructions/{created['id']}/ack",
            headers={"Authorization": f"Bearer {trader_token}"},
            timeout=10,
        )
        print("[HTTP] ack:", r2.status_code)
        r2.raise_for_status()

        # EXECUTE as trader
        r3 = requests.post(
            f"{BASE}/instructions/{created['id']}/execute",
            headers={"Authorization": f"Bearer {trader_token}"},
            timeout=10,
        )
        print("[HTTP] execute:", r3.status_code)
        r3.raise_for_status()


if __name__ == "__main__":
    asyncio.run(main())
