#!/usr/bin/env python3
"""
Initialize the secure testing database with tables and test users.
"""
import os
import sys
from sqlalchemy.orm import Session

# Add current directory to path for imports
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from database import engine, get_db
from database_models import Base, User
from auth import init_test_users

def init_database():
    """Initialize database tables and test users."""
    print("🔧 Initializing secure testing database...")
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")
    
    # Initialize test users
    db = next(get_db())
    try:
        users = init_test_users(db)
        print(f"✅ Test users created: {list(users.keys())}")
        print(f"   - Admin: username='admin', password='admin123'")
        print(f"   - User: username='testuser', password='test123'")
    except Exception as e:
        print(f"❌ Error creating test users: {e}")
    finally:
        db.close()
    
    print("🎉 Secure testing database initialization complete!")

if __name__ == "__main__":
    init_database()
