#!/usr/bin/env python3
"""Simple SSO test without complex dependencies."""

import os
import sys

# Add the src directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

# ---------------------------------------------------------------------------
# Logging Setup (replaces all legacy ``print`` output with proper logging)
# ---------------------------------------------------------------------------
from policy_core.core.logging_utils import configure_logging, patch_print

configure_logging()
patch_print()


# Test the basic SSO classes directly
def test_sso_base_classes():
    """Test SSO base classes can be imported and instantiated."""
    print("🔍 Testing SSO Base Classes...")

    try:
        # Test SSOUserInfo model
        from policy_core.core.auth.sso_base import SSOUserInfo

        user_info = SSOUserInfo(
            sub="test-123",
            email="test@example.com",
            email_verified=True,
            provider="google",
            provider_user_id="google-123",
        )

        print(f"✅ SSOUserInfo created: {user_info.email}")
        print(f"✅ Model is frozen: {user_info.__frozen__}")

        return True

    except Exception as e:
        print(f"❌ SSOUserInfo test failed: {e}")
        return False


def test_google_provider():
    """Test Google SSO provider."""
    print("\n🔍 Testing Google SSO Provider...")

    try:
        from policy_core.core.auth.providers.google import GoogleSSOProvider

        provider = GoogleSSOProvider(
            client_id="test-client-id",
            client_secret="test-secret",
            redirect_uri="http://localhost:8000/callback",
        )

        print(f"✅ Google provider created: {provider.provider_name}")
        print(f"✅ Client ID: {provider.client_id}")
        print(f"✅ Issuer: {provider.issuer}")

        # Test state generation
        state = provider.generate_state()
        nonce = provider.generate_nonce()

        print(f"✅ State generated: {state[:8]}...")
        print(f"✅ Nonce generated: {nonce[:8]}...")

        return True

    except Exception as e:
        print(f"❌ Google provider test failed: {e}")
        return False


def test_all_providers():
    """Test all SSO providers can be instantiated."""
    print("\n🔍 Testing All SSO Providers...")

    providers_config = [
        (
            "Google",
            "policy_core.core.auth.providers.google",
            "GoogleSSOProvider",
            {
                "client_id": "test-id",
                "client_secret": "test-secret",
                "redirect_uri": "http://localhost:8000/callback",
            },
        ),
        (
            "Azure AD",
            "policy_core.core.auth.providers.azure",
            "AzureADSSOProvider",
            {
                "client_id": "test-id",
                "client_secret": "test-secret",
                "redirect_uri": "http://localhost:8000/callback",
                "tenant_id": "test-tenant",
            },
        ),
        (
            "Okta",
            "policy_core.core.auth.providers.okta",
            "OktaSSOProvider",
            {
                "client_id": "test-id",
                "client_secret": "test-secret",
                "redirect_uri": "http://localhost:8000/callback",
                "okta_domain": "dev-12345.okta.com",
            },
        ),
        (
            "Auth0",
            "policy_core.core.auth.providers.auth0",
            "Auth0SSOProvider",
            {
                "client_id": "test-id",
                "client_secret": "test-secret",
                "redirect_uri": "http://localhost:8000/callback",
                "auth0_domain": "test.auth0.com",
            },
        ),
    ]

    success_count = 0

    for name, module_path, class_name, config in providers_config:
        try:
            module = __import__(module_path, fromlist=[class_name])
            provider_class = getattr(module, class_name)
            provider = provider_class(**config)

            print(f"✅ {name} provider: {provider.provider_name}")
            success_count += 1

        except Exception as e:
            print(f"❌ {name} provider failed: {e}")

    print(
        f"\n📊 Provider Test Results: {success_count}/{len(providers_config)} successful"
    )
    return success_count == len(providers_config)


def test_result_types():
    """Test Result type patterns."""
    print("\n🔍 Testing Result Type Patterns...")

    try:
        from policy_core.core.result_types import Err, Ok, Result

        # Test Ok result
        success = Ok("success value")
        assert success.is_ok() is True
        assert success.is_err() is False
        assert success.value == "success value"

        # Test Err result
        error = Err("error message")
        assert error.is_ok() is False
        assert error.is_err() is True
        assert error.error == "error message"

        print("✅ Ok result type working")
        print("✅ Err result type working")
        print("✅ Result patterns properly implemented")

        return True

    except Exception as e:
        print(f"❌ Result type test failed: {e}")
        return False


def main():
    """Run all SSO tests."""
    print("🚀 SSO Integration Test Suite")
    print("=" * 40)

    tests = [
        test_sso_base_classes,
        test_google_provider,
        test_all_providers,
        test_result_types,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} crashed: {e}")
            results.append(False)

    print("\n" + "=" * 40)
    print(f"📊 Test Summary: {sum(results)}/{len(results)} tests passed")

    if all(results):
        print("🎉 All SSO tests passed! Implementation is working correctly.")
        return 0
    else:
        print("⚠️  Some SSO tests failed. Check implementation.")
        return 1


if __name__ == "__main__":
    exit(main())
