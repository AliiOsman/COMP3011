from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.result import Result
from app.models.race import Race
from app.models.driver import Driver
from app.models.weather import WeatherSnapshot

async def calculate_wet_weather_scores(db: AsyncSession) -> dict:
    # Find races where rainfall recorded > 0
    wet_race_result = await db.execute(
        select(WeatherSnapshot.race_id)
        .where(WeatherSnapshot.rainfall > 0)
        .group_by(WeatherSnapshot.race_id)
        .having(func.count(WeatherSnapshot.id) >= 3)
    )
    wet_race_ids = [r[0] for r in wet_race_result.all()]

    # Fallback to known historically wet races
    if len(wet_race_ids) < 3:
        wet_names_result = await db.execute(
            select(Race.id).where(
                Race.name.ilike("%Brazil%") |
                Race.name.ilike("%British%") |
                Race.name.ilike("%Belgium%") |
                Race.name.ilike("%Japanese%") |
                Race.name.ilike("%German%")
            ).where(Race.season >= 2018)
        )
        wet_race_ids = list(set(wet_race_ids + [r[0] for r in wet_names_result.all()]))

    if not wet_race_ids:
        return {"error": "No wet race data found", "scores": []}

    # Get results for wet races
    results_result = await db.execute(
        select(Result)
        .where(Result.race_id.in_(wet_race_ids))
        .where(Result.position != None)
        .where(Result.grid != None)
        .where(Result.grid > 0)
        .where(Result.position > 0)
    )
    results = results_result.scalars().all()

    # Get drivers
    drivers_result = await db.execute(select(Driver))
    driver_map = {d.id: f"{d.forename} {d.surname}" for d in drivers_result.scalars().all()}

    # Calculate expected position based on grid
    # To normalise for car quality, compare position delta relative to grid
    # A driver starting P15 gaining 5 places is less impressive than 
    # a driver starting P3 gaining 5 places (fighting faster cars)
    driver_stats = {}
    for r in results:
        if r.driver_id not in driver_stats:
            driver_stats[r.driver_id] = {
                "deltas": [],
                "grids": [],
                "positions": [],
                "races": 0,
                "name": driver_map.get(r.driver_id, "Unknown")
            }
        delta = r.grid - r.position  # positive = gained places
        driver_stats[r.driver_id]["deltas"].append(delta)
        driver_stats[r.driver_id]["grids"].append(r.grid)
        driver_stats[r.driver_id]["positions"].append(r.position)
        driver_stats[r.driver_id]["races"] += 1

    # Score with grid normalisation
    # Bonus for beating drivers who started ahead of you
    scores = []
    for driver_id, stats in driver_stats.items():
        if stats["races"] < 3:
            continue

        raw_delta = sum(stats["deltas"]) / len(stats["deltas"])
        avg_grid = sum(stats["grids"]) / len(stats["grids"])
        avg_finish = sum(stats["positions"]) / len(stats["positions"])

        # Normalised score: penalise drivers who start far back
        # A driver starting P12 avg needs higher delta to score well
        normalised_score = raw_delta - (avg_grid - 10) * 0.15

        scores.append({
            "driver_id": driver_id,
            "driver": stats["name"],
            "wet_races_analysed": stats["races"],
            "avg_grid_position": round(avg_grid, 1),
            "avg_finish_position": round(avg_finish, 1),
            "avg_position_gain": round(raw_delta, 3),
            "normalised_wet_score": round(normalised_score, 3),
            "wet_weather_rating": (
                "Elite" if normalised_score > 2 else
                "Strong" if normalised_score > 0.5 else
                "Average" if normalised_score > -0.5 else
                "Weak"
            )
        })

    # Sort by normalised score
    scores.sort(key=lambda x: x["normalised_wet_score"], reverse=True)

    return {
        "wet_races_analysed": len(wet_race_ids),
        "total_drivers_scored": len(scores),
        "methodology": (
            "Normalised wet weather score = mean position gain adjusted for "
            "average grid position. Drivers starting near the front who still "
            "gain positions score higher than backmarkers gaining easy places. "
            "Minimum 3 wet races required for inclusion."
        ),
        "limitations": [
            "Based on circuit-level rainfall data and historically wet circuits",
            "Does not distinguish between light drizzle and heavy rain",
            "Grid position normalisation is approximate"
        ],
        "scores": scores
    }