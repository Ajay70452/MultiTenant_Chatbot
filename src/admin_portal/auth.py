"""
Admin Authentication Module

JWT-based authentication for admin portal.
Admin credentials are stored in the database (admin_users table).
"""

import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import jwt
import bcrypt

from src.admin_portal.schemas import AdminUser, AdminLoginRequest, AdminLoginResponse
from src.models.models import AdminUser as AdminUserModel
from src.core.db import get_db

logger = logging.getLogger(__name__)

# =============================================================================
# Configuration
# =============================================================================

# Secret key for JWT - in production, use a secure random key from env
SECRET_KEY = os.getenv("ADMIN_JWT_SECRET", "practice-brain-admin-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

# Security scheme
security = HTTPBearer()


# =============================================================================
# Helper Functions
# =============================================================================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against a hash using bcrypt directly."""
    try:
        return bcrypt.checkpw(
            plain_password.encode('utf-8'),
            hashed_password.encode('utf-8')
        )
    except Exception as e:
        logger.error(f"Password verification error: {e}")
        return False


def get_password_hash(password: str) -> str:
    """Generate password hash using bcrypt directly."""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token."""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_access_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {e}")
        return None


# =============================================================================
# Authentication Functions
# =============================================================================

def authenticate_admin(username: str, password: str, db: Session) -> Optional[AdminUser]:
    """
    Authenticate admin user against the database.
    """
    # Query admin user from database
    db_user = db.query(AdminUserModel).filter(
        AdminUserModel.username == username,
        AdminUserModel.is_active == True
    ).first()

    if not db_user:
        logger.warning(f"Admin login failed: user '{username}' not found or inactive")
        return None

    # Verify password
    if not verify_password(password, db_user.password_hash):
        logger.warning(f"Admin login failed: invalid password for '{username}'")
        return None

    # Update last login time
    db_user.last_login_at = datetime.utcnow()
    db.commit()

    return AdminUser(username=db_user.username, role=db_user.role)


def admin_login(request: AdminLoginRequest, db: Session) -> AdminLoginResponse:
    """
    Process admin login request.
    Returns JWT token if credentials are valid.
    """
    admin = authenticate_admin(request.username, request.password, db)

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )

    access_token = create_access_token(
        data={"sub": admin.username, "role": admin.role}
    )

    logger.info(f"Admin login successful: {admin.username}")

    return AdminLoginResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


# =============================================================================
# Dependencies
# =============================================================================

VALID_ADMIN_ROLES = {"admin", "superadmin", "viewer"}


async def require_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> AdminUser:
    """
    FastAPI dependency that requires valid admin JWT token.

    Usage:
        @router.get("/protected")
        async def protected_route(admin: AdminUser = Depends(require_admin)):
            pass
    """
    token = credentials.credentials
    payload = decode_access_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"}
        )

    username = payload.get("sub")
    role = payload.get("role")

    if not username or role not in VALID_ADMIN_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

    return AdminUser(username=username, role=role)


async def optional_admin(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[AdminUser]:
    """
    Optional admin authentication - doesn't raise error if not authenticated.
    """
    if not credentials:
        return None
    
    payload = decode_access_token(credentials.credentials)
    if not payload:
        return None
    
    return AdminUser(
        username=payload.get("sub", ""),
        role=payload.get("role", "")
    )
