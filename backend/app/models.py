from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Float,
    Boolean,
    Text,
    create_engine,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session
import os

# 支持环境变量切换数据库
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./data.db")

# SQLite 需要特殊配置
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), index=True, nullable=False)  # INVESTMENT_MANAGER | TRADER | ADMIN
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    instructions = relationship("Instruction", back_populates="creator")


class Instruction(Base):
    __tablename__ = "instructions"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    asset_code = Column(String(50), index=True, nullable=False)
    side = Column(String(10), nullable=False)  # BUY | SELL
    qty = Column(Float, nullable=False)
    price_type = Column(String(10), nullable=False)  # LIMIT | MKT
    limit_price = Column(Float, nullable=True)
    status = Column(String(20), default="SUBMITTED", nullable=False)  # SUBMITTED | SENT | ACKED | EXECUTING | EXECUTED | CANCELLED | FAILED
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # 新增字段
    target_traders = Column(String(200), nullable=True)  # JSON格式存储交易员ID列表,如 "[1,2,3]"
    urgency = Column(String(10), default="NORMAL", nullable=False)  # HIGH | NORMAL | LOW
    deadline = Column(DateTime, nullable=True)  # 执行截止时间
    remarks = Column(Text, nullable=True)  # 备注说明
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    creator = relationship("User", back_populates="instructions")
    logs = relationship("InstructionLog", back_populates="instruction", cascade="all, delete-orphan")
    acknowledgments = relationship("InstructionAcknowledgment", back_populates="instruction", cascade="all, delete-orphan")


class InstructionLog(Base):
    """指令操作日志表 - 用于审计追踪"""
    __tablename__ = "instruction_logs"

    id = Column(Integer, primary_key=True, index=True)
    instruction_id = Column(Integer, ForeignKey("instructions.id"), nullable=False)
    action = Column(String(50), nullable=False)  # CREATED | SENT | ACKED | EXECUTING | EXECUTED | CANCELLED | FAILED
    actor_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    actor_role = Column(String(20), nullable=False)  # 操作者角色
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    notes = Column(Text, nullable=True)  # 操作说明
    ip_address = Column(String(50), nullable=True)  # 操作IP
    
    instruction = relationship("Instruction", back_populates="logs")
    actor = relationship("User")


class InstructionAcknowledgment(Base):
    """交易员回执表 - 记录执行结果"""
    __tablename__ = "instruction_acknowledgments"

    id = Column(Integer, primary_key=True, index=True)
    instruction_id = Column(Integer, ForeignKey("instructions.id"), nullable=False)
    trader_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    ack_type = Column(String(20), nullable=False)  # RECEIVED | IN_PROGRESS | COMPLETED | FAILED
    ack_time = Column(DateTime, default=datetime.utcnow, nullable=False)
    execution_price = Column(Float, nullable=True)  # 实际成交价格
    execution_qty = Column(Float, nullable=True)  # 实际成交数量
    execution_time = Column(DateTime, nullable=True)  # 实际成交时间
    remarks = Column(Text, nullable=True)  # 回执说明（如失败原因）
    
    instruction = relationship("Instruction", back_populates="acknowledgments")
    trader = relationship("User")


# ---- DB init & seed ----
from passlib.context import CryptContext  # noqa: E402

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def init_db(seed: bool = True) -> None:
    Base.metadata.create_all(bind=engine)
    if not seed:
        return
    db: Session = SessionLocal()
    try:
        # if no users exist, seed three roles
        if db.query(User).count() == 0:
            from sqlalchemy.exc import IntegrityError

            def _add_user(username: str, role: str, password: str = "test123"):
                u = User(
                    username=username,
                    role=role,
                    hashed_password=pwd_context.hash(password),
                )
                db.add(u)

            _add_user("im1", "INVESTMENT_MANAGER")
            _add_user("trader1", "TRADER")
            _add_user("admin1", "ADMIN")
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
    finally:
        db.close()
