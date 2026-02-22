from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.pitstop import PitStop
from app.models.result import Result
from app.models.race import Race
from app.models.stint import TyreStint

async def calculate_pit_window(
    db: AsyncSession,
    race_id: int,
    driver_id: int
) -> dict:
    # Get race info
    race = await db.get(Race, race_id)
    if not race:
        return {"error": "Race not found"}

    # Get driver's pit stops in this race
    stops_result = await db.execute(
        select(PitStop)
        .where(PitStop.race_id == race_id)
        .where(PitStop.driver_id == driver_id)
        .order_by(PitStop.lap)
    )
    stops = stops_result.scalars().all()

    # Get driver's tyre stints
    stints_result = await db.execute(
        select(TyreStint)
        .where(TyreStint.race_id == race_id)
        .where(TyreStint.driver_id == driver_id)
        .order_by(TyreStint.stint_number)
    )
    stints = stints_result.scalars().all()

    # Get avg pit stop duration for this circuit (historical)
    circuit_races_result = await db.execute(
        select(Race.id).where(Race.circuit_id == race.circuit_id)
    )
    circuit_race_ids = [r[0] for r in circuit_races_result.all()]

    avg_stop_result = await db.execute(
        select(func.avg(PitStop.duration_seconds))
        .where(PitStop.race_id.in_(circuit_race_ids))
        .where(PitStop.duration_seconds != None)
        .where(PitStop.duration_seconds < 60)
    )
    avg_pit_duration = avg_stop_result.scalar() or 25.0

    # Get total laps from results
    driver_result = await db.execute(
        select(Result)
        .where(Result.race_id == race_id)
        .where(Result.driver_id == driver_id)
    )
    result = driver_result.scalars().first()
    total_laps = result.laps if result and result.laps else 50

    # Compound degradation rates (laps before significant degradation)
    degradation_windows = {
        "SOFT": 20,
        "MEDIUM": 30,
        "HARD": 40,
        "INTERMEDIATE": 25,
        "WET": 35,
    }

    # Build stint analysis
    stint_analysis = []
    recommended_pit_laps = []

    for stint in stints:
        compound = stint.compound or "MEDIUM"
        window = degradation_windows.get(compound, 30)
        optimal_pit = (stint.lap_start or 1) + window
        optimal_pit = min(optimal_pit, total_laps - 5)

        stint_analysis.append({
            "stint_number": stint.stint_number,
            "compound": compound,
            "lap_start": stint.lap_start,
            "lap_end": stint.lap_end,
            "tyre_age_at_start": stint.tyre_age_at_start,
            "optimal_pit_lap": optimal_pit,
            "degradation_window_laps": window,
        })
        recommended_pit_laps.append(optimal_pit)

    # Undercut window — pit 2-3 laps earlier than optimal
    undercut_laps = [max(1, lap - 3) for lap in recommended_pit_laps]

    return {
        "race_id": race_id,
        "driver_id": driver_id,
        "circuit": race.name,
        "season": race.season,
        "avg_pit_stop_duration_seconds": round(avg_pit_duration, 3),
        "total_laps": total_laps,
        "actual_pit_stops": [
            {"lap": s.lap, "stop_number": s.stop_number,
             "duration_seconds": s.duration_seconds}
            for s in stops
        ],
        "stint_analysis": stint_analysis,
        "recommended_pit_laps": recommended_pit_laps,
        "undercut_window_laps": undercut_laps,
        "strategy_summary": (
            f"{'1-stop' if len(stints) <= 2 else '2-stop'} strategy detected. "
            f"Optimal pit window based on compound degradation models."
        )
    }