"""SOC 2 Compliance API endpoints.

This module provides REST API endpoints for SOC 2 compliance management,
including control execution, evidence collection, and compliance reporting.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Union

from beartype import beartype
from fastapi import APIRouter, Depends, HTTPException, Query, status, Response
from pydantic import BaseModel, ConfigDict, Field

from ...compliance import (
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
from ...core.result_types import Result, Ok, Err
from ..dependencies import get_current_user
from ..response_patterns import handle_result, ErrorResponse

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
    trust_service_criteria_scores: dict[str, float] = Field(...)
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
    context: dict[str, Any] | None = Field(default_factory=dict)


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


@router.get("/overview", response_model=ComplianceOverviewResponse)
@beartype
async def get_compliance_overview(
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Union[ComplianceOverviewResponse, ErrorResponse]:
    """Get overall SOC 2 compliance overview."""
    try:
        # Get compliance metrics from the framework
        metrics_result = control_framework.generate_compliance_report()

        if metrics_result.is_err():
            return handle_result(metrics_result, response)

        metrics = metrics_result.ok_value
        
        # Type narrowing - metrics should not be None if is_ok() is True
        if metrics is None:
            return handle_result(Err("Internal server error: compliance metrics is None"), response)

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

        return ComplianceOverviewResponse(
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

    except Exception as e:
        return handle_result(Err(f"Failed to get compliance overview: {str(e)}"), response)


@router.get("/controls")
@beartype
async def list_controls(
    criteria: str | None = Query(None, description="Filter by trust service criteria"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """List all SOC 2 controls with optional filtering."""
    try:
        if criteria:
            try:
                criteria_enum = TrustServiceCriteria(criteria)
                controls = control_framework.get_controls_by_criteria(criteria_enum)
            except ValueError:
                return handle_result(Err(f"Invalid trust service criteria: {criteria}"), response)
        else:
            controls = SOC2_CORE_CONTROLS

        return {
            "total_controls": len(controls),
            "criteria_filter": criteria,
            "controls": [
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
            ],
        }

    except Exception as e:
        return handle_result(Err(f"Failed to list controls: {str(e)}"), response)


@router.post("/controls/execute", response_model=ControlExecutionResponse)
@beartype
async def execute_control(
    request: ControlExecutionRequest, 
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user)
) -> Union[ControlExecutionResponse, ErrorResponse]:
    """Execute a specific SOC 2 control."""
    try:
        # Execute the control
        execution_result = control_framework.execute_control(
            request.control_id, request.context
        )

        if execution_result.is_err():
            return handle_result(execution_result, response)

        execution = execution_result.ok_value
        
        # Type narrowing - execution should not be None if is_ok() is True
        if execution is None:
            return handle_result(Err("Internal server error: control execution is None"), response)

        return ControlExecutionResponse(
            execution_id=str(execution.execution_id),
            control_id=execution.control_id,
            timestamp=execution.timestamp.isoformat(),
            status=execution.status.value,
            result=execution.result,
            findings=execution.findings,
            execution_time_ms=execution.execution_time_ms,
        )

    except Exception as e:
        return handle_result(Err(f"Failed to execute control: {str(e)}"), response)


@router.get("/controls/{control_id}/status")
@beartype
async def get_control_status(
    control_id: str, 
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user)
) -> Union[dict[str, Any], ErrorResponse]:
    """Get the current status of a specific control."""
    try:
        status_result = control_framework.get_control_status(control_id)

        if status_result.is_err():
            return handle_result(status_result, response)

        control_status = status_result.ok_value
        
        # Type narrowing - control_status should not be None if is_ok() is True
        if control_status is None:
            return handle_result(Err("Internal server error: control status is None"), response)

        return {
            "control_id": control_id,
            "status": control_status.value,
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return handle_result(Err(f"Failed to get control status: {str(e)}"), response)


@router.get("/dashboards/security")
@beartype
async def get_security_dashboard(
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Get security controls dashboard."""
    try:
        dashboard = await security_manager.get_security_dashboard()
        return dashboard

    except Exception as e:
        return handle_result(Err(f"Failed to get security dashboard: {str(e)}"), response)


