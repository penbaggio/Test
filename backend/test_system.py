"""
系统功能测试脚本
测试所有核心功能是否正常工作
"""
import asyncio
import httpx
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

# 测试用户
USERS = {
    "im": {"username": "im1", "password": "test123"},
    "trader": {"username": "trader1", "password": "test123"},
    "admin": {"username": "admin1", "password": "test123"},
}


async def login(username: str, password: str) -> str:
    """登录获取token"""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/auth/token",
            data={"username": username, "password": password},
        )
        if response.status_code == 200:
            return response.json()["access_token"]
        raise Exception(f"登录失败: {response.text}")


async def test_create_instruction(token: str):
    """测试创建指令"""
    print("\n📝 测试: 创建指令...")
    async with httpx.AsyncClient() as client:
        payload = {
            "title": "测试买入指令",
            "asset_code": "600000.SH",
            "side": "BUY",
            "qty": 100,
            "price_type": "LIMIT",
            "limit_price": 10.50,
            "urgency": "HIGH",
            "remarks": "自动化测试",
        }
        response = await client.post(
            f"{BASE_URL}/instructions",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 创建成功: 指令 #{data['id']}")
            return data['id']
        else:
            print(f"❌ 创建失败: {response.text}")
            return None


async def test_list_instructions(token: str, role: str):
    """测试查询指令"""
    print(f"\n📋 测试: 查询指令 ({role})...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/instructions",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 查询成功: 共 {len(data)} 条指令")
            return data
        else:
            print(f"❌ 查询失败: {response.text}")
            return []


async def test_acknowledge_instruction(token: str, instruction_id: int):
    """测试交易员回执"""
    print(f"\n✍️ 测试: 回执指令 #{instruction_id}...")
    async with httpx.AsyncClient() as client:
        payload = {
            "ack_type": "COMPLETED",
            "execution_price": 10.48,
            "execution_qty": 100,
            "execution_time": datetime.utcnow().isoformat(),
        }
        response = await client.post(
            f"{BASE_URL}/instructions/{instruction_id}/ack",
            json=payload,
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            print(f"✅ 回执成功")
            return True
        else:
            print(f"❌ 回执失败: {response.text}")
            return False


async def test_get_logs(token: str, instruction_id: int):
    """测试获取日志"""
    print(f"\n📜 测试: 获取指令日志 #{instruction_id}...")
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/instructions/{instruction_id}/logs",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            logs = response.json()
            print(f"✅ 获取成功: 共 {len(logs)} 条日志")
            for log in logs:
                print(f"   - {log['action']} by {log['actor_role']} at {log['timestamp']}")
            return logs
        else:
            print(f"❌ 获取失败: {response.text}")
            return []


async def test_cancel_instruction(token: str, instruction_id: int):
    """测试撤销指令"""
    print(f"\n🚫 测试: 撤销指令 #{instruction_id}...")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/instructions/{instruction_id}/cancel",
            headers={"Authorization": f"Bearer {token}"},
        )
        if response.status_code == 200:
            print(f"✅ 撤销成功")
            return True
        else:
            print(f"❌ 撤销失败: {response.text}")
            return False


async def main():
    """主测试流程"""
    print("=" * 60)
    print("🧪 投资交易指令分发系统 - 功能测试")
    print("=" * 60)

    try:
        # 1. 登录所有用户
        print("\n🔐 步骤1: 用户登录")
        im_token = await login(USERS["im"]["username"], USERS["im"]["password"])
        print(f"✅ 投资经理登录成功")

        trader_token = await login(USERS["trader"]["username"], USERS["trader"]["password"])
        print(f"✅ 交易员登录成功")

        admin_token = await login(USERS["admin"]["username"], USERS["admin"]["password"])
        print(f"✅ 管理员登录成功")

        # 2. 投资经理创建指令
        print("\n📊 步骤2: 投资经理创建指令")
        instruction_id = await test_create_instruction(im_token)
        if not instruction_id:
            print("❌ 测试失败: 无法创建指令")
            return

        # 等待一下让WebSocket推送
        await asyncio.sleep(0.5)

        # 3. 各角色查询指令
        print("\n📊 步骤3: 查询指令列表")
        await test_list_instructions(im_token, "投资经理")
        await test_list_instructions(trader_token, "交易员")
        await test_list_instructions(admin_token, "管理员")

        # 4. 交易员回执
        print("\n📊 步骤4: 交易员执行回执")
        await test_acknowledge_instruction(trader_token, instruction_id)

        # 5. 查看日志
        print("\n📊 步骤5: 查看操作日志")
        await test_get_logs(admin_token, instruction_id)

        # 6. 创建新指令用于测试撤销
        print("\n📊 步骤6: 测试撤销功能")
        cancel_id = await test_create_instruction(im_token)
        if cancel_id:
            await test_cancel_instruction(im_token, cancel_id)

        print("\n" + "=" * 60)
        print("✅ 所有测试完成!")
        print("=" * 60)

    except Exception as e:
        print(f"\n❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\n⚠️  确保系统已启动: uvicorn app.main:app --reload\n")
    asyncio.run(main())
