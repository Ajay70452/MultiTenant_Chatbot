"""
Practice Brain Admin Portal Module

This module provides admin-only access to:
- Practice management and selection
- Knowledge library (documents inventory)
- Document preview and re-indexing
- Agent health monitoring
"""

from src.admin_portal.router import admin_portal_router

__all__ = ["admin_portal_router"]
