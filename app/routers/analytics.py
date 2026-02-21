from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def analytics_health():
    return {"status": "analytics router active"}