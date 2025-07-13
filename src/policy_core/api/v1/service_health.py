# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Service-level health checks for critical business services.

This module provides health checks for business services like
rating engine, quote service, and other critical components.
"""

import time
from datetime import datetime

from beartype import beartype
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from policy_core.core.cache import Cache
from policy_core.core.config import Settings, get_settings
from policy_core.core.database import Database
from policy_core.core.result_types import Err

from ...services.quote_service import QuoteService
from ...services.rating_engine import RatingEngine
from ..dependencies import get_cache, get_db_raw

router = APIRouter()


class ServiceHealthStatus(BaseModel):
    """Individual service health status."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    service_name: str = Field(..., description="Name of the service")
    status: str = Field(..., pattern=r"^(healthy|unhealthy|degraded)$")
    initialized: bool = Field(..., description="Whether service is initialized")
    response_time_ms: float | None = Field(
        default=None, ge=0, description="Response time in milliseconds"
    )
    message: str | None = Field(default=None, description="Additional status message")
    error_details: str | None = Field(default=None, description="Error details if any")
    required_config: list[str] | None = Field(
        default=None, description="Required configuration if missing"
    )


class ServiceHealthResponse(BaseModel):
    """Overall service health response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: str = Field(..., pattern=r"^(healthy|unhealthy|degraded)$")
    timestamp: datetime = Field(..., description="Health check timestamp")
    services: list[ServiceHealthStatus] = Field(
        ..., description="Individual service statuses"
    )
    total_response_time_ms: float = Field(..., ge=0, description="Total response time")
    critical_issues: list[str] = Field(
        default_factory=list, description="Critical issues found"
    )


@router.get("/health/services", response_model=ServiceHealthResponse)
@beartype
async def check_service_health(
    db: Database = Depends(get_db_raw),
    cache: Cache = Depends(get_cache),
    settings: Settings = Depends(get_settings),
) -> ServiceHealthResponse:
    """Check health of all critical business services.

    This endpoint validates that all services are properly configured
    and can perform their core functions.

    Returns:
        ServiceHealthResponse: Detailed service health information
    """
    start_time = time.time()
    service_statuses = []
    critical_issues = []
    overall_status = "healthy"

    # Check Rating Engine
    rating_start = time.time()
    try:
        rating_engine = RatingEngine(db, cache)

        # Check if engine can initialize
        init_result = await rating_engine.initialize()
        rating_response_time = (time.time() - rating_start) * 1000

        if isinstance(init_result, Err):
            service_statuses.append(
                ServiceHealthStatus(
                    service_name="rating_engine",
                    status="unhealthy",
                    initialized=False,
                    response_time_ms=rating_response_time,
                    message="Rating engine initialization failed",
                    error_details=init_result.error,
                    required_config=["Rate tables must be seeded in database"],
                )
            )
            critical_issues.append(
                "Rating Engine: No rate tables configured - quotes will fail"
            )
            overall_status = "unhealthy"
        else:
            # Test a simple calculation
            test_start = time.time()
            test_result = await rating_engine._get_minimum_premium("CA", "AUTO")
            test_time = (time.time() - test_start) * 1000

            if isinstance(test_result, Err):
                service_statuses.append(
                    ServiceHealthStatus(
                        service_name="rating_engine",
                        status="degraded",
                        initialized=True,
                        response_time_ms=rating_response_time + test_time,
                        message="Rating engine initialized but calculations may fail",
                        error_details=test_result.error,
                    )
                )
                if overall_status == "healthy":
                    overall_status = "degraded"
            else:
                service_statuses.append(
                    ServiceHealthStatus(
                        service_name="rating_engine",
                        status="healthy",
                        initialized=True,
                        response_time_ms=rating_response_time + test_time,
                        message="Rating engine operational",
                    )
                )
    except Exception as e:
        rating_response_time = (time.time() - rating_start) * 1000
        service_statuses.append(
            ServiceHealthStatus(
                service_name="rating_engine",
                status="unhealthy",
                initialized=False,
                response_time_ms=rating_response_time,
                message="Rating engine creation failed",
                error_details=str(e),
            )
        )
        critical_issues.append(f"Rating Engine: Service unavailable - {str(e)}")
        overall_status = "unhealthy"

    # Check Quote Service
    quote_start = time.time()
    try:
        # Initialize with rating engine if available
        quote_rating_engine: RatingEngine | None = None
        rating_engine_available = False
        try:
            quote_rating_engine = RatingEngine(db, cache)
            await quote_rating_engine.initialize()
            rating_engine_available = True
        except Exception:
            quote_rating_engine = None
            rating_engine_available = False

        QuoteService(db, cache, quote_rating_engine)
        quote_response_time = (time.time() - quote_start) * 1000

        if not rating_engine_available:
            service_statuses.append(
                ServiceHealthStatus(
                    service_name="quote_service",
                    status="degraded",
                    initialized=True,
                    response_time_ms=quote_response_time,
                    message="Quote service available but calculations will fail",
                    error_details="No rating engine configured",
                    required_config=["RatingEngine instance required"],
                )
            )
            critical_issues.append(
                "Quote Service: No rating engine - all quote calculations will fail"
            )
            if overall_status == "healthy":
                overall_status = "degraded"
        else:
            service_statuses.append(
                ServiceHealthStatus(
                    service_name="quote_service",
                    status="healthy",
                    initialized=True,
                    response_time_ms=quote_response_time,
                    message="Quote service operational with rating engine",
                )
            )
    except Exception as e:
        quote_response_time = (time.time() - quote_start) * 1000
        service_statuses.append(
            ServiceHealthStatus(
                service_name="quote_service",
                status="unhealthy",
                initialized=False,
                response_time_ms=quote_response_time,
                message="Quote service creation failed",
                error_details=str(e),
            )
        )
        critical_issues.append(f"Quote Service: Service unavailable - {str(e)}")
        overall_status = "unhealthy"

    # Check Admin Services
    admin_start = time.time()
    try:
        # Check if admin tables exist
        admin_tables_query = """
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name IN ('admin_users', 'admin_roles', 'admin_permissions')
        """
        table_count = await db.fetchval(admin_tables_query)
        admin_response_time = (time.time() - admin_start) * 1000

        if table_count < 3:
            service_statuses.append(
                ServiceHealthStatus(
                    service_name="admin_services",
                    status="unhealthy",
                    initialized=False,
                    response_time_ms=admin_response_time,
                    message="Admin tables missing",
                    error_details=f"Only {table_count}/3 admin tables found",
                    required_config=["Run database migrations to create admin tables"],
                )
            )
            critical_issues.append("Admin Services: Database tables not created")
            overall_status = "unhealthy"
        else:
            # Check if any admin users exist
            admin_count = await db.fetchval("SELECT COUNT(*) FROM admin_users")
            if admin_count == 0:
                service_statuses.append(
                    ServiceHealthStatus(
                        service_name="admin_services",
                        status="degraded",
                        initialized=True,
                        response_time_ms=admin_response_time,
                        message="Admin tables exist but no admin users created",
                        error_details="No admin users in system",
                        required_config=["Create initial admin user"],
                    )
                )
                if overall_status == "healthy":
                    overall_status = "degraded"
            else:
                service_statuses.append(
                    ServiceHealthStatus(
                        service_name="admin_services",
                        status="healthy",
                        initialized=True,
                        response_time_ms=admin_response_time,
                        message=f"Admin services operational with {admin_count} users",
                    )
                )
    except Exception as e:
        admin_response_time = (time.time() - admin_start) * 1000
        service_statuses.append(
            ServiceHealthStatus(
                service_name="admin_services",
                status="unhealthy",
                initialized=False,
                response_time_ms=admin_response_time,
                message="Admin services check failed",
                error_details=str(e),
            )
        )
        overall_status = "unhealthy"

    # Check External Integrations
    external_start = time.time()
    external_status = "healthy"
    external_message = "All external integrations configured"
    external_errors = []

    # Check VIN decoder configuration
    if not settings.vin_api_key or not settings.vin_api_endpoint:
        external_status = "degraded"
        external_errors.append("VIN decoder API not configured")
        critical_issues.append(
            "External Services: VIN decoder not configured - vehicle lookups will fail"
        )

    # Check SSO providers
    if not any(
        [
            settings.google_oauth_client_id,
            settings.azure_ad_client_id,
            settings.okta_domain,
        ]
    ):
        if external_status == "healthy":
            external_status = "degraded"
        external_errors.append("No SSO providers configured")

    external_response_time = (time.time() - external_start) * 1000

    service_statuses.append(
        ServiceHealthStatus(
            service_name="external_integrations",
            status=external_status,
            initialized=external_status != "unhealthy",
            response_time_ms=external_response_time,
            message=(
                external_message if not external_errors else "Some integrations missing"
            ),
            error_details="; ".join(external_errors) if external_errors else None,
            required_config=(
                [
                    "VIN_API_KEY",
                    "VIN_API_ENDPOINT",
                    "SSO provider credentials",
                ]
                if external_errors
                else None
            ),
        )
    )

    if external_status != "healthy" and overall_status == "healthy":
        overall_status = external_status

    total_response_time = (time.time() - start_time) * 1000

    return ServiceHealthResponse(
        status=overall_status,
        timestamp=datetime.utcnow(),
        services=service_statuses,
        total_response_time_ms=total_response_time,
        critical_issues=critical_issues,
    )


@router.get("/health/services/rating", response_model=ServiceHealthStatus)
@beartype
async def check_rating_engine_health(
    db: Database = Depends(get_db_raw),
    cache: Cache = Depends(get_cache),
) -> ServiceHealthStatus:
    """Check rating engine health specifically.

    Returns:
        ServiceHealthStatus: Rating engine health status
    """
    start_time = time.time()

    try:
        rating_engine = RatingEngine(db, cache)

        # Check initialization
        init_result = await rating_engine.initialize()

        if isinstance(init_result, Err):
            return ServiceHealthStatus(
                service_name="rating_engine",
                status="unhealthy",
                initialized=False,
                response_time_ms=(time.time() - start_time) * 1000,
                message="Rating engine cannot initialize",
                error_details=init_result.error,
                required_config=[
                    "Seed rate tables using: python scripts/seed_rate_tables.py",
                    "Configure state-specific rules",
                    "Set up territory factors",
                ],
            )

        # Test calculations for each state
        test_states = ["CA", "TX", "NY"]
        failed_states = []

        for state in test_states:
            test_result = await rating_engine._get_base_rates(state, "AUTO")
            if isinstance(test_result, Err):
                failed_states.append(state)

        response_time = (time.time() - start_time) * 1000

        if failed_states:
            return ServiceHealthStatus(
                service_name="rating_engine",
                status="degraded",
                initialized=True,
                response_time_ms=response_time,
                message=f"Rating unavailable for states: {', '.join(failed_states)}",
                error_details="Missing rate tables for some states",
                required_config=[f"Add rate tables for: {', '.join(failed_states)}"],
            )

        return ServiceHealthStatus(
            service_name="rating_engine",
            status="healthy",
            initialized=True,
            response_time_ms=response_time,
            message="Rating engine fully operational",
        )

    except Exception as e:
        return ServiceHealthStatus(
            service_name="rating_engine",
            status="unhealthy",
            initialized=False,
            response_time_ms=(time.time() - start_time) * 1000,
            message="Rating engine error",
            error_details=str(e),
        )
