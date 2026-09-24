"""叫号排队领域服务。

作废判定与开立染程拦截共用本模块的同一套时钟规则：
- 号被叫号（called_at 非空）后 CALL_TIMEOUT_MINUTES 分钟内必须开出染程；
- 超过时限，下一次任何读/写该缸排队状态的操作都会把它自动作废（voided_at 置为当前时刻）。
"""

from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.dye_lot import DyeLot
from app.models.queue_ticket import QueueTicket
from app.models.vat import Vat

# 叫号后必须在 30 分钟内开出染程，超时自动作废
CALL_TIMEOUT_MINUTES = 30


def now() -> datetime:
    """全排队流程共用时钟（UTC，带时区）。"""
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """数据库（如 SQLite）可能返回 naive 时间，统一按 UTC 补上时区以便比较。"""
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def call_deadline(called_at: datetime) -> datetime:
    return _aware(called_at) + timedelta(minutes=CALL_TIMEOUT_MINUTES)


def _is_expired(ticket: QueueTicket, current: datetime) -> bool:
    called_at = _aware(ticket.called_at)
    return (
        called_at is not None
        and ticket.voided_at is None
        and ticket.completed_at is None
        and current >= call_deadline(called_at)
    )


def _apply_expiry(ticket: QueueTicket, current: datetime) -> QueueTicket:
    """若号已超时则就地作废，并返回原号。"""
    if _is_expired(ticket, current):
        ticket.voided_at = current
    return ticket


def active_ticket(
    db: Session,
    vat_id: int,
    current: Optional[datetime] = None,
    for_update: bool = False,
) -> Optional[QueueTicket]:
    """取某染缸当前「未作废且未完成」的号；若叫号已超时则先自动作废。

    作废判定、列表展示、看板计数、开立拦截都经此函数，规则保持一致。
    for_update=True 时对号行加锁（开立染程消费号用，防并发重复消费）。
    """
    current = current or now()
    q = db.query(QueueTicket).filter(
        QueueTicket.vat_id == vat_id,
        QueueTicket.voided_at.is_(None),
        QueueTicket.completed_at.is_(None),
    )
    if for_update:
        q = q.with_for_update()
    ticket = q.order_by(QueueTicket.id.desc()).first()
    if ticket is None:
        return None
    _apply_expiry(ticket, current)
    if ticket.voided_at is not None:
        db.flush()
        return None
    return ticket


def sweep_expired(db: Session, current: Optional[datetime] = None) -> int:
    """把所有叫号超时的活动号批量作废，返回作废条数。"""
    current = current or now()
    bound = current - timedelta(minutes=CALL_TIMEOUT_MINUTES)
    updated = (
        db.query(QueueTicket)
        .filter(
            QueueTicket.voided_at.is_(None),
            QueueTicket.completed_at.is_(None),
            QueueTicket.called_at.isnot(None),
            QueueTicket.called_at <= bound,
        )
        .update({QueueTicket.voided_at: current}, synchronize_session=False)
    )
    if updated:
        db.flush()
    return updated


def waiting_count(db: Session, current: Optional[datetime] = None) -> int:
    """等待叫号条数：已取号、未叫号、未作废、未完成（与排队列表等待行口径一致）。"""
    current = current or now()
    sweep_expired(db, current)
    return (
        db.query(QueueTicket)
        .filter(
            QueueTicket.voided_at.is_(None),
            QueueTicket.completed_at.is_(None),
            QueueTicket.called_at.is_(None),
        )
        .count()
    )


def take_ticket(db: Session, vat: Vat, taken_by: str, current: Optional[datetime] = None) -> QueueTicket:
    """取号：同缸未作废且未完成的号同时最多一个。"""
    current = current or now()
    existing = active_ticket(db, vat.id, current)
    if existing is not None:
        raise HTTPException(status_code=409, detail="该染缸已有未完成的排队号，请等待叫号或作废后再取")
    ticket = QueueTicket(vat_id=vat.id, taken_at=current, taken_by=taken_by)
    db.add(ticket)
    db.flush()
    return ticket


