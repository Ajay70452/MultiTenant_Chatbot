"""
Agent Module - Prompt Factory Pattern

This module provides LLM agent functionality for both:
- Patient Concierge (Door 1): Appointment booking with state machine
- Clinical Advisor (Door 2): Doctor-facing clinical assistant

The Prompt Factory pattern allows different prompts and response formats
based on the agent type being invoked.
"""

import json
import logging
from enum import Enum
from typing import Dict, Optional, AsyncGenerator, List

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from src.core.config import OPENAI_API_KEY
from src.core.prompts.patient import build_patient_prompt, PATIENT_SYSTEM_PROMPT
from src.core.prompts.clinical import build_clinical_prompt
from src.core.image_utils import (
    validate_base64_image,
    normalize_image_data,
    build_multimodal_content,
    get_image_size_kb
)

logger = logging.getLogger(__name__)


# =============================================================================
# Enums
# =============================================================================

class AgentType(str, Enum):
    """Types of agents available in the system."""
    PATIENT = "patient"      # Door 1: Patient Concierge
    CLINICAL = "clinical"    # Door 2: Clinical Advisor


# =============================================================================
# Response Models
# =============================================================================

class PatientAgentResponse(BaseModel):
    """Structured response for the Patient Concierge agent.

    Used for appointment booking with state machine logic.
    """
    response_text: str = Field(..., description="Message for the user")
    updated_details: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Extracted fields such as name, phone, email, service"
    )
    user_confirmed: Optional[bool] = Field(
        default=False,
        description="Set to true only when user explicitly confirms details"
    )
    next_stage: str = Field(
        default="",
        description="The next stage of the conversation"
    )
    confidence_score: float = Field(
        default=0.0,
        description="Confidence score between 0 and 1"
    )


class ClinicalAgentResponse(BaseModel):
    """Structured response for the Clinical Advisor agent.

    Used for doctor-facing clinical guidance (stateless).
    """
    response_text: str = Field(..., description="Clinical guidance for the doctor")
    confidence_level: str = Field(
        default="moderate",
        description="Confidence in the response: low, moderate, high"
    )
    requires_referral: bool = Field(
        default=False,
        description="Whether the case may require specialist referral"
    )
    safety_warnings: List[str] = Field(
        default_factory=list,
        description="Any safety concerns or warnings to highlight"
    )


# =============================================================================
# Legacy Response Model (for backward compatibility)
# =============================================================================

# Alias for backward compatibility with existing code
AgentResponse = PatientAgentResponse


# =============================================================================
# Patient Concierge Agent (Door 1)
# =============================================================================

