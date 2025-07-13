#!/usr/bin/env python3
"""Setup test SSO providers for development and testing.

This script creates test SSO provider configurations in the database
to enable full SSO functionality testing.
"""

import asyncio
import json
from uuid import uuid4

import asyncpg
from beartype import beartype

from src.pd_prime_demo.core.config import get_settings


@beartype
async def setup_test_providers() -> None:
    """Set up test SSO provider configurations."""
    settings = get_settings()

    # Connect to database
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )

    try:
        # Check if providers already exist
        existing = await conn.fetchval("SELECT COUNT(*) FROM sso_provider_configs")

        if existing > 0:
            print(f"Found {existing} existing SSO providers, skipping setup")
            return

        # Test provider configurations
        providers = [
            {
                "provider_name": "google",
                "provider_type": "oidc",
                "configuration": {
                    "client_id": "test-google-client-id",
                    "client_secret": "test-google-client-secret",
                    "redirect_uri": "http://localhost:8000/auth/sso/google/callback",
                    "hosted_domain": None,
                    "scopes": ["openid", "email", "profile"],
                },
                "is_enabled": True,
                "auto_create_users": True,
                "allowed_domains": ["example.com", "testcorp.com"],
                "default_role": "agent",
            },
            {
                "provider_name": "azure",
                "provider_type": "oidc",
                "configuration": {
                    "client_id": "test-azure-client-id",
                    "client_secret": "test-azure-client-secret",
                    "redirect_uri": "http://localhost:8000/auth/sso/azure/callback",
                    "tenant_id": "test-tenant-id",
                    "scopes": ["openid", "email", "profile", "User.Read"],
                },
                "is_enabled": True,
                "auto_create_users": True,
                "allowed_domains": None,
                "default_role": "agent",
            },
            {
                "provider_name": "okta",
                "provider_type": "oidc",
                "configuration": {
                    "client_id": "test-okta-client-id",
                    "client_secret": "test-okta-client-secret",
                    "redirect_uri": "http://localhost:8000/auth/sso/okta/callback",
                    "okta_domain": "dev-12345.okta.com",
                    "authorization_server_id": "default",
                    "scopes": ["openid", "email", "profile", "groups"],
                },
                "is_enabled": True,
                "auto_create_users": True,
                "allowed_domains": None,
                "default_role": "agent",
            },
            {
                "provider_name": "auth0",
                "provider_type": "oidc",
                "configuration": {
                    "client_id": "test-auth0-client-id",
                    "client_secret": "test-auth0-client-secret",
                    "redirect_uri": "http://localhost:8000/auth/sso/auth0/callback",
                    "auth0_domain": "test-domain.auth0.com",
                    "audience": None,
                    "scopes": ["openid", "email", "profile"],
                },
                "is_enabled": True,
                "auto_create_users": True,
                "allowed_domains": None,
                "default_role": "agent",
            },
        ]

        # Insert providers
        for provider in providers:
            provider_id = uuid4()

            await conn.execute(
                """
                INSERT INTO sso_provider_configs (
                    id, provider_name, provider_type, configuration,
                    is_enabled, auto_create_users, allowed_domains, default_role,
                    created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """,
                provider_id,
                provider["provider_name"],
                provider["provider_type"],
                json.dumps(provider["configuration"]),
                provider["is_enabled"],
                provider["auto_create_users"],
                provider["allowed_domains"],
                provider["default_role"],
            )

            print(
                f"✅ Created SSO provider: {provider['provider_name']} ({provider_id})"
            )

            # Add sample group mappings for each provider
            if provider["provider_name"] == "google":
                await conn.execute(
                    """
                    INSERT INTO sso_group_mappings (
                        id, provider_id, sso_group_name, internal_role, auto_assign, created_at
                    ) VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
                    """,
                    uuid4(),
                    provider_id,
                    "admins@testcorp.com",
                    "admin",
                    True,
                )
                await conn.execute(
                    """
                    INSERT INTO sso_group_mappings (
                        id, provider_id, sso_group_name, internal_role, auto_assign, created_at
                    ) VALUES ($1, $2, $3, $4, $5, CURRENT_TIMESTAMP)
                    """,
                    uuid4(),
                    provider_id,
                    "underwriters@testcorp.com",
                    "underwriter",
                    True,
                )

        print(f"\n🎉 Successfully created {len(providers)} test SSO providers!")
        print("You can now test SSO authentication flows with these providers.")
        print("\nTest URLs:")
        for provider in providers:
            print(
                f"  {provider['provider_name']}: /auth/sso/{provider['provider_name']}/initiate"
            )

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(setup_test_providers())