def call_ticket(db: Session, ticket_id: int, current: Optional[datetime] = None) -> QueueTicket:
    """叫号：仅主管可调用（角色在路由层限制）。"""
    current = current or now()
    ticket = db.query(QueueTicket).filter(QueueTicket.id == ticket_id).first()
    if ticket is None:
        raise HTTPException(status_code=404, detail="排队号不存在")
    if ticket.completed_at is not None:
        raise HTTPException(status_code=409, detail="该排队号已完成，不能叫号")
    if ticket.voided_at is not None:
        raise HTTPException(status_code=409, detail="该排队号已作废，不能叫号")
    if ticket.called_at is not None:
        raise HTTPException(status_code=409, detail="该排队号已叫过号")
    # 同缸同时最多一个活动号；若已有其他活动号（理论上取号已拦住），这里再兜底
    other = active_ticket(db, ticket.vat_id, current)
    if other is not None and other.id != ticket.id:
        raise HTTPException(status_code=409, detail="该染缸已有叫号中的排队号")
    ticket.called_at = current
    db.flush()
    return ticket


def require_call_for_lot(
    db: Session, vat_id: int, current: Optional[datetime] = None
) -> QueueTicket:
    """开立染程前的强制叫号校验，失败一律 409 中文。

    返回可被本笔染程消费的有效号（已叫号且未超时）。
    """
    current = current or now()
    ticket = active_ticket(db, vat_id, current, for_update=True)
    if ticket is not None:
        if ticket.called_at is None:
            raise HTTPException(status_code=409, detail="排队号尚未叫号，禁止开染程")
        # active_ticket 已处理超时作废；此处理论上不可达，防御一次
        if current >= call_deadline(ticket.called_at):
            ticket.voided_at = current
            db.flush()
            raise HTTPException(
                status_code=409,
                detail=f"叫号已超过 {CALL_TIMEOUT_MINUTES} 分钟，该号已作废，禁止开染程",
            )
        return ticket

    # 无活动号：若最近一号是叫号超时被（本次）作废，给出超时提示；其余按未叫号处理
    latest = (
        db.query(QueueTicket)
        .filter(QueueTicket.vat_id == vat_id)
        .order_by(QueueTicket.id.desc())
        .first()
    )
    if (
        latest is not None
        and latest.completed_at is None
        and latest.called_at is not None
        and latest.voided_at is not None
        and current >= call_deadline(latest.called_at)
    ):
        raise HTTPException(
            status_code=409,
            detail=f"叫号已超过 {CALL_TIMEOUT_MINUTES} 分钟，该号已作废，禁止开染程",
        )
    raise HTTPException(status_code=409, detail="该染缸无有效叫号，未叫号禁止开染程")

def complete_ticket(db: Session, ticket: QueueTicket, lot: DyeLot, current: Optional[datetime] = None) -> None:
    """开立染程成功后把号标记完成并挂到该染程，号不可再用于第二笔染程。"""
    current = current or now()
    ticket.completed_at = current
    ticket.dye_lot_id = lot.id
    db.flush()


def attach_current_tickets(
    db: Session, vats: Iterable[Vat], current: Optional[datetime] = None
) -> None:
    """给染缸对象挂上 current_ticket 属性，供列表展示当前号状态。"""
    current = current or now()
    sweep_expired(db, current)
    vats = list(vats)
    ids = [v.id for v in vats]
    tickets = (
        db.query(QueueTicket)
        .filter(
            QueueTicket.voided_at.is_(None),
            QueueTicket.completed_at.is_(None),
            QueueTicket.vat_id.in_(ids),
        )
        .order_by(QueueTicket.id.desc())
        .all()
    ) if ids else []
    latest: dict[int, QueueTicket] = {}
    for t in tickets:  # 已按 id desc，首条即最新
        latest.setdefault(t.vat_id, t)
    for v in vats:
        setattr(v, "current_ticket", latest.get(v.id))
