"""OAuth2 authorization server implementation."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype
from jose import JWTError, jwt  # type: ignore[import-untyped]
from passlib.context import CryptContext

from pd_prime_demo.core.result_types import Err, Ok, Result

from ....core.cache import Cache
from ....core.config import Settings
from ....core.database import Database

# Password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class OAuth2Error(Exception):
    """OAuth2 specific errors."""

    def __init__(
        self,
        error: str,
        error_description: str | None = None,
        error_uri: str | None = None,
        status_code: int = 400,
    ) -> None:
        """Initialize OAuth2 error."""
        self.error = error
        self.error_description = error_description
        self.error_uri = error_uri
        self.status_code = status_code
        super().__init__(error_description or error)

    @beartype
    def to_dict(self) -> dict[str, Any]:
        """Convert to OAuth2 error response."""
        response = {"error": self.error}
        if self.error_description:
            response["error_description"] = self.error_description
        if self.error_uri:
            response["error_uri"] = self.error_uri
        return response


class OAuth2Server:
    """OAuth2 authorization server."""

    def __init__(
        self,
        db: Database,
        cache: Cache,
        settings: Settings,
    ) -> None:
        """Initialize OAuth2 server."""
        self._db = db
        self._cache = cache
        self._settings = settings

        # Token settings
        self._access_token_expire = timedelta(hours=1)
        self._refresh_token_expire = timedelta(days=30)
        self._authorization_code_expire = timedelta(minutes=10)

        # Supported flows
        self._supported_grant_types = [
            "authorization_code",
            "refresh_token",
            "client_credentials",
            "password",  # Only for trusted clients
        ]

        # Supported response types
        self._supported_response_types = ["code", "token"]

    @beartype
    async def create_client(
        self,
        client_name: str,
        redirect_uris: list[str],
        allowed_grant_types: list[str],
        allowed_scopes: list[str],
        client_type: str = "confidential",  # or "public"
    ) -> Result[dict[str, Any], str]:
        """Create a new OAuth2 client.

        Args:
            client_name: Name of the client application
            redirect_uris: List of allowed redirect URIs
            allowed_grant_types: List of allowed OAuth2 grant types
            allowed_scopes: List of allowed OAuth2 scopes
            client_type: Type of client ("confidential" or "public")

        Returns:
            Result containing client details or error message
        """
        try:
            # Validate grant types
            invalid_grants = set(allowed_grant_types) - set(self._supported_grant_types)
            if invalid_grants:
                return Err(f"Invalid grant types: {invalid_grants}")

            # Validate that grant types are explicitly specified
            if not allowed_grant_types:
                return Err(
                    "OAuth2 error: allowed_grant_types is required. "
                    "Required action: Specify at least one grant type."
                )

            # Generate credentials
            client_id = self._generate_client_id()
            client_secret = None
            client_secret_hash = None

            if client_type == "confidential":
                client_secret = self._generate_client_secret()
                client_secret_hash = pwd_context.hash(client_secret)

            # Store in database
            await self._db.execute(
                """
                INSERT INTO oauth2_clients (
                    client_id, client_secret_hash, client_name,
                    client_type, redirect_uris, allowed_grant_types,
                    allowed_scopes, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                """,
                client_id,
                client_secret_hash,
                client_name,
                client_type,
                redirect_uris,
                allowed_grant_types,
                allowed_scopes,
                datetime.now(timezone.utc),
            )

            result = {
                "client_id": client_id,
                "client_name": client_name,
                "client_type": client_type,
                "redirect_uris": redirect_uris,
                "allowed_grant_types": allowed_grant_types,
                "allowed_scopes": allowed_scopes,
            }

            if client_secret:
                result["client_secret"] = client_secret  # pragma: allowlist secret
                result["client_secret_note"] = (
                    "Store this securely. It cannot be retrieved later."  # pragma: allowlist secret
                )

            return Ok(result)

        except Exception as e:
            return Err(f"Failed to create client: {str(e)}")

    @beartype
    async def authorize(
        self,
        response_type: str,
        client_id: str,
        redirect_uri: str,
        scope: str,
        state: str | None = None,
        user_id: UUID | None = None,
        code_challenge: str | None = None,
        code_challenge_method: str | None = None,
    ) -> Result[dict[str, Any], str]:
        """Handle authorization request.

        Args:
            response_type: OAuth2 response type ("code" or "token")
            client_id: Client identifier
            redirect_uri: Redirect URI for response
            scope: Space-separated list of requested scopes
            state: Optional state parameter for CSRF protection
            user_id: Authenticated user ID (required for "code" flow)
            code_challenge: PKCE code challenge
            code_challenge_method: PKCE challenge method ("S256" or "plain")

        Returns:
            Result containing authorization response or OAuth2Error
        """
        try:
            # Validate client
            client = await self._get_client(client_id)
            if not client:
                return Err("invalid_client: Client not found")

            # Validate response type
            if response_type not in self._supported_response_types:
                return Err("unsupported_response_type")

            # Validate redirect URI
            if redirect_uri not in client["redirect_uris"]:
                return Err("invalid_request: Invalid redirect_uri")

            # Validate scope - EXPLICIT validation, no defaults
            if not scope:
                return Err(
                    "invalid_request: OAuth2 error: scope parameter is required. "
                    "Required action: Include 'scope' in authorization request."
                )

            requested_scopes = scope.split()
            if not requested_scopes:
                return Err(
                    "invalid_scope: OAuth2 error: at least one scope must be specified. "
                    "Required action: Include valid scopes in the request."
                )

            # Validate all requested scopes are allowed for this client
            if not all(s in client["allowed_scopes"] for s in requested_scopes):
                invalid_scopes = [
                    s for s in requested_scopes if s not in client["allowed_scopes"]
                ]
                return Err(
                    f"invalid_scope: Client not authorized for scopes: {', '.join(invalid_scopes)}. "
                    f"Allowed scopes: {', '.join(client['allowed_scopes'])}"
                )

            # Require user authentication for authorization code flow
            if response_type == "code" and not user_id:
                return Err("access_denied: User authentication required")

            # Generate authorization code
            if response_type == "code":
                # user_id is guaranteed to be not None due to check above
                assert user_id is not None
                code = await self._generate_authorization_code(
                    client_id,
                    user_id,
                    redirect_uri,
                    requested_scopes,
                    code_challenge,
                    code_challenge_method,
                )

                return Ok(
                    {
                        "code": code,
                        "state": state,
                    }
                )

            # Implicit flow (token response type)
            elif response_type == "token":
                if client["client_type"] != "public":
                    return Err(
                        "unauthorized_client: Implicit flow not allowed for confidential clients"
                    )

                tokens = await self._generate_tokens(
                    client_id,
                    user_id,
                    requested_scopes,
                )

                return Ok(
                    {
                        "access_token": tokens["access_token"],
                        "token_type": "Bearer",
                        "expires_in": int(self._access_token_expire.total_seconds()),
                        "scope": scope,
                        "state": state,
                    }
                )
            
            # This should not happen as response_type is validated above
            else:
                return Err(f"unsupported_response_type: {response_type}")

        except OAuth2Error as e:
            return Err(f"{e.error}: {e.error_description or e.error}")
        except Exception as e:
            return Err(f"server_error: {str(e)}")

    @beartype
    async def token(
        self,
        grant_type: str,
        client_id: str | None = None,
        client_secret: str | None = None,
        code: str | None = None,
        redirect_uri: str | None = None,
        refresh_token: str | None = None,
        scope: str | None = None,
        username: str | None = None,
        password: str | None = None,
        code_verifier: str | None = None,
    ) -> Result[dict[str, Any], str]:
        """Handle token request.

        Args:
            grant_type: OAuth2 grant type
            client_id: Client identifier
            client_secret: Client secret (for confidential clients)
            code: Authorization code (for authorization_code grant)
            redirect_uri: Redirect URI (for authorization_code grant)
            refresh_token: Refresh token (for refresh_token grant)
            scope: Requested scopes
            username: Username (for password grant)
            password: Password (for password grant)
            code_verifier: PKCE code verifier

        Returns:
            Result containing token response or OAuth2Error
        """
        try:
            # Validate grant type
            if grant_type not in self._supported_grant_types:
                return Err("unsupported_grant_type")

            # Authenticate client (except for public clients using authorization_code)
            client = await self._authenticate_client(client_id, client_secret)
            if not client and grant_type != "authorization_code":
                return Err("invalid_client")

            # Handle different grant types
            if grant_type == "authorization_code":
                return await self._handle_authorization_code_grant(
                    code, redirect_uri, client_id, code_verifier
                )

            elif grant_type == "refresh_token":
                if not client:
                    return Err("invalid_client")
                return await self._handle_refresh_token_grant(
                    refresh_token, scope, client
                )

            elif grant_type == "client_credentials":
                if not client:
                    return Err("invalid_client")
                return await self._handle_client_credentials_grant(client, scope)

            elif grant_type == "password":
                if not client:
                    return Err("invalid_client")
                return await self._handle_password_grant(
                    username, password, scope, client
                )

            else:
                return Err("unsupported_grant_type")

        except OAuth2Error as e:
            return Err(f"{e.error}: {e.error_description or e.error}")
        except Exception as e:
            return Err(f"server_error: {str(e)}")

    @beartype
    async def introspect(
        self,
        token: str,
        token_type_hint: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> dict[str, Any]:
        """Introspect a token.

        Args:
            token: Token to introspect
            token_type_hint: Hint about token type
            client_id: Client identifier for authentication
            client_secret: Client secret for authentication

        Returns:
            Token introspection response
        """
        # Authenticate client if credentials provided
        if client_id and client_secret:
            client = await self._authenticate_client(client_id, client_secret)
            if not client:
                return {"active": False}

        # Try to decode as JWT first
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self._settings.jwt_algorithm],
            )

            # Check if token is still valid
            exp = payload.get("exp", 0)
            if datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(
                timezone.utc
            ):
                return {"active": False}

            # Check if token is revoked
            jti = payload.get("jti")
            if jti and await self._is_token_revoked(jti):
                return {"active": False}

            return {
                "active": True,
                "scope": payload.get("scope", ""),
                "client_id": payload.get("client_id"),
                "username": payload.get("sub"),
                "exp": payload.get("exp"),
                "iat": payload.get("iat"),
                "jti": jti,
                "token_type": "access_token",
            }

        except JWTError:
            # Not a valid JWT, might be a refresh token
            return await self._introspect_refresh_token(token)

    @beartype
    async def revoke(
        self,
        token: str,
        token_type_hint: str | None = None,
        client_id: str | None = None,
        client_secret: str | None = None,
    ) -> Result[bool, str]:
        """Revoke a token.

        Args:
            token: Token to revoke
            token_type_hint: Hint about token type
            client_id: Client identifier for authentication
            client_secret: Client secret for authentication

        Returns:
            Result indicating success or error
        """
        # Authenticate client if credentials provided
        if client_id and client_secret:
            client = await self._authenticate_client(client_id, client_secret)
            if not client:
                return Err("Invalid client credentials")

        # Try to decode as JWT
        try:
            payload = jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self._settings.jwt_algorithm],
                options={"verify_exp": False},  # Allow expired tokens
            )

            jti = payload.get("jti")
            if jti:
                # Store in revocation list
                exp = payload.get("exp", 0)
                ttl = max(0, exp - int(datetime.now(timezone.utc).timestamp()))

                await self._cache.set(
                    f"revoked_token:{jti}",
                    "1",
                    ttl,
                )

                return Ok(True)

        except JWTError:
            pass

        # Try as refresh token
        return await self._revoke_refresh_token(token)

    # Helper methods

    @beartype
    def _generate_client_id(self) -> str:
        """Generate unique client ID."""
        return f"client_{uuid4().hex}"

    @beartype
    def _generate_client_secret(self) -> str:
        """Generate secure client secret."""
        return secrets.token_urlsafe(32)

    @beartype
    async def _get_client(self, client_id: str) -> dict[str, Any] | None:
        """Get client configuration from database."""
        row = await self._db.fetchrow(
            """
            SELECT client_id, client_secret_hash, client_name, client_type,
                   redirect_uris, allowed_grant_types, allowed_scopes
            FROM oauth2_clients
            WHERE client_id = $1 AND is_active = true
            """,
            client_id,
        )

        if not row:
            return None

        return dict(row)

    @beartype
    async def _authenticate_client(
        self, client_id: str | None, client_secret: str | None
    ) -> dict[str, Any] | None:
        """Authenticate OAuth2 client."""
        if not client_id:
            return None

        client = await self._get_client(client_id)
        if not client:
            return None

        # Public clients don't have secrets
        if client["client_type"] == "public":
            return client

        # Confidential clients must provide valid secret
        if not client_secret or not client.get("client_secret_hash"):
            return None

        if not pwd_context.verify(client_secret, client["client_secret_hash"]):
            return None

        return client

    @beartype
    async def _generate_authorization_code(
        self,
        client_id: str,
        user_id: UUID,
        redirect_uri: str,
        scopes: list[str],
        code_challenge: str | None = None,
        code_challenge_method: str | None = None,
    ) -> str:
        """Generate and store authorization code."""
        code = secrets.token_urlsafe(32)

        # Store code details
        await self._cache.set(
            f"auth_code:{code}",
            {
                "client_id": client_id,
                "user_id": str(user_id),
                "redirect_uri": redirect_uri,
                "scopes": scopes,
                "code_challenge": code_challenge,
                "code_challenge_method": code_challenge_method,
                "created_at": datetime.now(timezone.utc).isoformat(),
            },
            int(self._authorization_code_expire.total_seconds()),
        )

        return code

    @beartype
    async def _generate_tokens(
        self,
        client_id: str,
        user_id: UUID | None,
        scopes: list[str],
    ) -> dict[str, str]:
        """Generate access and refresh tokens."""
        # Get client configuration for token lifetime
        client = await self._get_client(client_id)
        if not client:
            raise OAuth2Error("invalid_client", "Client not found")

        # Use client-specific token lifetime if configured
        token_lifetime = client.get("token_lifetime")
        if not token_lifetime:
            # No default - must be explicitly configured
            raise OAuth2Error(
                "server_error",
                "OAuth2 error: Client access token lifetime not configured. "
                "Required action: Configure token_lifetime for client.",
            )

        access_token_expire = timedelta(seconds=token_lifetime)

        # Access token
        now = datetime.now(timezone.utc)
        jti = str(uuid4())

        access_payload = {
            "jti": jti,
            "client_id": client_id,
            "scope": " ".join(scopes),
            "iat": now,
            "exp": now + access_token_expire,
        }

        if user_id:
            access_payload["sub"] = str(user_id)
            access_payload["typ"] = "user"
        else:
            access_payload["typ"] = "client"

        access_token = jwt.encode(
            access_payload,
            self._settings.jwt_secret,
            algorithm=self._settings.jwt_algorithm,
        )

        # Refresh token (opaque token)
        refresh_token = secrets.token_urlsafe(32)

        # Store refresh token
        await self._db.execute(
            """
            INSERT INTO oauth2_refresh_tokens (
                token_hash, client_id, user_id, scopes,
                expires_at, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6)
            """,
            hashlib.sha256(refresh_token.encode()).hexdigest(),
            client_id,
            user_id,
            scopes,
            now + self._refresh_token_expire,
            now,
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
        }

    @beartype
    async def _handle_authorization_code_grant(
        self,
        code: str | None,
        redirect_uri: str | None,
        client_id: str | None,
        code_verifier: str | None = None,
    ) -> Result[dict[str, Any], str]:
        """Handle authorization code grant type with enhanced PKCE validation."""
        if not code:
            return Err("invalid_request: Missing authorization code")

        if not redirect_uri:
            return Err("invalid_request: Missing redirect_uri")

        if not client_id:
            return Err("invalid_request: Missing client_id")

        # Retrieve code details
        code_data = await self._cache.get(f"auth_code:{code}")
        if not code_data:
            return Err(
                "invalid_grant: Invalid or expired authorization code"
            )

        # Validate client
        if code_data["client_id"] != client_id:
            return Err(
                "invalid_grant: Code was issued to a different client"
            )

        # Validate redirect URI
        if code_data["redirect_uri"] != redirect_uri:
            return Err("invalid_grant: Redirect URI mismatch")

        # Enhanced PKCE validation per 2024 best practices
        code_challenge = code_data.get("code_challenge")
        if code_challenge:
            # PKCE is mandatory when challenge was provided
            if not code_verifier:
                return Err(
                    "invalid_request: Code verifier required for PKCE"
                )

            challenge_method = code_data.get("code_challenge_method", "plain")

            if challenge_method == "S256":
                # Compute SHA256 hash of verifier and base64url encode it
                import base64

                verifier_hash = hashlib.sha256(code_verifier.encode("ascii")).digest()
                computed_challenge = (
                    base64.urlsafe_b64encode(verifier_hash).decode("ascii").rstrip("=")
                )

                if computed_challenge != code_challenge:
                    return Err(
                        "invalid_grant: PKCE code verifier validation failed"
                    )

            elif challenge_method == "plain":
                # Plain method: verifier must match challenge exactly
                if code_verifier != code_challenge:
                    return Err(
                        "invalid_grant: PKCE code verifier validation failed"
                    )
            else:
                return Err(
                    f"invalid_request: Unsupported PKCE challenge method: {challenge_method}"
                )

        # Check if code verifier provided but no challenge (PKCE downgrade attack prevention)
        elif code_verifier:
            return Err(
                "invalid_request: Code verifier provided but no PKCE challenge was used"
            )

        # Delete code to prevent reuse (one-time use enforcement)
        await self._cache.delete(f"auth_code:{code}")

        # Generate tokens
        user_id = UUID(code_data["user_id"]) if code_data.get("user_id") else None
        tokens = await self._generate_tokens(
            client_id,
            user_id,
            code_data["scopes"],
        )

        # Log successful token exchange for security monitoring
        await self._log_token_exchange(
            client_id, user_id, "authorization_code", code_data["scopes"]
        )

        return Ok(
            {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_type": "Bearer",
                "expires_in": int(self._access_token_expire.total_seconds()),
                "scope": " ".join(code_data["scopes"]),
            }
        )

    @beartype
    async def _handle_refresh_token_grant(
        self,
        refresh_token: str | None,
        scope: str | None,
        client: dict[str, Any],
    ) -> Result[dict[str, Any], str]:
        """Handle refresh token grant type."""
        if not refresh_token:
            return Err("invalid_request: Missing refresh token")

        # Hash token for lookup
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()

        # Get refresh token from database
        row = await self._db.fetchrow(
            """
            SELECT client_id, user_id, scopes, expires_at
            FROM oauth2_refresh_tokens
            WHERE token_hash = $1 AND revoked_at IS NULL
            """,
            token_hash,
        )

        if not row:
            return Err("invalid_grant: Invalid refresh token")

        # Check expiration
        if row["expires_at"] < datetime.now(timezone.utc):
            return Err("invalid_grant: Refresh token has expired")

        # Validate client
        if row["client_id"] != client["client_id"]:
            return Err(
                "invalid_grant: Token was issued to a different client"
            )

        # Handle scope narrowing
        if scope:
            requested_scopes = scope.split()
            original_scopes = row["scopes"]

            # Ensure requested scopes are subset of original
            if not all(s in original_scopes for s in requested_scopes):
                return Err(
                    "invalid_scope: Cannot request scopes not in original grant"
                )

            scopes = requested_scopes
        else:
            scopes = row["scopes"]

        # Generate new tokens
        user_id = row["user_id"]
        tokens = await self._generate_tokens(
            client["client_id"],
            user_id,
            scopes,
        )

        # Optionally revoke old refresh token (rotation)
        await self._db.execute(
            """
            UPDATE oauth2_refresh_tokens
            SET revoked_at = $2
            WHERE token_hash = $1
            """,
            token_hash,
            datetime.now(timezone.utc),
        )

        return Ok(
            {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_type": "Bearer",
                "expires_in": int(self._access_token_expire.total_seconds()),
                "scope": " ".join(scopes),
            }
        )

    @beartype
    async def _handle_client_credentials_grant(
        self,
        client: dict[str, Any],
        scope: str | None,
    ) -> Result[dict[str, Any], str]:
        """Handle client credentials grant type."""
        # Validate grant type is allowed
        if "client_credentials" not in client["allowed_grant_types"]:
            return Err(
                "unauthorized_client: Client not authorized for this grant type"
            )

        # Validate scope
        if not scope:
            return Err(
                "invalid_request: OAuth2 error: scope parameter is required for client_credentials grant. "
                "Required action: Include 'scope' in token request."
            )

        requested_scopes = scope.split()
        if not all(s in client["allowed_scopes"] for s in requested_scopes):
            invalid_scopes = [
                s for s in requested_scopes if s not in client["allowed_scopes"]
            ]
            return Err(
                f"invalid_scope: Client not authorized for scopes: {', '.join(invalid_scopes)}"
            )

        # Generate tokens (no user_id for client credentials)
        tokens = await self._generate_tokens(
            client["client_id"],
            None,
            requested_scopes,
        )

        # Client credentials don't get refresh tokens
        return Ok(
            {
                "access_token": tokens["access_token"],
                "token_type": "Bearer",
                "expires_in": int(self._access_token_expire.total_seconds()),
                "scope": " ".join(requested_scopes),
            }
        )

    @beartype
    async def _handle_password_grant(
        self,
        username: str | None,
        password: str | None,
        scope: str | None,
        client: dict[str, Any],
    ) -> Result[dict[str, Any], str]:
        """Handle password grant type (only for trusted clients)."""
        # This grant type should only be used by highly trusted clients
        if "password" not in client["allowed_grant_types"]:
            return Err(
                "unauthorized_client: Client not authorized for password grant"
            )

        if not username or not password:
            return Err("invalid_request: Username and password required")

        # Authenticate user (delegate to user service)
        # This is a placeholder - actual implementation would verify credentials
        user_id = await self._authenticate_user(username, password)
        if not user_id:
            return Err("invalid_grant: Invalid username or password")

        # Handle scopes
        if scope:
            requested_scopes = scope.split()
            if not all(s in client["allowed_scopes"] for s in requested_scopes):
                return Err("invalid_scope")
            scopes = requested_scopes
        else:
            # No default scopes - must be explicit
            return Err(
                "invalid_request: OAuth2 error: scope parameter is required. "
                "Required action: Include 'scope' in token request."
            )

        # Generate tokens
        tokens = await self._generate_tokens(
            client["client_id"],
            user_id,
            scopes,
        )

        return Ok(
            {
                "access_token": tokens["access_token"],
                "refresh_token": tokens["refresh_token"],
                "token_type": "Bearer",
                "expires_in": int(self._access_token_expire.total_seconds()),
                "scope": " ".join(scopes),
            }
        )

    @beartype
    async def _authenticate_user(self, username: str, password: str) -> UUID | None:
        """Authenticate user credentials against customer database.

        Args:
            username: Email address used as username
            password: User password

        Returns:
            User ID if authentication successful, None otherwise
        """
        try:
            # Query customer by email (used as username)
            customer_row = await self._db.fetchrow(
                """
                SELECT id, data->>'password_hash' as password_hash,
                       data->>'status' as status
                FROM customers
                WHERE data->>'email' = $1
                """,
                username.lower().strip(),
            )

            if not customer_row:
                return None

            # Check if customer is active
            if customer_row.get("status") != "ACTIVE":
                return None

            # Verify password if password hash exists
            password_hash = customer_row.get("password_hash")
            if not password_hash:
                # Customer doesn't have password set (might use SSO only)
                return None

            if not pwd_context.verify(password, password_hash):
                return None

            return UUID(customer_row["id"]) if customer_row["id"] else None

        except Exception:
            # Authentication failure should not expose internal errors
            return None

    @beartype
    async def _is_token_revoked(self, jti: str) -> bool:
        """Check if token has been revoked."""
        revoked = await self._cache.get(f"revoked_token:{jti}")
        return revoked is not None

    @beartype
    async def _introspect_refresh_token(self, token: str) -> dict[str, Any]:
        """Introspect a refresh token."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        row = await self._db.fetchrow(
            """
            SELECT client_id, user_id, scopes, expires_at, created_at
            FROM oauth2_refresh_tokens
            WHERE token_hash = $1 AND revoked_at IS NULL
            """,
            token_hash,
        )

        if not row:
            return {"active": False}

        if row["expires_at"] < datetime.now(timezone.utc):
            return {"active": False}

        return {
            "active": True,
            "scope": " ".join(row["scopes"]),
            "client_id": row["client_id"],
            "username": str(row["user_id"]) if row["user_id"] else None,
            "exp": int(row["expires_at"].timestamp()),
            "iat": int(row["created_at"].timestamp()),
            "token_type": "refresh_token",
        }

    @beartype
    async def _revoke_refresh_token(self, token: str) -> Result[bool, str]:
        """Revoke a refresh token."""
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        result = await self._db.execute(
            """
            UPDATE oauth2_refresh_tokens
            SET revoked_at = $2
            WHERE token_hash = $1 AND revoked_at IS NULL
            """,
            token_hash,
            datetime.now(timezone.utc),
        )

        # Check if any row was updated
        if result and "UPDATE" in result:
            return Ok(True)
        else:
            return Err("Token not found or already revoked")

    @beartype
    async def _log_token_exchange(
        self,
        client_id: str,
        user_id: UUID | None,
        grant_type: str,
        scopes: list[str],
    ) -> None:
        """Log token exchange for security monitoring and analytics.

        Args:
            client_id: OAuth2 client ID
            user_id: User ID (if applicable)
            grant_type: Type of grant used
            scopes: Granted scopes
        """
        try:
            await self._db.execute(
                """
                INSERT INTO oauth2_token_logs (
                    client_id, user_id, grant_type, scopes, created_at
                ) VALUES ($1, $2, $3, $4, $5)
                """,
                client_id,
                user_id,
                grant_type,
                scopes,
                datetime.now(timezone.utc),
            )
        except Exception:
            # Don't fail token exchange if logging fails
            pass

    @beartype
    async def validate_client_rate_limit(
        self,
        client_id: str,
        operation: str = "token_request",
    ) -> Result[bool, str]:
        """Validate client-specific rate limiting.

        Args:
            client_id: OAuth2 client ID
            operation: Type of operation being rate limited

        Returns:
            Result indicating if operation is within limits
        """
        # Get client rate limit configuration
        client = await self._get_client(client_id)
        if not client:
            return Err("Client not found")

        # Default rate limits per operation type
        rate_limits = {
            "token_request": 300,  # 300 requests per minute
            "authorization": 100,  # 100 authorization requests per minute
            "introspection": 600,  # 600 introspection requests per minute
        }

        limit = rate_limits.get(operation, 60)

        # Check rate limit using sliding window
        now = datetime.now(timezone.utc)
        window_key = f"rate_limit:{client_id}:{operation}:{now.strftime('%Y%m%d%H%M')}"

        current_count = await self._cache.incr(window_key)

        # Set expiration on first increment
        if current_count == 1:
            await self._cache.expire(window_key, 60)

        if current_count > limit:
            return Err(
                f"Rate limit exceeded for {operation}: {current_count}/{limit} per minute"
            )

        return Ok(True)

    @beartype
    async def get_server_health(self) -> dict[str, Any]:
        """Get OAuth2 server health metrics.

        Returns:
            Health metrics including token counts, active clients, etc.
        """
        try:
            # Active tokens count
            active_tokens = await self._db.fetchval(
                """
                SELECT COUNT(*) FROM oauth2_tokens
                WHERE expires_at > $1 AND revoked_at IS NULL
                """,
                datetime.now(timezone.utc),
            )

            # Active clients count
            active_clients = await self._db.fetchval(
                "SELECT COUNT(*) FROM oauth2_clients WHERE is_active = true"
            )

            # Token requests in last hour
            one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
            recent_tokens = await self._db.fetchval(
                """
                SELECT COUNT(*) FROM oauth2_token_logs
                WHERE created_at > $1
                """,
                one_hour_ago,
            )

            return {
                "status": "healthy",
                "active_tokens": active_tokens or 0,
                "active_clients": active_clients or 0,
                "tokens_issued_last_hour": recent_tokens or 0,
                "server_time": datetime.now(timezone.utc).isoformat(),
                "supported_flows": self._supported_grant_types,
                "supported_response_types": self._supported_response_types,
            }

        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "server_time": datetime.now(timezone.utc).isoformat(),
            }
