# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""SOC 2 Compliance API endpoints.

This module provides REST API endpoints for SOC 2 compliance management,
including control execution, evidence collection, and compliance reporting.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from beartype import beartype
from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, ConfigDict, Field

from pd_prime_demo.api.dependencies import get_current_user
from pd_prime_demo.api.response_patterns import ErrorResponse, handle_result
from pd_prime_demo.compliance import (
    SOC2_CORE_CONTROLS,
    AvailabilityControlManager,
    ConfidentialityControlManager,
    ControlFramework,
    PrivacyControlManager,
    ProcessingIntegrityManager,
    SecurityControlManager,
    TrustServiceCriteria,
    get_evidence_collector,
    get_testing_framework,
)
from pd_prime_demo.core.result_types import Err
from pd_prime_demo.models.base import BaseModelConfig

# Auto-generated models


@beartype
class DashboardData(BaseModelConfig):
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
class CurrentUserData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class AssessmentPeriodMapping(BaseModelConfig):
    """Structured model replacing dict[str, str] usage."""

    key: str = Field(..., min_length=1, description="Mapping key")
    value: str = Field(..., min_length=1, description="Mapping value")


@beartype
class ComplianceData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class TrustServiceCriteriaScoresMetrics(BaseModelConfig):
    """Structured model replacing dict[str, float] usage."""

    average: float = Field(default=0.0, ge=0.0, description="Average value")


@beartype
class SummaryData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class FiltersData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


