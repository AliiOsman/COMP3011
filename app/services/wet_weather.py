from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.result import Result
from app.models.race import Race
from app.models.driver import Driver
from app.models.weather import WeatherSnapshot

async def calculate_wet_weather_scores(db: AsyncSession) -> dict:
    # Find races where rainfall > 0 using weather snapshots
    wet_race_result = await db.execute(
        select(WeatherSnapshot.race_id)
        .where(WeatherSnapshot.rainfall > 0)
        .distinct()
    )
    wet_race_ids = [r[0] for r in wet_race_result.all()]

    if not wet_race_ids:
        # Fallback: use known historically wet races by name
        wet_names_result = await db.execute(
            select(Race.id).where(
                Race.name.ilike("%Brazil%") |
                Race.name.ilike("%British%") |
                Race.name.ilike("%German%") |
                Race.name.ilike("%Belgium%")
            ).where(Race.season >= 2018)
        )
        wet_race_ids = [r[0] for r in wet_names_result.all()]

    if not wet_race_ids:
        return {"error": "No wet race data found", "scores": []}

    # Get all results for wet races
    results_result = await db.execute(
        select(Result)
        .where(Result.race_id.in_(wet_race_ids))
        .where(Result.position != None)
        .where(Result.grid != None)
        .where(Result.grid > 0)
    )
    results = results_result.scalars().all()

    # Get all drivers
    drivers_result = await db.execute(select(Driver))
    driver_map = {d.id: f"{d.forename} {d.surname}" for d in drivers_result.scalars().all()}

    # Calculate position delta per driver across wet races
    driver_stats = {}
    for r in results:
        if r.driver_id not in driver_stats:
            driver_stats[r.driver_id] = {
                "deltas": [],
                "races": 0,
                "name": driver_map.get(r.driver_id, "Unknown")
            }
        # Positive delta = gained positions (good wet performer)
        delta = r.grid - r.position
        driver_stats[r.driver_id]["deltas"].append(delta)
        driver_stats[r.driver_id]["races"] += 1

    # Score = mean position delta, only drivers with 3+ wet races
    scores = []
    for driver_id, stats in driver_stats.items():
        if stats["races"] < 3:
            continue
        mean_delta = sum(stats["deltas"]) / len(stats["deltas"])
        scores.append({
            "driver_id": driver_id,
            "driver": stats["name"],
            "wet_races_analysed": stats["races"],
            "avg_position_gain": round(mean_delta, 3),
            "wet_weather_rating": "Elite" if mean_delta > 2 else
                                  "Strong" if mean_delta > 0.5 else
                                  "Average" if mean_delta > -0.5 else "Weak"
        })

    scores.sort(key=lambda x: x["avg_position_gain"], reverse=True)

    return {
        "wet_races_analysed": len(wet_race_ids),
        "methodology": (
            "Score = mean(qualifying_position - race_position) across all wet races. "
            "Positive score indicates positions gained in wet conditions."
        ),
        "scores": scores
    }