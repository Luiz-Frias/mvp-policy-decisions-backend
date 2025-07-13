# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""API v1 router aggregation.

This module combines all v1 API routers into a single router
that can be mounted on the main FastAPI application.
"""

from fastapi import APIRouter

from .admin import oauth2_router as admin_oauth2_router
from .admin.pricing_controls import router as admin_pricing_router
from .admin.quotes import router as admin_quotes_router
from .admin.rate_management import router as admin_rate_router
from .admin.sso_management import router as admin_sso_router
from .admin.websocket_admin import router as admin_websocket_router
from .api_keys import router as api_keys_router
from .auth import router as auth_router
from .claims import router as claims_router
from .compliance import router as compliance_router
from .customers import router as customers_router
from .health import router as health_router
from .mfa import router as mfa_router
from .monitoring import router as monitoring_router
from .oauth2 import router as oauth2_router
from .policies import router as policies_router
from .quotes import router as quotes_router
from .service_health import router as service_health_router
from .sso_auth import router as sso_auth_router

# Create main v1 router
router = APIRouter(prefix="/api/v1")

# Include all sub-routers
router.include_router(health_router, tags=["health"])
router.include_router(service_health_router, tags=["service-health"])
router.include_router(monitoring_router, tags=["monitoring"])
router.include_router(policies_router, prefix="/policies", tags=["policies"])
router.include_router(customers_router, prefix="/customers", tags=["customers"])
router.include_router(claims_router, prefix="/claims", tags=["claims"])
router.include_router(quotes_router, tags=["quotes"])
router.include_router(compliance_router, tags=["compliance"])

# OAuth2 and authentication
router.include_router(oauth2_router, tags=["oauth2"])
router.include_router(api_keys_router, tags=["api-keys"])
router.include_router(sso_auth_router, tags=["sso-auth"])
router.include_router(mfa_router, tags=["mfa"])
router.include_router(auth_router, tags=["authentication"])

# Admin endpoints
router.include_router(admin_oauth2_router, prefix="/admin", tags=["admin"])
router.include_router(admin_sso_router, tags=["admin-sso"])
router.include_router(admin_pricing_router, tags=["admin-pricing"])
router.include_router(admin_rate_router, tags=["admin-rate-management"])
router.include_router(
    admin_quotes_router, prefix="/admin/quotes", tags=["admin-quotes"]
)
router.include_router(admin_websocket_router, prefix="/admin", tags=["admin-websocket"])


__all__ = ["router"]
