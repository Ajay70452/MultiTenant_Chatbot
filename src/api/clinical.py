"""
Clinical Advisor API Endpoint (Door 2)

This module provides the Clinical Advisor endpoint for doctors accessing
the system via the Ahsuite iframe integration.

Key differences from the Patient Concierge (Door 1):
- Stateless/free-flow conversation (no state machine)
- Uses Practice Profile (JSONB) instead of Pinecone RAG
- Supports text + optional Base64 image input (for X-ray analysis)
- Protected by X-Client-Token authentication

Security Features:
- Token-based authentication (session tokens or direct access tokens)
- Origin validation for CSRF protection
- Rate limiting per client
"""

import logging
import time
from collections import defaultdict
from typing import Optional, List, Dict, Tuple
from urllib.parse import urlparse
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Request, Header
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.core.config import ALLOWED_ORIGINS

from src.api.dependencies import (
    require_client_token,
    get_client_by_token,
    exchange_one_time_token,
    generate_session_token
)
from src.core.db import get_db
from src.core import state_manager, rag_engine
from src.core.agent import get_clinical_response
from src.models.models import Client

logger = logging.getLogger(__name__)

router = APIRouter()

# Parse allowed origins into a set for efficient lookup
_allowed_origins_set = set(origin.strip().lower() for origin in ALLOWED_ORIGINS.split(',') if origin.strip())


# =============================================================================
# Security: Origin Validation (CSRF Protection)
# =============================================================================

def _normalize_origin(origin: str) -> str:
    """Normalize an origin URL for comparison."""
    if not origin:
        return ""
    origin = origin.lower().strip()
    # Remove trailing slash
    if origin.endswith('/'):
        origin = origin[:-1]
    return origin


def _is_origin_allowed(origin: Optional[str]) -> bool:
    """
    Check if the request origin is in the allowed origins list.

    Args:
        origin: The Origin header value from the request

    Returns:
        True if origin is allowed, False otherwise
    """
    if not origin:
        # No origin header - could be same-origin request or non-browser client
        # For API endpoints with token auth, we allow this
        return True

    # Check for wildcard "*" which allows all origins
    if '*' in _allowed_origins_set:
        return True

    normalized = _normalize_origin(origin)

    # Check against allowed origins
    for allowed in _allowed_origins_set:
        if normalized == _normalize_origin(allowed):
            return True
        # Also check if it's a subdomain match for wildcard patterns
        # e.g., if *.example.com is allowed
        if allowed.startswith('*.'):
            domain = allowed[2:]  # Remove *.
            if normalized.endswith(domain) or normalized.endswith('.' + domain):
                return True

    return False


async def validate_origin(
    request: Request,
    origin: Optional[str] = Header(None),
    referer: Optional[str] = Header(None)
) -> None:
    """
    FastAPI dependency to validate the request origin for CSRF protection.

    For state-changing operations (POST, PUT, DELETE), we validate that:
    1. The Origin header matches our allowed origins, OR
    2. The Referer header (if Origin is missing) matches our allowed origins

    This provides defense-in-depth alongside token authentication.

    Raises:
        HTTPException: 403 if origin validation fails
    """
    # Only validate for state-changing methods
    if request.method not in ("POST", "PUT", "DELETE", "PATCH"):
        return

    # Check Origin header first (preferred)
    if origin:
        if not _is_origin_allowed(origin):
            logger.warning(f"Request from disallowed origin: {origin}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Request origin not allowed"
            )
        return

    # Fall back to Referer header if Origin is missing
    if referer:
        # Extract origin from referer URL
        try:
            parsed = urlparse(referer)
            referer_origin = f"{parsed.scheme}://{parsed.netloc}"
            if not _is_origin_allowed(referer_origin):
                logger.warning(f"Request from disallowed referer: {referer}")
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Request origin not allowed"
                )
        except Exception as e:
            logger.warning(f"Failed to parse referer header: {e}")
            # If we can't parse the referer, allow the request
            # (the token auth will still protect the endpoint)

    # If neither Origin nor Referer is present, allow the request
    # This could be a same-origin request or a direct API call
    # Token authentication provides the primary security layer


# =============================================================================
# Security: Rate Limiting
# =============================================================================

