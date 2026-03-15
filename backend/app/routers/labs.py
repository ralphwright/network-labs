from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from uuid import UUID
from app.database import get_db
from app.models.lab import Lab
from app.schemas.lab import LabResponse, LabSummary

router = APIRouter(prefix="/labs", tags=["labs"])


@router.get("", response_model=List[LabSummary])
async def get_labs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lab).where(Lab.is_active).order_by(Lab.sort_order))
    labs = result.scalars().all()
    return labs


@router.get("/{slug}", response_model=LabResponse)
async def get_lab_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lab).where(Lab.slug == slug, Lab.is_active))
    lab = result.scalar_one_or_none()
    if not lab:
        raise HTTPException(status_code=404, detail=f"Lab '{slug}' not found")
    return lab


@router.get("/id/{lab_id}", response_model=LabResponse)
async def get_lab_by_id(lab_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Lab).where(Lab.id == lab_id, Lab.is_active))
    lab = result.scalar_one_or_none()
    if not lab:
        raise HTTPException(status_code=404, detail=f"Lab '{lab_id}' not found")
    return lab
