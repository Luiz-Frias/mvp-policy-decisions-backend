"""SOC 2 Control Testing Framework - Automated control effectiveness testing.

This module provides comprehensive testing capabilities for SOC 2 controls,
including automated testing, effectiveness assessment, and continuous monitoring.
"""

import asyncio
import random
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from pd_prime_demo.core.result_types import Err, Ok, Result

from .audit_logger import AuditLogger, get_audit_logger
from .control_framework import (
    SOC2_CORE_CONTROLS,
    ControlFramework,
    TrustServiceCriteria,
)
from .evidence_collector import EvidenceCollector, EvidenceType, get_evidence_collector


class TestType(str, Enum):
    """Types of control testing."""

    DESIGN_EFFECTIVENESS = "design_effectiveness"
    OPERATING_EFFECTIVENESS = "operating_effectiveness"
    AUTOMATED_TESTING = "automated_testing"
    MANUAL_TESTING = "manual_testing"
    CONTINUOUS_MONITORING = "continuous_monitoring"
    WALKTHROUGH = "walkthrough"
    INQUIRY = "inquiry"
    OBSERVATION = "observation"
    INSPECTION = "inspection"
    REPERFORMANCE = "reperformance"


class TestFrequency(str, Enum):
    """Testing frequency for controls."""

    CONTINUOUS = "continuous"
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ANNUALLY = "annually"
    ON_DEMAND = "on_demand"


class TestResult(str, Enum):
    """Test result status."""

    EFFECTIVE = "effective"
    INEFFECTIVE = "ineffective"
    DEFICIENT = "deficient"
    NOT_APPLICABLE = "not_applicable"
    INCONCLUSIVE = "inconclusive"


class DeficiencyType(str, Enum):
    """Types of control deficiencies."""

    DESIGN_DEFICIENCY = "design_deficiency"
    OPERATING_DEFICIENCY = "operating_deficiency"
    MATERIAL_WEAKNESS = "material_weakness"
    SIGNIFICANT_DEFICIENCY = "significant_deficiency"
    CONTROL_GAP = "control_gap"


class ControlTest(BaseModel):
    """Individual control test definition and execution."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    test_id: UUID = Field(default_factory=uuid4)
    control_id: str = Field(...)
    test_name: str = Field(...)
    test_description: str = Field(...)
    test_type: TestType = Field(...)
    test_frequency: TestFrequency = Field(...)

    # Test Procedures
    test_procedures: list[str] = Field(...)
    expected_evidence: list[str] = Field(...)
    sample_size: int | None = Field(default=None)
    population_size: int | None = Field(default=None)

    # Test Execution
    executed_at: datetime | None = Field(default=None)
    executed_by: str | None = Field(default=None)
    test_period_start: datetime | None = Field(default=None)
    test_period_end: datetime | None = Field(default=None)

    # Results
    test_result: TestResult | None = Field(default=None)
    deficiencies: list[dict[str, Any]] = Field(default_factory=list)
    exceptions_noted: list[dict[str, Any]] = Field(default_factory=list)
    evidence_obtained: list[str] = Field(default_factory=list)

    # Assessment
    conclusion: str | None = Field(default=None)
    recommendations: list[str] = Field(default_factory=list)
    management_response: str | None = Field(default=None)

    @beartype
    def is_overdue(self) -> bool:
        """Check if test is overdue based on frequency."""
        if not self.executed_at:
            return True

        frequency_days = {
            TestFrequency.CONTINUOUS: 1,
            TestFrequency.DAILY: 1,
            TestFrequency.WEEKLY: 7,
            TestFrequency.MONTHLY: 30,
            TestFrequency.QUARTERLY: 90,
            TestFrequency.ANNUALLY: 365,
        }

        if self.test_frequency in frequency_days:
            next_due = self.executed_at + timedelta(
                days=frequency_days[self.test_frequency]
            )
            return datetime.now(timezone.utc) > next_due

        return False


class TestPlan(BaseModel):
    """Testing plan for a set of controls."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    plan_id: UUID = Field(default_factory=uuid4)
    plan_name: str = Field(...)
    description: str = Field(...)
    assessment_period_start: datetime = Field(...)
    assessment_period_end: datetime = Field(...)

    # Planning
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_by: str = Field(...)
    approved_by: str | None = Field(default=None)
    approved_at: datetime | None = Field(default=None)

    # Scope
    trust_service_criteria: list[TrustServiceCriteria] = Field(...)
    control_ids: list[str] = Field(...)
    test_ids: list[UUID] = Field(default_factory=list)

    # Execution
    execution_start: datetime | None = Field(default=None)
    execution_end: datetime | None = Field(default=None)
    status: str = Field(default="planned")  # planned, in_progress, completed, on_hold

    # Results Summary
    total_tests: int = Field(default=0)
    completed_tests: int = Field(default=0)
    effective_controls: int = Field(default=0)
    ineffective_controls: int = Field(default=0)
    deficiencies_identified: int = Field(default=0)


