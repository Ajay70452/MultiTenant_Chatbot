"""
Admin Portal API Router

All admin-only endpoints for Practice Brain management.
"""

import logging
import os
import json
from typing import Optional, List
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, status, UploadFile, File, Form
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from src.admin_portal.auth import (
    require_admin,
    admin_login,
    AdminUser
)
from src.admin_portal.schemas import (
    AdminLoginRequest,
    AdminLoginResponse,
    PracticeListResponse,
    PracticeInfo,
    DocumentListResponse,
    DocumentPreview,
    SourceListResponse,
    ReindexRequest,
    ReindexResponse,
    HealthResponse
)
from src.admin_portal.services import (
    PracticeService,
    DocumentService,
    HealthService,
    log_admin_action
)
from src.core.db import get_db
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Create router
admin_portal_router = APIRouter()

# Static files directory
STATIC_DIR = Path(__file__).parent / "static"


# =============================================================================
# Static Files / UI Endpoints
# =============================================================================

@admin_portal_router.get("/")
async def admin_ui():
    """Serve the admin portal UI."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content)
    return HTMLResponse("<h1>Admin Portal</h1><p>UI not found. API is running.</p>")


@admin_portal_router.get("/styles.css")
async def get_styles():
    """Serve CSS file."""
    css_path = STATIC_DIR / "styles.css"
    if css_path.exists():
        with open(css_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content, media_type="text/css")
    raise HTTPException(status_code=404, detail="CSS not found")


@admin_portal_router.get("/app.js")
async def get_js():
    """Serve JavaScript file."""
    js_path = STATIC_DIR / "app.js"
    if js_path.exists():
        with open(js_path, "r", encoding="utf-8") as f:
            content = f.read()
        return HTMLResponse(content=content, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="JavaScript not found")


# =============================================================================
# Authentication Endpoints
# =============================================================================

@admin_portal_router.post(
    "/login",
    response_model=AdminLoginResponse,
    summary="Admin Login",
    description="Authenticate admin user and receive JWT token."
)
async def login(request: AdminLoginRequest, db: Session = Depends(get_db)):
    """Login endpoint for admin users."""
    return admin_login(request, db)


@admin_portal_router.get(
    "/me",
    response_model=AdminUser,
    summary="Get Current Admin",
    description="Get information about the currently authenticated admin."
)
async def get_current_admin(admin: AdminUser = Depends(require_admin)):
    """Get current admin user info."""
    return admin


# =============================================================================
# Practice Endpoints
# =============================================================================

@admin_portal_router.get(
    "/practices",
    response_model=PracticeListResponse,
    summary="List Practices",
    description="Get all practices with their status and document counts."
)
async def list_practices(
    admin: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """List all practices."""
    practices = PracticeService.get_all_practices(db)

    log_admin_action(
        action="list_practices",
        actor=admin.username,
        details={"count": len(practices)}
    )

    return PracticeListResponse(practices=practices, total=len(practices))


@admin_portal_router.get(
    "/practices/{practice_id}",
    response_model=PracticeInfo,
    summary="Get Practice",
    description="Get details for a specific practice."
)
async def get_practice(
    practice_id: str,
    admin: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get a single practice by ID."""
    practice = PracticeService.get_practice_by_id(practice_id, db)
    
    if not practice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Practice not found"
        )
    
    return practice


# =============================================================================
# Document Endpoints
# =============================================================================

@admin_portal_router.get(
    "/practices/{practice_id}/documents",
    response_model=DocumentListResponse,
    summary="List Documents",
    description="Get all documents for a practice with optional filters."
)
async def list_documents(
    practice_id: str,
    status: Optional[str] = Query(None, description="Filter by status"),
    source_type: Optional[str] = Query(None, description="Filter by source type"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin: AdminUser = Depends(require_admin)
):
    """List documents for a practice."""
    documents = DocumentService.get_documents(
        practice_id=practice_id,
        status=status,
        source_type=source_type,
        limit=limit,
        offset=offset
    )
    
    return DocumentListResponse(
        documents=documents,
        total=len(documents),
        practice_id=practice_id
    )


@admin_portal_router.get(
    "/practices/{practice_id}/documents/{doc_id}",
    response_model=DocumentPreview,
    summary="Get Document Preview",
    description="Get document details with preview text."
)
async def get_document_preview(
    practice_id: str,
    doc_id: str,
    admin: AdminUser = Depends(require_admin)
):
    """Get document preview."""
    preview = DocumentService.get_document_by_id(practice_id, doc_id)
    
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found"
        )
    
    log_admin_action(
        action="view_document",
        actor=admin.username,
        practice_id=practice_id,
        doc_id=doc_id
    )
    
    return preview


