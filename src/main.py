from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from src.api.chat import router as chat_router
from src.api.admin import admin_router
from src.api.clinical import router as clinical_router
from src.api.reporting import router as reporting_router
from fastapi.middleware.cors import CORSMiddleware
from src.core.config import ALLOWED_ORIGINS
from src.core.logging_config import setup_logging
from fastapi.responses import FileResponse
from src.models.models import Conversation
import os
from pathlib import Path

setup_logging()

app = FastAPI(title="Dental Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS.split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api", tags=["Chat"])
app.include_router(admin_router, prefix="/api/admin", tags=["Admin"])
app.include_router(clinical_router, prefix="/api/clinical", tags=["Clinical Advisor"])
app.include_router(reporting_router, prefix="/api/ahsuite", tags=["Reporting Dashboard"])

# Mount static files for frontends
BASE_DIR = Path(__file__).parent.parent
FRONTENDS_DIR = BASE_DIR / "frontends"

if FRONTENDS_DIR.exists():
    app.mount("/frontends", StaticFiles(directory=str(FRONTENDS_DIR)), name="frontends")

@app.get("/")
def read_root():
    return {"status": "API is running"}

from fastapi.responses import HTMLResponse

@app.get("/logs")
def get_logs():
    return FileResponse('chatbot.log')

@app.get("/clear-logs")
def clear_logs():
    with open('chatbot.log', 'w'):
        pass
    return {"status": "Logs cleared"}

from src.services import webhook_routing_service

@app.get("/view-logs")
def view_logs():
    with open('chatbot.log', 'r') as f:
        logs = f.read()
    return HTMLResponse(f"<pre>{logs}</pre>")

from src.core.db import get_db, wait_for_db


@app.on_event("startup")
def on_startup():
    # wait for DB to be ready before serving requests
    wait_for_db(retries=10, delay=1.0)

@app.get("/test-webhook")
async def test_webhook(client_id: str):
    await webhook_routing_service.route_via_webhook(client_id, "test-conversation", {"test": "payload"})
    return {"status": "Test payload sent"}

@app.get("/status")
def get_status():
    try:
        db = next(get_db())
        db.execute("SELECT 1")
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}" 
    finally:
        db.close()
    return {"api_status": "ok", "db_status": db_status}

from src.core.config import OPENAI_API_KEY, ALLOWED_ORIGINS

@app.get("/version")
def get_version():
    return {"version": "1.0.0"}

from src.models.models import Client

@app.get("/config")
def get_config():
    return {
        "allowed_origins": ALLOWED_ORIGINS,
        "openai_api_key_set": "Yes" if OPENAI_API_KEY else "No"
    }

@app.get("/clients")
def get_clients():
    db = next(get_db())
    clients = db.query(Client).all()
    db.close()
    return {"clients": [client.client_id for client in clients]}

@app.get("/client-details/{client_id}")
def get_client_details(client_id: str):
    db = next(get_db())
    client = db.query(Client).filter(Client.client_id == client_id).first()
    db.close()
    if client:
        return {"client_id": client.client_id, "lead_webhook_url": client.lead_webhook_url}
    else:
        return {"error": "Client not found"}

@app.get("/conversations")
def get_conversations():
    db = next(get_db())
    conversations = db.query(Conversation).all()
    db.close()
    return {"conversations": [conversation.conversation_id for conversation in conversations]}

from src.core.state_manager import get_conversation_history

@app.get("/conversation/{conversation_id}")
def get_conversation(conversation_id: str):
    db = next(get_db())
    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id).first()
    db.close()
    if conversation:
        return {
            "conversation_id": conversation.conversation_id,
            "client_id": conversation.client_id,
            "current_stage": conversation.current_stage,
            "conversation_state": conversation.conversation_state,
            "is_finalized": conversation.is_finalized,
            "finalized_at": conversation.finalized_at
        }
    else:
        return {"error": "Conversation not found"}

from src.models.models import ChatLog

@app.get("/chat-history/{conversation_id}")
def get_chat_history(conversation_id: str):
    db = next(get_db())
    history = get_conversation_history(db, conversation_id)
    db.close()
    return {"chat_history": [message.content for message in history]}

