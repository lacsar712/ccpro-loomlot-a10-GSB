from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# 排队号状态：等待叫号 / 已叫号 / 已作废 / 已完成（开立染程）
TicketState = Literal["waiting", "called", "voided", "completed"]


class QueueTicketCreate(BaseModel):
    vat_id: int = Field(..., alias="vatId")

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
    state: TicketState
    deadline_at: Optional[datetime] = Field(None, serialization_alias="deadlineAt")
    expired: bool
