from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import List

from app.core.security import (
    verify_password, create_access_token, get_current_active_user, require_admin
)
from app.core import users as user_store
from app.core.limiter import limiter
from app.core.config import settings

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class Token(BaseModel):
    access_token: str
    token_type: str


class UserCreate(BaseModel):
    username: str
    password: str
    is_admin: bool = False


class UserInfo(BaseModel):
    username: str
    is_admin: bool
    is_active: bool


@router.post("/token", response_model=Token, summary="Login and get JWT token")
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    user = user_store.get_user(form_data.username)
    if not user or not verify_password(form_data.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token({"sub": user["username"]})
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserInfo, summary="Get current user info")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def read_me(request: Request, current_user=Depends(get_current_active_user)):
    return current_user


@router.get("/users", response_model=List[UserInfo], summary="List all users (admin only)")
@limiter.limit(settings.RATE_LIMIT_DEFAULT)
async def list_users(request: Request, _: dict = Depends(require_admin)):
    return user_store.list_users()


@router.post("/users", response_model=UserInfo, summary="Create user (admin only)")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def create_user(request: Request, data: UserCreate, _=Depends(require_admin)):
    if user_store.get_user(data.username):
        raise HTTPException(status_code=400, detail="Username already exists")
    return user_store.create_user(data.username, data.password, data.is_admin)


@router.delete("/users/{username}", summary="Delete user (admin only)")
@limiter.limit(settings.RATE_LIMIT_WRITE)
async def delete_user(request: Request, username: str, current_user=Depends(require_admin)):
    if username == current_user["username"]:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    if not user_store.delete_user(username):
        raise HTTPException(status_code=404, detail="User not found")
    return {"message": f"User '{username}' deleted"}
