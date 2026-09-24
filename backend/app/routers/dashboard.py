from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import get_current_user
from app.database import get_db
from app.models.dye_house import DyeHouse
from app.models.dye_lot import DyeLot
from app.models.fastness_check import FastnessCheck
from app.models.queue_ticket import QueueTicket
from app.models.user import User
from app.models.vat import Vat
from app import queue_service
from app.schemas.dashboard import DashboardStats

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
def get_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_user),
):
    now = datetime.now(timezone.utc)
    # 先把叫号超时的号统一作废，保证看板计数与排队列表等待行一致。
    expired = queue_service.expire_all_due(db, now)
    if expired:
        db.commit()
    return DashboardStats(
        dye_house_total=db.query(func.count(DyeHouse.id)).scalar() or 0,
        vat_ready_count=db.query(func.count(Vat.id)).filter(Vat.status == "ready").scalar() or 0,
        vat_dyeing_count=db.query(func.count(Vat.id)).filter(Vat.status == "dyeing").scalar() or 0,
        lots_last_7d=(
            db.query(func.count(DyeLot.id))
            .filter(DyeLot.started_at >= now - timedelta(days=7))
            .scalar()
            or 0
        ),
        checks_last_24h=(
            db.query(func.count(FastnessCheck.id))
            .filter(FastnessCheck.checked_at >= now - timedelta(hours=24))
            .scalar()
            or 0
        ),
        # 等待叫号：已取号、未叫号、未作废且未完成（与排队列表 waiting 行同一口径）。
        queue_waiting_count=(
            db.query(func.count(QueueTicket.id))
            .filter(
                QueueTicket.called_at.is_(None),
                QueueTicket.voided_at.is_(None),
                QueueTicket.completed_at.is_(None),
            )
            .scalar()
            or 0
        ),
    )
