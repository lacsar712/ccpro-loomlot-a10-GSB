from datetime import datetime
from typing import List, Optional, TYPE_CHECKING

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.vat import Vat
    from app.models.fastness_check import FastnessCheck
    from app.models.queue_ticket import QueueTicket


class DyeLot(Base):
    __tablename__ = "dye_lots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vat_id: Mapped[int] = mapped_column(ForeignKey("vats.id"), nullable=False, index=True)
    queue_ticket_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("queue_tickets.id", ondelete="SET NULL"), nullable=True, unique=True
    )
    recipe_name: Mapped[str] = mapped_column(String(128), nullable=False)
    fabric_kg: Mapped[float] = mapped_column(Float, nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    operator_name: Mapped[str] = mapped_column(String(64), nullable=False)

    vat: Mapped["Vat"] = relationship("Vat", back_populates="dye_lots")
    ticket: Mapped[Optional["QueueTicket"]] = relationship("QueueTicket", back_populates="dye_lot")
    fastness_checks: Mapped[List["FastnessCheck"]] = relationship(
        "FastnessCheck", back_populates="dye_lot", cascade="all, delete-orphan"
    )
