import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ConnectionBase(BaseModel):
    source_device_id: uuid.UUID
    target_device_id: uuid.UUID
    source_interface: str = "eth0"
    target_interface: str = "eth0"
    link_type: str = "ethernet"
    bandwidth_mbps: int = 1000
    configuration: dict = {}


class ConnectionCreate(ConnectionBase):
    topology_id: uuid.UUID


class ConnectionUpdate(BaseModel):
    source_device_id: uuid.UUID | None = None
    target_device_id: uuid.UUID | None = None
    source_interface: str | None = None
    target_interface: str | None = None
    link_type: str | None = None
    bandwidth_mbps: int | None = None
    configuration: dict | None = None


class ConnectionResponse(ConnectionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topology_id: uuid.UUID
    created_at: datetime
