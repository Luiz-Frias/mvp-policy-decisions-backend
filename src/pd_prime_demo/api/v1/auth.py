"""Authentication endpoints including SSO support."""

from uuid import uuid4

import asyncpg
from beartype import beartype
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from pd_prime_demo.core.cache import Cache, get_cache
from pd_prime_demo.core.database import Database

from ...core.auth.sso_manager import SSOManager
from ...core.result_types import Err
from ...core.security import Security, get_security
from ..dependencies import get_db_connection, get_sso_manager
from ..response_patterns import ErrorResponse, handle_result

router = APIRouter(prefix="/auth", tags=["authentication"])


class UserInfo(BaseModel):
    """User information model for API responses."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: str = Field(..., description="User ID")
    email: str = Field(..., description="User email")
    first_name: str = Field(..., description="First name")
    last_name: str = Field(..., description="Last name")
    role: str = Field(..., description="User role")
    sso_provider: str | None = Field(
        default=None, description="SSO provider if applicable"
    )


class LoginRequest(BaseModel):
    """Request model for email/password login."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    email: str = Field(..., description="User email")
    password: str = Field(..., description="User password")


class LoginResponse(BaseModel):
    """Response model for successful login."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")
    expires_in: int = Field(..., description="Token expiration in seconds")
    user: UserInfo = Field(..., description="User information")


class SSOLoginInitResponse(BaseModel):
    """Response model for SSO login initiation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    authorization_url: str = Field(..., description="URL to redirect user to")
    state: str = Field(..., description="State parameter for CSRF protection")


@router.post("/login")
@beartype
async def login(
    request: LoginRequest,
    response: Response,
    db: asyncpg.Connection = Depends(get_db_connection),
    security: Security = Depends(get_security),
) -> LoginResponse | ErrorResponse:
    """Login with email and password.

    This endpoint is for traditional email/password authentication.
    For SSO, use the /auth/sso/{provider}/login endpoint.
    """
    # Check if user exists
    user = await db.fetchrow(
        "SELECT * FROM users WHERE email = $1 AND is_active = true", request.email
    )

    if not user:
        return handle_result(Err("Invalid email or password"), response)

    # Check if user is SSO-only
    if user["password_hash"].startswith("sso:"):
        return handle_result(
            Err(
                "This account uses SSO authentication. Please use the SSO login option."
            ),
            response,
        )

    # Verify password
    if not security.verify_password(request.password, user["password_hash"]):
        # Update failed login attempts
        await db.execute(
            "UPDATE users SET failed_login_attempts = failed_login_attempts + 1 WHERE id = $1",
            user["id"],
        )
        return handle_result(Err("Invalid email or password"), response)

    # Reset failed login attempts and update last login
    await db.execute(
        """
        UPDATE users
        SET failed_login_attempts = 0, last_login_at = CURRENT_TIMESTAMP
        WHERE id = $1
        """,
        user["id"],
    )

    # Create access token
    token_data = security.create_access_token(
        subject=str(user["id"]), scopes=[user["role"]]  # Simple role-based scopes
    )

    # Log authentication event
    await db.execute(
        """
        INSERT INTO auth_logs (user_id, auth_method, status, created_at)
        VALUES ($1, 'password', 'success', CURRENT_TIMESTAMP)
        """,
        user["id"],
    )

    return LoginResponse(
        access_token=token_data.access_token,
        token_type=token_data.token_type,
        expires_in=token_data.expires_in,
        user=UserInfo(
            id=str(user["id"]),
            email=user["email"],
            first_name=user["first_name"],
            last_name=user["last_name"],
            role=user["role"],
        ),
    )


class SSOProviderInfo(BaseModel):
    """SSO provider information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    name: str = Field(..., description="Provider name")
    display_name: str = Field(..., description="Display name")
    login_url: str = Field(..., description="Login URL")


class SSOProvidersResponse(BaseModel):
    """Response model for SSO providers list."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    providers: list[SSOProviderInfo] = Field(..., description="Available SSO providers")