# Rate limit configuration
RATE_LIMIT_REQUESTS = 60  # Max requests per window
RATE_LIMIT_WINDOW_SECONDS = 60  # Window size (1 minute)
RATE_LIMIT_CLEANUP_INTERVAL = 300  # Cleanup old entries every 5 minutes

# In-memory rate limit store: {client_id: [(timestamp, count), ...]}
# Each entry tracks request counts per time window
_rate_limit_store: Dict[str, List[Tuple[float, int]]] = defaultdict(list)
_last_cleanup_time: float = time.time()


def _cleanup_rate_limit_store():
    """Remove expired entries from the rate limit store."""
    global _last_cleanup_time
    current_time = time.time()

    # Only cleanup periodically to avoid overhead
    if current_time - _last_cleanup_time < RATE_LIMIT_CLEANUP_INTERVAL:
        return

    _last_cleanup_time = current_time
    cutoff = current_time - RATE_LIMIT_WINDOW_SECONDS

    # Remove expired entries for all clients
    for client_id in list(_rate_limit_store.keys()):
        _rate_limit_store[client_id] = [
            (ts, count) for ts, count in _rate_limit_store[client_id]
            if ts > cutoff
        ]
        # Remove client entry if empty
        if not _rate_limit_store[client_id]:
            del _rate_limit_store[client_id]


def _get_request_count(client_id: str) -> int:
    """Get the number of requests in the current window for a client."""
    current_time = time.time()
    cutoff = current_time - RATE_LIMIT_WINDOW_SECONDS

    # Filter to only recent requests
    recent_requests = [
        (ts, count) for ts, count in _rate_limit_store[client_id]
        if ts > cutoff
    ]
    _rate_limit_store[client_id] = recent_requests

    return sum(count for _, count in recent_requests)


def _record_request(client_id: str):
    """Record a new request for rate limiting."""
    current_time = time.time()
    _rate_limit_store[client_id].append((current_time, 1))


def check_rate_limit(client_id: UUID) -> Tuple[bool, int, int]:
    """
    Check if a client has exceeded their rate limit.

    Args:
        client_id: The UUID of the client making the request

    Returns:
        Tuple of (is_allowed, current_count, limit)
        - is_allowed: True if the request should be allowed
        - current_count: Current number of requests in the window
        - limit: The rate limit threshold
    """
    _cleanup_rate_limit_store()

    client_key = str(client_id)
    current_count = _get_request_count(client_key)

    if current_count >= RATE_LIMIT_REQUESTS:
        return False, current_count, RATE_LIMIT_REQUESTS

    # Record this request
    _record_request(client_key)

    return True, current_count + 1, RATE_LIMIT_REQUESTS


async def rate_limit_dependency(
    client: Client = Depends(require_client_token)
) -> Client:
    """
    FastAPI dependency that enforces rate limiting per client.

    This dependency must be used AFTER require_client_token since it
    needs the authenticated client to track rate limits per client.

    Args:
        client: The authenticated client

    Returns:
        The client if rate limit not exceeded

    Raises:
        HTTPException: 429 if rate limit exceeded
    """
    is_allowed, current_count, limit = check_rate_limit(client.client_id)

    if not is_allowed:
        logger.warning(
            f"Rate limit exceeded for client: {client.client_id}",
            extra={
                'client_id': str(client.client_id),
                'request_count': current_count,
                'rate_limit': limit
            }
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Rate limit exceeded. Maximum {limit} requests per minute. Please try again later.",
            headers={
                "Retry-After": str(RATE_LIMIT_WINDOW_SECONDS),
                "X-RateLimit-Limit": str(limit),
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": str(int(time.time()) + RATE_LIMIT_WINDOW_SECONDS)
            }
        )

    return client



class TokenExchangeRequest(BaseModel):
    """Request schema for exchanging a URL token for a session token."""
    token: str = Field(
        ...,
        min_length=1,
        description="The one-time token from the URL parameter"
    )


class TokenExchangeResponse(BaseModel):
    """Response schema for token exchange."""
    session_token: str = Field(..., description="The session token to use for subsequent requests")
    client_id: str = Field(..., description="The authenticated client's ID")
    clinic_name: str = Field(..., description="The clinic name for display")
    expires_in_hours: int = Field(default=4, description="Hours until the session token expires")