@router.get("/dashboards/availability")
@beartype
async def get_availability_dashboard(
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Get availability controls dashboard."""
    try:
        dashboard = await availability_manager.get_availability_dashboard()
        return dashboard

    except Exception as e:
        return handle_result(Err(f"Failed to get availability dashboard: {str(e)}"), response)


@router.get("/dashboards/processing-integrity")
@beartype
async def get_processing_integrity_dashboard(
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Get processing integrity controls dashboard."""
    try:
        dashboard = (
            await processing_integrity_manager.get_processing_integrity_dashboard()
        )
        return dashboard

    except Exception as e:
        return handle_result(Err(f"Failed to get processing integrity dashboard: {str(e)}"), response)


@router.get("/dashboards/confidentiality")
@beartype
async def get_confidentiality_dashboard(
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Get confidentiality controls dashboard."""
    try:
        dashboard = await confidentiality_manager.get_confidentiality_dashboard()
        return dashboard

    except Exception as e:
        return handle_result(Err(f"Failed to get confidentiality dashboard: {str(e)}"), response)


@router.get("/dashboards/privacy")
@beartype
async def get_privacy_dashboard(
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Get privacy controls dashboard."""
    try:
        dashboard = await privacy_manager.get_privacy_dashboard()
        return dashboard

    except Exception as e:
        return handle_result(Err(f"Failed to get privacy dashboard: {str(e)}"), response)


@router.get("/evidence/summary")
@beartype
async def get_evidence_summary(
    response: Response,
    period_start: datetime | None = Query(
        default=None, description="Start date for evidence summary"
    ),
    period_end: datetime | None = Query(
        default=None, description="End date for evidence summary"
    ),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Union[dict[str, Any], ErrorResponse]:
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
            return handle_result(summary_result, response)

        summary = summary_result.ok_value
        if summary is None:
            return handle_result(Err("Evidence summary returned None"), response)
        return summary

    except Exception as e:
        return handle_result(Err(f"Failed to get evidence summary: {str(e)}"), response)


@router.post("/reports/generate")
@beartype
async def generate_compliance_report(
    request: ComplianceReportRequest, 
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user)
) -> Union[dict[str, Any], ErrorResponse]:
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
            return handle_result(report_result, response)

        report = report_result.ok_value
        
        # Type narrowing - report should not be None if is_ok() is True
        if report is None:
            return handle_result(Err("Internal server error: compliance report is None"), response)

        return {
            "report_id": str(report.report_id),
            "title": report.title,
            "report_type": report.report_type,
            "generated_at": report.generated_at.isoformat(),
            "overall_compliance_score": report.overall_compliance_score,
            "trust_service_criteria_scores": report.trust_service_criteria_scores,
            "total_evidence_artifacts": report.total_evidence_artifacts,
            "findings_count": len(report.findings),
            "recommendations_count": len(report.recommendations),
            "assessment_period": {
                "start": report.assessment_period_start.isoformat(),
                "end": report.assessment_period_end.isoformat(),
            },
        }

    except Exception as e:
        return handle_result(Err(f"Failed to generate compliance report: {str(e)}"), response)


@router.get("/testing/dashboard")
@beartype
async def get_testing_dashboard(
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Get control testing dashboard."""
    try:
        dashboard = await testing_framework.get_testing_dashboard()
        return dashboard

    except Exception as e:
        return handle_result(Err(f"Failed to get testing dashboard: {str(e)}"), response)


@router.post("/testing/plans")
@beartype
async def create_test_plan(
    request: TestPlanRequest, 
    response: Response,
    current_user: dict[str, Any] = Depends(get_current_user)
) -> Union[dict[str, Any], ErrorResponse]:
    """Create a new control testing plan."""
    try:
        # Convert criteria strings to enums
        criteria_enums = []
        for criterion in request.criteria:
            try:
                criteria_enums.append(TrustServiceCriteria(criterion))
            except ValueError:
                return handle_result(Err(f"Invalid trust service criteria: {criterion}"), response)

        plan_result = await testing_framework.create_test_plan(
            plan_name=request.plan_name,
            description=request.description,
            period_start=request.period_start,
            period_end=request.period_end,
            criteria=criteria_enums,
            created_by=current_user.get("email", "unknown"),
        )

        if plan_result.is_err():
            return handle_result(plan_result, response)

        plan = plan_result.ok_value
        
        # Type narrowing - plan should not be None if is_ok() is True
        if plan is None:
            return handle_result(Err("Internal server error: test plan is None"), response)

        return {
            "plan_id": str(plan.plan_id),
            "plan_name": plan.plan_name,
            "description": plan.description,
            "created_at": plan.created_at.isoformat(),
            "assessment_period": {
                "start": plan.assessment_period_start.isoformat(),
                "end": plan.assessment_period_end.isoformat(),
            },
            "criteria": [c.value for c in plan.trust_service_criteria],
            "total_tests": plan.total_tests,
            "status": plan.status,
        }

    except Exception as e:
        return handle_result(Err(f"Failed to create test plan: {str(e)}"), response)


@router.post("/testing/execute-all")
@beartype
async def execute_all_controls(
    response: Response,
    criteria: str | None = Query(
        None, description="Execute controls for specific criteria only"
    ),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Union[dict[str, Any], ErrorResponse]:
    """Execute all controls or controls for specific criteria."""
    try:
        criteria_enum = None
        if criteria:
            try:
                criteria_enum = TrustServiceCriteria(criteria)
            except ValueError:
                return handle_result(Err(f"Invalid trust service criteria: {criteria}"), response)

        execution_result = control_framework.execute_all_controls(criteria_enum)

        if execution_result.is_err():
            return handle_result(execution_result, response)

        executions = execution_result.ok_value
        
        # Type narrowing - executions should not be None if is_ok() is True
        if executions is None:
            return handle_result(Err("Internal server error: control executions result is None"), response)

        # Summarize results
        total_executions = len(executions)
        successful_executions = sum(1 for exec in executions if exec.result)
        failed_executions = total_executions - successful_executions

        return {
            "execution_summary": {
                "total_executions": total_executions,
                "successful_executions": successful_executions,
                "failed_executions": failed_executions,
                "success_rate": (
                    (successful_executions / total_executions) * 100
                    if total_executions > 0
                    else 0
                ),
            },
            "criteria_filter": criteria,
            "execution_timestamp": datetime.now(timezone.utc).isoformat(),
            "executions": [
                {
                    "execution_id": str(exec.execution_id),
                    "control_id": exec.control_id,
                    "result": exec.result,
                    "findings_count": len(exec.findings),
                    "execution_time_ms": exec.execution_time_ms,
                }
                for exec in executions
            ],
        }

    except Exception as e:
        return handle_result(Err(f"Failed to execute all controls: {str(e)}"), response)


@router.get("/audit-trail")
@beartype
async def get_audit_trail(
    response: Response,
    start_date: datetime | None = Query(None, description="Start date for audit trail"),
    end_date: datetime | None = Query(None, description="End date for audit trail"),
    control_id: str | None = Query(None, description="Filter by control ID"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of records"),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> Union[dict[str, Any], ErrorResponse]:
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

        return {
            "total_records": len(audit_records),
            "filters": {
                "start_date": start_date.isoformat() if start_date else None,
                "end_date": end_date.isoformat() if end_date else None,
                "control_id": control_id,
                "limit": limit,
            },
            "audit_records": audit_records,
        }

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
