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
# AUDIT LOG MODELS
# ============================================================================

class AuditLogEntry(BaseModel):
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
    request_body: dict[str, Any] = Field(default_factory=dict)
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
    security_alerts: dict[str, Any] = Field(default_factory=dict)
    before_state: dict[str, Any] | None = Field(default=None)
    after_state: dict[str, Any] | None = Field(default=None)


class AuditTrailSummary(BaseModel):
    """Summary of audit trail for compliance reporting."""
    
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    
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
    likelihood: Literal["rare", "unlikely", "possible", "likely", "certain"] = Field(...)
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
    test_result: Literal["effective", "ineffective", "deficient", "not_applicable", "inconclusive"] = Field(...)
    effectiveness_score: float = Field(ge=0.0, le=100.0)
    
    # Findings and Evidence
    findings: list[ControlTestFinding] = Field(default_factory=list)
    evidence_collected: list[str] = Field(default_factory=list)
    evidence_quality: Literal["comprehensive", "adequate", "limited", "insufficient"] = Field(...)
    
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
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    findings_by_type: dict[str, int] = Field(default_factory=dict)
    
    # Compliance by Criteria
    compliance_by_criteria: dict[str, dict[str, Any]] = Field(default_factory=dict)
    
    # Trending Data
    testing_trends: dict[str, list[float]] = Field(default_factory=dict)
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
    enforcement_mode: Literal["strict", "lenient", "monitoring"] = Field(default="strict")
    thresholds: dict[str, float] = Field(default_factory=dict)
    
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
    alert_thresholds: dict[str, float] = Field(default_factory=dict)
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
    vulnerabilities_by_severity: dict[str, int] = Field(default_factory=dict)
    
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
    warning_thresholds: dict[str, float] = Field(default_factory=dict)
    critical_thresholds: dict[str, float] = Field(default_factory=dict)
    
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
    retention_periods: dict[str, int] = Field(default_factory=dict)
    
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
    response_data: dict[str, Any] | None = Field(default=None)
    rejection_reason: str | None = Field(default=None, max_length=500)
    
    # Compliance Tracking
    due_date: datetime = Field(...)
    extension_granted: bool = Field(default=False)
    extension_reason: str | None = Field(default=None, max_length=500)
    
    # Communication Log
    communications: list[dict[str, Any]] = Field(default_factory=list)
    

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
    retention_policies: dict[str, int] = Field(default_factory=dict)
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
    assessment_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assessor: str = Field(..., min_length=1, max_length=100)
    
    # Coverage Analysis
    total_data_elements: int = Field(ge=0)
    classified_elements: int = Field(ge=0)
    unclassified_elements: int = Field(ge=0)
    coverage_percentage: float = Field(ge=0.0, le=100.0)
    
    # Classification Distribution
    classification_distribution: dict[str, int] = Field(default_factory=dict)
    
    # Accuracy Assessment
    sample_size: int = Field(ge=0)
    correctly_classified: int = Field(ge=0)
    misclassified: int = Field(ge=0)
    accuracy_percentage: float = Field(ge=0.0, le=100.0)
    
    # Issues and Recommendations
    unclassified_data: list[str] = Field(default_factory=list)
    misclassification_details: list[dict[str, Any]] = Field(default_factory=list)
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
    assessment_date: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    assessor: str = Field(..., min_length=1, max_length=100)
    
    # Access Matrix Analysis
    total_permissions: int = Field(ge=0)
    compliant_permissions: int = Field(ge=0)
    violations: int = Field(ge=0)
    compliance_percentage: float = Field(ge=0.0, le=100.0)
    
    # Violation Details
    violation_details: list[dict[str, Any]] = Field(default_factory=list)
    violation_types: dict[str, int] = Field(default_factory=dict)
    
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
    evidence_data: dict[str, Any] = Field(default_factory=dict)
    
    # Temporal Information
    evidence_period_start: datetime = Field(...)
    evidence_period_end: datetime = Field(...)
    collected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    # Quality Attributes
    reliability: Literal["high", "medium", "low"] = Field(default="medium")
    completeness: Literal["complete", "partial", "incomplete"] = Field(default="partial")
    relevance: Literal["directly_relevant", "relevant", "supporting"] = Field(default="relevant")
    
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
        if hasattr(info, 'data') and 'evidence_period_start' in info.data:
            if v <= info.data['evidence_period_start']:
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
    criteria_coverage: dict[str, int] = Field(default_factory=dict)
    evidence_gaps: list[str] = Field(default_factory=list)
    
    # Collection Metadata
    collection_period_start: datetime = Field(...)
    collection_period_end: datetime = Field(...)
    collected_by: str = Field(..., min_length=1, max_length=100)
    reviewed_by: str | None = Field(default=None, max_length=100)
    
    # Compliance Assessment
    adequacy_assessment: Literal["adequate", "partially_adequate", "inadequate"] = Field(...)
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
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
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