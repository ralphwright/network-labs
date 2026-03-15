from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID, uuid4

from app.database import get_db
from app.models.connection import Connection
from app.schemas.connection import ConnectionCreate, ConnectionUpdate, ConnectionResponse

router = APIRouter(prefix="/connections", tags=["connections"])


@router.get("", response_model=List[ConnectionResponse])
async def get_connections(
    topology_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Connection).where(Connection.topology_id == topology_id)
    )
    return result.scalars().all()


@router.post("", response_model=ConnectionResponse, status_code=status.HTTP_201_CREATED)
async def create_connection(payload: ConnectionCreate, db: AsyncSession = Depends(get_db)):
    connection = Connection(
        id=uuid4(),
        topology_id=payload.topology_id,
        source_device_id=payload.source_device_id,
        target_device_id=payload.target_device_id,
        source_interface=payload.source_interface,
        target_interface=payload.target_interface,
        link_type=payload.link_type,
        bandwidth_mbps=payload.bandwidth_mbps,
        configuration=payload.configuration,
    )
    db.add(connection)
    await db.commit()
    await db.refresh(connection)
    return connection


@router.get("/{connection_id}", response_model=ConnectionResponse)
async def get_connection(connection_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Connection).where(Connection.id == connection_id))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail=f"Connection '{connection_id}' not found")
    return connection


@router.put("/{connection_id}", response_model=ConnectionResponse)
async def update_connection(
    connection_id: UUID,
    payload: ConnectionUpdate,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Connection).where(Connection.id == connection_id))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail=f"Connection '{connection_id}' not found")
    if payload.source_device_id is not None:
        connection.source_device_id = payload.source_device_id
    if payload.target_device_id is not None:
        connection.target_device_id = payload.target_device_id
    if payload.source_interface is not None:
        connection.source_interface = payload.source_interface
    if payload.target_interface is not None:
        connection.target_interface = payload.target_interface
    if payload.link_type is not None:
        connection.link_type = payload.link_type
    if payload.bandwidth_mbps is not None:
        connection.bandwidth_mbps = payload.bandwidth_mbps
    if payload.configuration is not None:
        connection.configuration = payload.configuration
    await db.commit()
    await db.refresh(connection)
    return connection


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_connection(connection_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Connection).where(Connection.id == connection_id))
    connection = result.scalar_one_or_none()
    if not connection:
        raise HTTPException(status_code=404, detail=f"Connection '{connection_id}' not found")
    await db.delete(connection)
    await db.commit()
