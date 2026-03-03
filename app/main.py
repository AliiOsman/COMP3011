from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from app.database import engine, Base
from app.routers import drivers, races, pitstops, strategy, analytics, auth
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.middleware import SlowAPIMiddleware
from slowapi.errors import RateLimitExceeded
import app.models  # ensures all models are registered with Base
from contextlib import asynccontextmanager
from app.routers import mcp
from app.config import settings
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"], enabled=not settings.TESTING)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database connected and tables created")
    except Exception as e:
        print(f"⚠️ Database connection failed: {e}")

    yield  # <-- app runs here

    # Optional shutdown section (not required now)

app = FastAPI(
    lifespan=lifespan,
    title="F1 Strategic Intelligence API",
    description="""
    A RESTful API providing Formula 1 race strategy intelligence and analytics.
    """,
    contact={
        "name": "F1 Strategy API",
        "url": "https://github.com/AliiOsman/COMP3011"
    },
    license_info={
        "name": "MIT"
    },
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(drivers.router, prefix="/api/v1/drivers", tags=["Drivers"])
app.include_router(races.router, prefix="/api/v1/races", tags=["Races"])
app.include_router(pitstops.router, prefix="/api/v1/pitstops", tags=["Pit Stops"])
app.include_router(strategy.router, prefix="/api/v1/strategy", tags=["Strategy Intelligence"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])
app.include_router(mcp.router, prefix="/mcp", tags=["MCP"])

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Cache-Control"] = "no-store"
    return response

@app.middleware("http")
async def add_request_id(request: Request, call_next):
    import uuid
    request_id = str(uuid.uuid4())[:8]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

@app.get("/")
async def root():
    return {
        "name": "F1 Strategic Intelligence API",
        "version": "1.0.0",
        "description": "A RESTful API providing Formula 1 race strategy intelligence and analytics.",
        "features": [
            "CRUD Operations for drivers, races, and pit stops",
            "Strategy Intelligence — pit window calculator, tyre degradation models",
            "Constructor Elo Ratings — pairwise Elo system across all race results",
            "Wet Weather Scoring — normalised driver performance in wet conditions",
            "Pit Crew Analytics — constructor pit stop performance rankings",
            "Head-to-Head Rivalry Analyser — direct driver comparison across shared races",
            "MCP Compatible — structured for AI agent tool integration"
        ],
        "authentication": {
            "type": "JWT Bearer Token",
            "register": "/api/v1/auth/register",
            "login": "/api/v1/auth/token",
            "usage": "Include header: Authorization: Bearer <token>"
        },
        "endpoints": {
            "drivers": "/api/v1/drivers/",
            "races": "/api/v1/races/",
            "pitstops": "/api/v1/pitstops/",
            "strategy": {
                "pit_window": "/api/v1/strategy/pit-window/{race_id}/{driver_id}",
                "constructor_elo": "/api/v1/strategy/constructor-elo",
                "wet_weather": "/api/v1/strategy/wet-weather-scores",
                "tyre_model": "/api/v1/strategy/tyre-model/{circuit_id}/{compound}"
            },
            "analytics": {
                "pit_crew": "/api/v1/analytics/pit-crew-performance",
                "overtaking": "/api/v1/analytics/circuit-overtaking-difficulty",
                "driver_season": "/api/v1/analytics/driver-season-summary/{driver_id}",
                "head_to_head": "/api/v1/analytics/head-to-head/{driver_a_id}/{driver_b_id}",
                "tyre_degradation": "/api/v1/analytics/tyre-degradation"
            },
            "mcp": {
                "manifest": "/mcp/manifest",
                "health": "/mcp/health"
            },
            "docs": "/docs"
        },
        "data_sources": [
            "Kaggle F1 Historical Dataset (1950-2023)",
            "Jolpica/Ergast API (2024 season)",
            "OpenF1 API (live tyre and weather data 2023-2024)"
        ],
        "mcp_compatible": True,
        "status": "operational"
    }