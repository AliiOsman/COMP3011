from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.models.driver import Driver
from app.schemas.driver import DriverCreate, DriverUpdate
from typing import Optional

class DriverRepository:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, data: DriverCreate) -> Driver:
        driver = Driver(**data.model_dump())
        self.db.add(driver)
        await self.db.commit()
        await self.db.refresh(driver)
        return driver

    async def get_by_id(self, driver_id: int) -> Optional[Driver]:
        result = await self.db.execute(select(Driver).where(Driver.id == driver_id))
        return result.scalar_one_or_none()

    async def get_all(self, skip: int = 0, limit: int = 100) -> list[Driver]:
        result = await self.db.execute(select(Driver).offset(skip).limit(limit))
        return result.scalars().all()

    async def update(self, driver_id: int, data: DriverUpdate) -> Optional[Driver]:
        values = {k: v for k, v in data.model_dump().items() if v is not None}
        if not values:
            return await self.get_by_id(driver_id)
        await self.db.execute(update(Driver).where(Driver.id == driver_id).values(**values))
        await self.db.commit()
        return await self.get_by_id(driver_id)

    async def delete(self, driver_id: int) -> bool:
        result = await self.db.execute(delete(Driver).where(Driver.id == driver_id))
        await self.db.commit()
        return result.rowcount > 0

    async def search_by_nationality(self, nationality: str) -> list[Driver]:
        result = await self.db.execute(
            select(Driver).where(Driver.nationality.ilike(f"%{nationality}%"))
        )
        return result.scalars().all()