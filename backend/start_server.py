#!/usr/bin/env python3
"""
Simple server startup script for debugging.
"""
import uvicorn
import os

if __name__ == "__main__":
    print("Starting Secure Water Quality API...")
    print("Server will be available at:")
    print("   - Local: http://localhost:8443")
    print("   - Network: http://127.0.0.1:8443")
    print("   - All interfaces: http://0.0.0.0:8443")
    print()
    print("Test credentials:")
    print("   - Admin: username='admin', password='admin123'")
    print("   - User: username='testuser', password='test123'")
    print()
    print("API Documentation:")
    print("   - Swagger UI: http://localhost:8443/docs")
    print("   - ReDoc: http://localhost:8443/redoc")
    print()
    print("Press Ctrl+C to stop the server")
    print("=" * 50)
    
    # Start server with explicit host and port
    uvicorn.run(
        "main:app",
        host="127.0.0.1",  # Use localhost instead of 0.0.0.0
        port=8443,
        reload=True,
        log_level="info"
    )
