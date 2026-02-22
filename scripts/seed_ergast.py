import asyncio
import httpx
import pandas as pd
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select, text
from app.database import Base
from app.models.driver import Driver
from app.models.circuit import Circuit
from app.models.constructor import Constructor
from app.models.race import Race
from app.models.result import Result
from app.models.pitstop import PitStop
from app.models.weather import WeatherSnapshot
from app.models.stint import TyreStint
from app.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

def load_csv(filename):
    path = os.path.join(DATA_DIR, filename)
    df = pd.read_csv(path, na_values=["\\N", "NA", ""])
    print(f"  Loaded {filename}: {len(df)} rows")
    return df

# ─────────────────────────────────────────────
# PHASE 1 — KAGGLE CSV SEEDING
# ─────────────────────────────────────────────

async def seed_circuits(session):
    print("\n[Phase 1] Seeding circuits...")
    df = load_csv("circuits.csv")
    count = 0
    for _, row in df.iterrows():
        exists = await session.execute(
            select(Circuit).where(Circuit.ergast_id == str(row["circuitId"]))
        )
        if exists.scalar_one_or_none():
            continue
        session.add(Circuit(
            ergast_id=str(row["circuitId"]),
            name=row["name"],
            country=row["country"],
            city=row["location"],
            lat=float(row["lat"]) if pd.notna(row.get("lat")) else None,
            lng=float(row["lng"]) if pd.notna(row.get("lng")) else None,
        ))
        count += 1
    await session.commit()
    print(f"  ✅ {count} circuits seeded")

async def seed_constructors(session):
    print("\n[Phase 1] Seeding constructors...")
    df = load_csv("constructors.csv")
    count = 0
    for _, row in df.iterrows():
        exists = await session.execute(
            select(Constructor).where(Constructor.ergast_id == str(row["constructorId"]))
        )
        if exists.scalar_one_or_none():
            continue
        session.add(Constructor(
            ergast_id=str(row["constructorId"]),
            name=row["name"],
            nationality=row["nationality"]
        ))
        count += 1
    await session.commit()
    print(f"  ✅ {count} constructors seeded")

async def seed_drivers(session):
    print("\n[Phase 1] Seeding drivers...")
    df = load_csv("drivers.csv")
    count = 0
    for _, row in df.iterrows():
        code = str(row["code"]) if pd.notna(row.get("code")) else None
        session.add(Driver(
            forename=row["forename"],
            surname=row["surname"],
            nationality=row["nationality"],
            code=code,
            career_points=0.0
        ))
        count += 1
    await session.commit()
    print(f"  ✅ {count} drivers seeded")

async def seed_races(session):
    print("\n[Phase 1] Seeding races (2018–2023)...")
    df = load_csv("races.csv")
    df = df[df["year"] >= 2018]
    count = 0
    for _, row in df.iterrows():
        exists = await session.execute(
            select(Race).where(Race.ergast_id == int(row["raceId"]))
        )
        if exists.scalar_one_or_none():
            continue
        circuit_result = await session.execute(
            select(Circuit).where(Circuit.ergast_id == str(row["circuitId"]))
        )
        circuit = circuit_result.scalar_one_or_none()
        if not circuit:
            continue
        session.add(Race(
            ergast_id=int(row["raceId"]),
            season=int(row["year"]),
            round=int(row["round"]),
            name=row["name"],
            date=str(row["date"]) if pd.notna(row.get("date")) else None,
            circuit_id=circuit.id
        ))
        count += 1
    await session.commit()
    print(f"  ✅ {count} races seeded")

async def seed_results(session):
    print("\n[Phase 1] Seeding results...")

    races_result = await session.execute(select(Race))
    race_map = {r.ergast_id: r.id for r in races_result.scalars().all()}

    drivers_df = load_csv("drivers.csv")
    all_drivers_result = await session.execute(select(Driver))
    all_drivers = all_drivers_result.scalars().all()
    driver_map = {}
    for _, row in drivers_df.iterrows():
        for driver in all_drivers:
            if driver.forename == row["forename"] and driver.surname == row["surname"]:
                driver_map[int(row["driverId"])] = driver.id
                break

    constructors_df = load_csv("constructors.csv")
    all_constructors_result = await session.execute(select(Constructor))
    all_constructors = all_constructors_result.scalars().all()
    constructor_map = {}
    for _, row in constructors_df.iterrows():
        for c in all_constructors:
            if c.ergast_id == str(row["constructorId"]):
                constructor_map[int(row["constructorId"])] = c.id
                break

    results_df = load_csv("results.csv")
    results_df = results_df[results_df["raceId"].isin(race_map.keys())]
    count = 0
    for _, row in results_df.iterrows():
        race_db_id = race_map.get(int(row["raceId"]))
        driver_db_id = driver_map.get(int(row["driverId"]))
        constructor_db_id = constructor_map.get(int(row["constructorId"]))
        if not race_db_id or not driver_db_id or not constructor_db_id:
            continue
        try:
            position = int(row["position"]) if pd.notna(row.get("position")) else None
        except:
            position = None
        session.add(Result(
            race_id=race_db_id,
            driver_id=driver_db_id,
            constructor_id=constructor_db_id,
            grid=int(row["grid"]) if pd.notna(row.get("grid")) else None,
            position=position,
            points=float(row["points"]) if pd.notna(row.get("points")) else 0.0,
            laps=int(row["laps"]) if pd.notna(row.get("laps")) else None,
            status=str(row["statusId"]) if pd.notna(row.get("statusId")) else None,
        ))
        count += 1
    await session.commit()
    print(f"  ✅ {count} results seeded")

