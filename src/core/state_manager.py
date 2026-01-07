import datetime
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy.orm import Session
from langchain_core.messages import HumanMessage, AIMessage

from src.models.models import Conversation, ChatLog, PracticeProfile
from src.services.data_export import simple_data_exporter

logger = logging.getLogger(__name__)

def is_after_hours() -> bool:
    """
    Check if the current time is outside business hours.
    Business hours: 9 AM - 5 PM (local time, assumed UTC for now)
    """
    now = datetime.datetime.utcnow()
    hour = now.hour
    # After hours = before 9 AM or after 5 PM, or on weekends
    is_weekend = now.weekday() >= 5  # Saturday = 5, Sunday = 6
    is_outside_hours = hour < 9 or hour >= 17
    return is_weekend or is_outside_hours

def simple_data_exporter(conversation: Conversation):
    """
    A simple placeholder for exporting finalized lead data.
    In a real system, this would send an email, post to a webhook, or save to a CRM.
    """
    log_data = {
        'conversation_id': str(conversation.conversation_id),
        'client_id': str(conversation.client_id),
        'finalized_at': conversation.finalized_at.isoformat(),
        'collected_data': conversation.conversation_state
    }
    logger.info("LEAD FINALIZED", extra=log_data)

def finalize_conversation(db: Session, conversation_id: str):
    """
    Flags a conversation as finalized, captures the timestamp, and triggers data export.
    """
    try:
        conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
        
        if conversation and not conversation.is_finalized:
            logger.info(f"Conversation before finalize: {conversation.conversation_state}", extra={'conversation_id': conversation_id})
            conversation.is_finalized = True
            conversation.lead_captured = True  # Mark lead as captured for reporting
            conversation.finalized_at = datetime.datetime.utcnow()
            db.commit()
            db.refresh(conversation)
            
            logger.info(f"Finalizing conversation and exporting data...", extra={'conversation_id': conversation_id})
            simple_data_exporter(conversation)
            return True
    except Exception as e:
        logger.error(f"ERROR in finalize_conversation: {e}", extra={'conversation_id': conversation_id})
        db.rollback()
        return False

def load_or_create_conversation(db: Session, conversation_id: str, client_id: str):
    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    if not conversation:
        conversation = Conversation(
            conversation_id=conversation_id,
            client_id=client_id,
            current_stage='GREETING',
            is_after_hours=is_after_hours(),  # Track if conversation started outside business hours
            conversation_state={
                'name': None,
                'phone': None,
                'email': None,
                'service': None,
                'appointment_type': None,
                'last_visit': None,
                'preferred_date': None,
                'preferred_time': None
            }
        )
        db.add(conversation)
        db.commit()
        db.refresh(conversation)
    return conversation

def get_conversation_by_id(db: Session, conversation_id: str):
    """Get an existing conversation by ID without creating a new one."""
    return db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()

def save_state(db: Session, conversation_id: str, stage: str, state: dict):
    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    if conversation:
        logger.info(f"Saving state for conversation {conversation_id}: {state}", extra={'conversation_id': conversation_id})
        conversation.current_stage = stage
        conversation.conversation_state = state
        db.commit()
        logger.info(f"Saved state for conversation {conversation_id}", extra={'conversation_id': conversation_id})

def get_conversation_history(db: Session, conversation_id: str, limit: int = 10):
    logs = db.query(ChatLog).filter(ChatLog.conversation_id == conversation_id).order_by(ChatLog.created_at.desc()).limit(limit).all()
    history = []
    for log in reversed(logs): # reverse to get chronological order
        if log.sender_type == 'user':
            history.append(HumanMessage(content=log.message))
        else:
            history.append(AIMessage(content=log.message))
    return history

def log_message(db: Session, conversation_id: str, sender: str, message: str):
    log = ChatLog(
        conversation_id=conversation_id,
        sender_type=sender,
        message=message
    )
    db.add(log)
    db.commit()


# =============================================================================
# Practice Profile Functions (for Clinical Advisor)
# =============================================================================

def get_practice_profile(db: Session, client_id: UUID) -> Optional[dict]:
    """
    Load the practice profile JSON for a given client.

    This retrieves the "Brain" data that contains the doctor's clinical philosophy,
    treatment preferences, and other practice-specific information used by the
    Clinical Advisor agent.

    Args:
        db: Database session
        client_id: The UUID of the client whose profile to load

    Returns:
        The profile_json dict if found, None if no profile exists for this client
    """
    profile = db.query(PracticeProfile).filter(
        PracticeProfile.practice_id == client_id
    ).first()

    if not profile:
        logger.warning(f"No practice profile found for client: {client_id}")
        return None

    logger.info(f"Loaded practice profile for client: {client_id}")
    return profile.profile_json


def create_or_update_practice_profile(
    db: Session,
    client_id: UUID,
    profile_json: dict
) -> PracticeProfile:
    """
    Create or update the practice profile for a client.

    Args:
        db: Database session
        client_id: The UUID of the client
        profile_json: The practice profile data to store

    Returns:
        The created or updated PracticeProfile object
    """
    profile = db.query(PracticeProfile).filter(
        PracticeProfile.practice_id == client_id
    ).first()

    if profile:
        # Update existing profile
        profile.profile_json = profile_json
        profile.updated_at = datetime.datetime.utcnow()
        logger.info(f"Updated practice profile for client: {client_id}")
    else:
        # Create new profile
        profile = PracticeProfile(
            practice_id=client_id,
            profile_json=profile_json
        )
        db.add(profile)
        logger.info(f"Created practice profile for client: {client_id}")

    db.commit()
    db.refresh(profile)
    return profile


def delete_practice_profile(db: Session, client_id: UUID) -> bool:
    """
    Delete the practice profile for a client.

    Args:
        db: Database session
        client_id: The UUID of the client whose profile to delete

    Returns:
        True if a profile was deleted, False if no profile existed
    """
    profile = db.query(PracticeProfile).filter(
        PracticeProfile.practice_id == client_id
    ).first()

    if not profile:
        logger.warning(f"No practice profile to delete for client: {client_id}")
        return False

    db.delete(profile)
    db.commit()
    logger.info(f"Deleted practice profile for client: {client_id}")
    return True