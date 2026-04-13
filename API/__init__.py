"""
API Package - FastAPI endpoints and authentication.
====================================================

This package handles all HTTP API functionality.

INTEGRATION:
    from api import create_app, APIRegistry
    
    # Create FastAPI app
    app = create_app()
    
    # Or use existing
    from api.main import app

AVAILABLE MODULES:
    - main: FastAPI app with all endpoints
    - auth: JWT authentication + RBAC
    - metrics: Prometheus metrics
"""

from typing import Dict, Any, List

# Lazy imports
_components = {}


def _lazy_import(name: str):
    """Lazy import an API component."""
    if name in _components:
        return _components[name]
    
    if name == "app":
        from api.main import app
        _components[name] = app
    elif name == "auth":
        from api.auth import jwt_auth
        _components[name] = jwt_auth
    elif name == "metrics":
        from api.metrics import metrics
        _components[name] = metrics
    
    return _components.get(name)


def get_component(name: str):
    """Get a specific API component."""
    return _lazy_import(name)


def create_app():
    """Create and return the FastAPI application."""
    return _lazy_import("app")


class APIRegistry:
    """
    Registry for API integration with pipeline.
    
    Usage:
        from api import APIRegistry
        
        # The API is the entry point to the pipeline
        app = APIRegistry.get_app()
    """
    
    @staticmethod
    def get_app():
        """Get the FastAPI application."""
        return _lazy_import("app")
    
    @staticmethod
    def list_endpoints() -> List[str]:
        """List main API endpoints."""
        return [
            "GET /health",
            "GET /metrics", 
            "POST /query",
            "POST /v2/query",
            "POST /ingest",
            "GET /session/{session_id}"
        ]


__all__ = [
    "get_component",
    "create_app",
    "APIRegistry",
]