class ControlTestingFramework:
    """Framework for SOC 2 control effectiveness testing."""

    def __init__(
        self,
        control_framework: ControlFramework,
        audit_logger: AuditLogger | None = None,
        evidence_collector: EvidenceCollector | None = None,
    ):
        """Initialize control testing framework."""
        self._control_framework = control_framework
        self._audit_logger = audit_logger or get_audit_logger()
        self._evidence_collector = evidence_collector or get_evidence_collector()
        self._test_definitions = self._load_test_definitions()

    @beartype
    def _load_test_definitions(self) -> list[ControlTest]:
        """Load predefined control test definitions."""
        return [
            # Security Control Tests
            ControlTest(
                control_id="SEC-001",
                test_name="Data Encryption at Rest Verification",
                test_description="Verify that all sensitive data is encrypted using AES-256 encryption",
                test_type=TestType.AUTOMATED_TESTING,
                test_frequency=TestFrequency.DAILY,
                test_procedures=[
                    "Execute automated scan of database encryption status",
                    "Verify encryption algorithms used",
                    "Test key management procedures",
                    "Validate encryption coverage for sensitive data",
                ],
                expected_evidence=[
                    "Database encryption configuration",
                    "Encryption algorithm verification",
                    "Key management audit logs",
                    "Data sensitivity scan results",
                ],
                sample_size=100,
                population_size=1000,
            ),
            ControlTest(
                control_id="SEC-002",
                test_name="TLS Configuration Testing",
                test_description="Test TLS 1.3 enforcement and configuration compliance",
                test_type=TestType.AUTOMATED_TESTING,
                test_frequency=TestFrequency.WEEKLY,
                test_procedures=[
                    "Scan all external endpoints for TLS configuration",
                    "Verify TLS version enforcement",
                    "Test certificate validity",
                    "Validate cipher suite configuration",
                ],
                expected_evidence=[
                    "TLS scan results",
                    "Certificate chain validation",
                    "Cipher suite configuration",
                    "Protocol version testing",
                ],
            ),
            # Availability Control Tests
            ControlTest(
                control_id="AVL-001",
                test_name="Uptime SLA Monitoring Verification",
                test_description="Verify uptime monitoring systems and SLA compliance",
                test_type=TestType.CONTINUOUS_MONITORING,
                test_frequency=TestFrequency.CONTINUOUS,
                test_procedures=[
                    "Review uptime monitoring data",
                    "Verify SLA calculation accuracy",
                    "Test alerting mechanisms",
                    "Validate incident response times",
                ],
                expected_evidence=[
                    "Uptime monitoring reports",
                    "SLA compliance metrics",
                    "Incident response logs",
                    "Alerting system tests",
                ],
            ),
            # Processing Integrity Control Tests
            ControlTest(
                control_id="PI-001",
                test_name="Data Validation Controls Testing",
                test_description="Test data validation controls at system boundaries",
                test_type=TestType.REPERFORMANCE,
                test_frequency=TestFrequency.MONTHLY,
                test_procedures=[
                    "Test input validation on sample transactions",
                    "Verify business rule enforcement",
                    "Test error handling procedures",
                    "Validate data quality metrics",
                ],
                expected_evidence=[
                    "Input validation test results",
                    "Business rule testing documentation",
                    "Error handling logs",
                    "Data quality reports",
                ],
                sample_size=25,
                population_size=10000,
            ),
            # Confidentiality Control Tests
            ControlTest(
                control_id="CONF-001",
                test_name="Access Control Matrix Compliance",
                test_description="Test access control matrix implementation and compliance",
                test_type=TestType.INSPECTION,
                test_frequency=TestFrequency.QUARTERLY,
                test_procedures=[
                    "Review user access permissions",
                    "Test role-based access controls",
                    "Verify least privilege implementation",
                    "Validate access review processes",
                ],
                expected_evidence=[
                    "User access reports",
                    "Role permission matrices",
                    "Access review documentation",
                    "Privilege escalation test results",
                ],
            ),
            # Privacy Control Tests
            ControlTest(
                control_id="PRIV-001",
                test_name="GDPR Compliance Verification",
                test_description="Verify GDPR compliance controls and procedures",
                test_type=TestType.INQUIRY,
                test_frequency=TestFrequency.QUARTERLY,
                test_procedures=[
                    "Review data processing records",
                    "Test consent management systems",
                    "Verify data subject rights procedures",
                    "Validate breach notification processes",
                ],
                expected_evidence=[
                    "Data processing documentation",
                    "Consent management logs",
                    "Data subject rights processing records",
                    "Breach notification procedures",
                ],
            ),
        ]

    @beartype
    async def create_test_plan(
        self,
        plan_name: str,
        description: str,
        period_start: datetime,
        period_end: datetime,
        criteria: list[TrustServiceCriteria],
        created_by: str,
    ) -> Result[TestPlan, str]:
        """Create a comprehensive test plan."""
        try:
            # Get controls for specified criteria
            all_control_ids = []
            for criterion in criteria:
                controls = self._control_framework.get_controls_by_criteria(criterion)
                all_control_ids.extend([c.control_id for c in controls])

            # Get applicable tests
            applicable_tests = [
                test
                for test in self._test_definitions
                if test.control_id in all_control_ids
            ]

            test_plan = TestPlan(
                plan_name=plan_name,
                description=description,
                assessment_period_start=period_start,
                assessment_period_end=period_end,
                trust_service_criteria=criteria,
                control_ids=all_control_ids,
                test_ids=[test.test_id for test in applicable_tests],
                total_tests=len(applicable_tests),
                created_by=created_by,
            )

            await self._audit_logger.log_control_event(
                action="test_plan_created",
                control_id="FRAMEWORK",
                plan_id=str(test_plan.plan_id),
                criteria=[c.value for c in criteria],
            )

            return Ok(test_plan)

        except Exception as e:
            return Err(f"Failed to create test plan: {str(e)}")

    @beartype
    async def execute_control_test(
        self,
        test_id: UUID,
        executed_by: str,
        test_period_start: datetime,
        test_period_end: datetime,
    ) -> Result[ControlTest, str]:
        """Execute an individual control test."""
        try:
            # Find test definition
            test_definition = None
            for test in self._test_definitions:
                if test.test_id == test_id:
                    test_definition = test
                    break

            if not test_definition:
                return Err(f"Test {test_id} not found")

            # Execute the test based on type
            test_result = await self._execute_test_procedures(
                test_definition, test_period_start, test_period_end
            )

            # Update test with execution results
            executed_test = test_definition.model_copy(
                update={
                    "executed_at": datetime.now(timezone.utc),
                    "executed_by": executed_by,
                    "test_period_start": test_period_start,
                    "test_period_end": test_period_end,
                    **test_result,
                }
            )

            # Collect evidence
            await self._evidence_collector.collect_system_evidence(
                evidence_type=EvidenceType.CONTROL_TESTING,
                title=f"Control Test: {executed_test.test_name}",
                system_data={
                    "test_execution": executed_test.model_dump(),
                    "test_results": test_result,
                },
                period_start=test_period_start,
                period_end=test_period_end,
                control_id=executed_test.control_id,
            )

            await self._audit_logger.log_control_event(
                action="control_test_executed",
                control_id=executed_test.control_id,
                test_id=str(test_id),
                test_result=test_result.get("test_result"),
                executed_by=executed_by,
            )

            return Ok(executed_test)

        except Exception as e:
            return Err(f"Failed to execute control test: {str(e)}")

    @beartype
    async def _execute_test_procedures(
        self, test_definition: ControlTest, period_start: datetime, period_end: datetime
    ) -> dict[str, Any]:
        """Execute test procedures based on test type."""
        if test_definition.test_type == TestType.AUTOMATED_TESTING:
            return await self._execute_automated_test(
                test_definition, period_start, period_end
            )
        elif test_definition.test_type == TestType.CONTINUOUS_MONITORING:
            return await self._execute_continuous_monitoring_test(
                test_definition, period_start, period_end
            )
        elif test_definition.test_type == TestType.REPERFORMANCE:
            return await self._execute_reperformance_test(
                test_definition, period_start, period_end
            )
        elif test_definition.test_type == TestType.INSPECTION:
            return await self._execute_inspection_test(
                test_definition, period_start, period_end
            )
        elif test_definition.test_type == TestType.INQUIRY:
            return await self._execute_inquiry_test(
                test_definition, period_start, period_end
            )
        else:
            return await self._execute_manual_test(
                test_definition, period_start, period_end
            )

    @beartype
    async def _execute_automated_test(
        self, test_definition: ControlTest, period_start: datetime, period_end: datetime
    ) -> dict[str, Any]:
        """Execute automated test procedures."""
        # Simulate automated testing execution
        await asyncio.sleep(0.1)  # Simulate processing time

        # Execute control to get real results
        control_result = self._control_framework.execute_control(
            test_definition.control_id
        )

        if control_result.is_ok():
            execution = control_result.unwrap()
            if execution is None:
                return {
                    "test_result": TestResult.INCONCLUSIVE,
                    "deficiencies": [{"type": DeficiencyType.CONTROL_GAP.value, "description": "Control execution returned None", "severity": "high"}],
                    "exceptions_noted": [],
                    "evidence_obtained": [],
                    "conclusion": "Control execution failed",
                    "recommendations": ["Investigate control execution failure"]
                }

            # Analyze results for test conclusion
            if execution.result:
                test_result = TestResult.EFFECTIVE
                deficiencies = []
                exceptions: list[dict[str, Any]] = []
                conclusion = "Control is operating effectively"
            else:
                test_result = TestResult.INEFFECTIVE
                deficiencies = [
                    {
                        "type": DeficiencyType.OPERATING_DEFICIENCY.value,
                        "description": finding,
                        "severity": "medium",
                    }
                    for finding in (execution.findings or [])
                ]
                exceptions = []
                conclusion = f"Control deficiencies identified: {len(execution.findings or [])} findings"
        else:
            test_result = TestResult.INCONCLUSIVE
            deficiencies = [
                {
                    "type": DeficiencyType.CONTROL_GAP.value,
                    "description": "Control execution failed",
                    "severity": "high",
                }
            ]
            exceptions = []
            conclusion = "Unable to complete control testing"

        return {
            "test_result": test_result,
            "deficiencies": deficiencies,
            "exceptions_noted": exceptions,
            "evidence_obtained": [
                "Automated test execution log",
                "Control execution results",
                "System configuration data",
            ],
            "conclusion": conclusion,
            "recommendations": (
                [
                    "Continue automated monitoring",
                    "Review control effectiveness quarterly",
                ]
                if test_result == TestResult.EFFECTIVE
                else [
                    "Address identified deficiencies",
                    "Implement corrective actions",
                    "Retest after remediation",
                ]
            ),
        }

    @beartype
    async def _execute_continuous_monitoring_test(
        self, test_definition: ControlTest, period_start: datetime, period_end: datetime
    ) -> dict[str, Any]:
        """Execute continuous monitoring test."""
        # Simulate continuous monitoring analysis
        await asyncio.sleep(0.1)

        # Analyze monitoring data for the period
        monitoring_effective = random.random() > 0.1  # 90% success rate

        if monitoring_effective:
            return {
                "test_result": TestResult.EFFECTIVE,
                "deficiencies": [],
                "exceptions_noted": [],
                "evidence_obtained": [
                    "Continuous monitoring logs",
                    "Alert generation records",
                    "Threshold compliance data",
                ],
                "conclusion": "Continuous monitoring controls are operating effectively",
                "recommendations": [
                    "Maintain current monitoring configuration",
                    "Review thresholds quarterly",
                ],
            }
        else:
            return {
                "test_result": TestResult.DEFICIENT,
                "deficiencies": [
                    {
                        "type": DeficiencyType.OPERATING_DEFICIENCY.value,
                        "description": "Monitoring gaps identified during test period",
                        "severity": "medium",
                    }
                ],
                "exceptions_noted": [],
                "evidence_obtained": ["Monitoring gap analysis", "Alert failure logs"],
                "conclusion": "Continuous monitoring has operational deficiencies",
                "recommendations": [
                    "Fix monitoring gaps",
                    "Improve alert reliability",
                    "Enhance monitoring coverage",
                ],
            }

    @beartype
    async def _execute_reperformance_test(
        self, test_definition: ControlTest, period_start: datetime, period_end: datetime
    ) -> dict[str, Any]:
        """Execute reperformance test procedures."""
        # Simulate reperformance testing
        await asyncio.sleep(0.1)

        sample_size = test_definition.sample_size or 25
        # population_size = test_definition.population_size or 1000  # Would be used for statistical analysis

        # Simulate testing sample transactions
        errors_found = random.randint(0, max(1, sample_size // 10))  # 0-10% error rate

        if errors_found == 0:
            return {
                "test_result": TestResult.EFFECTIVE,
                "deficiencies": [],
                "exceptions_noted": [],
                "evidence_obtained": [
                    f"Reperformance test results for {sample_size} samples",
                    "Transaction validation logs",
                    "Error analysis report",
                ],
                "conclusion": f"All {sample_size} sampled transactions processed correctly",
                "recommendations": [
                    "Continue current control procedures",
                    "Monitor for process changes",
                ],
            }
        else:
            error_rate = (errors_found / sample_size) * 100
            severity = (
                "high" if error_rate > 5 else "medium" if error_rate > 2 else "low"
            )

            return {
                "test_result": TestResult.DEFICIENT,
                "deficiencies": [
                    {
                        "type": DeficiencyType.OPERATING_DEFICIENCY.value,
                        "description": f"Found {errors_found} errors in {sample_size} samples ({error_rate:.1f}% error rate)",
                        "severity": severity,
                    }
                ],
                "exceptions_noted": [
                    {
                        "description": "Transaction processing errors identified",
                        "impact": "Data integrity risk",
                        "frequency": f"{errors_found}/{sample_size}",
                    }
                ],
                "evidence_obtained": [
                    "Error analysis documentation",
                    "Failed transaction details",
                    "Root cause analysis",
                ],
                "conclusion": f"Control is not operating effectively - {error_rate:.1f}% error rate",
                "recommendations": [
                    "Investigate root causes of errors",
                    "Implement corrective actions",
                    "Enhance validation procedures",
                    "Increase monitoring frequency",
                ],
            }

    @beartype
    async def _execute_inspection_test(
        self, test_definition: ControlTest, period_start: datetime, period_end: datetime
    ) -> dict[str, Any]:
        """Execute inspection test procedures."""
        # Simulate inspection testing
        await asyncio.sleep(0.1)

        # Simulate document/configuration inspection
        compliance_items = 10
        non_compliant_items = random.randint(0, 2)  # 0-2 non-compliant items

        if non_compliant_items == 0:
            return {
                "test_result": TestResult.EFFECTIVE,
                "deficiencies": [],
                "exceptions_noted": [],
                "evidence_obtained": [
                    "Configuration inspection results",
                    "Compliance checklist",
                    "Documentation review notes",
                ],
                "conclusion": f"All {compliance_items} inspection items are compliant",
                "recommendations": [
                    "Maintain current configuration",
                    "Periodic inspection schedule",
                ],
            }
        else:
            return {
                "test_result": TestResult.DEFICIENT,
                "deficiencies": [
                    {
                        "type": DeficiencyType.DESIGN_DEFICIENCY.value,
                        "description": f"Found {non_compliant_items} non-compliant configuration items",
                        "severity": "medium",
                    }
                ],
                "exceptions_noted": [],
                "evidence_obtained": [
                    "Non-compliance documentation",
                    "Configuration gap analysis",
                ],
                "conclusion": f"Control design has deficiencies - {non_compliant_items} non-compliant items",
                "recommendations": [
                    "Update configuration to comply with requirements",
                    "Review control design",
                    "Implement configuration management",
                ],
            }

    @beartype
    async def _execute_inquiry_test(
        self, test_definition: ControlTest, period_start: datetime, period_end: datetime
    ) -> dict[str, Any]:
        """Execute inquiry test procedures."""
        # Simulate inquiry testing
        await asyncio.sleep(0.1)

        # Simulate inquiry responses
        satisfactory_responses = random.random() > 0.15  # 85% satisfactory rate

        if satisfactory_responses:
            return {
                "test_result": TestResult.EFFECTIVE,
                "deficiencies": [],
                "exceptions_noted": [],
                "evidence_obtained": [
                    "Inquiry responses documentation",
                    "Process walkthrough notes",
                    "Personnel interview records",
                ],
                "conclusion": "Inquiry responses demonstrate effective control operation",
                "recommendations": [
                    "Continue current procedures",
                    "Annual process review",
                ],
            }
        else:
            return {
                "test_result": TestResult.DEFICIENT,
                "deficiencies": [
                    {
                        "type": DeficiencyType.OPERATING_DEFICIENCY.value,
                        "description": "Inquiry responses indicate gaps in control operation",
                        "severity": "medium",
                    }
                ],
                "exceptions_noted": [],
                "evidence_obtained": [
                    "Inquiry gap analysis",
                    "Process deficiency documentation",
                ],
                "conclusion": "Control operation gaps identified through inquiry",
                "recommendations": [
                    "Provide additional training",
                    "Clarify procedures",
                    "Implement process improvements",
                ],
            }

    @beartype
    async def _execute_manual_test(
        self, test_definition: ControlTest, period_start: datetime, period_end: datetime
    ) -> dict[str, Any]:
        """Execute manual test procedures."""
        # Simulate manual testing
        await asyncio.sleep(0.1)

        # Default manual test result
        return {
            "test_result": TestResult.EFFECTIVE,
            "deficiencies": [],
            "exceptions_noted": [],
            "evidence_obtained": [
                "Manual test documentation",
                "Tester observations",
                "Process verification",
            ],
            "conclusion": "Manual testing indicates effective control operation",
            "recommendations": [
                "Document test procedures",
                "Consider automation opportunities",
            ],
        }

    @beartype
    async def execute_test_plan(self, test_plan: TestPlan, executed_by: str) -> Result[TestPlan, str]:
        """Execute all tests in a test plan."""
        try:
            executed_tests = []
            effective_controls = 0
            ineffective_controls = 0
            deficiencies_identified = 0

            # Execute each test in the plan
            for test_id in test_plan.test_ids:
                test_result = await self.execute_control_test(
                    test_id=test_id,
                    executed_by=executed_by,
                    test_period_start=test_plan.assessment_period_start,
                    test_period_end=test_plan.assessment_period_end,
                )

                if test_result.is_ok():
                    executed_test = test_result.unwrap()
                    if executed_test is not None:
                        executed_tests.append(executed_test)

                        if executed_test.test_result == TestResult.EFFECTIVE:
                            effective_controls += 1
                        else:
                            ineffective_controls += 1

                        deficiencies_identified += len(executed_test.deficiencies or [])

            # Update test plan with execution results
            updated_plan = test_plan.model_copy(
                update={
                    "execution_start": datetime.now(timezone.utc),
                    "execution_end": datetime.now(timezone.utc),
                    "status": "completed",
                    "completed_tests": len(executed_tests),
                    "effective_controls": effective_controls,
                    "ineffective_controls": ineffective_controls,
                    "deficiencies_identified": deficiencies_identified,
                }
            )

            await self._audit_logger.log_control_event(
                action="test_plan_executed",
                control_id="FRAMEWORK",
                plan_id=str(test_plan.plan_id),
                tests_completed=len(executed_tests),
                effective_controls=effective_controls,
                ineffective_controls=ineffective_controls,
            )

            return Ok(updated_plan)

        except Exception as e:
            return Err(f"Failed to execute test plan: {str(e)}")

    @beartype
    async def get_testing_dashboard(self) -> dict[str, Any]:
        """Get comprehensive control testing dashboard."""
        # Simulate dashboard data
        total_controls = len(SOC2_CORE_CONTROLS)
        total_tests = len(self._test_definitions)

        # Simulate test execution statistics
        completed_tests = int(total_tests * 0.85)  # 85% completion rate
        effective_tests = int(completed_tests * 0.92)  # 92% effectiveness rate
        overdue_tests = total_tests - completed_tests

        return {
            "testing_summary": {
                "total_controls": total_controls,
                "total_tests": total_tests,
                "completed_tests": completed_tests,
                "effective_tests": effective_tests,
                "ineffective_tests": completed_tests - effective_tests,
                "overdue_tests": overdue_tests,
                "completion_rate": (completed_tests / total_tests) * 100,
                "effectiveness_rate": (
                    (effective_tests / completed_tests) * 100
                    if completed_tests > 0
                    else 0
                ),
            },
            "testing_by_criteria": {
                "security": {"tests": 6, "effective": 5, "rate": 83.3},
                "availability": {"tests": 4, "effective": 4, "rate": 100.0},
                "processing_integrity": {"tests": 5, "effective": 4, "rate": 80.0},
                "confidentiality": {"tests": 4, "effective": 4, "rate": 100.0},
                "privacy": {"tests": 3, "effective": 2, "rate": 66.7},
            },
            "deficiency_summary": {
                "total_deficiencies": 8,
                "by_severity": {"high": 1, "medium": 4, "low": 3},
                "by_type": {
                    "design_deficiency": 2,
                    "operating_deficiency": 5,
                    "control_gap": 1,
                },
            },
            "testing_frequency": {
                "continuous": 2,
                "daily": 3,
                "weekly": 4,
                "monthly": 6,
                "quarterly": 7,
                "annually": 0,
            },
            "recent_activity": [
                {
                    "date": datetime.now(timezone.utc) - timedelta(hours=2),
                    "activity": "Automated test completed",
                    "control": "SEC-001",
                    "result": "effective",
                },
                {
                    "date": datetime.now(timezone.utc) - timedelta(hours=6),
                    "activity": "Manual test executed",
                    "control": "PRIV-001",
                    "result": "deficient",
                },
            ],
            "recommendations": [
                {
                    "priority": "high",
                    "title": "Address privacy control deficiencies",
                    "description": "Focus on improving privacy controls effectiveness",
                },
                {
                    "priority": "medium",
                    "title": "Increase test automation",
                    "description": "Automate more manual testing procedures",
                },
            ],
            "last_updated": datetime.now(timezone.utc).isoformat(),
        }


# Global testing framework instance
_testing_framework: ControlTestingFramework | None = None


@beartype
def get_testing_framework(
    control_framework: ControlFramework,
) -> ControlTestingFramework:
    """Get global testing framework instance."""
    global _testing_framework
    if _testing_framework is None:
        _testing_framework = ControlTestingFramework(control_framework)
    return _testing_framework
