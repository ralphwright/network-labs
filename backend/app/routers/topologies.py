from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel

from app.database import get_db
from app.models.topology import Topology
from app.models.device import Device
from app.models.connection import Connection
from app.schemas.topology import TopologyCreate, TopologyUpdate, TopologyResponse
from app.schemas.device import DeviceCreate
from app.schemas.connection import ConnectionCreate

router = APIRouter(prefix="/topologies", tags=["topologies"])


class TopologyCreateWithData(TopologyCreate):
    initial_topology: Optional[dict] = None


async def _load_topology(topology_id: UUID, db: AsyncSession) -> Topology:
    result = await db.execute(
        select(Topology)
        .where(Topology.id == topology_id)
        .options(
            selectinload(Topology.devices),
            selectinload(Topology.connections),
        )
    )
    topology = result.scalar_one_or_none()
    if not topology:
        raise HTTPException(status_code=404, detail=f"Topology '{topology_id}' not found")
    return topology


@router.get("", response_model=List[TopologyResponse])
async def get_topologies(
    lab_id: Optional[UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Topology).options(
        selectinload(Topology.devices),
        selectinload(Topology.connections),
    )
    if lab_id is not None:
        stmt = stmt.where(Topology.lab_id == lab_id)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("", response_model=TopologyResponse, status_code=status.HTTP_201_CREATED)
async def create_topology(
    payload: TopologyCreateWithData,
    db: AsyncSession = Depends(get_db),
):
    topology = Topology(
        id=uuid4(),
        lab_id=payload.lab_id,
        user_id=payload.user_id,
        name=payload.name,
        description=payload.description,
        is_template=payload.is_template,
    )
    db.add(topology)
    await db.flush()

    if payload.initial_topology:
        for d in payload.initial_topology.get("devices", []):
            device = Device(
                id=uuid4(),
                topology_id=topology.id,
                device_type=d.get("type", d.get("device_type", "router")),
                label=d.get("label", ""),
                x=d.get("x", 0.0),
                y=d.get("y", 0.0),
                configuration=d.get("configuration", {}),
            )
            db.add(device)

        await db.flush()

        # Build a label->id map for resolving connection references
        dev_result = await db.execute(
            select(Device).where(Device.topology_id == topology.id)
        )
        devices_by_label = {dev.label: dev.id for dev in dev_result.scalars().all()}

        for c in payload.initial_topology.get("connections", []):
            source_id = c.get("source_device_id") or devices_by_label.get(c.get("source"))
            target_id = c.get("target_device_id") or devices_by_label.get(c.get("target"))
            if source_id and target_id:
                connection = Connection(
                    id=uuid4(),
                    topology_id=topology.id,
                    source_device_id=source_id,
                    target_device_id=target_id,
                    source_interface=c.get("source_interface", "eth0"),
                    target_interface=c.get("target_interface", "eth0"),
                    link_type=c.get("link_type", "ethernet"),
                    bandwidth_mbps=c.get("bandwidth_mbps", 1000),
                    configuration=c.get("configuration", {}),
                )
                db.add(connection)

    await db.commit()
    return await _load_topology(topology.id, db)


@router.get("/{topology_id}", response_model=TopologyResponse)
async def get_topology(topology_id: UUID, db: AsyncSession = Depends(get_db)):
    return await _load_topology(topology_id, db)


@router.put("/{topology_id}", response_model=TopologyResponse)
async def update_topology(
    topology_id: UUID,
    payload: TopologyUpdate,
    db: AsyncSession = Depends(get_db),
):
    topology = await _load_topology(topology_id, db)
    if payload.name is not None:
        topology.name = payload.name
    if payload.description is not None:
        topology.description = payload.description
    if payload.is_template is not None:
        topology.is_template = payload.is_template
    await db.commit()
    return await _load_topology(topology_id, db)


@router.delete("/{topology_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_topology(topology_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Topology).where(Topology.id == topology_id))
    topology = result.scalar_one_or_none()
    if not topology:
        raise HTTPException(status_code=404, detail=f"Topology '{topology_id}' not found")
    await db.delete(topology)
    await db.commit()
