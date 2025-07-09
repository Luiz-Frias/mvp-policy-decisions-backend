"""SOC 2 Compliance Schemas - Comprehensive Pydantic models for compliance data structures.

This module provides enterprise-grade Pydantic models to replace dict[str, Any] usage
throughout the compliance layer, ensuring type safety and validation for SOC 2 compliance.
"""

from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Any, Literal
from uuid import UUID, uuid4

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.base import BaseModelConfig

# ============================================================================
# ENUMS - MUST BE DEFINED BEFORE STRUCTURED MODELS
# ============================================================================


class ComplianceStatus(str, Enum):
    """Status values for compliance assessments."""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PENDING = "pending"
    UNDER_REVIEW = "under_review"
    REMEDIATION_REQUIRED = "remediation_required"


class RiskLevel(str, Enum):
    """Risk levels for compliance findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class TrustServiceCriterion(str, Enum):
    """SOC 2 Trust Service Criteria."""

    SECURITY = "security"
    AVAILABILITY = "availability"
    PROCESSING_INTEGRITY = "processing_integrity"
    CONFIDENTIALITY = "confidentiality"
    PRIVACY = "privacy"


# ============================================================================
# STRUCTURED MODELS TO REPLACE DICT USAGE
# ============================================================================


@beartype
class StateProperty(BaseModelConfig):
    """Individual state property, replacing dict[str, str] key-value pairs."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    key: str = Field(..., min_length=1, max_length=200, description="Property key")
    value: str = Field(..., min_length=1, max_length=2000, description="Property value")


@beartype
class StateMetadata(BaseModelConfig):
    """Individual metadata entry, replacing dict[str, str] key-value pairs."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    key: str = Field(..., min_length=1, max_length=200, description="Metadata key")
    value: str = Field(..., min_length=1, max_length=2000, description="Metadata value")


@beartype
class RequestParameter(BaseModelConfig):
    """Individual request parameter, replacing dict[str, str] parameters."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    name: str = Field(..., min_length=1, max_length=200, description="Parameter name")
    value: str = Field(..., min_length=1, max_length=2000, description="Parameter value")


@beartype
class RequestHeader(BaseModelConfig):
    """Individual request header, replacing dict[str, str] headers."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    name: str = Field(..., min_length=1, max_length=200, description="Header name")
    value: str = Field(..., min_length=1, max_length=2000, description="Header value")


@beartype
class RequestBodyData(BaseModelConfig):
    """Structured request body data replacing dict[str, Any]."""

    model_config = ConfigDict(
        frozen=True,
        extra="allow",  # Allow additional fields for flexible request data
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Common request fields
    endpoint: str | None = Field(default=None, max_length=200)
    method: str | None = Field(default=None, max_length=10)
    parameters: list[RequestParameter] = Field(default_factory=list, description="Request parameters as structured list")
    headers: list[RequestHeader] = Field(default_factory=list, description="Request headers as structured list")
    payload_size: int | None = Field(default=None, ge=0)
    content_type: str | None = Field(default=None, max_length=100)


@beartype
class SecurityAlert(BaseModelConfig):
    """Individual security alert replacing dict entries."""

    alert_id: UUID = Field(default_factory=uuid4)
    alert_type: str = Field(..., min_length=1, max_length=100)
    severity: RiskLevel = Field(...)
    message: str = Field(..., min_length=1, max_length=500)
    triggered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    rule_id: str | None = Field(default=None, max_length=50)
    confidence_score: float = Field(ge=0.0, le=1.0, default=0.0)


@beartype
class SecurityAlerts(BaseModelConfig):
    """Collection of security alerts replacing dict[str, Any]."""

    alerts: list[SecurityAlert] = Field(default_factory=list)
    total_alerts: int = Field(ge=0, default=0)
    critical_count: int = Field(ge=0, default=0)
    high_count: int = Field(ge=0, default=0)
    medium_count: int = Field(ge=0, default=0)
    low_count: int = Field(ge=0, default=0)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@beartype
class StateData(BaseModelConfig):
    """Structured state data replacing dict[str, Any] for before/after states."""

    model_config = ConfigDict(
        frozen=True,
        extra="allow",  # Allow flexible state data
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Core state identifiers
    resource_id: str | None = Field(default=None, max_length=200)
    resource_type: str | None = Field(default=None, max_length=100)
    version: str | None = Field(default=None, max_length=50)

    # Timestamp information
    captured_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # State content - structured models replacing dict[str, str]
    properties: list[StateProperty] = Field(default_factory=list, description="State properties as structured key-value pairs")
    metadata: list[StateMetadata] = Field(default_factory=list, description="State metadata as structured key-value pairs")

    # Validation
    checksum: str | None = Field(default=None, max_length=64)
    is_valid: bool = Field(default=True)


# ============================================================================
# AUDIT LOG MODELS
# ============================================================================


@beartype
class FindingsBySeverity(BaseModelConfig):
    """Structured model for findings by severity, replacing dict[str, int]."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    critical: int = Field(default=0, ge=0)
    high: int = Field(default=0, ge=0)
    medium: int = Field(default=0, ge=0)
    low: int = Field(default=0, ge=0)
    info: int = Field(default=0, ge=0)


class FindingsByType(BaseModel):
    """Structured model for findings by type, replacing dict[str, int]."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    security: int = Field(default=0, ge=0)
    availability: int = Field(default=0, ge=0)
    processing_integrity: int = Field(default=0, ge=0)
    confidentiality: int = Field(default=0, ge=0)
    privacy: int = Field(default=0, ge=0)
    configuration: int = Field(default=0, ge=0)
    authentication: int = Field(default=0, ge=0)
    authorization: int = Field(default=0, ge=0)
    data_protection: int = Field(default=0, ge=0)


class CriteriaCompliance(BaseModel):
    """Individual criteria compliance data, replacing nested dict[str, Any]."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: ComplianceStatus = Field(...)
    compliance_percentage: float = Field(ge=0.0, le=100.0)
    controls_total: int = Field(ge=0)
    controls_passed: int = Field(ge=0)
    controls_failed: int = Field(ge=0)
    last_assessment: datetime | None = Field(default=None)
    next_assessment: datetime | None = Field(default=None)
    findings_count: int = Field(default=0, ge=0)


