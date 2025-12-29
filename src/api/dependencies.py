"""
Authentication dependencies for securing API routes.

This module provides token-based authentication for the Clinical Advisor
and other protected endpoints using the X-Client-Token header.

Security Features:
- One-time URL token exchange for session tokens
- Session tokens stored in memory (not exposed in URLs)
- Token expiration and rotation
- Constant-time comparison to prevent timing attacks
"""

import logging
import secrets
import hashlib
from datetime import datetime, timedelta
from typing import Optional, Dict, Tuple
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.core.db import get_db
from src.models.models import Client

logger = logging.getLogger(__name__)

# =============================================================================
# Session Token Management (In-Memory Store)
# =============================================================================

# In-memory store for session tokens: {session_token: (client_id, expiry_datetime)}
# In production, consider using Redis for distributed deployments
_session_store: Dict[str, Tuple[UUID, datetime]] = {}

# Session token expiry time (4 hours)
SESSION_TOKEN_EXPIRY_HOURS = 4

# One-time token expiry (5 minutes - for URL token exchange)
ONE_TIME_TOKEN_EXPIRY_MINUTES = 5

# In-memory store for one-time tokens: {hashed_token: (client_id, expiry_datetime, used)}
_one_time_tokens: Dict[str, Tuple[UUID, datetime, bool]] = {}


def _cleanup_expired_sessions():
    """Remove expired sessions from the store."""
    now = datetime.utcnow()
    expired = [token for token, (_, expiry) in _session_store.items() if expiry < now]
    for token in expired:
        del _session_store[token]


def _cleanup_expired_one_time_tokens():
    """Remove expired one-time tokens from the store."""
    now = datetime.utcnow()
    expired = [token for token, (_, expiry, _) in _one_time_tokens.items() if expiry < now]
    for token in expired:
        del _one_time_tokens[token]


def generate_session_token(client_id: UUID) -> str:
    """
    Generate a new session token for a client.

    Args:
        client_id: The UUID of the authenticated client

    Returns:
        A secure random session token
    """
    _cleanup_expired_sessions()

    # Generate a secure random token
    session_token = secrets.token_urlsafe(32)
    expiry = datetime.utcnow() + timedelta(hours=SESSION_TOKEN_EXPIRY_HOURS)

    _session_store[session_token] = (client_id, expiry)

    logger.info(f"Generated session token for client: {client_id}")
    return session_token


def validate_session_token(session_token: str) -> Optional[UUID]:
    """
    Validate a session token and return the associated client_id.

    Args:
        session_token: The session token to validate

    Returns:
        The client_id if valid, None otherwise
    """
    _cleanup_expired_sessions()

    if session_token not in _session_store:
        return None

    client_id, expiry = _session_store[session_token]

    if datetime.utcnow() > expiry:
        del _session_store[session_token]
        return None

    return client_id


def revoke_session_token(session_token: str) -> bool:
    """
    Revoke a session token (logout).

    Args:
        session_token: The session token to revoke

    Returns:
        True if token was revoked, False if not found
    """
    if session_token in _session_store:
        del _session_store[session_token]
        return True
    return False


def generate_one_time_url_token(client_id: UUID) -> str:
    """
    Generate a one-time token for URL-based authentication.
    This token can only be exchanged once for a session token.

    Args:
        client_id: The UUID of the client

    Returns:
        A one-time URL token
    """
    _cleanup_expired_one_time_tokens()

    # Generate token
    token = secrets.token_urlsafe(32)
    # Store hash of token (so even if store is compromised, tokens are safe)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    expiry = datetime.utcnow() + timedelta(minutes=ONE_TIME_TOKEN_EXPIRY_MINUTES)

    _one_time_tokens[token_hash] = (client_id, expiry, False)

    return token


