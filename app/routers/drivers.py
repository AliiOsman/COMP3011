from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.repositories.driver_repo import DriverRepository
from app.schemas.driver import DriverCreate, DriverUpdate, DriverResponse
from typing import List

router = APIRouter()

@router.post("/", response_model=DriverResponse, status_code=201)
async def create_driver(data: DriverCreate, db: AsyncSession = Depends(get_db)):
    repo = DriverRepository(db)
    return await repo.create(data)

@router.get("/", response_model=List[DriverResponse])
async def get_all_drivers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db)
):
    repo = DriverRepository(db)
    return await repo.get_all(skip=skip, limit=limit)

@router.get("/search", response_model=List[DriverResponse])
async def search_drivers_by_nationality(
    nationality: str = Query(..., min_length=2),
    db: AsyncSession = Depends(get_db)
):
    repo = DriverRepository(db)
    return await repo.search_by_nationality(nationality)

@router.get("/{driver_id}", response_model=DriverResponse)
async def get_driver(driver_id: int, db: AsyncSession = Depends(get_db)):
    repo = DriverRepository(db)
    driver = await repo.get_by_id(driver_id)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver

@router.put("/{driver_id}", response_model=DriverResponse)
async def update_driver(driver_id: int, data: DriverUpdate, db: AsyncSession = Depends(get_db)):
    repo = DriverRepository(db)
    driver = await repo.update(driver_id, data)
    if not driver:
        raise HTTPException(status_code=404, detail="Driver not found")
    return driver

@router.delete("/{driver_id}", status_code=204)
async def delete_driver(driver_id: int, db: AsyncSession = Depends(get_db)):
    repo = DriverRepository(db)
    deleted = await repo.delete(driver_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Driver not found")