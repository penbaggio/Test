import requests

BASE = "http://127.0.0.1:8000"


def login(username: str, password: str) -> str:
    resp = requests.post(
        f"{BASE}/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def create_instruction(token: str):
    payload = {
        "title": "买入测试标的",
        "asset_code": "000001.SZ",
        "side": "BUY",
        "qty": 1000,
        "price_type": "MKT",
        "limit_price": None
    }
    resp = requests.post(
        f"{BASE}/instructions",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    print(resp.status_code, resp.text)


if __name__ == "__main__":
    token = login("im1", "test123")
    create_instruction(token)
