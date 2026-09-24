from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import get_current_user, require_supervisor
from app.database import get_db
from app.models.queue_ticket import QueueTicket
from app.models.user import User
from app.models.vat import Vat
from app import queue_service
from app.schemas.queue_ticket import QueueTicketCreate, QueueTicketOut

router = APIRouter(prefix="/api/queue-tickets", tags=["queue-tickets"])


@router.get("", response_model=List[QueueTicketOut])
def list_tickets(
    vat_id: Optional[int] = Query(None, alias="vatId"),
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    expired = queue_service.expire_all_due(db)
    if expired:
        db.commit()
    q = db.query(QueueTicket)
    if vat_id is not None:
        q = q.filter(QueueTicket.vat_id == vat_id)
    tickets = q.order_by(QueueTicket.id.desc()).all()
    return [queue_service.serialize_ticket(t) for t in tickets]


@router.post("", response_model=QueueTicketOut, status_code=status.HTTP_201_CREATED)
def take_ticket(
    payload: QueueTicketCreate,
    db: Session = Depends(get_db),
    current: User = Depends(get_current_user),
):
    """操作员取号：同缸未作废且未完成的号同时最多一个。"""
    vat = db.query(Vat).filter(Vat.id == payload.vat_id).first()
    if not vat:
        raise HTTPException(status_code=400, detail="染缸不存在")
    # 读前先把该缸已超时的已叫号号作废，空出取号名额。
    active = queue_service.get_active_ticket(db, payload.vat_id)
    if active is not None:
        if active.called_at is None:
            raise HTTPException(status_code=409, detail="该染缸已有等待叫号的排队号，不能重复取号")
        if queue_service.expire_ticket(db, active):
            db.commit()
        else:
            raise HTTPException(
                status_code=409,
                detail=f"该染缸已有叫号在有效期内（{queue_service.CALL_TIMEOUT_MINUTES} 分钟内），不能重复取号",
            )
    ticket = QueueTicket(
        vat_id=payload.vat_id,
        taken_at=queue_service.now(),
        taken_by=current.display_name,
    )
    db.add(ticket)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="该染缸已有未作废且未完成的排队号，不能重复取号")
    db.refresh(ticket)
    return queue_service.serialize_ticket(ticket)


@router.post("/{ticket_id}/call", response_model=QueueTicketOut)
def call_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_supervisor),
):
    """主管叫号：仅等待中的号可叫；叫号后起算开立时限。"""
    ticket = db.query(QueueTicket).filter(QueueTicket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=404, detail="排队号不存在")
    if ticket.completed_at is not None:
        raise HTTPException(status_code=409, detail="该排队号已完成，不能再叫号")
    if ticket.voided_at is not None:
        raise HTTPException(status_code=409, detail="该排队号已作废，不能再叫号")
    if ticket.called_at is not None:
        if queue_service.expire_ticket(db, ticket):
            db.commit()
            raise HTTPException(
                status_code=409,
                detail=f"该号叫号已超过 {queue_service.CALL_TIMEOUT_MINUTES} 分钟时限，自动作废",
            )
        raise HTTPException(status_code=409, detail="该排队号已叫号，请勿重复叫号")
    ticket.called_at = queue_service.now()
    db.commit()
    db.refresh(ticket)
    return queue_service.serialize_ticket(ticket)
