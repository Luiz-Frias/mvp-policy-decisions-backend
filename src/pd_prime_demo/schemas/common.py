"""Common schemas used across the API."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Type variable for generic models
T = TypeVar("T")

# Additional models to replace dict usage


class AdditionalInfo(BaseModel):
    """Additional information key-value pairs."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    key: str = Field(..., min_length=1, max_length=100, description="Information key")
    value: str = Field(
        ..., min_length=1, max_length=1000, description="Information value"
    )


class ResourceLink(BaseModel):
    """Resource link information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    rel: str = Field(..., min_length=1, max_length=50, description="Link relation")
    href: str = Field(..., min_length=1, max_length=2000, description="Link URL")
    method: str = Field(default="GET", description="HTTP method for the link")
    title: str | None = Field(None, max_length=200, description="Link title")


class PaginationInfo(BaseModel):
    """Pagination information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    page: int = Field(..., ge=1, description="Current page number")
    per_page: int = Field(..., ge=1, le=1000, description="Items per page")
    total: int = Field(..., ge=0, description="Total number of items")
    pages: int = Field(..., ge=1, description="Total number of pages")
    has_next: bool = Field(..., description="Whether there are more pages")
    has_prev: bool = Field(..., description="Whether there are previous pages")


class MetadataItem(BaseModel):
    """Generic metadata item."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    key: str = Field(..., min_length=1, max_length=100, description="Metadata key")
    value: str | int | float | bool | None = Field(..., description="Metadata value")
    type: str = Field(default="string", description="Value type")


class ErrorContext(BaseModel):
    """Additional error context information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    request_id: str | None = Field(None, description="Request ID for correlation")
    user_id: str | None = Field(None, description="User ID associated with error")
    operation: str | None = Field(None, description="Operation being performed")
    resource_id: str | None = Field(None, description="Resource identifier")
    additional_info: list[AdditionalInfo] = Field(
        default_factory=list, description="Additional context info"
    )


class ResponseData(BaseModel, Generic[T]):
    """Generic response data structure."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    result: T | None = Field(None, description="Primary result data")
    metadata: list[MetadataItem] = Field(
        default_factory=list, description="Response metadata"
    )
    links: list[ResourceLink] = Field(
        default_factory=list, description="Related resource links"
    )
    pagination: PaginationInfo | None = Field(
        None, description="Pagination information"
    )


class OperationMetadata(BaseModel):
    """Operation metadata information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    operation_id: str | None = Field(None, description="Unique operation identifier")
    request_id: str | None = Field(None, description="Request tracking ID")
    execution_time_ms: float | None = Field(
        None, ge=0, description="Operation execution time"
    )
    cached: bool = Field(default=False, description="Whether result was cached")
    warnings: list[str] = Field(default_factory=list, description="Operation warnings")
    additional_data: list[MetadataItem] = Field(
        default_factory=list, description="Additional metadata"
    )


class APIInfo(BaseModel):
    """API information response."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    name: str = Field(..., description="API name")
    version: str = Field(..., description="API version")
    status: str = Field(..., description="API status")
    environment: str = Field(..., description="Environment name")


class PolicySummary(BaseModel):
    """Summary information for a policy."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: str = Field(..., description="Policy ID")
    policy_number: str = Field(..., description="Policy number")
    policy_type: str = Field(..., description="Policy type")
    status: str = Field(..., description="Policy status")
    effective_date: str = Field(..., description="Effective date ISO string")
    expiration_date: str = Field(..., description="Expiration date ISO string")


class HealthDetail(BaseModel):
    """Health check detail information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    status: str = Field(..., description="Component status")
    latency_ms: float | None = Field(None, description="Latency in milliseconds")
    error: str | None = Field(None, description="Error message if any")


class HealthMetadata(BaseModel):
    """Health check metadata."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    cpu_percent: float | None = Field(None, description="CPU usage percentage")
    memory_mb: float | None = Field(None, description="Memory usage in MB")
    uptime_seconds: float | None = Field(None, description="Uptime in seconds")
    connections: int | None = Field(None, description="Active connections")