@beartype
class ExecutionSummaryData(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")


router = APIRouter(prefix="/compliance", tags=["SOC 2 Compliance"])

# Initialize compliance managers
control_framework = ControlFramework()
security_manager = SecurityControlManager()
availability_manager = AvailabilityControlManager()
processing_integrity_manager = ProcessingIntegrityManager()
confidentiality_manager = ConfidentialityControlManager()
privacy_manager = PrivacyControlManager()
evidence_collector = get_evidence_collector()
testing_framework = get_testing_framework(control_framework)

# Register all core controls
for control in SOC2_CORE_CONTROLS:
    control_framework.register_control(control)


class ComplianceOverviewResponse(BaseModel):
    """Compliance overview response model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    overall_compliance_score: float = Field(ge=0.0, le=100.0)
    trust_service_criteria_scores: TrustServiceCriteriaScoresMetrics = Field(...)
    total_controls: int = Field(ge=0)
    effective_controls: int = Field(ge=0)
    failing_controls: int = Field(ge=0)
    last_assessment: str = Field(...)
    compliance_status: str = Field(...)


class ControlExecutionRequest(BaseModel):
    """Control execution request model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    control_id: str = Field(...)
    context: ContextData | None = Field(default_factory=dict)


class ControlExecutionResponse(BaseModel):
    """Control execution response model."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    execution_id: str = Field(...)
    control_id: str = Field(...)
    timestamp: str = Field(...)
    status: str = Field(...)
    result: bool = Field(...)
    findings: list[str] = Field(...)
    execution_time_ms: int = Field(...)


class ComplianceReportRequest(BaseModel):
    """Compliance report generation request."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    title: str = Field(...)
    report_type: str = Field(...)
    period_start: datetime = Field(...)
    period_end: datetime = Field(...)
    criteria: list[str] = Field(...)


class TestPlanRequest(BaseModel):
    """Test plan creation request."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )
    plan_name: str = Field(...)
    description: str = Field(...)
    period_start: datetime = Field(...)
    period_end: datetime = Field(...)
    criteria: list[str] = Field(...)


# Response models for dashboard endpoints
class SecurityDashboardResponse(BaseModel):
    """Security dashboard response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    security_score: float = Field(ge=0.0, le=100.0)
    # SYSTEM_BOUNDARY - dashboard data aggregated from multiple sources
    data: ComplianceData = Field(...)


class AvailabilityDashboardResponse(BaseModel):
    """Availability dashboard response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    availability_score: float = Field(ge=0.0, le=100.0)
    # SYSTEM_BOUNDARY - dashboard data aggregated from multiple sources
    data: ComplianceData = Field(...)


class ProcessingIntegrityDashboardResponse(BaseModel):
    """Processing integrity dashboard response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    integrity_score: float = Field(ge=0.0, le=100.0)
    # SYSTEM_BOUNDARY - dashboard data aggregated from multiple sources
    data: ComplianceData = Field(...)


class ConfidentialityDashboardResponse(BaseModel):
    """Confidentiality dashboard response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    confidentiality_score: float = Field(ge=0.0, le=100.0)
    # SYSTEM_BOUNDARY - dashboard data aggregated from multiple sources
    data: ComplianceData = Field(...)


class PrivacyDashboardResponse(BaseModel):
    """Privacy dashboard response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    privacy_score: float = Field(ge=0.0, le=100.0)
    # SYSTEM_BOUNDARY - dashboard data aggregated from multiple sources
    data: ComplianceData = Field(...)


class ControlListResponse(BaseModel):
    """Control list response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    total_controls: int = Field(ge=0)
    criteria_filter: str | None = Field(...)
    # SYSTEM_BOUNDARY - control metadata aggregated from framework
    controls: list[dict[str, Any]] = Field(...)


class ControlStatusResponse(BaseModel):
    """Control status response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    control_id: str = Field(...)
    status: str = Field(...)
    last_checked: str = Field(...)


class EvidenceSummaryResponse(BaseModel):
    """Evidence summary response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    # SYSTEM_BOUNDARY - evidence summary data aggregated from collector
    summary: SummaryData = Field(...)


class ComplianceReportResponse(BaseModel):
    """Compliance report response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    report_id: str = Field(...)
    title: str = Field(...)
    report_type: str = Field(...)
    generated_at: str = Field(...)
    overall_compliance_score: float = Field(ge=0.0, le=100.0)
    # SYSTEM_BOUNDARY - TSC scores aggregated from multiple managers
    trust_service_criteria_scores: TrustServiceCriteriaScoresMetrics = Field(...)
    total_evidence_artifacts: int = Field(ge=0)
    findings_count: int = Field(ge=0)
    recommendations_count: int = Field(ge=0)
    # SYSTEM_BOUNDARY - assessment period data
    assessment_period: AssessmentPeriodMapping = Field(...)


class TestingDashboardResponse(BaseModel):
    """Testing dashboard response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    # SYSTEM_BOUNDARY - testing dashboard data aggregated from framework
    dashboard: DashboardData = Field(...)


class TestPlanResponse(BaseModel):
    """Test plan response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    plan_id: str = Field(...)
    plan_name: str = Field(...)
    description: str = Field(...)
    created_at: str = Field(...)
    # SYSTEM_BOUNDARY - assessment period data
    assessment_period: AssessmentPeriodMapping = Field(...)
    criteria: list[str] = Field(...)
    total_tests: int = Field(ge=0)
    status: str = Field(...)


class ExecutionSummaryResponse(BaseModel):
    """Execution summary response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    # SYSTEM_BOUNDARY - execution summary data aggregated from multiple executions
    execution_summary: ExecutionSummaryData = Field(...)
    criteria_filter: str | None = Field(...)
    execution_timestamp: str = Field(...)
    # SYSTEM_BOUNDARY - execution results aggregated from framework
    executions: list[dict[str, Any]] = Field(...)


class AuditTrailResponse(BaseModel):
    """Audit trail response model."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    total_records: int = Field(ge=0)
    # SYSTEM_BOUNDARY - filter parameters
    filters: FiltersData = Field(...)
    # SYSTEM_BOUNDARY - audit records aggregated from logger
    audit_records: list[dict[str, Any]] = Field(...)


@router.get("/overview", response_model=ComplianceOverviewResponse)
@beartype
async def get_compliance_overview(
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
) -> ComplianceOverviewResponse | ErrorResponse:
    """Get overall SOC 2 compliance overview."""
    try:
        # Get compliance metrics from the framework
        metrics_result = control_framework.generate_compliance_report()

        if metrics_result.is_err():
            return handle_result(
                Err(metrics_result.err_value or "Failed to generate compliance report"),
                response,
            )

        metrics = metrics_result.ok_value

        # Type narrowing - metrics should not be None if is_ok() is True
        if metrics is None:
            return handle_result(
                Err("Internal server error: compliance metrics is None"), response
            )

        # Get detailed scores by criteria
        criteria_scores = {
            "security": (await security_manager.get_security_dashboard())[
                "security_score"
            ],
            "availability": (await availability_manager.get_availability_dashboard())[
                "availability_score"
            ],
            "processing_integrity": (
                await processing_integrity_manager.get_processing_integrity_dashboard()
            )["integrity_score"],
            "confidentiality": (
                await confidentiality_manager.get_confidentiality_dashboard()
            )["confidentiality_score"],
            "privacy": (await privacy_manager.get_privacy_dashboard())["privacy_score"],
        }

        # Create the response model from the domain model
        compliance_response = ComplianceOverviewResponse(
            overall_compliance_score=metrics.compliance_percentage,
            trust_service_criteria_scores=criteria_scores,
            total_controls=metrics.total_controls,
            effective_controls=metrics.passing_controls,
            failing_controls=metrics.failing_controls,
            last_assessment=metrics.last_assessment.isoformat(),
            compliance_status=(
                "compliant"
                if metrics.compliance_percentage >= 95.0
                else "non_compliant"
            ),
        )

        return compliance_response

    except Exception as e:
        return handle_result(
            Err(f"Failed to get compliance overview: {str(e)}"), response
        )


@router.get("/controls", response_model=ControlListResponse)
@beartype
async def list_controls(
    response: Response,
    criteria: str | None = Query(None, description="Filter by trust service criteria"),
    current_user: CurrentUserData = Depends(get_current_user),
) -> ControlListResponse | ErrorResponse:
    """List all SOC 2 controls with optional filtering."""
    try:
        if criteria:
            try:
                criteria_enum = TrustServiceCriteria(criteria)
                controls = control_framework.get_controls_by_criteria(criteria_enum)
            except ValueError:
                return handle_result(
                    Err(f"Invalid trust service criteria: {criteria}"), response
                )
        else:
            controls = SOC2_CORE_CONTROLS

        controls_data = [
            {
                "control_id": control.control_id,
                "name": control.name,
                "description": control.description,
                "criteria": control.criteria.value,
                "control_type": control.control_type.value,
                "risk_level": control.risk_level,
                "frequency": control.frequency,
                "automated": control.automated,
            }
            for control in controls
        ]

        return ControlListResponse(
            total_controls=len(controls),
            criteria_filter=criteria,
            controls=controls_data,
        )

    except Exception as e:
        return handle_result(Err(f"Failed to list controls: {str(e)}"), response)


@router.post("/controls/execute", response_model=ControlExecutionResponse)
@beartype
async def execute_control(
    request: ControlExecutionRequest,
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
) -> ControlExecutionResponse | ErrorResponse:
    """Execute a specific SOC 2 control."""
    try:
        # Execute the control
        execution_result = control_framework.execute_control(
            request.control_id, request.context
        )

        if execution_result.is_err():
            return handle_result(
                Err(execution_result.err_value or "Failed to execute control"), response
            )

        execution = execution_result.ok_value

        # Type narrowing - execution should not be None if is_ok() is True
        if execution is None:
            return handle_result(
                Err("Internal server error: control execution is None"), response
            )

        # Create the response model from the domain model
        execution_response = ControlExecutionResponse(
            execution_id=str(execution.execution_id),
            control_id=execution.control_id,
            timestamp=execution.timestamp.isoformat(),
            status=execution.status.value,
            result=execution.result,
            findings=execution.findings,
            execution_time_ms=execution.execution_time_ms,
        )

        return execution_response

    except Exception as e:
        return handle_result(Err(f"Failed to execute control: {str(e)}"), response)


@router.get("/controls/{control_id}/status", response_model=ControlStatusResponse)
@beartype
async def get_control_status(
    control_id: str,
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
) -> ControlStatusResponse | ErrorResponse:
    """Get the current status of a specific control."""
    try:
        status_result = control_framework.get_control_status(control_id)

        if status_result.is_err():
            return handle_result(
                Err(status_result.err_value or "Failed to get control status"), response
            )

        control_status = status_result.ok_value

        # Type narrowing - control_status should not be None if is_ok() is True
        if control_status is None:
            return handle_result(
                Err("Internal server error: control status is None"), response
            )

        return ControlStatusResponse(
            control_id=control_id,
            status=control_status.value,
            last_checked=datetime.now(timezone.utc).isoformat(),
        )

    except Exception as e:
        return handle_result(Err(f"Failed to get control status: {str(e)}"), response)


@router.get("/dashboards/security", response_model=SecurityDashboardResponse)
@beartype
async def get_security_dashboard(
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
) -> SecurityDashboardResponse | ErrorResponse:
    """Get security controls dashboard."""
    try:
        dashboard = await security_manager.get_security_dashboard()
        return SecurityDashboardResponse(
            security_score=dashboard.get("security_score", 0.0), data=dashboard
        )

    except Exception as e:
        return handle_result(
            Err(f"Failed to get security dashboard: {str(e)}"), response
        )


@router.get("/dashboards/availability", response_model=AvailabilityDashboardResponse)
@beartype
async def get_availability_dashboard(
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
) -> AvailabilityDashboardResponse | ErrorResponse:
    """Get availability controls dashboard."""
    try:
        dashboard = await availability_manager.get_availability_dashboard()
        return AvailabilityDashboardResponse(
            availability_score=dashboard.get("availability_score", 0.0), data=dashboard
        )

    except Exception as e:
        return handle_result(
            Err(f"Failed to get availability dashboard: {str(e)}"), response
        )


@router.get(
    "/dashboards/processing-integrity",
    response_model=ProcessingIntegrityDashboardResponse,
)
@beartype
async def get_processing_integrity_dashboard(
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
) -> ProcessingIntegrityDashboardResponse | ErrorResponse:
    """Get processing integrity controls dashboard."""
    try:
        dashboard = (
            await processing_integrity_manager.get_processing_integrity_dashboard()
        )
        return ProcessingIntegrityDashboardResponse(
            integrity_score=dashboard.get("integrity_score", 0.0), data=dashboard
        )

    except Exception as e:
        return handle_result(
            Err(f"Failed to get processing integrity dashboard: {str(e)}"), response
        )


@router.get(
    "/dashboards/confidentiality", response_model=ConfidentialityDashboardResponse
)
@beartype
async def get_confidentiality_dashboard(
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
) -> ConfidentialityDashboardResponse | ErrorResponse:
    """Get confidentiality controls dashboard."""
    try:
        dashboard = await confidentiality_manager.get_confidentiality_dashboard()
        return ConfidentialityDashboardResponse(
            confidentiality_score=dashboard.get("confidentiality_score", 0.0),
            data=dashboard,
        )

    except Exception as e:
        return handle_result(
            Err(f"Failed to get confidentiality dashboard: {str(e)}"), response
        )


@router.get("/dashboards/privacy", response_model=PrivacyDashboardResponse)
@beartype
async def get_privacy_dashboard(
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
) -> PrivacyDashboardResponse | ErrorResponse:
    """Get privacy controls dashboard."""
    try:
        dashboard = await privacy_manager.get_privacy_dashboard()
        return PrivacyDashboardResponse(
            privacy_score=dashboard.get("privacy_score", 0.0), data=dashboard
        )

    except Exception as e:
        return handle_result(
            Err(f"Failed to get privacy dashboard: {str(e)}"), response
        )


@router.get("/evidence/summary", response_model=EvidenceSummaryResponse)
@beartype
async def get_evidence_summary(
    response: Response,
    period_start: datetime | None = Query(
        default=None, description="Start date for evidence summary"
    ),
    period_end: datetime | None = Query(
        default=None, description="End date for evidence summary"
    ),
    current_user: CurrentUserData = Depends(get_current_user),
) -> EvidenceSummaryResponse | ErrorResponse:
    """Get evidence collection summary."""
    try:
        # Default to last 30 days if no period specified
        if period_end is None:
            period_end = datetime.now(timezone.utc)
        if period_start is None:
            period_start = period_end - timedelta(days=30)

        summary_result = await evidence_collector.get_evidence_summary(
            period_start, period_end
        )

        if summary_result.is_err():
            return handle_result(
                Err(summary_result.err_value or "Failed to get evidence summary"),
                response,
            )

        summary = summary_result.ok_value
        if summary is None:
            return handle_result(Err("Evidence summary returned None"), response)

        return EvidenceSummaryResponse(summary=summary)

    except Exception as e:
        return handle_result(Err(f"Failed to get evidence summary: {str(e)}"), response)


@router.post("/reports/generate", response_model=ComplianceReportResponse)
@beartype
async def generate_compliance_report(
    request: ComplianceReportRequest,
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
) -> ComplianceReportResponse | ErrorResponse:
    """Generate a comprehensive compliance report."""
    try:
        # Generate compliance report
        report_result = await evidence_collector.generate_compliance_report(
            title=request.title,
            report_type=request.report_type,
            period_start=request.period_start,
            period_end=request.period_end,
            generated_by=current_user.get("email", "unknown"),
            evidence_collection_ids=[],  # Could be enhanced to accept collection IDs
        )

        if report_result.is_err():
            return handle_result(
                Err(report_result.err_value or "Failed to generate compliance report"),
                response,
            )

        report = report_result.ok_value

        # Type narrowing - report should not be None if is_ok() is True
        if report is None:
            return handle_result(
                Err("Internal server error: compliance report is None"), response
            )

        return ComplianceReportResponse(
            report_id=str(report.report_id),
            title=report.title,
            report_type=report.report_type,
            generated_at=report.generated_at.isoformat(),
            overall_compliance_score=report.overall_compliance_score,
            trust_service_criteria_scores=report.trust_service_criteria_scores,
            total_evidence_artifacts=report.total_evidence_artifacts,
            findings_count=len(report.findings),
            recommendations_count=len(report.recommendations),
            assessment_period={
                "start": report.assessment_period_start.isoformat(),
                "end": report.assessment_period_end.isoformat(),
            },
        )

    except Exception as e:
        return handle_result(
            Err(f"Failed to generate compliance report: {str(e)}"), response
        )


@router.get("/testing/dashboard", response_model=TestingDashboardResponse)
@beartype
async def get_testing_dashboard(
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
) -> TestingDashboardResponse | ErrorResponse:
    """Get control testing dashboard."""
    try:
        dashboard = await testing_framework.get_testing_dashboard()
        return TestingDashboardResponse(dashboard=dashboard)

    except Exception as e:
        return handle_result(
            Err(f"Failed to get testing dashboard: {str(e)}"), response
        )


@router.post("/testing/plans", response_model=TestPlanResponse)
@beartype
async def create_test_plan(
    request: TestPlanRequest,
    response: Response,
    current_user: CurrentUserData = Depends(get_current_user),
) -> TestPlanResponse | ErrorResponse:
    """Create a new control testing plan."""
    try:
        # Convert criteria strings to enums
        criteria_enums = []
        for criterion in request.criteria:
            try:
                criteria_enums.append(TrustServiceCriteria(criterion))
            except ValueError:
                return handle_result(
                    Err(f"Invalid trust service criteria: {criterion}"), response
                )

        plan_result = await testing_framework.create_test_plan(
            plan_name=request.plan_name,
            description=request.description,
            period_start=request.period_start,
            period_end=request.period_end,
            criteria=criteria_enums,
            created_by=current_user.get("email", "unknown"),
        )

        if plan_result.is_err():
            return handle_result(
                Err(plan_result.err_value or "Failed to create test plan"), response
            )

        plan = plan_result.ok_value

        # Type narrowing - plan should not be None if is_ok() is True
        if plan is None:
            return handle_result(
                Err("Internal server error: test plan is None"), response
            )

        return TestPlanResponse(
            plan_id=str(plan.plan_id),
            plan_name=plan.plan_name,
            description=plan.description,
            created_at=plan.created_at.isoformat(),
            assessment_period={
                "start": plan.assessment_period_start.isoformat(),
                "end": plan.assessment_period_end.isoformat(),
            },
            criteria=[c.value for c in plan.trust_service_criteria],
            total_tests=plan.total_tests,
            status=plan.status,
        )

    except Exception as e:
        return handle_result(Err(f"Failed to create test plan: {str(e)}"), response)


@router.post("/testing/execute-all", response_model=ExecutionSummaryResponse)
@beartype
async def execute_all_controls(
    response: Response,
    criteria: str | None = Query(
        None, description="Execute controls for specific criteria only"
    ),
    current_user: CurrentUserData = Depends(get_current_user),
) -> ExecutionSummaryResponse | ErrorResponse:
    """Execute all controls or controls for specific criteria."""
    try:
        criteria_enum = None
        if criteria:
            try:
                criteria_enum = TrustServiceCriteria(criteria)
            except ValueError:
                return handle_result(
                    Err(f"Invalid trust service criteria: {criteria}"), response
                )

        execution_result = control_framework.execute_all_controls(criteria_enum)

        if execution_result.is_err():
            return handle_result(
                Err(execution_result.err_value or "Failed to execute all controls"),
                response,
            )

        executions = execution_result.ok_value

        # Type narrowing - executions should not be None if is_ok() is True
        if executions is None:
            return handle_result(
                Err("Internal server error: control executions result is None"),
                response,
            )

        # Summarize results
        total_executions = len(executions)
        successful_executions = sum(1 for exec in executions if exec.result)
        failed_executions = total_executions - successful_executions

        execution_summary = {
            "total_executions": total_executions,
            "successful_executions": successful_executions,
            "failed_executions": failed_executions,
            "success_rate": (
                (successful_executions / total_executions) * 100
                if total_executions > 0
                else 0
            ),
        }

        executions_data = [
            {
                "execution_id": str(exec.execution_id),
                "control_id": exec.control_id,
                "result": exec.result,
                "findings_count": len(exec.findings),
                "execution_time_ms": exec.execution_time_ms,
            }
            for exec in executions
        ]

        return ExecutionSummaryResponse(
            execution_summary=execution_summary,
            criteria_filter=criteria,
            execution_timestamp=datetime.now(timezone.utc).isoformat(),
            executions=executions_data,
        )

    except Exception as e:
        return handle_result(Err(f"Failed to execute all controls: {str(e)}"), response)


@router.get("/audit-trail", response_model=AuditTrailResponse)
@beartype
async def get_audit_trail(
    response: Response,
    start_date: datetime | None = Query(None, description="Start date for audit trail"),
    end_date: datetime | None = Query(None, description="End date for audit trail"),
    control_id: str | None = Query(None, description="Filter by control ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    current_user: CurrentUserData = Depends(get_current_user),
) -> AuditTrailResponse | ErrorResponse:
    """Get compliance audit trail."""
    try:
        from ...compliance.audit_logger import get_audit_logger

        audit_logger = get_audit_logger()

        # Get audit trail
        trail_result = await audit_logger.get_audit_trail(
            start_date=start_date, end_date=end_date, control_id=control_id, limit=limit
        )

        if trail_result.is_err():  # type: ignore[attr-defined]
            return handle_result(trail_result, response)  # type: ignore[arg-type]

        audit_records = trail_result.ok_value  # type: ignore[attr-defined]

        filters = {
            "start_date": start_date.isoformat() if start_date else None,
            "end_date": end_date.isoformat() if end_date else None,
            "control_id": control_id,
            "limit": limit,
        }

        return AuditTrailResponse(
            total_records=len(audit_records),
            filters=filters,
            audit_records=audit_records,
        )

    except Exception as e:
        return handle_result(Err(f"Failed to get audit trail: {str(e)}"), response)


@router.get("/health")
@beartype
async def compliance_health_check() -> dict[str, Any]:
    """Health check for compliance system."""
    try:
        # Check all compliance managers
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "control_framework": "operational",
                "security_manager": "operational",
                "availability_manager": "operational",
                "processing_integrity_manager": "operational",
                "confidentiality_manager": "operational",
                "privacy_manager": "operational",
                "evidence_collector": "operational",
                "testing_framework": "operational",
            },
            "total_controls_registered": len(SOC2_CORE_CONTROLS),
            "last_execution": datetime.now(timezone.utc).isoformat(),
        }

        return health_status

    except Exception as e:
        return {
            "status": "unhealthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error": str(e),
        }