class ComplianceByCriteria(BaseModel):
    """Structured model for compliance by criteria, replacing dict[str, dict[str, Any]]."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    security: CriteriaCompliance | None = Field(default=None)
    availability: CriteriaCompliance | None = Field(default=None)
    processing_integrity: CriteriaCompliance | None = Field(default=None)
    confidentiality: CriteriaCompliance | None = Field(default=None)
    privacy: CriteriaCompliance | None = Field(default=None)


class TestingTrends(BaseModel):
    """Structured model for testing trends, replacing dict[str, list[float]]."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    daily_completion_rates: list[float] = Field(default_factory=list)
    weekly_effectiveness_rates: list[float] = Field(default_factory=list)
    monthly_findings_trend: list[float] = Field(default_factory=list)
    quarterly_compliance_scores: list[float] = Field(default_factory=list)
    annual_audit_scores: list[float] = Field(default_factory=list)


class SecurityThresholds(BaseModel):
    """Structured model for security thresholds, replacing dict[str, float]."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    max_failed_login_attempts: float = Field(default=5.0, ge=0.0)
    session_timeout_minutes: float = Field(default=30.0, ge=0.0)
    password_expiry_days: float = Field(default=90.0, ge=0.0)
    account_lockout_duration_minutes: float = Field(default=15.0, ge=0.0)
    min_password_strength_score: float = Field(default=3.0, ge=0.0, le=5.0)
    two_factor_timeout_minutes: float = Field(default=10.0, ge=0.0)
    api_rate_limit_per_minute: float = Field(default=100.0, ge=0.0)
    max_concurrent_sessions: float = Field(default=3.0, ge=0.0)


class AlertThresholds(BaseModel):
    """Structured model for alert thresholds, replacing dict[str, float]."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    cpu_usage_percent: float = Field(default=80.0, ge=0.0, le=100.0)
    memory_usage_percent: float = Field(default=85.0, ge=0.0, le=100.0)
    disk_usage_percent: float = Field(default=90.0, ge=0.0, le=100.0)
    response_time_ms: float = Field(default=500.0, ge=0.0)
    error_rate_percent: float = Field(default=5.0, ge=0.0, le=100.0)
    failed_logins_per_minute: float = Field(default=10.0, ge=0.0)
    database_connection_count: float = Field(default=80.0, ge=0.0)
    queue_depth: float = Field(default=1000.0, ge=0.0)


# ============================================================================
# AUDIT LOG MODELS
# ============================================================================


# Create alias for AuditLogEntry pointing to AuditLogEntryDetailed
# This allows the audit_logger.py to use AuditLogEntry while we use the detailed version
AuditLogEntry = None  # Will be set after class definition below


@beartype
class AuditLogEntryDetailed(BaseModelConfig):
    """Structured audit log entry replacing dict usage in audit logging."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Core Identity
    log_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: str = Field(..., min_length=1, max_length=100)

    # User Context
    user_id: UUID | None = Field(default=None)
    session_id: UUID | None = Field(default=None)
    ip_address: str | None = Field(default=None, max_length=45)  # IPv6 compatible
    user_agent: str | None = Field(default=None, max_length=500)

    # Event Details
    action: str = Field(..., min_length=1, max_length=200)
    resource_type: str | None = Field(default=None, max_length=100)
    resource_id: str | None = Field(default=None, max_length=200)

    # Request Context
    request_method: str | None = Field(default=None, max_length=10)
    request_path: str | None = Field(default=None, max_length=500)
    request_body: RequestBodyData | None = Field(default=None)
    response_status: int | None = Field(default=None, ge=100, le=599)

    # Risk Assessment
    risk_level: RiskLevel = Field(default=RiskLevel.INFO)
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Compliance Metadata
    control_references: list[str] = Field(default_factory=list)
    compliance_tags: list[str] = Field(default_factory=list)
    evidence_references: list[str] = Field(default_factory=list)

    # Processing Context
    processing_time_ms: int | None = Field(default=None, ge=0)
    error_details: str | None = Field(default=None)

    # Security Context
    security_alerts: SecurityAlerts | None = Field(default=None)
    before_state: StateData | None = Field(default=None)
    after_state: StateData | None = Field(default=None)


# Set the alias now that AuditLogEntryDetailed is defined
AuditLogEntry = AuditLogEntryDetailed


@beartype
class AuditTrailSummary(BaseModelConfig):
    """Summary of audit trail for compliance reporting."""

    period_start: datetime = Field(...)
    period_end: datetime = Field(...)
    total_events: int = Field(ge=0)
    events_by_type: dict[str, int] = Field(default_factory=dict)
    events_by_risk_level: dict[str, int] = Field(default_factory=dict)
    unique_users: int = Field(ge=0)
    unique_resources: int = Field(ge=0)
    integrity_verified: bool = Field(default=True)
    completeness_score: float = Field(ge=0.0, le=100.0)


# ============================================================================
# CONTROL TESTING MODELS
# ============================================================================


class ControlTestFinding(BaseModel):
    """Individual finding from control testing."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    finding_id: UUID = Field(default_factory=uuid4)
    control_id: str = Field(..., min_length=1, max_length=50)
    finding_type: str = Field(..., min_length=1, max_length=100)
    severity: RiskLevel = Field(...)
    description: str = Field(..., min_length=1, max_length=1000)
    impact: str = Field(..., min_length=1, max_length=500)
    likelihood: Literal["rare", "unlikely", "possible", "likely", "certain"] = Field(
        ...
    )
    remediation_required: bool = Field(default=True)
    remediation_timeline: str | None = Field(default=None, max_length=100)


