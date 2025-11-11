from __future__ import annotations

import json
from typing import List
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .. import schemas
from ..auth import role_required
from ..deps import get_db
from ..models import Instruction, User, InstructionLog, InstructionAcknowledgment
from ..ws import ws_manager
from ..utils import create_instruction_log

router = APIRouter(prefix="/instructions", tags=["instructions"])


@router.post("", response_model=schemas.InstructionOut)
async def create_instruction(
    payload: schemas.InstructionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("INVESTMENT_MANAGER")),
):
    """创建投资指令"""
    # 处理指定交易员
    target_traders_json = None
    if payload.target_traders:
        target_traders_json = json.dumps(payload.target_traders)
    
    instr = Instruction(
        title=payload.title,
        asset_code=payload.asset_code,
        side=payload.side,
        qty=payload.qty,
        price_type=payload.price_type,
        limit_price=payload.limit_price,
        status="SUBMITTED",
        created_by=current_user.id,
        target_traders=target_traders_json,
        urgency=payload.urgency,
        deadline=payload.deadline,
        remarks=payload.remarks,
    )
    db.add(instr)
    db.flush()  # 获取ID但不提交
    
    # 记录操作日志
    create_instruction_log(
        db=db,
        instruction_id=instr.id,
        action="CREATED",
        actor=current_user,
        notes=f"创建指令: {payload.title}",
        request=request,
    )
    
    db.commit()
    db.refresh(instr)

    # WebSocket推送
    notification_data = {
        "type": "instruction.created",
        "data": {
            "id": instr.id,
            "title": instr.title,
            "asset_code": instr.asset_code,
            "side": instr.side,
            "qty": instr.qty,
            "price_type": instr.price_type,
            "limit_price": instr.limit_price,
            "urgency": instr.urgency,
            "deadline": instr.deadline.isoformat() if instr.deadline else None,
            "created_by": current_user.username,
            "created_at": instr.created_at.isoformat(),
        },
    }
    
    # 定向推送或广播
    if payload.target_traders:
        # TODO: 实现定向推送给指定交易员
        await ws_manager.broadcast_to_role(role="TRADER", message=notification_data)
    else:
        await ws_manager.broadcast_to_role(role="TRADER", message=notification_data)
    
    # 同时通知管理员
    await ws_manager.broadcast_to_role(role="ADMIN", message=notification_data)

    return instr


@router.get("", response_model=List[schemas.InstructionOut])
async def list_instructions(
    db: Session = Depends(get_db), current_user: User = Depends(role_required("INVESTMENT_MANAGER", "TRADER", "ADMIN"))
):
    q = db.query(Instruction).order_by(Instruction.id.desc())
    if current_user.role == "INVESTMENT_MANAGER":
        q = q.filter(Instruction.created_by == current_user.id)
    # traders & admin see all in MVP
    return q.all()


@router.post("/{instruction_id}/ack", response_model=schemas.AcknowledgmentOut)
async def create_acknowledgment(
    instruction_id: int,
    payload: schemas.AcknowledgmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("TRADER")),
):
    """交易员回执指令（增强版）"""
    instr = db.get(Instruction, instruction_id)
    if not instr:
        raise HTTPException(status_code=404, detail="指令不存在")
    
    # 创建回执记录
    ack = InstructionAcknowledgment(
        instruction_id=instruction_id,
        trader_id=current_user.id,
        ack_type=payload.ack_type,
        execution_price=payload.execution_price,
        execution_qty=payload.execution_qty,
        execution_time=payload.execution_time,
        remarks=payload.remarks,
    )
    db.add(ack)
    
    # 更新指令状态
    status_map = {
        "RECEIVED": "SENT",
        "IN_PROGRESS": "EXECUTING",
        "COMPLETED": "EXECUTED",
        "FAILED": "FAILED",
    }
    new_status = status_map.get(payload.ack_type, instr.status)
    if instr.status != new_status:
        instr.status = new_status
        db.add(instr)
    
    # 记录操作日志
    create_instruction_log(
        db=db,
        instruction_id=instruction_id,
        action=payload.ack_type,
        actor=current_user,
        notes=payload.remarks or f"回执: {payload.ack_type}",
        request=request,
    )
    
    db.commit()
    db.refresh(ack)
    
    # WebSocket通知
    notification = {
        "type": "instruction.acknowledged",
        "data": {
            "id": instruction_id,
            "trader": current_user.username,
            "ack_type": payload.ack_type,
            "status": new_status,
            "execution_price": payload.execution_price,
            "execution_qty": payload.execution_qty,
        },
    }
    
    await ws_manager.broadcast_to_role(role="INVESTMENT_MANAGER", message=notification)
    await ws_manager.broadcast_to_role(role="TRADER", message=notification)
    await ws_manager.broadcast_to_role(role="ADMIN", message=notification)
    
    return ack


@router.post("/{instruction_id}/cancel")
async def cancel_instruction(
    instruction_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("INVESTMENT_MANAGER")),
):
    """撤销指令（仅限未执行的）"""
    instr = db.get(Instruction, instruction_id)
    if not instr:
        raise HTTPException(status_code=404, detail="指令不存在")
    
    # 权限检查：只能撤销自己的指令
    if instr.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权撤销他人指令")
    
    # 状态检查
    if instr.status not in ["SUBMITTED", "SENT"]:
        raise HTTPException(status_code=400, detail=f"指令状态为{instr.status}，无法撤销")
    
    instr.status = "CANCELLED"
    db.add(instr)
    
    # 记录日志
    create_instruction_log(
        db=db,
        instruction_id=instruction_id,
        action="CANCELLED",
        actor=current_user,
        notes="投资经理撤销指令",
        request=request,
    )
    
    db.commit()
    
    # 通知所有相关方
    notification = {
        "type": "instruction.cancelled",
        "data": {
            "id": instruction_id,
            "title": instr.title,
            "cancelled_by": current_user.username,
        },
    }
    
    await ws_manager.broadcast_to_role(role="TRADER", message=notification)
    await ws_manager.broadcast_to_role(role="ADMIN", message=notification)
    
    return {"ok": True, "message": "指令已撤销"}


@router.get("/{instruction_id}/logs", response_model=List[schemas.InstructionLogOut])
async def get_instruction_logs(
    instruction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("INVESTMENT_MANAGER", "TRADER", "ADMIN")),
):
    """获取指令操作日志"""
    instr = db.get(Instruction, instruction_id)
    if not instr:
        raise HTTPException(status_code=404, detail="指令不存在")
    
    # 权限检查：投资经理只能看自己的
    if current_user.role == "INVESTMENT_MANAGER" and instr.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="无权查看他人指令日志")
    
    logs = db.query(InstructionLog).filter(
        InstructionLog.instruction_id == instruction_id
    ).order_by(InstructionLog.timestamp.desc()).all()
    
    return logs


@router.get("/{instruction_id}/acknowledgments", response_model=List[schemas.AcknowledgmentOut])
async def get_instruction_acknowledgments(
    instruction_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(role_required("INVESTMENT_MANAGER", "TRADER", "ADMIN")),
):
    """获取指令回执记录"""
    instr = db.get(Instruction, instruction_id)
    if not instr:
        raise HTTPException(status_code=404, detail="指令不存在")
    
    acks = db.query(InstructionAcknowledgment).filter(
        InstructionAcknowledgment.instruction_id == instruction_id
    ).order_by(InstructionAcknowledgment.ack_time.desc()).all()
    
    return acks
