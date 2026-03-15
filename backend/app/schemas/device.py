import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class DeviceBase(BaseModel):
    device_type: str
    label: str
    x: float = 0.0
    y: float = 0.0
    configuration: dict = {}


class DeviceCreate(DeviceBase):
    topology_id: uuid.UUID


class DeviceUpdate(BaseModel):
    device_type: str | None = None
    label: str | None = None
    x: float | None = None
    y: float | None = None
    configuration: dict | None = None


class DeviceResponse(DeviceBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topology_id: uuid.UUID
    created_at: datetime
