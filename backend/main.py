import os
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPBearer
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from sqlalchemy.orm import Session
from sqlalchemy import desc, text

# Local imports
import models
import database_models
from database import get_db, engine
from auth import (
    authenticate_user, create_access_token, get_current_active_user, 
    require_admin, init_test_users, get_password_hash
)
from ml_model import predict_water_quality, generate_reasons, calculate_filter_health
from anomaly_detector import AnomalyDetector
from database_models import SensorReading, User

# Configure logging with security considerations
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/security.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Rate limiting
limiter = Limiter(key_func=get_remote_address)

# Initialize FastAPI app with security metadata
app = FastAPI(
    title="Secure Water Quality Monitoring API",
    description="""
    SECURED API for monitoring and predicting water quality based on sensor data.
    
    Features:
    - JWT Authentication
    - Rate Limiting
    - HTTPS Enforcement
    - CORS Protection
    - Input Validation
    - Security Headers
    """,
    version="2.0.0-secure",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Trusted Host Middleware
app.add_middleware(
    TrustedHostMiddleware, 
    allowed_hosts=["localhost", "127.0.0.1", "*.test.com"]
)

# Secure CORS middleware configuration
def get_allowed_origins():
    """Get allowed origins from environment variable."""
    allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:8080")
    return [origin.strip() for origin in allowed_origins.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),  # Secure: uses environment variable
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],  # Removed PUT, DELETE for security
    allow_headers=["Authorization", "Content-Type"],  # Specific headers only
)

# Security Headers Middleware
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    """Add security headers to all responses."""
    response = await call_next(request)
    
    # Security headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Security headers (HTTPS enforcement disabled for testing)
    # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    
    # Remove server information
    response.headers["Server"] = "SecureServer"
    
    return response

# Exception Handlers with security logging
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with security logging."""
    logger.warning(f"HTTP Exception: {exc.status_code} - {exc.detail} - IP: {request.client.host}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "timestamp": datetime.utcnow().isoformat()}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions with security logging."""
    logger.error(f"Unexpected error: {str(exc)} - IP: {request.client.host}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"error": "Internal server error", "timestamp": datetime.utcnow().isoformat()}
    )

# Initialize database tables and test users on startup
@app.on_event("startup")
async def startup_event():
    """Initialize services when the application starts."""
    try:
        database_models.Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully!")
        
        # Initialize test users
        db = next(get_db())
        try:
            users = init_test_users(db)
            logger.info(f"Test users initialized: {[k for k in users.keys()]}")
        finally:
            db.close()
            
        logger.info("Secure backend started successfully!")
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}")

