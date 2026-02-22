from fastapi import FastAPI
from app.database import engine, Base
from app.routers import drivers, races, pitstops, strategy, analytics, auth
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import app.models  # ensures all models are registered with Base

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="F1 Strategic Intelligence API",
    description="A professional API for F1 race strategy analysis and prediction",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.include_router(auth.router, prefix="/api/v1/auth", tags=["Authentication"])
app.include_router(drivers.router, prefix="/api/v1/drivers", tags=["Drivers"])
app.include_router(races.router, prefix="/api/v1/races", tags=["Races"])
app.include_router(pitstops.router, prefix="/api/v1/pitstops", tags=["Pit Stops"])
app.include_router(strategy.router, prefix="/api/v1/strategy", tags=["Strategy Intelligence"])
app.include_router(analytics.router, prefix="/api/v1/analytics", tags=["Analytics"])

@app.on_event("startup")
async def startup():
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        print("✅ Database connected and tables created")
    except Exception as e:
        print(f"⚠️ Database connection failed: {e}")

@app.get("/")
async def root():
    return {"message": "F1 Strategic Intelligence API", "version": "1.0.0", "docs": "/docs"}