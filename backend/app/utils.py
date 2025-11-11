"""工具函数模块"""
from __future__ import annotations

from datetime import datetime
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import Request

from .models import InstructionLog, User


def create_instruction_log(
    db: Session,
    instruction_id: int,
    action: str,
    actor: User,
    notes: Optional[str] = None,
    request: Optional[Request] = None,
) -> InstructionLog:
    """
    创建指令操作日志
    
    Args:
        db: 数据库会话
        instruction_id: 指令ID
        action: 操作类型 (CREATED | SENT | ACKED | EXECUTING | EXECUTED | CANCELLED | FAILED)
        actor: 操作者用户对象
        notes: 操作说明
        request: FastAPI请求对象(用于获取IP)
    
    Returns:
        创建的日志对象
    """
    ip_address = None
    if request:
        # 获取真实IP (考虑代理情况)
        ip_address = request.headers.get("X-Forwarded-For", request.client.host if request.client else None)
        if ip_address and "," in ip_address:
            ip_address = ip_address.split(",")[0].strip()
    
    log = InstructionLog(
        instruction_id=instruction_id,
        action=action,
        actor_id=actor.id,
        actor_role=actor.role,
        timestamp=datetime.utcnow(),
        notes=notes,
        ip_address=ip_address,
    )
    db.add(log)
    return log


async def send_notification(message: str, webhook_url: Optional[str] = None) -> bool:
    """
    发送告警通知到钉钉/企业微信
    
    Args:
        message: 消息内容
        webhook_url: Webhook地址
    
    Returns:
        是否发送成功
    """
    if not webhook_url:
        return False
    
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            # 钉钉格式
            payload = {
                "msgtype": "text",
                "text": {"content": f"【投资指令系统告警】\n{message}"}
            }
            response = await client.post(webhook_url, json=payload, timeout=5.0)
            return response.status_code == 200
    except Exception as e:
        print(f"发送告警失败: {e}")
        return False
