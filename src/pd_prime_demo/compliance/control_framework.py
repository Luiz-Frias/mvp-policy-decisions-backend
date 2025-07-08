"""SOC 2 Control Framework - Central orchestration for all compliance controls.

This module provides the core framework for managing SOC 2 Type II compliance controls
across all five trust service criteria. It implements automated control testing,
evidence collection, and continuous monitoring.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List
from uuid import UUID, uuid4

from attrs import define, field, frozen
from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from ..services.result import Result


class TrustServiceCriteria(str, Enum):
    """SOC 2 Trust Service Criteria."""

    SECURITY = "security"
    AVAILABILITY = "availability"
    PROCESSING_INTEGRITY = "processing_integrity"
    CONFIDENTIALITY = "confidentiality"
    PRIVACY = "privacy"


class ControlType(str, Enum):
    """Types of compliance controls."""

    PREVENTIVE = "preventive"
    DETECTIVE = "detective"
    CORRECTIVE = "corrective"
    COMPENSATING = "compensating"


class ControlStatus(str, Enum):
    """Control execution status."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    FAILED = "failed"
    REMEDIATION = "remediation"
    TESTING = "testing"


@frozen
class ControlDefinition:
    """Immutable control definition."""

    control_id: str = field()
    name: str = field()
    description: str = field()
    criteria: TrustServiceCriteria = field()
    control_type: ControlType = field()
    objective: str = field()
    risk_level: str = field()  # "high", "medium", "low"
    frequency: str = field()  # "continuous", "daily", "weekly", "monthly"
    automated: bool = field(default=True)
    required_evidence: list[str] = field(factory=list)


class ControlExecution(BaseModel):
    """Control execution result with evidence."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    execution_id: UUID = Field(default_factory=uuid4)
    control_id: str = Field(..., min_length=1)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: ControlStatus = Field(...)
    result: bool = Field(...)
    evidence_collected: dict[str, Any] = Field(default_factory=dict)
    findings: list[str] = Field(default_factory=list)
    remediation_actions: list[str] = Field(default_factory=list)
    execution_time_ms: int = Field(ge=0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ComplianceMetrics(BaseModel):
    """Compliance program metrics."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    total_controls: int = Field(ge=0)
    active_controls: int = Field(ge=0)
    passing_controls: int = Field(ge=0)
    failing_controls: int = Field(ge=0)
    compliance_percentage: float = Field(ge=0.0, le=100.0)
    last_assessment: datetime = Field(...)
    high_risk_findings: int = Field(ge=0)
    medium_risk_findings: int = Field(ge=0)
    low_risk_findings: int = Field(ge=0)