class ClinicalMessage(BaseModel):
    """A single message in the clinical conversation history."""
    role: str = Field(
        ...,
        description="Message role: 'user' or 'assistant'",
        pattern=r'^(user|assistant)$'
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The message content"
    )

    @field_validator('content')
    @classmethod
    def validate_content(cls, v: str) -> str:
        """Validate message content for security."""
        if not v or not v.strip():
            raise ValueError("Message content cannot be empty")
        # Check for null bytes (security concern)
        if '\0' in v:
            raise ValueError("Message contains invalid null characters")
        return v.strip()


# Maximum conversation history items to accept
MAX_CONVERSATION_HISTORY_LENGTH = 50


class ClinicalChatRequest(BaseModel):
    """
    Request schema for the Clinical Advisor endpoint.

    The clinical advisor is stateless - the client must send the full
    conversation history with each request.

    Security validations:
    - Message length limits
    - Control character filtering
    - Conversation history size limits
    - Image format validation
    """
    message: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description="The doctor's question or message"
    )
    image_base64: Optional[str] = Field(
        None,
        description="Optional Base64-encoded image (e.g., X-ray) for analysis. "
                    "Should include the data URI prefix (e.g., 'data:image/png;base64,...')"
    )
    conversation_history: Optional[List[ClinicalMessage]] = Field(
        default=[],
        max_length=MAX_CONVERSATION_HISTORY_LENGTH,
        description="Previous messages in the conversation for context. "
                    f"Maximum {MAX_CONVERSATION_HISTORY_LENGTH} messages. "
                    "Since this endpoint is stateless, the client must maintain history."
    )

    @field_validator('message')
    @classmethod
    def validate_message(cls, v: str) -> str:
        """
        Comprehensive message validation for security.

        Checks:
        - Empty/whitespace-only messages
        - Null bytes (security concern)
        - Control characters (except newlines/tabs)
        - Excessive whitespace
        """
        if not v or not v.strip():
            raise ValueError("Message cannot be empty")

        # Check for null bytes (can cause issues in string processing)
        if '\0' in v:
            raise ValueError("Message contains invalid null characters")

        # Check for control characters (except newline, carriage return, tab)
        allowed_control_chars = {'\n', '\r', '\t'}
        for char in v:
            if char.isspace() and char not in allowed_control_chars and char != ' ':
                # Skip regular spaces and allowed whitespace
                continue
            if ord(char) < 32 and char not in allowed_control_chars:
                raise ValueError(f"Message contains invalid control character (code: {ord(char)})")

        # Collapse excessive whitespace (more than 10 consecutive newlines)
        import re
        v = re.sub(r'\n{10,}', '\n\n\n', v)

        return v.strip()

    @field_validator('image_base64')
    @classmethod
    def validate_image_base64(cls, v: Optional[str]) -> Optional[str]:
        """Validate image base64 format."""
        if v is None:
            return v

        # Check for null bytes
        if '\0' in v:
            raise ValueError("Image data contains invalid characters")

        # Basic validation - check if it looks like a data URI or raw base64
        if v.startswith('data:image/'):
            # Data URI format - validate it has the base64 marker
            if ';base64,' not in v:
                raise ValueError("Invalid data URI format. Expected 'data:image/...;base64,...'")
        elif len(v) < 100:
            # Raw base64 should be substantial for an image
            raise ValueError("Image data appears too short to be valid")

        return v

    @field_validator('conversation_history')
    @classmethod
    def validate_conversation_history(cls, v: Optional[List]) -> Optional[List]:
        """Validate conversation history size and content."""
        if v is None:
            return []

        if len(v) > MAX_CONVERSATION_HISTORY_LENGTH:
            raise ValueError(
                f"Conversation history exceeds maximum of {MAX_CONVERSATION_HISTORY_LENGTH} messages"
            )

        # Calculate total size of conversation history
        total_chars = sum(len(msg.content) for msg in v)
        max_total_chars = 100000  # 100KB max for entire history

        if total_chars > max_total_chars:
            raise ValueError(
                f"Total conversation history size ({total_chars} chars) exceeds maximum ({max_total_chars} chars)"
            )

        return v


