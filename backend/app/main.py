import asyncio
import logging
import os
import subprocess
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Dict, List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


class ConnectionManager:
    """Manages active WebSocket connections keyed by simulation ID."""

    def __init__(self) -> None:
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, simulation_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.setdefault(simulation_id, []).append(websocket)

    def disconnect(self, simulation_id: str, websocket: WebSocket) -> None:
        connections = self.active_connections.get(simulation_id, [])
        if websocket in connections:
            connections.remove(websocket)
        if not connections:
            self.active_connections.pop(simulation_id, None)

    async def broadcast(self, simulation_id: str, message: str) -> None:
        for connection in list(self.active_connections.get(simulation_id, [])):
            try:
                await connection.send_text(message)
            except Exception:
                self.disconnect(simulation_id, connection)


manager = ConnectionManager()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Network Labs API…")

    # Run alembic migrations
    # Resolve the project root (directory containing alembic.ini) relative to
    # this file so the path works both inside and outside the container.
    project_root = Path(__file__).resolve().parent.parent
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd=str(project_root),
        )
        if result.returncode == 0:
            logger.info("Database migrations applied successfully.")
        else:
            logger.warning("Alembic migration warning: %s", result.stderr)
    except Exception as exc:
        logger.warning("Could not run database migrations: %s", exc)

    # Seed lab data
    try:
        from app.database import get_db
        from app.seed.lab_data import seed_labs

        async for db in get_db():
            await seed_labs(db)
            break
    except Exception as exc:
        logger.warning("Could not seed lab data: %s", exc)

    yield

    logger.info("Shutting down Network Labs API.")


app = FastAPI(title="Network Labs API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------
try:
    from app.routers.labs import router as labs_router
    from app.routers.topologies import router as topologies_router
    from app.routers.devices import router as devices_router
    from app.routers.connections import router as connections_router
    from app.routers.simulations import router as simulations_router
    from app.routers.progress import router as progress_router

    app.include_router(labs_router, prefix="/api")
    app.include_router(topologies_router, prefix="/api")
    app.include_router(devices_router, prefix="/api")
    app.include_router(connections_router, prefix="/api")
    app.include_router(simulations_router, prefix="/api")
    app.include_router(progress_router, prefix="/api")
except ImportError as exc:
    logger.warning("One or more routers could not be loaded: %s", exc)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/health")
async def health_check():
    return {"status": "healthy", "version": "1.0.0"}


@app.websocket("/ws/simulation/{simulation_id}")
async def websocket_endpoint(websocket: WebSocket, simulation_id: str):
    await manager.connect(simulation_id, websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await manager.broadcast(simulation_id, data)
    except WebSocketDisconnect:
        manager.disconnect(simulation_id, websocket)
        logger.info("WebSocket disconnected for simulation %s", simulation_id)
