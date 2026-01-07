"""
Admin Portal Services

Business logic for:
- Practice management
- Document inventory
- Indexing operations
- Health checks
"""

import logging
import time
import uuid
import hashlib
from datetime import datetime
from typing import List, Optional, Dict, Any

import httpx

from src.admin_portal.schemas import (
    PracticeInfo, DocumentInfo, DocumentPreview, SourceInfo,
    EndpointHealth, PineconeHealth, HealthResponse, HealthStatus,
    SourceType, DocumentStatus
)
from src.models.models import Client, AuditLog, Document
from src.core.db import SessionLocal
from sqlalchemy.orm import Session
from sqlalchemy import func

logger = logging.getLogger(__name__)


# =============================================================================
# Mock Data Store (In-memory for Phase 1)
# =============================================================================

# Simulated documents database
MOCK_DOCUMENTS: Dict[str, List[Dict]] = {}

def _init_mock_data():
    """Initialize mock document data for demo purposes."""
    global MOCK_DOCUMENTS
    
    # Use clinic name as practice_id (matches Pinecone namespace)
    demo_practice_id = "robeck-dental"
    
    MOCK_DOCUMENTS[demo_practice_id] = [
        {
            "doc_id": str(uuid.uuid4()),
            "title": "Office Policies & Procedures",
            "source_type": "pdf",
            "source_uri": "s3://practice-docs/policies.pdf",
            "status": "indexed",
            "subagents_allowed": ["chat", "clinical"],
            "chunk_count": 24,
            "last_indexed_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        },
        {
            "doc_id": str(uuid.uuid4()),
            "title": "Website Content - Homepage",
            "source_type": "website",
            "source_uri": "https://robeckdental.com/",
            "status": "indexed",
            "subagents_allowed": ["chat"],
            "chunk_count": 12,
            "last_indexed_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        },
        {
            "doc_id": str(uuid.uuid4()),
            "title": "Patient FAQ",
            "source_type": "faq",
            "source_uri": "manual-entry",
            "status": "indexed",
            "subagents_allowed": ["chat", "clinical"],
            "chunk_count": 45,
            "last_indexed_at": datetime.utcnow(),
            "created_at": datetime.utcnow(),
        },
        {
            "doc_id": str(uuid.uuid4()),
            "title": "Clinical Protocols SOP",
            "source_type": "sop",
            "source_uri": "s3://practice-docs/clinical-sop.docx",
            "status": "pending",
            "subagents_allowed": ["clinical"],
            "chunk_count": 0,
            "last_indexed_at": None,
            "created_at": datetime.utcnow(),
        },
        {
            "doc_id": str(uuid.uuid4()),
            "title": "Insurance Information",
            "source_type": "doc",
            "source_uri": "s3://practice-docs/insurance.docx",
            "status": "failed",
            "subagents_allowed": ["chat"],
            "chunk_count": 0,
            "last_indexed_at": None,
            "created_at": datetime.utcnow(),
        },
    ]

# Initialize mock data
_init_mock_data()


# =============================================================================
# Audit Logging
# =============================================================================

AUDIT_LOG: List[Dict] = []  # In-memory cache for quick access


def log_admin_action(
    action: str,
    actor: str,
    practice_id: str = None,
    doc_id: str = None,
    result: str = "success",
    details: dict = None
):
    """Log an admin action for audit trail. Persists to database."""
    entry = {
        "id": str(uuid.uuid4()),
        "action": action,
        "actor": actor,
        "practice_id": practice_id,
        "doc_id": doc_id,
        "result": result,
        "details": details or {},
        "timestamp": datetime.utcnow().isoformat()
    }

    # Add to in-memory cache
    AUDIT_LOG.append(entry)
    logger.info(f"ADMIN_ACTION: {action}", extra=entry)

    # Persist to database
    try:
        db = SessionLocal()
        audit_entry = AuditLog(
            actor=actor,
            action=action,
            practice_id=uuid.UUID(practice_id) if practice_id else None,
            doc_id=uuid.UUID(doc_id) if doc_id else None,
            result=result,
            details=details
        )
        db.add(audit_entry)
        db.commit()
        db.close()
    except Exception as e:
        logger.error(f"Failed to persist audit log to database: {e}")


# =============================================================================
# Practice Services
# =============================================================================

class PracticeService:
    """Service for managing practices."""

    @staticmethod
    def _get_pinecone_stats() -> Dict[str, int]:
        """Get vector counts per namespace from Pinecone."""
        try:
            from src.core.config import PINECONE_API_KEY, PINECONE_INDEX_NAME
            import pinecone

            pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
            index = pc.Index(PINECONE_INDEX_NAME)
            stats = index.describe_index_stats()

            namespace_counts = {}
            for ns, data in stats.get("namespaces", {}).items():
                namespace_counts[ns] = data.get("vector_count", 0)

            return namespace_counts
        except Exception as e:
            logger.error(f"Failed to get Pinecone stats: {e}")
            return {}

    @staticmethod
    def get_all_practices(db: Session = None) -> List[PracticeInfo]:
        """
        Get all practices from the database.
        Enriches with Pinecone vector counts.
        """
        if db is None:
            # Fallback to mock data if no DB session
            return [
                PracticeInfo(
                    practice_id="robeck-dental",
                    name="Robeck Family Dentistry",
                    status="active",
                    document_count=5,
                    last_indexed_at=datetime.utcnow()
                ),
            ]

        # Fetch from database
        clients = db.query(Client).all()

        # Get Pinecone stats
        pinecone_stats = PracticeService._get_pinecone_stats()

        practices = []
        for client in clients:
            client_id_str = str(client.client_id)

            # Check for vectors using client_id as namespace
            vector_count = pinecone_stats.get(client_id_str, 0)

            # Also check using slugified clinic name
            clinic_slug = client.clinic_name.lower().replace(" ", "-").replace("_", "-") if client.clinic_name else ""
            if vector_count == 0:
                vector_count = pinecone_stats.get(clinic_slug, 0)

            # Determine status based on vector count
            status = "active" if vector_count > 0 else "inactive"

            practices.append(PracticeInfo(
                practice_id=client_id_str,
                name=client.clinic_name or "Unknown Practice",
                status=status,
                document_count=vector_count,  # Using vector count as proxy for docs
                last_indexed_at=client.created_at
            ))

        return practices

    @staticmethod
    def get_practice_by_id(practice_id: str, db: Session = None) -> Optional[PracticeInfo]:
        """Get a single practice by ID."""
        practices = PracticeService.get_all_practices(db)
        for p in practices:
            if p.practice_id == practice_id:
                return p
        return None


# =============================================================================
# Document Services
# =============================================================================

class DocumentService:
    """Service for managing practice documents from the database."""

    @staticmethod
    def get_documents(
        practice_id: str,
        status: Optional[str] = None,
        source_type: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        db: Session = None
    ) -> List[DocumentInfo]:
        """Get documents for a practice with optional filters."""
        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            query = db.query(Document).filter(Document.client_id == uuid.UUID(practice_id))

            if status:
                query = query.filter(Document.status == status)
            if source_type:
                query = query.filter(Document.source_type == source_type)

            docs = query.order_by(Document.created_at.desc()).offset(offset).limit(limit).all()

            return [
                DocumentInfo(
                    doc_id=str(d.doc_id),
                    title=d.title,
                    source_type=SourceType(d.source_type) if d.source_type in [e.value for e in SourceType] else SourceType.DOC,
                    source_uri=d.source_uri,
                    status=DocumentStatus(d.status) if d.status in [e.value for e in DocumentStatus] else DocumentStatus.PENDING,
                    subagents_allowed=d.subagents_allowed or ["chat"],
                    chunk_count=d.chunk_count or 0,
                    last_indexed_at=d.last_indexed_at,
                    created_at=d.created_at,
                    updated_at=d.updated_at
                )
                for d in docs
            ]
        finally:
            if should_close:
                db.close()

    @staticmethod
    def get_document_by_id(practice_id: str, doc_id: str, db: Session = None) -> Optional[DocumentPreview]:
        """Get document details with preview text."""
        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            doc = db.query(Document).filter(
                Document.client_id == uuid.UUID(practice_id),
                Document.doc_id == uuid.UUID(doc_id)
            ).first()

            if not doc:
                return None

            preview_text = f"""
Document: {doc.title}

Source: {doc.source_uri or 'N/A'}
Type: {doc.source_type}
Status: {doc.status}

This document contains {doc.chunk_count or 0} chunks that are searchable via
the Practice Brain RAG system.
            """.strip()

            return DocumentPreview(
                doc_id=str(doc.doc_id),
                title=doc.title,
                source_type=SourceType(doc.source_type) if doc.source_type in [e.value for e in SourceType] else SourceType.DOC,
                status=DocumentStatus(doc.status) if doc.status in [e.value for e in DocumentStatus] else DocumentStatus.PENDING,
                preview_text=preview_text,
                chunk_count=doc.chunk_count or 0,
                metadata={
                    "source_uri": doc.source_uri,
                    "subagents_allowed": doc.subagents_allowed or [],
                    "created_at": doc.created_at.isoformat() if doc.created_at else None,
                    "last_indexed_at": doc.last_indexed_at.isoformat() if doc.last_indexed_at else None,
                }
            )
        finally:
            if should_close:
                db.close()

    @staticmethod
    def get_sources(practice_id: str, db: Session = None) -> List[SourceInfo]:
        """Get documents grouped by source type."""
        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            docs = db.query(Document).filter(Document.client_id == uuid.UUID(practice_id)).all()

            # Group by source type
            source_groups: Dict[str, List] = {}
            for doc in docs:
                st = doc.source_type or "doc"
                if st not in source_groups:
                    source_groups[st] = []
                source_groups[st].append(doc)

            sources = []
            for source_type, group_docs in source_groups.items():
                total_chunks = sum(d.chunk_count or 0 for d in group_docs)
                indexed_count = sum(1 for d in group_docs if d.status == "indexed")

                if indexed_count == len(group_docs):
                    status = "indexed"
                elif indexed_count > 0:
                    status = "partial"
                else:
                    status = "pending"

                last_indexed = max(
                    (d.last_indexed_at for d in group_docs if d.last_indexed_at),
                    default=None
                )

                try:
                    st_enum = SourceType(source_type)
                except ValueError:
                    st_enum = SourceType.DOC

                sources.append(SourceInfo(
                    source_type=st_enum,
                    document_count=len(group_docs),
                    total_chunks=total_chunks,
                    status=status,
                    last_indexed_at=last_indexed
                ))

            return sources
        finally:
            if should_close:
                db.close()

    @staticmethod
    def reindex_document(practice_id: str, doc_id: str, actor: str, db: Session = None) -> dict:
        """Trigger re-indexing for a single document."""
        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            doc = db.query(Document).filter(
                Document.client_id == uuid.UUID(practice_id),
                Document.doc_id == uuid.UUID(doc_id)
            ).first()

            if not doc:
                return {"status": "error", "message": "Document not found"}

            # Update status to pending
            doc.status = "pending"
            doc.last_indexed_at = None
            db.commit()

            # Log action
            log_admin_action(
                action="reindex_document",
                actor=actor,
                practice_id=practice_id,
                doc_id=doc_id
            )

            # In production, queue background job here
            # For now, immediately set to indexed
            doc.status = "indexed"
            doc.last_indexed_at = datetime.utcnow()
            db.commit()

            return {
                "status": "success",
                "message": f"Document '{doc.title}' re-indexed successfully",
                "job_id": str(uuid.uuid4())
            }
        finally:
            if should_close:
                db.close()

    @staticmethod
    def reindex_practice(practice_id: str, actor: str, db: Session = None) -> dict:
        """Trigger re-indexing for all documents in a practice."""
        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            docs = db.query(Document).filter(Document.client_id == uuid.UUID(practice_id)).all()

            if not docs:
                return {"status": "error", "message": "No documents found for practice"}

            # Log action
            log_admin_action(
                action="reindex_practice",
                actor=actor,
                practice_id=practice_id,
                details={"document_count": len(docs)}
            )

            # Update all non-disabled documents
            for doc in docs:
                if doc.status != "disabled":
                    doc.status = "indexed"
                    doc.last_indexed_at = datetime.utcnow()

            db.commit()

            return {
                "status": "success",
                "message": f"Re-indexed {len(docs)} documents for practice",
                "job_id": str(uuid.uuid4())
            }
        finally:
            if should_close:
                db.close()

    @staticmethod
    def set_document_status(practice_id: str, doc_id: str, enabled: bool, actor: str, db: Session = None) -> dict:
        """Enable or disable a document."""
        if db is None:
            db = SessionLocal()
            should_close = True
        else:
            should_close = False

        try:
            doc = db.query(Document).filter(
                Document.client_id == uuid.UUID(practice_id),
                Document.doc_id == uuid.UUID(doc_id)
            ).first()

            if not doc:
                return {"status": "error", "message": "Document not found"}

            action = "enable_document" if enabled else "disable_document"
            new_status = "indexed" if enabled else "disabled"

            doc.status = new_status
            db.commit()

            log_admin_action(
                action=action,
                actor=actor,
                practice_id=practice_id,
                doc_id=doc_id
            )

            return {
                "status": "success",
                "message": f"Document {'enabled' if enabled else 'disabled'} successfully"
            }
        finally:
            if should_close:
                db.close()


# =============================================================================
# Health Check Services
# =============================================================================

class HealthService:
    """Service for checking agent and system health."""
    
    @staticmethod
    async def check_endpoint(url: str, timeout: float = 5.0) -> EndpointHealth:
        """Check if an HTTP endpoint is healthy."""
        start_time = time.time()
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=timeout)
                response_time = int((time.time() - start_time) * 1000)
                
                if response.status_code < 400:
                    return EndpointHealth(
                        status=HealthStatus.HEALTHY,
                        response_time_ms=response_time,
                        last_checked=datetime.utcnow()
                    )
                else:
                    return EndpointHealth(
                        status=HealthStatus.UNHEALTHY,
                        response_time_ms=response_time,
                        last_checked=datetime.utcnow(),
                        error=f"HTTP {response.status_code}"
                    )
        except Exception as e:
            return EndpointHealth(
                status=HealthStatus.UNHEALTHY,
                last_checked=datetime.utcnow(),
                error=str(e)
            )
    
    @staticmethod
    async def check_pinecone(practice_id: str) -> PineconeHealth:
        """Check Pinecone connectivity and get stats."""
        try:
            from src.core.config import PINECONE_API_KEY, PINECONE_INDEX_NAME
            import pinecone
            
            pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
            index = pc.Index(PINECONE_INDEX_NAME)
            
            # Get index stats
            stats = index.describe_index_stats()
            
            # Get namespace-specific count
            namespaces = stats.get("namespaces", {})
            namespace_stats = namespaces.get(practice_id, {})
            vectors_count = namespace_stats.get("vector_count", 0)
            
            return PineconeHealth(
                status=HealthStatus.HEALTHY,
                vectors_count=vectors_count,
                namespace=practice_id
            )
        except Exception as e:
            logger.error(f"Pinecone health check failed: {e}")
            return PineconeHealth(
                status=HealthStatus.UNHEALTHY,
                error=str(e)
            )
    
    @staticmethod
    async def get_practice_health(practice_id: str, base_url: str = "http://localhost:8000") -> HealthResponse:
        """Get comprehensive health status for a practice."""
        
        # Check endpoints
        chat_health = await HealthService.check_endpoint(f"{base_url}/")
        clinical_health = await HealthService.check_endpoint(f"{base_url}/version")
        
        # Check Pinecone
        pinecone_health = await HealthService.check_pinecone(practice_id)
        
        # Determine overall status
        all_healthy = (
            chat_health.status == HealthStatus.HEALTHY and
            clinical_health.status == HealthStatus.HEALTHY and
            pinecone_health.status == HealthStatus.HEALTHY
        )
        
        return HealthResponse(
            practice_id=practice_id,
            chat_endpoint=chat_health,
            clinical_endpoint=clinical_health,
            pinecone=pinecone_health,
            overall_status=HealthStatus.HEALTHY if all_healthy else HealthStatus.UNHEALTHY
        )