class ControlTestResult(BaseModel):
    """Comprehensive control test result replacing dict usage."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Test Identity
    test_id: UUID = Field(default_factory=uuid4)
    control_id: str = Field(..., min_length=1, max_length=50)
    test_name: str = Field(..., min_length=1, max_length=200)
    test_type: str = Field(..., min_length=1, max_length=100)

    # Test Execution
    executed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    executed_by: str = Field(..., min_length=1, max_length=100)
    execution_time_ms: int = Field(ge=0)

    # Test Results
    test_result: Literal[
        "effective", "ineffective", "deficient", "not_applicable", "inconclusive"
    ] = Field(...)
    effectiveness_score: float = Field(ge=0.0, le=100.0)

    # Findings and Evidence
    findings: list[ControlTestFinding] = Field(default_factory=list)
    evidence_collected: list[str] = Field(default_factory=list)
    evidence_quality: Literal[
        "comprehensive", "adequate", "limited", "insufficient"
    ] = Field(...)

    # Analysis
    conclusion: str = Field(..., min_length=1, max_length=1000)
    recommendations: list[str] = Field(default_factory=list)
    remediation_actions: list[str] = Field(default_factory=list)

    # Compliance Context
    trust_service_criteria: TrustServiceCriterion = Field(...)
    sample_size: int | None = Field(default=None, ge=0)
    population_size: int | None = Field(default=None, ge=0)
    test_period_start: datetime | None = Field(default=None)
    test_period_end: datetime | None = Field(default=None)


class ControlTestingDashboard(BaseModel):
    """Dashboard data for control testing overview."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Summary Statistics
    total_controls: int = Field(ge=0)
    tested_controls: int = Field(ge=0)
    effective_controls: int = Field(ge=0)
    ineffective_controls: int = Field(ge=0)

    # Testing Progress
    testing_completion_rate: float = Field(ge=0.0, le=100.0)
    effectiveness_rate: float = Field(ge=0.0, le=100.0)

    # Findings Summary
    total_findings: int = Field(ge=0)
    findings_by_severity: FindingsBySeverity = Field(
        default_factory=lambda: FindingsBySeverity()
    )
    findings_by_type: FindingsByType = Field(default_factory=lambda: FindingsByType())

    # Compliance by Criteria
    compliance_by_criteria: ComplianceByCriteria = Field(
        default_factory=lambda: ComplianceByCriteria()
    )

    # Trending Data
    testing_trends: TestingTrends = Field(default_factory=lambda: TestingTrends())
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ============================================================================
# SECURITY CONTROL MODELS
# ============================================================================


class SecurityControlConfig(BaseModel):
    """Configuration for security controls replacing dict usage."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Control Identity
    control_id: str = Field(..., min_length=1, max_length=50)
    control_name: str = Field(..., min_length=1, max_length=200)
    control_type: str = Field(..., min_length=1, max_length=100)

    # Configuration
    enabled: bool = Field(default=True)
    enforcement_mode: Literal["strict", "lenient", "monitoring"] = Field(
        default="strict"
    )
    thresholds: SecurityThresholds = Field(
        default_factory=lambda: SecurityThresholds()
    )

    # Encryption Settings
    encryption_algorithm: str = Field(default="AES-256-GCM")
    key_size: int = Field(default=256, ge=128)
    key_rotation_days: int = Field(default=90, ge=1)

    # TLS Configuration
    min_tls_version: str = Field(default="TLSv1.3")
    cipher_suites: list[str] = Field(default_factory=list)
    certificate_validation: bool = Field(default=True)

    # Monitoring Settings
    monitoring_enabled: bool = Field(default=True)
    alert_thresholds: AlertThresholds = Field(
        default_factory=lambda: AlertThresholds()
    )
    automated_response: bool = Field(default=False)

    # Compliance Metadata
    compliance_frameworks: list[str] = Field(default_factory=list)
    last_review_date: datetime | None = Field(default=None)
    next_review_date: datetime | None = Field(default=None)


class VulnerabilityFinding(BaseModel):
    """Individual vulnerability finding."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    vulnerability_id: str = Field(..., min_length=1, max_length=50)
    cve_id: str | None = Field(default=None, max_length=20)
    severity: RiskLevel = Field(...)
    component: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1, max_length=1000)
    remediation: str = Field(..., min_length=1, max_length=500)
    cvss_score: float | None = Field(default=None, ge=0.0, le=10.0)
    exploitability: Literal["low", "medium", "high", "critical"] = Field(...)
    patch_available: bool = Field(default=False)
    patch_version: str | None = Field(default=None, max_length=50)


class VulnerabilitySeverityBreakdown(BaseModel):
    """Structured replacement for vulnerabilities_by_severity dict."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    critical: int = Field(default=0, ge=0)
    high: int = Field(default=0, ge=0)
    medium: int = Field(default=0, ge=0)
    low: int = Field(default=0, ge=0)
    informational: int = Field(default=0, ge=0)


class SecurityAssessment(BaseModel):
    """Security assessment results replacing dict usage."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Assessment Identity
    assessment_id: UUID = Field(default_factory=uuid4)
    assessment_type: str = Field(..., min_length=1, max_length=100)
    conducted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    conducted_by: str = Field(..., min_length=1, max_length=100)

    # Scope and Coverage
    scope: list[str] = Field(default_factory=list)
    coverage_percentage: float = Field(ge=0.0, le=100.0)

    # Findings
    vulnerabilities: list[VulnerabilityFinding] = Field(default_factory=list)
    total_vulnerabilities: int = Field(ge=0)
    vulnerabilities_by_severity: VulnerabilitySeverityBreakdown = Field(
        default_factory=lambda: VulnerabilitySeverityBreakdown()
    )

    # Risk Analysis
    overall_risk_level: RiskLevel = Field(...)
    risk_score: float = Field(ge=0.0, le=100.0)

    # Compliance Status
    compliance_status: ComplianceStatus = Field(...)
    compliance_score: float = Field(ge=0.0, le=100.0)

    # Remediation
    remediation_required: bool = Field(default=False)
    remediation_timeline: str | None = Field(default=None, max_length=100)
    priority_actions: list[str] = Field(default_factory=list)