async def get_agent_response(
    stage: str,
    state: dict,
    history: list,
    user_message: str,
    context: str
) -> dict:
    """
    Get response from the Patient Concierge agent (Door 1).

    This is the original agent function, maintained for backward compatibility.
    Uses state machine logic for appointment booking.

    Args:
        stage: Current conversation stage
        state: Current conversation state dict
        history: List of previous messages
        user_message: The user's current message
        context: RAG context from Pinecone

    Returns:
        Dict with response_text, updated_details, user_confirmed, next_stage
    """
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, openai_api_key=OPENAI_API_KEY)
    structured_llm = llm.with_structured_output(PatientAgentResponse, method='function_calling')

    prompt = ChatPromptTemplate.from_messages([
        ("system", PATIENT_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{user_message}"),
    ])

    chain = prompt | structured_llm

    try:
        raw_result = await chain.ainvoke({
            "stage": stage,
            "state": json.dumps(state),
            "context": context or "",
            "history": history or [],
            "user_message": user_message,
        })

        logger.info(f"Raw LLM output: {raw_result}")

        if isinstance(raw_result, PatientAgentResponse):
            response_dict = raw_result.model_dump()
        else:
            response_dict = dict(raw_result)

        logger.info(f"Parsed AgentResponse: {response_dict}")
        response_dict['confidence_score'] = 0.9

        return response_dict

    except Exception as e:
        logger.error(f"ERROR in agent.py: Could not get structured output. Error: {e}")
        return {
            "response_text": "I'm sorry, I'm having a little trouble right now. Could you please rephrase that?",
            "updated_details": {},
            "user_confirmed": False,
            "next_stage": stage,
        }


# =============================================================================
# Clinical Advisor Agent (Door 2)
# =============================================================================

async def get_clinical_response(
    user_message: str,
    practice_profile: Optional[dict] = None,
    conversation_history: Optional[List[dict]] = None,
    image_base64: Optional[str] = None,
    rag_context: Optional[str] = None,
    clinic_name: Optional[str] = None
) -> dict:
    """
    Get response from the Clinical Advisor agent (Door 2).

    This agent provides clinical guidance to doctors. It is stateless
    and uses both the practice profile and RAG context for responses.

    Key differences from Patient Concierge:
    - NO state machine - stateless, free-flow conversation
    - NO stage transitions
    - Uses practice profile + RAG context from Pinecone
    - Supports multi-modal input (text + images)

    Args:
        user_message: The doctor's question or message
        practice_profile: The doctor's practice profile JSON
        conversation_history: List of previous messages (stateless - client provides)
        image_base64: Optional Base64-encoded image for analysis
        rag_context: Retrieved context from Pinecone RAG
        clinic_name: The name of the clinic/practice

    Returns:
        Dict with response_text, confidence_level, requires_referral, safety_warnings
    """
    # Validate and process image if provided
    has_valid_image = False
    normalized_image = None

    if image_base64:
        is_valid, mime_type, error_msg = validate_base64_image(image_base64)
        if is_valid:
            has_valid_image = True
            normalized_image = normalize_image_data(image_base64)
            image_size = get_image_size_kb(image_base64)
            logger.info(
                f"Processing clinical request with image",
                extra={
                    "mime_type": mime_type,
                    "image_size_kb": image_size
                }
            )
        else:
            logger.warning(f"Invalid image data provided: {error_msg}")
            # Continue without image rather than failing
            has_valid_image = False

    # Build the clinical system prompt with practice profile and RAG context
    system_prompt = build_clinical_prompt(
        practice_profile=practice_profile,
        conversation_history=conversation_history,
        rag_context=rag_context,
        clinic_name=clinic_name
    )

    # Choose model based on whether we have a valid image
    if has_valid_image:
        # Use GPT-4o for vision capabilities
        llm = ChatOpenAI(
            model="gpt-4o",
            temperature=0.1,
            openai_api_key=OPENAI_API_KEY,
            max_tokens=4096  # Allow longer responses for detailed clinical analysis
        )
        use_structured = False
    else:
        # Text-only: Use GPT-4-turbo with structured output
        llm = ChatOpenAI(
            model="gpt-4-turbo",
            temperature=0.1,
            openai_api_key=OPENAI_API_KEY
        )
        use_structured = True

    try:
        if use_structured:
            # Text-only: Use structured output for consistent response format
            structured_llm = llm.with_structured_output(
                ClinicalAgentResponse,
                method='function_calling'
            )

            # Build conversation messages
            messages = [("system", system_prompt)]

            # Add conversation history if provided (limit to last 10 for context window)
            if conversation_history:
                for msg in conversation_history[-10:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        messages.append(("human", content))
                    else:
                        messages.append(("assistant", content))

            messages.append(("human", "{user_message}"))

            prompt = ChatPromptTemplate.from_messages(messages)
            chain = prompt | structured_llm

            raw_result = await chain.ainvoke({"user_message": user_message})

            if isinstance(raw_result, ClinicalAgentResponse):
                response_dict = raw_result.model_dump()
            else:
                response_dict = dict(raw_result)

        else:
            # With image: Use vision model with multimodal content
            messages = [SystemMessage(content=system_prompt)]

            # Add conversation history
            if conversation_history:
                for msg in conversation_history[-10:]:
                    role = msg.get("role", "user")
                    content = msg.get("content", "")
                    if role == "user":
                        messages.append(HumanMessage(content=content))
                    else:
                        messages.append(AIMessage(content=content))

            # Build multimodal content with text and image
            multimodal_content = build_multimodal_content(
                text=user_message,
                images=[normalized_image] if normalized_image else None,
                image_detail="high"  # Use high detail for clinical images
            )
            messages.append(HumanMessage(content=multimodal_content))

            # Invoke the model
            raw_result = await llm.ainvoke(messages)

            # Parse unstructured response and extract metadata
            response_dict = _parse_clinical_response(raw_result.content)

        logger.info(
            f"Clinical response generated",
            extra={
                "confidence_level": response_dict.get("confidence_level"),
                "requires_referral": response_dict.get("requires_referral"),
                "has_image": has_valid_image,
                "safety_warnings_count": len(response_dict.get("safety_warnings", []))
            }
        )

        return response_dict

    except Exception as e:
        logger.error(f"ERROR in clinical agent: {e}", exc_info=True)
        return {
            "response_text": "I apologize, but I'm having difficulty processing your request. Please try rephrasing your question or contact support if the issue persists.",
            "confidence_level": "low",
            "requires_referral": False,
            "safety_warnings": ["Response generated after error - please verify independently"]
        }


def _parse_clinical_response(response_text: str) -> dict:
    """
    Parse an unstructured clinical response and extract metadata.

    This is used when we can't use structured output (e.g., with images).
    We analyze the response text to infer confidence, referral needs, etc.

    Args:
        response_text: The raw response from the LLM

    Returns:
        Dict with response_text, confidence_level, requires_referral, safety_warnings
    """
    response_lower = response_text.lower()
    safety_warnings = []

    # Detect referral recommendations
    referral_keywords = [
        "refer", "specialist", "oral surgeon", "endodontist",
        "periodontist", "orthodontist", "prosthodontist",
        "beyond the scope", "seek specialist"
    ]
    requires_referral = any(kw in response_lower for kw in referral_keywords)

    # Detect urgency/emergency
    emergency_keywords = [
        "emergency", "urgent", "immediately", "as soon as possible",
        "critical", "life-threatening", "hospital", "er ", "a&e"
    ]
    if any(kw in response_lower for kw in emergency_keywords):
        safety_warnings.append("Urgent attention may be required")

    # Detect uncertainty expressions
    uncertainty_keywords = [
        "difficult to determine", "cannot be certain", "limited view",
        "unclear", "inconclusive", "further imaging", "additional tests"
    ]
    if any(kw in response_lower for kw in uncertainty_keywords):
        safety_warnings.append("Clinical correlation recommended due to limitations")

    # Infer confidence level
    high_confidence_keywords = ["clearly", "definitely", "certainly", "consistent with"]
    low_confidence_keywords = ["possibly", "might be", "unclear", "difficult to"]

    if any(kw in response_lower for kw in low_confidence_keywords):
        confidence_level = "low"
    elif any(kw in response_lower for kw in high_confidence_keywords):
        confidence_level = "high"
    else:
        confidence_level = "moderate"

    return {
        "response_text": response_text,
        "confidence_level": confidence_level,
        "requires_referral": requires_referral,
        "safety_warnings": safety_warnings
    }


# =============================================================================
# Streaming Support (Patient Concierge)
# =============================================================================

async def get_agent_response_stream(
    stage: str,
    state: dict,
    history: list,
    user_message: str,
    context: str
) -> AsyncGenerator[str, None]:
    """
    Returns a generator that yields response tokens for streaming.

    This is for the Patient Concierge agent (Door 1).
    """
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, openai_api_key=OPENAI_API_KEY)

    prompt = ChatPromptTemplate.from_messages([
        ("system", PATIENT_SYSTEM_PROMPT),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{user_message}"),
    ])

    chain = prompt | llm

    try:
        async for chunk in chain.astream({
            "stage": stage,
            "state": json.dumps(state),
            "context": context or "",
            "history": history or [],
            "user_message": user_message,
        }):
            yield chunk.content
    except Exception as e:
        logger.error(f"ERROR in agent.py: Could not get stream output. Error: {e}")
        yield "I'm sorry, I'm having a little trouble right now. Could you please rephrase that?"


# =============================================================================
# Prompt Factory (Unified Interface)
# =============================================================================

class PromptFactory:
    """
    Factory class for building prompts based on agent type.

    Usage:
        factory = PromptFactory(AgentType.CLINICAL)
        response = await factory.get_response(message, **kwargs)
    """

    def __init__(self, agent_type: AgentType):
        self.agent_type = agent_type

    async def get_response(self, user_message: str, **kwargs) -> dict:
        """
        Get a response from the appropriate agent.

        Args:
            user_message: The user's message
            **kwargs: Additional arguments specific to the agent type

        For PATIENT agent:
            - stage: Current conversation stage
            - state: Current conversation state
            - history: Conversation history
            - context: RAG context

        For CLINICAL agent:
            - practice_profile: Doctor's practice profile
            - conversation_history: Previous messages
            - image_base64: Optional image for analysis

        Returns:
            Response dict from the appropriate agent
        """
        if self.agent_type == AgentType.PATIENT:
            return await get_agent_response(
                stage=kwargs.get("stage", "GREETING"),
                state=kwargs.get("state", {}),
                history=kwargs.get("history", []),
                user_message=user_message,
                context=kwargs.get("context", "")
            )
        elif self.agent_type == AgentType.CLINICAL:
            return await get_clinical_response(
                user_message=user_message,
                practice_profile=kwargs.get("practice_profile"),
                conversation_history=kwargs.get("conversation_history"),
                image_base64=kwargs.get("image_base64"),
                rag_context=kwargs.get("rag_context"),
                clinic_name=kwargs.get("clinic_name")
            )
        else:
            raise ValueError(f"Unknown agent type: {self.agent_type}")