async def seed_pitstops(session):
    print("\n[Phase 1] Seeding pit stops...")
    races_result = await session.execute(select(Race))
    race_map = {r.ergast_id: r.id for r in races_result.scalars().all()}

    drivers_df = load_csv("drivers.csv")
    all_drivers_result = await session.execute(select(Driver))
    all_drivers = all_drivers_result.scalars().all()
    driver_map = {}
    for _, row in drivers_df.iterrows():
        for driver in all_drivers:
            if driver.forename == row["forename"] and driver.surname == row["surname"]:
                driver_map[int(row["driverId"])] = driver.id
                break

    df = load_csv("pit_stops.csv")
    df = df[df["raceId"].isin(race_map.keys())]
    count = 0
    for _, row in df.iterrows():
        race_db_id = race_map.get(int(row["raceId"]))
        driver_db_id = driver_map.get(int(row["driverId"]))
        if not race_db_id or not driver_db_id:
            continue
        try:
            parts = str(row["duration"]).split(":")
            duration = float(parts[-1]) + (float(parts[-2]) * 60 if len(parts) > 1 else 0)
        except:
            duration = None
        session.add(PitStop(
            race_id=race_db_id,
            driver_id=driver_db_id,
            stop_number=int(row["stop"]),
            lap=int(row["lap"]),
            duration_seconds=duration
        ))
        count += 1
    await session.commit()
    print(f"  ✅ {count} pit stops seeded")

# ─────────────────────────────────────────────
# PHASE 2 — JOLPICA 2024 SEASON TOP-UP
# ─────────────────────────────────────────────

async def seed_2024_from_jolpica(session, client):
    print("\n[Phase 2] Fetching 2024 season from Jolpica...")
    try:
        r = await client.get(
            "https://api.jolpi.ca/ergast/f1/2024/results.json?limit=500",
            timeout=30
        )
        data = r.json()
        races_data = data["MRData"]["RaceTable"]["Races"]
        count = 0
        for race_data in races_data:
            circuit_result = await session.execute(
                select(Circuit).where(Circuit.ergast_id == race_data["Circuit"]["circuitId"])
            )
            circuit = circuit_result.scalar_one_or_none()
            if not circuit:
                session.add(Circuit(
                    ergast_id=race_data["Circuit"]["circuitId"],
                    name=race_data["Circuit"]["circuitName"],
                    country=race_data["Circuit"]["Location"]["country"],
                    city=race_data["Circuit"]["Location"]["locality"],
                    lat=float(race_data["Circuit"]["Location"]["lat"]),
                    lng=float(race_data["Circuit"]["Location"]["long"]),
                ))
                await session.commit()
                circuit_result = await session.execute(
                    select(Circuit).where(Circuit.ergast_id == race_data["Circuit"]["circuitId"])
                )
                circuit = circuit_result.scalar_one_or_none()

            ergast_id = 2024000 + int(race_data["round"])
            exists = await session.execute(select(Race).where(Race.ergast_id == ergast_id))
            if exists.scalar_one_or_none():
                continue

            race = Race(
                ergast_id=ergast_id,
                season=2024,
                round=int(race_data["round"]),
                name=race_data["raceName"],
                date=race_data.get("date"),
                circuit_id=circuit.id
            )
            session.add(race)
            await session.commit()
            await session.refresh(race)

            for res in race_data.get("Results", []):
                driver_code = res["Driver"].get("code")
                driver_result = await session.execute(
                    select(Driver).where(Driver.code == driver_code).limit(1)
                )
                driver = driver_result.scalar_one_or_none()
                if not driver:
                    driver = Driver(
                        forename=res["Driver"]["givenName"],
                        surname=res["Driver"]["familyName"],
                        nationality=res["Driver"]["nationality"],
                        code=res["Driver"].get("code"),
                        career_points=0.0
                    )
                    session.add(driver)
                    await session.commit()
                    await session.refresh(driver)

                constructor_result = await session.execute(
                    select(Constructor).where(Constructor.ergast_id == res["Constructor"]["constructorId"])
                )
                constructor = constructor_result.scalar_one_or_none()
                if not constructor:
                    constructor = Constructor(
                        ergast_id=res["Constructor"]["constructorId"],
                        name=res["Constructor"]["name"],
                        nationality=res["Constructor"]["nationality"]
                    )
                    session.add(constructor)
                    await session.commit()
                    await session.refresh(constructor)

                try:
                    position = int(res["position"]) if res.get("position", "").isdigit() else None
                except:
                    position = None

                session.add(Result(
                    race_id=race.id,
                    driver_id=driver.id,
                    constructor_id=constructor.id,
                    grid=int(res.get("grid", 0)),
                    position=position,
                    points=float(res.get("points", 0)),
                    laps=int(res.get("laps", 0)),
                    status=res.get("status"),
                ))
            await session.commit()
            count += 1
        print(f"  ✅ {count} 2024 races seeded from Jolpica")
    except Exception as e:
        print(f"  ⚠️ Jolpica failed: {e} — skipping 2024 top-up")

