"""OAuth2 authentication middleware with API key support."""

from collections.abc import Callable

from beartype import beartype
from fastapi import HTTPException, Request, Response
from fastapi.security.utils import get_authorization_scheme_param
from jose import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_401_UNAUTHORIZED, HTTP_403_FORBIDDEN

from ...core.auth.oauth2 import APIKeyManager, ScopeValidator
from ...core.cache import get_redis_client
from ...core.config import get_settings
from ...core.database import get_db_session


class OAuth2Middleware(BaseHTTPMiddleware):
    """Middleware for OAuth2 token validation and API key authentication."""

    def __init__(self, app, exempt_paths: set | None = None):
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
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
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
                await self._validate_api_key(request, api_key)
            else:
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail="Authorization required",
                    headers={"WWW-Authenticate": "Bearer"},
                )
        else:
            # Validate OAuth2 token
            scheme, token = get_authorization_scheme_param(authorization)

            if scheme.lower() == "bearer":
                await self._validate_oauth2_token(request, token)
            elif scheme.lower() == "apikey":
                await self._validate_api_key(request, token)
            else:
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail="Invalid authentication scheme",
                    headers={"WWW-Authenticate": "Bearer"},
                )

        # Process request
        response = await call_next(request)
        return response

    @beartype
    async def _validate_oauth2_token(self, request: Request, token: str) -> None:
        """Validate OAuth2 JWT token with enhanced security checks.

        Args:
            request: Current request
            token: JWT token to validate

        Raises:
            HTTPException: If token is invalid or lacks permissions
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
                    raise HTTPException(
                        status_code=HTTP_401_UNAUTHORIZED,
                        detail="Token has been revoked",
                    )

            # Enhanced client validation with certificate support
            client_id = payload.get("client_id")
            if client_id:
                # Check if client uses certificate authentication
                client_cert = request.headers.get("X-Client-Certificate")
                if client_cert:
                    await self._validate_client_certificate(
                        request, client_id, client_cert
                    )

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
                    raise HTTPException(
                        status_code=HTTP_403_FORBIDDEN,
                        detail=f"Insufficient scope. Required: {required_scope}",
                    )

        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Token has expired",
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail="Invalid token",
            )

    @beartype
    async def _validate_api_key(self, request: Request, api_key: str) -> None:
        """Validate API key.

        Args:
            request: Current request
            api_key: API key to validate

        Raises:
            HTTPException: If API key is invalid or lacks permissions
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
                raise HTTPException(
                    status_code=HTTP_401_UNAUTHORIZED,
                    detail=result.error,
                )

            # Store API key info in request state
            key_info = result.value
            request.state.auth = {
                "type": "api_key",
                "key_id": key_info["id"],
                "client_id": key_info["client_id"],
                "scopes": key_info["scopes"],
            }

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
    ) -> None:
        """Validate client certificate for mTLS authentication.

        Args:
            request: Current request
            client_id: OAuth2 client ID
            certificate_pem: Client certificate in PEM format

        Raises:
            HTTPException: If certificate is invalid
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
                    raise HTTPException(
                        status_code=HTTP_401_UNAUTHORIZED,
                        detail=f"Invalid client certificate: {result.error}",
                    )

                # Store certificate info in request state
                cert_info = result.value
                request.state.client_certificate = {
                    "certificate_id": cert_info["id"],
                    "subject_dn": cert_info["subject_dn"],
                    "validated": True,
                }

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=HTTP_401_UNAUTHORIZED,
                detail=f"Certificate validation failed: {str(e)}",
            )
