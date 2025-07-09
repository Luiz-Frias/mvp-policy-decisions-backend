"""SOC 2 Processing Integrity Controls - Implementation of processing integrity trust service criteria.

This module implements comprehensive processing integrity controls including:
- Data validation at all system boundaries
- Automated data reconciliation and consistency checks
- Change control and audit trails for all data modifications
- Error detection and correction mechanisms
- Data quality monitoring and reporting
"""

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field, validator

from pd_prime_demo.core.result_types import Err, Ok, Result

from ..core.database import get_database
from .audit_logger import AuditLogger, get_audit_logger
from .control_framework import ControlExecution, ControlStatus

# Type alias for control execution result
ControlResult = Result[ControlExecution, str]


class DataValidationRule(BaseModel):
    """Data validation rule definition."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    rule_id: str = Field(...)
    field_name: str = Field(...)
    validation_type: str = Field(...)  # required, format, range, custom
    parameters: dict[str, Any] = Field(default_factory=dict)
    error_message: str = Field(...)
    severity: str = Field(default="error")  # error, warning, info

    @beartype
    def validate_value(self, value: Any) -> tuple[bool, str | None]:
        """Validate a value against this rule."""
        try:
            if self.validation_type == "required":
                if value is None or (isinstance(value, str) and value.strip() == ""):
                    return False, self.error_message

            elif self.validation_type == "format":
                format_pattern = self.parameters.get("pattern")
                if format_pattern and isinstance(value, str):
                    import re

                    if not re.match(format_pattern, value):
                        return False, self.error_message

            elif self.validation_type == "range":
                min_val = self.parameters.get("min")
                max_val = self.parameters.get("max")
                if min_val is not None and value < min_val:
                    return False, self.error_message
                if max_val is not None and value > max_val:
                    return False, self.error_message

            elif self.validation_type == "custom":
                # Custom validation logic would go here
                pass

            return True, None

        except Exception as e:
            return False, f"Validation error: {str(e)}"


class DataValidationResult(BaseModel):
    """Result of data validation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    validation_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    data_source: str = Field(...)
    records_validated: int = Field(ge=0)
    records_passed: int = Field(ge=0)
    records_failed: int = Field(ge=0)
    validation_errors: list[dict[str, Any]] = Field(default_factory=list)
    data_quality_score: float = Field(ge=0.0, le=100.0)

    @validator("data_quality_score", pre=True, always=True)
    def calculate_quality_score(cls, v: Any, values: dict[str, Any]) -> float:
        """Calculate data quality score based on validation results."""
        if "records_validated" in values and values["records_validated"] > 0:
            passed = values.get("records_passed", 0)
            total = values["records_validated"]
            return float((passed / total) * 100)
        return 0.0


class ReconciliationResult(BaseModel):
    """Result of data reconciliation."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    reconciliation_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source_system: str = Field(...)
    target_system: str = Field(...)
    records_compared: int = Field(ge=0)
    matches: int = Field(ge=0)
    discrepancies: int = Field(ge=0)
    discrepancy_details: list[dict[str, Any]] = Field(default_factory=list)
    reconciliation_percentage: float = Field(ge=0.0, le=100.0)

    @validator("reconciliation_percentage", pre=True, always=True)
    def calculate_reconciliation_percentage(
        cls, v: Any, values: dict[str, Any]
    ) -> float:
        """Calculate reconciliation percentage."""
        if "records_compared" in values and values["records_compared"] > 0:
            matches = values.get("matches", 0)
            total = values["records_compared"]
            return float((matches / total) * 100)
        return 0.0


class ChangeRecord(BaseModel):
    """Record of data changes for audit trail."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    change_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    user_id: UUID | None = Field(default=None)
    table_name: str = Field(...)
    record_id: str = Field(...)
    operation: str = Field(...)  # INSERT, UPDATE, DELETE
    before_values: dict[str, Any] | None = Field(default=None)
    after_values: dict[str, Any] | None = Field(default=None)
    change_reason: str | None = Field(default=None)
    change_hash: str = Field(...)

    @validator("change_hash", pre=True, always=True)
    def calculate_change_hash(cls, v: Any, values: dict[str, Any]) -> str:
        """Calculate hash of the change for integrity verification."""
        change_data = {
            "table": values.get("table_name"),
            "record_id": values.get("record_id"),
            "operation": values.get("operation"),
            "before": values.get("before_values"),
            "after": values.get("after_values"),
            "timestamp": (
                values.get("timestamp").isoformat() if values.get("timestamp") is not None else None
            ),
        }
        change_json = json.dumps(change_data, sort_keys=True, default=str)
        return hashlib.sha256(change_json.encode()).hexdigest()


