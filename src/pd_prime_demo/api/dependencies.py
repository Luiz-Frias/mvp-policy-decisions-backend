"""FastAPI dependencies for authentication, database sessions, and caching.

This module provides reusable dependencies that can be injected into
API endpoints for cross-cutting concerns.
"""

import os
from collections.abc import AsyncGenerator

import asyncpg
from beartype import beartype
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis

from ..core.cache import get_redis_client
from ..core.config import Settings, get_settings
from ..core.database import get_db_session
from ..core.security import verify_jwt_token
from ..schemas.auth import CurrentUser

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


@beartype
async def get_redis() -> Redis:
    """Provide Redis client for dependency injection.

    Returns:
        Redis[str]: Active Redis client with string responses
    """
    return get_redis_client()


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
            scopes=payload.scopes,
        )
    except Exception as e:
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
        Optional[CurrentUser]: User information if authenticated, None otherwise
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
        scopes=["read", "write", "admin"],
    )


@beartype
async def get_user_with_demo_fallback(
    credentials: HTTPAuthorizationCredentials | None = Security(security),
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
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Invalid API key"
        )
    return True
