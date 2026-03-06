from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    verify_password,
)
from app.db.session import get_db
from app.models.user import JobTitleCatalog, RegistrationRequest, RegistrationRequestStatus, RestaurantCatalog, User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.user import RegistrationRequestPublic, UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegistrationRequestPublic, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    desired_login = payload.desired_login.strip().lower()
    existing = db.scalar(select(User).where(User.email == desired_login))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login is already used")

    existing_pending = db.scalar(
        select(RegistrationRequest).where(
            RegistrationRequest.desired_login == desired_login,
            RegistrationRequest.status == RegistrationRequestStatus.PENDING,
        )
    )
    if existing_pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request already pending")

    restaurant = db.scalar(
        select(RestaurantCatalog).where(func.lower(RestaurantCatalog.name) == payload.restaurant.strip().lower())
    )
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ресторан не найден в справочнике")

    job_title = db.scalar(
        select(JobTitleCatalog).where(
            JobTitleCatalog.restaurant_id == restaurant.id,
            func.lower(JobTitleCatalog.name) == payload.job_title.strip().lower(),
        )
    )
    if not job_title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Роль не найдена для выбранного ресторана")

    req = RegistrationRequest(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        restaurant=restaurant.name,
        desired_job_title=job_title.name,
        desired_login=desired_login,
        desired_password_hash=get_password_hash(payload.password),
        status=RegistrationRequestStatus.PENDING,
    )
    db.add(req)
    db.commit()
    db.refresh(req)
    return req


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.login.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect login or password")

    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id), user.role.value),
    )


@router.post("/refresh", response_model=TokenPair)
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    try:
        decoded = decode_token(payload.refresh_token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    if decoded.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")

    subject = decoded.get("sub")
    if not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token payload")

    user = db.get(User, UUID(subject))
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive or missing user")

    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id), user.role.value),
    )


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return current_user
