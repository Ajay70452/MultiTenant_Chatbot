from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from src.schemas.chat import ChatRequest, ChatResponse
import uuid
import logging

from src.core import state_manager, rag_engine, agent
from src.core.db import get_db
from src.services import webhook_routing_service

router = APIRouter()

@router.post("/chat", response_model=ChatResponse)
async def handle_chat_message(request: ChatRequest, db: Session = Depends(get_db)):
    conversation_id = request.conversation_id or uuid.uuid4()

    conversation = state_manager.load_or_create_conversation(db, conversation_id, request.client_id)
    history = state_manager.get_conversation_history(db, conversation_id)
    state_manager.log_message(db, conversation_id, 'user', request.message)

    context = ""
    if conversation.current_stage in ['GREETING', 'ANSWERING_QUESTION']:
        context = rag_engine.get_relevant_context(request.message, str(request.client_id))

    agent_output = await agent.get_agent_response(
        stage=conversation.current_stage,
        state=conversation.conversation_state,
        history=history,
        user_message=request.message,
        context=context
    )

    logger = logging.getLogger(__name__)
    logger = logging.getLogger(__name__)
    logger.info(
        f"Agent Output for Stage '{conversation.current_stage}': {agent_output}",
        extra={'conversation_id': str(conversation_id), 'client_id': request.client_id, 'confidence_score': agent_output.get('confidence_score')}
    )

    response_text = agent_output.get("response_text", "I'm sorry, I had trouble processing that.")
    updated_details = agent_output.get("updated_details", {})
    
    current_state = dict(conversation.conversation_state)
    current_state.update({k: v for k, v in updated_details.items() if v is not None})

    next_stage = agent_output.get("next_stage") or conversation.current_stage
    previous_stage = conversation.current_stage
    
    state_manager.save_state(db, conversation_id, next_stage, current_state)
    conversation.current_stage = next_stage

    if next_stage == 'CLOSING' and previous_stage != 'CLOSING':
        logger.info(f"Attempting to finalize conversation and route webhook.", extra={'conversation_id': str(conversation_id), 'client_id': request.client_id})
        logger.info(f"Current state being sent to webhook: {current_state}", extra={'conversation_id': str(conversation_id), 'client_id': request.client_id})
        # Persist finalization first
        state_manager.finalize_conversation(db, conversation_id)
        # Re-fetch conversation from DB to ensure we use the persisted state
        persisted_conversation = state_manager.get_conversation_by_id(db, conversation_id)
        persisted_state = persisted_conversation.conversation_state if persisted_conversation else {}
        logger.info(f"Persisted state fetched for webhook: {persisted_state}", extra={'conversation_id': str(conversation_id), 'client_id': request.client_id})
        await webhook_routing_service.route_via_webhook(
            client_id=str(request.client_id),
            conversation_id=str(conversation_id),
            lead_details=persisted_state
        )
        logger.info(f"Finished finalizing conversation and routing webhook.", extra={'conversation_id': str(conversation_id), 'client_id': request.client_id})

    state_manager.log_message(db, conversation_id, 'bot', response_text)

    return ChatResponse(conversation_id=conversation_id, response=response_text)