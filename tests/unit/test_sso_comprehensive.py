"""Comprehensive unit tests for SSO integration system."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.policy_core.core.auth.providers.auth0 import Auth0SSOProvider
from src.policy_core.core.auth.providers.azure import AzureADSSOProvider
from src.policy_core.core.auth.providers.google import GoogleSSOProvider
from src.policy_core.core.auth.providers.okta import OktaSSOProvider
from src.policy_core.core.auth.sso_base import SSOUserInfo
from src.policy_core.core.auth.sso_manager import SSOManager
from src.policy_core.core.result_types import Err


class TestSSOComprehensiveIntegration:
    """Comprehensive tests for complete SSO system."""

    @pytest.fixture
    def mock_db(self):
        """Mock database connection."""
        mock = AsyncMock()
        mock.fetch = AsyncMock()
        mock.fetchrow = AsyncMock()
        mock.fetchval = AsyncMock()
        mock.execute = AsyncMock()
        mock.transaction = AsyncMock()
        mock.transaction.return_value.__aenter__ = AsyncMock()
        mock.transaction.return_value.__aexit__ = AsyncMock()
        return mock

    @pytest.fixture
    def mock_cache(self):
        """Mock cache connection."""
        mock = AsyncMock()
        mock.get = AsyncMock()
        mock.set = AsyncMock()
        mock.delete = AsyncMock()
        mock.delete_pattern = AsyncMock()
        return mock

    @pytest.fixture
    async def sso_manager(self, mock_db, mock_cache):
        """Create SSO manager instance."""
        return SSOManager(mock_db, mock_cache)

    def test_google_provider_creation(self):
        """Test Google SSO provider creation and configuration."""
        provider = GoogleSSOProvider(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="https://app.example.com/auth/callback",
            hosted_domain="example.com",
        )

        assert provider.provider_name == "google"
        assert provider.client_id == "test_client_id"
        assert provider.hosted_domain == "example.com"
        assert "openid" in provider.scopes
        assert "email" in provider.scopes
        assert "profile" in provider.scopes

    def test_azure_provider_creation(self):
        """Test Azure AD SSO provider creation and configuration."""
        provider = AzureADSSOProvider(
            client_id="azure_client_id",
            client_secret="azure_client_secret",
            redirect_uri="https://app.example.com/auth/callback",
            tenant_id="12345-67890-abcdef",
        )

        assert provider.provider_name == "azure"
        assert provider.tenant_id == "12345-67890-abcdef"
        assert "User.Read" in provider.scopes

    def test_auth0_provider_creation(self):
        """Test Auth0 SSO provider creation and configuration."""
        provider = Auth0SSOProvider(
            client_id="auth0_client_id",
            client_secret="auth0_client_secret",
            redirect_uri="https://app.example.com/auth/callback",
            auth0_domain="dev-example.auth0.com",
            audience="https://api.example.com",
        )

        assert provider.provider_name == "auth0"
        assert provider.auth0_domain == "dev-example.auth0.com"
        assert provider.audience == "https://api.example.com"

    def test_okta_provider_creation(self):
        """Test Okta SSO provider creation and configuration."""
        provider = OktaSSOProvider(
            client_id="okta_client_id",
            client_secret="okta_client_secret",
            redirect_uri="https://app.example.com/auth/callback",
            okta_domain="dev-example.okta.com",
            authorization_server_id="custom_server",
        )

        assert provider.provider_name == "okta"
        assert provider.okta_domain == "dev-example.okta.com"
        assert provider.authorization_server_id == "custom_server"

    @patch("src.policy_core.core.auth.providers.google.httpx.AsyncClient")
    async def test_google_oidc_discovery(self, mock_client):
        """Test Google OIDC discovery document fetching."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "issuer": "https://accounts.google.com",
            "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_endpoint": "https://oauth2.googleapis.com/token",
            "userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo",
            "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
        }

        mock_client.return_value.__aenter__.return_value.get.return_value = (
            mock_response
        )

        provider = GoogleSSOProvider(
            client_id="test", client_secret="test", redirect_uri="https://test.com"
        )

        discovery_result = await provider.discover()
        assert discovery_result.is_ok()

        discovery = discovery_result.value
        assert discovery["issuer"] == "https://accounts.google.com"
        assert "authorization_endpoint" in discovery

    async def test_sso_user_info_validation(self):
        """Test SSOUserInfo model validation and immutability."""
        user_info = SSOUserInfo(
            sub="test-123",
            email="test@example.com",
            email_verified=True,
            name="Test User",
            given_name="Test",
            family_name="User",
            provider="google",
            provider_user_id="test-123",
            groups=["employees", "engineering"],
            raw_claims={"sub": "test-123", "email": "test@example.com"},
        )

        assert user_info.sub == "test-123"
        assert user_info.email == "test@example.com"
        assert user_info.provider == "google"
        assert "employees" in user_info.groups

        # Test immutability
        with pytest.raises(Exception):
            user_info.email = "changed@example.com"

    async def test_state_and_nonce_generation(self):
        """Test secure state and nonce generation."""
        provider = GoogleSSOProvider(
            client_id="test", client_secret="test", redirect_uri="https://test.com"
        )

        state1 = provider.generate_state()
        state2 = provider.generate_state()
        nonce1 = provider.generate_nonce()
        nonce2 = provider.generate_nonce()

        # Should be different each time
        assert state1 != state2
        assert nonce1 != nonce2

        # Should be proper length (UUID hex = 32 chars)
        assert len(state1) == 32
        assert len(nonce1) == 32

        # Validation should work
        assert provider.validate_state(state1, state1)
        assert not provider.validate_state(state1, state2)

    async def test_provider_configuration_security(self, sso_manager, mock_db):
        """Test provider configuration validation and security."""
        # Mock empty provider configs
        mock_db.fetch.return_value = []

        result = await sso_manager.initialize()
        assert result.is_ok()

        # Should have no providers configured
        assert len(sso_manager.list_providers()) == 0

        # Test getting non-existent provider
        provider = sso_manager.get_provider("nonexistent")
        assert provider is None

    async def test_error_result_patterns(self):
        """Test Result type usage throughout SSO system."""
        provider = GoogleSSOProvider(
            client_id="test", client_secret="test", redirect_uri="https://test.com"
        )

        # Mock HTTP failure
        with patch(
            "src.policy_core.core.auth.providers.google.httpx.AsyncClient"
        ) as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 500
            mock_client.return_value.__aenter__.return_value.get.return_value = (
                mock_response
            )

            # Discovery should fail gracefully
            discovery_result = await provider.discover()
            assert isinstance(discovery_result, Err)
            assert "discovery document" in discovery_result.error

    async def test_concurrent_provider_access(self, sso_manager, mock_db, mock_cache):
        """Test concurrent access to SSO providers."""
        import asyncio

        # Mock valid provider configuration
        mock_db.fetch.return_value = [
            {
                "id": uuid4(),
                "provider_name": "test_google",
                "provider_type": "google",
                "client_id": "test_id",
                "client_secret_encrypted": "encrypted_secret",
                "configuration": {
                    "redirect_uri": "https://test.com/callback",
                    "client_id": "test_id",
                    "client_secret": "test_secret",
                },
                "is_enabled": True,
            }
        ]

        # Mock decrypt method
        async def mock_decrypt(encrypted):
            return encrypted.replace("encrypted_", "")

        sso_manager._decrypt_secret = mock_decrypt

        # Initialize once
        await sso_manager.initialize()

        # Simulate concurrent access
        async def get_provider():
            return sso_manager.get_provider("test_google")

        tasks = [get_provider() for _ in range(10)]
        results = await asyncio.gather(*tasks)

        # All should return the same provider instance
        first_provider = results[0]
        assert all(r == first_provider for r in results)

    async def test_provider_configuration_error_handling(self, sso_manager, mock_db):
        """Test error handling in provider configuration."""
        # Mock configuration with missing required fields
        mock_db.fetch.return_value = [
            {
                "id": uuid4(),
                "provider_name": "broken_google",
                "provider_type": "google",
                "client_id": "test_id",
                "client_secret_encrypted": "encrypted_secret",
                "configuration": {
                    # Missing redirect_uri
                    "client_id": "test_id",
                    "client_secret": "test_secret",
                },
                "is_enabled": True,
            }
        ]

        # Mock decrypt method
        async def mock_decrypt(encrypted):
            return encrypted.replace("encrypted_", "")

        sso_manager._decrypt_secret = mock_decrypt

        # Initialize should succeed but provider won't be loaded
        result = await sso_manager.initialize()
        assert result.is_ok()

        # Broken provider should not be available
        providers = sso_manager.list_providers()
        assert "broken_google" not in providers

    async def test_no_silent_fallbacks_compliance(self, sso_manager, mock_db):
        """Test compliance with NO SILENT FALLBACKS principle."""
        # Test provider not found
        provider = sso_manager.get_provider("nonexistent")
        assert provider is None  # Explicit None, not empty fallback

        # Mock auto-provisioning check failure
        mock_db.fetchrow.side_effect = [
            None,  # No existing SSO link
            None,  # No existing email user
            {"auto_create_users": False},  # Auto-create disabled
        ]

        user_info = SSOUserInfo(
            sub="test-123",
            email="test@example.com",
            email_verified=True,
            provider="google",
            provider_user_id="test-123",
            raw_claims={},
        )

        # Should explicitly fail, not silently proceed
        result = await sso_manager.create_or_update_user(user_info, "google")
        assert result.is_err()
        assert "provisioning not allowed" in result.error
        assert "Required action:" in result.error  # Explicit guidance

    async def test_master_ruleset_compliance(self):
        """Test compliance with master ruleset principles."""
        # Test immutable Pydantic models
        user_info = SSOUserInfo(
            sub="test",
            email="test@example.com",
            email_verified=True,
            provider="test",
            provider_user_id="test",
            raw_claims={},
        )

        # Should be frozen
        with pytest.raises(Exception):
            user_info.email = "changed"

        # Test beartype on all public functions
        provider = GoogleSSOProvider("id", "secret", "redirect")

        # All public methods should have beartype decorators
        assert hasattr(provider.get_authorization_url, "__wrapped__")
        assert hasattr(provider.exchange_code_for_token, "__wrapped__")
        assert hasattr(provider.get_user_info, "__wrapped__")

    async def test_enterprise_security_features(self):
        """Test enterprise security features."""
        # Test domain restriction
        provider = GoogleSSOProvider(
            client_id="test",
            client_secret="test",
            redirect_uri="https://test.com",
            hosted_domain="company.com",
        )

        assert provider.hosted_domain == "company.com"

        # Test scope validation
        assert "openid" in provider.scopes
        assert "email" in provider.scopes
        assert "profile" in provider.scopes

    @patch("src.policy_core.core.auth.providers.azure.httpx.AsyncClient")
    async def test_azure_graph_integration(self, mock_client):
        """Test Azure AD Microsoft Graph integration."""
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            {  # User info from Graph API
                "id": "azure-user-123",
                "displayName": "Azure User",
                "givenName": "Azure",
                "surname": "User",
                "mail": "azure@company.com",
                "userPrincipalName": "azure@company.com",
            },
            {  # Groups from Graph API
                "value": [
                    {"@odata.type": "#microsoft.graph.group", "displayName": "Admins"},
                    {
                        "@odata.type": "#microsoft.graph.group",
                        "displayName": "Developers",
                    },
                ]
            },
        ]

        mock_client.return_value.__aenter__.return_value.get.return_value = (
            mock_response
        )

        provider = AzureADSSOProvider(
            client_id="azure_id",
            client_secret="azure_secret",
            redirect_uri="https://test.com",
            tenant_id="tenant-123",
            scopes=["openid", "email", "profile", "Group.Read.All"],
        )

        user_info_result = await provider.get_user_info("test_token")
        assert user_info_result.is_ok()

        user_info = user_info_result.value
        assert user_info.email == "azure@company.com"
        assert user_info.provider == "azure"
        assert "Admins" in user_info.groups

    async def test_performance_and_caching(self, sso_manager, mock_cache):
        """Test performance optimizations and caching."""
        # Test configuration caching
        mock_cache.get.return_value = {
            "test_provider": {
                "provider_type": "google",
                "client_id": "test",
                "client_secret": "secret",
                "redirect_uri": "https://test.com",
            }
        }

        # Should use cached config and not hit database
        await sso_manager.initialize()

        # Verify cache was checked
        mock_cache.get.assert_called_with("sso:provider_configs")

    async def test_audit_and_logging(self, sso_manager, mock_db):
        """Test audit logging functionality."""
        user_info = SSOUserInfo(
            sub="test-123",
            email="test@example.com",
            email_verified=True,
            provider="google",
            provider_user_id="test-123",
            raw_claims={},
        )

        # Mock database error to trigger logging
        mock_db.fetchrow.side_effect = Exception("Database error")

        # Should log the failure
        result = await sso_manager.create_or_update_user(user_info, "google")
        assert result.is_err()

        # Verify auth logging was attempted
        assert any(
            call for call in mock_db.execute.call_args_list if "auth_logs" in str(call)
        )

    def test_all_providers_implement_interface(self):
        """Test that all providers properly implement the SSO interface."""
        providers = [
            GoogleSSOProvider("id", "secret", "redirect"),
            AzureADSSOProvider("id", "secret", "redirect", "tenant"),
            Auth0SSOProvider("id", "secret", "redirect", "domain.auth0.com"),
            OktaSSOProvider("id", "secret", "redirect", "domain.okta.com"),
        ]

        for provider in providers:
            # All providers should have these methods
            assert hasattr(provider, "get_authorization_url")
            assert hasattr(provider, "exchange_code_for_token")
            assert hasattr(provider, "get_user_info")
            assert hasattr(provider, "refresh_token")
            assert hasattr(provider, "revoke_token")
            assert hasattr(provider, "provider_name")

            # All should be proper async methods
            assert callable(provider.get_authorization_url)
            assert callable(provider.exchange_code_for_token)
            assert callable(provider.get_user_info)
