import os
os.environ["TESTING"] = "true"

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)

async def override_get_db():
    async with TestSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(scope="session")
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(setup_database):
    """Function-scoped client — used by all tests"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def _session_http_client(setup_database):
    """Session-scoped client used ONLY for auth token creation"""
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac


@pytest_asyncio.fixture(scope="session")
async def auth_headers(_session_http_client):
    """Admin JWT — created ONCE for the whole test session"""
    await _session_http_client.post("/api/v1/auth/register", json={
        "username": "testadmin",
        "password": "testpass123",
        "role": "admin"
    })
    response = await _session_http_client.post(
        "/api/v1/auth/token",
        data={"username": "testadmin", "password": "testpass123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture(scope="session")
async def reader_headers(_session_http_client):
    """Reader JWT — created ONCE for the whole test session"""
    await _session_http_client.post("/api/v1/auth/register", json={
        "username": "testreader",
        "password": "testpass123",
        "role": "reader"
    })
    response = await _session_http_client.post(
        "/api/v1/auth/token",
        data={"username": "testreader", "password": "testpass123"}
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def sample_driver(client, auth_headers):
    response = await client.post(
        "/api/v1/drivers/",
        json={
            "forename": "Lewis",
            "surname": "Hamilton",
            "nationality": "British",
            "code": "HAM",
            "career_points": 4639.5
        },
        headers=auth_headers
    )
    return response.json()


@pytest_asyncio.fixture
async def sample_circuit(setup_database):
    async with TestSessionLocal() as session:
        from app.models.circuit import Circuit
        circuit = Circuit(
            ergast_id="silverstone",
            name="Silverstone Circuit",
            country="United Kingdom",
            city="Silverstone",
            lat=52.0786,
            lng=-1.0169
        )
        session.add(circuit)
        await session.commit()
        await session.refresh(circuit)
        return circuit


@pytest_asyncio.fixture
async def sample_race(setup_database, sample_circuit):
    async with TestSessionLocal() as session:
        from app.models.race import Race
        race = Race(
            ergast_id=99001,
            season=2023,
            round=10,
            name="British Grand Prix",
            date="2023-07-09",
            circuit_id=sample_circuit.id
        )
        session.add(race)
        await session.commit()
        await session.refresh(race)
        return race