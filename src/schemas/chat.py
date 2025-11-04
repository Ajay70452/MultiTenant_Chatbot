from pydantic import BaseModel
from typing import Optional
import uuid

class ChatRequest(BaseModel):
    conversation_id: Optional[uuid.UUID] = None
    client_id: uuid.UUID
    message: str

class ChatResponse(BaseModel):
    conversation_id: uuid.UUID
    response: str