class ClinicalChatResponse(BaseModel):
    """Response schema for the Clinical Advisor endpoint."""
    response: str = Field(..., description="The clinical advisor's response")
    client_id: str = Field(..., description="The authenticated client's ID")
    has_image: bool = Field(
        default=False,
        description="Whether the request included an image for analysis"
    )
    confidence_level: str = Field(
        default="moderate",
        description="AI confidence in the response: 'low', 'moderate', or 'high'"
    )
    requires_referral: bool = Field(
        default=False,
        description="Whether the AI detected potential need for specialist referral"
    )
    safety_warnings: List[str] = Field(
        default=[],
        description="Any safety concerns or warnings identified by the AI"
    )


# =============================================================================
# API Endpoints
# =============================================================================

@router.post(
    "/auth/exchange",
    response_model=TokenExchangeResponse,
    summary="Exchange URL Token for Session Token",
    description="""
    Exchange a one-time URL token for a secure session token.

    This endpoint should be called immediately when the clinical UI loads.
    The one-time token from the URL can only be used once and expires in 5 minutes.
    The returned session token should be stored in sessionStorage and used for
    all subsequent API requests.

    Security benefits:
    - Token is removed from URL immediately after exchange
    - One-time tokens cannot be reused (prevents replay attacks)
    - Session tokens are not exposed in browser history or server logs
    """
)
async def exchange_token(
    request: TokenExchangeRequest,
    db: Session = Depends(get_db),
    _origin_check: None = Depends(validate_origin)
) -> TokenExchangeResponse:
    """
    Exchange a one-time URL token for a session token.

    Args:
        request: Contains the one-time token from the URL
        db: Database session (injected)

    Returns:
        TokenExchangeResponse with session token and client info

    Raises:
        HTTPException: 401 if token is invalid, expired, or already used
    """
    # First try to exchange as a one-time token
    result = exchange_one_time_token(request.token)

    if result:
        client_id, session_token = result
        # Get client info
        client = db.query(Client).filter(Client.client_id == client_id).first()
        if client:
            logger.info(f"One-time token exchanged successfully for client: {client_id}")
            return TokenExchangeResponse(
                session_token=session_token,
                client_id=str(client_id),
                clinic_name=client.clinic_name or "Practice",
                expires_in_hours=4
            )

    # Fall back to direct access token exchange (for backwards compatibility)
    # This allows existing tokens to work but upgrades them to session tokens
    client = get_client_by_token(db, request.token)

    if client:
        session_token = generate_session_token(client.client_id)
        logger.info(f"Access token exchanged for session token, client: {client.client_id}")
        return TokenExchangeResponse(
            session_token=session_token,
            client_id=str(client.client_id),
            clinic_name=client.clinic_name or "Practice",
            expires_in_hours=4
        )

    logger.warning("Token exchange failed: invalid or expired token")
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid, expired, or already used token"
    )


