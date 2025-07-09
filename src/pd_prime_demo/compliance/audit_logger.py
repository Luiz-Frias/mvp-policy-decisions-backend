"""SOC 2 Audit Logging - Comprehensive audit trail for compliance evidence.

This module provides enterprise-grade audit logging capabilities that automatically
capture and store compliance-relevant events. All audit logs are immutable,
timestamped, and include complete context for SOC 2 evidence collection.
"""

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from ..core.database import get_database
from pd_prime_demo.core.result_types import Result


class AuditEventType(str, Enum):
    """Types of audit events for SOC 2 compliance."""

    # Security Events
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    DATA_ACCESS = "data_access"
    ENCRYPTION_OPERATION = "encryption_operation"
    SECURITY_INCIDENT = "security_incident"

    # Availability Events
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    SERVICE_FAILURE = "service_failure"
    BACKUP_OPERATION = "backup_operation"
    DISASTER_RECOVERY = "disaster_recovery"

    # Processing Integrity Events
    DATA_VALIDATION = "data_validation"
    DATA_TRANSFORMATION = "data_transformation"
    CALCULATION_EXECUTION = "calculation_execution"
    RECONCILIATION = "reconciliation"

    # Confidentiality Events
    DATA_CLASSIFICATION = "data_classification"
    ACCESS_GRANTED = "access_granted"
    ACCESS_DENIED = "access_denied"
    DATA_EXPORT = "data_export"

    # Privacy Events
    CONSENT_GIVEN = "consent_given"
    CONSENT_WITHDRAWN = "consent_withdrawn"
    DATA_DELETION = "data_deletion"
    PRIVACY_REQUEST = "privacy_request"

    # Control Events
    CONTROL_EXECUTION = "control_execution"
    CONTROL_FAILURE = "control_failure"
    REMEDIATION_ACTION = "remediation_action"
    COMPLIANCE_ASSESSMENT = "compliance_assessment"


class RiskLevel(str, Enum):
    """Risk levels for audit events."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ComplianceEvent(BaseModel):
    """Immutable audit event for SOC 2 compliance."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    # Event Identity
    event_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: AuditEventType = Field(...)

    # Security Context
    user_id: UUID | None = Field(default=None)
    session_id: UUID | None = Field(default=None)
    ip_address: str | None = Field(default=None)
    user_agent: str | None = Field(default=None)

    # Event Details
    action: str = Field(..., min_length=1, max_length=200)
    resource_type: str | None = Field(default=None, max_length=100)
    resource_id: str | None = Field(default=None, max_length=200)

    # Request Context
    request_method: str | None = Field(default=None, max_length=10)
    request_path: str | None = Field(default=None, max_length=500)
    response_status: int | None = Field(default=None, ge=100, le=599)

    # Risk Assessment
    risk_level: RiskLevel = Field(default=RiskLevel.INFO)
    risk_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Compliance Metadata
    control_references: list[str] = Field(default_factory=list)
    compliance_tags: list[str] = Field(default_factory=list)

    # Event Data
    event_data: dict[str, Any] = Field(default_factory=dict)
    before_state: dict[str, Any] | None = Field(default=None)
    after_state: dict[str, Any] | None = Field(default=None)

    # Processing Metadata
    processing_time_ms: int | None = Field(default=None, ge=0)
    error_details: str | None = Field(default=None)

    # Evidence Links
    evidence_references: list[str] = Field(default_factory=list)

    @beartype
    def to_audit_record(self) -> dict[str, Any]:
        """Convert to database audit record format."""
        return {
            "id": self.event_id,
            "user_id": self.user_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "session_id": self.session_id,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "request_method": self.request_method,
            "request_path": self.request_path,
            "request_body": self.event_data,
            "response_status": self.response_status,
            "risk_score": self.risk_score,
            "security_alerts": {
                "risk_level": self.risk_level.value,
                "control_references": self.control_references,
                "compliance_tags": self.compliance_tags,
                "evidence_references": self.evidence_references,
            },
            "created_at": self.timestamp,
        }


