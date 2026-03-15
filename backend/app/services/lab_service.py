import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.lab import Lab

logger = logging.getLogger(__name__)


class LabService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_all_labs(self) -> list[Lab]:
        result = await self.db.execute(
            select(Lab).where(Lab.is_active).order_by(Lab.sort_order)
        )
        return list(result.scalars().all())

    async def get_lab_by_slug(self, slug: str) -> Lab | None:
        result = await self.db.execute(
            select(Lab).where(Lab.slug == slug, Lab.is_active)
        )
        return result.scalar_one_or_none()

    async def get_lab_by_id(self, lab_id) -> Lab | None:
        result = await self.db.execute(
            select(Lab).where(Lab.id == lab_id, Lab.is_active)
        )
        return result.scalar_one_or_none()
