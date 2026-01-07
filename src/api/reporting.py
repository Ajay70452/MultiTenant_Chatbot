"""
Reporting API Endpoints for the AI Chat Activity Dashboard (Ahsuite Integration)

This module provides read-only endpoints for viewing chat metrics, leads,
conversations, and transcripts. All endpoints are protected by token authentication.

Routes:
- GET /api/ahsuite/practices/{practice_id}/chat/metrics - KPI snapshot
- GET /api/ahsuite/practices/{practice_id}/chat/leads - Lead list
- GET /api/ahsuite/practices/{practice_id}/chat/conversations - Conversation list
- GET /api/ahsuite/practices/{practice_id}/chat/conversations/{conversation_id}/transcript - Chat transcript
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func, and_

from src.api.dependencies import require_client_token
from src.core.db import get_db
from src.models.models import Client, Conversation, ChatLog

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# Response Schemas
# =============================================================================

class MetricsResponse(BaseModel):
    """Response schema for the metrics endpoint."""
    conversations_started: int = Field(..., description="Total conversations in the period")
    leads_captured: int = Field(..., description="Conversations that captured a lead")
    lead_capture_rate: float = Field(..., description="Percentage of conversations that became leads")
    after_hours_conversations: int = Field(..., description="Conversations outside business hours")


class LeadSummary(BaseModel):
    """Summary of a captured lead."""
    conversation_id: str
    started_at: datetime
    patient_name: Optional[str] = None
    patient_phone: Optional[str] = None
    patient_email: Optional[str] = None
    reason_for_visit: Optional[str] = None
    delivery_status: Optional[str] = None
    topic_tag: Optional[str] = None


class LeadsResponse(BaseModel):
    """Response schema for the leads endpoint."""
    leads: List[LeadSummary]
    total: int
    page: int
    page_size: int


class ConversationSummary(BaseModel):
    """Summary of a conversation."""
    conversation_id: str
    started_at: datetime
    current_stage: str
    lead_captured: bool
    topic_tag: Optional[str] = None
    is_after_hours: bool = False
    message_count: int = 0


class ConversationsResponse(BaseModel):
    """Response schema for the conversations endpoint."""
    conversations: List[ConversationSummary]
    total: int
    page: int
    page_size: int


class TranscriptMessage(BaseModel):
    """A single message in the transcript."""
    sender_type: str = Field(..., description="'user' or 'bot'")
    message: str
    created_at: datetime


class TranscriptResponse(BaseModel):
    """Response schema for the transcript endpoint."""
    conversation_id: str
    messages: List[TranscriptMessage]
    total_messages: int


# =============================================================================
# Helper Functions
# =============================================================================

def verify_practice_access(client: Client, practice_id: UUID) -> None:
    """
    Verify that the authenticated client has access to the requested practice.

    For now, clients can only access their own data (client_id == practice_id).

    Args:
        client: The authenticated client
        practice_id: The practice ID being requested

    Raises:
        HTTPException: 403 if access is denied
    """
    if client.client_id != practice_id:
        logger.warning(
            f"Access denied: client {client.client_id} attempted to access practice {practice_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied to this practice's data"
        )


# =============================================================================
# API Endpoints
# =============================================================================

@router.get(
    "/practices/{practice_id}/chat/metrics",
    response_model=MetricsResponse,
    summary="Get Chat Metrics",
    description="Get KPI snapshot including conversation counts, lead capture rate, and after-hours stats."
)
async def get_metrics(
    practice_id: UUID,
    from_date: Optional[datetime] = Query(None, description="Start date for the report period"),
    to_date: Optional[datetime] = Query(None, description="End date for the report period"),
    client: Client = Depends(require_client_token),
    db: Session = Depends(get_db)
) -> MetricsResponse:
    """
    Get aggregated chat metrics for a practice.

    Args:
        practice_id: The UUID of the practice
        from_date: Optional start date filter (defaults to 30 days ago)
        to_date: Optional end date filter (defaults to now)
        client: The authenticated client
        db: Database session

    Returns:
        MetricsResponse with aggregated KPIs
    """
    verify_practice_access(client, practice_id)

    # Default date range: last 30 days
    if not to_date:
        to_date = datetime.utcnow()
    if not from_date:
        from_date = to_date - timedelta(days=30)

    logger.info(
        f"Fetching metrics for practice {practice_id}",
        extra={
            'practice_id': str(practice_id),
            'from_date': str(from_date),
            'to_date': str(to_date)
        }
    )

    # Base query filter
    date_filter = and_(
        Conversation.client_id == practice_id,
        Conversation.last_activity_at >= from_date,
        Conversation.last_activity_at <= to_date
    )

    # Total conversations
    conversations_started = db.query(func.count(Conversation.conversation_id)).filter(
        date_filter
    ).scalar() or 0

    # Leads captured
    leads_captured = db.query(func.count(Conversation.conversation_id)).filter(
        date_filter,
        Conversation.lead_captured == True
    ).scalar() or 0

    # After hours conversations
    after_hours_conversations = db.query(func.count(Conversation.conversation_id)).filter(
        date_filter,
        Conversation.is_after_hours == True
    ).scalar() or 0

    # Calculate lead capture rate
    lead_capture_rate = (leads_captured / conversations_started) if conversations_started > 0 else 0.0

    return MetricsResponse(
        conversations_started=conversations_started,
        leads_captured=leads_captured,
        lead_capture_rate=round(lead_capture_rate, 3),
        after_hours_conversations=after_hours_conversations
    )


@router.get(
    "/practices/{practice_id}/chat/leads",
    response_model=LeadsResponse,
    summary="Get Leads List",
    description="Get a paginated list of captured leads with contact information and delivery status."
)
async def get_leads(
    practice_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    from_date: Optional[datetime] = Query(None, description="Start date filter"),
    to_date: Optional[datetime] = Query(None, description="End date filter"),
    client: Client = Depends(require_client_token),
    db: Session = Depends(get_db)
) -> LeadsResponse:
    """
    Get a paginated list of captured leads.

    Args:
        practice_id: The UUID of the practice
        page: Page number (1-indexed)
        page_size: Number of items per page
        from_date: Optional start date filter
        to_date: Optional end date filter
        client: The authenticated client
        db: Database session

    Returns:
        LeadsResponse with paginated lead data
    """
    verify_practice_access(client, practice_id)

    # Default date range: last 30 days
    if not to_date:
        to_date = datetime.utcnow()
    if not from_date:
        from_date = to_date - timedelta(days=30)

    # Base query filter for leads
    base_filter = and_(
        Conversation.client_id == practice_id,
        Conversation.lead_captured == True,
        Conversation.last_activity_at >= from_date,
        Conversation.last_activity_at <= to_date
    )

    # Get total count
    total = db.query(func.count(Conversation.conversation_id)).filter(base_filter).scalar() or 0

    # Get paginated results
    offset = (page - 1) * page_size
    conversations = db.query(Conversation).filter(base_filter).order_by(
        Conversation.last_activity_at.desc()
    ).offset(offset).limit(page_size).all()

    # Transform to response format
    leads = []
    for conv in conversations:
        state = conv.conversation_state or {}
        leads.append(LeadSummary(
            conversation_id=str(conv.conversation_id),
            started_at=conv.last_activity_at,
            patient_name=state.get('name'),
            patient_phone=state.get('phone'),
            patient_email=state.get('email'),
            reason_for_visit=state.get('appointment_type'),
            delivery_status=conv.delivery_status,
            topic_tag=conv.topic_tag
        ))

    return LeadsResponse(
        leads=leads,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get(
    "/practices/{practice_id}/chat/conversations",
    response_model=ConversationsResponse,
    summary="Get Conversations List",
    description="Get a paginated list of all conversations with summary information."
)
async def get_conversations(
    practice_id: UUID,
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    from_date: Optional[datetime] = Query(None, description="Start date filter"),
    to_date: Optional[datetime] = Query(None, description="End date filter"),
    lead_only: bool = Query(False, description="Only show leads"),
    client: Client = Depends(require_client_token),
    db: Session = Depends(get_db)
) -> ConversationsResponse:
    """
    Get a paginated list of conversations.

    Args:
        practice_id: The UUID of the practice
        page: Page number (1-indexed)
        page_size: Number of items per page
        from_date: Optional start date filter
        to_date: Optional end date filter
        lead_only: If true, only return conversations that captured leads
        client: The authenticated client
        db: Database session

    Returns:
        ConversationsResponse with paginated conversation data
    """
    verify_practice_access(client, practice_id)

    # Default date range: last 30 days
    if not to_date:
        to_date = datetime.utcnow()
    if not from_date:
        from_date = to_date - timedelta(days=30)

    # Base query filter
    filters = [
        Conversation.client_id == practice_id,
        Conversation.last_activity_at >= from_date,
        Conversation.last_activity_at <= to_date
    ]

    if lead_only:
        filters.append(Conversation.lead_captured == True)

    base_filter = and_(*filters)

    # Get total count
    total = db.query(func.count(Conversation.conversation_id)).filter(base_filter).scalar() or 0

    # Get paginated results
    offset = (page - 1) * page_size
    conversations = db.query(Conversation).filter(base_filter).order_by(
        Conversation.last_activity_at.desc()
    ).offset(offset).limit(page_size).all()

    # Get message counts for each conversation
    conversation_ids = [conv.conversation_id for conv in conversations]
    message_counts = {}
    if conversation_ids:
        counts = db.query(
            ChatLog.conversation_id,
            func.count(ChatLog.log_id).label('count')
        ).filter(
            ChatLog.conversation_id.in_(conversation_ids)
        ).group_by(ChatLog.conversation_id).all()
        message_counts = {str(c[0]): c[1] for c in counts}

    # Transform to response format
    result = []
    for conv in conversations:
        result.append(ConversationSummary(
            conversation_id=str(conv.conversation_id),
            started_at=conv.last_activity_at,
            current_stage=conv.current_stage,
            lead_captured=conv.lead_captured or False,
            topic_tag=conv.topic_tag,
            is_after_hours=conv.is_after_hours or False,
            message_count=message_counts.get(str(conv.conversation_id), 0)
        ))

    return ConversationsResponse(
        conversations=result,
        total=total,
        page=page,
        page_size=page_size
    )


@router.get(
    "/practices/{practice_id}/chat/conversations/{conversation_id}/transcript",
    response_model=TranscriptResponse,
    summary="Get Conversation Transcript",
    description="Get the full message transcript for a specific conversation."
)
async def get_transcript(
    practice_id: UUID,
    conversation_id: UUID,
    client: Client = Depends(require_client_token),
    db: Session = Depends(get_db)
) -> TranscriptResponse:
    """
    Get the full transcript of a conversation.

    Args:
        practice_id: The UUID of the practice
        conversation_id: The UUID of the conversation
        client: The authenticated client
        db: Database session

    Returns:
        TranscriptResponse with all messages

    Raises:
        HTTPException: 404 if conversation not found
    """
    verify_practice_access(client, practice_id)

    # Verify conversation belongs to this practice
    conversation = db.query(Conversation).filter(
        Conversation.conversation_id == conversation_id,
        Conversation.client_id == practice_id
    ).first()

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Get all messages
    messages = db.query(ChatLog).filter(
        ChatLog.conversation_id == conversation_id
    ).order_by(ChatLog.created_at.asc()).all()

    transcript = [
        TranscriptMessage(
            sender_type=msg.sender_type,
            message=msg.message,
            created_at=msg.created_at
        )
        for msg in messages
    ]

    logger.info(
        f"Transcript retrieved for conversation {conversation_id}",
        extra={
            'practice_id': str(practice_id),
            'conversation_id': str(conversation_id),
            'message_count': len(transcript)
        }
    )

    return TranscriptResponse(
        conversation_id=str(conversation_id),
        messages=transcript,
        total_messages=len(transcript)
    )