@router.get("/sso/providers", response_model=SSOProvidersResponse)
@beartype
async def list_sso_providers(
    sso_manager: SSOManager = Depends(get_sso_manager),
) -> SSOProvidersResponse:
    """List available SSO providers for login."""
    providers = sso_manager.list_providers()

    return SSOProvidersResponse(
        providers=[
            SSOProviderInfo(
                name=provider,
                display_name=provider.title(),
                login_url=f"/auth/sso/{provider}/login",
            )
            for provider in providers
        ]
    )


@router.get("/sso/{provider}/login")
@beartype
async def sso_login_init(
    provider: str,
    response: Response,
    redirect_uri: str | None = Query(None, description="Custom redirect URI"),
    sso_manager: SSOManager = Depends(get_sso_manager),
    cache: Cache = Depends(get_cache),
) -> SSOLoginInitResponse | ErrorResponse:
    """Initiate SSO login flow.

    This endpoint generates the authorization URL for the SSO provider
    and returns it along with a state parameter for CSRF protection.
    """
    sso_provider = sso_manager.get_provider(provider)
    if not sso_provider:
        return handle_result(
            Err(
                f"SSO provider '{provider}' not found. Available providers: {sso_manager.list_providers()}"
            ),
            response,
        )

    # Generate state for CSRF protection
    state = sso_provider.generate_state()

    # Store state in cache for validation (15 minutes expiry)
    await cache.set(
        f"sso:state:{state}",
        {
            "provider": provider,
            "redirect_uri": redirect_uri,
            "created_at": str(uuid4()),  # Timestamp proxy
        },
        ttl=900,
    )

    # Generate nonce for OIDC
    nonce = None
    if hasattr(sso_provider, "generate_nonce"):
        nonce = sso_provider.generate_nonce()
        await cache.set(f"sso:nonce:{state}", nonce, ttl=900)

    # Get authorization URL
    auth_url_result = await sso_provider.get_authorization_url(
        state=state,
        nonce=nonce,
    )

    if isinstance(auth_url_result, Err):
        return handle_result(
            Err(f"Failed to generate authorization URL: {auth_url_result.error}"),
            response,
        )

    return SSOLoginInitResponse(authorization_url=auth_url_result.value, state=state)


