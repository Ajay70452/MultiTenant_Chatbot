"""
RAG Engine for retrieving relevant context from Pinecone.

This module provides vector-based context retrieval for the chatbot,
with comprehensive error handling and graceful degradation.
"""

import logging
from typing import Optional

import pinecone
from langchain_openai import OpenAIEmbeddings

from src.core.config import PINECONE_API_KEY, OPENAI_API_KEY, PINECONE_INDEX_NAME

logger = logging.getLogger(__name__)

# Configuration
RAG_TOP_K = 3  # Number of relevant chunks to retrieve
RAG_TIMEOUT_SECONDS = 10  # Timeout for Pinecone queries

# Initialize Pinecone client (with error handling)
_pinecone_client: Optional[pinecone.Pinecone] = None
_embeddings: Optional[OpenAIEmbeddings] = None


def _get_pinecone_client() -> Optional[pinecone.Pinecone]:
    """Get or initialize the Pinecone client with error handling."""
    global _pinecone_client

    if _pinecone_client is not None:
        return _pinecone_client

    if not PINECONE_API_KEY:
        logger.error("PINECONE_API_KEY not configured")
        return None

    try:
        _pinecone_client = pinecone.Pinecone(api_key=PINECONE_API_KEY)
        logger.info("Pinecone client initialized successfully")
        return _pinecone_client
    except Exception as e:
        logger.error(f"Failed to initialize Pinecone client: {e}")
        return None


def _get_embeddings() -> Optional[OpenAIEmbeddings]:
    """Get or initialize the OpenAI embeddings with error handling."""
    global _embeddings

    if _embeddings is not None:
        return _embeddings

    if not OPENAI_API_KEY:
        logger.error("OPENAI_API_KEY not configured")
        return None

    try:
        _embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
        logger.info("OpenAI embeddings initialized successfully")
        return _embeddings
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI embeddings: {e}")
        return None


def get_relevant_context(query: str, client_id: str) -> str:
    """
    Retrieve relevant context from Pinecone for a given query.

    This function includes comprehensive error handling and will return
    an empty string on any failure, allowing the system to continue
    functioning without RAG context.

    Args:
        query: The user's query to find relevant context for
        client_id: The client ID (used as Pinecone namespace for isolation)

    Returns:
        A string containing relevant context, or empty string on error
    """
    if not query or not query.strip():
        logger.warning("Empty query provided to RAG engine")
        return ""

    if not client_id:
        logger.warning("No client_id provided to RAG engine")
        return ""

    # Get Pinecone client
    pc = _get_pinecone_client()
    if pc is None:
        logger.warning("Pinecone client unavailable, skipping RAG retrieval")
        return ""

    # Get embeddings
    embeddings = _get_embeddings()
    if embeddings is None:
        logger.warning("Embeddings unavailable, skipping RAG retrieval")
        return ""

    try:
        # Get the index
        if not PINECONE_INDEX_NAME:
            logger.error("PINECONE_INDEX_NAME not configured")
            return ""

        index = pc.Index(PINECONE_INDEX_NAME)

        # Generate query embedding
        try:
            query_vector = embeddings.embed_query(query)
        except Exception as e:
            logger.error(f"Failed to generate query embedding: {e}")
            return ""

        # Query Pinecone
        try:
            results = index.query(
                vector=query_vector,
                top_k=RAG_TOP_K,
                namespace=client_id,
                include_metadata=True
            )
        except Exception as e:
            logger.error(f"Pinecone query failed: {e}")
            return ""

        # Extract context from results
        context_parts = []

        # Handle both object and dict response formats
        if hasattr(results, 'matches'):
            matches = results.matches
        else:
            matches = results.get('matches', [])

        if not matches:
            logger.info(f"No RAG matches found for client: {client_id}")
            return ""

        for match in matches:
            try:
                # Handle both object and dict formats for match
                if hasattr(match, 'metadata'):
                    metadata = match.metadata
                else:
                    metadata = match.get('metadata', {})

                text = metadata.get('text', '')
                if text and text.strip():
                    context_parts.append(text.strip())
            except Exception as e:
                logger.warning(f"Error extracting context from match: {e}")
                continue

        if context_parts:
            context = "\n\n".join(context_parts)
            logger.info(
                f"RAG context retrieved successfully",
                extra={
                    'client_id': client_id,
                    'num_matches': len(context_parts),
                    'context_length': len(context)
                }
            )
            return context

        return ""

    except pinecone.exceptions.PineconeException as e:
        logger.error(f"Pinecone error during RAG retrieval: {e}")
        return ""
    except Exception as e:
        logger.error(f"Unexpected error during RAG retrieval: {e}")
        return ""


def health_check() -> dict:
    """
    Check the health of the RAG engine components.

    Returns:
        A dict with status of each component
    """
    status = {
        "pinecone_configured": bool(PINECONE_API_KEY),
        "openai_configured": bool(OPENAI_API_KEY),
        "index_name": PINECONE_INDEX_NAME or "NOT SET",
        "pinecone_client": "OK" if _get_pinecone_client() else "FAILED",
        "embeddings": "OK" if _get_embeddings() else "FAILED"
    }

    # Try to list indexes as a connection test
    try:
        pc = _get_pinecone_client()
        if pc:
            # This will verify the connection is working
            pc.list_indexes()
            status["pinecone_connection"] = "OK"
        else:
            status["pinecone_connection"] = "CLIENT_UNAVAILABLE"
    except Exception as e:
        status["pinecone_connection"] = f"FAILED: {str(e)}"

    return status