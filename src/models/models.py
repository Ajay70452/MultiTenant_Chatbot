from sqlalchemy import create_engine, Column, String, DateTime, JSON, ForeignKey, BigInteger, Integer, Boolean
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
import uuid
import datetime

from src.core.config import DATABASE_URL

# 1. Create the engine
engine = create_engine(DATABASE_URL) 

# 2. Create the SessionLocal object (The one the script is trying to import)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 3. Define the Base class (if it's not already defined elsewhere)
from sqlalchemy.orm import declarative_base
Base = declarative_base() 

class Client(Base):
    __tablename__ = 'clients'
    client_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    clinic_name = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    lead_webhook_url = Column(String, nullable=True)
    access_token = Column(String(64), nullable=True, unique=True, index=True)

    # One-to-one relationship with PracticeProfile
    profile = relationship("PracticeProfile", back_populates="client", uselist=False)

class Conversation(Base):
    __tablename__ = 'conversations'
    conversation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey('clients.client_id'), nullable=False)
    current_stage = Column(String(50), nullable=False, default='GREETING')
    conversation_state = Column(JSON, default={})
    last_activity_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_finalized = Column(Boolean, default=False, nullable=False)
    finalized_at = Column(DateTime, nullable=True)

    # Reporting columns for AI Chat Dashboard
    lead_captured = Column(Boolean, default=False, nullable=False)
    delivery_status = Column(String(50), nullable=True)
    topic_tag = Column(String(100), nullable=True)
    is_after_hours = Column(Boolean, default=False, nullable=False)

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

class PracticeProfile(Base):
    __tablename__ = 'practice_profiles'

    # The ID is also the foreign key, enforcing a one-to-one relationship
    practice_id = Column(UUID(as_uuid=True), ForeignKey('clients.client_id'), primary_key=True)

    # The "Brain" itself, using the efficient JSONB type
    profile_json = Column(JSONB, nullable=False, default={})

    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    client = relationship("Client", back_populates="profile")


# ===================== Admin Portal Models =====================

class Document(Base):
    """Tracks documents indexed into Pinecone for each practice"""
    __tablename__ = 'documents'

    doc_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_id = Column(UUID(as_uuid=True), ForeignKey('clients.client_id'), nullable=False)
    title = Column(String(500), nullable=False)
    source_type = Column(String(50), nullable=False)  # 'pdf', 'docx', 'url', 'text'
    source_uri = Column(String(1000), nullable=True)  # Original file path or URL
    status = Column(String(20), nullable=False, default='pending')  # pending, processing, indexed, failed
    chunk_count = Column(Integer, nullable=False, default=0)
    error_message = Column(String, nullable=True)
    subagents_allowed = Column(JSON, default=['chat', 'clinical'])  # Which agents can access this doc
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    last_indexed_at = Column(DateTime, nullable=True)

    # Relationship
    client = relationship("Client", backref="documents")


class AdminUser(Base):
    """Admin portal users with role-based access"""
    __tablename__ = 'admin_users'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    username = Column(String(100), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    role = Column(String(50), nullable=False, default='admin')  # admin, superadmin, viewer
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


class AuditLog(Base):
    """Audit trail for all admin portal actions"""
    __tablename__ = 'audit_logs'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    actor = Column(String(100), nullable=False)  # Username of admin who performed action
    action = Column(String(100), nullable=False)  # e.g., 'create_practice', 'index_document', 'delete_document'
    practice_id = Column(UUID(as_uuid=True), nullable=True)  # Related practice if applicable
    doc_id = Column(UUID(as_uuid=True), nullable=True)  # Related document if applicable
    result = Column(String(20), nullable=False, default='success')  # success, failure
    details = Column(JSON, nullable=True)  # Additional context (file names, error messages, etc.)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, index=True)