class ErrorDetail(BaseModel):
    """Individual error detail."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    code: str = Field(..., description="Error code")
    message: str = Field(..., description="Error message")
    field: str | None = Field(None, description="Field that caused the error")
    context: ErrorContext | None = Field(None, description="Additional error context")


class ErrorResponse(BaseModel):
    """Standardized error response model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    error: bool = Field(True, description="Indicates this is an error response")
    status_code: int = Field(..., description="HTTP status code")
    message: str = Field(..., description="Primary error message")
    details: list[ErrorDetail] | None = Field(
        None, description="Detailed error information"
    )
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Error timestamp"
    )
    request_id: str | None = Field(None, description="Request ID for tracking")


class SuccessResponse(BaseModel, Generic[T]):
    """Standardized success response wrapper."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    success: bool = Field(True, description="Indicates successful operation")
    message: str = Field(..., description="Success message")
    data: ResponseData[T] | None = Field(None, description="Response data")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Response timestamp"
    )


class PaginatedResponse(BaseModel, Generic[T]):
    """Standardized paginated response wrapper."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    items: list[T] = Field(..., description="List of items")
    pagination: PaginationInfo = Field(..., description="Pagination information")
    metadata: list[MetadataItem] = Field(
        default_factory=list, description="Response metadata"
    )
    links: list[ResourceLink] = Field(
        default_factory=list, description="Related resource links"
    )


class ApiOperation(BaseModel):
    """Standard API operation result."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    operation_id: str = Field(..., description="Unique operation identifier")
    success: bool = Field(..., description="Operation success status")
    message: str = Field(..., description="Operation message")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Operation timestamp"
    )
    resource_id: str | None = Field(None, description="Created/modified resource ID")
    resource_type: str | None = Field(None, description="Resource type")
    metadata: OperationMetadata | None = Field(
        None, description="Additional operation metadata"
    )


# Common domain models for reuse across schemas


# SOC 2 Compliance Models - Structured Pydantic models (no dict usage)


class ControlExecutionDetails(BaseModel):
    """Structured control execution details."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    control_id: str = Field(..., min_length=1, description="Control identifier")
    execution_timestamp: datetime = Field(..., description="Execution timestamp")
    success: bool = Field(..., description="Execution success status")
    automated: bool = Field(default=True, description="Automated execution flag")
    criteria: str = Field(..., min_length=1, description="Trust service criteria")
    findings: list[str] = Field(default_factory=list, description="Execution findings")
    remediation_actions: list[str] = Field(
        default_factory=list, description="Remediation actions"
    )


class SystemDataEvidence(BaseModel):
    """Structured system data evidence."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    cpu_usage_percent: float | None = Field(
        None, ge=0.0, le=100.0, description="CPU usage"
    )
    memory_usage_mb: float | None = Field(
        None, ge=0.0, description="Memory usage in MB"
    )
    disk_usage_percent: float | None = Field(
        None, ge=0.0, le=100.0, description="Disk usage"
    )
    active_connections: int | None = Field(None, ge=0, description="Active connections")
    error_count: int | None = Field(None, ge=0, description="Error count")
    response_time_ms: float | None = Field(
        None, ge=0.0, description="Response time in ms"
    )
    uptime_seconds: int | None = Field(None, ge=0, description="Uptime in seconds")
    security_events: int | None = Field(None, ge=0, description="Security events count")
    backup_status: str | None = Field(None, description="Backup status")
    encryption_status: str | None = Field(None, description="Encryption status")
    access_control_status: str | None = Field(None, description="Access control status")
    audit_log_entries: int | None = Field(
        None, ge=0, description="Audit log entries count"
    )


class CollectionMetadata(BaseModel):
    """Structured evidence collection metadata."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    collector_id: str = Field(
        ..., min_length=1, description="Evidence collector identifier"
    )
    collection_timestamp: datetime = Field(..., description="Collection timestamp")
    collection_method: str = Field(..., min_length=1, description="Collection method")
    automated_collection: bool = Field(
        default=True, description="Automated collection flag"
    )
    data_source: str = Field(..., min_length=1, description="Data source identifier")
    collection_duration_ms: int = Field(
        ..., ge=0, description="Collection duration in ms"
    )
    data_completeness: bool = Field(default=True, description="Data completeness flag")
    validation_passed: bool = Field(default=True, description="Validation status")
    retention_period_days: int = Field(
        default=2555, ge=1, description="Retention period in days"
    )


