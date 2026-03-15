from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List
from uuid import UUID, uuid4
import json
import asyncio
from datetime import datetime, timezone

from app.database import get_db
from app.models.simulation import Simulation
from app.models.topology import Topology
from app.models.lab import Lab
from app.schemas.simulation import SimulationCreate, SimulationResponse
from app.services.simulation_engine import SimulationEngine
from app.services.topology_service import TopologyService

router = APIRouter(prefix="/simulations", tags=["simulations"])

engine = SimulationEngine()


@router.post("", response_model=SimulationResponse, status_code=201)
async def run_simulation(payload: SimulationCreate, db: AsyncSession = Depends(get_db)):
    simulation = Simulation(
        id=uuid4(),
        topology_id=payload.topology_id,
        lab_id=payload.lab_id,
        status="running",
        configuration=payload.configuration,
        started_at=datetime.now(timezone.utc),
    )
    db.add(simulation)
    await db.commit()
    await db.refresh(simulation)

    try:
        topology_svc = TopologyService(db)
        topology = await topology_svc.get_topology_with_details(payload.topology_id)
        if not topology:
            raise ValueError(f"Topology '{payload.topology_id}' not found")

        lab_result = await db.execute(select(Lab).where(Lab.id == payload.lab_id))
        lab = lab_result.scalar_one_or_none()
        if not lab:
            raise ValueError(f"Lab '{payload.lab_id}' not found")

        topology_data = await topology_svc.topology_to_dict(topology)
        results = engine.run_simulation(lab, topology_data, payload.configuration)

        simulation.status = "completed"
        simulation.results = results
    except Exception as exc:
        simulation.status = "failed"
        simulation.results = {"errors": [str(exc)], "success": False}

    simulation.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(simulation)
    return simulation


@router.get("/{simulation_id}", response_model=SimulationResponse)
async def get_simulation(simulation_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Simulation).where(Simulation.id == simulation_id))
    simulation = result.scalar_one_or_none()
    if not simulation:
        raise HTTPException(status_code=404, detail=f"Simulation '{simulation_id}' not found")
    return simulation


@router.websocket("/{simulation_id}/ws")
async def simulation_websocket(simulation_id: UUID, websocket: WebSocket):
    await websocket.accept()
    try:
        from app.database import get_db as _get_db
        async for db in _get_db():
            result = await db.execute(
                select(Simulation).where(Simulation.id == simulation_id)
            )
            simulation = result.scalar_one_or_none()
            if simulation:
                await websocket.send_text(
                    json.dumps({
                        "id": str(simulation.id),
                        "status": simulation.status,
                        "results": simulation.results,
                        "started_at": simulation.started_at.isoformat() if simulation.started_at else None,
                        "completed_at": simulation.completed_at.isoformat() if simulation.completed_at else None,
                    })
                )
            else:
                await websocket.send_text(
                    json.dumps({"error": f"Simulation '{simulation_id}' not found"})
                )
            break

        while True:
            await asyncio.sleep(30)
            await websocket.send_text(json.dumps({"type": "ping"}))
    except WebSocketDisconnect:
        pass
