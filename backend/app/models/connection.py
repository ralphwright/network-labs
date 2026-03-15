import uuid
from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    topology_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topologies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    target_device_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("devices.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_interface: Mapped[str] = mapped_column(String(50), nullable=False, default="eth0")
    target_interface: Mapped[str] = mapped_column(String(50), nullable=False, default="eth0")
    link_type: Mapped[str] = mapped_column(String(20), nullable=False, default="ethernet")
    bandwidth_mbps: Mapped[int | None] = mapped_column(Integer, default=1000, nullable=True)
    configuration: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    topology: Mapped["Topology"] = relationship("Topology", back_populates="connections")
    source_device: Mapped["Device"] = relationship(
        "Device",
        back_populates="source_connections",
        foreign_keys=[source_device_id],
    )
    target_device: Mapped["Device"] = relationship(
        "Device",
        back_populates="target_connections",
        foreign_keys=[target_device_id],
    )