def exchange_one_time_token(one_time_token: str) -> Optional[Tuple[UUID, str]]:
    """
    Exchange a one-time URL token for a session token.
    The one-time token is invalidated after use.

    Args:
        one_time_token: The one-time token from the URL

    Returns:
        Tuple of (client_id, session_token) if valid, None otherwise
    """
    _cleanup_expired_one_time_tokens()

    token_hash = hashlib.sha256(one_time_token.encode()).hexdigest()

    if token_hash not in _one_time_tokens:
        logger.warning("One-time token not found or expired")
        return None

    client_id, expiry, used = _one_time_tokens[token_hash]

    # Check if already used
    if used:
        logger.warning(f"Attempted reuse of one-time token for client: {client_id}")
        # Remove the token entirely on reuse attempt (potential attack)
        del _one_time_tokens[token_hash]
        return None

    # Check expiry
    if datetime.utcnow() > expiry:
        del _one_time_tokens[token_hash]
        return None

    # Mark as used
    _one_time_tokens[token_hash] = (client_id, expiry, True)

    # Generate session token
    session_token = generate_session_token(client_id)

    logger.info(f"One-time token exchanged for session token, client: {client_id}")
    return (client_id, session_token)


def verify_client_token(db: Session, client_id: UUID, token: str) -> bool:
    """
    Verify that the provided token matches the stored access_token for the client.

    Args:
        db: Database session
        client_id: The UUID of the client to verify
        token: The token provided in the request header

    Returns:
        True if the token is valid, False otherwise
    """
    client = db.query(Client).filter(Client.client_id == client_id).first()

    if not client:
        logger.warning(f"Client not found: {client_id}")
        return False

    if client.access_token is None:
        logger.warning(f"Client {client_id} has no access_token configured")
        return False

    # Use constant-time comparison to prevent timing attacks
    import secrets
    is_valid = secrets.compare_digest(client.access_token, token)

    if not is_valid:
        logger.warning(f"Invalid token attempt for client: {client_id}")

    return is_valid


def get_client_by_token(db: Session, token: str) -> Optional[Client]:
    """
    Look up a client by their access token.

    Args:
        db: Database session
        token: The access token to look up

    Returns:
        The Client object if found, None otherwise
    """
    return db.query(Client).filter(Client.access_token == token).first()


async def require_client_token(
    x_client_token: str = Header(..., description="Client access token for authentication"),
    db: Session = Depends(get_db)
) -> Client:
    """
    FastAPI dependency that requires a valid X-Client-Token header.

    This dependency supports two authentication methods:
    1. Session token (preferred) - obtained via /auth/exchange endpoint
    2. Direct access token (legacy/fallback) - stored in database

    The function first checks if the token is a valid session token,
    then falls back to checking the database access token.

    Usage:
        @router.post("/protected-endpoint")
        async def protected_route(client: Client = Depends(require_client_token)):
            # client is now the authenticated Client object
            pass

    Args:
        x_client_token: The token from the X-Client-Token header
        db: Database session (injected)

    Returns:
        The authenticated Client object

    Raises:
        HTTPException: 401 if token is missing or invalid
    """
    if not x_client_token:
        logger.warning("Missing X-Client-Token header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Client-Token header"
        )

    # First, try to validate as a session token
    client_id = validate_session_token(x_client_token)
    if client_id:
        client = db.query(Client).filter(Client.client_id == client_id).first()
        if client:
            logger.info(f"Authenticated via session token: {client.client_id} ({client.clinic_name})")
            return client

    # Fall back to direct access token lookup (legacy support)
    client = get_client_by_token(db, x_client_token)

    if not client:
        logger.warning("Invalid or unknown access token attempted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token"
        )

    logger.info(f"Authenticated via access token: {client.client_id} ({client.clinic_name})")
    return client


async def optional_client_token(
    x_client_token: Optional[str] = Header(None, description="Optional client access token"),
    db: Session = Depends(get_db)
) -> Optional[Client]:
    """
    FastAPI dependency that optionally authenticates via X-Client-Token header.

    Unlike require_client_token, this does not raise an error if no token is provided.
    Useful for endpoints that behave differently for authenticated vs unauthenticated users.

    Args:
        x_client_token: Optional token from the X-Client-Token header
        db: Database session (injected)

    Returns:
        The authenticated Client object if token is valid, None otherwise
    """
    if not x_client_token:
        return None

    return get_client_by_token(db, x_client_token)