@app.get("/chat-logs")
def get_chat_logs():
    db = next(get_db())
    logs = db.query(ChatLog).all()
    db.close()
    return {"chat_logs": [log.message for log in logs]}

from src.models.models import Client

@app.get("/chat-log/{log_id}")
def get_chat_log(log_id: int):
    db = next(get_db())
    log = db.query(ChatLog).filter(ChatLog.id == log_id).first()
    db.close()
    if log:
        return {
            "id": log.id,
            "conversation_id": log.conversation_id,
            "sender_type": log.sender_type,
            "message": log.message,
            "created_at": log.created_at
        }
    else:
        return {"error": "Chat log not found"}

@app.get("/webhooks")
def get_webhooks():
    db = next(get_db())
    clients = db.query(Client).all()
    db.close()
    return {"webhooks": [client.lead_webhook_url for client in clients]}

@app.get("/finalized-conversations")
def get_finalized_conversations():
    db = next(get_db())
    conversations = db.query(Conversation).filter(Conversation.is_finalized == True).all()
    db.close()
    return {"finalized_conversations": [conversation.conversation_id for conversation in conversations]}

@app.get("/finalized-conversation/{conversation_id}")
def get_finalized_conversation(conversation_id: str):
    db = next(get_db())
    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id, Conversation.is_finalized == True).first()
    db.close()
    if conversation:
        return {
            "conversation_id": conversation.conversation_id,
            "client_id": conversation.client_id,
            "current_stage": conversation.current_stage,
            "conversation_state": conversation.conversation_state,
            "is_finalized": conversation.is_finalized,
            "finalized_at": conversation.finalized_at
        }
    else:
        return {"error": "Finalized conversation not found"}

@app.get("/unfinalized-conversations")
def get_unfinalized_conversations():
    db = next(get_db())
    conversations = db.query(Conversation).filter(Conversation.is_finalized == False).all()
    db.close()
    return {"unfinalized_conversations": [conversation.conversation_id for conversation in conversations]}

from src.models.models import WebhookFailure

@app.get("/unfinalized-conversation/{conversation_id}")
def get_unfinalized_conversation(conversation_id: str):
    db = next(get_db())
    conversation = db.query(Conversation).filter(Conversation.conversation_id == conversation_id, Conversation.is_finalized == False).first()
    db.close()
    if conversation:
        return {
            "conversation_id": conversation.conversation_id,
            "client_id": conversation.client_id,
            "current_stage": conversation.current_stage,
            "conversation_state": conversation.conversation_state,
            "is_finalized": conversation.is_finalized,
            "finalized_at": conversation.finalized_at
        }
    else:
        return {"error": "Unfinalized conversation not found"}

@app.get("/failed-webhooks")
def get_failed_webhooks():
    db = next(get_db())
    failures = db.query(WebhookFailure).all()
    db.close()
    return {"failed_webhooks": [failure.id for failure in failures]}

from src.models.models import WebhookSuccess

@app.get("/failed-webhook/{failure_id}")
def get_failed_webhook(failure_id: int):
    db = next(get_db())
    failure = db.query(WebhookFailure).filter(WebhookFailure.id == failure_id).first()
    db.close()
    if failure:
        return {
            "id": failure.id,
            "client_id": failure.client_id,
            "conversation_id": failure.conversation_id,
            "payload": failure.payload,
            "response_status_code": failure.response_status_code,
            "response_text": failure.response_text,
            "created_at": failure.created_at
        }
    else:
        return {"error": "Failed webhook not found"}

@app.get("/successful-webhooks")
def get_successful_webhooks():
    db = next(get_db())
    successes = db.query(WebhookSuccess).all()
    db.close()
    return {"successful_webhooks": [success.id for success in successes]}

@app.get("/successful-webhook/{success_id}")
def get_successful_webhook(success_id: int):
    db = next(get_db())
    success = db.query(WebhookSuccess).filter(WebhookSuccess.id == success_id).first()
    db.close()
    if success:
        return {
            "id": success.id,
            "client_id": success.client_id,
            "conversation_id": success.conversation_id,
            "payload": success.payload,
            "response_status_code": success.response_status_code,
            "response_text": success.response_text,
            "created_at": success.created_at
        }
    else:
        return {"error": "Successful webhook not found"}

