# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""OAuth2 authorization endpoints."""

from typing import Any
from uuid import UUID

from beartype import beartype
from fastapi import APIRouter, Depends, Form, Query, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict

from pd_prime_demo.core.cache import Cache
from pd_prime_demo.core.config import Settings, get_settings
from pd_prime_demo.core.database import Database

from ...core.auth.oauth2 import OAuth2Server
from ..dependencies import get_db_connection, get_redis
from ..response_patterns import ErrorResponse

router = APIRouter(prefix="/oauth2", tags=["oauth2"])


class TokenRequest(BaseModel):
    """OAuth2 token request model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    grant_type: str
    client_id: str | None = None
    client_secret: str | None = None
    code: str | None = None
    redirect_uri: str | None = None
    refresh_token: str | None = None
    scope: str | None = None
    username: str | None = None
    password: str | None = None
    code_verifier: str | None = None


class IntrospectRequest(BaseModel):
    """Token introspection request model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    token: str
    token_type_hint: str | None = None


@beartype
async def get_oauth2_server(
    db: Any = Depends(get_db_connection),
    redis: Any = Depends(get_redis),
    settings: Settings = Depends(get_settings),
) -> OAuth2Server:
    """Get OAuth2 server instance."""
    # Wrap connections in our interfaces
    database = Database(db)
    cache = Cache(redis)

    return OAuth2Server(database, cache, settings)