@admin_portal_router.get(
    "/practices/{practice_id}/sources",
    response_model=SourceListResponse,
    summary="List Sources",
    description="Get documents grouped by source type (Chatbase-style view)."
)
async def list_sources(
    practice_id: str,
    admin: AdminUser = Depends(require_admin)
):
    """Get sources (grouped documents) for a practice."""
    sources = DocumentService.get_sources(practice_id)
    
    return SourceListResponse(sources=sources, practice_id=practice_id)


# =============================================================================
# Re-index Endpoints
# =============================================================================

@admin_portal_router.post(
    "/practices/{practice_id}/documents/{doc_id}/reindex",
    response_model=ReindexResponse,
    summary="Re-index Document",
    description="Trigger re-indexing for a single document."
)
async def reindex_document(
    practice_id: str,
    doc_id: str,
    request: ReindexRequest = ReindexRequest(),
    admin: AdminUser = Depends(require_admin)
):
    """Re-index a single document."""
    result = DocumentService.reindex_document(
        practice_id=practice_id,
        doc_id=doc_id,
        actor=admin.username
    )
    
    return ReindexResponse(**result)


@admin_portal_router.post(
    "/practices/{practice_id}/reindex",
    response_model=ReindexResponse,
    summary="Re-index Practice",
    description="Trigger re-indexing for all documents in a practice."
)
async def reindex_practice(
    practice_id: str,
    request: ReindexRequest = ReindexRequest(),
    admin: AdminUser = Depends(require_admin)
):
    """Re-index all documents in a practice."""
    result = DocumentService.reindex_practice(
        practice_id=practice_id,
        actor=admin.username
    )
    
    return ReindexResponse(**result)


@admin_portal_router.post(
    "/practices/{practice_id}/documents/{doc_id}/disable",
    response_model=ReindexResponse,
    summary="Disable Document",
    description="Disable a document from retrieval."
)
async def disable_document(
    practice_id: str,
    doc_id: str,
    admin: AdminUser = Depends(require_admin)
):
    """Disable a document."""
    result = DocumentService.set_document_status(
        practice_id=practice_id,
        doc_id=doc_id,
        enabled=False,
        actor=admin.username
    )
    
    return ReindexResponse(**result)


@admin_portal_router.post(
    "/practices/{practice_id}/documents/{doc_id}/enable",
    response_model=ReindexResponse,
    summary="Enable Document",
    description="Re-enable a disabled document."
)
async def enable_document(
    practice_id: str,
    doc_id: str,
    admin: AdminUser = Depends(require_admin)
):
    """Enable a document."""
    result = DocumentService.set_document_status(
        practice_id=practice_id,
        doc_id=doc_id,
        enabled=True,
        actor=admin.username
    )
    
    return ReindexResponse(**result)


# =============================================================================
# Health Endpoints
# =============================================================================

@admin_portal_router.get(
    "/practices/{practice_id}/health",
    response_model=HealthResponse,
    summary="Practice Health Check",
    description="Check health of all agents and services for a practice."
)
async def get_practice_health(
    practice_id: str,
    admin: AdminUser = Depends(require_admin)
):
    """Get health status for a practice."""
    health = await HealthService.get_practice_health(practice_id)
    
    log_admin_action(
        action="health_check",
        actor=admin.username,
        practice_id=practice_id,
        details={"overall_status": health.overall_status}
    )
    
    return health


# =============================================================================
# Audit Log Endpoint
# =============================================================================

