"""
Authentication API router.

Endpoints:
  POST /auth/register        — Create a new user account.
  POST /auth/login           — Authenticate via JSON body, return JWT.
  POST /auth/login/form      — OAuth2 form login (for Swagger UI compatibility).
  GET  /auth/me              — Return the authenticated user's profile.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.schemas.auth import UserCreate, UserResponse, LoginRequest, TokenResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def register(request: UserCreate, db: Session = Depends(get_db)) -> UserResponse:
    """
    Create a new user account.

    - **email**: valid e-mail address (normalised to lowercase)
    - **password**: minimum 8 characters
    - **full_name**: optional display name

    Returns the created user profile (without the password).
    Raises **400** if the e-mail address is already registered.
    """
    return auth_service.register(db, request)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with JSON body",
)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    """
    Authenticate using a JSON body and return a JWT access token.

    - **email**: registered e-mail address
    - **password**: account password

    Returns an access token of type **bearer**.
    Raises **401** on invalid credentials.
    """
    return auth_service.login(db, request)


@router.post(
    "/login/form",
    response_model=TokenResponse,
    summary="Login with OAuth2 form (Swagger UI)",
    include_in_schema=True,
)
def login_form(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
) -> TokenResponse:
    """
    OAuth2-compatible form login endpoint.

    Accepts `username` (treated as email) and `password` as form fields.
    This endpoint exists so Swagger UI's *Authorize* button works correctly.
    """
    # Reuse the JSON-body login service, mapping `username` → `email`
    login_request = LoginRequest(email=form_data.username, password=form_data.password)
    return auth_service.login(db, login_request)


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Return the profile of the currently authenticated user.

    Requires a valid **Bearer** token in the `Authorization` header.
    Raises **401** if the token is missing, invalid, or expired.
    """
    return current_user
