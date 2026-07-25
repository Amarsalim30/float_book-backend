"""
Authentication service layer.

Business logic for user registration, login, and current-user retrieval.
All database interactions are delegated to ``user_repository``.
"""
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password, create_access_token
from app.repositories import user_repository
from app.schemas.auth import UserCreate, LoginRequest, TokenResponse, UserResponse


def register(db: Session, request: UserCreate) -> UserResponse:
    """
    Register a new user.

    Args:
        db: Active database session.
        request: Validated ``UserCreate`` payload (email already normalised).

    Returns:
        The newly created ``User`` ORM instance (Pydantic serialises it).

    Raises:
        HTTPException(400): If the e-mail address is already registered.
    """
    existing = user_repository.get_by_email(db, request.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email address already exists.",
        )

    hashed_pw = get_password_hash(request.password)
    user = user_repository.create(db, request.email, hashed_pw, request.full_name)
    return user


def login(db: Session, request: LoginRequest) -> TokenResponse:
    """
    Authenticate a user and issue a JWT access token.

    Args:
        db: Active database session.
        request: ``LoginRequest`` with ``email`` and ``password``.

    Returns:
        ``TokenResponse`` containing the signed JWT and token type.

    Raises:
        HTTPException(401): If the user does not exist or the password
            is incorrect. A generic message is used deliberately to prevent
            user enumeration attacks.
    """
    user = user_repository.get_by_email(db, request.email)

    # Use a constant-time generic message for both "not found" and "wrong password"
    # to prevent user enumeration.
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account has been deactivated. Please contact support.",
        )

    access_token = create_access_token(data={"sub": str(user.id)})
    return TokenResponse(access_token=access_token)
