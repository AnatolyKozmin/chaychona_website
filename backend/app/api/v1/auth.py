from datetime import datetime
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
from app.models.user import (
    JobTitleCatalog,
    RegistrationRequest,
    RegistrationRequestStatus,
    RestaurantCatalog,
    Role,
    User,
)
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenPair
from app.schemas.user import UserPublic

router = APIRouter(prefix="/auth", tags=["auth"])


def _normalize_login(value: str) -> str:
    """Логин без пробелов по краям и без регистра.

    Автозамена на телефоне дописывает пробел после слова, а клавиатура делает
    первую букву заглавной — без нормализации человек «вводит тот же логин»
    и не может войти.
    """
    return value.strip().lower()


def _tokens_for(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(str(user.id), user.role.value),
        refresh_token=create_refresh_token(str(user.id), user.role.value),
    )


def _user_from_request(req: RegistrationRequest) -> User:
    return User(
        email=req.desired_login,
        full_name=f"{req.first_name} {req.last_name}",
        restaurant=req.restaurant,
        password_hash=req.desired_password_hash,
        role=Role.LEARNER,
        job_title=req.desired_job_title,
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    """Самостоятельная регистрация сотрудника: аккаунт создаётся сразу.

    Раньше каждую заявку одобрял суперадмин вручную, и при потоке новых
    сотрудников люди днями не могли войти. Заявку всё равно пишем — со статусом
    «одобрено» — чтобы в админке было видно, кто и когда зарегистрировался.
    """
    desired_login = _normalize_login(payload.desired_login)
    if db.scalar(select(User).where(User.email == desired_login)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Такой логин уже занят. Если это вы — войдите, а если нет — придумайте другой.",
        )

    restaurant = db.scalar(
        select(RestaurantCatalog).where(func.lower(RestaurantCatalog.name) == payload.restaurant.strip().lower())
    )
    if not restaurant:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Выберите ресторан из списка")

    job_title = db.scalar(
        select(JobTitleCatalog).where(
            JobTitleCatalog.restaurant_id == restaurant.id,
            func.lower(JobTitleCatalog.name) == payload.job_title.strip().lower(),
        )
    )
    if not job_title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Выберите должность из списка")

    # Старая заявка с тем же логином (до перехода на самостоятельную регистрацию)
    # не должна мешать: человек заполняет форму заново — значит, это он.
    for stale in db.scalars(
        select(RegistrationRequest).where(
            RegistrationRequest.desired_login == desired_login,
            RegistrationRequest.status == RegistrationRequestStatus.PENDING,
        )
    ).all():
        stale.status = RegistrationRequestStatus.REJECTED
        stale.rejection_reason = "Заменена новой регистрацией"
        stale.processed_at = datetime.utcnow()

    req = RegistrationRequest(
        first_name=payload.first_name.strip(),
        last_name=payload.last_name.strip(),
        restaurant=restaurant.name,
        desired_job_title=job_title.name,
        desired_login=desired_login,
        desired_password_hash=get_password_hash(payload.password),
        status=RegistrationRequestStatus.APPROVED,
        processed_at=datetime.utcnow(),
    )
    user = _user_from_request(req)
    db.add(req)
    db.add(user)
    db.commit()
    db.refresh(user)
    return _tokens_for(user)


@router.post("/login", response_model=TokenPair)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    login_value = _normalize_login(payload.login)
    user = db.scalar(select(User).where(User.email == login_value))

    if user is None:
        # Заявка, поданная до самостоятельной регистрации и так и не одобренная:
        # пароль совпал — значит, это её автор. Заводим аккаунт прямо сейчас,
        # а не отвечаем «неверный пароль», после которого человек регистрировался
        # заново под другим логином.
        pending = db.scalar(
            select(RegistrationRequest)
            .where(
                RegistrationRequest.desired_login == login_value,
                RegistrationRequest.status == RegistrationRequestStatus.PENDING,
            )
            .order_by(RegistrationRequest.created_at.desc())
        )
        if pending is not None and verify_password(payload.password, pending.desired_password_hash):
            user = _user_from_request(pending)
            pending.status = RegistrationRequestStatus.APPROVED
            pending.processed_at = datetime.utcnow()
            db.add(user)
            db.commit()
            db.refresh(user)
            return _tokens_for(user)

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверный логин или пароль")
    # Как и в /refresh и get_current_user: отключённый пользователь не должен получать токены,
    # иначе вход «проходит», но каждый следующий запрос отвечает 401.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Учётная запись отключена. Обратитесь к администратору.",
        )

    return _tokens_for(user)


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

    return _tokens_for(user)


@router.get("/me", response_model=UserPublic)
def me(current_user: User = Depends(get_current_user)):
    return current_user
