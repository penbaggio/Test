from __future__ import annotations

from datetime import datetime
from typing import Optional, Literal, List

from pydantic import BaseModel, Field


# ---- Auth ----
class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    user_id: int
    username: str
    role: Literal["INVESTMENT_MANAGER", "TRADER", "ADMIN"]


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    is_active: bool

    class Config:
        from_attributes = True


# ---- Instructions ----
class InstructionCreate(BaseModel):
    title: str = Field(..., max_length=200)
    asset_code: str = Field(..., max_length=50)
    side: Literal["BUY", "SELL"]
    qty: float = Field(..., gt=0)
    price_type: Literal["LIMIT", "MKT"]
    limit_price: float | None = Field(None, ge=0)
    # 新增字段
    target_traders: Optional[List[int]] = None  # 指定交易员ID列表
    urgency: Literal["HIGH", "NORMAL", "LOW"] = "NORMAL"  # 紧急程度
    deadline: Optional[datetime] = None  # 执行截止时间
    remarks: Optional[str] = None  # 备注说明


class InstructionOut(BaseModel):
    id: int
    title: str
    asset_code: str
    side: str
    qty: float
    price_type: str
    limit_price: float | None
    status: str
    created_at: datetime
    created_by: int
    # 新增字段
    target_traders: Optional[str] = None
    urgency: str
    deadline: Optional[datetime] = None
    remarks: Optional[str] = None
    updated_at: datetime

    class Config:
        from_attributes = True


# ---- 新增：交易员回执 ----
class AcknowledgmentCreate(BaseModel):
    """交易员回执创建"""
    ack_type: Literal["RECEIVED", "IN_PROGRESS", "COMPLETED", "FAILED"]
    execution_price: Optional[float] = Field(None, ge=0)
    execution_qty: Optional[float] = Field(None, gt=0)
    execution_time: Optional[datetime] = None
    remarks: Optional[str] = None


class AcknowledgmentOut(BaseModel):
    """交易员回执输出"""
    id: int
    instruction_id: int
    trader_id: int
    ack_type: str
    ack_time: datetime
    execution_price: Optional[float]
    execution_qty: Optional[float]
    execution_time: Optional[datetime]
    remarks: Optional[str]

    class Config:
        from_attributes = True


# ---- 新增：指令日志 ----
class InstructionLogOut(BaseModel):
    """指令日志输出"""
    id: int
    instruction_id: int
    action: str
    actor_id: int
    actor_role: str
    timestamp: datetime
    notes: Optional[str]
    ip_address: Optional[str]

    class Config:
        from_attributes = True
