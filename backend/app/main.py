from __future__ import annotations

import json
from fastapi import FastAPI, WebSocket, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from jose import jwt

from .models import init_db
from .auth import SECRET_KEY, ALGORITHM, get_current_user
from .ws import ws_manager
from .routers import instructions as instructions_router
from .routers import users as users_router
from .redis_client import redis_manager
from .logger import logger

app = FastAPI(title="Investment Instruction Dispatch Service", version="0.3.0")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup():
    """启动时初始化"""
    logger.info("🚀 系统启动中...")
    init_db(seed=True)
    await redis_manager.connect()
    logger.info("✅ 系统启动完成")


@app.on_event("shutdown")
async def _shutdown():
    """关闭时清理资源"""
    logger.info("⏹️ 系统关闭中...")
    await redis_manager.disconnect()
    logger.info("✅ 系统已关闭")


# Routers
app.include_router(users_router.router)
app.include_router(instructions_router.router)


@app.get("/")
async def root():
    return {"status": "ok"}

# Mount static frontend at /app
from pathlib import Path
static_dir = Path(__file__).parent / "static"
app.mount("/app", StaticFiles(directory=str(static_dir), html=True), name="app")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket连接端点"""
    # Expect token as query parameter: /ws?token=...
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4401)
        return
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = int(payload.get("sub"))
        role = payload.get("role")
        username = payload.get("username")
        if not user_id or not role:
            raise ValueError("invalid token")
    except Exception as e:
        logger.error(f"WebSocket认证失败: {e}")
        await websocket.close(code=4401)
        return

    await ws_manager.connect(user_id=user_id, role=role, websocket=websocket)
    
    # 设置用户在线状态
    await redis_manager.set_user_online(user_id, username)
    
    # 发送离线消息
    pending_msgs = await redis_manager.get_pending_messages(user_id)
    if pending_msgs:
        logger.info(f"用户 {username} 有 {len(pending_msgs)} 条离线消息")
        for msg in reversed(pending_msgs):  # 按时间顺序发送
            try:
                await websocket.send_json(msg)
            except Exception as e:
                logger.error(f"发送离线消息失败: {e}")
    
    try:
        # Echo ping/pong or receive client heartbeats
        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text(json.dumps({"type": "pong"}))
    except Exception as e:
        logger.debug(f"WebSocket连接断开: {e}")
    finally:
        ws_manager.disconnect(user_id=user_id, role=role, websocket=websocket)
        await redis_manager.set_user_offline(user_id)
        logger.info(f"用户 {username} 离线")
