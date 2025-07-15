#!/usr/bin/env python3
"""Configure external integrations: VIN decoder and SSO providers.

This script:
1. Checks current SSO provider status
2. Creates configuration for VIN decoder (placeholder for now)
3. Enables and configures SSO providers with demo/test credentials
"""

import asyncio
import sys
from pathlib import Path

# Add project root and src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from policy_core.core.database import Database
from policy_core.core.config import get_settings
from policy_core.core.result_types import Ok, Err


async def check_current_sso_status(db: Database) -> None:
    """Check current SSO provider configuration."""
    print("\n📋 Current SSO Provider Status:")
    print("=" * 60)
    
    # Check if SSO tables exist
    table_exists = await db.fetchval("""
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_name = 'sso_provider_configs'
        )
    """)
    
    if not table_exists:
        print("  ⚠️  SSO tables not found. Please run the SQL migration: migrations/001_create_sso_tables.sql")
        return
    
    providers = await db.fetch("""
        SELECT provider_name as provider, provider_type, is_enabled, auto_create_users as auto_provision, allowed_domains as domain_whitelist
        FROM sso_provider_configs 
        ORDER BY provider_name
    """)
    
    for p in providers:
        status = "✅ Enabled" if p["is_enabled"] else "❌ Disabled"
        auto = "✓" if p["auto_provision"] else "✗"
        domains = p.get("domain_whitelist", []) or []
        domain_str = f" (domains: {', '.join(domains)})" if domains else ""
        
        print(f"  {p['provider']:10} - {p['provider_type']:20} {status} | Auto-provision: {auto}{domain_str}")


async def configure_vin_decoder(db: Database) -> None:
    """Configure VIN decoder settings (placeholder for now)."""
    print("\n🚗 VIN Decoder Configuration:")
    print("=" * 60)
    
    # Check current settings
    settings = get_settings()
    
    if settings.vin_api_key and settings.vin_api_endpoint:
        print(f"  ✅ VIN API Key: {'*' * 8}{settings.vin_api_key[-4:]}")
        print(f"  ✅ VIN API Endpoint: {settings.vin_api_endpoint}")
    else:
        print("  ⚠️  VIN decoder not configured")
        print("  ℹ️  To configure, set environment variables:")
        print("     - VIN_API_KEY")
        print("     - VIN_API_ENDPOINT")
        print("\n  📝 Supported VIN decoder services:")
        print("     - NHTSA VIN Decoder API (free, limited)")
        print("     - Polk Vehicle Data API (commercial)")
        print("     - Experian AutoCheck API (commercial)")


async def enable_demo_sso_providers(db: Database) -> None:
    """Enable SSO providers with demo/test configuration."""
    print("\n🔐 Configuring SSO Providers:")
    print("=" * 60)
    
    # Google OAuth configuration
    print("\n  📌 Google OAuth:")
    result = await db.execute("""
        UPDATE sso_provider_configs 
        SET 
            is_enabled = true,
            client_id = 'demo-google-client-id.apps.googleusercontent.com',
            client_secret_encrypted = 'demo-google-client-secret-encrypted',
            configuration = jsonb_build_object(
                'issuer', 'https://accounts.google.com',
                'authorization_endpoint', 'https://accounts.google.com/o/oauth2/v2/auth',
                'token_endpoint', 'https://oauth2.googleapis.com/token',
                'userinfo_endpoint', 'https://openidconnect.googleapis.com/v1/userinfo',
                'scopes', ARRAY['openid', 'email', 'profile'],
                'redirect_uri', 'http://localhost:8000/auth/sso/callback',
                'hosted_domain', 'example.com'
            ),
            allowed_domains = ARRAY['example.com'],
            auto_create_users = true,
            updated_at = CURRENT_TIMESTAMP
        WHERE provider_name = 'google'
    """)
    print(f"     ✅ Enabled with demo credentials (domain: example.com)")
    
    # Azure AD configuration
    print("\n  📌 Azure AD:")
    result = await db.execute("""
        UPDATE sso_provider_configs 
        SET 
            is_enabled = true,
            client_id = 'demo-azure-ad-client-id',
            client_secret = 'demo-azure-ad-client-secret',
            issuer = 'https://login.microsoftonline.com/demo-tenant-id/v2.0',
            authorization_endpoint = 'https://login.microsoftonline.com/demo-tenant-id/oauth2/v2.0/authorize',
            token_endpoint = 'https://login.microsoftonline.com/demo-tenant-id/oauth2/v2.0/token',
            userinfo_endpoint = 'https://graph.microsoft.com/v1.0/me',
            scopes = ARRAY['openid', 'email', 'profile', 'User.Read'],
            domain_whitelist = ARRAY['contoso.com'],
            auto_provision = true,
            config = jsonb_build_object('tenant_id', 'demo-tenant-id'),
            updated_at = CURRENT_TIMESTAMP
        WHERE provider = 'azure'
    """)
    print(f"     ✅ Enabled with demo credentials (domain: contoso.com)")
    
    # Okta configuration
    print("\n  📌 Okta:")
    result = await db.execute("""
        UPDATE sso_provider_configs 
        SET 
            is_enabled = true,
            client_id = 'demo-okta-client-id',
            client_secret = 'demo-okta-client-secret',
            issuer = 'https://demo.okta.com/oauth2/default',
            authorization_endpoint = 'https://demo.okta.com/oauth2/default/v1/authorize',
            token_endpoint = 'https://demo.okta.com/oauth2/default/v1/token',
            userinfo_endpoint = 'https://demo.okta.com/oauth2/default/v1/userinfo',
            scopes = ARRAY['openid', 'email', 'profile', 'groups'],
            domain_whitelist = ARRAY['oktademo.com'],
            auto_provision = true,
            config = jsonb_build_object('okta_domain', 'demo.okta.com'),
            updated_at = CURRENT_TIMESTAMP
        WHERE provider = 'okta'
    """)
    print(f"     ✅ Enabled with demo credentials (domain: oktademo.com)")
    
    # Auth0 configuration
    print("\n  📌 Auth0:")
    result = await db.execute("""
        UPDATE sso_provider_configs 
        SET 
            is_enabled = false,  -- Keep disabled by default
            client_id = 'demo-auth0-client-id',
            client_secret = 'demo-auth0-client-secret',
            issuer = 'https://demo.auth0.com/',
            authorization_endpoint = 'https://demo.auth0.com/authorize',
            token_endpoint = 'https://demo.auth0.com/oauth/token',
            userinfo_endpoint = 'https://demo.auth0.com/userinfo',
            scopes = ARRAY['openid', 'email', 'profile'],
            auto_provision = false,
            config = jsonb_build_object('domain', 'demo.auth0.com'),
            updated_at = CURRENT_TIMESTAMP
        WHERE provider = 'auth0'
    """)
    print(f"     ℹ️  Configured but kept disabled")


