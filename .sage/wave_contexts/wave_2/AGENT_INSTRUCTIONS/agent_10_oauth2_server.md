# Agent 10: OAuth2 Server Developer

## YOUR MISSION

Build a complete OAuth2 authorization server with client management, scope-based permissions, JWT tokens, and API key management for partner integrations.

## CRITICAL: NO SILENT FALLBACKS PRINCIPLE

### OAuth2 Security Requirements (NON-NEGOTIABLE)

1. **EXPLICIT CLIENT CONFIGURATION**:
   - NO default scopes when client scopes undefined
   - NO fallback grant types without explicit approval
   - NO assumed redirect URIs for client validation
   - ALL client credentials MUST be explicitly validated

2. **FAIL FAST ON TOKEN VALIDATION**:

   ```python
   # ❌ FORBIDDEN - Silent fallback to basic auth
   async def validate_token(token: str):
       try:
           return await jwt.decode(token)
       except:
           return await basic_auth.validate(token)  # Silent fallback

   # ✅ REQUIRED - Explicit token validation
   async def validate_token(token: str) -> Result[TokenClaims, str]:
       if not token:
           return Err(
               "OAuth2 error: access_token is required. "
               "Required action: Include 'Authorization: Bearer <token>' header."
           )
   ```

3. **SCOPE VALIDATION**:

   ```python
   # ❌ FORBIDDEN - Default scope assignment
   scopes = request.scopes or ["read"]  # Silent default

   # ✅ REQUIRED - Explicit scope validation
   if not request.scopes:
       return Err(
           "OAuth2 error: scope parameter is required. "
           "Required action: Include 'scope' in authorization request."
       )
   ```

4. **CLIENT REGISTRATION**: Never auto-approve client registrations without admin review

## ADDITIONAL GAPS TO WATCH

### Similar Gaps (OAuth2 Domain)

```python
# ❌ WATCH FOR: Token lifetime assumptions
access_token = jwt.encode(payload, secret, expires_in=3600)  # 1 hour default
# ✅ REQUIRED: Client-specific token lifetimes
client_config = await get_client_configuration(client_id)
if not client_config.access_token_lifetime:
    return Err("Client access token lifetime not configured")
access_token = jwt.encode(payload, secret, expires_in=client_config.access_token_lifetime)
```

### Lateral Gaps (Security Anti-Patterns)

```python
# ❌ WATCH FOR: Scope creep assumptions
# Granting broader scopes than requested
requested_scopes = ["read:quotes"]
granted_scopes = ["read:quotes", "write:quotes", "admin:all"]  # Dangerous!
# ✅ REQUIRED: Exact scope validation
if not all(scope in client.allowed_scopes for scope in requested_scopes):
    return Err(f"Client not authorized for scopes: {requested_scopes}")
granted_scopes = requested_scopes  # Grant exactly what was requested and authorized
```

### Inverted Gaps (Over-Secure vs Under-Secure)

```python
# ❌ WATCH FOR: Token validation paranoia
# Validating tokens 47 times per request
async def validate_request_token(token):
    await validate_token_signature(token)
    await validate_token_expiry(token)
    await validate_token_audience(token)
    await validate_token_issuer(token)
    await validate_token_subject(token)
    # ... 42 more validations taking 500ms total
# ✅ BALANCED: Essential validation with caching
@cache_result(ttl=300)  # Cache valid tokens for 5 minutes
async def validate_essential_token_claims(token):
    # Core validations only: signature, expiry, scope
    return await fast_token_validation(token)
```

### Meta-Gaps (OAuth2 Server Validation)

```python
# ❌ WATCH FOR: Authorization server that can't authorize itself
def authorize_client(client_id, scopes):
    # What authorizes the authorization server to make this decision?
    return generate_authorization_code(client_id, scopes)
# ✅ REQUIRED: Authorization server authorization
async def authorize_client_with_server_validation(client_id, scopes, server_authority):
    # Validate that this server instance has authority to issue tokens
    authority_validation = await validate_server_authority(server_authority)
    if authority_validation.is_err():
        return Err("Authorization server lacks authority to issue tokens")
```

### Scale-Based Gaps (Token Generation Under Load)

```python
# ❌ WATCH FOR: Crypto operations blocking event loop
# Generating 10k tokens synchronously
for request in token_requests:
    token = jwt.encode(payload, rsa_private_key)  # CPU-intensive RSA signing
# ✅ REQUIRED: Async token generation with proper pool
async def generate_tokens_with_pool(token_requests, crypto_pool):
    # Use dedicated thread pool for CPU-intensive crypto
    tasks = [crypto_pool.submit(jwt.encode, req.payload, rsa_key) for req in token_requests]
    return await asyncio.gather(*tasks)
```

### Time-Based Gaps (US Business Hours + Token Expiry)

```python
# ❌ WATCH FOR: Token expiration during business transactions
# 1-hour tokens that expire mid-quote process
token_lifetime = timedelta(hours=1)  # Might expire during complex workflow
# ✅ REQUIRED: Business-process-aware token lifetimes
if is_business_hours() and is_complex_workflow(scopes):
    # Longer tokens during business hours for complex processes
    token_lifetime = timedelta(hours=8)  # Full business day
else:
    token_lifetime = timedelta(hours=1)  # Standard lifetime
```

