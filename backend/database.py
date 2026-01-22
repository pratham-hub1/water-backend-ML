import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Use project root database path for production
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQLALCHEMY_DATABASE_URL = f"sqlite:///{os.path.join(PROJECT_ROOT, 'water_quality_secure.db')}"

# Configure secure database engine with enhanced settings
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, 
    poolclass=StaticPool,
    connect_args={
        "check_same_thread": False,
        "timeout": 60,
        "isolation_level": "EXCLUSIVE"  # Enhanced isolation for security
    },
    echo=False  # Disable SQL logging in production/testing
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    Dependency that provides a database session for use in FastAPI endpoints.
    Ensures the session is closed after use.
    Enhanced with security considerations.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    """
    Create all tables in the database based on the ORM models.
    Should be run once during setup or migration.
    """
    import database_models
    database_models.Base.metadata.create_all(bind=engine)

def get_db_path():
    """Returns the database file path for security verification."""
    return os.path.join(PROJECT_ROOT, 'water_quality_secure.db')
