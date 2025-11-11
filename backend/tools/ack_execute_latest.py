import requests

BASE = "http://127.0.0.1:8000"

def login(username: str, password: str) -> str:
    r = requests.post(
        f"{BASE}/auth/token",
        data={"username": username, "password": password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def get_latest_instruction(token: str) -> int | None:
    r = requests.get(f"{BASE}/instructions", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    r.raise_for_status()
    data = r.json()
    return data[0]["id"] if data else None


def ack_and_execute(token: str, inst_id: int) -> None:
    r = requests.post(f"{BASE}/instructions/{inst_id}/ack", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    print("ACK:", r.status_code, r.text)
    r.raise_for_status()
    r2 = requests.post(f"{BASE}/instructions/{inst_id}/execute", headers={"Authorization": f"Bearer {token}"}, timeout=10)
    print("EXEC:", r2.status_code, r2.text)
    r2.raise_for_status()


if __name__ == "__main__":
    trader_token = login("trader1", "test123")
    inst_id = get_latest_instruction(trader_token)
    if inst_id is None:
        print("no instruction found")
    else:
        ack_and_execute(trader_token, inst_id)