@router.post(
    "/chat",
    response_model=ClinicalChatResponse,
    summary="Clinical Advisor Chat",
    description="""
    Chat endpoint for the Clinical Advisor (doctor-facing).

    This endpoint:
    - Requires X-Client-Token header for authentication
    - Is stateless (client maintains conversation history)
    - Uses the practice profile for context (not Pinecone RAG)
    - Supports optional image input for X-ray/scan analysis

    The clinical advisor acts as a professional clinical colleague,
    providing guidance based on the doctor's practice philosophy
    and clinical preferences stored in their profile.
    """
)
async def clinical_chat(
    request: ClinicalChatRequest,
    client: Client = Depends(rate_limit_dependency),  # Includes auth + rate limiting
    db: Session = Depends(get_db),
    _origin_check: None = Depends(validate_origin)
) -> ClinicalChatResponse:
    """
    Handle a clinical advisor chat message.

    Args:
        request: The chat request containing message, optional image, and history
        client: The authenticated client (injected via dependency)
        db: Database session (injected via dependency)

    Returns:
        ClinicalChatResponse with the advisor's response
    """
    logger.info(
        f"Clinical chat request from client: {client.client_id}",
        extra={
            'client_id': str(client.client_id),
            'clinic_name': client.clinic_name,
            'has_image': request.image_base64 is not None,
            'history_length': len(request.conversation_history or [])
        }
    )

    # Load the practice profile (the "Brain")
    practice_profile = state_manager.get_practice_profile(db, client.client_id)

    if not practice_profile:
        logger.warning(f"No practice profile configured for client: {client.client_id}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Practice profile not configured. Please contact support to set up your clinical profile."
        )

    has_image = request.image_base64 is not None

    # Convert conversation history to the format expected by the agent
    conversation_history = None
    if request.conversation_history:
        conversation_history = [
            {"role": msg.role, "content": msg.content}
            for msg in request.conversation_history
        ]

    # Retrieve RAG context from Pinecone for the user's message
    # Wrapped in try-catch for defense in depth (RAG engine also handles errors internally)
    try:
        rag_context = rag_engine.get_relevant_context(
            query=request.message,
            client_id=str(client.client_id)
        )
    except Exception as e:
        # Log error but continue without RAG context - graceful degradation
        logger.error(
            f"RAG retrieval failed for client {client.client_id}: {e}",
            extra={'client_id': str(client.client_id), 'error': str(e)}
        )
        rag_context = ""

    logger.info(
        f"RAG context retrieved for clinical chat",
        extra={
            'client_id': str(client.client_id),
            'rag_context_length': len(rag_context) if rag_context else 0,
            'has_rag_context': bool(rag_context)
        }
    )

    # Call the clinical agent with both practice profile and RAG context
    agent_response = await get_clinical_response(
        user_message=request.message,
        practice_profile=practice_profile,
        conversation_history=conversation_history,
        image_base64=request.image_base64,
        rag_context=rag_context,
        clinic_name=client.clinic_name
    )

    logger.info(
        f"Clinical chat response generated for client: {client.client_id}",
        extra={
            'client_id': str(client.client_id),
            'response_length': len(agent_response.get("response_text", "")),
            'confidence_level': agent_response.get("confidence_level"),
            'requires_referral': agent_response.get("requires_referral")
        }
    )

    # Return response with all metadata
    # NOTE: This endpoint is STATELESS - no state machine, no stage transitions
    # The client (Ahsuite iframe) is responsible for maintaining conversation history
    return ClinicalChatResponse(
        response=agent_response.get("response_text", ""),
        client_id=str(client.client_id),
        has_image=has_image,
        confidence_level=agent_response.get("confidence_level", "moderate"),
        requires_referral=agent_response.get("requires_referral", False),
        safety_warnings=agent_response.get("safety_warnings", [])
    )


@router.get(
    "/profile",
    summary="Get Practice Profile",
    description="Retrieve the current practice profile status for the authenticated client. "
                "Returns profile metadata but not the full profile content for security."
)
async def get_profile(
    request: Request,
    client: Client = Depends(require_client_token),
    db: Session = Depends(get_db),
    _origin_check: None = Depends(validate_origin)
) -> dict:
    """
    Get the practice profile status for the authenticated client.

    For security, this endpoint returns profile metadata rather than
    the full profile content. The full profile is only used internally
    by the clinical chat endpoint.

    Args:
        request: The FastAPI request object (for logging)
        client: The authenticated client (injected via dependency)
        db: Database session (injected via dependency)

    Returns:
        Profile status including whether a profile is configured
    """
    # Log all profile access attempts for security auditing
    logger.info(
        f"Practice profile access by client: {client.client_id}",
        extra={
            'client_id': str(client.client_id),
            'clinic_name': client.clinic_name,
            'endpoint': '/profile',
            'method': 'GET'
        }
    )

    profile = state_manager.get_practice_profile(db, client.client_id)

    # Return metadata about the profile, not the full content
    # This reduces the risk of sensitive practice philosophy data being exposed
    response = {
        "client_id": str(client.client_id),
        "clinic_name": client.clinic_name,
        "has_profile": profile is not None,
    }

    # Only include profile summary if it exists (not full content)
    if profile:
        response["profile_configured"] = True
        response["profile_sections"] = list(profile.keys()) if isinstance(profile, dict) else []
    else:
        response["profile_configured"] = False
        response["profile_sections"] = []

    return response
