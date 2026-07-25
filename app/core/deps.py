"""
FastAPI dependencies for authentication and authorization.

Provides the `get_current_user` dependency which extracts the Bearer token
from the Authorization header, validates it, and returns the current user.
Raises HTTP 401 if the token is missing, invalid, or expired.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import decode_token
from app.repositories import user_repository
from app.models.user import User

# tokenUrl tells Swagger UI where to POST credentials to obtain a token
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login/form")


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Validate the Bearer JWT token and return the authenticated user.

    Raises HTTP 401 UNAUTHORIZED with WWW-Authenticate: Bearer header
    if the token is missing, malformed, expired, or the user no longer exists.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if user_id is None:
        raise credentials_exception

    try:
        uid = int(user_id)
    except (ValueError, TypeError):
        raise credentials_exception

    user = user_repository.get_by_id(db, uid)
    if user is None:
        raise credentials_exception

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive user account",
        )

    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Alias dependency that explicitly requires an active user."""
    return current_user