@router.get("/sso/{provider}/callback")
@beartype
async def sso_callback(
    provider: str,
    response: Response,
    code: str = Query(..., description="Authorization code"),
    state: str = Query(..., description="State parameter"),
    error: str | None = Query(None, description="Error from provider"),
    error_description: str | None = Query(None, description="Error description"),
    request: Request | None = None,
    sso_manager: SSOManager = Depends(get_sso_manager),
    cache: Cache = Depends(get_cache),
    db: asyncpg.Connection = Depends(get_db_connection),
    security: Security = Depends(get_security),
) -> LoginResponse | RedirectResponse | ErrorResponse:
    """Handle SSO callback after user authentication.

    This endpoint is called by the SSO provider after the user
    has authenticated. It exchanges the authorization code for
    tokens and creates or updates the user account.
    """
    # Check for errors from provider
    if error:
        return handle_result(
            Err(
                f"SSO authentication failed: {error} - {error_description or 'No details provided'}"
            ),
            response,
        )

    # Validate state
    state_data = await cache.get(f"sso:state:{state}")
    if not state_data or state_data.get("provider") != provider:
        return handle_result(
            Err("Invalid state parameter. Please try logging in again."), response
        )

    # Get SSO provider
    sso_provider = sso_manager.get_provider(provider)
    if not sso_provider:
        return handle_result(Err(f"SSO provider '{provider}' not found"), response)

    # Exchange code for tokens
    token_result = await sso_provider.exchange_code_for_token(code, state)
    if isinstance(token_result, Err):
        return handle_result(
            Err(f"Failed to exchange code for token: {token_result.error}"), response
        )

    tokens = token_result.value

    # Get user info
    user_info_result = await sso_provider.get_user_info(tokens["access_token"])
    if isinstance(user_info_result, Err):
        return handle_result(
            Err(f"Failed to get user info: {user_info_result.error}"), response
        )

    sso_user_info = user_info_result.value

    # Create or update user
    user_result = await sso_manager.create_or_update_user(sso_user_info, provider)
    if isinstance(user_result, Err):
        return handle_result(user_result, response)

    user = user_result.value

    # Create session
    session_id = uuid4()
    await db.execute(
        """
        INSERT INTO user_sessions (
            id, user_id, session_token_hash, auth_method,
            sso_provider_id, ip_address, user_agent,
            created_at, last_activity_at, expires_at
        ) VALUES (
            $1, $2, $3, $4,
            (SELECT id FROM sso_providers WHERE provider_name = $5),
            $6, $7,
            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP,
            CURRENT_TIMESTAMP + INTERVAL '8 hours'
        )
        """,
        session_id,
        user.id,
        security.hash_password(str(session_id)),  # Hash session token
        f"sso_{provider}",
        provider,
        request.client.host if request and request.client else None,
        request.headers.get("user-agent") if request else None,
    )

    # Create access token
    token_data = security.create_access_token(subject=str(user.id), scopes=[user.role])

    # Store refresh token if provided
    if "refresh_token" in tokens:
        await cache.set(
            f"sso:refresh:{user.id}:{provider}",
            tokens["refresh_token"],
            ttl=30 * 24 * 3600,  # 30 days
        )

    # Clean up state and nonce
    await cache.delete(f"sso:state:{state}")
    await cache.delete(f"sso:nonce:{state}")

    # Check if we should redirect
    redirect_uri = state_data.get("redirect_uri")
    if redirect_uri:
        # In production, validate redirect_uri against whitelist
        return RedirectResponse(
            url=f"{redirect_uri}?token={token_data.access_token}", status_code=302
        )

    return LoginResponse(
        access_token=token_data.access_token,
        token_type=token_data.token_type,
        expires_in=token_data.expires_in,
        user=UserInfo(
            id=str(user.id),
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            role=user.role,
            sso_provider=provider,
        ),
    )


class LogoutResponse(BaseModel):
    """Response model for logout."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    message: str = Field(..., description="Logout confirmation message")


@router.post("/logout", response_model=LogoutResponse)
@beartype
async def logout(
    response: Response,
    session_id: str = Query(..., description="Session ID to invalidate"),
    db: asyncpg.Connection = Depends(get_db_connection),
    cache: Cache = Depends(get_cache),
) -> LogoutResponse | ErrorResponse:
    """Logout and invalidate session.

    This endpoint invalidates the user's session and optionally
    revokes SSO tokens if the session was created via SSO.
    """
    # Get session info
    session = await db.fetchrow(
        """
        SELECT s.*, u.id as user_id, sp.provider_name
        FROM user_sessions s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN sso_providers sp ON s.sso_provider_id = sp.id
        WHERE s.id = $1 AND s.revoked_at IS NULL
        """,
        session_id,
    )

    if not session:
        return handle_result(Err("Session not found or already invalidated"), response)

    # Revoke session
    await db.execute(
        """
        UPDATE user_sessions
        SET revoked_at = CURRENT_TIMESTAMP, revoke_reason = 'user_logout'
        WHERE id = $1
        """,
        session_id,
    )

    # If SSO session, try to revoke tokens
    if session["provider_name"]:
        # Get SSO manager
        database = Database(db)
        sso_manager = SSOManager(database, cache)
        await sso_manager.initialize()

        provider = sso_manager.get_provider(session["provider_name"])
        if provider:
            # Get refresh token if available
            refresh_token = await cache.get(
                f"sso:refresh:{session['user_id']}:{session['provider_name']}"
            )
            if refresh_token:
                # Try to revoke token
                await provider.revoke_token(refresh_token, "refresh_token")
                # Clean up cached token
                await cache.delete(
                    f"sso:refresh:{session['user_id']}:{session['provider_name']}"
                )

    return LogoutResponse(message="Successfully logged out")