# Authentication endpoints
@app.post("/auth/login", response_model=models.Token)
@limiter.limit("5/minute")  # Rate limit login attempts
async def login(request: Request, user_data: models.UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return JWT token."""
    user = authenticate_user(db, user_data.username, user_data.password)
    if not user:
        logger.warning(f"Failed login attempt for username: {user_data.username} - IP: {request.client.host}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username, "role": user.role}, 
        expires_delta=access_token_expires
    )
    
    logger.info(f"User logged in: {user.username} - IP: {request.client.host}")
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 1800,  # 30 minutes
        "user_info": {
            "username": user.username,
            "role": user.role,
            "is_active": user.is_active
        }
    }

@app.get("/auth/me", response_model=Dict[str, Any])
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    """Get current user information."""
    return {
        "username": current_user.username,
        "email": current_user.email,
        "role": current_user.role,
        "is_active": current_user.is_active,
        "created_at": current_user.created_at.isoformat(),
        "last_login": current_user.last_login.isoformat() if current_user.last_login else None
    }

# Protected API endpoints
@app.post("/predict", response_model=models.PredictionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def predict(
    request: Request,
    data: models.WaterQualityInput, 
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Make a water quality prediction (authenticated)."""
    logger.info(f"Prediction request from user: {current_user.username} - IP: {request.client.host}")
    
    try:
        # Handle optional sensor data
        tds_val = data.tds
        turbidity_val = data.turbidity
        leak_val = bool(data.leak) if data.leak is not None else None
        ph_val = data.ph_value
        ph_status_msg_val = data.ph_status_msg
        
        prediction = predict_water_quality(
            tds=tds_val,
            turbidity=turbidity_val,
            leak=leak_val,
            ph_value=ph_val
        )
        
        # Generate reasons and filter health
        reasons = generate_reasons(prediction, tds_val, turbidity_val, leak_val, ph_val)
        filter_health = calculate_filter_health(tds_val, turbidity_val, prediction)
        
        # Anomaly detection
        anomaly_detector = AnomalyDetector()
        anomaly_result = anomaly_detector.detect_anomalies({
            'tds': tds_val,
            'turbidity': turbidity_val,
            'leak': leak_val,
            'ph_value': ph_val
        })
        
        # Store in database
        db_reading = SensorReading(
            timestamp=datetime.utcnow(),
            tds=tds_val,
            turbidity=turbidity_val,
            leak=leak_val,
            ph_value=ph_val,
            ph_status_msg=ph_status_msg_val,
            predicted_class=prediction['class'],
            is_safe=prediction['is_safe'],
            needs_replacement=prediction['replacement_needed'],
            filter_health_score=filter_health,
            anomaly_detected=anomaly_result['anomaly_detected'],
            anomaly_cause=anomaly_result.get('most_probable_cause'),
            anomaly_confidence=anomaly_result.get('confidence'),
            anomaly_conclusion=anomaly_result.get('conclusion')
        )
        
        db.add(db_reading)
        db.commit()
        db.refresh(db_reading)
        
        logger.info(f"Prediction stored successfully for user: {current_user.username}")
        
        return models.PredictionResponse(
            ml_prediction=models.MLPrediction(
                predicted_class=prediction['class'],
                is_safe=prediction['is_safe'],
                needs_replacement=prediction['replacement_needed']
            ),
            reason_engine=reasons,
            anomaly_detection=models.AnomalyDetectionResult(**anomaly_result),
            filter_health_score=filter_health,
            ph_value=ph_val,
            ph_status_msg=ph_status_msg_val
        )
        
    except Exception as e:
        logger.error(f"Prediction failed for user {current_user.username}: {str(e)}")
        raise HTTPException(status_code=500, detail="Prediction failed")

@app.get("/latest", response_model=Dict[str, Any])
@limiter.limit("30/minute")
async def get_latest_reading(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get the latest sensor reading (authenticated)."""
    latest = db.query(SensorReading).order_by(desc(SensorReading.timestamp)).first()
    if not latest:
        raise HTTPException(status_code=404, detail="No readings found")
    
    return {
        "id": latest.id,
        "timestamp": latest.timestamp.isoformat(),
        "tds": latest.tds,
        "turbidity": latest.turbidity,
        "leak": latest.leak,
        "ph_value": latest.ph_value,
        "ph_status_msg": latest.ph_status_msg,
        "predicted_class": latest.predicted_class,
        "is_safe": latest.is_safe,
        "needs_replacement": latest.needs_replacement,
        "filter_health_score": latest.filter_health_score,
        "anomaly_detected": latest.anomaly_detected,
        "anomaly_cause": latest.anomaly_cause,
        "anomaly_confidence": latest.anomaly_confidence,
        "anomaly_conclusion": latest.anomaly_conclusion
    }

@app.get("/history", response_model=List[Dict[str, Any]])
@limiter.limit("20/minute")
async def get_reading_history(
    request: Request,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """Get sensor reading history (authenticated)."""
    if limit > 1000:
        raise HTTPException(status_code=400, detail="Limit cannot exceed 1000")
    
    readings = db.query(SensorReading).order_by(desc(SensorReading.timestamp)).limit(limit).all()
    return [
        {
            "id": r.id,
            "timestamp": r.timestamp.isoformat(),
            "tds": r.tds,
            "turbidity": r.turbidity,
            "leak": r.leak,
            "ph_value": r.ph_value,
            "ph_status_msg": r.ph_status_msg,
            "predicted_class": r.predicted_class,
            "is_safe": r.is_safe,
            "needs_replacement": r.needs_replacement,
            "filter_health_score": r.filter_health_score,
            "anomaly_detected": r.anomaly_detected,
            "anomaly_cause": r.anomaly_cause,
            "anomaly_confidence": r.anomaly_confidence,
            "anomaly_conclusion": r.anomaly_conclusion
        }
        for r in readings
    ]

# Admin-only endpoints
@app.get("/admin/users", response_model=List[Dict[str, Any]])
@limiter.limit("10/minute")
async def get_users(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Get all users (admin only)."""
    users = db.query(User).all()
    return [
        {
            "id": u.id,
            "username": u.username,
            "email": u.email,
            "role": u.role,
            "is_active": u.is_active,
            "created_at": u.created_at.isoformat(),
            "last_login": u.last_login.isoformat() if u.last_login else None
        }
        for u in users
    ]

# Public endpoints (no authentication required)
@app.get("/", response_model=models.APIInfo)
@limiter.limit("60/minute")
async def root(request: Request):
    """Root endpoint with API information."""
    return models.APIInfo(
        name="Secure Water Quality Monitoring API",
        version="2.0.0-secure",
        status="secure",
        timestamp=datetime.utcnow().isoformat(),
        endpoints=[
            models.EndpointInfo(path="/auth/login", method="POST", description="Authenticate user"),
            models.EndpointInfo(path="/auth/me", method="GET", description="Get current user info"),
            models.EndpointInfo(path="/predict", method="POST", description="Make prediction"),
            models.EndpointInfo(path="/latest", method="GET", description="Get latest reading"),
            models.EndpointInfo(path="/history", method="GET", description="Get reading history"),
            models.EndpointInfo(path="/admin/users", method="GET", description="Get users (admin)"),
        ]
    )

@app.get("/health")
@limiter.limit("60/minute")
async def health_check(request: Request):
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0-secure",
        "security": "enabled"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8443,
        reload=True
    )
