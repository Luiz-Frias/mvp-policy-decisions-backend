#!/usr/bin/env python3
"""Comprehensive OAuth2 RFC 6749 compliance test script."""

import asyncio
import sys
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Logging Setup (replaces legacy ``print`` calls with structured logging)
# ---------------------------------------------------------------------------
from src.pd_prime_demo.core.logging_utils import configure_logging, patch_print

configure_logging()
patch_print()

from src.pd_prime_demo.core.auth.oauth2.scopes import ScopeValidator
from src.pd_prime_demo.core.auth.oauth2.server import OAuth2Server
from src.pd_prime_demo.core.config import Settings


async def test_oauth2_rfc_compliance():
    """Test OAuth2 server RFC 6749 compliance."""
    print("Testing OAuth2 RFC 6749 Compliance...")
    print("=" * 60)

    # Initialize with test settings
    settings = Settings(
        database_url="sqlite:///:memory:",
        redis_url="redis://localhost:6379/0",
        secret_key="test_secret_key_for_oauth2_testing_12345",
        jwt_secret="test_jwt_secret_for_oauth2_testing_12345",
        api_env="development",
        openai_api_key="test_openai_key",
    )

    # Create mock database for testing
    class MockDatabase:
        def __init__(self):
            self.clients = {}
            self.tokens = {}
            self.auth_codes = {}

        async def execute(self, query: str, *args) -> str:
            if "INSERT INTO oauth2_clients" in query:
                return "INSERT 1"
            elif "INSERT INTO oauth2_tokens" in query:
                return "INSERT 1"
            elif "INSERT INTO oauth2_authorization_codes" in query:
                return "INSERT 1"
            return "UPDATE 1"

        async def fetchrow(self, query: str, *args) -> dict | None:
            if "SELECT * FROM oauth2_clients" in query and args:
                client_id = args[0]
                return self.clients.get(client_id)
            elif "SELECT * FROM oauth2_authorization_codes" in query and args:
                auth_code = args[0]
                return self.auth_codes.get(auth_code)
            return None

        async def fetchval(self, query: str, *args) -> Any:
            return "test_id"

        async def fetch(self, query: str, *args) -> list[dict]:
            return []

        async def fetchall(self, query: str, *args) -> list[dict]:
            return []

    # Create mock cache for testing
    class MockCache:
        def __init__(self):
            self._data = {}

        async def connect(self):
            pass

        async def disconnect(self):
            pass

        async def set(self, key, value, ttl=None):
            self._data[key] = value
            return True

        async def get(self, key):
            return self._data.get(key)

        async def delete(self, key):
            if key in self._data:
                del self._data[key]
            return True

        async def incr(self, key):
            self._data[key] = self._data.get(key, 0) + 1
            return self._data[key]

        async def expire(self, key, ttl):
            return True

        async def delete_pattern(self, pattern):
            return True

    db = MockDatabase()
    cache = MockCache()
    oauth2_server = OAuth2Server(db, cache, settings)

    # Test 1: RFC 6749 Section 4.1 - Authorization Code Grant
    print("\n1. Testing Authorization Code Grant (RFC 6749 Section 4.1)...")

    # Create test client
    client_result = await oauth2_server.create_client(
        client_name="Test Confidential Client",
        redirect_uris=["https://example.com/callback"],
        allowed_grant_types=["authorization_code", "refresh_token"],
        allowed_scopes=["quote:read", "quote:write"],
        client_type="confidential",
    )

    if client_result.is_ok():
        client = client_result.value
        print(f"   ✓ Client created: {client['client_id']}")

        # Store client in mock database
        db.clients[client["client_id"]] = client

        # Test authorization code generation
        auth_code_result = await oauth2_server.generate_authorization_code(
            client_id=client["client_id"],
            redirect_uri="https://example.com/callback",
            scope="quote:read quote:write",
            user_id="test_user_123",
        )

        if auth_code_result.is_ok():
            auth_code = auth_code_result.value
            print(f"   ✓ Authorization code generated: {auth_code[:20]}...")

            # Store auth code in mock database
            db.auth_codes[auth_code] = {
                "client_id": client["client_id"],
                "user_id": "test_user_123",
                "scope": "quote:read quote:write",
                "redirect_uri": "https://example.com/callback",
                "expires_at": "2025-07-06T01:00:00",
            }

            # Test token exchange
            token_result = await oauth2_server.exchange_code_for_token(
                code=auth_code,
                client_id=client["client_id"],
                client_secret=client["client_secret"],
                redirect_uri="https://example.com/callback",
            )

            if token_result.is_ok():
                tokens = token_result.value
                print(f"   ✓ Access token issued: {tokens['access_token'][:20]}...")
                if "refresh_token" in tokens:
                    print(
                        f"   ✓ Refresh token issued: {tokens['refresh_token'][:20]}..."
                    )
            else:
                print(f"   ✗ Token exchange failed: {token_result.error}")
        else:
            print(
                f"   ✗ Authorization code generation failed: {auth_code_result.error}"
            )
    else:
        print(f"   ✗ Client creation failed: {client_result.error}")

    # Test 2: RFC 6749 Section 4.2 - Implicit Grant (Should be rejected for security)
    print("\n2. Testing Implicit Grant Security (RFC 6749 Section 4.2)...")

    public_client_result = await oauth2_server.create_client(
        client_name="Test Public Client",
        redirect_uris=["https://example.com/callback"],
        allowed_grant_types=["implicit"],  # Should be rejected
        allowed_scopes=["quote:read"],
        client_type="public",
    )

    # The implementation should reject implicit grant as per modern security practices
    if public_client_result.is_err():
        print("   ✓ Implicit grant properly rejected for security")
    else:
        print("   ⚠️ Implicit grant allowed - consider security implications")

    # Test 3: RFC 6749 Section 4.3 - Resource Owner Password Credentials Grant
    print(
        "\n3. Testing Resource Owner Password Credentials Grant (RFC 6749 Section 4.3)..."
    )

    # Create client with password grant
    password_client_result = await oauth2_server.create_client(
        client_name="Test Password Client",
        redirect_uris=[],
        allowed_grant_types=["password"],
        allowed_scopes=["quote:read"],
        client_type="confidential",
    )

    if password_client_result.is_ok():
        password_client = password_client_result.value
        print(f"   ✓ Password grant client created: {password_client['client_id']}")

        # Store client in mock database
        db.clients[password_client["client_id"]] = password_client

        # Test password grant
        password_token_result = await oauth2_server.password_grant(
            client_id=password_client["client_id"],
            client_secret=password_client["client_secret"],
            username="testuser",
            password="testpass",
            scope="quote:read",
        )

        if password_token_result.is_ok():
            tokens = password_token_result.value
            print(f"   ✓ Password grant token issued: {tokens['access_token'][:20]}...")
        else:
            print(f"   ✗ Password grant failed: {password_token_result.error}")
    else:
        print(
            f"   ✗ Password grant client creation failed: {password_client_result.error}"
        )

    # Test 4: RFC 6749 Section 4.4 - Client Credentials Grant
    print("\n4. Testing Client Credentials Grant (RFC 6749 Section 4.4)...")

    # Create client with client credentials grant
    cc_client_result = await oauth2_server.create_client(
        client_name="Test Client Credentials Client",
        redirect_uris=[],
        allowed_grant_types=["client_credentials"],
        allowed_scopes=["analytics:read"],
        client_type="confidential",
    )

    if cc_client_result.is_ok():
        cc_client = cc_client_result.value
        print(f"   ✓ Client credentials client created: {cc_client['client_id']}")

        # Store client in mock database
        db.clients[cc_client["client_id"]] = cc_client

        # Test client credentials grant
        cc_token_result = await oauth2_server.client_credentials_grant(
            client_id=cc_client["client_id"],
            client_secret=cc_client["client_secret"],
            scope="analytics:read",
        )

        if cc_token_result.is_ok():
            tokens = cc_token_result.value
            print(
                f"   ✓ Client credentials token issued: {tokens['access_token'][:20]}..."
            )
        else:
            print(f"   ✗ Client credentials grant failed: {cc_token_result.error}")
    else:
        print(
            f"   ✗ Client credentials client creation failed: {cc_client_result.error}"
        )

    # Test 5: RFC 6749 Section 6 - Refreshing an Access Token
    print("\n5. Testing Token Refresh (RFC 6749 Section 6)...")

    if "tokens" in locals() and "refresh_token" in tokens:
        refresh_result = await oauth2_server.refresh_token(
            refresh_token=tokens["refresh_token"],
            client_id=client["client_id"],
            client_secret=client["client_secret"],
        )

        if refresh_result.is_ok():
            new_tokens = refresh_result.value
            print(f"   ✓ Token refreshed: {new_tokens['access_token'][:20]}...")
        else:
            print(f"   ✗ Token refresh failed: {refresh_result.error}")
    else:
        print("   ⚠️ No refresh token available for testing")

    # Test 6: RFC 6749 Section 7 - Accessing Protected Resources
    print("\n6. Testing Protected Resource Access (RFC 6749 Section 7)...")

    if "tokens" in locals():
        # Test token introspection
        introspection_result = await oauth2_server.introspect_token(
            token=tokens["access_token"]
        )

        if introspection_result.is_ok():
            token_info = introspection_result.value
            print(
                f"   ✓ Token introspection successful: active={token_info.get('active')}"
            )
        else:
            print(f"   ✗ Token introspection failed: {introspection_result.error}")
    else:
        print("   ⚠️ No access token available for testing")

    # Test 7: RFC 7009 - Token Revocation
    print("\n7. Testing Token Revocation (RFC 7009)...")

    if "tokens" in locals():
        revocation_result = await oauth2_server.revoke_token(
            token=tokens["access_token"],
            client_id=client["client_id"],
            client_secret=client["client_secret"],
        )

        if revocation_result.is_ok():
            print("   ✓ Token revocation successful")
        else:
            print(f"   ✗ Token revocation failed: {revocation_result.error}")
    else:
        print("   ⚠️ No access token available for testing")

    # Test 8: PKCE Support (RFC 7636)
    print("\n8. Testing PKCE Support (RFC 7636)...")

    # Generate PKCE parameters
    pkce_result = oauth2_server.generate_pkce_challenge()
    if pkce_result.is_ok():
        pkce_params = pkce_result.value
        print(
            f"   ✓ PKCE code verifier generated: {pkce_params['code_verifier'][:20]}..."
        )
        print(
            f"   ✓ PKCE code challenge generated: {pkce_params['code_challenge'][:20]}..."
        )
        print(f"   ✓ PKCE challenge method: {pkce_params['code_challenge_method']}")
    else:
        print(f"   ✗ PKCE generation failed: {pkce_result.error}")

    # Test 9: Error Handling Compliance
    print("\n9. Testing Error Handling Compliance...")

    # Test invalid client
    invalid_client_result = await oauth2_server.client_credentials_grant(
        client_id="invalid_client", client_secret="invalid_secret", scope="quote:read"
    )

    if invalid_client_result.is_err():
        print("   ✓ Invalid client properly rejected")
    else:
        print("   ✗ Invalid client not properly rejected")

    # Test invalid scope
    is_valid, _, error = ScopeValidator.validate_scopes(["invalid:scope"])
    if not is_valid:
        print("   ✓ Invalid scope properly rejected")
    else:
        print("   ✗ Invalid scope not properly rejected")

    # Test 10: NO SILENT FALLBACKS Compliance
    print("\n10. Testing NO SILENT FALLBACKS Compliance...")

    # Test missing required scope parameter
    is_valid, _, error = ScopeValidator.validate_scopes([])
    if not is_valid and "scope parameter is required" in error:
        print("   ✓ Empty scope properly rejected with explicit error")
    else:
        print("   ✗ Empty scope should be rejected with explicit error")

    # Test missing client_id
    missing_client_result = await oauth2_server.client_credentials_grant(
        client_id="", client_secret="secret", scope="quote:read"
    )

    if (
        missing_client_result.is_err()
        and "client_id is required" in missing_client_result.error
    ):
        print("   ✓ Missing client_id properly rejected with explicit error")
    else:
        print("   ✗ Missing client_id should be rejected with explicit error")

    print("\n" + "=" * 60)
    print("OAuth2 RFC 6749 Compliance Testing Complete!")
    print("🎉 All major OAuth2 flows and security features tested!")


if __name__ == "__main__":
    asyncio.run(test_oauth2_rfc_compliance())
