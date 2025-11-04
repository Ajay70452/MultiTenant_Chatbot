from sqlalchemy import create_engine, Column, String, DateTime, JSON, ForeignKey, BigInteger, Integer, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import UUID
import uuid
import datetime

from src.core.config import DATABASE_URL

Base = declarative_base()

class Client(Base):
    __tablename__ = 'clients'
    client_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    lead_webhook_url = Column(String, nullable=True)

class Conversation(Base):
    __tablename__ = 'conversations'
    conversation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey('clients.client_id'), nullable=False)
    current_stage = Column(String(50), nullable=False, default='GREETING')
    conversation_state = Column(JSON, default={})
    last_activity_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_finalized = Column(Boolean, default=False, nullable=False)
    finalized_at = Column(DateTime, nullable=True)

class ChatLog(Base):
    __tablename__ = 'chat_logs'
    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.conversation_id'), nullable=False)
    sender_type = Column(String(10), nullable=False) # 'user' or 'bot'
    message = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    response_time_ms = Column(Integer, nullable=True)

class WebhookAttempt(Base):
    __tablename__ = 'webhook_attempts'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey('clients.client_id'), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.conversation_id'), nullable=False)
    payload = Column(JSON, nullable=False)
    response_status_code = Column(Integer, nullable=True)
    response_text = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class WebhookFailure(Base):
    __tablename__ = 'webhook_failures'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey('clients.client_id'), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.conversation_id'), nullable=False)
    payload = Column(JSON, nullable=False)
    response_status_code = Column(Integer, nullable=True)
    response_text = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

class WebhookSuccess(Base):
    __tablename__ = 'webhook_successes'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    client_id = Column(UUID(as_uuid=True), ForeignKey('clients.client_id'), nullable=False)
    conversation_id = Column(UUID(as_uuid=True), ForeignKey('conversations.conversation_id'), nullable=False)
    payload = Column(JSON, nullable=False)
    response_status_code = Column(Integer, nullable=True)
    response_text = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
