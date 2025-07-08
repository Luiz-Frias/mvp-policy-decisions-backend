#!/usr/bin/env python3
"""Validate MFA implementation completeness and functionality."""

import asyncio
import sys
from pathlib import Path
from typing import Any

# Add src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    from pd_prime_demo.core.auth.mfa import RiskEngine, TOTPProvider
    from pd_prime_demo.core.auth.mfa.models import MFAMethod, RiskLevel
except ImportError as e:
    print(f"Import error: {e}")
    print("Please ensure you're running from the project root directory")
    sys.exit(1)


class MFAValidator:
    """Validator for MFA implementation."""

    def __init__(self) -> None:
        """Initialize validator."""
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.success_count = 0
        self.test_count = 0

    def validate_module_imports(self) -> None:
        """Validate that all MFA modules can be imported."""
        print("🔍 Validating module imports...")
        self.test_count += 1

        try:
            # Import all modules to validate they exist - these are intentionally unused
            from pd_prime_demo.core.auth.mfa import (  # noqa: F401
                MFAManager,
                RiskEngine,
                TOTPProvider,
                WebAuthnProvider,
            )
            from pd_prime_demo.core.auth.mfa.models import (  # noqa: F401
                MFAChallenge,
                MFAConfig,
                MFAMethod,
                MFAStatus,
                RiskAssessment,
                RiskLevel,
                TOTPSetupData,
                WebAuthnCredential,
            )

            print("✅ All MFA modules imported successfully")
            self.success_count += 1
        except ImportError as e:
            self.errors.append(f"Failed to import MFA modules: {e}")
            print(f"❌ Import error: {e}")

    def validate_totp_provider(self) -> None:
        """Validate TOTP provider functionality."""
        print("\n🔍 Validating TOTP provider...")
        self.test_count += 1

        try:
            # Mock settings for testing
            class MockSettings:
                secret_key = "test_secret_key_12345678901234567890"
                app_name = "Test App"

            settings = MockSettings()
            totp_provider = TOTPProvider(settings)

            # Test setup generation
            result = totp_provider.generate_setup("test@example.com", "123")
            if result.is_err():
                self.errors.append(f"TOTP setup generation failed: {result.error}")
                return

            setup_data = result.value

            # Validate setup data
            if not setup_data.secret:
                self.errors.append("TOTP secret is empty")
                return

            if not setup_data.qr_code.startswith("data:image/png;base64,"):
                self.errors.append("Invalid QR code format")
                return

            if len(setup_data.backup_codes) != 10:
                self.errors.append(
                    f"Expected 10 backup codes, got {len(setup_data.backup_codes)}"
                )
                return

            # Test encryption/decryption
            encrypt_result = totp_provider.encrypt_secret(setup_data.secret)
            if encrypt_result.is_err():
                self.errors.append(f"TOTP encryption failed: {encrypt_result.error}")
                return

            encrypted = encrypt_result.value
            decrypt_result = totp_provider.decrypt_secret(encrypted)
            if decrypt_result.is_err():
                self.errors.append(f"TOTP decryption failed: {decrypt_result.error}")
                return

            if decrypt_result.value != setup_data.secret:
                self.errors.append("TOTP encryption/decryption mismatch")
                return

            # Test code generation and verification
            code_result = totp_provider.generate_current_code(encrypted)
            if code_result.is_err():
                self.errors.append(f"TOTP code generation failed: {code_result.error}")
                return

            code = code_result.value
            verify_result = totp_provider.verify_code(encrypted, code)
            if verify_result.is_err():
                self.errors.append(f"TOTP verification failed: {verify_result.error}")
                return

            if not verify_result.value:
                self.errors.append("TOTP code verification returned False")
                return

            print("✅ TOTP provider validation passed")
            self.success_count += 1

        except Exception as e:
            self.errors.append(f"TOTP provider validation error: {e}")
            print(f"❌ TOTP provider error: {e}")

    def validate_risk_engine(self) -> None:
        """Validate risk engine functionality."""
        print("\n🔍 Validating risk engine...")
        self.test_count += 1

        try:
            # Mock dependencies
            class MockDB:
                async def fetchrow(self, query, *args):
                    return None

                async def execute(self, query, *args):
                    return None

            class MockCache:
                def __init__(self):
                    self._data: dict[str, Any] = {}

                async def get(self, key):
                    return self._data.get(key)

                async def set(self, key, value, ttl=None):
                    self._data[key] = value

                async def delete(self, key):
                    self._data.pop(key, None)

                async def incr(self, key):
                    current = self._data.get(key, 0)
                    self._data[key] = current + 1
                    return self._data[key]

                async def expire(self, key, ttl):
                    pass

            # Mock settings for testing
            class MockSettings:
                secret_key = "test_secret_key_12345678901234567890"
                app_name = "Test App"

            settings = MockSettings()
            risk_engine = RiskEngine(MockDB(), MockCache(), settings)

            # Test risk assessment
            async def test_assessment():
                result = await risk_engine.assess_risk(
                    "test_user", "192.168.1.1", "Mozilla/5.0", "device123"
                )

                if result.is_err():
                    self.errors.append(f"Risk assessment failed: {result.error}")
                    return False

                assessment = result.value

                # Validate assessment structure
                if not isinstance(assessment.risk_level, RiskLevel):
                    self.errors.append(
                        f"Invalid risk level type: {type(assessment.risk_level)}"
                    )
                    return False

                if not (0 <= assessment.risk_score <= 1.0):
                    self.errors.append(
                        f"Risk score out of range: {assessment.risk_score}"
                    )
                    return False

                if not isinstance(assessment.require_mfa, bool):
                    self.errors.append(
                        f"require_mfa is not boolean: {type(assessment.require_mfa)}"
                    )
                    return False

                if not isinstance(assessment.recommended_methods, list):
                    self.errors.append(
                        f"recommended_methods is not list: {type(assessment.recommended_methods)}"
                    )
                    return False

                return True

            # Run async test
            result = asyncio.run(test_assessment())
            if result:
                print("✅ Risk engine validation passed")
                self.success_count += 1
            else:
                print("❌ Risk engine validation failed")

        except Exception as e:
            self.errors.append(f"Risk engine validation error: {e}")
            print(f"❌ Risk engine error: {e}")

    def validate_models(self) -> None:
        """Validate MFA models."""
        print("\n🔍 Validating MFA models...")
        self.test_count += 1

        try:
            # Test MFA method enum
            methods = [
                MFAMethod.TOTP,
                MFAMethod.WEBAUTHN,
                MFAMethod.SMS,
                MFAMethod.BIOMETRIC,
            ]
            if len(methods) != 4:
                self.errors.append(f"Expected 4 MFA methods, got {len(methods)}")
                return

            # Test risk level enum
            levels = [
                RiskLevel.LOW,
                RiskLevel.MEDIUM,
                RiskLevel.HIGH,
                RiskLevel.CRITICAL,
            ]
            if len(levels) != 4:
                self.errors.append(f"Expected 4 risk levels, got {len(levels)}")
                return

            # Test model creation
            from datetime import datetime, timezone
            from uuid import uuid4

            from pd_prime_demo.core.auth.mfa.models import (
                MFAConfig,
                RiskAssessment,
                TOTPSetupData,
            )

            # Test MFAConfig
            config = MFAConfig(
                user_id=uuid4(),
                totp_enabled=True,
                totp_secret_encrypted="encrypted_secret",
                webauthn_enabled=False,
                webauthn_credentials=[],
                sms_enabled=False,
                sms_phone_encrypted=None,
                recovery_codes_encrypted=[],
                preferred_method=MFAMethod.TOTP,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )

            if not config.totp_enabled:
                self.errors.append("MFAConfig creation failed")
                return

            # Test TOTPSetupData
            setup = TOTPSetupData(
                secret="ABCDEFGHIJKLMNOP",
                qr_code="data:image/png;base64,abc",
                manual_entry_key="ABCD EFGH",
                backup_codes=["12345678"],
            )

            if not setup.secret:
                self.errors.append("TOTPSetupData creation failed")
                return

            # Test RiskAssessment
            assessment = RiskAssessment(
                risk_level=RiskLevel.MEDIUM,
                risk_score=0.5,
                factors={"new_device": 0.8},
                require_mfa=True,
                recommended_methods=[MFAMethod.TOTP],
                reason="New device detected",
            )

            if assessment.risk_level != RiskLevel.MEDIUM:
                self.errors.append("RiskAssessment creation failed")
                return

            print("✅ MFA models validation passed")
            self.success_count += 1

        except Exception as e:
            self.errors.append(f"MFA models validation error: {e}")
            print(f"❌ MFA models error: {e}")

    def validate_api_endpoints(self) -> None:
        """Validate MFA API endpoints exist."""
        print("\n🔍 Validating API endpoints...")
        self.test_count += 1

        try:
            from pd_prime_demo.api.v1.mfa import router

            # Check that router has routes
            if not router.routes:
                self.errors.append("MFA router has no routes")
                return

            # Extract route paths
            route_paths = []
            for route in router.routes:
                if hasattr(route, "path"):
                    route_paths.append(route.path)

            # Expected endpoints
            expected_endpoints = [
                "/status",
                "/totp/setup",
                "/totp/verify-setup",
                "/challenge",
                "/recovery-codes/generate",
                "/device/trust",
                "/risk-assessment",
            ]

            missing_endpoints = []
            for endpoint in expected_endpoints:
                full_path = f"/mfa{endpoint}"
                if not any(full_path in path for path in route_paths):
                    missing_endpoints.append(endpoint)

            if missing_endpoints:
                self.errors.append(f"Missing API endpoints: {missing_endpoints}")
                return

            print("✅ API endpoints validation passed")
            self.success_count += 1

        except Exception as e:
            self.errors.append(f"API endpoints validation error: {e}")
            print(f"❌ API endpoints error: {e}")

    def validate_database_schema(self) -> None:
        """Validate MFA database schema exists."""
        print("\n🔍 Validating database schema...")
        self.test_count += 1

        try:
            # Check migration file exists
            migration_file = (
                Path(__file__).parent.parent
                / "alembic"
                / "versions"
                / "004_add_security_compliance_tables.py"
            )

            if not migration_file.exists():
                self.errors.append("MFA migration file not found")
                return

            # Read migration content
            migration_content = migration_file.read_text()

            # Check for required tables
            required_tables = ["user_mfa_settings", "user_sessions", "oauth2_clients"]

            missing_tables = []
            for table in required_tables:
                if table not in migration_content:
                    missing_tables.append(table)

            if missing_tables:
                self.errors.append(f"Missing database tables: {missing_tables}")
                return

            # Check for MFA-specific columns
            mfa_columns = [
                "totp_enabled",
                "totp_secret_encrypted",
                "webauthn_enabled",
                "webauthn_credentials",
                "sms_enabled",
                "sms_phone_encrypted",
                "recovery_codes_encrypted",
            ]

            missing_columns = []
            for column in mfa_columns:
                if column not in migration_content:
                    missing_columns.append(column)

            if missing_columns:
                self.errors.append(f"Missing MFA columns: {missing_columns}")
                return

            print("✅ Database schema validation passed")
            self.success_count += 1

        except Exception as e:
            self.errors.append(f"Database schema validation error: {e}")
            print(f"❌ Database schema error: {e}")

    def validate_dependencies(self) -> None:
        """Validate required dependencies are available."""
        print("\n🔍 Validating dependencies...")
        self.test_count += 1

        required_packages = [
            "pyotp",
            "qrcode",
            "webauthn",
            "cryptography",
        ]

        missing_packages = []

        for package in required_packages:
            try:
                __import__(package)
            except ImportError:
                missing_packages.append(package)

        if missing_packages:
            self.errors.append(f"Missing required packages: {missing_packages}")
            print(f"❌ Missing packages: {missing_packages}")
            return

        print("✅ Dependencies validation passed")
        self.success_count += 1

    def run_validation(self) -> bool:
        """Run all validations."""
        print("🚀 Starting MFA implementation validation...\n")

        # Run all validations
        self.validate_dependencies()
        self.validate_module_imports()
        self.validate_models()
        self.validate_totp_provider()
        self.validate_risk_engine()
        self.validate_api_endpoints()
        self.validate_database_schema()

        # Print summary
        print("\n📊 Validation Summary:")
        print(f"Tests run: {self.test_count}")
        print(f"Passed: {self.success_count}")
        print(f"Failed: {self.test_count - self.success_count}")

        if self.errors:
            print(f"\n❌ Errors ({len(self.errors)}):")
            for error in self.errors:
                print(f"  - {error}")

        if self.warnings:
            print(f"\n⚠️ Warnings ({len(self.warnings)}):")
            for warning in self.warnings:
                print(f"  - {warning}")

        if not self.errors:
            print("\n🎉 All MFA validations passed!")
            return True
        else:
            print(f"\n💥 MFA validation failed with {len(self.errors)} errors!")
            return False


def main() -> None:
    """Main validation function."""
    validator = MFAValidator()
    success = validator.run_validation()

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
