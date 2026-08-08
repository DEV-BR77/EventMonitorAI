from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import (
    CurrentUser,
    create_token,
    hash_password,
    require_roles,
    verify_password,
)
from app.database.session import get_db
from app.models.dashboard import User
from app.schemas.dashboard import LoginRequest, TokenResponse, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["Authentication"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("/bootstrap", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def bootstrap(data: LoginRequest, db: DatabaseSession) -> TokenResponse:
    if db.scalar(select(func.count(User.id))) != 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already initialized")
    if len(data.password) < 10:
        raise HTTPException(status_code=422, detail="Password must contain at least 10 characters")
    user = User(username=data.username, password_hash=hash_password(data.password), role="admin")
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_token(user), role=user.role, username=user.username)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: DatabaseSession) -> TokenResponse:
    user = db.scalar(select(User).where(User.username == data.username))
    if user is None or not user.active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return TokenResponse(access_token=create_token(user), role=user.role, username=user.username)


@router.get("/me", response_model=UserRead)
def me(user: CurrentUser) -> User:
    return user


@router.get("/users", response_model=list[UserRead])
def users(
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.username)).all())


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> User:
    if db.scalar(select(User).where(User.username == data.username)):
        raise HTTPException(status_code=409, detail="Username already exists")
    if len(data.password) < 10:
        raise HTTPException(status_code=422, detail="Password must contain at least 10 characters")
    user = User(username=data.username, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
