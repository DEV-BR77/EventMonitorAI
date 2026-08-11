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
from app.models.dashboard import Tenant, TenantMembership, TenantSubscription, User
from app.schemas.dashboard import LoginRequest, TokenResponse, UserCreate, UserRead, UserUpdate
from app.services.login_guard import clear_failures, record_failure, retry_after

router = APIRouter(prefix="/auth", tags=["Authentication"])
DatabaseSession = Annotated[Session, Depends(get_db)]


@router.post("/bootstrap", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def bootstrap(data: LoginRequest, db: DatabaseSession) -> TokenResponse:
    if db.scalar(select(func.count(User.id))) != 0:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already initialized")
    if len(data.password) < 10:
        raise HTTPException(status_code=422, detail="Password must contain at least 10 characters")
    user = User(username=data.username, password_hash=hash_password(data.password), role="admin")
    tenant = db.get(Tenant, 1) or Tenant(id=1, name="EventMonitorAI", slug="eventmonitorai")
    db.add_all([tenant, user])
    db.flush()
    db.add(TenantMembership(tenant_id=tenant.id, user_id=user.id, role="admin"))
    if db.scalar(select(TenantSubscription).where(TenantSubscription.tenant_id == tenant.id)) is None:
        db.add(TenantSubscription(tenant_id=tenant.id, plan="self_hosted", status="active", max_devices=10))
    db.commit()
    db.refresh(user)
    return TokenResponse(access_token=create_token(user, tenant.id, "admin"), role="admin", username=user.username, tenant_id=tenant.id, tenant_name=tenant.name)


@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest, db: DatabaseSession) -> TokenResponse:
    wait = retry_after(data.username)
    if wait:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Zu viele fehlgeschlagene Anmeldeversuche. Bitte später erneut versuchen.",
            headers={"Retry-After": str(wait)},
        )
    normalized_username = data.username.strip().casefold()
    user = db.scalar(select(User).where(func.lower(User.username) == normalized_username))
    if user is None or not user.active or not verify_password(data.password, user.password_hash):
        record_failure(data.username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Benutzername oder Passwort ist ungültig",
        )
    clear_failures(data.username)
    membership = db.scalar(select(TenantMembership).where(TenantMembership.user_id == user.id, TenantMembership.active.is_(True)).order_by(TenantMembership.id))
    if membership is None:
        tenant = db.get(Tenant, 1) or Tenant(id=1, name="EventMonitorAI", slug="eventmonitorai")
        db.add(tenant)
        db.flush()
        membership = TenantMembership(tenant_id=tenant.id, user_id=user.id, role=user.role)
        db.add(membership)
        if db.scalar(select(TenantSubscription).where(TenantSubscription.tenant_id == tenant.id)) is None:
            db.add(TenantSubscription(tenant_id=tenant.id, plan="self_hosted", status="active", max_devices=10))
        db.commit()
    tenant = db.get(Tenant, membership.tenant_id)
    if tenant is None or not tenant.active:
        raise HTTPException(status_code=403, detail="Kundenbereich ist deaktiviert")
    return TokenResponse(access_token=create_token(user, tenant.id, membership.role), role=membership.role, username=user.username, tenant_id=tenant.id, tenant_name=tenant.name)


@router.get("/me")
def me(user: CurrentUser, db: DatabaseSession) -> dict[str, object]:
    tenant_id = db.info["tenant_id"]
    tenant = db.get(Tenant, tenant_id)
    return {"id": user.id, "username": user.username, "role": db.info["tenant_role"], "active": user.active, "created_at": user.created_at, "tenant_id": tenant_id, "tenant_name": tenant.name}


@router.get("/users", response_model=list[UserRead])
def users(
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> list[User]:
    return list(db.scalars(select(User).join(TenantMembership, TenantMembership.user_id == User.id).where(TenantMembership.tenant_id == db.info["tenant_id"], TenantMembership.active.is_(True)).order_by(User.username)).all())


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    data: UserCreate,
    db: DatabaseSession,
    _: Annotated[User, Depends(require_roles("admin"))],
) -> User:
    username = data.username.strip()
    if db.scalar(select(User).where(func.lower(User.username) == username.casefold())):
        raise HTTPException(status_code=409, detail="Username already exists")
    if len(data.password) < 10:
        raise HTTPException(status_code=422, detail="Password must contain at least 10 characters")
    user = User(username=username, password_hash=hash_password(data.password), role=data.role)
    db.add(user)
    db.flush()
    db.add(TenantMembership(tenant_id=db.info["tenant_id"], user_id=user.id, role=data.role))
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserRead)
def update_user(
    user_id: int,
    data: UserUpdate,
    db: DatabaseSession,
    current_user: Annotated[User, Depends(require_roles("admin"))],
) -> User:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Benutzer nicht gefunden")
    if user.id == current_user.id and (not data.active or data.role != "admin"):
        raise HTTPException(
            status_code=409,
            detail="Das eigene Administratorkonto kann nicht deaktiviert oder herabgestuft werden",
        )
    user.role = data.role
    user.active = data.active
    if data.password:
        user.password_hash = hash_password(data.password)
        clear_failures(user.username)
    tenant_id = db.info.get("tenant_id")
    if tenant_id is not None:
        membership = db.scalar(select(TenantMembership).where(TenantMembership.tenant_id == tenant_id, TenantMembership.user_id == user.id))
        if membership is None:
            raise HTTPException(status_code=404, detail="Benutzer gehört nicht zu diesem Kundenbereich")
        membership.role = data.role
        membership.active = data.active
    db.commit()
    db.refresh(user)
    return user
