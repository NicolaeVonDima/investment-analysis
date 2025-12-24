"""
Authentication routes: register, login, logout, refresh, me.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from fastapi.security import HTTPBearer
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import UserModel, UserSessionModel
from app.schemas import UserRegister, UserLogin, TokenResponse, UserResponse
from app.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    verify_token,
    get_current_user,
    hash_refresh_token,
    verify_refresh_token_hash,
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_DAYS
)

router = APIRouter(prefix="/api/auth", tags=["auth"])
security = HTTPBearer()


class RefreshTokenRequest(BaseModel):
    refresh_token: str


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserRegister,
    db: Session = Depends(get_db)
):
    """Register a new user."""
    # Check if email already exists
    existing_user = db.query(UserModel).filter(UserModel.email == user_data.email.lower()).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Create new user
    user = UserModel(
        email=user_data.email.lower(),
        password_hash=get_password_hash(user_data.password),
        first_name=user_data.first_name,
        last_name=user_data.last_name,
        role='freemium',
        is_primary_account=True
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return UserResponse(
        id=str(user.id),
        email=user.email,
        email_verified=user.email_verified,
        first_name=user.first_name,
        last_name=user.last_name,
        role=user.role,
        subscription_tier=user.subscription_tier,
        subscription_expires_at=user.subscription_expires_at,
        is_primary_account=user.is_primary_account,
        created_at=user.created_at
    )


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserLogin,
    db: Session = Depends(get_db)
):
    """Login and get access/refresh tokens."""
    # Find user by email
    user = db.query(UserModel).filter(UserModel.email == credentials.email.lower()).first()
    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )
    
    # Update last login
    user.last_login_at = datetime.now(timezone.utc)
    db.commit()
    
    # Create tokens
    access_token = create_access_token(data={"sub": str(user.id)})
    refresh_token = create_refresh_token(data={"sub": str(user.id)})
    
    # Store refresh token in database
    refresh_token_hash = hash_refresh_token(refresh_token)
    expires_at = datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    
    session = UserSessionModel(
        user_id=user.id,
        refresh_token_hash=refresh_token_hash,
        expires_at=expires_at
    )
    db.add(session)
    db.commit()
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """Refresh access token using refresh token."""
    refresh_token = request.refresh_token
    
    # Verify refresh token
    try:
        payload = verify_token(refresh_token, "refresh")
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
        
        # Find user
        user = db.query(UserModel).filter(UserModel.id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found"
            )
        
        # Find and verify session
        sessions = db.query(UserSessionModel).filter(
            UserSessionModel.user_id == user.id,
            UserSessionModel.expires_at > datetime.now(timezone.utc)
        ).all()
        
        session_found = False
        for session in sessions:
            if verify_refresh_token_hash(refresh_token, session.refresh_token_hash):
                session_found = True
                break
        
        if not session_found:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Create new access token
        new_access_token = create_access_token(data={"sub": str(user.id)})
        
        return TokenResponse(
            access_token=new_access_token,
            refresh_token=refresh_token  # Return same refresh token
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not refresh token"
        )


@router.post("/logout")
async def logout(
    current_user: UserModel = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Logout and invalidate refresh tokens."""
    # Delete all sessions for this user
    db.query(UserSessionModel).filter(UserSessionModel.user_id == current_user.id).delete()
    db.commit()
    
    return {"message": "Logged out successfully"}


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserModel = Depends(get_current_user)
):
    """Get current user information."""
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        email_verified=current_user.email_verified,
        first_name=current_user.first_name,
        last_name=current_user.last_name,
        role=current_user.role,
        subscription_tier=current_user.subscription_tier,
        subscription_expires_at=current_user.subscription_expires_at,
        is_primary_account=current_user.is_primary_account,
        created_at=current_user.created_at
    )