class AdditionalEvidenceContext(BaseModel):
    """Structured additional evidence context."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    context_type: str = Field(..., min_length=1, description="Context type")
    business_process: str | None = Field(None, description="Related business process")
    risk_assessment: str | None = Field(None, description="Risk assessment level")
    compliance_framework: str | None = Field(None, description="Compliance framework")
    testing_approach: str | None = Field(None, description="Testing approach used")
    evidence_reliability: str = Field(
        default="high", description="Evidence reliability rating"
    )
    reviewer_notes: str | None = Field(None, description="Reviewer notes")
    quality_score: float | None = Field(
        None, ge=0.0, le=100.0, description="Quality score"
    )
    remediation_priority: str | None = Field(None, description="Remediation priority")
    stakeholder_impact: str | None = Field(None, description="Stakeholder impact")


class EvidenceContent(BaseModel):
    """Evidence content structure for SOC 2 compliance artifacts."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    control_execution: ControlExecutionDetails | None = Field(
        None, description="Control execution details"
    )
    system_data: SystemDataEvidence | None = Field(
        None, description="System data collected as evidence"
    )
    collection_metadata: CollectionMetadata = Field(
        ..., description="Evidence collection metadata"
    )
    data_integrity_hash: str | None = Field(
        None, description="Data integrity verification hash"
    )
    verification_status: str = Field(
        default="pending", description="Evidence verification status"
    )
    additional_context: AdditionalEvidenceContext | None = Field(
        None, description="Additional evidence context"
    )


class ComplianceScores(BaseModel):
    """Trust service criteria compliance scores."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    security: float = Field(..., ge=0.0, le=100.0, description="Security score")
    availability: float = Field(..., ge=0.0, le=100.0, description="Availability score")
    processing_integrity: float = Field(
        ..., ge=0.0, le=100.0, description="Processing integrity score"
    )
    confidentiality: float = Field(
        ..., ge=0.0, le=100.0, description="Confidentiality score"
    )
    privacy: float = Field(..., ge=0.0, le=100.0, description="Privacy score")
    overall_score: float = Field(
        ..., ge=0.0, le=100.0, description="Overall compliance score"
    )


class MetricsCollection(BaseModel):
    """Collection of compliance and system metrics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    total_controls: int = Field(..., ge=0, description="Total number of controls")
    active_controls: int = Field(..., ge=0, description="Active controls count")
    effective_controls: int = Field(..., ge=0, description="Effective controls count")
    ineffective_controls: int = Field(
        ..., ge=0, description="Ineffective controls count"
    )
    compliance_percentage: float = Field(
        ..., ge=0.0, le=100.0, description="Overall compliance percentage"
    )
    evidence_artifacts_count: int = Field(
        ..., ge=0, description="Total evidence artifacts"
    )
    last_assessment_date: datetime = Field(..., description="Last assessment timestamp")
    next_assessment_due: datetime = Field(..., description="Next assessment due date")
    high_risk_findings: int = Field(..., ge=0, description="High risk findings count")
    medium_risk_findings: int = Field(
        ..., ge=0, description="Medium risk findings count"
    )
    low_risk_findings: int = Field(..., ge=0, description="Low risk findings count")


class ControlEvidence(BaseModel):
    """Evidence collected from control execution."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    control_id: str = Field(..., min_length=1, max_length=50, description="Control ID")
    execution_id: str = Field(
        ..., min_length=1, max_length=100, description="Execution ID"
    )
    timestamp: datetime = Field(..., description="Execution timestamp")
    status: str = Field(
        ..., min_length=1, max_length=20, description="Execution status"
    )
    result: bool = Field(..., description="Control execution result")
    findings: list[str] = Field(default_factory=list, description="Control findings")
    evidence_items: list[str] = Field(
        default_factory=list, description="Evidence items collected"
    )
    execution_time_ms: int = Field(
        ..., ge=0, description="Execution time in milliseconds"
    )
    criteria: str = Field(
        ..., min_length=1, max_length=50, description="Trust service criteria"
    )
    automated: bool = Field(default=True, description="Whether control is automated")
    remediation_required: bool = Field(
        default=False, description="Whether remediation is required"
    )
    remediation_actions: list[str] = Field(
        default_factory=list, description="Remediation actions needed"
    )


class ComplianceFinding(BaseModel):
    """Individual compliance finding or deficiency."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    finding_id: str = Field(
        ..., min_length=1, max_length=20, description="Finding identifier"
    )
    severity: str = Field(
        ..., min_length=1, max_length=20, description="Finding severity level"
    )
    criteria: str = Field(
        ..., min_length=1, max_length=50, description="Trust service criteria"
    )
    control_id: str | None = Field(
        None, max_length=50, description="Related control ID"
    )
    title: str = Field(..., min_length=1, max_length=200, description="Finding title")
    description: str = Field(
        ..., min_length=1, max_length=2000, description="Finding description"
    )
    recommendation: str = Field(
        ..., min_length=1, max_length=1000, description="Recommendation"
    )
    risk_level: str = Field(..., min_length=1, max_length=20, description="Risk level")
    detected_at: datetime = Field(..., description="Detection timestamp")
    remediation_deadline: datetime | None = Field(
        None, description="Remediation deadline"
    )
    status: str = Field(
        default="open", min_length=1, max_length=20, description="Finding status"
    )
    assigned_to: str | None = Field(None, max_length=100, description="Assigned person")
    estimated_effort: str | None = Field(
        None, max_length=50, description="Estimated effort"
    )
    business_impact: str | None = Field(
        None, max_length=500, description="Business impact"
    )


