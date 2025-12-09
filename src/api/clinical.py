"""
Clinical Advisor API Endpoint (Door 2)

This module provides the Clinical Advisor endpoint for doctors accessing
the system via the Ahsuite iframe integration.

Key differences from the Patient Concierge (Door 1):
- Stateless/free-flow conversation (no state machine)
- Uses Practice Profile (JSONB) instead of Pinecone RAG
- Supports text + optional Base64 image input (for X-ray analysis)
- Protected by X-Client-Token authentication
"""

import logging
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from src.api.dependencies import require_client_token
from src.core.db import get_db
from src.core import state_manager, rag_engine
from src.core.agent import get_clinical_response
from src.models.models import Client

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Pydantic Schemas
# =============================================================================

class ClinicalMessage(BaseModel):
    """A single message in the clinical conversation history."""
    role: str = Field(..., description="Message role: 'user' or 'assistant'")
    content: str = Field(..., description="The message content")


class ClinicalChatRequest(BaseModel):
    """
    Request schema for the Clinical Advisor endpoint.

    The clinical advisor is stateless - the client must send the full
    conversation history with each request.
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
        description="Previous messages in the conversation for context. "
                    "Since this endpoint is stateless, the client must maintain history."
    )

    @field_validator('image_base64')
    @classmethod
    def validate_image_base64(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v

        # Basic validation - check if it looks like a data URI or raw base64
        if v.startswith('data:image/'):
            # Data URI format - validate it has the base64 marker
            if ';base64,' not in v:
                raise ValueError("Invalid data URI format. Expected 'data:image/...;base64,...'")
        elif len(v) < 100:
            # Raw base64 should be substantial for an image
            raise ValueError("Image data appears too short to be valid")

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
# API Endpoint
# =============================================================================

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
    client: Client = Depends(require_client_token),
    db: Session = Depends(get_db)
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
    rag_context = rag_engine.get_relevant_context(
        query=request.message,
        client_id=str(client.client_id)
    )

    logger.info(
        f"RAG context retrieved for clinical chat: {rag_context[:500] if rag_context else 'EMPTY'}",
        extra={
            'client_id': str(client.client_id),
            'rag_context_length': len(rag_context) if rag_context else 0
        }
    )

    # Call the clinical agent with both practice profile and RAG context
    agent_response = await get_clinical_response(
        user_message=request.message,
        practice_profile=practice_profile,
        conversation_history=conversation_history,
        image_base64=request.image_base64,
        rag_context=rag_context
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
    description="Retrieve the current practice profile for the authenticated client."
)
async def get_profile(
    client: Client = Depends(require_client_token),
    db: Session = Depends(get_db)
) -> dict:
    """
    Get the practice profile for the authenticated client.

    Args:
        client: The authenticated client (injected via dependency)
        db: Database session (injected via dependency)

    Returns:
        The practice profile JSON or an empty dict if not configured
    """
    profile = state_manager.get_practice_profile(db, client.client_id)

    return {
        "client_id": str(client.client_id),
        "clinic_name": client.clinic_name,
        "profile": profile or {},
        "has_profile": profile is not None
    }
