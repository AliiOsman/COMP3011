from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.race import Race
from app.models.circuit import Circuit
from app.middleware.auth import get_current_user, require_admin
from pydantic import BaseModel
from typing import Optional, List

router = APIRouter()

class RaceResponse(BaseModel):
    id: int
    ergast_id: int
    season: int
    round: int
    name: str
    date: Optional[str]
    circuit_id: int

    model_config = {"from_attributes": True}

class RaceCreate(BaseModel):
    ergast_id: int
    season: int
    round: int
    name: str
    date: Optional[str] = None
    circuit_id: int

class RaceUpdate(BaseModel):
    name: Optional[str] = None
    date: Optional[str] = None
    round: Optional[int] = None

@router.get("/", response_model=List[RaceResponse])
async def get_races(
    season: Optional[int] = Query(None),
    circuit_id: Optional[int] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, le=200),
    db: AsyncSession = Depends(get_db)
):
    query = select(Race)
    if season:
        query = query.where(Race.season == season)
    if circuit_id:
        query = query.where(Race.circuit_id == circuit_id)
    query = query.order_by(Race.season, Race.round).offset(skip).limit(limit)
    result = await db.execute(query)
    return result.scalars().all()

@router.get("/{race_id}", response_model=RaceResponse)
async def get_race(race_id: int, db: AsyncSession = Depends(get_db)):
    race = await db.get(Race, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    return race

@router.post("/", response_model=RaceResponse, status_code=201)
async def create_race(
    data: RaceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    race = Race(**data.model_dump())
    db.add(race)
    await db.commit()
    await db.refresh(race)
    return race

@router.put("/{race_id}", response_model=RaceResponse)
async def update_race(
    race_id: int,
    data: RaceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    race = await db.get(Race, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(race, field, value)
    await db.commit()
    await db.refresh(race)
    return race

@router.delete("/{race_id}", status_code=204)
async def delete_race(
    race_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    race = await db.get(Race, race_id)
    if not race:
        raise HTTPException(status_code=404, detail="Race not found")
    await db.delete(race)
    await db.commit()