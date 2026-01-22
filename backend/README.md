# Secure Water Quality Monitoring API - Testing Environment
# Backend system with Ml integration
This is a **secured testing version** of the water quality monitoring backend with comprehensive security improvements implemented.

## 🔒 Security Features Implemented

### 1. Authentication & Authorization
- **JWT-based authentication** with secure token generation
- **Role-based access control** (admin, user roles)
- **Protected endpoints** requiring authentication
- **Admin-only endpoints** for user management

### 2. CORS Configuration
- **Environment-based CORS** using `ALLOWED_ORIGINS` variable
- **Specific allowed origins** instead of wildcard `*`
- **Configurable for different environments**

### 3. Input Validation & Sanitization
- **Enhanced Pydantic models** with strict validation
- **Regex-based input sanitization** for text fields
- **Range validation** for numeric sensor data
- **Injection attack prevention**

### 4. Rate Limiting
- **Endpoint-specific rate limits** using SlowAPI
- **Login attempt limiting** (5/minute)
- **API request limiting** (10-60/minute based on endpoint)
- **IP-based tracking**

### 5. Security Headers
- **X-Content-Type-Options: nosniff**
- **X-Frame-Options: DENY**
- **X-XSS-Protection: 1; mode=block**
- **Content-Security-Policy: default-src 'self'**
- **Referrer-Policy: strict-origin-when-cross-origin**
- **Server header obfuscation**

### 6. Database Security
- **Isolated database** (`water_quality_test.db`)
- **Secure file location** in `backend_testing/secure_db/`
- **Enhanced database isolation** settings

### 7. Logging & Monitoring
- **Security event logging** to `logs/security.log`
- **Authentication attempt logging**
- **Error logging with IP tracking**
- **Structured logging format**

## 🚀 Getting Started

### Prerequisites
```bash
pip install -r requirements.txt
```

### Environment Configuration
Copy and configure the `.env` file:
```bash
cp .env.example .env
# Edit .env with your configuration
```

### Database Initialization
The database and test users are automatically initialized on startup.

### Running the Server
```bash
cd backend_testing
python main.py
```

Server runs on: `http://localhost:8443`

## 🔐 Authentication

### Test Users
- **Admin**: username=`admin`, password=`admin123`
- **User**: username=`testuser`, password=`test123`

### Login Endpoint
```bash
POST /auth/login
Content-Type: application/json

{
  "username": "admin",
  "password": "admin123"
}
```

### Using the Token
Include the JWT token in Authorization header:
```bash
Authorization: Bearer <your-jwt-token>
```

## 📡 API Endpoints

### Public Endpoints
- `GET /` - API information
- `GET /health` - Health check

### Authentication
- `POST /auth/login` - User login
- `GET /auth/me` - Get current user info (requires auth)

### Protected Endpoints (Require Authentication)
- `POST /predict` - Make water quality prediction
- `GET /latest` - Get latest sensor reading
- `GET /history` - Get reading history

### Admin-Only Endpoints
- `GET /admin/users` - Get all users (admin only)

## 🛡️ Security Configuration

### Environment Variables
- `JWT_SECRET_KEY` - JWT signing secret
- `ALLOWED_ORIGINS` - Comma-separated allowed origins
- `ACCESS_TOKEN_EXPIRE_MINUTES` - Token expiration time
- `RATE_LIMIT_ENABLED` - Enable/disable rate limiting

### CORS Configuration
Set allowed origins in `.env`:
```
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8080
```

## 🔍 Testing the Security Features

### 1. Test Authentication
```bash
# Try accessing protected endpoint without token
curl -X GET http://localhost:8443/latest
# Should return 401 Unauthorized

# Login and get token
curl -X POST http://localhost:8443/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'

# Use token to access protected endpoint
curl -X GET http://localhost:8443/latest \
  -H "Authorization: Bearer <token>"
```

### 2. Test Rate Limiting
```bash
# Make multiple rapid requests to trigger rate limiting
for i in {1..10}; do
  curl -X POST http://localhost:8443/auth/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"wrong"}'
done
```

### 3. Test Input Validation
```bash
# Send invalid data to test validation
curl -X POST http://localhost:8443/predict \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"tds": -100, "ph_status_msg": "<script>alert(1)</script>"}'
```

## 📁 Project Structure

```
backend_testing/
├── main.py              # Secure FastAPI application
├── auth.py              # JWT authentication system
├── database.py          # Secure database configuration
├── database_models.py   # ORM models with user support
├── models.py            # Enhanced Pydantic models
├── ml_model.py          # ML prediction logic (copied)
├── anomaly_detector.py  # Anomaly detection (copied)
├── .env                 # Environment configuration
├── requirements.txt     # Dependencies
├── secure_db/           # Isolated database directory
│   └── water_quality_test.db
├── logs/                # Security logs
└── README.md            # This file
```

## ⚠️ Important Security Notes

1. **This is a testing environment** - do not use in production
2. **JWT secret key** should be changed in production
3. **HTTPS/TLS** should be enabled in production
4. **Database credentials** should use environment variables
5. **Rate limits** should be adjusted based on expected load

## 🔄 Comparison with Original Backend

| Feature | Original Backend | Secure Testing Backend |
|---------|------------------|----------------------|
| Authentication | ❌ None | ✅ JWT + Role-based |
| CORS | ❌ Wildcard (*) | ✅ Environment-based |
| Input Validation | ⚠️ Basic | ✅ Enhanced + Sanitization |
| Rate Limiting | ❌ None | ✅ Per-endpoint limits |
| Security Headers | ❌ None | ✅ Comprehensive |
| Database | 🔓 Shared | ✅ Isolated & Secure |
| Logging | ⚠️ Basic | ✅ Security-focused |
| HTTPS | ❌ None | ⚠️ Configurable |

## 🐛 Troubleshooting

### Common Issues
1. **Import errors**: Ensure all dependencies are installed
2. **Database errors**: Check database file permissions
3. **Authentication failures**: Verify JWT secret and user credentials
4. **CORS errors**: Check ALLOWED_ORIGINS configuration

### Logs
Check `logs/security.log` for detailed security events and errors.
