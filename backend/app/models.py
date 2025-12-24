"""
Database models for portfolios and scenarios.
"""

from sqlalchemy import Column, Integer, String, Float, Boolean, JSON, DateTime, func, ForeignKey, Index
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
import uuid
from app.database import Base


class UserModel(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    email_verified = Column(Boolean, default=False, nullable=False)
    password_hash = Column(String(255), nullable=False)
    
    # Profile
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    avatar_url = Column(String(500), nullable=True)
    
    # Subscription
    role = Column(String(20), nullable=False, default='freemium')  # 'freemium', 'paid', 'admin'
    subscription_tier = Column(String(50), nullable=True)  # 'basic', 'premium', 'enterprise'
    subscription_expires_at = Column(DateTime(timezone=True), nullable=True)
    
    # Hierarchy
    parent_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    is_primary_account = Column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    sessions = relationship("UserSessionModel", back_populates="user", cascade="all, delete-orphan")
    portfolios = relationship("PortfolioModel", back_populates="user", cascade="all, delete-orphan")
    family_members = relationship("FamilyMemberModel", back_populates="user", foreign_keys="FamilyMemberModel.user_id", cascade="all, delete-orphan")


class UserSessionModel(Base):
    __tablename__ = "user_sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    refresh_token_hash = Column(String(255), nullable=False, index=True)
    device_info = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 max length
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user = relationship("UserModel", back_populates="sessions")


class UserInvitationModel(Base):
    __tablename__ = "user_invitations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    inviter_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    invitee_email = Column(String(255), nullable=False, index=True)
    family_member_id = Column(String(100), nullable=True)  # Links to FamilyMember.id
    
    status = Column(String(20), default='pending', nullable=False)  # 'pending', 'accepted', 'declined', 'expired'
    invitation_token = Column(String(255), unique=True, nullable=False, index=True)
    
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    inviter = relationship("UserModel", foreign_keys=[inviter_user_id])


class PortfolioModel(Base):
    __tablename__ = "portfolios"

    id = Column(String, primary_key=True, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)  # Nullable for migration
    name = Column(String, nullable=False)
    color = Column(String, nullable=False)
    capital = Column(Float, nullable=False)
    goal = Column(String, nullable=True)
    risk_label = Column(String, nullable=True)  # e.g., "Risk: Medium"
    horizon = Column(String, nullable=True)  # e.g., "2026 - 2029"
    selected_strategy = Column(String, nullable=True)  # For custom portfolios: "Aggressive Growth", "Balanced Allocation", or "Income Focused"
    overperform_strategy = Column(JSON, nullable=True)  # {title, content: []}
    allocation = Column(JSON, nullable=False)  # {vwce, tvbetetf, ernx, ayeg, fidelis}
    # member_allocations removed - we now use per-member portfolios instead
    rules = Column(JSON, nullable=False)  # {tvbetetfConditional}
    strategy = Column(JSON, nullable=True)  # {overperformanceStrategy, overperformanceThreshold}
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("UserModel", back_populates="portfolios")


class ScenarioModel(Base):
    __tablename__ = "scenarios"

    id = Column(String, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True, index=True)
    inflation = Column(Float, nullable=False)  # International inflation
    romanian_inflation = Column(Float, nullable=True, default=0.08)  # Romanian inflation (default 8%)
    growth_cushion = Column(Float, nullable=True, default=0.02)  # Real growth cushion (e.g., 0.02 = 2%)
    tax_on_sale_proceeds = Column(Float, nullable=True)  # Tax rate on capital gains (e.g., 0.10 = 10%)
    tax_on_dividends = Column(Float, nullable=True)  # Tax rate on dividends/yield (e.g., 0.05 = 5%)
    asset_returns = Column(JSON, nullable=False)  # {vwce, tvbetetf, ernx, ernxYield, ayeg, ayegYield, fidelis}
    trim_rules = Column(JSON, nullable=False)  # {vwce: {enabled, threshold}, ...}
    fidelis_cap = Column(Float, nullable=False)
    is_default = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class FamilyMemberModel(Base):
    __tablename__ = "family_members"

    id = Column(String, primary_key=True, index=True)  # UUID
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=True, index=True)  # Nullable for migration
    linked_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True)  # If invited & accepted
    email = Column(String(255), nullable=True)
    color = Column(String(20), nullable=True)
    name = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    user = relationship("UserModel", back_populates="family_members", foreign_keys=[user_id], remote_side="UserModel.id")