## MANDATORY PRE-WORK

1. Read ALL documents listed in AGENT_TEMPLATE.md FIRST
2. Specifically study:
   - OAuth2 RFC 6749 (30-second search for key concepts)
   - JWT best practices (30-second search if unfamiliar)
   - Existing JWT implementation in `src/pd_prime_demo/core/security.py`

## SPECIFIC TASKS

### 1. Create OAuth2 Server Core (`src/pd_prime_demo/core/auth/oauth2/server.py`)

```python
"""OAuth2 authorization server implementation."""

import secrets
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Tuple
from uuid import UUID, uuid4

from jose import jwt, JWTError
from passlib.context import CryptContext
from beartype import beartype

from ....core.config import Settings
from ....core.database import Database
from ....core.cache import Cache
from ....services.result import Result, Ok, Err


# Password hashing
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


class OAuth2Error(Exception):
    """OAuth2 specific errors."""

    def __init__(
        self,
        error: str,
        error_description: Optional[str] = None,
        error_uri: Optional[str] = None,
        status_code: int = 400,
    ) -> None:
        """Initialize OAuth2 error."""
        self.error = error
        self.error_description = error_description
        self.error_uri = error_uri
        self.status_code = status_code
        super().__init__(error_description or error)

    def to_dict(self) -> Dict[str, Any]:
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
        redirect_uris: List[str],
        allowed_grant_types: List[str],
        allowed_scopes: List[str],
        client_type: str = "confidential",  # or "public"
    ) -> Result[Dict[str, Any], str]:
        """Create a new OAuth2 client."""
        try:
            # Validate grant types
            invalid_grants = set(allowed_grant_types) - set(self._supported_grant_types)
            if invalid_grants:
                return Err(f"Invalid grant types: {invalid_grants}")

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
                result["client_secret_note"] = "Store this securely. It cannot be retrieved later."  # pragma: allowlist secret

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
        state: Optional[str] = None,
        user_id: Optional[UUID] = None,
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None,
    ) -> Result[Dict[str, Any], OAuth2Error]:
        """Handle authorization request."""
        try:
            # Validate client
            client = await self._get_client(client_id)
            if not client:
                raise OAuth2Error("invalid_client", "Client not found")

            # Validate response type
            if response_type not in self._supported_response_types:
                raise OAuth2Error("unsupported_response_type")

            # Validate redirect URI
            if redirect_uri not in client["redirect_uris"]:
                raise OAuth2Error("invalid_request", "Invalid redirect_uri")

            # Validate scope
            requested_scopes = scope.split()
            if not all(s in client["allowed_scopes"] for s in requested_scopes):
                raise OAuth2Error("invalid_scope")

            # Require user authentication for authorization code flow
            if response_type == "code" and not user_id:
                raise OAuth2Error("access_denied", "User authentication required")

            # Generate authorization code
            if response_type == "code":
                code = await self._generate_authorization_code(
                    client_id,
                    user_id,
                    redirect_uri,
                    requested_scopes,
                    code_challenge,
                    code_challenge_method,
                )

                return Ok({
                    "code": code,
                    "state": state,
                })

            # Implicit flow (token response type)
            elif response_type == "token":
                if client["client_type"] != "public":
                    raise OAuth2Error(
                        "unauthorized_client",
                        "Implicit flow not allowed for confidential clients"
                    )

                tokens = await self._generate_tokens(
                    client_id,
                    user_id,
                    requested_scopes,
                )

                return Ok({
                    "access_token": tokens["access_token"],
                    "token_type": "Bearer",
                    "expires_in": int(self._access_token_expire.total_seconds()),
                    "scope": scope,
                    "state": state,
                })

        except OAuth2Error:
            raise
        except Exception as e:
            raise OAuth2Error("server_error", str(e))

    @beartype
    async def token(
        self,
        grant_type: str,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        code: Optional[str] = None,
        redirect_uri: Optional[str] = None,
        refresh_token: Optional[str] = None,
        scope: Optional[str] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        code_verifier: Optional[str] = None,
    ) -> Result[Dict[str, Any], OAuth2Error]:
        """Handle token request."""
        try:
            # Validate grant type
            if grant_type not in self._supported_grant_types:
                raise OAuth2Error("unsupported_grant_type")

            # Authenticate client
            client = await self._authenticate_client(client_id, client_secret)
            if not client and grant_type != "authorization_code":
                raise OAuth2Error("invalid_client")

            # Handle different grant types
            if grant_type == "authorization_code":
                return await self._handle_authorization_code_grant(
                    code, redirect_uri, client_id, code_verifier
                )

            elif grant_type == "refresh_token":
                return await self._handle_refresh_token_grant(
                    refresh_token, scope, client
                )

            elif grant_type == "client_credentials":
                return await self._handle_client_credentials_grant(
                    client, scope
                )

            elif grant_type == "password":
                return await self._handle_password_grant(
                    username, password, scope, client
                )

            else:
                raise OAuth2Error("unsupported_grant_type")

        except OAuth2Error:
            raise
        except Exception as e:
            raise OAuth2Error("server_error", str(e))

    @beartype
    async def introspect(
        self,
        token: str,
        token_type_hint: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Introspect a token."""
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
            if datetime.fromtimestamp(exp, tz=timezone.utc) < datetime.now(timezone.utc):
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
        token_type_hint: Optional[str] = None,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
    ) -> Result[bool, str]:
        """Revoke a token."""
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
    async def _generate_authorization_code(
        self,
        client_id: str,
        user_id: UUID,
        redirect_uri: str,
        scopes: List[str],
        code_challenge: Optional[str] = None,
        code_challenge_method: Optional[str] = None,
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
        user_id: Optional[UUID],
        scopes: List[str],
    ) -> Dict[str, str]:
        """Generate access and refresh tokens."""
        # Access token
        now = datetime.now(timezone.utc)
        jti = str(uuid4())

        access_payload = {
            "jti": jti,
            "client_id": client_id,
            "scope": " ".join(scopes),
            "iat": now,
            "exp": now + self._access_token_expire,
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

    # ... Additional helper methods for each grant type ...
```