# ============================================================================
# AVAILABILITY CONTROL MODELS
# ============================================================================

class AvailabilityMetrics(BaseModel):
    """Availability metrics replacing dict usage in availability controls."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    # Uptime Metrics
    uptime_percentage: Decimal = Field(ge=0.0, le=100.0, decimal_places=4)
    downtime_minutes: int = Field(ge=0)
    availability_sla: Decimal = Field(default=Decimal("99.9"), ge=0.0, le=100.0)
    sla_compliance: bool = Field(...)
    
    # Incident Metrics
    incident_count: int = Field(ge=0)
    critical_incidents: int = Field(ge=0)
    mean_time_to_repair: float = Field(ge=0.0)
    mean_time_between_failures: float = Field(ge=0.0)
    
    # Performance Metrics
    response_time_p50: float = Field(ge=0.0)
    response_time_p95: float = Field(ge=0.0)
    response_time_p99: float = Field(ge=0.0)
    throughput_rps: float = Field(ge=0.0)
    error_rate_percentage: float = Field(ge=0.0, le=100.0)
    
    # Resource Utilization
    cpu_usage_percentage: float = Field(ge=0.0, le=100.0)
    memory_usage_percentage: float = Field(ge=0.0, le=100.0)
    disk_usage_percentage: float = Field(ge=0.0, le=100.0)
    
    # Measurement Context
    measurement_period_start: datetime = Field(...)
    measurement_period_end: datetime = Field(...)
    measurement_period_hours: int = Field(ge=1)


class PerformanceThresholds(BaseModel):
    """Structured replacement for threshold dictionaries."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    response_time_ms: float = Field(default=100.0, ge=0.0)
    error_rate_percentage: float = Field(default=5.0, ge=0.0, le=100.0)
    throughput_rps: float = Field(default=100.0, ge=0.0)
    cpu_usage_percentage: float = Field(default=80.0, ge=0.0, le=100.0)
    memory_usage_percentage: float = Field(default=80.0, ge=0.0, le=100.0)
    disk_usage_percentage: float = Field(default=90.0, ge=0.0, le=100.0)


class DataRetentionPolicies(BaseModel):
    """Structured replacement for retention_periods dict."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    personal_data_days: int = Field(default=2555, ge=1)  # 7 years
    financial_data_days: int = Field(default=2555, ge=1)  # 7 years
    audit_logs_days: int = Field(default=2555, ge=1)  # 7 years
    session_data_days: int = Field(default=30, ge=1)  # 30 days
    temporary_data_days: int = Field(default=1, ge=1)  # 1 day
    backup_data_days: int = Field(default=90, ge=1)  # 90 days
    analytics_data_days: int = Field(default=365, ge=1)  # 1 year


class DataSubjectResponseData(BaseModel):
    """Structured replacement for response_data dict."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    # Response Metadata
    response_type: str = Field(default="data_export", min_length=1, max_length=50)
    format: str = Field(default="json", min_length=1, max_length=20)
    
    # Data Export Details
    records_count: int = Field(default=0, ge=0)
    data_categories: list[str] = Field(default_factory=list)
    export_format: str = Field(default="csv", min_length=1, max_length=20)
    file_size_bytes: int = Field(default=0, ge=0)
    
    # Redaction Information
    redacted_fields: list[str] = Field(default_factory=list)
    redaction_reason: str | None = Field(default=None, max_length=200)
    
    # Delivery Information
    delivery_method: str = Field(default="secure_download", min_length=1, max_length=50)
    download_url: str | None = Field(default=None, max_length=500)
    expires_at: datetime | None = Field(default=None)
    
    # Verification
    data_hash: str | None = Field(default=None, max_length=128)
    verification_code: str | None = Field(default=None, max_length=50)


class CommunicationRecord(BaseModel):
    """Structured replacement for communications list elements."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    # Communication Identity
    communication_id: UUID = Field(default_factory=uuid4)
    communication_type: str = Field(..., min_length=1, max_length=50)
    
    # Content
    subject: str = Field(..., min_length=1, max_length=200)
    message: str = Field(..., min_length=1, max_length=5000)
    
    # Participants
    sender: str = Field(..., min_length=1, max_length=100)
    recipient: str = Field(..., min_length=1, max_length=100)
    
    # Timing
    sent_at: datetime = Field(...)
    delivered_at: datetime | None = Field(default=None)
    read_at: datetime | None = Field(default=None)
    
    # Channel
    channel: str = Field(..., min_length=1, max_length=50)  # email, sms, portal, etc.
    reference_number: str | None = Field(default=None, max_length=100)
    
    # Status
    delivery_status: str = Field(default="sent", min_length=1, max_length=50)
    response_required: bool = Field(default=False)
    response_received: bool = Field(default=False)


class DataClassificationBreakdown(BaseModel):
    """Structured replacement for classification_distribution dict."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    public: int = Field(default=0, ge=0)
    internal: int = Field(default=0, ge=0)
    confidential: int = Field(default=0, ge=0)
    restricted: int = Field(default=0, ge=0)
    top_secret: int = Field(default=0, ge=0)
    unclassified: int = Field(default=0, ge=0)