# ─────────────────────────────────────────────
# PHASE 3 — OPENF1 WEATHER + TYRE STINTS
# ─────────────────────────────────────────────

async def fetch_openf1(client, url, retries=3):
    for attempt in range(retries):
        try:
            r = await client.get(url, timeout=30)
            return r.json()
        except Exception as e:
            if attempt == retries - 1:
                print(f"  ⚠️ Failed: {url} — {e}")
                return []
            await asyncio.sleep(2)

async def seed_openf1_data(session, client):
    print("\n[Phase 3] Fetching OpenF1 sessions for 2023–2024...")

    all_sessions = []
    for year in [2023, 2024]:
        data = await fetch_openf1(client, f"https://api.openf1.org/v1/sessions?year={year}&session_name=Race")
        all_sessions.extend(data)
        await asyncio.sleep(0.5)

    print(f"  Found {len(all_sessions)} race sessions in OpenF1")

    races_result = await session.execute(select(Race))
    all_races = races_result.scalars().all()

    circuits_result = await session.execute(select(Circuit))
    all_circuits = circuits_result.scalars().all()
    circuit_by_country = {c.country.lower(): c for c in all_circuits}

    drivers_result = await session.execute(select(Driver))
    all_drivers = drivers_result.scalars().all()

    weather_count = 0
    stint_count = 0

    for openf1_session in all_sessions:
        session_key = openf1_session["session_key"]
        year = openf1_session["year"]
        country = openf1_session["country_name"]

        # Match to our race using country + year
        matched_race = None
        for race in all_races:
            if race.season == year:
                circuit = next((c for c in all_circuits if c.id == race.circuit_id), None)
                if circuit and circuit.country.lower() == country.lower():
                    matched_race = race
                    break

        if not matched_race:
            continue

        # Check if already seeded
        existing_weather = await session.execute(
            select(WeatherSnapshot).where(WeatherSnapshot.session_key == session_key).limit(1)
        )
        if existing_weather.scalar_one_or_none():
            continue

        # Fetch weather (sample every 10th reading to keep DB size manageable)
        weather_data = await fetch_openf1(
            client, f"https://api.openf1.org/v1/weather?session_key={session_key}"
        )
        
        if not isinstance(weather_data, list):
            weather_data = []
        for i, w in enumerate(weather_data):
            if not isinstance(w, dict):
                continue
            session.add(WeatherSnapshot(
                race_id=matched_race.id,
                session_key=session_key,
                timestamp=w.get("date", ""),
                air_temperature=w.get("air_temperature"),
                track_temperature=w.get("track_temperature"),
                humidity=w.get("humidity"),
                rainfall=w.get("rainfall"),
                wind_speed=w.get("wind_speed"),
                pressure=w.get("pressure"),
            ))
            weather_count += 1
        await session.commit()

        # Fetch tyre stints for all drivers
        stints_data = await fetch_openf1(
            client, f"https://api.openf1.org/v1/stints?session_key={session_key}"
        )
        if not isinstance(stints_data, list):
            stints_data = []
        for stint in stints_data:
            if not isinstance(stint, dict):
                continue
            driver_number = stint.get("driver_number")
            matched_driver = next(
                (d for d in all_drivers if str(driver_number) in str(d.code or "")), None
            )
            session.add(TyreStint(
                race_id=matched_race.id,
                session_key=session_key,
                driver_number=driver_number,
                driver_id=matched_driver.id if matched_driver else None,
                stint_number=stint.get("stint_number", 0),
                compound=stint.get("compound"),
                lap_start=stint.get("lap_start"),
                lap_end=stint.get("lap_end"),
                tyre_age_at_start=stint.get("tyre_age_at_start"),
            ))
            stint_count += 1
        await session.commit()

        print(f"  ✅ Session {session_key} ({country} {year}): {len(weather_data)} weather, {len(stints_data)} stints")
        await asyncio.sleep(0.4)  # respect rate limit

    print(f"\n  ✅ Total: {weather_count} weather snapshots, {stint_count} tyre stints seeded")

# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

async def main():
    print("🏁 F1 Strategic Intelligence API — Database Seeder")
    print("=" * 50)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created")

    async with AsyncSessionLocal() as session:
        # Phase 1 — CSV
        await seed_circuits(session)
        await seed_constructors(session)
        await seed_drivers(session)
        await seed_races(session)
        await seed_results(session)
        await seed_pitstops(session)

        # Phase 2 — Jolpica
        async with httpx.AsyncClient() as client:
            await seed_2024_from_jolpica(session, client)

            # Phase 3 — OpenF1
            await seed_openf1_data(session, client)

    print("\n" + "=" * 50)
    print("🏁 All seeding complete!")

if __name__ == "__main__":
    asyncio.run(main())