### 2. Create Scope Management (`src/pd_prime_demo/core/auth/oauth2/scopes.py`)

```python
"""OAuth2 scope definitions and validation."""

from typing import List, Dict, Set, Optional
from enum import Enum

from beartype import beartype


class ScopeCategory(str, Enum):
    """Scope categories."""

    USER = "user"
    QUOTE = "quote"
    POLICY = "policy"
    CLAIM = "claim"
    ADMIN = "admin"
    ANALYTICS = "analytics"


class Scope:
    """OAuth2 scope definition."""

    def __init__(
        self,
        name: str,
        description: str,
        category: ScopeCategory,
        includes: Optional[List[str]] = None,
        requires_user: bool = True,
    ) -> None:
        """Initialize scope."""
        self.name = name
        self.description = description
        self.category = category
        self.includes = includes or []
        self.requires_user = requires_user


# Define all available scopes
SCOPES = {
    # User scopes
    "user:read": Scope(
        "user:read",
        "Read user profile information",
        ScopeCategory.USER,
    ),
    "user:write": Scope(
        "user:write",
        "Update user profile information",
        ScopeCategory.USER,
        includes=["user:read"],
    ),

    # Quote scopes
    "quote:read": Scope(
        "quote:read",
        "Read quote information",
        ScopeCategory.QUOTE,
    ),
    "quote:write": Scope(
        "quote:write",
        "Create and update quotes",
        ScopeCategory.QUOTE,
        includes=["quote:read"],
    ),
    "quote:calculate": Scope(
        "quote:calculate",
        "Calculate quote pricing",
        ScopeCategory.QUOTE,
        includes=["quote:read"],
    ),
    "quote:convert": Scope(
        "quote:convert",
        "Convert quotes to policies",
        ScopeCategory.QUOTE,
        includes=["quote:read", "policy:write"],
    ),

    # Policy scopes
    "policy:read": Scope(
        "policy:read",
        "Read policy information",
        ScopeCategory.POLICY,
    ),
    "policy:write": Scope(
        "policy:write",
        "Create and update policies",
        ScopeCategory.POLICY,
        includes=["policy:read"],
    ),
    "policy:cancel": Scope(
        "policy:cancel",
        "Cancel policies",
        ScopeCategory.POLICY,
        includes=["policy:read", "policy:write"],
    ),

    # Claim scopes
    "claim:read": Scope(
        "claim:read",
        "Read claim information",
        ScopeCategory.CLAIM,
    ),
    "claim:write": Scope(
        "claim:write",
        "Create and update claims",
        ScopeCategory.CLAIM,
        includes=["claim:read"],
    ),

    # Analytics scopes
    "analytics:read": Scope(
        "analytics:read",
        "Read analytics data",
        ScopeCategory.ANALYTICS,
        requires_user=False,
    ),

    # Admin scopes
    "admin:users": Scope(
        "admin:users",
        "Manage users",
        ScopeCategory.ADMIN,
    ),
    "admin:clients": Scope(
        "admin:clients",
        "Manage OAuth2 clients",
        ScopeCategory.ADMIN,
    ),
}


class ScopeValidator:
    """Validate and expand OAuth2 scopes."""

    @staticmethod
    @beartype
    def validate_scopes(
        requested_scopes: List[str],
        allowed_scopes: Optional[List[str]] = None,
    ) -> Tuple[bool, List[str], Optional[str]]:
        """Validate requested scopes."""
        # Check if all requested scopes exist
        invalid_scopes = [s for s in requested_scopes if s not in SCOPES]
        if invalid_scopes:
            return False, [], f"Invalid scopes: {', '.join(invalid_scopes)}"

        # Check if scopes are allowed for client
        if allowed_scopes is not None:
            disallowed = set(requested_scopes) - set(allowed_scopes)
            if disallowed:
                return False, [], f"Scopes not allowed: {', '.join(disallowed)}"

        # Expand scopes to include dependencies
        expanded_scopes = ScopeValidator.expand_scopes(requested_scopes)

        return True, list(expanded_scopes), None

    @staticmethod
    @beartype
    def expand_scopes(scopes: List[str]) -> Set[str]:
        """Expand scopes to include all dependencies."""
        expanded = set()

        def add_scope_with_includes(scope_name: str) -> None:
            if scope_name in expanded:
                return

            expanded.add(scope_name)

            scope = SCOPES.get(scope_name)
            if scope and scope.includes:
                for included in scope.includes:
                    add_scope_with_includes(included)

        for scope in scopes:
            add_scope_with_includes(scope)

        return expanded

    @staticmethod
    @beartype
    def check_scope_permission(
        token_scopes: List[str],
        required_scope: str,
    ) -> bool:
        """Check if token has required scope."""
        expanded = ScopeValidator.expand_scopes(token_scopes)
        return required_scope in expanded
```

