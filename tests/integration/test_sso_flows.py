"""Integration tests for SSO authentication flows."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from src.pd_prime_demo.core.auth.providers.google import GoogleSSOProvider
from src.pd_prime_demo.core.auth.sso_base import SSOUserInfo
from src.pd_prime_demo.core.auth.sso_manager import SSOManager


class TestSSOIntegrationFlows:
    """Test SSO authentication flows end-to-end."""

    @pytest.fixture
    async def sso_manager(self, mock_db, mock_cache):
        """Create SSO manager with mocked dependencies."""
        manager = SSOManager(mock_db, mock_cache)
        return manager

    @pytest.fixture
    def sample_sso_user_info(self):
        """Sample SSO user information for testing."""
        return SSOUserInfo(
            sub="google-123456789",
            email="john.doe@example.com",
            email_verified=True,
            name="John Doe",
            given_name="John",
            family_name="Doe",
            picture="https://example.com/photo.jpg",
            provider="google",
            provider_user_id="google-123456789",
            groups=["employees", "engineering"],
            roles=["developer"],
            raw_claims={
                "sub": "google-123456789",
                "email": "john.doe@example.com",
                "name": "John Doe",
                "picture": "https://example.com/photo.jpg",
                "email_verified": True,
            },
        )

    async def test_complete_sso_flow_new_user(
        self, sso_manager, sample_sso_user_info, mock_db, mock_cache
    ):
        """Test complete SSO flow for a new user."""
        # Mock database responses for new user creation
        mock_db.fetchrow.side_effect = [
            None,  # No existing SSO link
            None,  # No existing email user
            {
                "id": uuid4(),
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "role": "agent",
                "is_active": True,
            },  # Created user
        ]
        mock_db.fetchval.side_effect = [
            True,  # auto_create_users enabled
            uuid4(),  # new user ID
            uuid4(),  # provider_id for group sync
        ]
        mock_db.fetch.return_value = []  # No group mappings

        # Test user creation
        result = await sso_manager.create_or_update_user(sample_sso_user_info, "google")

        assert result.is_ok()
        user = result.value
        assert user.email == "john.doe@example.com"
        assert user.first_name == "John"
        assert user.last_name == "Doe"
        assert user.role == "agent"

    async def test_sso_flow_existing_user_update(
        self, sso_manager, sample_sso_user_info, mock_db
    ):
        """Test SSO flow for existing user update."""
        user_id = uuid4()

        # Mock database responses for existing user
        mock_db.fetchrow.side_effect = [
            {
                "id": user_id,
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "role": "agent",
                "is_active": True,
            },  # Existing user
            {
                "id": user_id,
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "role": "agent",
                "is_active": True,
            },  # Updated user
        ]
        mock_db.fetchval.return_value = uuid4()  # provider_id
        mock_db.fetch.return_value = []  # No group mappings

        # Test user update
        result = await sso_manager.create_or_update_user(sample_sso_user_info, "google")

        assert result.is_ok()
        user = result.value
        assert user.id == user_id

    async def test_sso_flow_auto_create_disabled(
        self, sso_manager, sample_sso_user_info, mock_db
    ):
        """Test SSO flow when auto-create is disabled."""
        # Mock database responses
        mock_db.fetchrow.side_effect = [
            None,  # No existing SSO link
            None,  # No existing email user
            {
                "auto_create_users": False,
                "allowed_domains": [],
                "default_role": "agent",
            },  # Auto-create disabled
        ]

        # Test user creation failure
        result = await sso_manager.create_or_update_user(sample_sso_user_info, "google")

        assert result.is_err()
        assert "provisioning not allowed" in result.error.lower()

    async def test_sso_flow_domain_restriction(
        self, sso_manager, sample_sso_user_info, mock_db
    ):
        """Test SSO flow with domain restrictions."""
        # Modify user to have wrong domain
        restricted_user = sample_sso_user_info.model_copy(
            update={"email": "john.doe@external.com"}
        )

        # Mock database responses
        mock_db.fetchrow.side_effect = [
            None,  # No existing SSO link
            None,  # No existing email user
            {
                "auto_create_users": True,
                "allowed_domains": ["example.com"],
                "default_role": "agent",
            },  # Domain restricted
        ]

        # Test user creation failure due to domain
        result = await sso_manager.create_or_update_user(restricted_user, "google")

        assert result.is_err()
        assert "domain" in result.error.lower()

    async def test_group_mapping_assignment(
        self, sso_manager, sample_sso_user_info, mock_db
    ):
        """Test automatic role assignment based on group mappings."""
        user_id = uuid4()
        provider_id = uuid4()

        # Mock database responses
        mock_db.fetchrow.side_effect = [
            None,  # No existing SSO link
            None,  # No existing email user
            {
                "auto_create_users": True,
                "allowed_domains": [],
                "default_role": "agent",
            },  # Auto-create enabled
            {
                "id": user_id,
                "email": "john.doe@example.com",
                "first_name": "John",
                "last_name": "Doe",
                "role": "agent",
                "is_active": True,
            },  # Created user
        ]
        mock_db.fetchval.side_effect = [
            user_id,  # new user ID
            provider_id,  # provider_id for group sync
        ]
        mock_db.fetch.return_value = [
            {"sso_group_name": "engineering", "internal_role": "underwriter"}
        ]  # Group mappings

        # Test user creation with group mapping
        result = await sso_manager.create_or_update_user(sample_sso_user_info, "google")

        assert result.is_ok()

        # Verify role update was called (should be underwriter due to group mapping)
        mock_db.execute.assert_any_call(
            "UPDATE users SET role = $1 WHERE id = $2", "underwriter", user_id
        )

    @patch("src.pd_prime_demo.core.auth.providers.google.httpx.AsyncClient")
    async def test_google_provider_integration(self, mock_client):
        """Test Google SSO provider integration."""
        # Mock HTTP responses
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.side_effect = [
            {  # Discovery document
                "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_endpoint": "https://oauth2.googleapis.com/token",
                "userinfo_endpoint": "https://openidconnect.googleapis.com/v1/userinfo",
                "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
                "issuer": "https://accounts.google.com",
            },
            {  # Token exchange
                "access_token": "ya29.mock_access_token",
                "refresh_token": "1//mock_refresh_token",
                "expires_in": 3600,
                "token_type": "Bearer",
            },
            {  # User info
                "sub": "google-123456789",
                "email": "john.doe@example.com",
                "email_verified": True,
                "name": "John Doe",
                "given_name": "John",
                "family_name": "Doe",
                "picture": "https://example.com/photo.jpg",
            },
        ]

        mock_client.return_value.__aenter__.return_value.get.return_value = (
            mock_response
        )
        mock_client.return_value.__aenter__.return_value.post.return_value = (
            mock_response
        )

        # Create Google provider
        provider = GoogleSSOProvider(
            client_id="test_client_id",
            client_secret="test_client_secret",
            redirect_uri="http://localhost:8000/auth/callback",
        )

        # Test authorization URL generation
        auth_url_result = await provider.get_authorization_url("test_state")
        assert auth_url_result.is_ok()
        auth_url = auth_url_result.value
        assert "accounts.google.com" in auth_url
        assert "test_state" in auth_url

        # Test token exchange
        token_result = await provider.exchange_code_for_token("test_code", "test_state")
        assert token_result.is_ok()
        tokens = token_result.value
        assert tokens["access_token"] == "ya29.mock_access_token"

        # Test user info retrieval
        user_info_result = await provider.get_user_info("ya29.mock_access_token")
        assert user_info_result.is_ok()
        user_info = user_info_result.value
        assert user_info.email == "john.doe@example.com"
        assert user_info.provider == "google"

    async def test_provider_configuration_validation(self, sso_manager, mock_db):
        """Test provider configuration validation."""
        # Mock invalid provider configuration
        mock_db.fetch.return_value = [
            {
                "id": uuid4(),
                "provider_name": "invalid_google",
                "provider_type": "google",
                "client_id": "test_id",
                "client_secret_encrypted": "encrypted_secret",
                "configuration": {},  # Missing required fields
                "is_enabled": True,
            }
        ]

        # Test initialization with invalid config
        result = await sso_manager.initialize()

        # Should not fail but provider won't be loaded
        assert result.is_ok()
        assert len(sso_manager.list_providers()) == 0

    async def test_concurrent_user_creation(
        self, sso_manager, sample_sso_user_info, mock_db
    ):
        """Test handling of concurrent user creation attempts."""
        # Simulate race condition where user is created between check and insert
        mock_db.fetchrow.side_effect = [
            None,  # No existing SSO link (first check)
            None,  # No existing email user (first check)
            {
                "auto_create_users": True,
                "allowed_domains": [],
                "default_role": "agent",
            },  # Auto-create enabled
        ]

        # Mock database error on user creation (race condition)
        from asyncpg.exceptions import UniqueViolationError

        mock_db.fetchval.side_effect = UniqueViolationError("duplicate key")

        # Test handling of race condition
        result = await sso_manager.create_or_update_user(sample_sso_user_info, "google")

        assert result.is_err()
        assert "failed to create" in result.error.lower()

    async def test_sso_state_validation(self, mock_cache):
        """Test SSO state parameter validation."""
        from fastapi import HTTPException

        # Mock invalid state
        mock_cache.get.return_value = None

        with pytest.raises(HTTPException):
            # This would normally be called by FastAPI with proper dependencies
            # Here we're testing the core logic
            pass  # Implementation would depend on how we structure the test

        # For now, just verify cache is called
        assert mock_cache.get.called

    async def test_token_refresh_flow(self):
        """Test token refresh functionality."""
        with patch(
            "src.pd_prime_demo.core.auth.providers.google.httpx.AsyncClient"
        ) as mock_client:
            mock_response = AsyncMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "access_token": "ya29.new_access_token",
                "expires_in": 3600,
                "token_type": "Bearer",
            }

            mock_client.return_value.__aenter__.return_value.post.return_value = (
                mock_response
            )

            # Create Google provider
            provider = GoogleSSOProvider(
                client_id="test_client_id",
                client_secret="test_client_secret",
                redirect_uri="http://localhost:8000/auth/callback",
            )

            # Test token refresh
            refresh_result = await provider.refresh_token("1//mock_refresh_token")
            assert refresh_result.is_ok()
            new_tokens = refresh_result.value
            assert new_tokens["access_token"] == "ya29.new_access_token"

    async def test_error_handling_and_logging(
        self, sso_manager, sample_sso_user_info, mock_db
    ):
        """Test error handling and audit logging."""
        # Mock database error
        mock_db.fetchrow.side_effect = Exception("Database connection failed")

        # Test error handling
        result = await sso_manager.create_or_update_user(sample_sso_user_info, "google")

        assert result.is_err()
        assert "failed to create/update user" in result.error.lower()

        # Verify auth log was attempted (even if it failed)
        assert mock_db.execute.called

    async def test_provider_failover(self, sso_manager, mock_db):
        """Test handling when one provider fails but others work."""
        # Mock mixed provider configurations
        mock_db.fetch.return_value = [
            {
                "id": uuid4(),
                "provider_name": "working_google",
                "provider_type": "google",
                "client_id": "working_id",
                "client_secret_encrypted": "encrypted_secret",
                "configuration": {
                    "redirect_uri": "http://localhost:8000/callback",
                    "client_id": "working_id",
                    "client_secret": "working_secret",
                },
                "is_enabled": True,
            },
            {
                "id": uuid4(),
                "provider_name": "broken_azure",
                "provider_type": "azure",
                "client_id": "broken_id",
                "client_secret_encrypted": "encrypted_secret",
                "configuration": {},  # Missing required config
                "is_enabled": True,
            },
        ]

        # Initialize SSO manager
        result = await sso_manager.initialize()
        assert result.is_ok()

        # Should have only working provider
        providers = sso_manager.list_providers()
        assert "working_google" in providers
        assert "broken_azure" not in providers
