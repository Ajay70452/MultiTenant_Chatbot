import datetime
import logging
from sqlalchemy.orm import Session
from src.models.models import Conversation, ChatLog
from langchain_core.messages import HumanMessage, AIMessage
from src.services.data_export import simple_data_exporter

logger = logging.getLogger(__name__)

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