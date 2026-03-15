import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class ProgressBase(BaseModel):
    lab_id: uuid.UUID
    status: str = "not_started"
    score: int | None = None
    attempts: int = 0


class ProgressCreate(ProgressBase):
    user_id: uuid.UUID


class ProgressUpdate(BaseModel):
    status: str | None = None
    score: int | None = None
    attempts: int | None = None
    completed_at: datetime | None = None


class ProgressResponse(ProgressBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    last_simulation_id: uuid.UUID | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None
