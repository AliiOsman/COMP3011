from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.pitstop import PitStop
from app.middleware.auth import get_current_user, require_admin
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()

class PitStopResponse(BaseModel):
    id: int
    race_id: int
    driver_id: int
    stop_number: int
    lap: int
    duration_seconds: Optional[float]
    tyre_compound: Optional[str]

    model_config = {"from_attributes": True}

class PitStopCreate(BaseModel):
    race_id: int
    driver_id: int
    stop_number: int
    lap: int
    duration_seconds: Optional[float] = None
    tyre_compound: Optional[str] = None

class PitStopUpdate(BaseModel):
    lap: Optional[int] = None
    duration_seconds: Optional[float] = None
    tyre_compound: Optional[str] = None

@router.get("/", response_model=List[PitStopResponse])
async def get_pitstops(
    race_id: Optional[int] = Query(None),
    driver_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, le=500),
    db: AsyncSession = Depends(get_db)
):
    query = select(PitStop)
    if race_id:
        query = query.where(PitStop.race_id == race_id)
    if driver_id:
        query = query.where(PitStop.driver_id == driver_id)
    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{pitstop_id}", response_model=PitStopResponse)
async def get_pitstop(pitstop_id: int, db: AsyncSession = Depends(get_db)):
    stop = await db.get(PitStop, pitstop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Pit stop not found")
    return stop

@router.post("/", response_model=PitStopResponse, status_code=201)
async def create_pitstop(
    data: PitStopCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    stop = PitStop(**data.model_dump())
    db.add(stop)
    await db.commit()
    await db.refresh(stop)
    return stop

@router.put("/{pitstop_id}", response_model=PitStopResponse)
async def update_pitstop(
    pitstop_id: int,
    data: PitStopUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    stop = await db.get(PitStop, pitstop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Pit stop not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(stop, field, value)
    await db.commit()
    await db.refresh(stop)
    return stop

@router.delete("/{pitstop_id}", status_code=204)
async def delete_pitstop(
    pitstop_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    stop = await db.get(PitStop, pitstop_id)
    if not stop:
        raise HTTPException(status_code=404, detail="Pit stop not found")
    await db.delete(stop)
    await db.commit()