async def create_sso_group_mappings(db: Database) -> None:
    """Create default SSO group mappings."""
    print("\n👥 Creating SSO Group Mappings:")
    print("=" * 60)
    
    # Clear existing mappings
    await db.execute("DELETE FROM sso_group_mappings")
    
    # Google Workspace groups
    await db.execute("""
        INSERT INTO sso_group_mappings (provider, external_group, local_role, priority)
        VALUES 
            ('google', 'admins@example.com', 'admin', 100),
            ('google', 'underwriters@example.com', 'underwriter', 50),
            ('google', 'agents@example.com', 'agent', 25),
            ('google', 'users@example.com', 'customer', 10)
    """)
    print("  ✅ Google Workspace group mappings created")
    
    # Azure AD groups
    await db.execute("""
        INSERT INTO sso_group_mappings (provider, external_group, local_role, priority)
        VALUES 
            ('azure', 'Insurance-Admins', 'admin', 100),
            ('azure', 'Insurance-Underwriters', 'underwriter', 50),
            ('azure', 'Insurance-Agents', 'agent', 25),
            ('azure', 'All-Users', 'customer', 10)
    """)
    print("  ✅ Azure AD group mappings created")
    
    # Okta groups
    await db.execute("""
        INSERT INTO sso_group_mappings (provider, external_group, local_role, priority)
        VALUES 
            ('okta', 'insurance-admins', 'admin', 100),
            ('okta', 'insurance-underwriters', 'underwriter', 50),
            ('okta', 'insurance-agents', 'agent', 25),
            ('okta', 'everyone', 'customer', 10)
    """)
    print("  ✅ Okta group mappings created")


async def verify_configuration(db: Database) -> None:
    """Verify the configuration is working."""
    print("\n✅ Configuration Summary:")
    print("=" * 60)
    
    # Check enabled SSO providers
    enabled = await db.fetch("""
        SELECT provider, display_name, domain_whitelist
        FROM sso_providers 
        WHERE is_enabled = true
        ORDER BY provider
    """)
    
    print(f"\n  Enabled SSO Providers: {len(enabled)}")
    for p in enabled:
        domains = p.get("domain_whitelist", []) or []
        print(f"    - {p['display_name']} ({p['provider']}): {', '.join(domains)}")
    
    # Check group mappings
    mappings = await db.fetchval("""
        SELECT COUNT(*) FROM sso_group_mappings
    """)
    print(f"\n  SSO Group Mappings: {mappings}")
    
    # Check VIN decoder
    settings = get_settings()
    vin_status = "✅ Configured" if settings.vin_api_key else "⚠️ Not configured"
    print(f"\n  VIN Decoder: {vin_status}")
    
    print("\n🎉 External integrations configuration complete!")
    print("\nℹ️  Note: These are DEMO credentials for development/testing.")
    print("   For production, update with real OAuth credentials via admin API.")


async def main():
    """Main configuration function."""
    print("🚀 Configuring External Integrations")
    print("=" * 60)
    
    settings = get_settings()
    print(f"Settings type: {type(settings)}")
    db = Database()  # Don't pass settings - it gets them internally
    print(f"Database instance type: {type(db)}")
    
    try:
        await db.connect()
        print("Database connected successfully")
        
        # Show current status
        await check_current_sso_status(db)
        
        # Configure integrations
        await configure_vin_decoder(db)
        await enable_demo_sso_providers(db)
        await create_sso_group_mappings(db)
        
        # Verify configuration
        await verify_configuration(db)
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(main())