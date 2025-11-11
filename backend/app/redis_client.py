"""Redis缓存和消息队列模块"""
from __future__ import annotations

import os
import json
from typing import Optional, Any
from contextlib import asynccontextmanager

try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None


class RedisManager:
    """Redis管理器 - 用于缓存和消息队列"""
    
    def __init__(self):
        self.redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
        self.client: Optional[redis.Redis] = None
        self.enabled = REDIS_AVAILABLE and os.getenv("REDIS_ENABLED", "false").lower() == "true"
    
    async def connect(self):
        """连接Redis"""
        if not self.enabled:
            print("Redis未启用或未安装redis库")
            return
        
        try:
            self.client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
            await self.client.ping()
            print(f"✅ Redis连接成功: {self.redis_url}")
        except Exception as e:
            print(f"⚠️ Redis连接失败: {e}")
            self.enabled = False
            self.client = None
    
    async def disconnect(self):
        """断开Redis连接"""
        if self.client:
            await self.client.close()
            print("Redis连接已关闭")
    
    async def set_user_online(self, user_id: int, username: str) -> bool:
        """设置用户在线状态"""
        if not self.enabled or not self.client:
            return False
        
        try:
            await self.client.hset(
                f"user:{user_id}",
                mapping={
                    "online": "true",
                    "username": username,
                    "last_seen": str(int(__import__("time").time())),
                },
            )
            return True
        except Exception as e:
            print(f"设置用户在线状态失败: {e}")
            return False
    
    async def set_user_offline(self, user_id: int) -> bool:
        """设置用户离线状态"""
        if not self.enabled or not self.client:
            return False
        
        try:
            await self.client.hset(f"user:{user_id}", "online", "false")
            return True
        except Exception as e:
            print(f"设置用户离线状态失败: {e}")
            return False
    
    async def is_user_online(self, user_id: int) -> bool:
        """检查用户是否在线"""
        if not self.enabled or not self.client:
            return False
        
        try:
            online = await self.client.hget(f"user:{user_id}", "online")
            return online == "true"
        except Exception:
            return False
    
    async def queue_message(self, user_id: int, message: dict) -> bool:
        """将消息加入用户离线消息队列"""
        if not self.enabled or not self.client:
            return False
        
        try:
            await self.client.lpush(
                f"user:{user_id}:pending_msgs",
                json.dumps(message, ensure_ascii=False),
            )
            # 设置7天过期
            await self.client.expire(f"user:{user_id}:pending_msgs", 7 * 24 * 3600)
            return True
        except Exception as e:
            print(f"消息入队失败: {e}")
            return False
    
    async def get_pending_messages(self, user_id: int) -> list[dict]:
        """获取用户所有离线消息"""
        if not self.enabled or not self.client:
            return []
        
        try:
            key = f"user:{user_id}:pending_msgs"
            messages = await self.client.lrange(key, 0, -1)
            if messages:
                # 清空队列
                await self.client.delete(key)
                return [json.loads(msg) for msg in messages]
            return []
        except Exception as e:
            print(f"获取离线消息失败: {e}")
            return []
    
    async def cache_set(self, key: str, value: Any, expire: int = 3600) -> bool:
        """设置缓存"""
        if not self.enabled or not self.client:
            return False
        
        try:
            await self.client.setex(
                key,
                expire,
                json.dumps(value, ensure_ascii=False) if isinstance(value, (dict, list)) else str(value),
            )
            return True
        except Exception as e:
            print(f"设置缓存失败: {e}")
            return False
    
    async def cache_get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if not self.enabled or not self.client:
            return None
        
        try:
            value = await self.client.get(key)
            if value:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return value
            return None
        except Exception as e:
            print(f"获取缓存失败: {e}")
            return None


# 全局Redis管理器实例
redis_manager = RedisManager()