@app.get("/client-failed-webhooks/{client_id}")
def get_client_failed_webhooks(client_id: str):
    db = next(get_db())
    failures = db.query(WebhookFailure).filter(WebhookFailure.client_id == client_id).all()
    db.close()
    return {"failed_webhooks": [failure.id for failure in failures]}

from src.models.models import WebhookAttempt

@app.get("/client-successful-webhooks/{client_id}")
def get_client_successful_webhooks(client_id: str):
    db = next(get_db())
    successes = db.query(WebhookSuccess).filter(WebhookSuccess.client_id == client_id).all()
    db.close()
    return {"successful_webhooks": [success.id for success in successes]}

@app.get("/client-webhook-attempts/{client_id}")
def get_client_webhook_attempts(client_id: str):
    db = next(get_db())
    attempts = db.query(WebhookAttempt).filter(WebhookAttempt.client_id == client_id).all()
    db.close()
    return {"webhook_attempts": [attempt.id for attempt in attempts]}

@app.get("/webhook-attempt/{attempt_id}")
def get_webhook_attempt(attempt_id: int):
    db = next(get_db())
    attempt = db.query(WebhookAttempt).filter(WebhookAttempt.id == attempt_id).first()
    db.close()
    if attempt:
        return {
            "id": attempt.id,
            "client_id": attempt.client_id,
            "conversation_id": attempt.conversation_id,
            "payload": attempt.payload,
            "response_status_code": attempt.response_status_code,
            "response_text": attempt.response_text,
            "created_at": attempt.created_at
        }
    else:
        return {"error": "Webhook attempt not found"}

@app.get("/conversation-webhook-attempts/{conversation_id}")
def get_conversation_webhook_attempts(conversation_id: str):
    db = next(get_db())
    attempts = db.query(WebhookAttempt).filter(WebhookAttempt.conversation_id == conversation_id).all()
    db.close()
    return {"webhook_attempts": [attempt.id for attempt in attempts]}

@app.get("/conversation-failed-webhooks/{conversation_id}")
def get_conversation_failed_webhooks(conversation_id: str):
    db = next(get_db())
    failures = db.query(WebhookFailure).filter(WebhookFailure.conversation_id == conversation_id).all()
    db.close()
    return {"failed_webhooks": [failure.id for failure in failures]}

@app.get("/conversation-successful-webhooks/{conversation_id}")
def get_conversation_successful_webhooks(conversation_id: str):
    db = next(get_db())
    successes = db.query(WebhookSuccess).filter(WebhookSuccess.conversation_id == conversation_id).all()
    db.close()
    return {"successful_webhooks": [success.id for success in successes]}

@app.get("/client-conversation-webhook-attempts/{client_id}/{conversation_id}")
def get_client_conversation_webhook_attempts(client_id: str, conversation_id: str):
    db = next(get_db())
    attempts = db.query(WebhookAttempt).filter(WebhookAttempt.client_id == client_id, WebhookAttempt.conversation_id == conversation_id).all()
    db.close()
    return {"webhook_attempts": [attempt.id for attempt in attempts]}

@app.get("/client-conversation-failed-webhooks/{client_id}/{conversation_id}")
def get_client_conversation_failed_webhooks(client_id: str, conversation_id: str):
    db = next(get_db())
    failures = db.query(WebhookFailure).filter(WebhookFailure.client_id == client_id, WebhookFailure.conversation_id == conversation_id).all()
    db.close()
    return {"failed_webhooks": [failure.id for failure in failures]}

@app.get("/client-conversation-successful-webhooks/{client_id}/{conversation_id}")
def get_client_conversation_successful_webhooks(client_id: str, conversation_id: str):
    db = next(get_db())
    successes = db.query(WebhookSuccess).filter(WebhookSuccess.client_id == client_id, WebhookSuccess.conversation_id == conversation_id).all()
    db.close()
    return {"successful_webhooks": [success.id for success in successes]}

@app.get("/client-conversation-failed-webhooks/{client_id}/{conversation_id}/{webhook_id}")
def get_client_conversation_failed_webhooks_by_webhook(client_id: str, conversation_id: str, webhook_id: int):
    db = next(get_db())
    failures = db.query(WebhookFailure).filter(WebhookFailure.client_id == client_id, WebhookFailure.conversation_id == conversation_id, WebhookFailure.id == webhook_id).all()
    db.close()
    return {"failed_webhooks": [failure.id for failure in failures]}

