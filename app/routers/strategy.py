from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import get_db
from app.services.pit_window import calculate_pit_window
from app.services.elo_engine import compute_constructor_elo
from app.services.wet_weather import calculate_wet_weather_scores
from app.services.tyre_model import calculate_tyre_degradation

router = APIRouter()

@router.get("/pit-window/{race_id}/{driver_id}")
async def get_pit_window(
    race_id: int,
    driver_id: int,
    db: AsyncSession = Depends(get_db)
):
    """
    Calculate optimal pit window for a driver in a specific race.
    Uses tyre compound degradation models and historical pit stop data
    from this circuit to recommend optimal pit laps and undercut windows.
    """
    result = await calculate_pit_window(db, race_id, driver_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/constructor-elo")
async def get_constructor_elo(db: AsyncSession = Depends(get_db)):
    """
    Compute Elo ratings for all F1 constructors based on historical
    race results. Uses a round-robin pairwise comparison model with
    K-factor of 32. All constructors initialised at 1500.
    """
    return await compute_constructor_elo(db)

@router.get("/wet-weather-scores")
async def get_wet_weather_scores(db: AsyncSession = Depends(get_db)):
    """
    Score all drivers on wet weather performance using position delta
    analysis across historically wet races. Cross-referenced with
    OpenF1 rainfall data where available.
    """
    return await calculate_wet_weather_scores(db)

@router.get("/tyre-model/{circuit_id}/{compound}")
async def get_tyre_model(
    circuit_id: int,
    compound: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Returns quadratic regression model for tyre degradation at a
    specific circuit for a given compound. Used internally by the
    pit window calculator.
    """
    result = await calculate_tyre_degradation(db, circuit_id, compound)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result