class MisclassificationDetail(BaseModel):
    """Structured replacement for misclassification_details list elements."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    # Data Element Information
    data_element_id: str = Field(..., min_length=1, max_length=100)
    data_element_name: str = Field(..., min_length=1, max_length=200)
    data_type: str = Field(..., min_length=1, max_length=100)
    
    # Classification Details
    assigned_classification: str = Field(..., min_length=1, max_length=50)
    correct_classification: str = Field(..., min_length=1, max_length=50)
    confidence_score: float = Field(ge=0.0, le=100.0)
    
    # Context
    misclassification_reason: str = Field(..., min_length=1, max_length=500)
    impact_assessment: str = Field(..., min_length=1, max_length=500)
    
    # Remediation
    remediation_action: str = Field(..., min_length=1, max_length=200)
    corrected_at: datetime | None = Field(default=None)
    corrected_by: str | None = Field(default=None, max_length=100)


class AccessViolationDetail(BaseModel):
    """Structured replacement for violation_details list elements."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    # Violation Identity
    violation_id: UUID = Field(default_factory=uuid4)
    violation_type: str = Field(..., min_length=1, max_length=100)
    severity: Literal["critical", "high", "medium", "low"] = Field(...)
    
    # User and Resource Information
    user_id: UUID = Field(...)
    username: str = Field(..., min_length=1, max_length=100)
    resource_type: str = Field(..., min_length=1, max_length=100)
    resource_id: str = Field(..., min_length=1, max_length=100)
    
    # Access Details
    requested_permission: str = Field(..., min_length=1, max_length=100)
    granted_permission: str = Field(..., min_length=1, max_length=100)
    expected_permission: str = Field(..., min_length=1, max_length=100)
    
    # Violation Context
    violation_description: str = Field(..., min_length=1, max_length=500)
    business_justification: str | None = Field(default=None, max_length=500)
    
    # Temporal Information
    discovered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    first_occurrence: datetime = Field(...)
    last_occurrence: datetime = Field(...)
    
    # Remediation
    remediation_required: bool = Field(default=True)
    remediation_status: str = Field(default="pending", min_length=1, max_length=50)
    remediation_plan: str | None = Field(default=None, max_length=1000)
    remediated_at: datetime | None = Field(default=None)


class AccessViolationBreakdown(BaseModel):
    """Structured replacement for violation_types dict."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    excessive_permissions: int = Field(default=0, ge=0)
    unauthorized_access: int = Field(default=0, ge=0)
    privilege_escalation: int = Field(default=0, ge=0)
    role_separation_violation: int = Field(default=0, ge=0)
    dormant_account_access: int = Field(default=0, ge=0)
    shared_account_usage: int = Field(default=0, ge=0)
    emergency_access_abuse: int = Field(default=0, ge=0)
    cross_system_violations: int = Field(default=0, ge=0)


class EvidenceData(BaseModel):
    """Structured replacement for evidence_data dict."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    # Evidence Content
    content_type: str = Field(default="system_output", min_length=1, max_length=100)
    content_format: str = Field(default="json", min_length=1, max_length=50)
    raw_data: str | None = Field(default=None)
    
    # Metrics and Measurements
    numerical_values: list[float] = Field(default_factory=list)
    categorical_values: list[str] = Field(default_factory=list)
    boolean_indicators: list[bool] = Field(default_factory=list)
    
    # System Information
    system_name: str | None = Field(default=None, max_length=100)
    system_version: str | None = Field(default=None, max_length=50)
    configuration_settings: list[str] = Field(default_factory=list)
    
    # Test Results
    test_status: str | None = Field(default=None, max_length=50)
    test_output: str | None = Field(default=None)
    error_messages: list[str] = Field(default_factory=list)
    
    # File and Document Information
    file_paths: list[str] = Field(default_factory=list)
    document_references: list[str] = Field(default_factory=list)
    screenshots: list[str] = Field(default_factory=list)
    
    # Database and Query Results
    query_results: str | None = Field(default=None)
    record_counts: list[int] = Field(default_factory=list)
    data_samples: list[str] = Field(default_factory=list)


class CriteriaCoverageBreakdown(BaseModel):
    """Structured replacement for criteria_coverage dict."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    security: int = Field(default=0, ge=0)
    availability: int = Field(default=0, ge=0)
    processing_integrity: int = Field(default=0, ge=0)
    confidentiality: int = Field(default=0, ge=0)
    privacy: int = Field(default=0, ge=0)


class FindingsSeverityBreakdown(BaseModel):
    """Structured replacement for findings_by_severity dict."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    critical: int = Field(default=0, ge=0)
    high: int = Field(default=0, ge=0)
    medium: int = Field(default=0, ge=0)
    low: int = Field(default=0, ge=0)
    informational: int = Field(default=0, ge=0)


class BackupValidation(BaseModel):
    """Backup validation results replacing dict usage."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
    # Backup Identity
    backup_id: str = Field(..., min_length=1, max_length=100)
    backup_type: str = Field(..., min_length=1, max_length=50)
    backup_time: datetime = Field(...)
    
    # Backup Status
    backup_successful: bool = Field(...)
    backup_size_gb: Decimal = Field(ge=0, decimal_places=2)
    backup_duration_minutes: int = Field(ge=0)
    
    # Validation Results
    integrity_verified: bool = Field(...)
    completeness_verified: bool = Field(...)
    restoration_tested: bool = Field(...)
    restoration_successful: bool | None = Field(default=None)
    restoration_time_minutes: int | None = Field(default=None, ge=0)
    
    # Compliance Metrics
    recovery_time_objective: int = Field(ge=0)  # RTO in minutes
    recovery_point_objective: int = Field(ge=0)  # RPO in minutes
    rto_compliance: bool = Field(...)
    rpo_compliance: bool = Field(...)
    
    # Security
    encryption_enabled: bool = Field(default=True)
    encryption_algorithm: str | None = Field(default=None)
    access_controls_verified: bool = Field(default=True)
    
    # Location and Retention
    storage_location: str = Field(..., min_length=1, max_length=200)
    offsite_storage: bool = Field(default=True)
    retention_period_days: int = Field(ge=1)
    retention_compliance: bool = Field(...)


class PerformanceBaseline(BaseModel):
    """Performance baseline for availability monitoring."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Baseline Identity
    baseline_id: UUID = Field(default_factory=uuid4)
    baseline_name: str = Field(..., min_length=1, max_length=200)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Performance Thresholds
    max_response_time_ms: int = Field(ge=0)
    max_error_rate_percentage: float = Field(ge=0.0, le=100.0)
    min_throughput_rps: float = Field(ge=0.0)
    max_cpu_usage_percentage: float = Field(ge=0.0, le=100.0)
    max_memory_usage_percentage: float = Field(ge=0.0, le=100.0)

    # Availability Thresholds
    min_uptime_percentage: Decimal = Field(ge=0.0, le=100.0, decimal_places=4)
    max_downtime_minutes_monthly: int = Field(ge=0)

    # Alerting Configuration
    warning_thresholds: PerformanceThresholds = Field(
        default_factory=lambda: PerformanceThresholds()
    )
    critical_thresholds: PerformanceThresholds = Field(
        default_factory=lambda: PerformanceThresholds()
    )

    # Measurement Context
    measurement_window_minutes: int = Field(ge=1)
    statistical_method: str = Field(default="percentile")
    confidence_level: float = Field(default=95.0, ge=0.0, le=100.0)


