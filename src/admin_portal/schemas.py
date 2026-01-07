"""
Pydantic schemas for Admin Portal API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime
from enum import Enum


# =============================================================================
# Enums
# =============================================================================

class SourceType(str, Enum):
    WEBSITE = "website"
    PDF = "pdf"
    DOC = "doc"
    FAQ = "faq"
    SOP = "sop"
    OTHER = "other"


class DocumentStatus(str, Enum):
    PENDING = "pending"
    INDEXED = "indexed"
    FAILED = "failed"
    DISABLED = "disabled"


class HealthStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


# =============================================================================
# Auth Schemas
# =============================================================================

class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=3)
    password: str = Field(..., min_length=6)


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int = 3600


class AdminUser(BaseModel):
    username: str
    role: str = "admin"


# =============================================================================
# Practice Schemas
# =============================================================================

class PracticeInfo(BaseModel):
    practice_id: str
    name: str
    status: str = "active"
    document_count: int = 0
    last_indexed_at: Optional[datetime] = None


class PracticeListResponse(BaseModel):
    practices: List[PracticeInfo]
    total: int


# =============================================================================
# Document Schemas
# =============================================================================

class DocumentInfo(BaseModel):
    doc_id: str
    title: str
    source_type: SourceType
    source_uri: Optional[str] = None
    status: DocumentStatus
    subagents_allowed: List[str] = ["chat", "clinical"]
    chunk_count: int = 0
    last_indexed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class DocumentListResponse(BaseModel):
    documents: List[DocumentInfo]
    total: int
    practice_id: str


class DocumentPreview(BaseModel):
    doc_id: str
    title: str
    source_type: SourceType
    status: DocumentStatus
    preview_text: str
    chunk_count: int
    metadata: dict = {}


class SourceInfo(BaseModel):
    source_type: SourceType
    document_count: int
    total_chunks: int
    status: str
    last_indexed_at: Optional[datetime] = None


class SourceListResponse(BaseModel):
    sources: List[SourceInfo]
    practice_id: str


# =============================================================================
# Re-index Schemas
# =============================================================================

class ReindexRequest(BaseModel):
    force: bool = False


class ReindexResponse(BaseModel):
    status: str
    message: str
    job_id: Optional[str] = None


# =============================================================================
# Health Schemas
# =============================================================================

class EndpointHealth(BaseModel):
    status: HealthStatus
    response_time_ms: Optional[int] = None
    last_checked: datetime
    error: Optional[str] = None


class PineconeHealth(BaseModel):
    status: HealthStatus
    vectors_count: int = 0
    namespace: Optional[str] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    practice_id: str
    chat_endpoint: EndpointHealth
    clinical_endpoint: EndpointHealth
    pinecone: PineconeHealth
    overall_status: HealthStatus
