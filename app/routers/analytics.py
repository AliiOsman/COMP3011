from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.database import get_db
from app.models.pitstop import PitStop
from app.models.result import Result
from app.models.constructor import Constructor
from app.models.circuit import Circuit
from app.models.race import Race
from app.services.tyre_model import calculate_tyre_degradation
from typing import Optional

router = APIRouter()

@router.get("/pit-crew-performance")
async def get_pit_crew_performance(
    season: Optional[int] = Query(None, description="Filter by season"),
    db: AsyncSession = Depends(get_db)
):
    """
    Ranks constructors by pit crew execution speed using statistical
    analysis. Computes mean, minimum, and consistency score (inverse
    of std deviation) across all pit stops.
    """
    query = (
        select(
            Constructor.name,
            Constructor.id,
            func.avg(PitStop.duration_seconds).label("avg_duration"),
            func.min(PitStop.duration_seconds).label("fastest_stop"),
            func.count(PitStop.id).label("total_stops"),
            func.stddev(PitStop.duration_seconds).label("std_deviation")
        )
        .join(Result, Result.constructor_id == Constructor.id)
        .join(PitStop, (PitStop.race_id == Result.race_id) &
              (PitStop.driver_id == Result.driver_id))
    )

    if season:
        query = query.join(Race, Race.id == PitStop.race_id).where(Race.season == season)

    query = (
        query
        .where(PitStop.duration_seconds != None)
        .where(PitStop.duration_seconds > 1)
        .where(PitStop.duration_seconds < 60)
        .group_by(Constructor.id, Constructor.name)
        .having(func.count(PitStop.id) >= 5)
        .order_by(func.avg(PitStop.duration_seconds))
    )

    result = await db.execute(query)
    rows = result.all()

    return {
        "season_filter": season,
        "methodology": (
            "Consistency score = 100 / (1 + std_deviation). "
            "Higher = more consistent pit stops."
        ),
        "rankings": [
            {
                "rank": i + 1,
                "constructor": row.name,
                "constructor_id": row.id,
                "avg_stop_seconds": round(float(row.avg_duration), 3),
                "fastest_stop_seconds": round(float(row.fastest_stop), 3),
                "total_stops_analysed": row.total_stops,
                "consistency_score": round(
                    100 / (1 + float(row.std_deviation or 1)), 2
                )
            }
            for i, row in enumerate(rows)
        ]
    }

@router.get("/circuit-overtaking-difficulty")
async def get_circuit_overtaking_difficulty(db: AsyncSession = Depends(get_db)):
    """
    Scores circuits by overtaking difficulty using mean position change
    between qualifying grid and race finish across all races at that circuit.
    Lower mean position change = harder to overtake.
    """
    query = (
        select(
            Circuit.name,
            Circuit.id,
            Circuit.country,
            func.avg(func.abs(Result.position - Result.grid)).label("avg_position_change"),
            func.count(Result.id).label("results_analysed")
        )
        .join(Race, Race.circuit_id == Circuit.id)
        .join(Result, Result.race_id == Race.id)
        .where(Result.position != None)
        .where(Result.grid != None)
        .where(Result.grid > 0)
        .group_by(Circuit.id, Circuit.name, Circuit.country)
        .having(func.count(Result.id) >= 10)
        .order_by(func.avg(func.abs(Result.position - Result.grid)))
    )

    result = await db.execute(query)
    rows = result.all()

    return {
        "methodology": (
            "Overtaking difficulty = mean absolute position change "
            "(grid → finish) across all races. Lower = harder to overtake."
        ),
        "circuits": [
            {
                "rank": i + 1,
                "circuit": row.name,
                "circuit_id": row.id,
                "country": row.country,
                "avg_position_change": round(float(row.avg_position_change), 3),
                "overtaking_difficulty": (
                    "Very Hard" if float(row.avg_position_change) < 2 else
                    "Hard" if float(row.avg_position_change) < 3 else
                    "Medium" if float(row.avg_position_change) < 4 else
                    "Easy"
                ),
                "results_analysed": row.results_analysed
            }
            for i, row in enumerate(rows)
        ]
    }

@router.get("/tyre-degradation")
async def get_tyre_degradation(
    circuit_id: int = Query(..., description="Circuit ID"),
    compound: str = Query("SOFT", description="Tyre compound: SOFT, MEDIUM, HARD"),
    db: AsyncSession = Depends(get_db)
):
    """
    Fits a quadratic regression model to historical tyre stint data
    for a specific circuit and compound. Returns degradation curve
    and model coefficients.
    """
    result = await calculate_tyre_degradation(db, circuit_id, compound)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result

@router.get("/driver-season-summary/{driver_id}")
async def get_driver_season_summary(
    driver_id: int,
    season: int = Query(..., description="Season year e.g. 2023"),
    db: AsyncSession = Depends(get_db)
):
    """
    Returns a full season performance summary for a driver including
    points, wins, podiums, DNFs, and average finishing position.
    """
    results_result = await db.execute(
        select(Result)
        .join(Race, Race.id == Result.race_id)
        .where(Result.driver_id == driver_id)
        .where(Race.season == season)
        .order_by(Race.round)
    )
    results = results_result.scalars().all()

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No results found for driver {driver_id} in {season}"
        )

    positions = [r.position for r in results if r.position]
    points_list = [r.points for r in results if r.points]

    return {
        "driver_id": driver_id,
        "season": season,
        "races_entered": len(results),
        "total_points": round(sum(points_list), 1),
        "wins": sum(1 for p in positions if p == 1),
        "podiums": sum(1 for p in positions if p and p <= 3),
        "points_finishes": sum(1 for p in positions if p and p <= 10),
        "dnfs": sum(1 for r in results if r.position is None),
        "avg_finishing_position": round(
            sum(positions) / len(positions), 2
        ) if positions else None,
        "best_finish": min(positions) if positions else None,
        "race_by_race": [
            {
                "race_id": r.race_id,
                "grid": r.grid,
                "position": r.position,
                "points": r.points,
                "status": r.status
            }
            for r in results
        ]
    }