@admin_portal_router.get(
    "/audit-log",
    summary="Get Audit Log",
    description="Get recent admin actions."
)
async def get_audit_log(
    limit: int = Query(50, ge=1, le=200),
    admin: AdminUser = Depends(require_admin),
    db: Session = Depends(get_db)
):
    """Get audit log entries from database."""
    from src.models.models import AuditLog

    # Query from database, most recent first
    audit_entries = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit).all()

    entries = [
        {
            "id": entry.id,
            "action": entry.action,
            "actor": entry.actor,
            "practice_id": str(entry.practice_id) if entry.practice_id else None,
            "doc_id": str(entry.doc_id) if entry.doc_id else None,
            "result": entry.result,
            "details": entry.details or {},
            "timestamp": entry.created_at.isoformat() if entry.created_at else None
        }
        for entry in audit_entries
    ]

    total_count = db.query(AuditLog).count()
    return {"entries": entries, "total": total_count}


# =============================================================================
# File Upload & Indexing Endpoints
# =============================================================================

SUPPORTED_EXTENSIONS = [".txt", ".pdf", ".docx", ".doc", ".md", ".html", ".json"]
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB


@admin_portal_router.post(
    "/practices/{practice_id}/documents/upload",
    summary="Upload and Index Document",
    description="Upload a file and index it into Pinecone for RAG retrieval."
)
async def upload_and_index_document(
    practice_id: str,
    file: UploadFile = File(..., description="File to upload (PDF, DOCX, TXT, etc.)"),
    title: Optional[str] = Form(None, description="Document title (defaults to filename)"),
    source_type: Optional[str] = Form("pdf", description="Source type (pdf, doc, manual)"),
    subagents: Optional[str] = Form("chat,clinical", description="Comma-separated list of agents"),
    admin: AdminUser = Depends(require_admin)
):
    """
    Upload a document file and index it into Pinecone.
    
    Supported file types: PDF, DOCX, DOC, TXT, MD, HTML, JSON
    
    The file will be:
    1. Extracted for text content
    2. Split into semantic chunks
    3. Embedded using OpenAI text-embedding-3-small
    4. Uploaded to Pinecone in the practice's namespace
    """
    from src.admin_portal.indexing_service import get_indexing_service, SUPPORTED_EXTENSIONS as EXTS
    
    # Validate file extension
    filename = file.filename or "unnamed_file"
    ext = os.path.splitext(filename.lower())[1]
    
    if ext not in EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    
    # Check file size
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large. Maximum size: {MAX_FILE_SIZE / (1024*1024)}MB"
        )
    
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file uploaded"
        )
    
    # Parse subagents
    subagents_list = [s.strip() for s in subagents.split(",") if s.strip()] if subagents else ["chat", "clinical"]
    
    # Process and index
    try:
        indexing_service = get_indexing_service()
    except ValueError as e:
        logger.error(f"Indexing service initialization failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Indexing service not configured: {str(e)}"
        )
    
    try:
        result = indexing_service.process_and_index_file(
            practice_id=practice_id,
            filename=filename,
            file_content=content,
            title=title,
            source_type=source_type or ext[1:],
            subagents_allowed=subagents_list
        )
    except Exception as e:
        logger.error(f"Error during file indexing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Indexing failed: {str(e)}"
        )
    
    # Log the action
    log_admin_action(
        action="upload_document",
        actor=admin.username,
        practice_id=practice_id,
        doc_id=result.get("doc_id"),
        details={
            "filename": filename,
            "file_size": len(content),
            "status": result.get("status"),
            "chunk_count": result.get("chunk_count", 0)
        }
    )
    
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message", "Failed to index document")
        )
    
    return result