# ============================================================================
# PRIVACY CONTROL MODELS
# ============================================================================


class PrivacyControlSettings(BaseModel):
    """Privacy control settings replacing dict usage."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Control Identity
    control_id: str = Field(..., min_length=1, max_length=50)
    control_name: str = Field(..., min_length=1, max_length=200)
    privacy_framework: str = Field(..., min_length=1, max_length=50)  # GDPR, CCPA, etc.

    # Data Processing Settings
    lawful_basis: str = Field(..., min_length=1, max_length=100)
    processing_purposes: list[str] = Field(default_factory=list)
    data_categories: list[str] = Field(default_factory=list)
    retention_periods: DataRetentionPolicies = Field(
        default_factory=lambda: DataRetentionPolicies()
    )

    # Consent Management
    consent_required: bool = Field(default=True)
    consent_type: str = Field(..., min_length=1, max_length=50)
    consent_withdrawal_enabled: bool = Field(default=True)
    consent_granularity: str = Field(default="purpose")

    # Data Subject Rights
    right_to_access: bool = Field(default=True)
    right_to_rectification: bool = Field(default=True)
    right_to_erasure: bool = Field(default=True)
    right_to_portability: bool = Field(default=True)
    right_to_restriction: bool = Field(default=True)
    right_to_object: bool = Field(default=True)

    # Technical Measures
    pseudonymization_enabled: bool = Field(default=False)
    encryption_at_rest: bool = Field(default=True)
    encryption_in_transit: bool = Field(default=True)
    access_logging: bool = Field(default=True)

    # Organizational Measures
    staff_training_required: bool = Field(default=True)
    dpo_assigned: bool = Field(default=True)
    pia_required: bool = Field(default=False)

    # International Transfers
    international_transfers_allowed: bool = Field(default=False)
    adequacy_decisions: list[str] = Field(default_factory=list)
    safeguards_implemented: list[str] = Field(default_factory=list)


class ConsentManagementRecord(BaseModel):
    """Consent management record replacing dict usage."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Consent Identity
    consent_id: UUID = Field(default_factory=uuid4)
    user_id: UUID = Field(...)
    data_subject_id: str = Field(..., min_length=1, max_length=100)

    # Consent Details
    consent_type: str = Field(..., min_length=1, max_length=50)
    processing_purposes: list[str] = Field(default_factory=list)
    data_categories: list[str] = Field(default_factory=list)

    # Consent Status
    consent_given: bool = Field(...)
    consent_timestamp: datetime = Field(...)
    consent_method: str = Field(..., min_length=1, max_length=100)
    consent_version: str = Field(..., min_length=1, max_length=20)

    # Withdrawal Information
    withdrawal_enabled: bool = Field(default=True)
    withdrawn_at: datetime | None = Field(default=None)
    withdrawal_method: str | None = Field(default=None, max_length=100)

    # Legal Basis
    legal_basis: str = Field(..., min_length=1, max_length=100)
    lawful_basis_assessment: str = Field(..., min_length=1, max_length=500)

    # Context Information
    ip_address: str | None = Field(default=None, max_length=45)
    user_agent: str | None = Field(default=None, max_length=500)
    language: str | None = Field(default=None, max_length=10)

    # Expiration
    expires_at: datetime | None = Field(default=None)
    auto_renewal: bool = Field(default=False)

    # Audit Information
    created_by: str = Field(..., min_length=1, max_length=100)
    last_modified_by: str | None = Field(default=None, max_length=100)
    last_modified_at: datetime | None = Field(default=None)


class DataSubjectRightsRequest(BaseModel):
    """Data subject rights request replacing dict usage."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Request Identity
    request_id: UUID = Field(default_factory=uuid4)
    request_reference: str = Field(..., min_length=1, max_length=50)
    data_subject_id: str = Field(..., min_length=1, max_length=100)

    # Request Details
    request_type: str = Field(..., min_length=1, max_length=50)
    request_description: str = Field(..., min_length=1, max_length=1000)
    specific_data_requested: list[str] = Field(default_factory=list)

    # Request Status
    status: str = Field(..., min_length=1, max_length=50)
    submitted_at: datetime = Field(...)
    acknowledgment_sent_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)

    # Identity Verification
    identity_verified: bool = Field(default=False)
    verification_method: str | None = Field(default=None, max_length=100)
    verification_documents: list[str] = Field(default_factory=list)

    # Processing Information
    assigned_to: str | None = Field(default=None, max_length=100)
    processing_notes: str | None = Field(default=None, max_length=2000)

    # Response Information
    response_method: str | None = Field(default=None, max_length=100)
    response_data: DataSubjectResponseData | None = Field(default=None)
    rejection_reason: str | None = Field(default=None, max_length=500)

    # Compliance Tracking
    due_date: datetime = Field(...)
    extension_granted: bool = Field(default=False)
    extension_reason: str | None = Field(default=None, max_length=500)

    # Communication Log
    communications: list[CommunicationRecord] = Field(default_factory=list)


# ============================================================================
# CONFIDENTIALITY CONTROL MODELS
# ============================================================================


class ConfidentialitySettings(BaseModel):
    """Confidentiality control settings replacing dict usage."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Control Identity
    control_id: str = Field(..., min_length=1, max_length=50)
    control_name: str = Field(..., min_length=1, max_length=200)
    control_type: str = Field(..., min_length=1, max_length=100)

    # Data Classification
    classification_scheme: str = Field(..., min_length=1, max_length=100)
    classification_levels: list[str] = Field(default_factory=list)
    default_classification: str = Field(..., min_length=1, max_length=50)

    # Access Control
    access_model: str = Field(..., min_length=1, max_length=50)  # RBAC, ABAC, etc.
    default_access_level: str = Field(..., min_length=1, max_length=50)
    least_privilege_enforced: bool = Field(default=True)

    # Data Protection
    encryption_required: bool = Field(default=True)
    encryption_algorithms: list[str] = Field(default_factory=list)
    key_management_system: str = Field(..., min_length=1, max_length=100)

    # Data Loss Prevention
    dlp_enabled: bool = Field(default=True)
    dlp_policies: list[str] = Field(default_factory=list)
    data_exfiltration_monitoring: bool = Field(default=True)

    # Masking and Anonymization
    data_masking_enabled: bool = Field(default=True)
    masking_techniques: list[str] = Field(default_factory=list)
    anonymization_required: bool = Field(default=False)

    # Retention and Disposal
    retention_policies: DataRetentionPolicies = Field(
        default_factory=lambda: DataRetentionPolicies()
    )
    secure_disposal_required: bool = Field(default=True)
    disposal_methods: list[str] = Field(default_factory=list)

    # Monitoring and Auditing
    access_monitoring: bool = Field(default=True)
    audit_logging: bool = Field(default=True)
    anomaly_detection: bool = Field(default=True)

    # Compliance Framework
    compliance_frameworks: list[str] = Field(default_factory=list)
    regulatory_requirements: list[str] = Field(default_factory=list)


