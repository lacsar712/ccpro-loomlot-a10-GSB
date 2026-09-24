from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class QueueTicketCreate(BaseModel):
    vat_id: int = Field(..., alias="vatId")
    taken_by: str = Field(..., min_length=1, max_length=64, alias="takenBy")

    model_config = ConfigDict(populate_by_name=True)


class QueueTicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    vat_id: int = Field(serialization_alias="vatId")
    taken_at: datetime = Field(serialization_alias="takenAt")
    called_at: Optional[datetime] = Field(None, serialization_alias="calledAt")
    voided_at: Optional[datetime] = Field(None, serialization_alias="voidedAt")
    completed_at: Optional[datetime] = Field(None, serialization_alias="completedAt")
    taken_by: str = Field(serialization_alias="takenBy")
    dye_lot_id: Optional[int] = Field(None, serialization_alias="dyeLotId")

    # 由路由层计算的派生展示字段
    status: str = ""
    expires_at: Optional[datetime] = Field(None, serialization_alias="expiresAt")


class QueueTicketListItem(QueueTicketOut):
    """排队列表项，附带染缸/染坊冗余信息便于前端展示。"""

    vat_code: str = Field(default="", serialization_alias="vatCode")
    house_name: Optional[str] = Field(None, serialization_alias="houseName")
