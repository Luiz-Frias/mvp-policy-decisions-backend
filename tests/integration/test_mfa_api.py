"""Integration tests for MFA API endpoints."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from src.policy_core.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return {"sub": str(uuid4()), "email": "test@example.com", "name": "Test User"}


@pytest.fixture
def auth_headers(mock_user):
    """Mock authorization headers."""
    # In a real test, this would be a valid JWT token
    return {"Authorization": "Bearer mock_token"}


class TestMFAStatusEndpoint:
    """Tests for MFA status endpoint."""

    @patch("src.policy_core.api.dependencies.get_current_user")
    @patch("src.policy_core.api.v1.mfa.get_mfa_manager")
    async def test_get_mfa_status_success(
        self, mock_mfa_manager, mock_get_current_user, client, mock_user, auth_headers
    ):
        """Test successful MFA status retrieval."""
        # Mock dependencies
        mock_get_current_user.return_value = mock_user

        # Mock MFA config
        mock_config = AsyncMock()
        mock_config.totp_enabled = True
        mock_config.webauthn_enabled = False
        mock_config.sms_enabled = False
        mock_config.recovery_codes_encrypted = ["code1", "code2"]
        mock_config.preferred_method = "totp"

        mock_manager = AsyncMock()
        mock_manager.get_user_mfa_config.return_value = AsyncMock(
            is_err=lambda: False, value=mock_config
        )
        mock_mfa_manager.return_value = mock_manager

        # Make request
        response = client.get("/api/v1/mfa/status", headers=auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert data["totp_enabled"] is True
        assert data["webauthn_enabled"] is False
        assert data["sms_enabled"] is False
        assert data["recovery_codes_count"] == 2

    @patch("src.policy_core.api.dependencies.get_current_user")
    @patch("src.policy_core.api.v1.mfa.get_mfa_manager")
    async def test_get_mfa_status_error(
        self, mock_mfa_manager, mock_get_current_user, client, mock_user, auth_headers
    ):
        """Test MFA status retrieval with error."""
        # Mock dependencies
        mock_get_current_user.return_value = mock_user

        mock_manager = AsyncMock()
        mock_manager.get_user_mfa_config.return_value = AsyncMock(
            is_err=lambda: True, error="Database error"
        )
        mock_mfa_manager.return_value = mock_manager

        # Make request
        response = client.get("/api/v1/mfa/status", headers=auth_headers)

        # Assertions
        assert response.status_code == 500


class TestTOTPSetupEndpoint:
    """Tests for TOTP setup endpoint."""

    @patch("src.policy_core.api.dependencies.get_current_user")
    @patch("src.policy_core.api.v1.mfa.get_mfa_manager")
    async def test_totp_setup_success(
        self, mock_mfa_manager, mock_get_current_user, client, mock_user, auth_headers
    ):
        """Test successful TOTP setup."""
        # Mock dependencies
        mock_get_current_user.return_value = mock_user

        # Mock MFA config (TOTP not enabled)
        mock_config = AsyncMock()
        mock_config.totp_enabled = False

        # Mock setup data
        mock_setup_data = AsyncMock()
        mock_setup_data.qr_code = "data:image/png;base64,abc123"
        mock_setup_data.manual_entry_key = "ABCD EFGH IJKL"
        mock_setup_data.backup_codes = ["12345678", "87654321"]

        mock_manager = AsyncMock()
        mock_manager.get_user_mfa_config.return_value = AsyncMock(
            is_ok=lambda: True, value=mock_config
        )
        mock_manager.setup_totp.return_value = AsyncMock(
            is_err=lambda: False, value=mock_setup_data
        )
        mock_mfa_manager.return_value = mock_manager

        # Make request
        response = client.post("/api/v1/mfa/totp/setup", headers=auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "qr_code" in data
        assert "manual_entry_key" in data
        assert "backup_codes" in data
        assert len(data["backup_codes"]) == 2

    @patch("src.policy_core.api.dependencies.get_current_user")
    @patch("src.policy_core.api.v1.mfa.get_mfa_manager")
    async def test_totp_setup_already_enabled(
        self, mock_mfa_manager, mock_get_current_user, client, mock_user, auth_headers
    ):
        """Test TOTP setup when already enabled."""
        # Mock dependencies
        mock_get_current_user.return_value = mock_user

        # Mock MFA config (TOTP already enabled)
        mock_config = AsyncMock()
        mock_config.totp_enabled = True

        mock_manager = AsyncMock()
        mock_manager.get_user_mfa_config.return_value = AsyncMock(
            is_ok=lambda: True, value=mock_config
        )
        mock_mfa_manager.return_value = mock_manager

        # Make request
        response = client.post("/api/v1/mfa/totp/setup", headers=auth_headers)

        # Assertions
        assert response.status_code == 400
        assert "already enabled" in response.json()["detail"]


class TestTOTPVerificationEndpoint:
    """Tests for TOTP verification endpoint."""

    @patch("src.policy_core.api.dependencies.get_current_user")
    @patch("src.policy_core.api.v1.mfa.get_mfa_manager")
    async def test_totp_verify_setup_success(
        self, mock_mfa_manager, mock_get_current_user, client, mock_user, auth_headers
    ):
        """Test successful TOTP setup verification."""
        # Mock dependencies
        mock_get_current_user.return_value = mock_user

        mock_manager = AsyncMock()
        mock_manager.verify_totp_setup.return_value = AsyncMock(
            is_err=lambda: False, value=True
        )
        mock_mfa_manager.return_value = mock_manager

        # Make request
        response = client.post(
            "/api/v1/mfa/totp/verify-setup",
            headers=auth_headers,
            json={"code": "123456"},
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "successfully enabled" in data["message"]

    @patch("src.policy_core.api.dependencies.get_current_user")
    @patch("src.policy_core.api.v1.mfa.get_mfa_manager")
    async def test_totp_verify_setup_invalid_code(
        self, mock_mfa_manager, mock_get_current_user, client, mock_user, auth_headers
    ):
        """Test TOTP setup verification with invalid code."""
        # Mock dependencies
        mock_get_current_user.return_value = mock_user

        mock_manager = AsyncMock()
        mock_manager.verify_totp_setup.return_value = AsyncMock(
            is_err=lambda: True, error="Invalid TOTP code"
        )
        mock_mfa_manager.return_value = mock_manager

        # Make request
        response = client.post(
            "/api/v1/mfa/totp/verify-setup",
            headers=auth_headers,
            json={"code": "000000"},
        )

        # Assertions
        assert response.status_code == 400

    async def test_totp_verify_setup_invalid_format(self, client, auth_headers):
        """Test TOTP verification with invalid code format."""
        # Make request with invalid code format
        response = client.post(
            "/api/v1/mfa/totp/verify-setup",
            headers=auth_headers,
            json={"code": "12345"},  # Too short
        )

        # Assertions
        assert response.status_code == 422  # Validation error


class TestMFAChallengeEndpoint:
    """Tests for MFA challenge endpoint."""

    @patch("src.policy_core.api.dependencies.get_current_user")
    @patch("src.policy_core.api.v1.mfa.get_mfa_manager")
    async def test_create_mfa_challenge_success(
        self, mock_mfa_manager, mock_get_current_user, client, mock_user, auth_headers
    ):
        """Test successful MFA challenge creation."""
        # Mock dependencies
        mock_get_current_user.return_value = mock_user

        # Mock challenge
        mock_challenge = AsyncMock()
        mock_challenge.challenge_id = uuid4()
        mock_challenge.method = "totp"
        mock_challenge.created_at = AsyncMock()
        mock_challenge.expires_at = AsyncMock()
        mock_challenge.metadata = {}

        # Mock total_seconds for timedelta
        mock_timedelta = AsyncMock()
        mock_timedelta.total_seconds.return_value = 300

        # Mock the subtraction result
        with patch("src.policy_core.api.v1.mfa.datetime"):
            mock_challenge.expires_at.__sub__.return_value = mock_timedelta

            mock_manager = AsyncMock()
            mock_manager.create_mfa_challenge.return_value = AsyncMock(
                is_err=lambda: False, value=mock_challenge
            )
            mock_mfa_manager.return_value = mock_manager

            # Make request
            response = client.post("/api/v1/mfa/challenge", headers=auth_headers)

            # Assertions
            assert response.status_code == 200
            data = response.json()
            assert "challenge_id" in data
            assert "method" in data
            assert "expires_in" in data


class TestRiskAssessmentEndpoint:
    """Tests for risk assessment endpoint."""

    @patch("src.policy_core.api.dependencies.get_current_user")
    @patch("src.policy_core.api.v1.mfa.get_mfa_manager")
    async def test_get_risk_assessment_success(
        self, mock_mfa_manager, mock_get_current_user, client, mock_user, auth_headers
    ):
        """Test successful risk assessment retrieval."""
        # Mock dependencies
        mock_get_current_user.return_value = mock_user

        # Mock risk assessment
        mock_assessment = AsyncMock()
        mock_assessment.risk_level = AsyncMock(value="medium")
        mock_assessment.risk_score = 0.4
        mock_assessment.require_mfa = True
        mock_assessment.recommended_methods = [AsyncMock(value="totp")]
        mock_assessment.reason = "New device detected"

        mock_risk_engine = AsyncMock()
        mock_risk_engine.assess_risk.return_value = AsyncMock(
            is_err=lambda: False, value=mock_assessment
        )

        mock_manager = AsyncMock()
        mock_manager._risk_engine = mock_risk_engine
        mock_mfa_manager.return_value = mock_manager

        # Make request
        response = client.get("/api/v1/mfa/risk-assessment", headers=auth_headers)

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "risk_level" in data
        assert "risk_score" in data
        assert "require_mfa" in data
        assert "recommended_methods" in data
        assert "reason" in data


class TestRecoveryCodesEndpoint:
    """Tests for recovery codes endpoint."""

    @patch("src.policy_core.api.dependencies.get_current_user")
    @patch("src.policy_core.api.v1.mfa.get_mfa_manager")
    async def test_generate_recovery_codes_success(
        self, mock_mfa_manager, mock_get_current_user, client, mock_user, auth_headers
    ):
        """Test successful recovery codes generation."""
        # Mock dependencies
        mock_get_current_user.return_value = mock_user

        mock_codes = ["12345678", "87654321", "11111111", "22222222", "33333333"]

        mock_manager = AsyncMock()
        mock_manager.generate_recovery_codes.return_value = AsyncMock(
            is_err=lambda: False, value=mock_codes
        )
        mock_mfa_manager.return_value = mock_manager

        # Make request
        response = client.post(
            "/api/v1/mfa/recovery-codes/generate", headers=auth_headers
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "recovery_codes" in data
        assert "warning" in data
        assert len(data["recovery_codes"]) == 5


class TestDeviceTrustEndpoint:
    """Tests for device trust endpoint."""

    @patch("src.policy_core.api.dependencies.get_current_user")
    @patch("src.policy_core.api.v1.mfa.get_mfa_manager")
    async def test_trust_device_success(
        self, mock_mfa_manager, mock_get_current_user, client, mock_user, auth_headers
    ):
        """Test successful device trust."""
        # Mock dependencies
        mock_get_current_user.return_value = mock_user

        # Mock device trust
        mock_device_trust = AsyncMock()
        mock_device_trust.device_id = uuid4()
        mock_device_trust.expires_at = AsyncMock()
        mock_device_trust.expires_at.isoformat.return_value = "2024-01-01T00:00:00Z"

        mock_manager = AsyncMock()
        mock_manager.trust_device.return_value = AsyncMock(
            is_err=lambda: False, value=mock_device_trust
        )
        mock_mfa_manager.return_value = mock_manager

        # Make request
        response = client.post(
            "/api/v1/mfa/device/trust",
            headers=auth_headers,
            json={
                "device_fingerprint": "abc123",
                "device_name": "iPhone 13",
                "trust_duration_days": 30,
            },
        )

        # Assertions
        assert response.status_code == 200
        data = response.json()
        assert "device_id" in data
        assert "trusted_until" in data
