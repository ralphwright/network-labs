from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID, uuid4

from app.database import get_db
from app.models.progress import Progress
from app.schemas.progress import ProgressCreate, ProgressUpdate, ProgressResponse

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=List[ProgressResponse])
async def get_progress_records(
    user_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Progress).where(Progress.user_id == user_id))
    return result.scalars().all()


@router.get("/{lab_id}", response_model=ProgressResponse)
async def get_progress_for_lab(
    lab_id: UUID,
    user_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Progress).where(Progress.user_id == user_id, Progress.lab_id == lab_id)
    )
    progress = result.scalar_one_or_none()
    if not progress:
        raise HTTPException(
            status_code=404,
            detail=f"Progress record not found for lab '{lab_id}' and user '{user_id}'",
        )
    return progress


@router.post("", response_model=ProgressResponse, status_code=status.HTTP_201_CREATED)
async def create_progress(payload: ProgressCreate, db: AsyncSession = Depends(get_db)):
    progress = Progress(
        id=uuid4(),
        user_id=payload.user_id,
        lab_id=payload.lab_id,
        status=payload.status,
        score=payload.score,
        attempts=payload.attempts,
    )
    db.add(progress)
    await db.commit()
    await db.refresh(progress)
    return progress


@router.put("/{lab_id}", response_model=ProgressResponse)
async def update_progress(
    lab_id: UUID,
    payload: ProgressUpdate,
    user_id: UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Progress).where(Progress.user_id == user_id, Progress.lab_id == lab_id)
    )
    progress = result.scalar_one_or_none()
    if not progress:
        raise HTTPException(
            status_code=404,
            detail=f"Progress record not found for lab '{lab_id}' and user '{user_id}'",
        )
    if payload.status is not None:
        progress.status = payload.status
    if payload.score is not None:
        progress.score = payload.score
    if payload.attempts is not None:
        progress.attempts = payload.attempts
    if payload.completed_at is not None:
        progress.completed_at = payload.completed_at
    await db.commit()
    await db.refresh(progress)
    return progress