### 3. Create API Key Management (`src/pd_prime_demo/core/auth/oauth2/api_keys.py`)

```python
"""API key management for simplified authentication."""

import secrets
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from uuid import UUID

from beartype import beartype

from ....core.database import Database
from ....core.cache import Cache
from ....services.result import Result, Ok, Err


class APIKeyManager:
    """Manage API keys for partner integrations."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize API key manager."""
        self._db = db
        self._cache = cache
        self._cache_prefix = "api_key:"

    @beartype
    async def create_api_key(
        self,
        name: str,
        client_id: str,
        scopes: List[str],
        expires_in_days: Optional[int] = None,
        rate_limit_per_minute: int = 60,
        allowed_ips: Optional[List[str]] = None,
    ) -> Result[Dict[str, Any], str]:
        """Create a new API key."""
        try:
            # Generate key
            key_prefix = "pd_"  # Prefix for easy identification
            key_secret = secrets.token_urlsafe(32)
            api_key = f"{key_prefix}{key_secret}"

            # Hash for storage
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            # Calculate expiration
            expires_at = None
            if expires_in_days:
                expires_at = datetime.now(timezone.utc) + timedelta(days=expires_in_days)

            # Store in database
            key_id = await self._db.fetchval(
                """
                INSERT INTO api_keys (
                    key_hash, name, client_id, scopes,
                    rate_limit_per_minute, allowed_ips,
                    expires_at, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                RETURNING id
                """,
                key_hash,
                name,
                client_id,
                scopes,
                rate_limit_per_minute,
                allowed_ips,
                expires_at,
                datetime.now(timezone.utc),
            )

            # Cache key info for fast lookup
            cache_data = {
                "id": str(key_id),
                "client_id": client_id,
                "scopes": scopes,
                "rate_limit": rate_limit_per_minute,
                "allowed_ips": allowed_ips,
            }

            cache_ttl = 3600  # 1 hour
            if expires_at:
                # Cache until expiration
                cache_ttl = int((expires_at - datetime.now(timezone.utc)).total_seconds())

            await self._cache.set(
                f"{self._cache_prefix}{key_hash}",
                cache_data,
                min(cache_ttl, 86400),  # Max 1 day cache
            )

            return Ok({
                "id": key_id,
                "api_key": api_key,
                "name": name,
                "scopes": scopes,
                "expires_at": expires_at.isoformat() if expires_at else None,
                "rate_limit_per_minute": rate_limit_per_minute,
                "note": "Store this API key securely. It cannot be retrieved later.",
            })

        except Exception as e:
            return Err(f"Failed to create API key: {str(e)}")

    @beartype
    async def validate_api_key(
        self,
        api_key: str,
        required_scope: Optional[str] = None,
        request_ip: Optional[str] = None,
    ) -> Result[Dict[str, Any], str]:
        """Validate API key and check permissions."""
        try:
            # Hash the key
            key_hash = hashlib.sha256(api_key.encode()).hexdigest()

            # Check cache first
            cache_key = f"{self._cache_prefix}{key_hash}"
            cached = await self._cache.get(cache_key)

            if cached:
                key_info = cached
            else:
                # Load from database
                row = await self._db.fetchrow(
                    """
                    SELECT id, client_id, scopes, rate_limit_per_minute,
                           allowed_ips, expires_at, active
                    FROM api_keys
                    WHERE key_hash = $1
                    """,
                    key_hash,
                )

                if not row:
                    return Err("Invalid API key")

                if not row["active"]:
                    return Err("API key is disabled")

                if row["expires_at"] and row["expires_at"] < datetime.now(timezone.utc):
                    return Err("API key has expired")

                key_info = {
                    "id": str(row["id"]),
                    "client_id": row["client_id"],
                    "scopes": row["scopes"],
                    "rate_limit": row["rate_limit_per_minute"],
                    "allowed_ips": row["allowed_ips"],
                }

                # Cache for future lookups
                await self._cache.set(cache_key, key_info, 3600)

            # Check IP allowlist
            if key_info.get("allowed_ips") and request_ip:
                if request_ip not in key_info["allowed_ips"]:
                    return Err(f"IP {request_ip} not allowed for this API key")

            # Check scope
            if required_scope:
                from .scopes import ScopeValidator

                if not ScopeValidator.check_scope_permission(
                    key_info["scopes"],
                    required_scope
                ):
                    return Err(f"API key lacks required scope: {required_scope}")

            # Check rate limit
            rate_limit_ok = await self._check_rate_limit(
                key_info["id"],
                key_info["rate_limit"]
            )

            if not rate_limit_ok:
                return Err("Rate limit exceeded")

            # Update last used
            await self._update_last_used(key_info["id"])

            return Ok(key_info)

        except Exception as e:
            return Err(f"Failed to validate API key: {str(e)}")

    @beartype
    async def _check_rate_limit(
        self,
        key_id: str,
        limit_per_minute: int,
    ) -> bool:
        """Check if API key is within rate limit."""
        now = datetime.now(timezone.utc)
        minute_key = now.strftime("%Y%m%d%H%M")

        rate_limit_key = f"rate_limit:{key_id}:{minute_key}"

        # Increment counter
        count = await self._cache.incr(rate_limit_key)

        # Set expiration on first increment
        if count == 1:
            await self._cache.expire(rate_limit_key, 60)

        return count <= limit_per_minute

    # ... Additional methods for key rotation, revocation, etc. ...
```