@define
class ControlFramework:
    """Central SOC 2 compliance control framework."""

    _controls: dict[str, ControlDefinition] = field(factory=dict)
    _executions: list[ControlExecution] = field(factory=list)
    _audit_logger: Any = field(default=None)  # Will be injected

    @beartype
    def register_control(self, control: ControlDefinition):
        """Register a new compliance control."""
        try:
            if control.control_id in self._controls:
                return Result.err(f"Control {control.control_id} already registered")

            self._controls[control.control_id] = control

            if self._audit_logger:
                self._audit_logger.log_control_event(
                    "control_registered",
                    control_id=control.control_id,
                    metadata={"criteria": control.criteria.value},
                )

            return Result.ok(None)

        except Exception as e:
            return Result.err(f"Failed to register control: {str(e)}")

    @beartype
    def execute_control(self, control_id: str, context: dict[str, Any] | None = None):
        """Execute a compliance control and collect evidence."""
        try:
            if control_id not in self._controls:
                return Result.err(f"Control {control_id} not found")

            control = self._controls[control_id]
            start_time = datetime.now(timezone.utc)

            # Execute control based on type and criteria
            execution_result = self._execute_control_logic(control, context or {})

            end_time = datetime.now(timezone.utc)
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            execution = ControlExecution(
                control_id=control_id,
                timestamp=start_time,
                status=(
                    ControlStatus.ACTIVE
                    if execution_result["success"]
                    else ControlStatus.FAILED
                ),
                result=execution_result["success"],
                evidence_collected=execution_result.get("evidence", {}),
                findings=execution_result.get("findings", []),
                remediation_actions=execution_result.get("remediation", []),
                execution_time_ms=execution_time_ms,
                metadata={"context": context},
            )

            self._executions.append(execution)

            if self._audit_logger:
                self._audit_logger.log_control_execution(execution)

            return Result.ok(execution)

        except Exception as e:
            return Result.err(f"Control execution failed: {str(e)}")

    @beartype
    def _execute_control_logic(
        self, control: ControlDefinition, context: dict[str, Any]
    ) -> dict[str, Any]:
        """Execute control-specific logic based on criteria and type."""
        # This is the hook where specific control managers implement their logic
        # For now, return basic structure - specific implementations in control managers

        return {
            "success": True,
            "evidence": {
                "control_id": control.control_id,
                "execution_timestamp": datetime.now(timezone.utc).isoformat(),
                "criteria": control.criteria.value,
                "automated": control.automated,
            },
            "findings": [],
            "remediation": [],
        }

    @beartype
    def get_controls_by_criteria(
        self, criteria: TrustServiceCriteria
    ) -> list[ControlDefinition]:
        """Get all controls for a specific trust service criteria."""
        return [
            control
            for control in self._controls.values()
            if control.criteria == criteria
        ]

    @beartype
    def get_control_status(self, control_id: str):
        """Get current status of a control."""
        if control_id not in self._controls:
            return Result.err(f"Control {control_id} not found")

        # Get latest execution
        recent_executions = [
            exec for exec in self._executions if exec.control_id == control_id
        ]

        if not recent_executions:
            return Result.ok(ControlStatus.INACTIVE)

        latest_execution = max(recent_executions, key=lambda x: x.timestamp)
        return Result.ok(latest_execution.status)

    @beartype
    def generate_compliance_report(self):
        """Generate compliance metrics report."""
        try:
            total_controls = len(self._controls)

            if total_controls == 0:
                return Result.ok(
                    ComplianceMetrics(
                        total_controls=0,
                        active_controls=0,
                        passing_controls=0,
                        failing_controls=0,
                        compliance_percentage=0.0,
                        last_assessment=datetime.now(timezone.utc),
                        high_risk_findings=0,
                        medium_risk_findings=0,
                        low_risk_findings=0,
                    )
                )

            # Get latest execution for each control
            latest_executions = {}
            for execution in self._executions:
                control_id = execution.control_id
                if (
                    control_id not in latest_executions
                    or execution.timestamp > latest_executions[control_id].timestamp
                ):
                    latest_executions[control_id] = execution

            active_controls = len(latest_executions)
            passing_controls = sum(
                1 for exec in latest_executions.values() if exec.result
            )
            failing_controls = active_controls - passing_controls

            compliance_percentage = (
                (passing_controls / total_controls) * 100 if total_controls > 0 else 0.0
            )

            # Count findings by risk level
            high_risk_findings = 0
            medium_risk_findings = 0
            low_risk_findings = 0

            for execution in latest_executions.values():
                control = self._controls[execution.control_id]
                if not execution.result:
                    if control.risk_level == "high":
                        high_risk_findings += len(execution.findings)
                    elif control.risk_level == "medium":
                        medium_risk_findings += len(execution.findings)
                    else:
                        low_risk_findings += len(execution.findings)

            return Result.ok(
                ComplianceMetrics(
                    total_controls=total_controls,
                    active_controls=active_controls,
                    passing_controls=passing_controls,
                    failing_controls=failing_controls,
                    compliance_percentage=compliance_percentage,
                    last_assessment=datetime.now(timezone.utc),
                    high_risk_findings=high_risk_findings,
                    medium_risk_findings=medium_risk_findings,
                    low_risk_findings=low_risk_findings,
                )
            )

        except Exception as e:
            return Result.err(f"Failed to generate compliance report: {str(e)}")

    @beartype
    def get_failing_controls(self) -> list[ControlExecution]:
        """Get all controls that are currently failing."""
        latest_executions = {}
        for execution in self._executions:
            control_id = execution.control_id
            if (
                control_id not in latest_executions
                or execution.timestamp > latest_executions[control_id].timestamp
            ):
                latest_executions[control_id] = execution

        return [exec for exec in latest_executions.values() if not exec.result]

    @beartype
    def execute_all_controls(self, criteria: TrustServiceCriteria | None = None):
        """Execute all controls or controls for specific criteria."""
        try:
            controls_to_execute = (
                self.get_controls_by_criteria(criteria)
                if criteria
                else list(self._controls.values())
            )

            executions = []
            for control in controls_to_execute:
                result = self.execute_control(control.control_id)
                if result.is_ok():
                    executions.append(result.unwrap())
                else:
                    # Log but continue with other controls
                    if self._audit_logger:
                        self._audit_logger.log_error(
                            f"Control {control.control_id} execution failed",
                            error=result.unwrap_err(),
                        )

            return Result.ok(executions)

        except Exception as e:
            return Result.err(f"Bulk control execution failed: {str(e)}")


