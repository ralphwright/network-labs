import uuid
from datetime import datetime
from pydantic import BaseModel, ConfigDict


class LabBase(BaseModel):
    slug: str
    title: str
    description: str
    category: str
    difficulty: str
    estimated_minutes: int
    objectives: list[str]
    theory_content: str | None = None
    instructions: list[dict] | None = None
    initial_topology: dict | None = None
    verification_rules: dict | None = None
    prerequisites: list[str]
    sort_order: int


class LabCreate(LabBase):
    pass


class LabUpdate(BaseModel):
    slug: str | None = None
    title: str | None = None
    description: str | None = None
    category: str | None = None
    difficulty: str | None = None
    estimated_minutes: int | None = None
    objectives: list[str] | None = None
    theory_content: str | None = None
    instructions: list[dict] | None = None
    initial_topology: dict | None = None
    verification_rules: dict | None = None
    prerequisites: list[str] | None = None
    sort_order: int | None = None


class LabResponse(LabBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None


class LabSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    title: str
    description: str
    category: str
    difficulty: str
    estimated_minutes: int
    sort_order: int
    prerequisites: list[str]
    objectives: list[str]
