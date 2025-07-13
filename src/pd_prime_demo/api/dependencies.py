# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""FastAPI dependencies for authentication, database sessions, and caching.

This module provides reusable dependencies that can be injected into
API endpoints for cross-cutting concerns.
"""

import os
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING

import asyncpg
from beartype import beartype
from fastapi import Depends, Header, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis

if TYPE_CHECKING:
    from ..services.quote_service import QuoteService
    from ..services.quote_wizard import QuoteWizardService

from ..core.auth.sso_manager import SSOManager
from ..core.cache import Cache, get_redis_client
from ..core.config import Settings, get_settings
from ..core.database import Database, get_db_session
from ..core.security import verify_jwt_token
from ..models.admin import AdminUser
from ..schemas.auth import CurrentUser
from ..services.admin.oauth2_admin_service import OAuth2AdminService
from ..services.admin.sso_admin_service import SSOAdminService

# Security scheme
security = HTTPBearer()


@beartype
async def get_db() -> AsyncGenerator[asyncpg.Connection, None]:
    """Provide database connection for dependency injection.

    Yields:
        asyncpg.Connection: Active database connection

    Note:
        Connection is automatically returned to pool after request completion.
    """
    async with get_db_session() as conn:
        yield conn


@beartype
async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    """Provide direct database connection for beartype-compatible injection.

    This dependency properly resolves the async generator for beartype compatibility
    while maintaining proper resource management through FastAPI's dependency system.

    Yields:
        asyncpg.Connection: Active database connection

    Note:
        This is designed for use with @beartype decorated endpoints.
        The async generator is resolved by FastAPI before beartype checks.
    """
    async with get_db_session() as conn:
        yield conn


# Alias for backward compatibility
get_db_raw = get_db_connection


@beartype
async def get_redis() -> Redis:
    """Provide Redis client for dependency injection.

    Returns:
        Redis[str]: Active Redis client with string responses
    """
    return get_redis_client()


@beartype
async def get_cache() -> Cache:
    """Provide Cache instance for dependency injection.

    Returns:
        Cache: Active Cache instance
    """
    redis = get_redis_client()
    return Cache(redis)


@beartype
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Validate JWT token and return current user.

    Args:
        credentials: HTTP Bearer token from request
        settings: Application settings

    Returns:
        dict: User information from JWT payload

    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials

    try:
        payload = await verify_jwt_token(token, settings.jwt_secret)
        return CurrentUser(
            user_id=payload.sub,
            username=payload.sub,  # In real app, fetch from DB
            email=f"{payload.sub}@example.com",  # In real app, fetch from DB
            client_id=getattr(
                payload, "client_id", f"client_{payload.sub}"
            ),  # Extract client_id from token
            scopes=payload.scopes,
        )
    except Exception as e:
        # NOTE: This is a dependency function, not an endpoint
        # We need to keep raising HTTPException here as FastAPI expects it
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


@beartype
async def get_optional_user(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
    settings: Settings = Depends(get_settings),
) -> CurrentUser | None:
    """Optionally validate JWT token if provided.

    Args:
        credentials: Optional HTTP Bearer token
        settings: Application settings

    Returns:
        CurrentUser | None: User information if authenticated, None otherwise
    """
    if not credentials:
        return None

    try:
        return await get_current_user(credentials, settings)
    except HTTPException:
        return None


@beartype
class PaginationParams:
    """Common pagination parameters for list endpoints."""

    def __init__(
        self,
        skip: int = 0,
        limit: int = 100,
    ) -> None:
        """Initialize pagination parameters.

        Args:
            skip: Number of records to skip (offset)
            limit: Maximum number of records to return

        Raises:
            HTTPException: If parameters are invalid
        """
        if skip < 0:
            # NOTE: This is a dependency class, not an endpoint
            # We need to keep raising HTTPException here as FastAPI expects it
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Skip parameter cannot be negative",
            )

        if limit < 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit must be at least 1",
            )

        if limit > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Limit cannot exceed 1000",
            )

        self.skip = skip
        self.limit = limit


@beartype
async def get_demo_user() -> CurrentUser:
    """Provide demo user for development/demo purposes.

    Returns:
        CurrentUser: Demo user with full access

    Note:
        This bypasses authentication for demo purposes only.
        Remove in production environment.
    """
    return CurrentUser(
        user_id="demo-user-123",
        username="demo_user",
        email="demo@example.com",
        client_id="client_demo-user-123",
        scopes=["read", "write", "admin"],
    )


@beartype
async def get_optional_bearer_token(
    authorization: str | None = Header(default=None),
) -> HTTPAuthorizationCredentials | None:
    """Extract optional Bearer token from Authorization header.

    Args:
        authorization: Authorization header value

    Returns:
        HTTPAuthorizationCredentials if Bearer token present, None otherwise
    """
    if not authorization or not authorization.startswith("Bearer "):
        return None

    token = authorization[7:]  # Remove "Bearer " prefix
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@beartype
async def get_user_with_demo_fallback(
    credentials: HTTPAuthorizationCredentials | None = Depends(
        get_optional_bearer_token
    ),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Get current user with demo fallback based on environment.

    Returns production user if DEMO_MODE=false or JWT token provided,
    otherwise returns demo user for development/demo purposes.

    Args:
        credentials: Optional HTTP Bearer token
        settings: Application settings

    Returns:
        CurrentUser: Authenticated user or demo user based on mode

    Note:
        Set DEMO_MODE=true for demo authentication bypass.
        Set DEMO_MODE=false for production JWT authentication.
    """
    demo_mode = os.getenv("DEMO_MODE", "false").lower() == "true"

    # If demo mode is enabled and no credentials provided, use demo user
    if demo_mode and not credentials:
        return await get_demo_user()

    # If credentials provided, always validate (even in demo mode)
    if credentials:
        try:
            return await get_current_user(credentials, settings)
        except HTTPException:
            # In demo mode, fall back to demo user if JWT fails
            if demo_mode:
                return await get_demo_user()
            raise

    # Production mode requires authentication
    # NOTE: This is a dependency function, not an endpoint
    # We need to keep raising HTTPException here as FastAPI expects it
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required",
        headers={"WWW-Authenticate": "Bearer"},
    )