## SEARCH TRIGGERS (30-second timeout)

If confidence < 95% on:

- OAuth2 flows → Search: "oauth2 grant types explained"
- JWT best practices → Search: "jwt security best practices"
- PKCE implementation → Search: "oauth2 pkce flow"

## DELIVERABLES

1. **OAuth2 Server**: Complete authorization server
2. **Scope Management**: Flexible scope system
3. **API Key Manager**: Simple key-based auth
4. **Client Management UI**: Admin interface
5. **Developer Portal**: API documentation

## SUCCESS CRITERIA

1. All OAuth2 flows working correctly
2. JWT tokens properly signed and validated
3. Refresh token rotation implemented
4. API keys with rate limiting work
5. Comprehensive security measures

## PARALLEL COORDINATION

- Agent 09 handles SSO integration
- Agent 11 adds MFA to OAuth2
- Agent 01 creates OAuth2 tables
- Agent 12 ensures compliance

Document all security decisions clearly!

## ADDITIONAL REQUIREMENT: Admin OAuth2 Client Management

**IMPORTANT**: You must ALSO read `.sage/wave_contexts/wave_2/AGENT_DEPLOYMENT_SUMMARY.md` to understand the full system context.

### 4. Create Admin OAuth2 Client Management Service (`src/pd_prime_demo/services/admin/oauth2_admin_service.py`)

You must also implement comprehensive admin OAuth2 client management:

