from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_drivers():
    return {"drivers": []}