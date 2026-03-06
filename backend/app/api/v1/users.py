from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.security import get_password_hash
from app.db.session import get_db
from app.models.user import (
    JobTitleCatalog,
    RegistrationRequest,
    RegistrationRequestStatus,
    RestaurantCatalog,
    Role,
    User,
)
from app.schemas.user import (
    CatalogItemCreate,
    CatalogItemPublic,
    CreateUserRequest,
    JobTitleCatalogItemCreate,
    JobTitleCatalogItemPublic,
    RegistrationRequestPublic,
    RestaurantWithRolesPublic,
    SetLearnerProfileRequest,
    SetJobTitleRequest,
    SetRoleRequest,
    UserPublic,
)

router = APIRouter(prefix="/users", tags=["users"])


def _resolve_learner_assignment(db: Session, restaurant_name: str, job_title_name: str) -> tuple[str, str]:
    restaurant = db.scalar(
        select(RestaurantCatalog).where(func.lower(RestaurantCatalog.name) == restaurant_name.strip().lower())
    )
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ресторан не найден в справочнике")

    job_title = db.scalar(
        select(JobTitleCatalog).where(
            JobTitleCatalog.restaurant_id == restaurant.id,
            func.lower(JobTitleCatalog.name) == job_title_name.strip().lower(),
        )
    )
    if not job_title:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Роль не найдена для выбранного ресторана",
        )

    return restaurant.name, job_title.name