class ProcessingIntegrityManager:
    """Manager for SOC 2 processing integrity controls."""

    def __init__(self, audit_logger: AuditLogger | None = None) -> None:
        """Initialize processing integrity control manager."""
        self._audit_logger = audit_logger or get_audit_logger()
        self._database = get_database()
        self._validation_rules = self._load_validation_rules()

    @beartype
    def _load_validation_rules(self) -> list[DataValidationRule]:
        """Load data validation rules."""
        return [
            # Customer validation rules
            DataValidationRule(
                rule_id="CUST-001",
                field_name="email",
                validation_type="format",
                parameters={
                    "pattern": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
                },
                error_message="Invalid email format",
            ),
            DataValidationRule(
                rule_id="CUST-002",
                field_name="phone",
                validation_type="format",
                parameters={"pattern": r"^\+?[\d\s\-\(\)]{10,15}$"},
                error_message="Invalid phone number format",
            ),
            # Policy validation rules
            DataValidationRule(
                rule_id="POL-001",
                field_name="premium_amount",
                validation_type="range",
                parameters={"min": 0, "max": 100000},
                error_message="Premium amount must be between $0 and $100,000",
            ),
            DataValidationRule(
                rule_id="POL-002",
                field_name="policy_number",
                validation_type="required",
                parameters={},
                error_message="Policy number is required",
            ),
            # Quote validation rules
            DataValidationRule(
                rule_id="QUO-001",
                field_name="coverage_amount",
                validation_type="range",
                parameters={"min": 10000, "max": 10000000},
                error_message="Coverage amount must be between $10,000 and $10,000,000",
            ),
            DataValidationRule(
                rule_id="QUO-002",
                field_name="deductible",
                validation_type="range",
                parameters={"min": 250, "max": 10000},
                error_message="Deductible must be between $250 and $10,000",
            ),
        ]

    @beartype
    async def execute_data_validation_control(self, control_id: str = "PI-001") -> ControlResult:
        """Execute comprehensive data validation control."""
        try:
            start_time = datetime.now(timezone.utc)
            findings = []
            evidence = {}

            # Validate data in critical tables
            validation_results = []

            # Validate customers
            customer_validation = await self._validate_table_data(
                "customers", ["email", "phone"]
            )
            validation_results.append(customer_validation)

            # Validate policies
            policy_validation = await self._validate_table_data(
                "policies", ["premium_amount", "policy_number"]
            )
            validation_results.append(policy_validation)

            # Validate quotes
            quote_validation = await self._validate_table_data(
                "quotes", ["coverage_amount", "deductible"]
            )
            validation_results.append(quote_validation)

            evidence["validation_results"] = [
                result.model_dump() for result in validation_results
            ]

            # Check overall data quality
            overall_quality = sum(
                result.data_quality_score for result in validation_results
            ) / len(validation_results)
            evidence["overall_data_quality"] = overall_quality

            if overall_quality < 95.0:
                findings.append(
                    f"Overall data quality score {overall_quality:.1f}% below 95% threshold"
                )

            # Check for validation errors
            total_errors = sum(
                len(result.validation_errors) for result in validation_results
            )
            if total_errors > 0:
                findings.append(f"Found {total_errors} data validation errors")

            # Check input validation at API boundaries
            api_validation = await self._check_api_input_validation()
            evidence["api_validation"] = api_validation

            if not api_validation["all_endpoints_validated"]:
                findings.extend(api_validation["unvalidated_endpoints"])

            end_time = datetime.now(timezone.utc)
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            execution = ControlExecution(
                control_id=control_id,
                timestamp=start_time,
                status=(
                    ControlStatus.ACTIVE if len(findings) == 0 else ControlStatus.FAILED
                ),
                result=len(findings) == 0,
                evidence_collected=evidence,
                findings=findings,
                remediation_actions=(
                    [
                        "Fix data validation errors",
                        "Implement additional validation rules",
                        "Add validation to missing API endpoints",
                        "Improve data quality monitoring",
                    ]
                    if findings
                    else []
                ),
                execution_time_ms=execution_time_ms,
            )

            return Ok(execution)

        except Exception as e:
            return Err(f"Data validation control failed: {str(e)}")

    @beartype
    async def _validate_table_data(
        self, table_name: str, fields_to_validate: list[str]
    ) -> DataValidationResult:
        """Validate data in a specific table."""
        # Simulated data validation - in production, query actual database
        sample_data = await self._get_sample_data(table_name)

        records_validated = len(sample_data)
        validation_errors = []
        records_failed = 0

        for record in sample_data:
            record_errors = []

            for field in fields_to_validate:
                if field in record:
                    # Find applicable validation rules
                    applicable_rules = [
                        rule
                        for rule in self._validation_rules
                        if rule.field_name == field
                    ]

                    for rule in applicable_rules:
                        is_valid, error_msg = rule.validate_value(record[field])
                        if not is_valid:
                            record_errors.append(
                                {
                                    "rule_id": rule.rule_id,
                                    "field": field,
                                    "value": record[field],
                                    "error": error_msg,
                                }
                            )

            if record_errors:
                records_failed += 1
                validation_errors.extend(record_errors)

        records_passed = records_validated - records_failed

        return DataValidationResult(
            data_source=table_name,
            records_validated=records_validated,
            records_passed=records_passed,
            records_failed=records_failed,
            validation_errors=validation_errors,
        )

    @beartype
    async def _get_sample_data(self, table_name: str) -> list[dict[str, Any]]:
        """Get sample data for validation testing."""
        # Simulated sample data
        if table_name == "customers":
            return [
                {"id": "1", "email": "valid@example.com", "phone": "+1-555-123-4567"},
                {"id": "2", "email": "invalid-email", "phone": "555-123-4567"},
                {"id": "3", "email": "another@example.com", "phone": "invalid-phone"},
            ]
        elif table_name == "policies":
            return [
                {"id": "1", "premium_amount": 1500.00, "policy_number": "POL-001"},
                {
                    "id": "2",
                    "premium_amount": -100.00,
                    "policy_number": "POL-002",
                },  # Invalid negative
                {
                    "id": "3",
                    "premium_amount": 2000.00,
                    "policy_number": "",
                },  # Invalid empty
            ]
        elif table_name == "quotes":
            return [
                {"id": "1", "coverage_amount": 100000, "deductible": 1000},
                {
                    "id": "2",
                    "coverage_amount": 5000,
                    "deductible": 500,
                },  # Invalid coverage too low
                {
                    "id": "3",
                    "coverage_amount": 500000,
                    "deductible": 15000,
                },  # Invalid deductible too high
            ]
        else:
            return []

    @beartype
    async def _check_api_input_validation(self) -> dict[str, Any]:
        """Check API input validation implementation."""
        # Simulated API validation check
        api_endpoints = [
            {"endpoint": "/api/v1/customers", "has_validation": True},
            {"endpoint": "/api/v1/policies", "has_validation": True},
            {"endpoint": "/api/v1/quotes", "has_validation": True},
            {"endpoint": "/api/v1/claims", "has_validation": True},
            {
                "endpoint": "/api/v1/admin/users",
                "has_validation": False,
            },  # Missing validation
        ]

        unvalidated_endpoints = [
            endpoint["endpoint"]
            for endpoint in api_endpoints
            if not endpoint["has_validation"]
        ]

        return {
            "total_endpoints": len(api_endpoints),
            "validated_endpoints": len(api_endpoints) - len(unvalidated_endpoints),
            "unvalidated_endpoints": [
                f"Missing validation: {ep}" for ep in unvalidated_endpoints
            ],
            "all_endpoints_validated": len(unvalidated_endpoints) == 0,
            "validation_coverage": (
                (len(api_endpoints) - len(unvalidated_endpoints)) / len(api_endpoints)
            )
            * 100,
        }

    @beartype
    async def execute_data_reconciliation_control(self, control_id: str = "PI-002") -> ControlResult:
        """Execute data reconciliation control."""
        try:
            start_time = datetime.now(timezone.utc)
            findings = []
            evidence = {}

            # Reconcile critical data between systems
            reconciliation_results = []

            # Reconcile policy data
            policy_reconciliation = await self._reconcile_data(
                "policy_system", "billing_system", "policies"
            )
            reconciliation_results.append(policy_reconciliation)

            # Reconcile customer data
            customer_reconciliation = await self._reconcile_data(
                "crm_system", "policy_system", "customers"
            )
            reconciliation_results.append(customer_reconciliation)

            # Reconcile financial data
            financial_reconciliation = await self._reconcile_financial_data()
            reconciliation_results.append(financial_reconciliation)

            evidence["reconciliation_results"] = [
                result.model_dump() for result in reconciliation_results
            ]

            # Check reconciliation thresholds
            for result in reconciliation_results:
                if result.reconciliation_percentage < 99.0:
                    findings.append(
                        f"{result.source_system} vs {result.target_system} reconciliation "
                        f"{result.reconciliation_percentage:.1f}% below 99% threshold"
                    )

                if result.discrepancies > 0:
                    findings.append(
                        f"Found {result.discrepancies} discrepancies between "
                        f"{result.source_system} and {result.target_system}"
                    )

            # Check automated reconciliation processes
            auto_reconciliation = await self._check_automated_reconciliation()
            evidence["automated_reconciliation"] = auto_reconciliation

            if not auto_reconciliation["all_processes_running"]:
                findings.extend(auto_reconciliation["failed_processes"])

            end_time = datetime.now(timezone.utc)
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            execution = ControlExecution(
                control_id=control_id,
                timestamp=start_time,
                status=(
                    ControlStatus.ACTIVE if len(findings) == 0 else ControlStatus.FAILED
                ),
                result=len(findings) == 0,
                evidence_collected=evidence,
                findings=findings,
                remediation_actions=(
                    [
                        "Investigate reconciliation discrepancies",
                        "Fix automated reconciliation processes",
                        "Implement additional data consistency checks",
                        "Review data synchronization procedures",
                    ]
                    if findings
                    else []
                ),
                execution_time_ms=execution_time_ms,
            )

            return Ok(execution)

        except Exception as e:
            return Err(f"Data reconciliation control failed: {str(e)}")

    @beartype
    async def _reconcile_data(
        self, source_system: str, target_system: str, data_type: str
    ) -> ReconciliationResult:
        """Reconcile data between two systems."""
        # Simulated reconciliation
        if data_type == "policies":
            records_compared = 1000
            matches = 998
            discrepancies = 2
            discrepancy_details = [
                {
                    "record_id": "POL-001",
                    "field": "premium_amount",
                    "source_value": 1500.00,
                    "target_value": 1450.00,
                    "difference": 50.00,
                },
                {
                    "record_id": "POL-002",
                    "field": "effective_date",
                    "source_value": "2024-01-01",
                    "target_value": "2024-01-02",
                    "difference": "1 day",
                },
            ]
        elif data_type == "customers":
            records_compared = 5000
            matches = 4995
            discrepancies = 5
            discrepancy_details = [
                {
                    "record_id": "CUST-001",
                    "field": "email",
                    "source_value": "old@example.com",
                    "target_value": "new@example.com",
                    "difference": "email updated in source only",
                }
            ]
        else:
            records_compared = 500
            matches = 500
            discrepancies = 0
            discrepancy_details = []

        return ReconciliationResult(
            source_system=source_system,
            target_system=target_system,
            records_compared=records_compared,
            matches=matches,
            discrepancies=discrepancies,
            discrepancy_details=discrepancy_details,
        )

    @beartype
    async def _reconcile_financial_data(self) -> ReconciliationResult:
        """Reconcile financial data between systems."""
        # Simulated financial reconciliation
        return ReconciliationResult(
            source_system="policy_system",
            target_system="accounting_system",
            records_compared=250,
            matches=248,
            discrepancies=2,
            discrepancy_details=[
                {
                    "record_id": "INV-001",
                    "field": "total_amount",
                    "source_value": 15000.00,
                    "target_value": 14950.00,
                    "difference": 50.00,
                }
            ],
        )

    @beartype
    async def _check_automated_reconciliation(self) -> dict[str, Any]:
        """Check automated reconciliation processes."""
        processes = [
            {
                "name": "daily_policy_reconciliation",
                "status": "running",
                "last_run": datetime.now(timezone.utc) - timedelta(hours=2),
            },
            {
                "name": "hourly_transaction_reconciliation",
                "status": "running",
                "last_run": datetime.now(timezone.utc) - timedelta(minutes=30),
            },
            {
                "name": "weekly_customer_reconciliation",
                "status": "failed",
                "last_run": datetime.now(timezone.utc) - timedelta(days=2),
            },
        ]

        failed_processes = [
            f"Process {proc['name']} is {proc['status']}"
            for proc in processes
            if proc["status"] != "running"
        ]

        return {
            "total_processes": len(processes),
            "running_processes": len(
                [p for p in processes if p["status"] == "running"]
            ),
            "failed_processes": failed_processes,
            "all_processes_running": len(failed_processes) == 0,
            "processes_detail": processes,
        }

    @beartype
    async def execute_change_control_audit(self, control_id: str = "PI-003") -> ControlResult:
        """Execute change control and audit trail verification."""
        try:
            start_time = datetime.now(timezone.utc)
            findings = []
            evidence = {}

            # Check audit trail completeness
            audit_trail_check = await self._verify_audit_trail_completeness()
            evidence["audit_trail"] = audit_trail_check

            if not audit_trail_check["complete"]:
                findings.extend(audit_trail_check["missing_trails"])

            # Verify change integrity
            change_integrity = await self._verify_change_integrity()
            evidence["change_integrity"] = change_integrity

            if change_integrity["tampered_records"] > 0:
                findings.append(
                    f"Found {change_integrity['tampered_records']} potentially tampered change records"
                )

            # Check approval workflows
            approval_check = await self._check_change_approval_workflows()
            evidence["approval_workflows"] = approval_check

            if not approval_check["all_changes_approved"]:
                findings.append(
                    f"Found {approval_check['unapproved_changes']} unapproved changes"
                )

            # Verify segregation of duties
            segregation_check = await self._check_segregation_of_duties()
            evidence["segregation_of_duties"] = segregation_check

            if segregation_check["violations"] > 0:
                findings.append(
                    f"Found {segregation_check['violations']} segregation of duties violations"
                )

            end_time = datetime.now(timezone.utc)
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            execution = ControlExecution(
                control_id=control_id,
                timestamp=start_time,
                status=(
                    ControlStatus.ACTIVE if len(findings) == 0 else ControlStatus.FAILED
                ),
                result=len(findings) == 0,
                evidence_collected=evidence,
                findings=findings,
                remediation_actions=(
                    [
                        "Implement missing audit trails",
                        "Investigate change integrity issues",
                        "Enforce change approval workflows",
                        "Address segregation of duties violations",
                    ]
                    if findings
                    else []
                ),
                execution_time_ms=execution_time_ms,
            )

            return Ok(execution)

        except Exception as e:
            return Err(f"Change control audit failed: {str(e)}")

    @beartype
    async def _verify_audit_trail_completeness(self) -> dict[str, Any]:
        """Verify completeness of audit trails."""
        critical_tables = ["policies", "customers", "claims", "payments", "users"]

        audit_coverage = {}
        missing_trails = []

        for table in critical_tables:
            # Simulated audit trail check
            has_triggers = True  # All tables should have audit triggers
            has_recent_activity = True  # Should have recent audit records

            audit_coverage[table] = {
                "has_triggers": has_triggers,
                "has_recent_activity": has_recent_activity,
                "coverage": 100 if has_triggers and has_recent_activity else 0,
            }

            if not has_triggers:
                missing_trails.append(f"Table {table} missing audit triggers")
            if not has_recent_activity:
                missing_trails.append(f"Table {table} has no recent audit activity")

        overall_coverage = sum(
            coverage["coverage"] for coverage in audit_coverage.values()
        ) / len(critical_tables)

        return {
            "complete": len(missing_trails) == 0,
            "coverage_percentage": overall_coverage,
            "tables_checked": critical_tables,
            "missing_trails": missing_trails,
            "audit_coverage": audit_coverage,
        }

    @beartype
    async def _verify_change_integrity(self) -> dict[str, Any]:
        """Verify integrity of change records."""
        # Simulated change integrity verification
        sample_changes = [
            {
                "change_id": "CHG-001",
                "table": "policies",
                "operation": "UPDATE",
                "expected_hash": "abc123",
                "actual_hash": "abc123",
                "tampered": False,
            },
            {
                "change_id": "CHG-002",
                "table": "customers",
                "operation": "INSERT",
                "expected_hash": "def456",
                "actual_hash": "def456",
                "tampered": False,
            },
            {
                "change_id": "CHG-003",
                "table": "claims",
                "operation": "UPDATE",
                "expected_hash": "ghi789",
                "actual_hash": "xyz999",
                "tampered": True,
            },
        ]

        tampered_records = sum(1 for change in sample_changes if change["tampered"])

        return {
            "total_changes_checked": len(sample_changes),
            "tampered_records": tampered_records,
            "integrity_percentage": (
                (len(sample_changes) - tampered_records) / len(sample_changes)
            )
            * 100,
            "sample_changes": sample_changes,
        }

    @beartype
    async def _check_change_approval_workflows(self) -> dict[str, Any]:
        """Check change approval workflow compliance."""
        # Simulated approval workflow check
        recent_changes = [
            {"change_id": "CHG-001", "approved": True, "approver": "manager1"},
            {"change_id": "CHG-002", "approved": True, "approver": "manager2"},
            {"change_id": "CHG-003", "approved": False, "approver": None},  # Unapproved
            {"change_id": "CHG-004", "approved": True, "approver": "manager1"},
        ]

        unapproved_changes = sum(
            1 for change in recent_changes if not change["approved"]
        )

        return {
            "total_changes": len(recent_changes),
            "approved_changes": len(recent_changes) - unapproved_changes,
            "unapproved_changes": unapproved_changes,
            "all_changes_approved": unapproved_changes == 0,
            "approval_rate": (
                (len(recent_changes) - unapproved_changes) / len(recent_changes)
            )
            * 100,
        }

    @beartype
    async def _check_segregation_of_duties(self) -> dict[str, Any]:
        """Check segregation of duties violations."""
        # Simulated segregation check
        user_activities = [
            {"user": "user1", "created_policy": True, "approved_policy": False},  # Good
            {
                "user": "user2",
                "created_claim": True,
                "approved_claim": True,
            },  # Violation
            {
                "user": "user3",
                "entered_payment": True,
                "approved_payment": False,
            },  # Good
        ]

        violations = sum(
            1
            for activity in user_activities
            if (activity.get("created_policy") and activity.get("approved_policy"))
            or (activity.get("created_claim") and activity.get("approved_claim"))
            or (activity.get("entered_payment") and activity.get("approved_payment"))
        )

        return {
            "users_checked": len(user_activities),
            "violations": violations,
            "violation_details": [
                f"User {activity['user']} both created and approved same transaction type"
                for activity in user_activities
                if any(
                    activity.get(f"created_{key.split('_')[1]}")
                    and activity.get(f"approved_{key.split('_')[1]}")
                    for key in activity.keys()
                    if key.startswith("created_")
                )
            ],
        }

    @beartype
    async def execute_error_detection_control(self, control_id: str = "PI-004") -> ControlResult:
        """Execute error detection and correction control."""
        try:
            start_time = datetime.now(timezone.utc)
            findings = []
            evidence = {}

            # Check error detection systems
            error_detection = await self._check_error_detection_systems()
            evidence["error_detection"] = error_detection

            if not error_detection["all_systems_active"]:
                findings.extend(error_detection["inactive_systems"])

            # Analyze error trends
            error_trends = await self._analyze_error_trends()
            evidence["error_trends"] = error_trends

            if error_trends["error_rate_increasing"]:
                findings.append("Error rate is increasing beyond acceptable thresholds")

            # Check error correction mechanisms
            error_correction = await self._check_error_correction_mechanisms()
            evidence["error_correction"] = error_correction

            if error_correction["uncorrected_errors"] > 0:
                findings.append(
                    f"Found {error_correction['uncorrected_errors']} uncorrected errors"
                )

            end_time = datetime.now(timezone.utc)
            execution_time_ms = int((end_time - start_time).total_seconds() * 1000)

            execution = ControlExecution(
                control_id=control_id,
                timestamp=start_time,
                status=(
                    ControlStatus.ACTIVE if len(findings) == 0 else ControlStatus.FAILED
                ),
                result=len(findings) == 0,
                evidence_collected=evidence,
                findings=findings,
                remediation_actions=(
                    [
                        "Activate error detection systems",
                        "Address increasing error rates",
                        "Implement automated error correction",
                        "Improve error monitoring and alerting",
                    ]
                    if findings
                    else []
                ),
                execution_time_ms=execution_time_ms,
            )

            return Ok(execution)

        except Exception as e:
            return Err(f"Error detection control failed: {str(e)}")

    @beartype
    async def _check_error_detection_systems(self) -> dict[str, Any]:
        """Check error detection system status."""
        detection_systems = [
            {"name": "input_validation", "active": True, "coverage": 95},
            {"name": "business_rule_validation", "active": True, "coverage": 90},
            {"name": "data_consistency_checks", "active": True, "coverage": 85},
            {
                "name": "calculation_verification",
                "active": False,
                "coverage": 0,
            },  # Inactive
        ]

        inactive_systems = [
            f"System {system['name']} is inactive"
            for system in detection_systems
            if not system["active"]
        ]

        active_systems = [s for s in detection_systems if s["active"]]
        average_coverage = (
            sum(float(system["coverage"]) for system in active_systems) / len(active_systems)
            if active_systems else 0.0
        )

        return {
            "total_systems": len(detection_systems),
            "active_systems": len([s for s in detection_systems if s["active"]]),
            "inactive_systems": inactive_systems,
            "all_systems_active": len(inactive_systems) == 0,
            "average_coverage": average_coverage,
            "systems_detail": detection_systems,
        }

    @beartype
    async def _analyze_error_trends(self) -> dict[str, Any]:
        """Analyze error trends over time."""
        # Simulated error trend analysis
        error_data = [
            {"date": "2024-01-01", "errors": 12},
            {"date": "2024-01-02", "errors": 15},
            {"date": "2024-01-03", "errors": 18},
            {"date": "2024-01-04", "errors": 22},
            {"date": "2024-01-05", "errors": 25},
        ]

        # Simple trend calculation
        recent_errors = [d["errors"] for d in error_data[-3:]]
        older_errors = [d["errors"] for d in error_data[:2]]

        recent_avg = sum(recent_errors) / len(recent_errors)
        older_avg = sum(older_errors) / len(older_errors)

        increase_percentage = ((recent_avg - older_avg) / older_avg) * 100

        return {
            "error_rate_increasing": increase_percentage > 20,  # 20% increase threshold
            "increase_percentage": increase_percentage,
            "recent_average": recent_avg,
            "historical_average": older_avg,
            "trend_data": error_data,
        }

    @beartype
    async def _check_error_correction_mechanisms(self) -> dict[str, Any]:
        """Check error correction mechanisms."""
        errors_found = [
            {"error_id": "ERR-001", "corrected": True, "correction_time": 15},
            {"error_id": "ERR-002", "corrected": True, "correction_time": 8},
            {
                "error_id": "ERR-003",
                "corrected": False,
                "correction_time": None,
            },  # Uncorrected
            {"error_id": "ERR-004", "corrected": True, "correction_time": 22},
        ]

        uncorrected_errors = sum(1 for error in errors_found if not error["corrected"])
        corrected_errors = len(errors_found) - uncorrected_errors

        average_correction_time = (
            sum(
                float(error["correction_time"])
                for error in errors_found
                if error["corrected"] and error["correction_time"]
            )
            / corrected_errors
            if corrected_errors > 0
            else 0
        )

        return {
            "total_errors": len(errors_found),
            "corrected_errors": corrected_errors,
            "uncorrected_errors": uncorrected_errors,
            "correction_rate": (corrected_errors / len(errors_found)) * 100,
            "average_correction_time_minutes": average_correction_time,
            "errors_detail": errors_found,
        }

    @beartype
    async def get_processing_integrity_dashboard(self) -> dict[str, Any]:
        """Get comprehensive processing integrity dashboard data."""
        # Execute all processing integrity controls
        validation_result = await self.execute_data_validation_control()
        reconciliation_result = await self.execute_data_reconciliation_control()
        change_control_result = await self.execute_change_control_audit()
        error_detection_result = await self.execute_error_detection_control()

        results = [
            validation_result,
            reconciliation_result,
            change_control_result,
            error_detection_result,
        ]

        # Calculate processing integrity metrics
        total_controls = len(results)
        passing_controls = sum(1 for r in results if r.is_ok() and r.unwrap().result)
        integrity_score = (
            (passing_controls / total_controls) * 100 if total_controls > 0 else 0
        )

        # Get specific metrics
        validation_evidence = (
            validation_result.unwrap().evidence_collected
            if validation_result.is_ok()
            else {}
        )
        overall_quality = validation_evidence.get("overall_data_quality", 0)

        return {
            "integrity_score": integrity_score,
            "data_quality_score": overall_quality,
            "total_controls": total_controls,
            "passing_controls": passing_controls,
            "failing_controls": total_controls - passing_controls,
            "validation_errors": sum(
                len(result.validation_errors)
                for result in validation_evidence.get("validation_results", [])
                if hasattr(result, "validation_errors")
            ),
            "reconciliation_discrepancies": sum(
                result.get("discrepancies", 0)
                for result in reconciliation_result.unwrap().evidence_collected.get(
                    "reconciliation_results", []
                )
                if reconciliation_result.is_ok()
            ),
            "last_assessment": datetime.now(timezone.utc).isoformat(),
            "compliance_status": (
                "compliant" if integrity_score >= 95 else "non_compliant"
            ),
            "control_results": [
                {
                    "control_id": r.unwrap().control_id if r.is_ok() else "unknown",
                    "status": r.unwrap().status.value if r.is_ok() else "error",
                    "result": r.unwrap().result if r.is_ok() else False,
                    "findings_count": len(r.unwrap().findings) if r.is_ok() else 1,
                }
                for r in results
            ],
        }