```python
"""Admin OAuth2 client management service."""

from typing import List, Dict, Any, Optional
from uuid import UUID, uuid4
from datetime import datetime, timedelta
import secrets
import hashlib

from beartype import beartype

from ...core.cache import Cache
from ...core.database import Database
from ..result import Result, Ok, Err

class OAuth2AdminService:
    """Service for admin OAuth2 client management."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize OAuth2 admin service."""
        self._db = db
        self._cache = cache
        self._client_cache_prefix = "oauth2_client:"

    @beartype
    async def create_oauth2_client(
        self,
        admin_user_id: UUID,
        client_name: str,
        client_type: str,  # 'public', 'confidential'
        allowed_grant_types: List[str],
        allowed_scopes: List[str],
        redirect_uris: List[str],
        description: Optional[str] = None,
        token_lifetime: int = 3600,  # 1 hour default
        refresh_token_lifetime: int = 86400 * 7,  # 1 week default
    ) -> Result[Dict[str, Any], str]:
        """Create new OAuth2 client application."""
        try:
            # Generate client credentials
            client_id = f"pd_{secrets.token_urlsafe(16)}"
            client_secret = None
            client_secret_hash = None

            if client_type == 'confidential':
                client_secret = secrets.token_urlsafe(32)
                client_secret_hash = hashlib.sha256(client_secret.encode()).hexdigest()

            # Validate grant types and scopes
            valid_grants = ['authorization_code', 'client_credentials', 'refresh_token']
            invalid_grants = set(allowed_grant_types) - set(valid_grants)
            if invalid_grants:
                return Err(f"Invalid grant types: {invalid_grants}")

            # Validate scopes exist
            from ...core.auth.oauth2.scopes import SCOPES
            invalid_scopes = [s for s in allowed_scopes if s not in SCOPES]
            if invalid_scopes:
                return Err(f"Invalid scopes: {invalid_scopes}")

            oauth2_client_id = uuid4()

            await self._db.execute(
                """
                INSERT INTO oauth2_clients (
                    id, client_id, client_secret_hash, client_name,
                    client_type, description, allowed_grant_types,
                    allowed_scopes, redirect_uris, token_lifetime,
                    refresh_token_lifetime, created_by, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13)
                """,
                oauth2_client_id, client_id, client_secret_hash, client_name,
                client_type, description, allowed_grant_types, allowed_scopes,
                redirect_uris, token_lifetime, refresh_token_lifetime,
                admin_user_id, datetime.utcnow()
            )

            # Clear client cache
            await self._cache.delete_pattern(f"{self._client_cache_prefix}*")

            # Log client creation
            await self._log_oauth2_activity(
                admin_user_id, "create_client", oauth2_client_id,
                {"client_name": client_name, "client_type": client_type}
            )

            result = {
                "id": oauth2_client_id,
                "client_id": client_id,
                "client_name": client_name,
                "client_type": client_type,
                "allowed_scopes": allowed_scopes,
                "redirect_uris": redirect_uris,
                "token_lifetime": token_lifetime,
            }

            if client_secret:
                result["client_secret"] = client_secret
                result["note"] = "Store client_secret securely. It cannot be retrieved later."

            return Ok(result)

        except Exception as e:
            return Err(f"Client creation failed: {str(e)}")

    @beartype
    async def update_client_config(
        self,
        client_id: str,
        admin_user_id: UUID,
        updates: Dict[str, Any],
    ) -> Result[bool, str]:
        """Update OAuth2 client configuration."""
        try:
            # Get existing client
            client = await self._db.fetchrow(
                "SELECT * FROM oauth2_clients WHERE client_id = $1",
                client_id
            )
            if not client:
                return Err("Client not found")

            # Build update query dynamically
            allowed_fields = [
                'client_name', 'description', 'allowed_scopes',
                'redirect_uris', 'token_lifetime', 'refresh_token_lifetime',
                'is_active'
            ]

            update_fields = []
            values = []
            param_count = 1

            for field, value in updates.items():
                if field in allowed_fields:
                    param_count += 1
                    update_fields.append(f"{field} = ${param_count}")
                    values.append(value)

            if not update_fields:
                return Err("No valid fields to update")

            # Add updated metadata
            param_count += 1
            update_fields.append(f"updated_by = ${param_count}")
            values.append(admin_user_id)

            param_count += 1
            update_fields.append(f"updated_at = ${param_count}")
            values.append(datetime.utcnow())

            query = f"""
                UPDATE oauth2_clients
                SET {', '.join(update_fields)}
                WHERE client_id = $1
            """

            await self._db.execute(query, client_id, *values)

            # Clear cache
            await self._cache.delete_pattern(f"{self._client_cache_prefix}*")

            # Log update
            await self._log_oauth2_activity(
                admin_user_id, "update_client", client['id'],
                {"updates": list(updates.keys())}
            )

            return Ok(True)

        except Exception as e:
            return Err(f"Update failed: {str(e)}")

    @beartype
    async def regenerate_client_secret(
        self,
        client_id: str,
        admin_user_id: UUID,
    ) -> Result[str, str]:
        """Regenerate client secret for confidential clients."""
        try:
            # Get client
            client = await self._db.fetchrow(
                "SELECT * FROM oauth2_clients WHERE client_id = $1",
                client_id
            )
            if not client:
                return Err("Client not found")

            if client['client_type'] != 'confidential':
                return Err("Only confidential clients have secrets")

            # Generate new secret
            new_secret = secrets.token_urlsafe(32)
            secret_hash = hashlib.sha256(new_secret.encode()).hexdigest()

            # Update database
            await self._db.execute(
                """
                UPDATE oauth2_clients
                SET client_secret_hash = $2, updated_by = $3, updated_at = $4
                WHERE client_id = $1
                """,
                client_id, secret_hash, admin_user_id, datetime.utcnow()
            )

            # Revoke all existing tokens for this client
            await self._revoke_client_tokens(client_id)

            # Clear cache
            await self._cache.delete_pattern(f"{self._client_cache_prefix}*")

            # Log secret regeneration
            await self._log_oauth2_activity(
                admin_user_id, "regenerate_secret", client['id'],
                {"client_id": client_id}
            )

            return Ok(new_secret)

        except Exception as e:
            return Err(f"Secret regeneration failed: {str(e)}")

    @beartype
    async def get_client_analytics(
        self,
        client_id: str,
        date_from: datetime,
        date_to: datetime,
    ) -> Result[Dict[str, Any], str]:
        """Get OAuth2 client usage analytics."""
        try:
            # Token usage statistics
            token_stats = await self._db.fetchrow(
                """
                SELECT
                    COUNT(*) as total_tokens,
                    COUNT(DISTINCT user_id) as unique_users,
                    COUNT(*) FILTER (WHERE grant_type = 'authorization_code') as auth_code_grants,
                    COUNT(*) FILTER (WHERE grant_type = 'client_credentials') as client_cred_grants,
                    COUNT(*) FILTER (WHERE grant_type = 'refresh_token') as refresh_grants,
                    COUNT(*) FILTER (WHERE revoked_at IS NOT NULL) as revoked_tokens
                FROM oauth2_tokens
                WHERE client_id = $1
                    AND created_at BETWEEN $2 AND $3
                """,
                client_id, date_from, date_to
            )

            # API usage by scope
            scope_usage = await self._db.fetch(
                """
                SELECT
                    unnest(scopes) as scope,
                    COUNT(*) as usage_count
                FROM oauth2_tokens
                WHERE client_id = $1
                    AND created_at BETWEEN $2 AND $3
                GROUP BY scope
                ORDER BY usage_count DESC
                """,
                client_id, date_from, date_to
            )

            # Usage timeline
            usage_timeline = await self._db.fetch(
                """
                SELECT
                    date_trunc('day', created_at) as date,
                    COUNT(*) as token_count,
                    COUNT(DISTINCT user_id) as unique_users
                FROM oauth2_tokens
                WHERE client_id = $1
                    AND created_at BETWEEN $2 AND $3
                GROUP BY date
                ORDER BY date
                """,
                client_id, date_from, date_to
            )

            return Ok({
                "token_statistics": dict(token_stats) if token_stats else {},
                "scope_usage": [dict(row) for row in scope_usage],
                "usage_timeline": [dict(row) for row in usage_timeline],
                "period": {"from": date_from, "to": date_to}
            })

        except Exception as e:
            return Err(f"Analytics failed: {str(e)}")

    @beartype
    async def revoke_client_access(
        self,
        client_id: str,
        admin_user_id: UUID,
        reason: str,
    ) -> Result[int, str]:
        """Revoke all active tokens for a client."""
        try:
            # Count tokens to be revoked
            token_count = await self._db.fetchval(
                """
                SELECT COUNT(*) FROM oauth2_tokens
                WHERE client_id = $1 AND revoked_at IS NULL
                """,
                client_id
            )

            # Revoke all active tokens
            await self._db.execute(
                """
                UPDATE oauth2_tokens
                SET revoked_at = $2, revoked_by = $3, revocation_reason = $4
                WHERE client_id = $1 AND revoked_at IS NULL
                """,
                client_id, datetime.utcnow(), admin_user_id, reason
            )

            # Clear token cache
            await self._cache.delete_pattern(f"oauth2_token:*")

            # Log revocation
            await self._log_oauth2_activity(
                admin_user_id, "revoke_client_tokens", None,
                {"client_id": client_id, "tokens_revoked": token_count, "reason": reason}
            )

            return Ok(token_count)

        except Exception as e:
            return Err(f"Token revocation failed: {str(e)}")
```