@router.get("/authorize")
@beartype
async def authorize(
    response_type: str = Query(..., description="OAuth2 response type (code or token)"),
    client_id: str = Query(..., description="OAuth2 client ID"),
    redirect_uri: str = Query(..., description="Redirect URI for response"),
    scope: str = Query(..., description="Space-separated list of scopes"),
    state: str | None = Query(None, description="State parameter for CSRF protection"),
    code_challenge: str | None = Query(None, description="PKCE code challenge"),
    code_challenge_method: str | None = Query(
        None, description="PKCE challenge method"
    ),
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> Any:
    """OAuth2 authorization endpoint.

    This endpoint handles the authorization request for the OAuth2 flow.
    For production, this would redirect to a login page if user is not authenticated.

    Args:
        response_type: OAuth2 response type (code or token)
        client_id: Client identifier
        redirect_uri: Where to redirect after authorization
        scope: Requested scopes
        state: CSRF protection state
        code_challenge: PKCE challenge for public clients
        code_challenge_method: PKCE method (S256 or plain)
        oauth2_server: OAuth2 server instance

    Returns:
        Redirect to redirect_uri with authorization code or error
    """
    # In production, this would:
    # 1. Check if user is authenticated (redirect to login if not)
    # 2. Show consent screen if needed
    # 3. Generate authorization code and redirect

    # Check for authenticated user session
    # In production, this would check session cookies or JWT tokens
    user_id = await _get_authenticated_user_id(oauth2_server, client_id)

    result = await oauth2_server.authorize(
        response_type=response_type,
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        state=state,
        user_id=user_id,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
    )

    if result.is_err():
        error_str = result.unwrap_err()
        # Build error redirect
        error_params = f"error={error_str}"
        if state:
            error_params += f"&state={state}"

        separator = "&" if "?" in redirect_uri else "?"
        return RedirectResponse(url=f"{redirect_uri}{separator}{error_params}")

    # Build success redirect
    response_data = result.ok_value
    if not response_data:
        error_params = "error=server_error&error_description=Invalid response data"
        if state:
            error_params += f"&state={state}"
        separator = "&" if "?" in redirect_uri else "?"
        return RedirectResponse(url=f"{redirect_uri}{separator}{error_params}")

    if response_type == "code":
        params = f"code={response_data['code']}"
        if state:
            params += f"&state={state}"
        separator = "&" if "?" in redirect_uri else "?"
        return RedirectResponse(url=f"{redirect_uri}{separator}{params}")

    elif response_type == "token":
        # For implicit flow, parameters go in fragment
        params = f"access_token={response_data['access_token']}"
        params += f"&token_type={response_data['token_type']}"
        params += f"&expires_in={response_data['expires_in']}"
        if response_data.get("scope"):
            params += f"&scope={response_data['scope']}"
        if state:
            params += f"&state={state}"

        separator = "#" if "?" not in redirect_uri else "&"
        return RedirectResponse(url=f"{redirect_uri}{separator}{params}")


@router.post("/token")
@beartype
async def token(
    response: Response,
    grant_type: str = Form(...),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    code: str | None = Form(None),
    redirect_uri: str | None = Form(None),
    refresh_token: str | None = Form(None),
    scope: str | None = Form(None),
    username: str | None = Form(None),
    password: str | None = Form(None),
    code_verifier: str | None = Form(None),
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> (
    dict[str, Any] | ErrorResponse
):  # SYSTEM_BOUNDARY - OAuth2 spec requires specific response format
    """OAuth2 token endpoint.

    This endpoint handles all OAuth2 token requests including:
    - authorization_code: Exchange auth code for tokens
    - refresh_token: Get new access token using refresh token
    - client_credentials: Get token for client (no user context)
    - password: Get token using username/password (trusted clients only)

    Args:
        grant_type: OAuth2 grant type
        client_id: Client identifier
        client_secret: Client secret (for confidential clients)
        code: Authorization code (for authorization_code grant)
        redirect_uri: Must match the one used in /authorize
        refresh_token: Refresh token (for refresh_token grant)
        scope: Requested scopes
        username: Username (for password grant)
        password: Password (for password grant)
        code_verifier: PKCE verifier (for authorization_code with PKCE)
        oauth2_server: OAuth2 server instance

    Returns:
        Token response with access_token and optional refresh_token

    Raises:
        HTTPException: OAuth2 error response
    """
    # Apply rate limiting before processing token request
    if client_id:
        rate_limit_result = await oauth2_server.validate_client_rate_limit(
            client_id, "token_request"
        )
        if rate_limit_result.is_err():
            response.status_code = 429
            return ErrorResponse(
                error="rate_limit_exceeded",
                error_code="rate_limit_exceeded",
                details={"error_description": rate_limit_result.err_value},
            )

    result = await oauth2_server.token(
        grant_type=grant_type,
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=redirect_uri,
        refresh_token=refresh_token,
        scope=scope,
        username=username,
        password=password,
        code_verifier=code_verifier,
    )

    if result.is_err():
        error_str = result.unwrap_err()
        response.status_code = 400
        return ErrorResponse(error=error_str, error_code="invalid_request")

    assert result.ok_value is not None
    return result.ok_value


@router.post("/introspect")
@beartype
async def introspect(
    token: str = Form(...),
    token_type_hint: str | None = Form(None),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> dict[str, Any]:
    """OAuth2 token introspection endpoint.

    This endpoint allows resource servers to query the authorization server
    to determine the active state of an OAuth 2.0 token.

    Args:
        token: Token to introspect
        token_type_hint: Hint about token type (access_token or refresh_token)
        client_id: Client credentials for authentication
        client_secret: Client secret for authentication
        oauth2_server: OAuth2 server instance

    Returns:
        Token introspection response
    """
    return await oauth2_server.introspect(
        token=token,
        token_type_hint=token_type_hint,
        client_id=client_id,
        client_secret=client_secret,
    )


@router.post("/revoke")
@beartype
async def revoke(
    token: str = Form(...),
    token_type_hint: str | None = Form(None),
    client_id: str | None = Form(None),
    client_secret: str | None = Form(None),
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> dict[str, str]:
    """OAuth2 token revocation endpoint.

    This endpoint allows clients to notify the authorization server that a
    previously obtained refresh or access token is no longer needed.

    Args:
        token: Token to revoke
        token_type_hint: Hint about token type
        client_id: Client credentials for authentication
        client_secret: Client secret for authentication
        oauth2_server: OAuth2 server instance

    Returns:
        Empty response on success
    """
    await oauth2_server.revoke(
        token=token,
        token_type_hint=token_type_hint,
        client_id=client_id,
        client_secret=client_secret,
    )

    # OAuth2 spec says to always return 200 OK, even if token was invalid
    return {"status": "ok"}


@router.get("/.well-known/oauth-authorization-server")
@beartype
async def oauth_metadata(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict[str, Any]:
    """OAuth2 authorization server metadata endpoint.

    This endpoint provides metadata about the OAuth2 authorization server
    as specified in RFC 8414.

    Args:
        request: FastAPI request object
        settings: Application settings

    Returns:
        OAuth2 server metadata
    """
    base_url = str(request.base_url).rstrip("/")

    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/api/v1/oauth2/authorize",
        "token_endpoint": f"{base_url}/api/v1/oauth2/token",
        "token_endpoint_auth_methods_supported": [
            "client_secret_basic",
            "client_secret_post",
        ],
        "introspection_endpoint": f"{base_url}/api/v1/oauth2/introspect",
        "revocation_endpoint": f"{base_url}/api/v1/oauth2/revoke",
        "response_types_supported": ["code", "token"],
        "grant_types_supported": [
            "authorization_code",
            "refresh_token",
            "client_credentials",
            "password",
        ],
        "code_challenge_methods_supported": ["S256", "plain"],
        "scopes_supported": [
            "user:read",
            "user:write",
            "quote:read",
            "quote:write",
            "quote:calculate",
            "quote:convert",
            "policy:read",
            "policy:write",
            "policy:cancel",
            "claim:read",
            "claim:write",
            "claim:approve",
            "analytics:read",
            "analytics:export",
            "admin:users",
            "admin:clients",
            "admin:system",
        ],
        "service_documentation": f"{base_url}/docs",
    }


@router.get("/health")
@beartype
async def oauth2_health(
    oauth2_server: OAuth2Server = Depends(get_oauth2_server),
) -> dict[str, Any]:
    """OAuth2 authorization server health check.

    This endpoint provides health metrics for the OAuth2 authorization server
    including active tokens, clients, and recent activity.

    Args:
        oauth2_server: OAuth2 server instance

    Returns:
        Health status and metrics
    """
    return await oauth2_server.get_server_health()


@beartype
async def _get_authenticated_user_id(
    oauth2_server: OAuth2Server, client_id: str
) -> UUID | None:
    """Get authenticated user ID from session or create demo user.

    In production, this would:
    1. Check for authenticated session cookies
    2. Validate JWT tokens from Authorization header
    3. Redirect to login page if not authenticated

    For development/demo purposes, create a demo user for the client.

    Args:
        oauth2_server: OAuth2 server instance for database access
        client_id: Client ID requesting authorization

    Returns:
        User ID if authenticated, None otherwise
    """
    # For demo purposes, create or get a demo user for this client
    # In production, remove this and implement proper session management

    try:
        # Check if demo user exists for this client
        demo_email = f"demo-user-{client_id}@example.com"

        # Get database instance from oauth2_server
        user_row = await oauth2_server._db.fetchrow(
            """
            SELECT id FROM customers
            WHERE data->>'email' = $1
            """,
            demo_email,
        )

        if user_row:
            return UUID(str(user_row["id"]))

        # Create demo user if not exists
        import uuid
        from datetime import datetime, timezone

        user_id = uuid.uuid4()
        customer_data = {
            "first_name": "Demo",
            "last_name": "User",
            "email": demo_email,
            "phone_number": "+1-555-0123",
            "date_of_birth": "1990-01-01",
            "address_line1": "123 Demo Street",
            "city": "Demo City",
            "state_province": "CA",
            "postal_code": "90210",
            "country_code": "US",
            "customer_type": "INDIVIDUAL",
            "tax_id_masked": "***-**-1234",
            "marketing_consent": False,
            "status": "ACTIVE",
            "total_policies": 0,
        }

        await oauth2_server._db.execute(
            """
            INSERT INTO customers (id, external_id, data, created_at, updated_at)
            VALUES ($1, $2, $3, $4, $5)
            """,
            user_id,
            f"DEMO-{str(user_id)[:8].upper()}",
            customer_data,
            datetime.now(timezone.utc),
            datetime.now(timezone.utc),
        )

        return user_id

    except Exception:
        # If anything fails, return None (not authenticated)
        return None
