from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Integer, DateTime, ForeignKey, Index, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.vat import Vat
    from app.models.dye_lot import DyeLot


class QueueTicket(Base):
    """染缸叫号排队号。

    生命周期：taken（已取号，等待叫号）→ called（已叫号，等待开染程）
    → completed（已挂到染程）或 voided（作废，含叫号超时自动作废）。
    同一染缸同时只允许一个「未作废且未完成」的号。
    """

    __tablename__ = "queue_tickets"
    __table_args__ = (
        # 数据库层兜底：同一染缸未作废且未完成的号同时最多一个
        Index(
            "uq_active_ticket_per_vat",
            "vat_id",
            unique=True,
            postgresql_where=text("voided_at IS NULL AND completed_at IS NULL"),
            sqlite_where=text("voided_at IS NULL AND completed_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vat_id: Mapped[int] = mapped_column(ForeignKey("vats.id"), nullable=False, index=True)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    taken_by: Mapped[str] = mapped_column(String(64), nullable=False)
    dye_lot_id: Mapped[int | None] = mapped_column(ForeignKey("dye_lots.id"), nullable=True)

    vat: Mapped["Vat"] = relationship("Vat", back_populates="queue_tickets")
    dye_lot: Mapped["DyeLot | None"] = relationship("DyeLot", foreign_keys=[dye_lot_id])