# Pre-defined SOC 2 controls
SOC2_CORE_CONTROLS = [
    # Security Controls
    ControlDefinition(
        control_id="SEC-001",
        name="Data Encryption at Rest",
        description="Ensure all sensitive data is encrypted using AES-256 encryption",
        criteria=TrustServiceCriteria.SECURITY,
        control_type=ControlType.PREVENTIVE,
        objective="Protect sensitive data from unauthorized access",
        risk_level="high",
        frequency="continuous",
        automated=True,
        required_evidence=["encryption_config", "key_management", "data_scan"],
    ),
    ControlDefinition(
        control_id="SEC-002",
        name="Transport Layer Security",
        description="Enforce TLS 1.3 for all data in transit",
        criteria=TrustServiceCriteria.SECURITY,
        control_type=ControlType.PREVENTIVE,
        objective="Secure data transmission",
        risk_level="high",
        frequency="continuous",
        automated=True,
        required_evidence=["tls_config", "certificate_validation", "traffic_analysis"],
    ),
    # Availability Controls
    ControlDefinition(
        control_id="AVL-001",
        name="Uptime Monitoring",
        description="Monitor system availability and maintain 99.9% uptime SLA",
        criteria=TrustServiceCriteria.AVAILABILITY,
        control_type=ControlType.DETECTIVE,
        objective="Ensure system availability meets SLA requirements",
        risk_level="high",
        frequency="continuous",
        automated=True,
        required_evidence=["uptime_metrics", "incident_reports", "sla_monitoring"],
    ),
    # Processing Integrity Controls
    ControlDefinition(
        control_id="PI-001",
        name="Data Validation",
        description="Validate all input data at system boundaries",
        criteria=TrustServiceCriteria.PROCESSING_INTEGRITY,
        control_type=ControlType.PREVENTIVE,
        objective="Ensure data accuracy and completeness",
        risk_level="medium",
        frequency="continuous",
        automated=True,
        required_evidence=["validation_logs", "error_rates", "data_quality_metrics"],
    ),
    # Confidentiality Controls
    ControlDefinition(
        control_id="CONF-001",
        name="Access Control Matrix",
        description="Implement role-based access control with least privilege",
        criteria=TrustServiceCriteria.CONFIDENTIALITY,
        control_type=ControlType.PREVENTIVE,
        objective="Restrict access to confidential information",
        risk_level="high",
        frequency="daily",
        automated=True,
        required_evidence=["access_logs", "permission_matrix", "role_definitions"],
    ),
    # Privacy Controls
    ControlDefinition(
        control_id="PRIV-001",
        name="GDPR Compliance Engine",
        description="Implement GDPR data protection and privacy rights",
        criteria=TrustServiceCriteria.PRIVACY,
        control_type=ControlType.PREVENTIVE,
        objective="Ensure privacy compliance and data protection",
        risk_level="high",
        frequency="continuous",
        automated=True,
        required_evidence=[
            "consent_records",
            "data_processing_logs",
            "privacy_impact_assessments",
        ],
    ),
]
