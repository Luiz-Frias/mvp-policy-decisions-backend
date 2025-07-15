#!/usr/bin/env python3
"""Populate SSO tables with demo data.

This script populates the sso_providers table with demo SSO provider configurations.
"""

import asyncio
import sys
from pathlib import Path
from uuid import uuid4

# Add project root and src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from policy_core.core.database import Database
from policy_core.core.config import get_settings


async def populate_sso_providers():
    """Populate SSO providers table with demo data."""
    db = Database()
    
    try:
        await db.connect()
        print("🔥 Connected to database")
        
        # Check if data already exists
        count = await db.fetchval("SELECT COUNT(*) FROM sso_providers")
        if count > 0:
            print(f"⚠️  Found {count} existing SSO providers, skipping population")
            return
        
        print("\n📋 Populating SSO providers...")
        
        # Demo providers to insert
        providers = [
            {
                "id": uuid4(),
                "provider_name": "google",
                "provider_type": "oidc", 
                "client_id": "demo-google-client-id.apps.googleusercontent.com",
                "client_secret_encrypted": "demo-google-secret-encrypted",
                "issuer_url": "https://accounts.google.com",
                "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_url": "https://oauth2.googleapis.com/token",
                "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
                "enabled": True,
                "auto_create_users": True,
                "allowed_domains": '["example.com", "test.com"]'
            },
            {
                "id": uuid4(),
                "provider_name": "azure",
                "provider_type": "oidc",
                "client_id": "demo-azure-client-id",
                "client_secret_encrypted": "demo-azure-secret-encrypted", 
                "issuer_url": "https://login.microsoftonline.com/demo-tenant/v2.0",
                "authorize_url": "https://login.microsoftonline.com/demo-tenant/oauth2/v2.0/authorize",
                "token_url": "https://login.microsoftonline.com/demo-tenant/oauth2/v2.0/token",
                "userinfo_url": "https://graph.microsoft.com/v1.0/me",
                "enabled": True,
                "auto_create_users": True,
                "allowed_domains": '["contoso.com", "microsoft.com"]'
            },
            {
                "id": uuid4(),
                "provider_name": "okta",
                "provider_type": "oidc",
                "client_id": "demo-okta-client-id",
                "client_secret_encrypted": "demo-okta-secret-encrypted",
                "issuer_url": "https://demo.okta.com/oauth2/default", 
                "authorize_url": "https://demo.okta.com/oauth2/default/v1/authorize",
                "token_url": "https://demo.okta.com/oauth2/default/v1/token",
                "userinfo_url": "https://demo.okta.com/oauth2/default/v1/userinfo",
                "enabled": False,  # Disabled by default
                "auto_create_users": True,
                "allowed_domains": '["oktademo.com"]'
            }
        ]
        
        # Insert providers
        for provider in providers:
            await db.execute("""
                INSERT INTO sso_providers (
                    id, provider_name, provider_type,
                    client_id, client_secret_encrypted,
                    issuer_url, authorize_url, token_url, userinfo_url,
                    enabled, auto_create_users, allowed_domains,
                    created_at, updated_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, 
                    $12::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                )
            """, 
                provider["id"],
                provider["provider_name"],
                provider["provider_type"],
                provider["client_id"],
                provider["client_secret_encrypted"],
                provider["issuer_url"],
                provider["authorize_url"],
                provider["token_url"],
                provider["userinfo_url"],
                provider["enabled"],
                provider["auto_create_users"],
                provider["allowed_domains"]
            )
            
            status = "✅ Enabled" if provider["enabled"] else "❌ Disabled"
            print(f"  {status} {provider['provider_name']} ({provider['provider_type']})")
        
        print(f"\n✅ Successfully populated {len(providers)} SSO providers")
        
        # Also populate sso_provider_configs if it exists and is empty
        configs_exist = await db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_name = 'sso_provider_configs'
            )
        """)
        
        if configs_exist:
            config_count = await db.fetchval("SELECT COUNT(*) FROM sso_provider_configs")
            if config_count == 0:
                print("\n📋 Also populating sso_provider_configs table...")
                
                # Insert into sso_provider_configs
                for provider in providers[:2]:  # Just Google and Azure
                    await db.execute("""
                        INSERT INTO sso_provider_configs (
                            id, provider_name, provider_type,
                            configuration,
                            is_enabled, auto_create_users, 
                            allowed_domains, default_role,
                            created_at, updated_at
                        ) VALUES (
                            gen_random_uuid(), $1, $2, $3::jsonb,
                            $4, $5, $6, 'agent',
                            CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                        )
                    """,
                        provider["provider_name"],
                        provider["provider_type"],
                        f'{{"client_id": "{provider["client_id"]}", "client_secret": "demo-secret"}}',
                        provider["enabled"],
                        provider["auto_create_users"],
                        ["example.com"] if provider["provider_name"] == "google" else ["contoso.com"]
                    )
                    print(f"  ✅ Added to sso_provider_configs: {provider['provider_name']}")
        
        print("\n🎉 SSO provider configuration complete!")
        print("\nDemo credentials (for development only):")
        print("  Google: demo-google-client-id.apps.googleusercontent.com")
        print("  Azure: demo-azure-client-id") 
        print("  Okta: demo-okta-client-id (disabled)")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(populate_sso_providers())