class DataClassificationResult(BaseModel):
    """Data classification assessment result."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Assessment Identity
    assessment_id: UUID = Field(default_factory=uuid4)
    assessment_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    assessor: str = Field(..., min_length=1, max_length=100)

    # Coverage Analysis
    total_data_elements: int = Field(ge=0)
    classified_elements: int = Field(ge=0)
    unclassified_elements: int = Field(ge=0)
    coverage_percentage: float = Field(ge=0.0, le=100.0)

    # Classification Distribution
    classification_distribution: DataClassificationBreakdown = Field(
        default_factory=lambda: DataClassificationBreakdown()
    )

    # Accuracy Assessment
    sample_size: int = Field(ge=0)
    correctly_classified: int = Field(ge=0)
    misclassified: int = Field(ge=0)
    accuracy_percentage: float = Field(ge=0.0, le=100.0)

    # Issues and Recommendations
    unclassified_data: list[str] = Field(default_factory=list)
    misclassification_details: list[MisclassificationDetail] = Field(
        default_factory=list
    )
    recommendations: list[str] = Field(default_factory=list)

    # Compliance Status
    compliance_status: ComplianceStatus = Field(...)
    compliance_threshold: float = Field(ge=0.0, le=100.0)
    compliance_met: bool = Field(...)

    # Automated Systems
    automated_classification_enabled: bool = Field(default=False)
    automated_accuracy: float | None = Field(default=None, ge=0.0, le=100.0)
    false_positive_rate: float | None = Field(default=None, ge=0.0, le=100.0)
    false_negative_rate: float | None = Field(default=None, ge=0.0, le=100.0)


class AccessControlMatrixResult(BaseModel):
    """Access control matrix assessment result."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Assessment Identity
    assessment_id: UUID = Field(default_factory=uuid4)
    assessment_date: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    assessor: str = Field(..., min_length=1, max_length=100)

    # Access Matrix Analysis
    total_permissions: int = Field(ge=0)
    compliant_permissions: int = Field(ge=0)
    violations: int = Field(ge=0)
    compliance_percentage: float = Field(ge=0.0, le=100.0)

    # Violation Details
    violation_details: list[AccessViolationDetail] = Field(default_factory=list)
    violation_types: AccessViolationBreakdown = Field(
        default_factory=lambda: AccessViolationBreakdown()
    )

    # Least Privilege Analysis
    users_analyzed: int = Field(ge=0)
    users_compliant: int = Field(ge=0)
    excessive_permissions: int = Field(ge=0)
    least_privilege_compliance: float = Field(ge=0.0, le=100.0)

    # Role Analysis
    total_roles: int = Field(ge=0)
    valid_roles: int = Field(ge=0)
    invalid_role_assignments: list[str] = Field(default_factory=list)
    role_separation_violations: int = Field(ge=0)

    # Access Reviews
    users_requiring_review: int = Field(ge=0)
    completed_reviews: int = Field(ge=0)
    overdue_reviews: int = Field(ge=0)
    review_completion_rate: float = Field(ge=0.0, le=100.0)

    # Remediation
    remediation_required: bool = Field(default=False)
    high_risk_violations: int = Field(ge=0)
    remediation_recommendations: list[str] = Field(default_factory=list)

    # Compliance Status
    compliance_status: ComplianceStatus = Field(...)
    matrix_last_updated: datetime | None = Field(default=None)
    next_review_date: datetime | None = Field(default=None)


# ============================================================================
# EVIDENCE COLLECTION MODELS
# ============================================================================


