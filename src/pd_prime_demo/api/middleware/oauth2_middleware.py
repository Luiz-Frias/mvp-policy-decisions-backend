"""OAuth2 authentication middleware with API key support."""

from collections.abc import Awaitable, Callable
from typing import Any

from beartype import beartype
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from fastapi.security.utils import get_authorization_scheme_param
from jose import jwt  # type: ignore[import-untyped]
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from ...api.response_patterns import ErrorResponse
from ...core.auth.oauth2 import APIKeyManager, ScopeValidator
from ...core.cache import get_redis_client
from ...core.config import get_settings
from ...core.database import get_db_session


class OAuth2Middleware(BaseHTTPMiddleware):
    """Middleware for OAuth2 token validation and API key authentication."""

    def __init__(self, app: Any, exempt_paths: set[str] | None = None) -> None:
        """Initialize OAuth2 middleware.

        Args:
            app: FastAPI application
            exempt_paths: Set of paths that don't require authentication
        """
        super().__init__(app)
        self.settings = get_settings()
        self.exempt_paths = exempt_paths or {
            "/docs",
            "/openapi.json",
            "/api/v1/health",
            "/api/v1/monitoring/metrics",
            "/api/v1/oauth2/token",
            "/api/v1/oauth2/authorize",
            "/api/v1/oauth2/.well-known/oauth-authorization-server",
        }

    @beartype
    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        """Process request through OAuth2 validation.

        Args:
            request: Incoming request
            call_next: Next middleware or endpoint

        Returns:
            Response from the endpoint
        """
        # Skip authentication for exempt paths
        if any(request.url.path.startswith(path) for path in self.exempt_paths):
            return await call_next(request)

        # Get authorization header
        authorization = request.headers.get("Authorization")
        if not authorization:
            # Check for API key in header
            api_key = request.headers.get("X-API-Key")
            if api_key:
                result = await self._validate_api_key(request, api_key)
                if result:
                    return result
            else:
                # Middleware returns Response directly for errors
                error = ErrorResponse(
                    error="Authorization required"
                )
                return JSONResponse(
                    status_code=HTTP_401_UNAUTHORIZED,
                    content=error.model_dump(),
                    headers={"WWW-Authenticate": "Bearer"}
                )
        else:
            # Validate OAuth2 token
            scheme, token = get_authorization_scheme_param(authorization)

            if scheme.lower() == "bearer":
                result = await self._validate_oauth2_token(request, token)
                if result:
                    return result
            elif scheme.lower() == "apikey":
                result = await self._validate_api_key(request, token)
                if result:
                    return result
            else:
                # Middleware returns Response directly for errors
                error = ErrorResponse(
                    error="Invalid authentication scheme"
                )
                return JSONResponse(
                    status_code=HTTP_401_UNAUTHORIZED,
                    content=error.model_dump(),
                    headers={"WWW-Authenticate": "Bearer"}
                )

        # Process request
        response = await call_next(request)
        return response

    @beartype
    async def _validate_oauth2_token(self, request: Request, token: str) -> Response | None:
        """Validate OAuth2 JWT token with enhanced security checks.

        Args:
            request: Current request
            token: JWT token to validate

        Returns:
            JSONResponse with error if validation fails, None if successful
        """
        try:
            # Decode token
            payload = jwt.decode(
                token,
                self.settings.jwt_secret,
                algorithms=[self.settings.jwt_algorithm],
            )

            # Check if token is revoked
            jti = payload.get("jti")
            if jti:
                redis = get_redis_client()
                revoked = await redis.get(f"revoked_token:{jti}")
                if revoked:
                    # Middleware returns Response directly for errors
                    error = ErrorResponse(
                        error="Token has been revoked"
                    )
                    return JSONResponse(
                        status_code=HTTP_401_UNAUTHORIZED,
                        content=error.model_dump()
                    )

            # Enhanced client validation with certificate support
            client_id = payload.get("client_id")
            if client_id:
                # Check if client uses certificate authentication
                client_cert = request.headers.get("X-Client-Certificate")
                if client_cert:
                    result = await self._validate_client_certificate(
                        request, client_id, client_cert
                    )
                    if result:
                        return result

            # Store token info in request state
            request.state.auth = {
                "type": "oauth2",
                "client_id": client_id,
                "user_id": payload.get("sub"),
                "scopes": payload.get("scope", "").split(),
                "jti": jti,
                "token_type": payload.get("typ", "access"),
            }

            # Check required scope for endpoint
            required_scope = self._get_required_scope(request)
            if required_scope:
                token_scopes = request.state.auth["scopes"]
                if not ScopeValidator.check_scope_permission(
                    token_scopes, required_scope
                ):
                    # Middleware returns Response directly for errors
                    error = ErrorResponse(
                        error=f"Insufficient scope. Required: {required_scope}"
                    )
                    return JSONResponse(
                        status_code=HTTP_403_FORBIDDEN,
                        content=error.model_dump()
                    )

            # Success - token is valid
            return None

        except jwt.ExpiredSignatureError:
            # Middleware returns Response directly for errors
            error = ErrorResponse(
                error="Token has expired"
            )
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content=error.model_dump()
            )
        except jwt.JWTError:
            # Middleware returns Response directly for errors
            error = ErrorResponse(
                error="Invalid token"
            )
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content=error.model_dump()
            )

    @beartype
    async def _validate_api_key(self, request: Request, api_key: str) -> Response | None:
        """Validate API key.

        Args:
            request: Current request
            api_key: API key to validate

        Returns:
            JSONResponse with error if validation fails, None if successful
        """
        # Get database and cache connections
        async with get_db_session() as db:
            redis = get_redis_client()
            from ...core.cache import Cache
            from ...core.database import Database

            database = Database(db)
            cache = Cache(redis)

            # Create API key manager
            api_key_manager = APIKeyManager(database, cache)

            # Get client IP
            client_ip = request.client.host if request.client else None

            # Get required scope
            required_scope = self._get_required_scope(request)

            # Validate API key
            result = await api_key_manager.validate_api_key(
                api_key,
                required_scope,
                client_ip,
            )

            if result.is_err():
                # Middleware returns Response directly for errors
                error = ErrorResponse(
                    error=result.err_value or "API key validation failed"
                )
                return JSONResponse(
                    status_code=HTTP_401_UNAUTHORIZED,
                    content=error.model_dump()
                )

            # Store API key info in request state
            key_info = result.ok_value
            if key_info:
                request.state.auth = {
                    "type": "api_key",
                    "key_id": key_info["id"],
                    "client_id": key_info["client_id"],
                    "scopes": key_info["scopes"],
                }
            else:
                # Middleware returns Response directly for errors
                error = ErrorResponse(
                    error="Invalid API key validation result"
                )
                return JSONResponse(
                    status_code=HTTP_401_UNAUTHORIZED,
                    content=error.model_dump()
                )

            # Success - API key is valid
            return None

    @beartype
    def _get_required_scope(self, request: Request) -> str | None:
        """Get required scope for the current endpoint.

        Args:
            request: Current request

        Returns:
            Required scope name or None
        """
        # Map endpoints to required scopes
        # This is a simplified mapping - in production, this would be more sophisticated
        path = request.url.path
        method = request.method

        if path.startswith("/api/v1/quotes"):
            if method == "GET":
                return "quote:read"
            elif method in ["POST", "PUT", "PATCH"]:
                return "quote:write"
            elif method == "DELETE":
                return "quote:write"

        elif path.startswith("/api/v1/policies"):
            if method == "GET":
                return "policy:read"
            elif method in ["POST", "PUT", "PATCH"]:
                return "policy:write"
            elif method == "DELETE":
                return "policy:cancel"

        elif path.startswith("/api/v1/claims"):
            if method == "GET":
                return "claim:read"
            elif method in ["POST", "PUT", "PATCH"]:
                return "claim:write"
            elif "approve" in path:
                return "claim:approve"

        elif path.startswith("/api/v1/admin"):
            return "admin:clients"

        # Default: no specific scope required
        return None

    @beartype
    async def _validate_client_certificate(
        self,
        request: Request,
        client_id: str,
        certificate_pem: str,
    ) -> Response | None:
        """Validate client certificate for mTLS authentication.

        Args:
            request: Current request
            client_id: OAuth2 client ID
            certificate_pem: Client certificate in PEM format

        Returns:
            JSONResponse with error if validation fails, None if successful
        """
        try:
            # Get database and cache connections
            async with get_db_session() as db:
                redis = get_redis_client()
                from ...core.auth.oauth2.client_certificates import (
                    ClientCertificateManager,
                )
                from ...core.cache import Cache
                from ...core.database import Database

                database = Database(db)
                cache = Cache(redis)

                # Create certificate manager
                cert_manager = ClientCertificateManager(database, cache)

                # Validate certificate
                result = await cert_manager.validate_client_certificate(
                    client_id, certificate_pem
                )

                if result.is_err():
                    # Middleware returns Response directly for errors
                    error = ErrorResponse(
                        error=f"Invalid client certificate: {result.err_value}"
                    )
                    return JSONResponse(
                        status_code=HTTP_401_UNAUTHORIZED,
                        content=error.model_dump()
                    )

                # Store certificate info in request state
                cert_info = result.ok_value
                if cert_info:
                    request.state.client_certificate = {
                        "certificate_id": cert_info["id"],
                        "subject_dn": cert_info["subject_dn"],
                        "validated": True,
                    }
                else:
                    # Middleware returns Response directly for errors
                    error = ErrorResponse(
                        error="Invalid certificate validation result"
                    )
                    return JSONResponse(
                        status_code=HTTP_401_UNAUTHORIZED,
                        content=error.model_dump()
                    )

                # Success - certificate is valid
                return None

        except Exception as e:
            # Middleware returns Response directly for errors
            error = ErrorResponse(
                error=f"Certificate validation failed: {str(e)}"
            )
            return JSONResponse(
                status_code=HTTP_401_UNAUTHORIZED,
                content=error.model_dump()
            )