@admin_portal_router.post(
    "/practices/{practice_id}/documents/upload-stream",
    summary="Upload and Index Document with Progress",
    description="Upload a file and index it with real-time progress updates via SSE."
)
async def upload_and_index_document_stream(
    practice_id: str,
    file: UploadFile = File(..., description="File to upload"),
    title: Optional[str] = Form(None, description="Document title"),
    source_type: Optional[str] = Form("pdf", description="Source type"),
    subagents: Optional[str] = Form("chat,clinical", description="Comma-separated list of agents"),
    admin: AdminUser = Depends(require_admin)
):
    """
    Upload and index with Server-Sent Events for progress updates.
    """
    from src.admin_portal.indexing_service import get_indexing_service, SUPPORTED_EXTENSIONS as EXTS
    
    # Validate file
    filename = file.filename or "unnamed_file"
    ext = os.path.splitext(filename.lower())[1]
    
    if ext not in EXTS:
        async def error_stream():
            yield f"data: {json.dumps({'stage': 'error', 'percent': 0, 'message': f'Unsupported file type: {ext}'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")
    
    content = await file.read()
    
    if len(content) == 0:
        async def error_stream():
            yield f"data: {json.dumps({'stage': 'error', 'percent': 0, 'message': 'Empty file uploaded'})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")
    
    subagents_list = [s.strip() for s in subagents.split(",") if s.strip()] if subagents else ["chat", "clinical"]
    
    async def progress_stream():
        try:
            indexing_service = get_indexing_service()
            
            for progress in indexing_service.process_and_index_file_with_progress(
                practice_id=practice_id,
                filename=filename,
                file_content=content,
                title=title,
                source_type=source_type or ext[1:],
                subagents_allowed=subagents_list
            ):
                yield f"data: {json.dumps(progress)}\n\n"
                
        except Exception as e:
            yield f"data: {json.dumps({'stage': 'error', 'percent': 0, 'message': str(e)})}\n\n"
    
    return StreamingResponse(progress_stream(), media_type="text/event-stream")


@admin_portal_router.post(
    "/practices/{practice_id}/documents/index-text",
    summary="Index Text Content",
    description="Index raw text content directly into Pinecone."
)
async def index_text_content(
    practice_id: str,
    title: str = Form(..., description="Document title"),
    content: str = Form(..., description="Text content to index"),
    source_type: Optional[str] = Form("manual", description="Source type"),
    source_uri: Optional[str] = Form("manual-entry", description="Source URI"),
    subagents: Optional[str] = Form("chat,clinical", description="Comma-separated list of agents"),
    admin: AdminUser = Depends(require_admin)
):
    """
    Index raw text content directly.
    
    Use this for manual text entry or pasting content that doesn't need file extraction.
    """
    from src.admin_portal.indexing_service import get_indexing_service
    
    if len(content.strip()) < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Content too short. Minimum 50 characters required."
        )
    
    # Parse subagents
    subagents_list = [s.strip() for s in subagents.split(",") if s.strip()] if subagents else ["chat", "clinical"]
    
    indexing_service = get_indexing_service()
    
    result = indexing_service.index_text_content(
        practice_id=practice_id,
        title=title,
        text_content=content,
        source_type=source_type,
        source_uri=source_uri,
        subagents_allowed=subagents_list
    )
    
    log_admin_action(
        action="index_text",
        actor=admin.username,
        practice_id=practice_id,
        doc_id=result.get("doc_id"),
        details={
            "title": title,
            "content_length": len(content),
            "status": result.get("status")
        }
    )
    
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message", "Failed to index text")
        )
    
    return result


@admin_portal_router.get(
    "/practices/{practice_id}/index-stats",
    summary="Get Index Statistics",
    description="Get Pinecone index statistics for a practice."
)
async def get_index_stats(
    practice_id: str,
    admin: AdminUser = Depends(require_admin)
):
    """Get Pinecone index statistics for a practice namespace."""
    from src.admin_portal.indexing_service import get_indexing_service
    
    indexing_service = get_indexing_service()
    result = indexing_service.get_index_stats(practice_id)
    
    return result


@admin_portal_router.delete(
    "/practices/{practice_id}/documents/{doc_id}/vectors",
    summary="Delete Document Vectors",
    description="Delete all vectors for a document from Pinecone."
)
async def delete_document_vectors(
    practice_id: str,
    doc_id: str,
    admin: AdminUser = Depends(require_admin)
):
    """Delete all vectors for a document from Pinecone."""
    from src.admin_portal.indexing_service import get_indexing_service
    
    indexing_service = get_indexing_service()
    result = indexing_service.delete_document(practice_id, doc_id)
    
    log_admin_action(
        action="delete_vectors",
        actor=admin.username,
        practice_id=practice_id,
        doc_id=doc_id,
        details=result
    )
    
    if result.get("status") == "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=result.get("message", "Failed to delete vectors")
        )
    
    return result

