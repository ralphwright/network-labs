import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from uuid import UUID
from app.models.topology import Topology
from app.models.device import Device
from app.models.connection import Connection

logger = logging.getLogger(__name__)


class TopologyService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_topology_with_details(self, topology_id: UUID) -> Topology | None:
        result = await self.db.execute(
            select(Topology)
            .where(Topology.id == topology_id)
            .options(
                selectinload(Topology.devices),
                selectinload(Topology.connections),
            )
        )
        return result.scalar_one_or_none()

    async def topology_to_dict(self, topology: Topology) -> dict:
        devices = []
        for d in topology.devices:
            devices.append({
                "id": str(d.id),
                "type": d.device_type,
                "label": d.label,
                "x": d.x,
                "y": d.y,
                "configuration": d.configuration or {},
            })
        connections = []
        for c in topology.connections:
            connections.append({
                "id": str(c.id),
                "source": str(c.source_device_id),
                "target": str(c.target_device_id),
                "source_interface": c.source_interface,
                "target_interface": c.target_interface,
                "link_type": c.link_type,
                "bandwidth_mbps": c.bandwidth_mbps,
            })
        return {"devices": devices, "connections": connections}
