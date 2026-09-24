from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_admin
from app.database import get_db
from app.models.dye_house import DyeHouse
from app.models.queue_ticket import QueueTicket
from app.models.user import User
from app.models.vat import Vat
from app.schemas.queue_ticket import QueueTicketCreate, QueueTicketOut, QueueTicketListItem
from app.services import queue_service as qs

router = APIRouter(prefix="/api/queue", tags=["queue"])


def _status_of(ticket: QueueTicket) -> str:
    if ticket.voided_at is not None:
        return "voided"
    if ticket.completed_at is not None:
        return "completed"
    if ticket.called_at is not None:
        return "called"
    return "taken"


def _decorate(ticket: QueueTicket, out_cls=QueueTicketOut, **extra):
    """补充 status / expiresAt 派生字段。"""
    st = _status_of(ticket)
    expires_at = qs.call_deadline(ticket.called_at) if ticket.called_at else None
    out = out_cls.model_validate(ticket)
    return out.model_copy(update={"status": st, "expires_at": expires_at, **extra})


@router.get("", response_model=List[QueueTicketListItem])
def list_tickets(
    vat_id: Optional[int] = Query(None, alias="vatId"),
    scope: str = Query("active", pattern="^(active|all)$"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """排队列表。

    scope=active（默认）：未作废且未完成的号（叫号超时者先统一自动作废，与开立拦截共用时钟）；
    scope=all：全部历史号。
    """
    current = qs.now()
    qs.sweep_expired(db, current)

    q = (
        db.query(QueueTicket, Vat.vat_code, DyeHouse.name)
        .join(Vat, Vat.id == QueueTicket.vat_id)
        .join(DyeHouse, DyeHouse.id == Vat.dye_house_id)
    )
    if vat_id is not None:
        q = q.filter(QueueTicket.vat_id == vat_id)
    if scope == "active":
        q = q.filter(QueueTicket.voided_at.is_(None), QueueTicket.completed_at.is_(None))
    rows = q.order_by(QueueTicket.id.desc()).all()
    return [
        _decorate(t, QueueTicketListItem, vat_code=code, house_name=house)
        for t, code, house in rows
    ]


@router.post("/take", response_model=QueueTicketOut, status_code=status.HTTP_201_CREATED)
def take_ticket(
    payload: QueueTicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """操作员可取号。同缸未作废且未完成的号同时最多一个。"""
    vat = db.query(Vat).filter(Vat.id == payload.vat_id).first()
    if not vat:
        raise HTTPException(status_code=400, detail="染缸不存在")
    taken_by = payload.taken_by.strip() or current_user.display_name
    ticket = qs.take_ticket(db, vat, taken_by)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该染缸已有未完成的排队号，请等待叫号或作废后再取")
    db.refresh(ticket)
    return _decorate(ticket)


@router.post("/{ticket_id}/call", response_model=QueueTicketOut)
def call_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    """叫号仅主管。叫号后 30 分钟内必须开出染程，超时自动作废。"""
    ticket = qs.call_ticket(db, ticket_id)
    db.commit()
    db.refresh(ticket)
    return _decorate(ticket)
