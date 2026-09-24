from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.vat import Vat
    from app.models.dye_lot import DyeLot


class QueueTicket(Base):
    """染缸叫号排队号。

    生命周期：取号(waiting) → 叫号(called) → 开出染程(completed)；
    叫号后规定时限内未开出染程则作废(voided)。
    同一染缸同时至多存在一个「未作废且未完成」的号（部分唯一索引兜底）。
    """

    __tablename__ = "queue_tickets"
    __table_args__ = (
        Index(
            "uq_vat_active_ticket",
            "vat_id",
            unique=True,
            postgresql_where=text("voided_at IS NULL AND completed_at IS NULL"),
            sqlite_where=text("voided_at IS NULL AND completed_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vat_id: Mapped[int] = mapped_column(ForeignKey("vats.id"), nullable=False, index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    called_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    taken_by: Mapped[str] = mapped_column(String(64), nullable=False)

    vat: Mapped["Vat"] = relationship("Vat", back_populates="queue_tickets")
    dye_lot: Mapped[Optional["DyeLot"]] = relationship("DyeLot", back_populates="ticket")
