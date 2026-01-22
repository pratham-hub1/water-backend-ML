from sqlalchemy import Column, Integer, Float, Boolean, DateTime, String
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

Base = declarative_base()

class SensorReading(Base):
    """
    ORM model for a sensor reading record. Fields match to DB columns exactly.
    Enhanced with security considerations for testing environment.
    """
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    tds = Column(Float, nullable=True, comment="Total Dissolved Solids in ppm")
    turbidity = Column(Float, nullable=True, comment="Turbidity in NTU")
    leak = Column(Boolean, nullable=True, comment="Water leak detection status")
    ph_value = Column(Float, nullable=True, comment="pH sensor reading (0-14)")
    ph_status_msg = Column(String(50), nullable=True, comment="pH status message")
    predicted_class = Column(Integer, nullable=False)
    is_safe = Column(Boolean, nullable=False)
    needs_replacement = Column(Boolean, nullable=False)
    filter_health_score = Column(Integer, nullable=True, comment="Filter health score (0-100)")
    anomaly_detected = Column(Boolean, default=False, nullable=True)
    anomaly_cause = Column(String(100), nullable=True)
    anomaly_confidence = Column(Float, nullable=True)
    anomaly_conclusion = Column(String(200), nullable=True)

class User(Base):
    """
    ORM model for user authentication and authorization.
    Added for security implementation.
    """
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="user")  # admin, user
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