@beartype
async def verify_api_key(
    credentials: HTTPAuthorizationCredentials = Security(HTTPBearer()),
    settings: Settings = Depends(get_settings),
) -> bool:
    """Verify API key for service-to-service authentication.

    Args:
        credentials: API key from request header
        settings: Application settings

    Returns:
        bool: True if API key is valid

    Raises:
        HTTPException: If API key is invalid
    """
    # In production, this would check against a database or external service
    # For now, we'll use a simple comparison with the secret key
    if credentials.credentials != settings.secret_key:
        # NOTE: This is a dependency function, not an endpoint
        # We need to keep raising HTTPException here as FastAPI expects it
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key"
        )
    return True


# Admin-specific dependencies


@beartype
async def get_current_admin_user(
    credentials: HTTPAuthorizationCredentials = Security(security),
    settings: Settings = Depends(get_settings),
    db: asyncpg.Connection = Depends(get_db_connection),
) -> AdminUser:
    """Validate JWT token and return current admin user.

    Args:
        credentials: HTTP Bearer token from request
        settings: Application settings
        db: Database connection

    Returns:
        AdminUser: Admin user information

    Raises:
        HTTPException: If token is invalid, expired, or user is not an admin
    """
    token = credentials.credentials

    try:
        payload = await verify_jwt_token(token, settings.jwt_secret)

        # Get admin user from database
        user_row = await db.fetchrow(
            """
            SELECT u.*, r.permissions
            FROM admin_users u
            LEFT JOIN admin_roles r ON u.role_id = r.id
            WHERE u.id = $1 AND u.deactivated_at IS NULL
            """,
            payload.sub,
        )

        if not user_row:
            # NOTE: This is a dependency function, not an endpoint
            # We need to keep raising HTTPException here as FastAPI expects it
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized as admin",
            )

        # Convert row to AdminUser model
        user_data = dict(user_row)
        permissions = user_data.pop("permissions", [])

        admin_user = AdminUser(**user_data)

        # Note: effective_permissions is a computed field based on role
        # No need to set it manually as it's calculated from the role

        return admin_user

    except HTTPException:
        raise
    except Exception as e:
        # NOTE: This is a dependency function, not an endpoint
        # We need to keep raising HTTPException here as FastAPI expects it
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


