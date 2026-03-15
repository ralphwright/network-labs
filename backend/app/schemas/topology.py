import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict

from app.schemas.device import DeviceResponse
from app.schemas.connection import ConnectionResponse


class TopologyBase(BaseModel):
    name: str
    description: str | None = None
    is_template: bool = False


class TopologyCreate(TopologyBase):
    lab_id: uuid.UUID
    user_id: uuid.UUID | None = None


class TopologyUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    is_template: bool | None = None


class TopologyResponse(TopologyBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lab_id: uuid.UUID
    user_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime | None = None
    devices: list[DeviceResponse] = []
    connections: list[ConnectionResponse] = []
