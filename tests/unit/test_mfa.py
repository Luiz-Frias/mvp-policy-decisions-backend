"""Unit tests for MFA implementation."""

from uuid import uuid4

import pytest

from src.pd_prime_demo.core.auth.mfa.models import MFAMethod, RiskLevel
from src.pd_prime_demo.core.auth.mfa.risk_engine import RiskEngine
from src.pd_prime_demo.core.auth.mfa.totp import TOTPProvider
from src.pd_prime_demo.core.config import get_settings


@pytest.fixture
def settings():
    """Get test settings."""
    return get_settings()


@pytest.fixture
def totp_provider(settings):
    """Create TOTP provider instance."""
    return TOTPProvider(settings)


class TestTOTPProvider:
    """Tests for TOTP provider."""

    def test_generate_setup_success(self, totp_provider):
        """Test successful TOTP setup generation."""
        result = totp_provider.generate_setup("test@example.com", "123")

        assert result.is_ok()
        setup_data = result.value

        assert setup_data.secret
        assert setup_data.qr_code.startswith("data:image/png;base64,")
        assert len(setup_data.backup_codes) == 10
        assert setup_data.manual_entry_key

    def test_encrypt_decrypt_secret(self, totp_provider):
        """Test secret encryption and decryption."""
        secret = "ABCDEFGHIJKLMNOP"

        # Encrypt
        encrypt_result = totp_provider.encrypt_secret(secret)
        assert encrypt_result.is_ok()
        encrypted = encrypt_result.value

        # Decrypt
        decrypt_result = totp_provider.decrypt_secret(encrypted)
        assert decrypt_result.is_ok()
        assert decrypt_result.value == secret

    def test_verify_code_with_valid_code(self, totp_provider):
        """Test TOTP code verification with valid code."""
        secret = "ABCDEFGHIJKLMNOP"

        # Encrypt secret
        encrypt_result = totp_provider.encrypt_secret(secret)
        assert encrypt_result.is_ok()
        encrypted_secret = encrypt_result.value

        # Generate current code
        code_result = totp_provider.generate_current_code(encrypted_secret)
        assert code_result.is_ok()
        current_code = code_result.value

        # Verify code
        verify_result = totp_provider.verify_code(encrypted_secret, current_code)
        assert verify_result.is_ok()
        assert verify_result.value is True

    def test_verify_code_with_invalid_code(self, totp_provider):
        """Test TOTP code verification with invalid code."""
        secret = "ABCDEFGHIJKLMNOP"

        # Encrypt secret
        encrypt_result = totp_provider.encrypt_secret(secret)
        assert encrypt_result.is_ok()
        encrypted_secret = encrypt_result.value

        # Verify invalid code
        verify_result = totp_provider.verify_code(encrypted_secret, "000000")
        assert verify_result.is_ok()
        assert verify_result.value is False

    def test_validate_secret_valid(self, totp_provider):
        """Test secret validation with valid secret."""
        assert totp_provider.validate_secret("ABCDEFGHIJKLMNOPQRSTUVWXYZ234567")

    def test_validate_secret_invalid(self, totp_provider):
        """Test secret validation with invalid secret."""
        # Too short
        assert not totp_provider.validate_secret("ABC")

        # Invalid characters
        assert not totp_provider.validate_secret("ABCDEFGH!@#$%^&*")

    def test_get_time_remaining(self, totp_provider):
        """Test getting time remaining in TOTP interval."""
        remaining = totp_provider.get_time_remaining()
        assert 0 <= remaining <= 30


