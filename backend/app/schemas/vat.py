from datetime import datetime
from typing import Optional, Literal

from pydantic import BaseModel, ConfigDict, Field

VatStatus = Literal["ready", "dyeing", "drain"]


class CurrentTicketBrief(BaseModel):
    """染缸列表里展示的当前排队号简要状态。"""

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    taken_at: datetime = Field(serialization_alias="takenAt")
    called_at: Optional[datetime] = Field(None, serialization_alias="calledAt")
    status: Literal["taken", "called"]
    expires_at: Optional[datetime] = Field(None, serialization_alias="expiresAt")


class VatCreate(BaseModel):
    dye_house_id: int = Field(..., alias="dyeHouseId")
    vat_code: str = Field(..., min_length=1, max_length=64, alias="vatCode")
    fiber_type: str = Field(..., min_length=1, max_length=64, alias="fiberType")
    capacity_l: float = Field(..., gt=0, alias="capacityL")
    status: VatStatus = "ready"

    model_config = ConfigDict(populate_by_name=True)


class VatUpdate(BaseModel):
    dye_house_id: Optional[int] = Field(None, alias="dyeHouseId")
    vat_code: Optional[str] = Field(None, min_length=1, max_length=64, alias="vatCode")
    fiber_type: Optional[str] = Field(None, min_length=1, max_length=64, alias="fiberType")
    capacity_l: Optional[float] = Field(None, gt=0, alias="capacityL")
    status: Optional[VatStatus] = None

    model_config = ConfigDict(populate_by_name=True)


class VatOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)

    id: int
    dye_house_id: int = Field(serialization_alias="dyeHouseId")
    vat_code: str = Field(serialization_alias="vatCode")
    fiber_type: str = Field(serialization_alias="fiberType")
    capacity_l: float = Field(serialization_alias="capacityL")
    status: VatStatus
    current_ticket: Optional[CurrentTicketBrief] = Field(None, serialization_alias="currentTicket")
