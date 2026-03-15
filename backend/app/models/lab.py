import uuid
from sqlalchemy import Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Lab(Base):
    __tablename__ = "labs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    difficulty: Mapped[str] = mapped_column(String(20), nullable=False)
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    objectives: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    theory_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    initial_topology: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    verification_rules: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    prerequisites: Mapped[dict | list | None] = mapped_column(JSONB, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    topologies: Mapped[list["Topology"]] = relationship(
        "Topology", back_populates="lab"
    )
    progress_records: Mapped[list["Progress"]] = relationship(
        "Progress", back_populates="lab"
    )
