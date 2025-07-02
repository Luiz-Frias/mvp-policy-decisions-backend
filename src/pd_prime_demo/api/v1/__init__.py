"""API v1 router aggregation.

This module combines all v1 API routers into a single router
that can be mounted on the main FastAPI application.
"""

from fastapi import APIRouter

from .claims import router as claims_router
from .customers import router as customers_router
from .health import router as health_router
from .policies import router as policies_router

# Create main v1 router
router = APIRouter(prefix="/api/v1")

# Include all sub-routers
router.include_router(health_router, tags=["health"])
router.include_router(policies_router, prefix="/policies", tags=["policies"])
router.include_router(customers_router, prefix="/customers", tags=["customers"])
router.include_router(claims_router, prefix="/claims", tags=["claims"])


__all__ = ["router"]
