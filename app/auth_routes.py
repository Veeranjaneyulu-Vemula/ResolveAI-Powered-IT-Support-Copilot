from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import (
    authentication_error,
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, Token, UserCreate, UserResponse


router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
def register_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
) -> User:
    email = str(user_data.email).lower()
    username = user_data.username.lower()

    email_exists = db.scalars(
        select(User).where(User.email == email)
    ).first()
    if email_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already registered",
        )

    username_exists = db.scalars(
        select(User).where(User.username == username)
    ).first()
    if username_exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username already registered",
        )

    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(user_data.password),
    )

    try:
        db.add(user)
        db.commit()
    except IntegrityError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email or username already registered",
        ) from error
    except SQLAlchemyError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not register user",
        ) from error

    db.refresh(user)
    return user


@router.post("/login", response_model=Token)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db),
) -> Token:
    identifier = login_data.identifier.lower()
    statement = select(User).where(
        or_(User.email == identifier, User.username == identifier)
    )
    user = db.scalars(statement).first()

    if (
        user is None
        or not user.is_active
        or not verify_password(login_data.password, user.hashed_password)
    ):
        raise authentication_error()

    return Token(access_token=create_access_token(user.id))


@router.get("/me", response_model=UserResponse)
def get_authenticated_user(
    current_user: User = Depends(get_current_user),
) -> User:
    return current_user
