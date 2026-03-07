import os
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.elo_engine import compute_constructor_elo
from app.services.wet_weather import calculate_wet_weather_scores

REGULATIONS_2026 = """
KEY 2026 F1 REGULATION CHANGES:
1. POWER UNIT: 50/50 split between ICE and electrical power (up from 20/80 MGU-K ratio).
   New MGU-K delivers 350kW (vs 120kW in 2025). MGU-H removed entirely.
2. AERODYNAMICS: Active aerodynamics introduced - 'Z-mode' (low drag on straights)
   and 'X-mode' (high downforce in corners). Cars automatically switch between modes.
3. CAR DIMENSIONS: Shorter (5400mm vs 5600mm) and narrower (1900mm vs 2000mm).
   Significant weight reduction target.
4. TYRE COMPOUNDS: Pirelli developing new compounds for lighter, more powerful cars.
   Higher electrical torque increases tyre stress significantly.
5. OVERTAKING: Active aero designed to reduce dirty air effect by 50% vs 2022 cars,
   improving wheel-to-wheel racing.
6. IMPLICATIONS: Teams with strong electrical/hybrid expertise (Mercedes, Ferrari)
   may have advantage. Active aero requires sophisticated software.
   Smaller cars favour different circuit characteristics.
   High electrical torque means tyre management becomes even more critical.
"""


async def get_ai_strategy_recommendation(
    session: AsyncSession,
    constructor_name: str,
    circuit_name: str,
    circuit_id: int,
    season: int = 2026
) -> dict:
    """
    Combines historical F1 performance data with local LLaMA AI reasoning
    to generate 2026 regulation-aware strategic recommendations.

    Uses Ollama (local) in development, Anthropic Claude in production
    if ANTHROPIC_API_KEY is set.
    """

    # Gather real data from existing services
    elo_data = await compute_constructor_elo(session)
    wet_data = await calculate_wet_weather_scores(session)

    # Extract constructor Elo rating and rank
    constructor_elo = None
    elo_rank = None
    for i, r in enumerate(elo_data.get("ratings", [])):
        if constructor_name.lower() in r["constructor"].lower():
            constructor_elo = round(r["elo"], 2)
            elo_rank = i + 1
            break

    total_constructors = len(elo_data.get("ratings", []))

    # Extract top wet weather drivers
    top_wet_drivers = [
        f"{s['driver']} ({s['wet_weather_rating']})"
        for s in wet_data.get("scores", [])[:5]
    ]

    # Build the prompt with real data embedded
    prompt = f"""You are an expert F1 race strategist advising for the 2026 season.

HISTORICAL PERFORMANCE DATA (from F1 database 2018-2024):
- Constructor: {constructor_name}
- Elo Rating: {constructor_elo or 'Not found'} (Rank {elo_rank or 'Unknown'} of {total_constructors} constructors)
- Circuit: {circuit_name}
- Top wet weather performers in dataset: {', '.join(top_wet_drivers) if top_wet_drivers else 'No data available'}

{REGULATIONS_2026}

Based on this constructor's historical Elo performance and the 2026 regulation changes, provide a structured assessment with exactly these four sections:

1. REGULATION IMPACT ASSESSMENT
How will the 2026 changes specifically affect {constructor_name} based on their Elo rank of {elo_rank or 'Unknown'} out of {total_constructors}?

2. CIRCUIT STRATEGY FOR {circuit_name.upper()}
What strategic approach should {constructor_name} adopt for this circuit under 2026 regulations? Consider active aero Z-mode vs X-mode deployment, tyre management under higher electrical torque, and optimal pit stop timing.

3. KEY RISKS
The 2 biggest strategic risks for {constructor_name} in 2026.

4. CONFIDENCE LEVEL
Rate confidence as Low, Medium, or High and explain why based on the data provided.

Be concise, specific, and always reference the Elo rating in your assessment."""

    ai_response = None
    model_used = None

    async with httpx.AsyncClient(timeout=60) as client:
        groq_key = os.environ.get("GROQ_API_KEY")
        if groq_key:
            try:
                response = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {groq_key}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 1000
                    }
                )
                ai_response = response.json()["choices"][0]["message"]["content"]
                model_used = "llama-3.1-8b-instant (Groq)"
            except Exception as e:
                model_used = "unavailable"
                ai_response = None

        if not ai_response:
            model_used = "unavailable"
    return {
        "constructor": constructor_name,
        "circuit": circuit_name,
        "season": season,
        "historical_data": {
            "elo_rating": constructor_elo,
            "elo_rank": elo_rank,
            "total_constructors_ranked": total_constructors,
            "top_wet_weather_drivers": top_wet_drivers,
            "data_coverage": "2018-2024 seasons"
        },
        "regulation_changes_considered": [
            "50/50 ICE/Electric power split (350kW MGU-K)",
            "Active aerodynamics Z-mode/X-mode",
            "Smaller lighter car dimensions (5400mm x 1900mm)",
            "MGU-H removal",
            "New Pirelli compounds for higher torque loads"
        ],
        "ai_strategic_recommendation": ai_response,
        "model_used": model_used,
        "powered_by": "LLaMA 3.2 via Ollama (local) / Claude (production) + F1 Historical Database",
        "disclaimer": (
            "This recommendation combines historical performance patterns (2018-2024) "
            "with AI reasoning about known 2026 regulation changes. "
            "No 2026 race data exists — this is a predictive pre-season analysis tool. "
            "Not suitable for real race strategy decisions."
        )
    }