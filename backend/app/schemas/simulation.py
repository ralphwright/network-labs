import uuid
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict

SimulationStatus = Literal["pending", "running", "completed", "failed"]


class ObjectiveResult(BaseModel):
    objective_id: str
    description: str
    passed: bool
    message: str


class SimulationCreate(BaseModel):
    topology_id: uuid.UUID
    lab_id: uuid.UUID
    configuration: dict = {}


class SimulationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    topology_id: uuid.UUID
    lab_id: uuid.UUID
    user_id: uuid.UUID | None = None
    status: SimulationStatus
    configuration: dict | None = None
    results: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
