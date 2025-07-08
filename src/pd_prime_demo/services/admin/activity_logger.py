"""Admin activity logging service."""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from beartype import beartype

from ...core.database import Database


class AdminActivityLogger:
    """Log all admin activities for audit trail."""

    def __init__(self, db: Database) -> None:
        """Initialize activity logger with dependency validation."""
        if not db or not hasattr(db, "execute"):
            raise ValueError("Database connection required and must be active")

        self._db = db

    @beartype
    async def log_activity(
        self,
        admin_user_id: UUID,
        action: str,
        resource_type: str,
        resource_id: UUID | None = None,
        old_values: dict[str, Any] | None = None,
        new_values: dict[str, Any] | None = None,
        status: str = "success",
        error_message: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        additional_context: dict[str, Any] | None = None,
    ) -> None:
        """Log admin activity asynchronously.

        This is a fire-and-forget operation that should not fail the main operation.

        Args:
            admin_user_id: Admin performing the action
            action: Action performed (e.g., 'create', 'update', 'delete', 'login')
            resource_type: Type of resource (e.g., 'policy', 'customer', 'claim')
            resource_id: ID of the affected resource (if applicable)
            old_values: Previous values (for updates)
            new_values: New values (for creates/updates)
            status: Operation status ('success', 'failure', 'partial')
            error_message: Error details if status is not success
            ip_address: Client IP address
            user_agent: Client user agent string
            additional_context: Any additional context data
        """
        try:
            await self._db.execute(
                """
                INSERT INTO admin_activity_logs (
                    admin_user_id, action, resource_type, resource_id,
                    old_values, new_values, status, error_message,
                    ip_address, user_agent, additional_context, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
                """,
                admin_user_id,
                action,
                resource_type,
                resource_id,
                json.dumps(old_values) if old_values else None,
                json.dumps(new_values) if new_values else None,
                status,
                error_message,
                ip_address,
                user_agent,
                json.dumps(additional_context) if additional_context else None,
                datetime.utcnow(),
            )
        except Exception:
            # Silently fail - logging should not break main operations
            pass

    @beartype
    async def log_login(
        self,
        admin_user_id: UUID,
        success: bool,
        ip_address: str | None = None,
        user_agent: str | None = None,
        error_reason: str | None = None,
    ) -> None:
        """Log admin login attempt.

        Args:
            admin_user_id: Admin attempting to log in
            success: Whether login was successful
            ip_address: Client IP address
            user_agent: Client user agent
            error_reason: Reason for failed login
        """
        await self.log_activity(
            admin_user_id=admin_user_id,
            action="login",
            resource_type="admin_session",
            status="success" if success else "failure",
            error_message=error_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            additional_context={
                "login_time": datetime.utcnow().isoformat(),
                "success": success,
            },
        )

    @beartype
    async def log_logout(
        self,
        admin_user_id: UUID,
        session_duration_seconds: int | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log admin logout.

        Args:
            admin_user_id: Admin logging out
            session_duration_seconds: Length of session
            ip_address: Client IP address
        """
        await self.log_activity(
            admin_user_id=admin_user_id,
            action="logout",
            resource_type="admin_session",
            ip_address=ip_address,
            additional_context={
                "logout_time": datetime.utcnow().isoformat(),
                "session_duration_seconds": session_duration_seconds,
            },
        )

    @beartype
    async def log_permission_check(
        self,
        admin_user_id: UUID,
        resource: str,
        action: str,
        allowed: bool,
        ip_address: str | None = None,
    ) -> None:
        """Log permission check (for security auditing).

        Args:
            admin_user_id: Admin being checked
            resource: Resource being accessed
            action: Action being attempted
            allowed: Whether permission was granted
            ip_address: Client IP address
        """
        await self.log_activity(
            admin_user_id=admin_user_id,
            action="permission_check",
            resource_type="permission",
            status="success" if allowed else "denied",
            ip_address=ip_address,
            additional_context={
                "resource": resource,
                "action": action,
                "allowed": allowed,
                "check_time": datetime.utcnow().isoformat(),
            },
        )

    @beartype
    async def log_data_export(
        self,
        admin_user_id: UUID,
        export_type: str,
        record_count: int,
        filters: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log data export for compliance.

        Args:
            admin_user_id: Admin performing export
            export_type: Type of data exported
            record_count: Number of records exported
            filters: Filters applied to export
            ip_address: Client IP address
        """
        await self.log_activity(
            admin_user_id=admin_user_id,
            action="data_export",
            resource_type=export_type,
            ip_address=ip_address,
            additional_context={
                "export_time": datetime.utcnow().isoformat(),
                "record_count": record_count,
                "filters": filters,
            },
        )

    @beartype
    async def log_bulk_operation(
        self,
        admin_user_id: UUID,
        operation: str,
        resource_type: str,
        affected_count: int,
        success_count: int,
        failure_count: int,
        ip_address: str | None = None,
    ) -> None:
        """Log bulk operations.

        Args:
            admin_user_id: Admin performing operation
            operation: Type of bulk operation
            resource_type: Type of resources affected
            affected_count: Total records attempted
            success_count: Successfully processed
            failure_count: Failed to process
            ip_address: Client IP address
        """
        status = "success" if failure_count == 0 else "partial"

        await self.log_activity(
            admin_user_id=admin_user_id,
            action=f"bulk_{operation}",
            resource_type=resource_type,
            status=status,
            ip_address=ip_address,
            additional_context={
                "operation_time": datetime.utcnow().isoformat(),
                "affected_count": affected_count,
                "success_count": success_count,
                "failure_count": failure_count,
            },
        )

    @beartype
    async def get_activity_summary(
        self,
        admin_user_id: UUID | None = None,
        days: int = 7,
    ) -> dict[str, Any]:
        """Get activity summary for dashboards.

        Args:
            admin_user_id: Filter by specific admin (None for all)
            days: Number of days to look back

        Returns:
            Summary statistics of admin activities
        """
        query = """
            SELECT
                action,
                resource_type,
                status,
                COUNT(*) as count
            FROM admin_activity_logs
            WHERE created_at > NOW() - INTERVAL '%s days'
        """

        params = [days]

        if admin_user_id:
            query += " AND admin_user_id = $2"
            params.append(admin_user_id)

        query += " GROUP BY action, resource_type, status"

        rows = await self._db.fetch(query, *params)

        summary = {
            "total_activities": 0,
            "by_action": {},
            "by_resource": {},
            "by_status": {"success": 0, "failure": 0, "partial": 0},
        }

        for row in rows:
            count = row["count"]
            summary["total_activities"] += count

            action = row["action"]
            if action not in summary["by_action"]:
                summary["by_action"][action] = 0
            summary["by_action"][action] += count

            resource = row["resource_type"]
            if resource not in summary["by_resource"]:
                summary["by_resource"][resource] = 0
            summary["by_resource"][resource] += count

            status = row["status"]
            if status in summary["by_status"]:
                summary["by_status"][status] += count

        return summary