@beartype
async def get_oauth2_admin_service(
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: Redis = Depends(get_redis),
) -> OAuth2AdminService:
    """Provide OAuth2 admin service instance.

    Args:
        db: Database connection
        redis: Redis client

    Returns:
        OAuth2AdminService: Service instance for OAuth2 admin operations
    """
    from ..core.database import Database

    # Wrap connections in our database/cache interfaces
    database = Database(db)
    cache = Cache(redis)

    return OAuth2AdminService(database, cache)


@beartype
async def get_quote_service(
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: Redis = Depends(get_redis),
) -> "QuoteService":
    """Provide Quote service instance.

    Args:
        db: Database connection
        redis: Redis client

    Returns:
        QuoteService: Service instance for quote operations
    """
    from ..core.database import Database
    from ..services.quote_service import QuoteService
    from ..websocket.app import get_manager

    # Wrap connections in our database/cache interfaces
    database = Database(db)
    cache = Cache(redis)

    # Get WebSocket manager for real-time updates
    websocket_manager = None
    try:
        # Get the WebSocket manager instance for real-time updates
        websocket_manager = get_manager()
    except Exception:
        # WebSocket manager might not be available in all contexts (e.g., testing)
        pass

    # Note: Rating engine will be injected when Agent 06 creates it
    return QuoteService(
        database, cache, rating_engine=None, websocket_manager=websocket_manager
    )


@beartype
async def get_wizard_service(
    redis: Redis = Depends(get_redis),
) -> "QuoteWizardService":
    """Provide Quote Wizard service instance.

    Args:
        redis: Redis client

    Returns:
        QuoteWizardService: Service instance for wizard operations
    """
    from ..services.quote_wizard import QuoteWizardService

    # Wrap redis in our cache interface
    cache = Cache(redis)

    return QuoteWizardService(cache)


@beartype
async def get_sso_admin_service(
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: Redis = Depends(get_redis),
) -> SSOAdminService:
    """Provide SSO admin service instance.

    Args:
        db: Database connection
        redis: Redis client

    Returns:
        SSOAdminService: Service instance for SSO admin operations
    """
    from ..core.database import Database

    # Wrap connections in our database/cache interfaces
    database = Database(db)
    cache = Cache(redis)

    return SSOAdminService(database, cache)


@beartype
async def get_sso_manager(
    db: asyncpg.Connection = Depends(get_db_connection),
    redis: Redis = Depends(get_redis),
) -> SSOManager:
    """Provide SSO manager instance.

    Args:
        db: Database connection
        redis: Redis client

    Returns:
        SSOManager: Service instance for SSO operations
    """
    from ..core.database import Database

    # Wrap connections in our database/cache interfaces
    database = Database(db)
    cache = Cache(redis)

    # Initialize the SSO manager
    sso_manager = SSOManager(database, cache)
    await sso_manager.initialize()

    return sso_manager


@beartype
def get_database() -> Database:
    """Backward-compatibility wrapper returning global Database instance.

    Several legacy components import `get_database` from this module. The
    canonical helper now lives in `pd_prime_demo.core.database_enhanced` (and
    previously in `pd_prime_demo.core.database`).  To minimise churn while we
    update callers, we simply delegate to the core helper here.
    """
    from ..core.database_enhanced import get_database as _core_get_database

    return _core_get_database()
