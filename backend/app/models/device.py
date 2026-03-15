import uuid
from sqlalchemy import DateTime, Float, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topology_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    device_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    x: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    y: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    configuration: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    topology: Mapped["Topology"] = relationship("Topology", back_populates="devices")
    source_connections: Mapped[list["Connection"]] = relationship(
        "Connection",
        back_populates="source_device",
        foreign_keys="Connection.source_device_id",
    )
    target_connections: Mapped[list["Connection"]] = relationship(
        "Connection",
        back_populates="target_device",
        foreign_keys="Connection.target_device_id",
    )
