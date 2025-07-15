# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Risk-based authentication engine."""

import logging
from datetime import datetime, timezone
from ipaddress import ip_address, ip_network
from typing import Any

from beartype import beartype
from pydantic import Field

from policy_core.core.cache import Cache
from policy_core.core.config import Settings
from policy_core.core.database import Database
from policy_core.core.result_types import Err, Ok, Result
from policy_core.models.base import BaseModelConfig

from .models import MFAMethod, RiskAssessment, RiskFactors, RiskLevel

# Auto-generated models


@beartype
class Loc1Data(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class ContextData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class UpdatesMetrics(BaseModelConfig):
    """Structured model replacing dict[str, float] usage."""

    average: float = Field(default=0.0, ge=0.0, description="Average value")


@beartype
class AdditionalContextData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


class RiskEngine:
    """Risk assessment engine for adaptive MFA."""

    def __init__(self, db: Database, cache: Cache, settings: Settings) -> None:
        """Initialize risk engine."""
        self._db = db
        self._cache = cache
        self._settings = settings

        # Load dynamic config or fall back to defaults
        config: dict[str, Any] = getattr(settings, "risk_engine_config", {})

        # ------------------------------------------------------------------
        # Parse thresholds: YAML uses lowercase keys. Convert to RiskLevel.
        # ------------------------------------------------------------------
        default_thresholds: dict[RiskLevel, float] = {
            RiskLevel.LOW: 0.0,
            RiskLevel.MEDIUM: 0.4,
            RiskLevel.HIGH: 0.7,
            RiskLevel.CRITICAL: 0.9,
        }

        raw_thresholds: dict[str, float] = config.get("thresholds", {})  # type: ignore[arg-type]
        self._risk_thresholds: dict[RiskLevel, float] = {
            RiskLevel.LOW: float(
                raw_thresholds.get("low", default_thresholds[RiskLevel.LOW])
            ),
            RiskLevel.MEDIUM: float(
                raw_thresholds.get("medium", default_thresholds[RiskLevel.MEDIUM])
            ),
            RiskLevel.HIGH: float(
                raw_thresholds.get("high", default_thresholds[RiskLevel.HIGH])
            ),
            RiskLevel.CRITICAL: float(
                raw_thresholds.get("critical", default_thresholds[RiskLevel.CRITICAL])
            ),
        }

        # MFA requirements by risk level
        self._mfa_requirements = {
            RiskLevel.LOW: [],  # No MFA required
            RiskLevel.MEDIUM: [MFAMethod.TOTP, MFAMethod.SMS],  # Any one method
            RiskLevel.HIGH: [MFAMethod.TOTP, MFAMethod.WEBAUTHN],  # Stronger methods
            RiskLevel.CRITICAL: [MFAMethod.WEBAUTHN],  # Highest security only
        }

        # Known safe networks (office IPs, VPNs, etc.)
        self._safe_networks = [
            ip_network("10.0.0.0/8"),  # Private network example
            ip_network("192.168.0.0/16"),  # Private network example
        ]
        default_weights: dict[str, float] = {
            "new_device": 0.3,
            "new_location": 0.25,
            "impossible_travel": 0.4,
            "suspicious_time": 0.15,
            "failed_attempts": 0.2,
            "untrusted_network": 0.2,
            "account_age": 0.1,
            "unusual_behavior": 0.25,
        }

        self._risk_weights: dict[str, float] = {
            **default_weights,
            **config.get("weights", {}),  # type: ignore[arg-type]
        }

        # ------------------------------------------------------------------
        # Log effective configuration (use info level to appear in CI logs)
        # ------------------------------------------------------------------
        logger = logging.getLogger(__name__)
        if logger.isEnabledFor(logging.INFO):
            logger.info(
                "RiskEngine initialized with thresholds=%s weights=%s",
                {k.value: v for k, v in self._risk_thresholds.items()},
                self._risk_weights,
            )

    @beartype
    async def assess_risk(
        self,
        user_id: str,
        ip_address: str,
        user_agent: str,
        device_fingerprint: str | None = None,
        additional_context: AdditionalContextData | None = None,
    ) -> Result[RiskAssessment, str]:
        """Assess authentication risk based on multiple factors.

        Args:
            user_id: User's ID
            ip_address: Client IP address
            user_agent: Client user agent string
            device_fingerprint: Optional device fingerprint
            additional_context: Additional context data

        Returns:
            Result containing risk assessment or error
        """
        try:
            # Initialize risk factors
            risk_factors = RiskFactors()

            # 1. Check device trust
            device_risk = await self._assess_device_risk(
                user_id, device_fingerprint, user_agent
            )
            risk_factors = self._update_risk_factors(risk_factors, device_risk)

            # 2. Check location and travel patterns
            location_risk = await self._assess_location_risk(user_id, ip_address)
            risk_factors = self._update_risk_factors(risk_factors, location_risk)

            # 3. Check network trust
            network_risk = self._assess_network_risk(ip_address)
            risk_factors = self._update_risk_factors(risk_factors, network_risk)

            # 4. Check time-based patterns
            time_risk = await self._assess_time_risk(user_id)
            risk_factors = self._update_risk_factors(risk_factors, time_risk)

            # 5. Check recent failed attempts
            attempt_risk = await self._assess_failed_attempts(user_id)
            risk_factors = self._update_risk_factors(risk_factors, attempt_risk)

            # 6. Check account age and history
            account_risk = await self._assess_account_risk(user_id)
            risk_factors = self._update_risk_factors(risk_factors, account_risk)

            # 7. Check for unusual behavior patterns
            if additional_context:
                behavior_risk = await self._assess_behavior_risk(
                    user_id, additional_context
                )
                risk_factors = self._update_risk_factors(risk_factors, behavior_risk)

            # Calculate overall risk score
            risk_score = self._calculate_risk_score(risk_factors)

            # Determine risk level
            risk_level = self._determine_risk_level(risk_score)

            # Determine MFA requirements
            require_mfa = risk_level != RiskLevel.LOW
            recommended_methods = self._mfa_requirements.get(risk_level, [])

            # Build reason string
            reason = self._build_risk_reason(risk_factors, risk_level)

            # Log risk assessment
            await self._log_risk_assessment(
                user_id, risk_score, risk_factors, risk_level
            )

            return Ok(
                RiskAssessment(
                    risk_level=risk_level,
                    risk_score=risk_score,
                    factors=risk_factors,
                    require_mfa=require_mfa,
                    recommended_methods=recommended_methods,
                    reason=reason,
                )
            )

        except Exception as e:
            return Err(f"Failed to assess risk: {str(e)}")

    @beartype
    async def _assess_device_risk(
        self, user_id: str, device_fingerprint: str | None, user_agent: str
    ) -> dict[str, float]:
        """Assess risk based on device factors."""
        risk_factors = {}

        try:
            if device_fingerprint:
                # Check if device is known
                device_key = f"known_device:{user_id}:{device_fingerprint}"
                known_device = await self._cache.get(device_key)

                if not known_device:
                    # New device
                    risk_factors["new_device"] = 1.0

                    # Store device for future
                    await self._cache.set(
                        device_key,
                        {
                            "first_seen": datetime.now(timezone.utc).isoformat(),
                            "user_agent": user_agent,
                        },
                        ttl=86400 * 90,  # 90 days
                    )
                else:
                    # Check if user agent changed significantly
                    if known_device.get("user_agent") != user_agent:
                        risk_factors["device_change"] = 0.5
            else:
                # No device fingerprint is suspicious
                risk_factors["no_device_id"] = 0.7

        except Exception:
            risk_factors["device_check_error"] = 0.5

        return risk_factors

    @beartype
    async def _assess_location_risk(
        self, user_id: str, current_ip: str
    ) -> dict[str, float]:
        """Assess risk based on location and travel patterns."""
        risk_factors = {}

        try:
            # Get location from IP (mock implementation)
            current_location = self._get_location_from_ip(current_ip)

            # Get last known location
            last_location_key = f"last_location:{user_id}"
            last_location_data = await self._cache.get(last_location_key)

            if last_location_data:
                last_location = last_location_data["location"]
                last_time = datetime.fromisoformat(last_location_data["timestamp"])

                # Check for impossible travel
                distance = self._calculate_distance(current_location, last_location)
                time_diff = (
                    datetime.now(timezone.utc) - last_time
                ).total_seconds() / 3600

                if time_diff > 0:
                    speed = distance / time_diff  # km/h

                    if speed > 1000:  # Faster than commercial flight
                        risk_factors["impossible_travel"] = 1.0
                    elif speed > 500:  # Very fast travel
                        risk_factors["fast_travel"] = 0.7

                # Check for new country
                if current_location["country"] != last_location["country"]:
                    risk_factors["new_country"] = 0.8
                elif current_location["city"] != last_location["city"]:
                    risk_factors["new_city"] = 0.5
            else:
                # First login location
                risk_factors["new_location"] = 0.6

            # Update last location
            await self._cache.set(
                last_location_key,
                {
                    "location": current_location,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "ip": current_ip,
                },
                ttl=86400 * 30,  # 30 days
            )

        except Exception:
            risk_factors["location_check_error"] = 0.4

        return risk_factors

    @beartype
    def _assess_network_risk(self, client_ip: str) -> dict[str, float]:
        """Assess risk based on network characteristics."""
        risk_factors = {}

        try:
            ip_obj = ip_address(client_ip)

            # Check if IP is in safe networks
            is_safe = any(ip_obj in network for network in self._safe_networks)

            if not is_safe:
                # Check for risky network types
                if ip_obj.is_private:
                    risk_factors["private_network"] = 0.1
                elif self._is_vpn_or_proxy(client_ip):
                    risk_factors["vpn_proxy"] = 0.6
                elif self._is_tor_exit_node(client_ip):
                    risk_factors["tor_network"] = 0.9
                else:
                    risk_factors["untrusted_network"] = 0.3

        except Exception:
            risk_factors["network_check_error"] = 0.5

        return risk_factors

    @beartype
    async def _assess_time_risk(self, user_id: str) -> dict[str, float]:
        """Assess risk based on time patterns."""
        risk_factors = {}

        try:
            current_hour = datetime.now(timezone.utc).hour

            # Check unusual hours (2 AM - 5 AM)
            if 2 <= current_hour <= 5:
                risk_factors["unusual_hour"] = 0.4

            # Check user's typical login pattern
            pattern_key = f"login_pattern:{user_id}"
            login_pattern = await self._cache.get(pattern_key)

            if login_pattern:
                typical_hours = login_pattern.get("typical_hours", [])
                if current_hour not in typical_hours:
                    risk_factors["atypical_time"] = 0.3

        except Exception:
            pass

        return risk_factors

    @beartype
    async def _assess_failed_attempts(self, user_id: str) -> dict[str, float]:
        """Assess risk based on recent failed login attempts."""
        risk_factors = {}

        try:
            # Check recent failed attempts
            attempts_key = f"failed_attempts:{user_id}"
            failed_count = await self._cache.get(attempts_key) or 0

            if failed_count > 0:
                # Scale risk based on number of failures
                risk_factors["failed_attempts"] = min(failed_count * 0.2, 1.0)

        except Exception:
            pass

        return risk_factors

    @beartype
    async def _assess_account_risk(self, user_id: str) -> dict[str, float]:
        """Assess risk based on account characteristics."""
        risk_factors = {}

        try:
            # Get user account age (mock implementation)
            account_age_days = await self._get_account_age(user_id)

            if account_age_days < 7:
                risk_factors["new_account"] = 0.7
            elif account_age_days < 30:
                risk_factors["young_account"] = 0.4

            # Check if account has MFA enabled
            has_mfa = await self._check_mfa_enabled(user_id)
            if not has_mfa:
                risk_factors["no_mfa"] = 0.3

        except Exception:
            pass

        return risk_factors

    @beartype
    async def _assess_behavior_risk(
        self,
        user_id: str,
        context: AdditionalContextData | ContextData | dict[str, float],
    ) -> dict[str, float]:
        """Assess risk based on behavioral patterns."""
        risk_factors = {}

        # Normalize to dict for easier access
        ctx_dict: dict[str, Any]
        if isinstance(context, (AdditionalContextData, ContextData)):
            ctx_dict = context.model_dump()
        else:
            ctx_dict = context or {}

        # Check for unusual actions
        action = ctx_dict.get("action")
        if action in ["bulk_export", "permission_change", "api_key_create"]:
            risk_factors["sensitive_action"] = 0.6

        # Check for bulk data access flag
        if ctx_dict.get("bulk_access", False):
            risk_factors["bulk_access"] = 0.5

        return risk_factors

    @beartype
    def _calculate_risk_score(
        self, risk_factors: RiskFactors | dict[str, float]
    ) -> float:
        """Calculate weighted risk score."""
        rf_res = _to_risk_factors(risk_factors)
        if rf_res.is_err():
            # Fall back to 0 risk on invalid input
            return 0.0

        factors = rf_res.unwrap()

        # Simple weighted sum approach
        score = 0.0
        # Map weight keys to RiskFactors attributes
        alias_map = {
            "new_device": "device_risk",
            "no_device_id": "device_risk",
            "new_location": "location_risk",
            "location_check_error": "location_risk",
            "impossible_travel": "location_risk",
            "untrusted_network": "network_risk",
            "failed_attempts": "velocity_risk",
            "suspicious_time": "time_risk",
            "unusual_behavior": "behavioral_risk",
        }

        for factor_name, weight in self._risk_weights.items():
            attr = alias_map.get(factor_name, factor_name)
            factor_value = getattr(factors, attr, 0.0)
            score += factor_value * weight

        # Normalize score to 0-1 range
        return min(max(score, 0.0), 1.0)

    @beartype
    def _determine_risk_level(self, risk_score: float) -> RiskLevel:
        """Determine risk level from score."""
        if risk_score >= self._risk_thresholds[RiskLevel.CRITICAL]:
            return RiskLevel.CRITICAL
        elif risk_score >= self._risk_thresholds[RiskLevel.HIGH]:
            return RiskLevel.HIGH
        elif risk_score >= self._risk_thresholds[RiskLevel.MEDIUM]:
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW

    @beartype
    def _build_risk_reason(
        self, risk_factors: RiskFactors | dict[str, float], risk_level: RiskLevel
    ) -> str:
        """Build human-readable risk reason."""
        rf_res = _to_risk_factors(risk_factors)
        if rf_res.is_err():
            return "Risk factors unavailable"

        risk_factors = rf_res.unwrap()

        if risk_level == RiskLevel.LOW:
            return "Normal authentication pattern detected"

        # Convert RiskFactors to dict for analysis
        factors_dict = {
            "location_risk": risk_factors.location_risk,
            "device_risk": risk_factors.device_risk,
            "behavioral_risk": risk_factors.behavioral_risk,
            "time_risk": risk_factors.time_risk,
            "network_risk": risk_factors.network_risk,
            "velocity_risk": risk_factors.velocity_risk,
            "credential_risk": risk_factors.credential_risk,
        }

        # Find top risk factors
        top_factors = sorted(factors_dict.items(), key=lambda x: x[1], reverse=True)[:3]

        reasons = []
        for factor, score in top_factors:
            if score > 0.5:
                if "location" in factor:
                    reasons.append("login from new location")
                elif "device" in factor:
                    reasons.append("new device detected")
                elif "behavioral" in factor:
                    reasons.append("unusual behavior pattern")
                elif "time" in factor:
                    reasons.append("atypical login time")
                elif "network" in factor:
                    reasons.append("untrusted network")
                elif "velocity" in factor:
                    reasons.append("rapid login attempts")
                elif "credential" in factor:
                    reasons.append("credential security concern")

        if reasons:
            return f"Additional verification required due to: {', '.join(reasons)}"
        else:
            return f"{risk_level.value.title()} risk detected"

    @beartype
    def _update_risk_factors(
        self,
        risk_factors: RiskFactors,
        updates: UpdatesMetrics | dict[str, float],
    ) -> RiskFactors:
        """Update risk factors with new values."""
        # Map risk factor names to appropriate categories
        # Convert dict inputs to UpdatesMetrics-like handling
        if isinstance(updates, dict):
            updates_dict = updates
        else:
            updates_dict = updates.model_dump()

        new_data = risk_factors.model_dump()
        allowed = set(RiskFactors.__fields__.keys())
        for factor, value in updates_dict.items():
            if factor not in allowed:
                # Map some common aliases to base categories
                if factor in ["new_device", "no_device_id"]:
                    target = "device_risk"
                elif factor in ["new_location", "location_check_error"]:
                    target = "location_risk"
                elif factor in ["failed_attempts", "rapid_attempts", "velocity"]:
                    target = "velocity_risk"
                elif factor in ["untrusted_network", "vpn_proxy"]:
                    target = "network_risk"
                elif factor in ["sensitive_action", "bulk_access", "unusual_behavior"]:
                    target = "behavioral_risk"
                else:
                    continue
                current = new_data.get(target, 0.0)
                new_data[target] = max(current, value)
            else:
                current = new_data.get(factor, 0.0)
                new_data[factor] = max(current, value)

        return RiskFactors.model_validate(new_data)

    # Helper methods (mock implementations)

    @beartype
    def _get_location_from_ip(self, ip: str) -> dict[str, str | float]:
        """Get geographic location from IP (mock)."""
        # In production, use MaxMind GeoIP2 or similar
        return {
            "country": "US",
            "city": "New York",
            "latitude": 40.7128,
            "longitude": -74.0060,
        }

    @beartype
    def _calculate_distance(
        self,
        loc1: Loc1Data | dict[str, str | float],
        loc2: Loc1Data | dict[str, str | float],
    ) -> float:
        """Calculate distance between two locations in km (mock)."""
        # In production, use proper geographic distance calculation
        return 100.0  # Mock 100km

    @beartype
    def _is_vpn_or_proxy(self, ip: str) -> bool:
        """Check if IP is known VPN/proxy (mock)."""
        # In production, use IP intelligence services
        return False

    @beartype
    def _is_tor_exit_node(self, ip: str) -> bool:
        """Check if IP is Tor exit node (mock)."""
        # In production, check against Tor exit node list
        return False

    @beartype
    async def _get_account_age(self, user_id: str) -> int:
        """Get account age in days (mock)."""
        # In production, query from database
        return 90  # Mock 90 days

    @beartype
    async def _check_mfa_enabled(self, user_id: str) -> bool:
        """Check if user has MFA enabled (mock)."""
        # In production, query from database
        return False

    @beartype
    async def _log_risk_assessment(
        self,
        user_id: str,
        risk_score: float,
        risk_factors: RiskFactors,
        risk_level: RiskLevel,
    ) -> None:
        """Log risk assessment for analysis and audit."""
        # In production, store in database for analysis
        pass


# ---------------------------------------------------------------------------
# LEGACY_INPUT_BOUNDARY
# Convert loose dict inputs into strict RiskFactors model for backward compatibility.
# ---------------------------------------------------------------------------


@beartype
def _to_risk_factors(data: RiskFactors | dict[str, float]) -> Result[RiskFactors, str]:
    """Coerce legacy dict risk_factors into RiskFactors model."""
    if isinstance(data, RiskFactors):
        return Ok(data)
    if isinstance(data, dict):
        try:
            allowed_keys = {field for field in RiskFactors.__fields__.keys()}
            filtered = {k: v for k, v in data.items() if k in allowed_keys}
            return Ok(RiskFactors.model_validate(filtered))
        except Exception as exc:  # pragma: no cover
            return Err(f"Invalid risk factors: {exc}")
    return Err("Unsupported risk factor type; expected RiskFactors or dict")
