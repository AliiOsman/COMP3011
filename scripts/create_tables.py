import asyncio
from app.database import engine, Base
from app.models import driver, race, result, pitstop, stint, constructor

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Tables created.")

asyncio.run(main())