class ComplianceRecommendation(BaseModel):
    """Compliance improvement recommendation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    recommendation_id: str = Field(
        ..., min_length=1, max_length=20, description="Recommendation ID"
    )
    priority: str = Field(
        ..., min_length=1, max_length=20, description="Priority level"
    )
    title: str = Field(
        ..., min_length=1, max_length=200, description="Recommendation title"
    )
    description: str = Field(
        ..., min_length=1, max_length=2000, description="Recommendation description"
    )
    category: str = Field(
        ..., min_length=1, max_length=50, description="Recommendation category"
    )
    estimated_effort: str | None = Field(
        None, max_length=50, description="Estimated effort"
    )
    responsible_party: str | None = Field(
        None, max_length=100, description="Responsible party"
    )
    target_completion: datetime | None = Field(
        None, description="Target completion date"
    )
    expected_benefit: str | None = Field(
        None, max_length=500, description="Expected benefit"
    )
    implementation_notes: str | None = Field(
        None, max_length=1000, description="Implementation notes"
    )
    dependencies: list[str] = Field(default_factory=list, description="Dependencies")
    status: str = Field(
        default="pending", min_length=1, max_length=20, description="Status"
    )


class ManagementResponse(BaseModel):
    """Management response to compliance findings."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    response_id: str = Field(
        ..., min_length=1, max_length=20, description="Response ID"
    )
    finding_id: str = Field(
        ..., min_length=1, max_length=20, description="Related finding ID"
    )
    response_date: datetime = Field(..., description="Response date")
    respondent: str = Field(
        ..., min_length=1, max_length=100, description="Respondent name"
    )
    response_text: str = Field(
        ..., min_length=1, max_length=2000, description="Response text"
    )
    agreed_action: str = Field(
        ..., min_length=1, max_length=1000, description="Agreed action"
    )
    target_date: datetime | None = Field(None, description="Target completion date")
    assigned_owner: str | None = Field(
        None, max_length=100, description="Assigned owner"
    )
    risk_acceptance: bool = Field(default=False, description="Risk acceptance flag")
    alternative_controls: list[str] = Field(
        default_factory=list, description="Alternative controls"
    )
    status: str = Field(
        default="pending", min_length=1, max_length=20, description="Response status"
    )


