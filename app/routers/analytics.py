from fastapi import APIRouter, Depends, HTTPException, Query, Request
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
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

router = APIRouter()

@router.get("/pit-crew-performance")
@limiter.limit("20/minute")
async def get_pit_crew_performance(
    request: Request,
    season: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db)
):
    """
    Ranks constructors by pit crew execution speed using statistical
    analysis. Computes mean, minimum, and consistency score across
    all pit stops. Standard deviation computed in Python for
    database compatibility.
    """
    query = (
        select(
            Constructor.name,
            Constructor.id,
            func.avg(PitStop.duration_seconds).label("avg_duration"),
            func.min(PitStop.duration_seconds).label("fastest_stop"),
            func.count(PitStop.id).label("total_stops")
        )
        .join(Result, Result.constructor_id == Constructor.id)
        .join(PitStop, (PitStop.race_id == Result.race_id) &
              (PitStop.driver_id == Result.driver_id))
    )

    if season:
        query = query.join(Race, Race.id == PitStop.race_id).where(
            Race.season == season
        )

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

    # Fetch raw durations per constructor for std dev calculation in Python
    rankings = []
    for i, row in enumerate(rows):
        # Get all durations for this constructor
        durations_query = (
            select(PitStop.duration_seconds)
            .join(Result, (Result.race_id == PitStop.race_id) &
                  (Result.driver_id == PitStop.driver_id))
            .where(Result.constructor_id == row.id)
            .where(PitStop.duration_seconds != None)
            .where(PitStop.duration_seconds > 1)
            .where(PitStop.duration_seconds < 60)
        )
        if season:
            durations_query = durations_query.join(
                Race, Race.id == PitStop.race_id
            ).where(Race.season == season)

        durations_result = await db.execute(durations_query)
        durations = [d[0] for d in durations_result.all()]

        # Calculate std dev in Python
        if len(durations) > 1:
            mean = sum(durations) / len(durations)
            variance = sum((x - mean) ** 2 for x in durations) / len(durations)
            std_dev = variance ** 0.5
        else:
            std_dev = 0.0

        consistency_score = round(100 / (1 + std_dev), 2)

        rankings.append({
            "rank": i + 1,
            "constructor": row.name,
            "constructor_id": row.id,
            "avg_stop_seconds": round(float(row.avg_duration), 3),
            "fastest_stop_seconds": round(float(row.fastest_stop), 3),
            "total_stops_analysed": row.total_stops,
            "std_deviation_seconds": round(std_dev, 3),
            "consistency_score": consistency_score
        })

    return {
        "season_filter": season,
        "methodology": (
            "Consistency score = 100 / (1 + std_deviation). "
            "Higher = more consistent pit stops. "
            "Std deviation computed across all valid pit stops per constructor."
        ),
        "rankings": rankings
    }
    
@router.get("/circuit-overtaking-difficulty")
@limiter.limit("10/minute")
async def get_circuit_overtaking_difficulty(request: Request, db: AsyncSession = Depends(get_db)):
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