@app.get("/client-conversation-successful-webhooks/{client_id}/{conversation_id}/{webhook_id}")
def get_client_conversation_successful_webhooks_by_webhook(client_id: str, conversation_id: str, webhook_id: int):
    db = next(get_db())
    successes = db.query(WebhookSuccess).filter(WebhookSuccess.client_id == client_id, WebhookSuccess.conversation_id == conversation_id, WebhookSuccess.id == webhook_id).all()
    db.close()
    return {"successful_webhooks": [success.id for success in successes]}

@app.get("/client-conversation-webhook-attempt/{client_id}/{conversation_id}/{webhook_id}/{attempt_id}")
def get_client_conversation_webhook_attempt_by_webhook_and_attempt(client_id: str, conversation_id: str, webhook_id: int, attempt_id: int):
    db = next(get_db())
    attempt = db.query(WebhookAttempt).filter(WebhookAttempt.client_id == client_id, WebhookAttempt.conversation_id == conversation_id, WebhookAttempt.id == webhook_id, WebhookAttempt.id == attempt_id).first()
    db.close()
    if attempt:
        return {
            "id": attempt.id,
            "client_id": attempt.client_id,
            "conversation_id": attempt.conversation_id,
            "payload": attempt.payload,
            "response_status_code": attempt.response_status_code,
            "response_text": attempt.response_text,
            "created_at": attempt.created_at
        }
    else:
        return {"error": "Webhook attempt not found"}

@app.get("/client-conversation-failed-webhook-attempt/{client_id}/{conversation_id}/{webhook_id}/{attempt_id}")
def get_client_conversation_failed_webhook_attempt_by_webhook_and_attempt(client_id: str, conversation_id: str, webhook_id: int, attempt_id: int):
    db = next(get_db())
    failure = db.query(WebhookFailure).filter(WebhookFailure.client_id == client_id, WebhookFailure.conversation_id == conversation_id, WebhookFailure.id == webhook_id, WebhookFailure.id == attempt_id).first()
    db.close()
    if failure:
        return {
            "id": failure.id,
            "client_id": failure.client_id,
            "conversation_id": failure.conversation_id,
            "payload": failure.payload,
            "response_status_code": failure.response_status_code,
            "response_text": failure.response_text,
            "created_at": failure.created_at
        }
    else:
        return {"error": "Failed webhook attempt not found"}

@app.get("/client-conversation-successful-webhook-attempt/{client_id}/{conversation_id}/{webhook_id}/{attempt_id}")
def get_client_conversation_successful_webhook_attempt_by_webhook_and_attempt(client_id: str, conversation_id: str, webhook_id: int, attempt_id: int):
    db = next(get_db())
    success = db.query(WebhookSuccess).filter(WebhookSuccess.client_id == client_id, WebhookSuccess.conversation_id == conversation_id, WebhookSuccess.id == webhook_id, WebhookSuccess.id == attempt_id).first()
    db.close()
    if success:
        return {
            "id": success.id,
            "client_id": success.client_id,
            "conversation_id": success.conversation_id,
            "payload": success.payload,
            "response_status_code": success.response_status_code,
            "response_text": success.response_text,
            "created_at": success.created_at
        }
    else:
        return {"error": "Successful webhook attempt not found"}

@app.get("/client-conversation-webhook-attempts/{client_id}/{conversation_id}/{webhook_id}")
def get_client_conversation_webhook_attempts_by_webhook(client_id: str, conversation_id: str, webhook_id: int):
    db = next(get_db())
    attempts = db.query(WebhookAttempt).filter(WebhookAttempt.client_id == client_id, WebhookAttempt.conversation_id == conversation_id, WebhookAttempt.id == webhook_id).all()
    db.close()
    return {"webhook_attempts": [attempt.id for attempt in attempts]}

@app.get("/webhook/{client_id}")
def get_webhook(client_id: str):
    db = next(get_db())
    client = db.query(Client).filter(Client.client_id == client_id).first()
    db.close()
    if client:
        return {"client_id": client.client_id, "lead_webhook_url": client.lead_webhook_url}
    else:
        return {"error": "Client not found"}