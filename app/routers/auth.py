from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.database import get_db
from app.models.user import User
from app.middleware.auth import hash_password, verify_password, create_access_token
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)


class UserCreate(BaseModel):
    username: str
    password: str
    role: str = "reader"

class Token(BaseModel):
    access_token: str
    token_type: str

@router.post("/register", status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, data: UserCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Username already exists")
    user = User(
        username=data.username,
        hashed_password=hash_password(data.password),
        role=data.role
    )
    db.add(user)
    await db.commit()
    return {"message": f"User '{data.username}' created with role '{data.role}'"}

@router.post("/token", response_model=Token)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).where(User.username == form_data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    token = create_access_token({"sub": user.username, "role": user.role})
    return {"access_token": token, "token_type": "bearer"}

@router.get("/me")
async def get_me(db: AsyncSession = Depends(get_db),
                 token: str = Depends(lambda: None)):
    return {"message": "Use Bearer token to authenticate"}