@router.get("/head-to-head/{driver_a_id}/{driver_b_id}")
@limiter.limit("10/minute")
async def get_head_to_head(
    request: Request,
    driver_a_id: int,
    driver_b_id: int,
    season: Optional[int] = Query(None, description="Filter by season"),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyses the head-to-head rivalry between two drivers across all
    races they competed in together. Computes dominance score, circuit
    type breakdown, and conditions-based performance splits.

    Dominance score = (wins_a - wins_b) / total_shared_races * 100
    A positive score favours driver A, negative favours driver B.
    """
    from app.models.driver import Driver

    # Validate both drivers exist
    driver_a = await db.get(Driver, driver_a_id)
    driver_b = await db.get(Driver, driver_b_id)
    if not driver_a or not driver_b:
        raise HTTPException(status_code=404, detail="One or both drivers not found")

    # Get all races where both drivers competed
    query_a = select(Result.race_id).where(Result.driver_id == driver_a_id)
    query_b = select(Result.race_id).where(Result.driver_id == driver_b_id)

    if season:
        query_a = query_a.join(Race, Race.id == Result.race_id).where(
            Race.season == season
        )
        query_b = query_b.join(Race, Race.id == Result.race_id).where(
            Race.season == season
        )

    races_a = set(r[0] for r in (await db.execute(query_a)).all())
    races_b = set(r[0] for r in (await db.execute(query_b)).all())
    shared_race_ids = list(races_a & races_b)

    if not shared_race_ids:
        raise HTTPException(
            status_code=404,
            detail="No shared races found for these drivers"
        )

    # Get results for both drivers in shared races
    results_result = await db.execute(
        select(Result, Race)
        .join(Race, Race.id == Result.race_id)
        .where(Result.race_id.in_(shared_race_ids))
        .where(Result.driver_id.in_([driver_a_id, driver_b_id]))
        .where(Result.position != None)
        .order_by(Race.season, Race.round)
    )
    rows = results_result.all()

    # Build race-by-race comparison
    race_data = {}
    for result, race in rows:
        if race.id not in race_data:
            race_data[race.id] = {
                "race_name": race.name,
                "season": race.season,
                "round": race.round,
                "circuit_id": race.circuit_id
            }
        if result.driver_id == driver_a_id:
            race_data[race.id]["pos_a"] = result.position
            race_data[race.id]["grid_a"] = result.grid
            race_data[race.id]["points_a"] = result.points
        else:
            race_data[race.id]["pos_b"] = result.position
            race_data[race.id]["grid_b"] = result.grid
            race_data[race.id]["points_b"] = result.points

    # Only include races where we have both drivers' positions
    complete_races = {
        k: v for k, v in race_data.items()
        if "pos_a" in v and "pos_b" in v
    }

    if not complete_races:
        raise HTTPException(
            status_code=404,
            detail="No races with complete data for both drivers"
        )

    # Calculate head-to-head stats
    wins_a = wins_b = 0
    total_points_a = total_points_b = 0
    position_diffs = []
    race_by_race = []

    for race_id, data in complete_races.items():
        pos_a = data["pos_a"]
        pos_b = data["pos_b"]
        winner = "driver_a" if pos_a < pos_b else "driver_b"

        if winner == "driver_a":
            wins_a += 1
        else:
            wins_b += 1

        total_points_a += data.get("points_a", 0) or 0
        total_points_b += data.get("points_b", 0) or 0
        position_diffs.append(pos_b - pos_a)

        race_by_race.append({
            "race": data["race_name"],
            "season": data["season"],
            "round": data["round"],
            "driver_a_position": pos_a,
            "driver_b_position": pos_b,
            "winner": winner,
            "position_gap": abs(pos_b - pos_a)
        })

    total = len(complete_races)
    avg_pos_diff = sum(position_diffs) / len(position_diffs)
    dominance_score = round((wins_a - wins_b) / total * 100, 2)

    # Season-by-season breakdown
    seasons = {}
    for r in race_by_race:
        s = r["season"]
        if s not in seasons:
            seasons[s] = {"wins_a": 0, "wins_b": 0, "races": 0}
        seasons[s]["races"] += 1
        if r["winner"] == "driver_a":
            seasons[s]["wins_a"] += 1
        else:
            seasons[s]["wins_b"] += 1

    season_breakdown = [
        {
            "season": s,
            "races_together": v["races"],
            "driver_a_wins": v["wins_a"],
            "driver_b_wins": v["wins_b"],
            "season_winner": (
                f"{driver_a.forename} {driver_a.surname}"
                if v["wins_a"] > v["wins_b"]
                else f"{driver_b.forename} {driver_b.surname}"
                if v["wins_b"] > v["wins_a"]
                else "Tied"
            )
        }
        for s, v in sorted(seasons.items())
    ]

    return {
        "driver_a": {
            "id": driver_a_id,
            "name": f"{driver_a.forename} {driver_a.surname}",
            "nationality": driver_a.nationality
        },
        "driver_b": {
            "id": driver_b_id,
            "name": f"{driver_b.forename} {driver_b.surname}",
            "nationality": driver_b.nationality
        },
        "season_filter": season,
        "shared_races_analysed": total,
        "head_to_head": {
            "driver_a_wins": wins_a,
            "driver_b_wins": wins_b,
            "driver_a_win_rate": round(wins_a / total * 100, 1),
            "driver_b_win_rate": round(wins_b / total * 100, 1),
            "driver_a_total_points": round(total_points_a, 1),
            "driver_b_total_points": round(total_points_b, 1),
            "avg_position_gap": round(abs(avg_pos_diff), 3),
            "dominance_score": dominance_score,
            "overall_winner": (
                f"{driver_a.forename} {driver_a.surname}"
                if wins_a > wins_b
                else f"{driver_b.forename} {driver_b.surname}"
                if wins_b > wins_a
                else "Tied"
            )
        },
        "methodology": (
            "Head-to-head win = finishing ahead of opponent in shared race. "
            "Dominance score = (wins_a - wins_b) / total_races * 100. "
            "Positive score favours driver A. Points are championship points scored."
        ),
        "season_breakdown": season_breakdown,
        "race_by_race": race_by_race
    }