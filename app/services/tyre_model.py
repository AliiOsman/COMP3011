import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.stint import TyreStint
from app.models.race import Race
from app.models.circuit import Circuit

async def calculate_tyre_degradation(
    db: AsyncSession,
    circuit_id: int,
    compound: str
) -> dict:
    """
    Fits a quadratic regression model to tyre stint data for a given
    circuit and compound. Models expected lap time degradation as a
    function of tyre age in laps.
    """
    # Get all races at this circuit
    races_result = await db.execute(
        select(Race.id).where(Race.circuit_id == circuit_id)
    )
    race_ids = [r[0] for r in races_result.all()]

    if not race_ids:
        return {"error": f"No races found for circuit_id {circuit_id}"}

    # Get all stints for this compound at this circuit
    stints_result = await db.execute(
        select(TyreStint)
        .where(TyreStint.race_id.in_(race_ids))
        .where(TyreStint.compound == compound.upper())
        .where(TyreStint.lap_start != None)
        .where(TyreStint.lap_end != None)
    )
    stints = stints_result.scalars().all()

    if len(stints) < 3:
        return {
            "error": f"Insufficient data for {compound} at circuit {circuit_id}",
            "stints_found": len(stints)
        }

    # Build tyre age vs stint length data points
    tyre_ages = []
    stint_lengths = []
    for stint in stints:
        age = stint.tyre_age_at_start or 0
        length = (stint.lap_end - stint.lap_start) if stint.lap_end and stint.lap_start else 0
        if length > 0:
            tyre_ages.append(float(age))
            stint_lengths.append(float(length))

    if len(tyre_ages) < 3:
        return {"error": "Not enough valid stint data points for regression"}

    tyre_ages = np.array(tyre_ages)
    stint_lengths = np.array(stint_lengths)

    # Fit quadratic regression: stint_length = a*age^2 + b*age + c
    coefficients = np.polyfit(tyre_ages, stint_lengths, deg=2)
    a, b, c = coefficients

    # R-squared
    predicted = np.polyval(coefficients, tyre_ages)
    ss_res = np.sum((stint_lengths - predicted) ** 2)
    ss_tot = np.sum((stint_lengths - np.mean(stint_lengths)) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    # Generate degradation curve predictions (age 0 to 50 laps)
    age_range = list(range(0, 51, 5))
    degradation_curve = [
        {
            "tyre_age_laps": age,
            "predicted_stint_length": max(0, round(float(np.polyval(coefficients, age)), 2))
        }
        for age in age_range
    ]

    # Get circuit name
    circuit_result = await db.get(Circuit, circuit_id)
    circuit_name = circuit_result.name if circuit_result else f"Circuit {circuit_id}"

    return {
        "circuit_id": circuit_id,
        "circuit": circuit_name,
        "compound": compound.upper(),
        "stints_analysed": len(stints),
        "model": {
            "type": "Quadratic Regression",
            "coefficients": {
                "a (quadratic)": round(float(a), 6),
                "b (linear)": round(float(b), 6),
                "c (intercept)": round(float(c), 6)
            },
            "r_squared": round(float(r_squared), 4),
            "interpretation": (
                "Model predicts expected stint length based on tyre age at start. "
                "Higher tyre age at start = shorter expected stint."
            )
        },
        "degradation_curve": degradation_curve,
        "recommendation": (
            f"Based on {len(stints)} {compound} stints at {circuit_name}, "
            f"model fit quality is {'good' if r_squared > 0.5 else 'moderate'} "
            f"(R²={round(float(r_squared), 3)})."
        )
    }