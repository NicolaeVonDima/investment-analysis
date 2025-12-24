"""
Script to create a user and migrate existing data to that user.
"""
import sys
import os
from datetime import datetime, timezone

# Add the app directory to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.database import SessionLocal, init_db
from app.models import UserModel, PortfolioModel, FamilyMemberModel
from passlib.context import CryptContext

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    """Hash a password."""
    return pwd_context.hash(password)

def create_user_and_migrate():
    """Create a user and migrate existing portfolios and family members to that user."""
    db = SessionLocal()
    
    try:
        # Initialize database (creates tables if they don't exist)
        init_db()
        
        # Create a user
        email = "user@example.com"
        password = "password123"  # Change this to a secure password
        
        # Check if user already exists
        existing_user = db.query(UserModel).filter(UserModel.email == email).first()
        if existing_user:
            print(f"User {email} already exists. Using existing user.")
            user = existing_user
        else:
            user = UserModel(
                email=email,
                password_hash=get_password_hash(password),
                first_name="Demo",
                last_name="User",
                role='freemium',
                is_primary_account=True
            )
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"Created user: {email}")
        
        # Migrate portfolios
        portfolios = db.query(PortfolioModel).filter(PortfolioModel.user_id.is_(None)).all()
        if portfolios:
            for portfolio in portfolios:
                portfolio.user_id = user.id
            db.commit()
            print(f"Migrated {len(portfolios)} portfolios to user {email}")
        else:
            print("No portfolios to migrate")
        
        # Migrate family members
        family_members = db.query(FamilyMemberModel).filter(FamilyMemberModel.user_id.is_(None)).all()
        if family_members:
            for member in family_members:
                member.user_id = user.id
            db.commit()
            print(f"Migrated {len(family_members)} family members to user {email}")
        else:
            print("No family members to migrate")
        
        print("\n" + "="*50)
        print("LOGIN CREDENTIALS:")
        print("="*50)
        print(f"Email: {email}")
        print(f"Password: {password}")
        print("="*50)
        print("\nYou can now login with these credentials at http://localhost:3005/login")
        
    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()

if __name__ == "__main__":
    create_user_and_migrate()