### 5. Create Admin OAuth2 Management API (`src/pd_prime_demo/api/v1/admin/oauth2_management.py`)

```python
"""Admin OAuth2 client management endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from datetime import datetime
from uuid import UUID

from beartype import beartype

from ....services.admin.oauth2_admin_service import OAuth2AdminService
from ...dependencies import get_oauth2_admin_service, get_current_admin_user
from ....models.admin import AdminUser

router = APIRouter()

@router.post("/clients")
@beartype
async def create_oauth2_client(
    client_request: OAuth2ClientCreateRequest,
    oauth2_service: OAuth2AdminService = Depends(get_oauth2_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Create new OAuth2 client application."""
    if "admin:clients" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await oauth2_service.create_oauth2_client(
        admin_user.id,
        client_request.client_name,
        client_request.client_type,
        client_request.allowed_grant_types,
        client_request.allowed_scopes,
        client_request.redirect_uris,
        client_request.description,
        client_request.token_lifetime,
        client_request.refresh_token_lifetime
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return result.value

@router.post("/clients/{client_id}/regenerate-secret")
@beartype
async def regenerate_client_secret(
    client_id: str,
    oauth2_service: OAuth2AdminService = Depends(get_oauth2_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Regenerate client secret."""
    if "admin:clients" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await oauth2_service.regenerate_client_secret(
        client_id, admin_user.id
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return {
        "client_secret": result.value,
        "note": "Store this securely. It cannot be retrieved later."
    }

@router.get("/clients/{client_id}/analytics")
@beartype
async def get_client_analytics(
    client_id: str,
    date_from: datetime,
    date_to: datetime,
    oauth2_service: OAuth2AdminService = Depends(get_oauth2_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Get OAuth2 client usage analytics."""
    result = await oauth2_service.get_client_analytics(
        client_id, date_from, date_to
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return result.value

@router.post("/clients/{client_id}/revoke")
@beartype
async def revoke_client_access(
    client_id: str,
    revocation_request: TokenRevocationRequest,
    oauth2_service: OAuth2AdminService = Depends(get_oauth2_admin_service),
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Revoke all access tokens for a client."""
    if "admin:clients" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    result = await oauth2_service.revoke_client_access(
        client_id, admin_user.id, revocation_request.reason
    )

    if result.is_err():
        raise HTTPException(status_code=400, detail=result.error)

    return {"tokens_revoked": result.value}
```

### 6. Add OAuth2 Management Tables

Tell Agent 01 to also create:

```sql
-- OAuth2 client applications
CREATE TABLE oauth2_clients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id VARCHAR(100) UNIQUE NOT NULL,
    client_secret_hash VARCHAR(255), -- NULL for public clients
    client_name VARCHAR(100) NOT NULL,
    client_type VARCHAR(20) NOT NULL, -- 'public', 'confidential'
    description TEXT,

    -- Authorization configuration
    allowed_grant_types TEXT[] NOT NULL,
    allowed_scopes TEXT[] NOT NULL,
    redirect_uris TEXT[] NOT NULL,

    -- Token configuration
    token_lifetime INTEGER DEFAULT 3600, -- seconds
    refresh_token_lifetime INTEGER DEFAULT 604800, -- 1 week

    -- Status
    is_active BOOLEAN DEFAULT true,

    -- Audit
    created_by UUID REFERENCES admin_users(id),
    updated_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- OAuth2 access tokens
CREATE TABLE oauth2_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    client_id VARCHAR(100) REFERENCES oauth2_clients(client_id),
    user_id UUID REFERENCES customers(id), -- NULL for client_credentials
    scopes TEXT[] NOT NULL,
    grant_type VARCHAR(50) NOT NULL,

    -- Expiration
    expires_at TIMESTAMPTZ NOT NULL,

    -- Revocation
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES admin_users(id),
    revocation_reason TEXT,

    -- Metadata
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- OAuth2 refresh tokens
CREATE TABLE oauth2_refresh_tokens (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    access_token_id UUID REFERENCES oauth2_tokens(id),
    client_id VARCHAR(100) REFERENCES oauth2_clients(client_id),
    user_id UUID REFERENCES customers(id),

    -- Expiration and revocation
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    revoked_by UUID REFERENCES admin_users(id),

    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- OAuth2 authorization codes (temporary)
CREATE TABLE oauth2_authorization_codes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    code_hash VARCHAR(255) UNIQUE NOT NULL,
    client_id VARCHAR(100) REFERENCES oauth2_clients(client_id),
    user_id UUID REFERENCES customers(id),
    scopes TEXT[] NOT NULL,
    redirect_uri TEXT NOT NULL,
    code_challenge VARCHAR(255), -- For PKCE
    code_challenge_method VARCHAR(10), -- 'S256' or 'plain'

    expires_at TIMESTAMPTZ NOT NULL,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_oauth2_tokens_client_user ON oauth2_tokens(client_id, user_id);
CREATE INDEX idx_oauth2_tokens_expires ON oauth2_tokens(expires_at);
CREATE INDEX idx_oauth2_refresh_tokens_access ON oauth2_refresh_tokens(access_token_id);
```

