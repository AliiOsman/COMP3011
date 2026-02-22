import asyncio
import httpx
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import select
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import Base
from app.models.driver import Driver
from app.models.circuit import Circuit
from app.models.constructor import Constructor
from app.models.race import Race
from app.models.result import Result
from app.models.pitstop import PitStop
from app.config import settings

DATABASE_URL = settings.DATABASE_URL
engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

BASE_URL = "http://ergast.com/api/f1"
SEASONS = [2021, 2022, 2023]  # expand later if needed

async def fetch(client: httpx.AsyncClient, url: str) -> dict:
    r = await client.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

async def seed_circuits(session, client):
    print("Seeding circuits...")
    data = await fetch(client, f"{BASE_URL}/circuits.json?limit=100")
    circuits = data["MRData"]["CircuitTable"]["Circuits"]
    for c in circuits:
        exists = await session.execute(select(Circuit).where(Circuit.ergast_id == c["circuitId"]))
        if exists.scalar_one_or_none():
            continue
        session.add(Circuit(
            ergast_id=c["circuitId"],
            name=c["circuitName"],
            country=c["Location"]["country"],
            city=c["Location"]["locality"],
            lat=float(c["Location"]["lat"]),
            lng=float(c["Location"]["long"])
        ))
    await session.commit()
    print("✅ Circuits done")

async def seed_constructors(session, client):
    print("Seeding constructors...")
    data = await fetch(client, f"{BASE_URL}/constructors.json?limit=200")
    constructors = data["MRData"]["ConstructorTable"]["Constructors"]
    for c in constructors:
        exists = await session.execute(select(Constructor).where(Constructor.ergast_id == c["constructorId"]))
        if exists.scalar_one_or_none():
            continue
        session.add(Constructor(
            ergast_id=c["constructorId"],
            name=c["name"],
            nationality=c["nationality"]
        ))
    await session.commit()
    print("✅ Constructors done")

async def seed_drivers(session, client):
    print("Seeding drivers...")
    data = await fetch(client, f"{BASE_URL}/drivers.json?limit=1000")
    drivers = data["MRData"]["DriverTable"]["Drivers"]
    for d in drivers:
        exists = await session.execute(select(Driver).where(Driver.code == d.get("code")))
        if d.get("code") and exists.scalar_one_or_none():
            continue
        session.add(Driver(
            forename=d["givenName"],
            surname=d["familyName"],
            nationality=d["nationality"],
            code=d.get("code"),
            career_points=0.0
        ))
    await session.commit()
    print("✅ Drivers done")

async def seed_races_and_results(session, client):
    for season in SEASONS:
        print(f"Seeding races for {season}...")
        data = await fetch(client, f"{BASE_URL}/{season}/results.json?limit=500")
        races_data = data["MRData"]["RaceTable"]["Races"]

        for race_data in races_data:
            # Get or create circuit
            circuit_result = await session.execute(
                select(Circuit).where(Circuit.ergast_id == race_data["Circuit"]["circuitId"])
            )
            circuit = circuit_result.scalar_one_or_none()
            if not circuit:
                continue

            # Get or create race
            race_result = await session.execute(
                select(Race).where(Race.ergast_id == int(race_data["round"]) + season * 1000)
            )
            race = race_result.scalar_one_or_none()
            if not race:
                race = Race(
                    ergast_id=int(race_data["round"]) + season * 1000,
                    season=season,
                    round=int(race_data["round"]),
                    name=race_data["raceName"],
                    date=race_data.get("date"),
                    circuit_id=circuit.id
                )
                session.add(race)
                await session.commit()
                await session.refresh(race)

            # Seed results
            for res in race_data.get("Results", []):
                driver_result = await session.execute(
                    select(Driver).where(Driver.code == res["Driver"].get("code"))
                )
                driver = driver_result.scalar_one_or_none()

                constructor_result = await session.execute(
                    select(Constructor).where(Constructor.ergast_id == res["Constructor"]["constructorId"])
                )
                constructor = constructor_result.scalar_one_or_none()

                if not driver or not constructor:
                    continue

                session.add(Result(
                    race_id=race.id,
                    driver_id=driver.id,
                    constructor_id=constructor.id,
                    grid=int(res.get("grid", 0)),
                    position=int(res["position"]) if res.get("position", "").isdigit() else None,
                    points=float(res.get("points", 0)),
                    laps=int(res.get("laps", 0)),
                    status=res.get("status"),
                ))
            await session.commit()

        print(f"✅ Season {season} done")

async def seed_pitstops(session, client):
    for season in SEASONS:
        print(f"Seeding pit stops for {season}...")
        races_result = await session.execute(select(Race).where(Race.season == season))
        races = races_result.scalars().all()

        for race in races:
            data = await fetch(client, f"{BASE_URL}/{season}/{race.round}/pitstops.json?limit=100")
            stops = data["MRData"]["RaceTable"]["Races"]
            if not stops:
                continue

            for stop in stops[0].get("PitStops", []):
                driver_result = await session.execute(
                    select(Driver).where(Driver.code == stop["driverId"].upper()[:3])
                )
                driver = driver_result.scalar_one_or_none()
                if not driver:
                    continue

                try:
                    parts = stop["duration"].split(":")
                    duration = float(parts[-1]) + (float(parts[-2]) * 60 if len(parts) > 1 else 0)
                except:
                    duration = None

                session.add(PitStop(
                    race_id=race.id,
                    driver_id=driver.id,
                    stop_number=int(stop["stop"]),
                    lap=int(stop["lap"]),
                    duration_seconds=duration
                ))
            await session.commit()
        print(f"✅ Pit stops {season} done")

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        async with httpx.AsyncClient() as client:
            await seed_circuits(session, client)
            await seed_constructors(session, client)
            await seed_drivers(session, client)
            await seed_races_and_results(session, client)
            await seed_pitstops(session, client)

    print("\n🏁 All seeding complete!")

if __name__ == "__main__":
    asyncio.run(main())