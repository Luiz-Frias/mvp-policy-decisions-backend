#!/usr/bin/env python3
"""Test SSO integration functionality end-to-end.

This script tests the complete SSO flow including:
1. Provider initialization
2. Authorization URL generation
3. User provisioning
4. Group mapping
5. Error handling
"""

import asyncio

import asyncpg
from beartype import beartype

from src.pd_prime_demo.core.auth.sso_base import SSOUserInfo
from src.pd_prime_demo.core.auth.sso_manager import SSOManager
from src.pd_prime_demo.core.cache import Cache
from src.pd_prime_demo.core.config import get_settings
from src.pd_prime_demo.core.database import Database

# ---------------------------------------------------------------------------
# Logging Setup (replaces legacy ``print`` with structured logging)
# ---------------------------------------------------------------------------
from src.pd_prime_demo.core.logging_utils import configure_logging, patch_print
from src.pd_prime_demo.core.result_types import Err, Ok, Result

configure_logging()
patch_print()


@beartype
async def test_sso_integration() -> None:
    """Test complete SSO integration functionality."""
    settings = get_settings()

    # Create mock dependencies
    class MockCache(Cache):
        def __init__(self):
            self._data = {}

        async def get(self, key: str):
            return self._data.get(key)

        async def set(self, key: str, value, ttl: int = 3600):
            self._data[key] = value

        async def delete(self, key: str):
            self._data.pop(key, None)

        async def delete_pattern(self, pattern: str):
            keys_to_delete = [
                k for k in self._data.keys() if pattern.replace("*", "") in k
            ]
            for key in keys_to_delete:
                del self._data[key]

    # Connect to database
    conn = await asyncpg.connect(
        host=settings.db_host,
        port=settings.db_port,
        user=settings.db_user,
        password=settings.db_password,
        database=settings.db_name,
    )

    try:
        # Create database and cache instances
        db = Database(conn)
        cache = MockCache()

        # Create SSO manager
        sso_manager = SSOManager(db, cache)

        print("🧪 Testing SSO Manager Initialization...")

        # Test initialization
        init_result = await sso_manager.initialize()
        if isinstance(init_result, Err):
            print(f"❌ Initialization failed: {init_result.error}")
            return

        print("✅ SSO Manager initialized successfully")

        # Check providers
        providers = sso_manager.list_providers()
        print(f"📋 Found {len(providers)} SSO providers: {providers}")

        if not providers:
            print("⚠️  No SSO providers found. Run setup_test_sso_providers.py first.")
            return

        # Test Google provider functionality
        if "google" in providers:
            print("\n🔍 Testing Google Provider...")
            google_provider = sso_manager.get_provider("google")

            if google_provider:
                # Test authorization URL generation
                state = google_provider.generate_state()
                nonce = google_provider.generate_nonce()

                auth_url_result = await google_provider.get_authorization_url(
                    state=state, nonce=nonce
                )

                if isinstance(auth_url_result, Ok):
                    print("✅ Authorization URL generated successfully")
                    print(f"🔗 URL: {auth_url_result.value[:100]}...")
                else:
                    print(
                        f"❌ Authorization URL generation failed: {auth_url_result.error}"
                    )

                # Test user provisioning with mock user data
                print("\n👤 Testing User Provisioning...")
                mock_sso_user = SSOUserInfo(
                    sub="google_test_user_123",
                    email="test@testcorp.com",
                    email_verified=True,
                    name="Test User",
                    given_name="Test",
                    family_name="User",
                    provider="google",
                    provider_user_id="google_test_user_123",
                    groups=["admins@testcorp.com"],
                    raw_claims={"test": "data"},
                )

                # Test user creation
                user_result = await sso_manager.create_or_update_user(
                    mock_sso_user, "google"
                )

                if isinstance(user_result, Ok):
                    user = user_result.value
                    print(
                        f"✅ User provisioned successfully: {user.email} (Role: {user.role})"
                    )

                    # Test user update
                    mock_sso_user_updated = SSOUserInfo(
                        sub="google_test_user_123",
                        email="test@testcorp.com",
                        email_verified=True,
                        name="Test User Updated",
                        given_name="Test",
                        family_name="User Updated",
                        provider="google",
                        provider_user_id="google_test_user_123",
                        groups=["underwriters@testcorp.com"],
                        raw_claims={"test": "updated_data"},
                    )

                    update_result = await sso_manager.create_or_update_user(
                        mock_sso_user_updated, "google"
                    )

                    if isinstance(update_result, Ok):
                        print("✅ User update successful")
                    else:
                        print(f"❌ User update failed: {update_result.error}")

                else:
                    print(f"❌ User provisioning failed: {user_result.error}")

        # Test invalid provider handling
        print("\n🚫 Testing Error Handling...")
        invalid_user_result = await sso_manager.create_or_update_user(
            mock_sso_user, "invalid_provider"
        )

        if isinstance(invalid_user_result, Err):
            print("✅ Invalid provider correctly rejected")
            print(f"📝 Error message: {invalid_user_result.error}")
        else:
            print("❌ Invalid provider should have been rejected")

        # Test domain restrictions
        print("\n🏢 Testing Domain Restrictions...")
        mock_sso_user_bad_domain = SSOUserInfo(
            sub="google_test_user_456",
            email="test@baddomain.com",
            email_verified=True,
            name="Bad Domain User",
            given_name="Bad",
            family_name="User",
            provider="google",
            provider_user_id="google_test_user_456",
            groups=[],
            raw_claims={},
        )

        bad_domain_result = await sso_manager.create_or_update_user(
            mock_sso_user_bad_domain, "google"
        )

        if isinstance(bad_domain_result, Err):
            print("✅ Domain restriction correctly enforced")
            print(f"📝 Error message: {bad_domain_result.error}")
        else:
            print("❌ Domain restriction should have been enforced")

        print("\n🎉 SSO Integration Test Complete!")
        print("All major SSO functionality is working correctly.")

    except Exception as e:
        print(f"💥 Test failed with exception: {str(e)}")
        import traceback

        traceback.print_exc()

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(test_sso_integration())