@router.get("", response_model=list[UserPublic])
def list_users(
    _: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    return list(db.scalars(select(User).order_by(User.created_at.desc())).all())


@router.patch("/{user_id}/role", response_model=UserPublic)
def set_role(
    user_id: UUID,
    payload: SetRoleRequest,
    current_user: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if user.id == current_user.id and payload.role != Role.SUPERADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot change your own superadmin role",
        )

    if user.role == Role.SUPERADMIN and payload.role != Role.SUPERADMIN:
        superadmin_count = db.scalar(select(func.count(User.id)).where(User.role == Role.SUPERADMIN)) or 0
        if superadmin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one superadmin must remain in the system",
            )

    user.role = payload.role
    if user.role != Role.LEARNER:
        user.job_title = None
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/job-title", response_model=UserPublic)
def set_job_title(
    user_id: UUID,
    payload: SetJobTitleRequest,
    current_user: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user.role == Role.ADMIN and user.role in {Role.SUPERADMIN, Role.ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins can update learners only")

    if user.role != Role.LEARNER:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Job title is available for learners")

    user.job_title = payload.job_title
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}/learner-profile", response_model=UserPublic)
def set_learner_profile(
    user_id: UUID,
    payload: SetLearnerProfileRequest,
    current_user: User = Depends(require_roles(Role.SUPERADMIN, Role.ADMIN)),
    db: Session = Depends(get_db),
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    if current_user.role == Role.ADMIN and user.role in {Role.SUPERADMIN, Role.ADMIN}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins can update learners only")

    if user.role != Role.LEARNER:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Profile is editable for learners only")

    restaurant_name, job_title_name = _resolve_learner_assignment(db, payload.restaurant, payload.job_title)
    user.restaurant = restaurant_name
    user.job_title = job_title_name
    db.commit()
    db.refresh(user)
    return user


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: CreateUserRequest,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    login = payload.login.strip().lower()
    existing = db.scalar(select(User).where(User.email == login))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login is already used")

    restaurant_name: str | None = None
    job_title_name: str | None = None
    if payload.role == Role.LEARNER:
        if not payload.restaurant or not payload.job_title:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Для обучающегося нужно выбрать ресторан и роль",
            )
        restaurant_name, job_title_name = _resolve_learner_assignment(db, payload.restaurant, payload.job_title)

    user = User(
        email=login,
        full_name=f"{payload.first_name.strip()} {payload.last_name.strip()}",
        restaurant=restaurant_name if payload.role == Role.LEARNER else (payload.restaurant.strip() if payload.restaurant else None),
        password_hash=get_password_hash(payload.password),
        role=payload.role,
        job_title=job_title_name if payload.role == Role.LEARNER else None,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/registration-requests", response_model=list[RegistrationRequestPublic])
def list_registration_requests(
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    return list(
        db.scalars(
            select(RegistrationRequest).order_by(
                RegistrationRequest.status.asc(), RegistrationRequest.created_at.desc()
            )
        ).all()
    )


@router.post("/registration-requests/{request_id}/approve", response_model=UserPublic)
def approve_registration_request(
    request_id: UUID,
    current_user: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    req = db.get(RegistrationRequest, request_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req.status != RegistrationRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request is already processed")

    existing_user = db.scalar(select(User).where(User.email == req.desired_login))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Login is already used")

    new_user = User(
        email=req.desired_login,
        full_name=f"{req.first_name} {req.last_name}",
        restaurant=req.restaurant,
        password_hash=req.desired_password_hash,
        role=Role.LEARNER,
        job_title=req.desired_job_title,
    )
    db.add(new_user)

    req.status = RegistrationRequestStatus.APPROVED
    req.processed_at = datetime.utcnow()
    req.processed_by_user_id = current_user.id
    req.rejection_reason = None

    db.commit()
    db.refresh(new_user)
    return new_user


@router.post("/registration-requests/{request_id}/reject", response_model=RegistrationRequestPublic)
def reject_registration_request(
    request_id: UUID,
    current_user: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    req = db.get(RegistrationRequest, request_id)
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
    if req.status != RegistrationRequestStatus.PENDING:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Request is already processed")

    req.status = RegistrationRequestStatus.REJECTED
    req.processed_at = datetime.utcnow()
    req.processed_by_user_id = current_user.id
    req.rejection_reason = "Rejected by superadmin"
    db.commit()
    db.refresh(req)
    return req


@router.get("/catalog/restaurants", response_model=list[CatalogItemPublic])
def list_restaurants(
    db: Session = Depends(get_db),
):
    return list(db.scalars(select(RestaurantCatalog).order_by(RestaurantCatalog.name.asc())).all())


@router.post("/catalog/restaurants", response_model=CatalogItemPublic, status_code=status.HTTP_201_CREATED)
def create_restaurant(
    payload: CatalogItemCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    existing = db.scalar(select(RestaurantCatalog).where(RestaurantCatalog.name == name))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Ресторан уже существует")

    item = RestaurantCatalog(name=name)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/catalog/job-titles", response_model=list[CatalogItemPublic])
def list_job_titles(
    restaurant_id: UUID | None = None,
    db: Session = Depends(get_db),
):
    query = select(JobTitleCatalog).order_by(JobTitleCatalog.name.asc())
    if restaurant_id:
        query = query.where(JobTitleCatalog.restaurant_id == restaurant_id)
    return list(db.scalars(query).all())


@router.post("/catalog/job-titles", response_model=JobTitleCatalogItemPublic, status_code=status.HTTP_201_CREATED)
def create_job_title(
    payload: JobTitleCatalogItemCreate,
    _: User = Depends(require_roles(Role.SUPERADMIN)),
    db: Session = Depends(get_db),
):
    name = payload.name.strip()
    restaurant = db.get(RestaurantCatalog, payload.restaurant_id)
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ресторан не найден")

    existing = db.scalar(
        select(JobTitleCatalog).where(
            JobTitleCatalog.restaurant_id == payload.restaurant_id,
            func.lower(JobTitleCatalog.name) == name.lower(),
        )
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Такая роль уже существует в этом ресторане")

    item = JobTitleCatalog(name=name, restaurant_id=payload.restaurant_id)
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/catalog/restaurants-with-roles", response_model=list[RestaurantWithRolesPublic])
def list_restaurants_with_roles(
    db: Session = Depends(get_db),
):
    restaurants = list(db.scalars(select(RestaurantCatalog).order_by(RestaurantCatalog.name.asc())).all())
    job_titles = list(db.scalars(select(JobTitleCatalog).order_by(JobTitleCatalog.name.asc())).all())

    roles_by_restaurant: dict[UUID, list[CatalogItemPublic]] = {}
    for item in job_titles:
        if item.restaurant_id is None:
            continue
        roles_by_restaurant.setdefault(item.restaurant_id, []).append(CatalogItemPublic.model_validate(item))

    result: list[RestaurantWithRolesPublic] = []
    for restaurant in restaurants:
        result.append(
            RestaurantWithRolesPublic(
                id=restaurant.id,
                name=restaurant.name,
                roles=roles_by_restaurant.get(restaurant.id, []),
            )
        )
    return result
