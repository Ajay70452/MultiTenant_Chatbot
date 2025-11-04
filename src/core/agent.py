from typing import Dict, Optional, AsyncGenerator
import json

from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from src.core.config import OPENAI_API_KEY
from src.core.prompt import SYSTEM_PROMPT


class AgentResponse(BaseModel):
    """Structured response returned by the agent.

    - response_text: The message to show the user.
    - updated_details: Any newly extracted details like name, phone, email, service.
    - user_confirmed: True only when user explicitly confirms details while in CONFIRMING_DETAILS stage.
    """
    response_text: str = Field(..., description="Message for the user")
    updated_details: Dict[str, Optional[str]] = Field(
        default_factory=dict,
        description="Extracted fields such as name, phone, email, service"
    )
    user_confirmed: Optional[bool] = Field(
        default=False,
        description="Set to true only when user explicitly confirms details in CONFIRMING_DETAILS stage"
    )
    next_stage: str = Field(
        default="",
        description="The next stage of the conversation, as determined by the agent."
    )
    confidence_score: float = Field(
        default=0.0,
        description="A float value between 0 and 1 indicating the agent's confidence in its response."
    )


import logging

logger = logging.getLogger(__name__)

async def get_agent_response(stage: str, state: dict, history: list, user_message: str, context: str):
    """Returns a dict with keys: response_text, updated_details, user_confirmed.

    Uses LangChain structured output to avoid JSON parsing errors.
    Async version to prevent blocking when handling multiple concurrent users.
    """
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, openai_api_key=OPENAI_API_KEY)
    structured_llm = llm.with_structured_output(AgentResponse, method='function_calling')

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            SYSTEM_PROMPT,
        ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{user_message}"),
    ])

    chain = prompt | structured_llm

    try:
        raw_result = await chain.ainvoke(
            {
                "stage": stage,
                "state": json.dumps(state),
                "context": context or "",
                "history": history or [],
                "user_message": user_message,
            }
        )
        logger.info(f"Raw LLM output: {raw_result}")
        if isinstance(raw_result, AgentResponse):
            response_dict = raw_result.dict()
        else:
            response_dict = dict(raw_result)
        logger.info(f"Parsed AgentResponse: {response_dict}")
        # TODO: Implement a proper confidence score calculation
        response_dict['confidence_score'] = 0.9
        return response_dict
    except Exception as e:
        logger.error(f"ERROR in agent.py: Could not get structured output. Error: {e}")
        return {
            "response_text": "I'm sorry, I'm having a little trouble right now. Could you please rephrase that?",
            "updated_details": {},
            "user_confirmed": False,
        }

async def get_agent_response_stream(stage: str, state: dict, history: list, user_message: str, context: str) -> AsyncGenerator[str, None]:
    """Returns a generator that yields the response tokens."""
    llm = ChatOpenAI(model="gpt-4-turbo", temperature=0, openai_api_key=OPENAI_API_KEY)

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            SYSTEM_PROMPT,
        ),
        MessagesPlaceholder(variable_name="history"),
        ("human", "{user_message}"),
    ])

    chain = prompt | llm

    try:
        async for chunk in chain.astream(
            {
                "stage": stage,
                "state": json.dumps(state),
                "context": context or "",
                "history": history or [],
                "user_message": user_message,
            }
        ):
            yield chunk.content
    except Exception as e:
        logger.error(f"ERROR in agent.py: Could not get stream output. Error: {e}")
        yield "I'm sorry, I'm having a little trouble right now. Could you please rephrase that?"