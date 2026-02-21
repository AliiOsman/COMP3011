from fastapi import APIRouter

router = APIRouter()

@router.get("/health")
async def strategy_health():
    return {"status": "strategy router active"}