Make sure all OAuth2 operations include proper admin authentication and comprehensive audit logging!

## ADDITIONAL GAPS TO WATCH

### OAuth2 Authorization Server Anti-Patterns and Edge Cases

**Token Validation Extremes and Performance:**

- **Similar Gap**: Over-validating JWT tokens with expensive cryptographic operations on every API call causing latency spikes
- **Lateral Gap**: Token introspection not properly cached causing database bottlenecks during high-traffic periods
- **Inverted Gap**: Under-validating token claims missing revoked tokens still in circulation
- **Meta-Gap**: Not monitoring token validation performance impact on overall API response times

**Scope Management and Permission Granularity:**

- **Similar Gap**: Over-granular OAuth2 scopes creating complex permission matrices that are difficult to manage and audit
- **Lateral Gap**: Scope inheritance not properly implemented causing permission gaps in related operations
- **Inverted Gap**: Over-broad scopes violating principle of least privilege for API access
- **Meta-Gap**: Not analyzing actual scope usage patterns against granted permissions to optimize scope design

**Client Registration Workflow Security:**

- **Similar Gap**: Automated client registration without proper business justification review allowing potentially malicious integrations
- **Lateral Gap**: Client registration not properly integrated with organizational approval workflows
- **Inverted Gap**: Over-restrictive client registration preventing legitimate business integrations
- **Meta-Gap**: Not monitoring client registration patterns for potential security threats or abuse

**Grant Type Implementation Edge Cases:**

- **Similar Gap**: Authorization code flow not properly implementing PKCE causing mobile app security vulnerabilities
- **Lateral Gap**: Client credentials flow not properly rate-limited allowing potential abuse
- **Inverted Gap**: Disabling useful grant types due to security concerns without implementing proper controls
- **Meta-Gap**: Not testing OAuth2 flow security against current attack patterns and vulnerabilities

**Time-Based OAuth2 Security Issues:**

- **Token Rotation**: Refresh token rotation not properly implemented causing session hijacking vulnerabilities
- **Code Expiration**: Authorization codes not expiring quickly enough creating replay attack windows
- **Token Lifetime**: Access token lifetimes not balanced between security and user experience

**Scale-Based OAuth2 Performance:**

- **Token Storage**: OAuth2 token storage not optimized for high-volume token issuance and validation
- **Concurrent Flows**: Multiple simultaneous OAuth2 flows for same user not properly coordinated
- **Rate Limiting**: OAuth2 endpoints not properly rate-limited causing potential DoS vulnerabilities

**Cross-Application Integration Complexity:**

- **Multi-Tenant Support**: OAuth2 server not properly isolating tenants in shared infrastructure
- **API Gateway Integration**: OAuth2 tokens not properly validated at API gateway level
- **Microservice Authorization**: Service-to-service OAuth2 communication not properly secured

**Redirect URI Validation and Security:**

- **Dynamic Redirects**: Redirect URI validation not handling dynamic subdomain scenarios securely
- **Mobile Deep Links**: OAuth2 redirect handling not secure for mobile app custom URL schemes
- **Localhost Development**: Development redirect URIs not properly isolated from production configurations

**Token Revocation and Cleanup:**

- **Bulk Revocation**: Mass token revocation not efficiently implemented for security incident response
- **Automatic Cleanup**: Expired token cleanup not properly scheduled causing database bloat
- **Cascading Revocation**: Token revocation not properly cascading to related sessions and derived tokens

**Audit and Compliance Integration:**

- **OAuth2 Event Logging**: Not capturing sufficient OAuth2 flow details for security audits
- **Compliance Reporting**: OAuth2 usage patterns not properly tracked for regulatory compliance
- **Data Retention**: OAuth2 audit logs not properly managed for privacy and compliance requirements

**Error Handling and Security Disclosure:**

- **Error Information Leakage**: OAuth2 error responses revealing too much information about system internals
- **Client Error Handling**: OAuth2 errors not providing sufficient context for client troubleshooting
- **Attack Surface**: OAuth2 error conditions not properly hardened against information disclosure attacks

**Integration with External Identity Systems:**

- **Federation Compatibility**: OAuth2 server not properly integrating with SAML or other federation protocols
- **Identity Provider Sync**: OAuth2 user identity not properly synchronized with external identity sources
- **Cross-Protocol Security**: OAuth2 and SSO integration not maintaining consistent security posture