class AuditLogger:
    """Enterprise audit logger for SOC 2 compliance."""

    def __init__(self, database=None):
        """Initialize audit logger with database connection."""
        self._database = database or get_database()
        self._batch_size = 100
        self._pending_events: list[ComplianceEvent] = []

    @beartype
    async def log_event(self, event: ComplianceEvent):
        """Log a single compliance event."""
        try:
            # Immediate write for high-risk events
            if event.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                await self._write_event_to_database(event)
            else:
                # Batch write for lower-risk events
                self._pending_events.append(event)
                if len(self._pending_events) >= self._batch_size:
                    await self._flush_pending_events()

            return Result.ok(None)

        except Exception as e:
            return Result.err(f"Failed to log audit event: {str(e)}")

    @beartype
    async def _write_event_to_database(self, event: ComplianceEvent) -> None:
        """Write single event to database."""
        audit_record = event.to_audit_record()

        query = """
            INSERT INTO audit_logs (
                id, user_id, ip_address, user_agent, session_id,
                action, resource_type, resource_id,
                request_method, request_path, request_body,
                response_status, risk_score, security_alerts,
                created_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15
            )
        """

        await self._database.execute(
            query,
            audit_record["id"],
            audit_record["user_id"],
            audit_record["ip_address"],
            audit_record["user_agent"],
            audit_record["session_id"],
            audit_record["action"],
            audit_record["resource_type"],
            audit_record["resource_id"],
            audit_record["request_method"],
            audit_record["request_path"],
            json.dumps(audit_record["request_body"]),
            audit_record["response_status"],
            audit_record["risk_score"],
            json.dumps(audit_record["security_alerts"]),
            audit_record["created_at"],
        )

    @beartype
    async def _flush_pending_events(self) -> None:
        """Flush all pending events to database."""
        if not self._pending_events:
            return

        # Batch insert for efficiency
        values = []
        for event in self._pending_events:
            audit_record = event.to_audit_record()
            values.extend(
                [
                    audit_record["id"],
                    audit_record["user_id"],
                    audit_record["ip_address"],
                    audit_record["user_agent"],
                    audit_record["session_id"],
                    audit_record["action"],
                    audit_record["resource_type"],
                    audit_record["resource_id"],
                    audit_record["request_method"],
                    audit_record["request_path"],
                    json.dumps(audit_record["request_body"]),
                    audit_record["response_status"],
                    audit_record["risk_score"],
                    json.dumps(audit_record["security_alerts"]),
                    audit_record["created_at"],
                ]
            )

        # Generate placeholders for batch insert
        placeholders = []
        for i in range(len(self._pending_events)):
            base = i * 15
            placeholders.append(
                f"(${base+1}, ${base+2}, ${base+3}, ${base+4}, ${base+5}, "
                f"${base+6}, ${base+7}, ${base+8}, ${base+9}, ${base+10}, "
                f"${base+11}, ${base+12}, ${base+13}, ${base+14}, ${base+15})"
            )

        # Safe query construction - placeholders are parameterized, not string concatenated
        query = """
            INSERT INTO audit_logs (
                id, user_id, ip_address, user_agent, session_id,
                action, resource_type, resource_id,
                request_method, request_path, request_body,
                response_status, risk_score, security_alerts,
                created_at
            ) VALUES """ + ", ".join(
            placeholders
        )

        await self._database.execute(query, *values)
        self._pending_events.clear()

    # Convenience methods for common audit events

    @beartype
    async def log_authentication_event(
        self,
        user_id: UUID,
        action: str,
        success: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        **metadata: Any,
    ):
        """Log authentication-related event."""
        event = ComplianceEvent(
            event_type=AuditEventType.AUTHENTICATION,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            action=action,
            risk_level=RiskLevel.HIGH if not success else RiskLevel.INFO,
            risk_score=0.8 if not success else 0.1,
            compliance_tags=["authentication", "security"],
            control_references=["SEC-001", "SEC-002"],
            event_data={"success": success, **metadata},
        )
        return await self.log_event(event)

    @beartype
    async def log_data_access_event(
        self,
        user_id: UUID,
        resource_type: str,
        resource_id: str,
        action: str,
        ip_address: str | None = None,
        **metadata: Any,
    ):
        """Log data access event."""
        event = ComplianceEvent(
            event_type=AuditEventType.DATA_ACCESS,
            user_id=user_id,
            ip_address=ip_address,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            risk_level=RiskLevel.MEDIUM,
            risk_score=0.3,
            compliance_tags=["data_access", "confidentiality"],
            control_references=["CONF-001"],
            event_data=metadata,
        )
        return await self.log_event(event)

    @beartype
    async def log_control_execution(self, execution):
        """Log control execution event."""
        event = ComplianceEvent(
            event_type=AuditEventType.CONTROL_EXECUTION,
            action=f"control_executed_{execution.control_id}",
            resource_type="compliance_control",
            resource_id=execution.control_id,
            risk_level=RiskLevel.HIGH if not execution.result else RiskLevel.INFO,
            risk_score=0.9 if not execution.result else 0.1,
            compliance_tags=["control_execution", "compliance"],
            control_references=[execution.control_id],
            processing_time_ms=execution.execution_time_ms,
            event_data={
                "execution_id": str(execution.execution_id),
                "status": execution.status.value,
                "result": execution.result,
                "findings": execution.findings,
                "evidence_collected": execution.evidence_collected,
            },
        )
        return await self.log_event(event)

    @beartype
    async def log_control_event(self, action: str, control_id: str, **metadata: Any):
        """Log general control-related event."""
        event = ComplianceEvent(
            event_type=AuditEventType.CONTROL_EXECUTION,
            action=action,
            resource_type="compliance_control",
            resource_id=control_id,
            risk_level=RiskLevel.INFO,
            risk_score=0.1,
            compliance_tags=["control_management"],
            control_references=[control_id],
            event_data=metadata,
        )
        return await self.log_event(event)

    @beartype
    async def log_encryption_event(
        self, action: str, data_type: str, encryption_algorithm: str, **metadata: Any
    ):
        """Log encryption operation."""
        event = ComplianceEvent(
            event_type=AuditEventType.ENCRYPTION_OPERATION,
            action=action,
            resource_type="encrypted_data",
            risk_level=RiskLevel.MEDIUM,
            risk_score=0.2,
            compliance_tags=["encryption", "security"],
            control_references=["SEC-001"],
            event_data={
                "data_type": data_type,
                "algorithm": encryption_algorithm,
                **metadata,
            },
        )
        return await self.log_event(event)

    @beartype
    async def log_privacy_event(
        self, user_id: UUID, action: str, data_type: str, **metadata: Any
    ):
        """Log privacy-related event."""
        event = ComplianceEvent(
            event_type=AuditEventType.PRIVACY_REQUEST,
            user_id=user_id,
            action=action,
            resource_type="personal_data",
            risk_level=RiskLevel.HIGH,
            risk_score=0.6,
            compliance_tags=["privacy", "gdpr", "ccpa"],
            control_references=["PRIV-001"],
            event_data={"data_type": data_type, **metadata},
        )
        return await self.log_event(event)

    @beartype
    async def log_error(self, message: str, **metadata: Any):
        """Log system error for compliance monitoring."""
        event = ComplianceEvent(
            event_type=AuditEventType.SECURITY_INCIDENT,
            action="system_error",
            risk_level=RiskLevel.MEDIUM,
            risk_score=0.4,
            compliance_tags=["error", "incident"],
            error_details=message,
            event_data=metadata,
        )
        return await self.log_event(event)

    @beartype
    async def get_audit_trail(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        user_id: UUID | None = None,
        event_type: AuditEventType | None = None,
        control_id: str | None = None,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Retrieve audit trail for compliance reporting."""
        try:
            conditions = []
            params = []
            param_count = 0

            if start_date:
                param_count += 1
                conditions.append(f"created_at >= ${param_count}")
                params.append(start_date)

            if end_date:
                param_count += 1
                conditions.append(f"created_at <= ${param_count}")
                params.append(end_date)

            if user_id:
                param_count += 1
                conditions.append(f"user_id = ${param_count}")
                params.append(user_id)

            if event_type:
                param_count += 1
                conditions.append(f"action LIKE ${param_count}")
                params.append(f"%{event_type.value}%")

            if control_id:
                param_count += 1
                conditions.append(
                    f"security_alerts->'control_references' @> ${param_count}"
                )
                params.append(json.dumps([control_id]))

            where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

            param_count += 1
            # Safe query construction - where_clause is built from parameterized conditions
            query = (
                """
                SELECT * FROM audit_logs
                """
                + where_clause
                + f"""
                ORDER BY created_at DESC
                LIMIT ${param_count}
            """
            )
            params.append(limit)

            rows = await self._database.fetch(query, *params)

            # Convert rows to dictionaries
            audit_records = []
            for row in rows:
                record = dict(row)
                # Parse JSON fields
                if record.get("request_body"):
                    record["request_body"] = json.loads(record["request_body"])
                if record.get("security_alerts"):
                    record["security_alerts"] = json.loads(record["security_alerts"])
                audit_records.append(record)

            return Result.ok(audit_records)

        except Exception as e:
            return Result.err(f"Failed to retrieve audit trail: {str(e)}")

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit - flush any pending events."""
        if self._pending_events:
            await self._flush_pending_events()


# Global audit logger instance
_audit_logger: AuditLogger | None = None


@beartype
def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger()
    return _audit_logger
