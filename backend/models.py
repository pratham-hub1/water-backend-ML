from typing import Dict, List, Optional, Any
import random
from pydantic import BaseModel, Field, validator
import re

class WaterQualityInput(BaseModel):
    """
    Enhanced Pydantic model for water quality sensor input with security validation.
    Fields:
        tds: Total Dissolved Solids in ppm (float > 0) - Optional
        turbidity: Turbidity in NTU (float >= 0) - Optional
        leak: Leak status (0 or 1) - Optional
        ph_value: pH sensor reading (0-14) - Optional
        ph_status_msg: pH status message - Optional
    All fields are optional to support partial sensor payloads.
    """
    tds: Optional[float] = Field(None, gt=0, le=2000, description="Total Dissolved Solids in ppm (0-2000)")
    turbidity: Optional[float] = Field(None, ge=0, le=1000, description="Turbidity in NTU (0-1000)")
    leak: Optional[int] = Field(None, ge=0, le=1, description="Leak status (0 or 1)")
    ph_value: Optional[float] = Field(None, ge=0.0, le=14.0, description="pH sensor reading (0-14)")
    ph_status_msg: Optional[str] = Field(None, max_length=50, description="pH status message")
    
    @validator('ph_status_msg')
    def validate_ph_status_msg(cls, v):
        """Validate pH status message for potential injection."""
        if v is None:
            return v
        # Allow only safe characters
        if not re.match(r'^[a-zA-Z0-9\s\-\.\(\):]+$', v):
            raise ValueError('Invalid characters in pH status message')
        return v.strip()[:50]

class AnomalyDetail(BaseModel):
    """Detailed information about a detected anomaly."""
    sensor: str
    value: float
    anomaly_type: str
    confidence: float
    cause: str

class AnomalyDetectionResult(BaseModel):
    """Results from the anomaly detection system."""
    anomaly_detected: bool = False
    most_probable_cause: Optional[str] = None
    confidence: float = 0.0
    conclusion: str = "No anomalies detected"
    details: List[AnomalyDetail] = []

class MLPrediction(BaseModel):
    """Machine learning model prediction results."""
    predicted_class: int
    is_safe: bool
    needs_replacement: bool

class PredictionResponse(BaseModel):
    """Complete prediction response including ML results and anomaly detection."""
    ml_prediction: MLPrediction
    reason_engine: List[str] = Field(
        ...,
        description="List of human-readable reasons for the prediction"
    )
    anomaly_detection: AnomalyDetectionResult
    filter_health_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="Filter health score (100 = best, 0 = worst)"
    )
    ph_value: Optional[float] = Field(None, ge=0.0, le=14.0, description="pH sensor reading")
    ph_status_msg: Optional[str] = Field(None, max_length=50, description="pH status message")

class UserCreate(BaseModel):
    """User creation model with validation."""
    username: str = Field(..., min_length=3, max_length=50, description="Username")
    email: str = Field(..., description="Email address")
    password: str = Field(..., min_length=6, max_length=100, description="Password")
    role: str = Field("user", description="User role (admin/user)")
    
    @validator('username')
    def validate_username(cls, v):
        """Validate username for security."""
        if not re.match(r'^[a-zA-Z0-9_-]+$', v):
            raise ValueError('Username can only contain alphanumeric characters, underscores, and hyphens')
        return v
    
    @validator('email')
    def validate_email(cls, v):
        """Validate email format."""
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, v):
            raise ValueError('Invalid email format')
        return v.lower()
    
    @validator('role')
    def validate_role(cls, v):
        """Validate user role."""
        if v not in ['admin', 'user']:
            raise ValueError('Role must be either admin or user')
        return v

class UserLogin(BaseModel):
    """User login model."""
    username: str = Field(..., description="Username")
    password: str = Field(..., description="Password")

class Token(BaseModel):
    """JWT token response model."""
    access_token: str
    token_type: str
    expires_in: int
    user_info: Dict[str, Any]

class EndpointInfo(BaseModel):
    path: str
    method: str
    description: str

class APIInfo(BaseModel):
    name: str
    version: str
    status: str
    timestamp: str
    description: str = 'Water Quality Monitoring API - Provides endpoints for prediction and monitoring'
    endpoints: List[EndpointInfo]

def generate_dummy_data() -> Dict[str, float]:
    """
    Generate dummy sensor data for testing purposes.
    Returns a dictionary with random but plausible sensor values.
    """
    return {
        "tds": round(random.uniform(20, 800), 2),  # TDS between 20 and 800 ppm
        "turbidity": round(random.uniform(0, 30), 2),  # Turbidity between 0 and 30 NTU
        "leak": random.choice([0, 1]),  # Leak is either 0 (no) or 1 (yes)
        "ph_value": round(random.uniform(6.5, 8.5), 2)  # pH in normal range (6.5-8.5)
    }
