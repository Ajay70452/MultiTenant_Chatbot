"""
Authentication dependencies for securing API routes.

This module provides token-based authentication for the Clinical Advisor
and other protected endpoints using the X-Client-Token header.
"""

import logging
from typing import Optional
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from src.core.db import get_db
from src.models.models import Client

logger = logging.getLogger(__name__)


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

    This dependency:
    1. Extracts the token from the X-Client-Token header
    2. Looks up the client by their access token
    3. Returns the authenticated Client object

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

    client = get_client_by_token(db, x_client_token)

    if not client:
        logger.warning(f"Invalid or unknown access token attempted")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token"
        )

    logger.info(f"Authenticated client: {client.client_id} ({client.clinic_name})")
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
