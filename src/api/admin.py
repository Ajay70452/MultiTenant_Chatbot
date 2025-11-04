from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Dict, Any
import uuid

from src.models.models import Conversation
from src.core.db import get_db

admin_router = APIRouter()

@admin_router.get("/leads/{client_id}", response_model=List[Dict[str, Any]])
def get_finalized_leads(client_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieves all finalized conversations (leads) for a specific client.
    This provides a simple way to see all captured leads for follow-up.
    """
    try:
        leads = db.query(Conversation).filter(
            Conversation.client_id == client_id,
            Conversation.is_finalized == True
        ).order_by(Conversation.finalized_at.desc()).all()
        
        if not leads:
            return []
        
        return [
            {
                "conversation_id": str(lead.conversation_id),
                "final_state": lead.conversation_state,
                "finalized_at": lead.finalized_at.isoformat() if lead.finalized_at else None
            } for lead in leads
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {e}")