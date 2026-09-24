"""叫号排队的共享时钟规则。

作废判定与开立染程拦截都走本模块，保证两侧使用同一套时钟：
- 叫号后 CALL_TIMEOUT_MINUTES 分钟内必须开出染程；
- 超过时限的已叫号号在被访问时惰性作废；
- 仅「已叫号且未超时、未作废、未完成」的号允许开立染程。
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.queue_ticket import QueueTicket

CALL_TIMEOUT_MINUTES = settings.queue_call_timeout_minutes


def now() -> datetime:
    return datetime.now(timezone.utc)


def as_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """归一化为 UTC 带时区时间（SQLite 读回会丢失时区，按 UTC 处理）。"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def call_deadline(called_at: datetime) -> datetime:
    return as_aware(called_at) + timedelta(minutes=CALL_TIMEOUT_MINUTES)


def is_call_expired(ticket: QueueTicket, at: Optional[datetime] = None) -> bool:
    """已叫号号是否已超过开立时限。未叫号不视为超时。"""
    if ticket.called_at is None:
        return False
    at = as_aware(at) or now()
    return at >= call_deadline(ticket.called_at)


def is_active(ticket: QueueTicket, at: Optional[datetime] = None) -> bool:
    """未作废且未完成（可能已超时——超时需经 expire_ticket 落库作废）。"""
    return ticket.voided_at is None and ticket.completed_at is None


def get_active_ticket(db: Session, vat_id: int, at: Optional[datetime] = None):
    """取该缸唯一的未作废未完成号；没有则 None。"""
    at = as_aware(at) or now()
    ticket = (
        db.query(QueueTicket)
        .filter(
            QueueTicket.vat_id == vat_id,
            QueueTicket.voided_at.is_(None),
            QueueTicket.completed_at.is_(None),
        )
        .first()
    )
    return ticket


def expire_ticket(db: Session, ticket: QueueTicket, at: Optional[datetime] = None) -> bool:
    """已叫号且超时则把号作废（voided_at 落为超时时刻）。

    返回 True 表示本次调用把它作废了。作废时刻取「叫号时限到期时刻」，
    与开立拦截共用同一时钟，避免作废时刻晚于拦截判定。
    """
    if not is_active(ticket) or ticket.called_at is None:
        return False
    deadline = call_deadline(ticket.called_at)
    at = as_aware(at) or now()
    if at < deadline:
        return False
    ticket.voided_at = deadline
    db.flush()
    return True


def openable_ticket_or_409(db: Session, vat_id: int, at: Optional[datetime] = None):
    """开立染程前的统一闸口：返回可挂的号，否则抛 409 中文。

    规则：
    - 无未完成号 → 未叫号，禁止开染程；
    - 已叫号超时 → 惰性作废后按已作废拒绝；
    - 仅已叫号、未超时、未作废未完成 → 放行。
    """
    from fastapi import HTTPException

    at = as_aware(at) or now()
    ticket = get_active_ticket(db, vat_id, at)
    if ticket is None:
        raise HTTPException(status_code=409, detail="该染缸尚未叫号，禁止开出染程，请先取号并等待主管叫号")
    if ticket.called_at is None:
        raise HTTPException(status_code=409, detail="该排队号尚未叫号，禁止开出染程，请等待主管叫号")
    if expire_ticket(db, ticket, at):
        raise HTTPException(
            status_code=409,
            detail=f"排队号已超过叫号后 {CALL_TIMEOUT_MINUTES} 分钟时限，自动作废，请重新取号",
        )
    return ticket


def expire_all_due(db: Session, at: Optional[datetime] = None) -> int:
    """把所有「已叫号且超时」的在途号统一作废，返回作废条数。

    列表/看板读取前调用，保证展示状态与开立拦截的时钟判定一致。
    """
    at = as_aware(at) or now()
    tickets = (
        db.query(QueueTicket)
        .filter(
            QueueTicket.voided_at.is_(None),
            QueueTicket.completed_at.is_(None),
            QueueTicket.called_at.isnot(None),
        )
        .all()
    )
    count = 0
    for ticket in tickets:
        if expire_ticket(db, ticket, at):
            count += 1
    if count:
        db.flush()
    return count


def ticket_state(ticket: QueueTicket, at: Optional[datetime] = None) -> str:
    """对外状态；已叫号但超时的在途号在展示上即视为作废。"""
    at = as_aware(at) or now()
    if ticket.completed_at is not None:
        return "completed"
    if ticket.voided_at is not None:
        return "voided"
    if ticket.called_at is None:
        return "waiting"
    if at >= call_deadline(ticket.called_at):
        return "voided"
    return "called"


def serialize_ticket(ticket: QueueTicket, at: Optional[datetime] = None):
    from app.schemas.queue_ticket import QueueTicketOut

    at = as_aware(at) or now()
    state = ticket_state(ticket, at)
    expired = state == "voided" and ticket.voided_at is None
    deadline = call_deadline(ticket.called_at) if ticket.called_at is not None else None
    return QueueTicketOut(
        id=ticket.id,
        vat_id=ticket.vat_id,
        taken_at=ticket.taken_at,
        called_at=ticket.called_at,
        voided_at=ticket.voided_at,
        completed_at=ticket.completed_at,
        taken_by=ticket.taken_by,
        state=state,
        deadline_at=deadline,
        expired=expired,
    )