class TestRiskEngine:
    """Tests for risk assessment engine."""

    @pytest.fixture
    def mock_db(self):
        """Mock database connection."""

        class MockDB:
            async def fetchrow(self, query, *args):
                return None

            async def execute(self, query, *args):
                return None

        return MockDB()

    @pytest.fixture
    def mock_cache(self):
        """Mock cache connection."""

        class MockCache:
            def __init__(self):
                self._data = {}

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

        return MockCache()

    @pytest.fixture
    def risk_engine(self, mock_db, mock_cache, settings):
        """Create risk engine instance."""
        return RiskEngine(mock_db, mock_cache, settings)

    async def test_assess_risk_low_risk(self, risk_engine):
        """Test risk assessment for low-risk scenario."""
        user_id = str(uuid4())
        ip_address = "192.168.1.1"  # Private network
        user_agent = "Mozilla/5.0"

        result = await risk_engine.assess_risk(user_id, ip_address, user_agent)

        assert result.is_ok()
        assessment = result.value
        assert assessment.risk_level in [RiskLevel.LOW, RiskLevel.MEDIUM]
        assert 0 <= assessment.risk_score <= 1.0

    async def test_assess_risk_new_device(self, risk_engine):
        """Test risk assessment with new device."""
        user_id = str(uuid4())
        ip_address = "203.0.113.1"  # Public IP
        user_agent = "Mozilla/5.0"
        device_fingerprint = "new_device_123"

        result = await risk_engine.assess_risk(
            user_id, ip_address, user_agent, device_fingerprint
        )

        assert result.is_ok()
        assessment = result.value
        # New device should increase risk
        assert assessment.risk_score > 0.0

    async def test_assess_risk_trusted_network(self, risk_engine):
        """Test risk assessment from trusted network."""
        user_id = str(uuid4())
        ip_address = "10.0.0.1"  # Private network
        user_agent = "Mozilla/5.0"

        result = await risk_engine.assess_risk(user_id, ip_address, user_agent)

        assert result.is_ok()
        assessment = result.value
        # Private network should have lower risk
        assert assessment.risk_level == RiskLevel.LOW

    def test_calculate_risk_score_empty_factors(self, risk_engine):
        """Test risk score calculation with no risk factors."""
        score = risk_engine._calculate_risk_score({})
        assert score == 0.0

    def test_calculate_risk_score_with_factors(self, risk_engine):
        """Test risk score calculation with risk factors."""
        factors = {"new_device": 1.0, "new_location": 0.8, "failed_attempts": 0.5}

        score = risk_engine._calculate_risk_score(factors)
        assert 0.0 <= score <= 1.0

    def test_determine_risk_level(self, risk_engine):
        """Test risk level determination from score."""
        assert risk_engine._determine_risk_level(0.0) == RiskLevel.LOW
        assert risk_engine._determine_risk_level(0.5) == RiskLevel.MEDIUM
        assert risk_engine._determine_risk_level(0.7) == RiskLevel.HIGH
        assert risk_engine._determine_risk_level(0.9) == RiskLevel.CRITICAL

    def test_build_risk_reason(self, risk_engine):
        """Test risk reason building."""
        # Low risk
        reason = risk_engine._build_risk_reason({}, RiskLevel.LOW)
        assert "Normal" in reason

        # High risk with factors
        factors = {"new_device": 0.8, "impossible_travel": 0.9, "tor_network": 0.7}
        reason = risk_engine._build_risk_reason(factors, RiskLevel.HIGH)
        assert "Additional verification required" in reason


class TestMFAModels:
    """Tests for MFA models."""

    def test_mfa_method_enum(self):
        """Test MFA method enumeration."""
        assert MFAMethod.TOTP == "totp"
        assert MFAMethod.WEBAUTHN == "webauthn"
        assert MFAMethod.SMS == "sms"
        assert MFAMethod.BIOMETRIC == "biometric"
        assert MFAMethod.RECOVERY_CODE == "recovery_code"

    def test_risk_level_enum(self):
        """Test risk level enumeration."""
        assert RiskLevel.LOW == "low"
        assert RiskLevel.MEDIUM == "medium"
        assert RiskLevel.HIGH == "high"
        assert RiskLevel.CRITICAL == "critical"
