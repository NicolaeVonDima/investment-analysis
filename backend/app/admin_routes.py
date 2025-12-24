"""
Admin routes for user management.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel

from app.database import get_db
from app.models import UserModel
from app.auth import get_current_admin_user
from app.schemas import UserResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])


class UserUpdateRequest(BaseModel):
    email: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: Optional[str] = None
    subscription_tier: Optional[str] = None


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    admin_user: UserModel = Depends(get_current_admin_user)
):
    """List all users (admin only)."""
    users = db.query(UserModel).offset(skip).limit(limit).all()
    return [
        UserResponse(
            id=str(u.id),
            email=u.email,
            email_verified=u.email_verified,
            first_name=u.first_name,
            last_name=u.last_name,
            role=u.role,
            subscription_tier=u.subscription_tier,
            subscription_expires_at=u.subscription_expires_at,
            is_primary_account=u.is_primary_account,
            created_at=u.created_at
        )
        for u in users
    ]


@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin_user: UserModel = Depends(get_current_admin_user)
):
    """Get user details (admin only)."""
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
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


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdateRequest,
    db: Session = Depends(get_db),
    admin_user: UserModel = Depends(get_current_admin_user)
):
    """Update user (admin only)."""
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from removing their own admin role
    if str(user.id) == str(admin_user.id) and user_data.role and user_data.role != 'admin':
        raise HTTPException(
            status_code=400,
            detail="Cannot remove your own admin role"
        )
    
    # Validate role
    if user_data.role and user_data.role not in ['freemium', 'paid', 'admin']:
        raise HTTPException(
            status_code=400,
            detail="Invalid role. Must be 'freemium', 'paid', or 'admin'"
        )
    
    # Update fields
    if user_data.email is not None:
        # Check if email is already taken by another user
        existing = db.query(UserModel).filter(
            UserModel.email == user_data.email.lower(),
            UserModel.id != user_id
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="Email already in use")
        user.email = user_data.email.lower()
    
    if user_data.first_name is not None:
        user.first_name = user_data.first_name
    if user_data.last_name is not None:
        user.last_name = user_data.last_name
    if user_data.role is not None:
        user.role = user_data.role
    if user_data.subscription_tier is not None:
        user.subscription_tier = user_data.subscription_tier
    
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


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    admin_user: UserModel = Depends(get_current_admin_user)
):
    """Delete user (admin only)."""
    user = db.query(UserModel).filter(UserModel.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Prevent admin from deleting themselves
    if str(user.id) == str(admin_user.id):
        raise HTTPException(
            status_code=400,
            detail="Cannot delete your own account"
        )
    
    db.delete(user)
    db.commit()
    
    return {"message": "User deleted successfully"}


@router.get("/stats")
async def get_stats(
    db: Session = Depends(get_db),
    admin_user: UserModel = Depends(get_current_admin_user)
):
    """Get platform statistics (admin only)."""
    total_users = db.query(UserModel).count()
    freemium_users = db.query(UserModel).filter(UserModel.role == 'freemium').count()
    paid_users = db.query(UserModel).filter(UserModel.role == 'paid').count()
    admin_users = db.query(UserModel).filter(UserModel.role == 'admin').count()
    
    return {
        "total_users": total_users,
        "freemium_users": freemium_users,
        "paid_users": paid_users,
        "admin_users": admin_users
    }