class EvidenceItem(BaseModel):
    """Individual evidence item for compliance documentation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Evidence Identity
    evidence_id: UUID = Field(default_factory=uuid4)
    evidence_type: str = Field(..., min_length=1, max_length=100)
    title: str = Field(..., min_length=1, max_length=200)
    description: str = Field(..., min_length=1, max_length=1000)

    # Control Context
    control_id: str = Field(..., min_length=1, max_length=50)
    trust_service_criteria: TrustServiceCriterion = Field(...)

    # Evidence Content
    data_source: str = Field(..., min_length=1, max_length=200)
    collection_method: str = Field(..., min_length=1, max_length=100)
    evidence_data: EvidenceData = Field(default_factory=lambda: EvidenceData())

    # Temporal Information
    evidence_period_start: datetime = Field(...)
    evidence_period_end: datetime = Field(...)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Quality Attributes
    reliability: Literal["high", "medium", "low"] = Field(default="medium")
    completeness: Literal["complete", "partial", "incomplete"] = Field(
        default="partial"
    )
    relevance: Literal["directly_relevant", "relevant", "supporting"] = Field(
        default="relevant"
    )

    # Integrity and Authentication
    integrity_hash: str | None = Field(default=None, max_length=128)
    digital_signature: str | None = Field(default=None, max_length=512)
    chain_of_custody: list[str] = Field(default_factory=list)

    # Storage and Retention
    storage_location: str = Field(..., min_length=1, max_length=200)
    retention_period_days: int = Field(ge=1)
    disposal_date: datetime | None = Field(default=None)

    # Metadata
    collector: str = Field(..., min_length=1, max_length=100)
    reviewer: str | None = Field(default=None, max_length=100)
    approval_status: str = Field(default="pending")

    @field_validator("evidence_period_end")
    @classmethod
    def validate_period_end(cls, v: datetime, info: Any) -> datetime:
        """Validate that evidence period end is after start."""
        if hasattr(info, "data") and "evidence_period_start" in info.data:
            if v <= info.data["evidence_period_start"]:
                raise ValueError("Evidence period end must be after start")
        return v


class EvidenceCollection(BaseModel):
    """Collection of evidence items for compliance assessment."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Collection Identity
    collection_id: UUID = Field(default_factory=uuid4)
    collection_name: str = Field(..., min_length=1, max_length=200)
    collection_purpose: str = Field(..., min_length=1, max_length=500)

    # Evidence Items
    evidence_items: list[EvidenceItem] = Field(default_factory=list)
    total_items: int = Field(ge=0)

    # Quality Metrics
    high_reliability_items: int = Field(ge=0)
    complete_items: int = Field(ge=0)
    directly_relevant_items: int = Field(ge=0)

    # Coverage Analysis
    controls_covered: list[str] = Field(default_factory=list)
    criteria_coverage: CriteriaCoverageBreakdown = Field(
        default_factory=lambda: CriteriaCoverageBreakdown()
    )
    evidence_gaps: list[str] = Field(default_factory=list)

    # Collection Metadata
    collection_period_start: datetime = Field(...)
    collection_period_end: datetime = Field(...)
    collected_by: str = Field(..., min_length=1, max_length=100)
    reviewed_by: str | None = Field(default=None, max_length=100)

    # Compliance Assessment
    adequacy_assessment: Literal["adequate", "partially_adequate", "inadequate"] = (
        Field(...)
    )
    confidence_level: Literal["high", "medium", "low"] = Field(...)
    recommendations: list[str] = Field(default_factory=list)


# ============================================================================
# COMPLIANCE REPORTING MODELS
# ============================================================================


class ComplianceReport(BaseModel):
    """Comprehensive compliance report."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Report Identity
    report_id: UUID = Field(default_factory=uuid4)
    report_type: str = Field(..., min_length=1, max_length=100)
    report_title: str = Field(..., min_length=1, max_length=200)

    # Report Scope
    assessment_period_start: datetime = Field(...)
    assessment_period_end: datetime = Field(...)
    trust_service_criteria: list[TrustServiceCriterion] = Field(default_factory=list)

    # Overall Assessment
    overall_compliance_status: ComplianceStatus = Field(...)
    overall_compliance_score: float = Field(ge=0.0, le=100.0)

    # Detailed Results
    control_results: list[ControlTestResult] = Field(default_factory=list)
    evidence_collections: list[EvidenceCollection] = Field(default_factory=list)

    # Findings Summary
    total_findings: int = Field(ge=0)
    findings_by_severity: FindingsSeverityBreakdown = Field(
        default_factory=lambda: FindingsSeverityBreakdown()
    )
    critical_findings: list[ControlTestFinding] = Field(default_factory=list)

    # Recommendations
    management_recommendations: list[str] = Field(default_factory=list)
    technical_recommendations: list[str] = Field(default_factory=list)
    process_recommendations: list[str] = Field(default_factory=list)

    # Report Metadata
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    generated_by: str = Field(..., min_length=1, max_length=100)
    reviewed_by: str | None = Field(default=None, max_length=100)
    approved_by: str | None = Field(default=None, max_length=100)

    # Distribution
    distribution_list: list[str] = Field(default_factory=list)
    confidentiality_level: str = Field(default="confidential")

    # Version Control
    version: str = Field(default="1.0")
    previous_version: str | None = Field(default=None)
    change_summary: str | None = Field(default=None)


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================


@beartype
def create_audit_log_entry(
    event_type: str,
    action: str,
    user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    **kwargs: Any,
) -> AuditLogEntry:
    """Create a standardized audit log entry."""
    return AuditLogEntry(
        event_type=event_type,
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        **kwargs,
    )


@beartype
def create_control_test_result(
    control_id: str,
    test_name: str,
    test_type: str,
    test_result: str,
    executed_by: str,
    trust_service_criteria: TrustServiceCriterion,
    **kwargs: Any,
) -> ControlTestResult:
    """Create a standardized control test result."""
    return ControlTestResult(
        control_id=control_id,
        test_name=test_name,
        test_type=test_type,
        test_result=test_result,  # type: ignore
        executed_by=executed_by,
        trust_service_criteria=trust_service_criteria,
        **kwargs,
    )


@beartype
def create_evidence_item(
    evidence_type: str,
    title: str,
    description: str,
    control_id: str,
    trust_service_criteria: TrustServiceCriterion,
    evidence_period_start: datetime,
    evidence_period_end: datetime,
    **kwargs: Any,
) -> EvidenceItem:
    """Create a standardized evidence item."""
    return EvidenceItem(
        evidence_type=evidence_type,
        title=title,
        description=description,
        control_id=control_id,
        trust_service_criteria=trust_service_criteria,
        evidence_period_start=evidence_period_start,
        evidence_period_end=evidence_period_end,
        **kwargs,
    )
