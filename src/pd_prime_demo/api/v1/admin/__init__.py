"""Admin API endpoints."""

from .oauth2_management import router as oauth2_router
from .quotes import router as admin_quotes_router

__all__ = ["oauth2_router", "admin_quotes_router"]