class EvidenceQualityMetrics(BaseModel):
    """Evidence quality assessment metrics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    completeness_score: float = Field(
        ..., ge=0.0, le=100.0, description="Evidence completeness score"
    )
    accuracy_score: float = Field(
        ..., ge=0.0, le=100.0, description="Evidence accuracy score"
    )
    timeliness_score: float = Field(
        ..., ge=0.0, le=100.0, description="Evidence timeliness score"
    )
    relevance_score: float = Field(
        ..., ge=0.0, le=100.0, description="Evidence relevance score"
    )
    integrity_verified: bool = Field(
        ..., description="Evidence integrity verification status"
    )
    source_reliability: float = Field(
        ..., ge=0.0, le=100.0, description="Source reliability score"
    )
    automated_collection_rate: float = Field(
        ..., ge=0.0, le=100.0, description="Automated collection rate"
    )
    manual_review_required: bool = Field(
        default=False, description="Manual review requirement"
    )
    retention_compliance: bool = Field(
        default=True, description="Retention policy compliance"
    )
    access_control_verified: bool = Field(
        default=True, description="Access control verification"
    )


class SystemDataMetrics(BaseModel):
    """System data and performance metrics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    cpu_usage_percent: float = Field(
        ..., ge=0.0, le=100.0, description="CPU usage percentage"
    )
    memory_usage_mb: float = Field(..., ge=0.0, description="Memory usage in MB")
    disk_usage_percent: float = Field(
        ..., ge=0.0, le=100.0, description="Disk usage percentage"
    )
    network_throughput_mbps: float = Field(
        ..., ge=0.0, description="Network throughput in Mbps"
    )
    active_connections: int = Field(..., ge=0, description="Active connections count")
    error_rate_percent: float = Field(
        ..., ge=0.0, le=100.0, description="Error rate percentage"
    )
    response_time_ms: float = Field(
        ..., ge=0.0, description="Average response time in ms"
    )
    uptime_percent: float = Field(
        ..., ge=0.0, le=100.0, description="System uptime percentage"
    )
    security_events_count: int = Field(..., ge=0, description="Security events count")
    backup_status: str = Field(
        ..., min_length=1, max_length=20, description="Backup status"
    )
    last_backup_time: datetime = Field(..., description="Last backup timestamp")
    sync_status: str = Field(
        ..., min_length=1, max_length=20, description="Synchronization status"
    )


class Money(BaseModel):
    """Money value with currency."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    amount: Decimal = Field(..., decimal_places=2, description="Monetary amount")
    currency: str = Field(
        default="USD", min_length=3, max_length=3, description="Currency code"
    )


class Address(BaseModel):
    """Standard address model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    street_address: str = Field(
        ..., min_length=1, max_length=200, description="Street address"
    )
    city: str = Field(..., min_length=1, max_length=100, description="City")
    state: str = Field(
        ..., min_length=2, max_length=50, description="State or province"
    )
    postal_code: str = Field(
        ..., min_length=1, max_length=20, description="Postal code"
    )
    country: str = Field(
        default="US", min_length=2, max_length=3, description="Country code"
    )


class ContactInfo(BaseModel):
    """Contact information model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    email: str | None = Field(None, max_length=320, description="Email address")
    phone: str | None = Field(None, max_length=20, description="Phone number")
    mobile: str | None = Field(None, max_length=20, description="Mobile number")


class DateRange(BaseModel):
    """Date range model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    start_date: datetime = Field(..., description="Start date")
    end_date: datetime = Field(..., description="End date")

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: datetime, info: Any) -> datetime:
        """Ensure end_date is after start_date."""
        if (
            hasattr(info, "data")
            and "start_date" in info.data
            and v <= info.data["start_date"]
        ):
            raise ValueError("end_date must be after start_date")
        return v


class Status(BaseModel):
    """Generic status model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    code: str = Field(..., min_length=1, max_length=50, description="Status code")
    name: str = Field(..., min_length=1, max_length=100, description="Status name")
    description: str | None = Field(
        None, max_length=500, description="Status description"
    )
    is_active: bool = Field(default=True, description="Whether status is active")


class Audit(BaseModel):
    """Audit trail information."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    created_by: str | None = Field(None, description="User who created the record")
    updated_at: datetime | None = Field(None, description="Last update timestamp")
    updated_by: str | None = Field(None, description="User who last updated the record")
    version: int = Field(default=1, ge=1, description="Record version number")


class ValidationResult(BaseModel):
    """Validation result model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    is_valid: bool = Field(..., description="Whether validation passed")
    errors: list[ErrorDetail] = Field(
        default_factory=list, description="Validation errors"
    )
    warnings: list[str] = Field(default_factory=list, description="Validation warnings")


class SearchCriteria(BaseModel):
    """Search criteria model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    query: str | None = Field(None, max_length=500, description="Search query")
    filters: list[MetadataItem] = Field(
        default_factory=list, description="Search filters"
    )
    sort_by: str | None = Field(None, max_length=100, description="Sort field")
    sort_order: str = Field(default="asc", description="Sort order (asc/desc)")
    page: int = Field(default=1, ge=1, description="Page number")
    per_page: int = Field(default=50, ge=1, le=1000, description="Items per page")
