from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.core.security import hash_password, verify_password, create_access_token, decode_token
from app.repositories import user_repository
from app.schemas.auth import UserCreate, LoginRequest, TokenResponse, UserResponse


def register(db: Session, request: UserCreate) -> UserResponse:
    existing_user = user_repository.get_by_email(db, request.email)
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    hashed_password = hash_password(request.password)
    user = user_repository.create(db, request.email, hashed_password, request.full_name)
    
    return user


def login(db: Session, request: LoginRequest) -> TokenResponse:
    user = user_repository.get_by_email(db, request.email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    if not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    access_token = create_access_token(data={"sub": str(user.id)})
    
    return TokenResponse(access_token=access_token)


def get_current_user(db: Session, token: str):
    if not token:
        return None
    
    payload = decode_token(token)
    if not payload:
        return None
    
    user_id = payload.get("sub")
    if not user_id:
        return None
    
    return user_repository.get_by_id(db, int(user_id))
