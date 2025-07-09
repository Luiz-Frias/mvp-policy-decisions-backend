"""Admin rate management service with approval workflows.

This module provides comprehensive admin rate management features including
versioning, A/B testing, and analytics.
"""

import json
from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ...core.cache import Cache
from ...core.database import Database
from ..rating.rate_tables import RateTableService


@beartype
class RateManagementService:
    """Service for admin rate management and approval workflows."""

    def __init__(self, db: Database, cache: Cache) -> None:
        """Initialize rate management service."""
        self._db = db
        self._cache = cache
        self._rate_table_service = RateTableService(db, cache)

    @beartype
    async def create_rate_table_version(
        self,
        table_name: str,
        rate_data: dict[str, Any],
        admin_user_id: UUID,
        effective_date: date,
        notes: str | None = None,
    ) -> dict:
        """Create new version of rate table requiring approval."""
        # Validate admin permissions
        has_permission = await self._check_permission(admin_user_id, "rate:write")
        if not has_permission:
            return Err(
                "Insufficient permissions to create rate tables. "
                "Required permission: rate:write"
            )

        # Create rate version through rate table service
        result = await self._rate_table_service.create_rate_table_version(
            table_name, rate_data, admin_user_id, effective_date, notes
        )

        if isinstance(result, Err):
            return result

        version = result.value

        # Create approval workflow
        workflow_result = await self._create_approval_workflow(
            version.id, admin_user_id
        )
        if isinstance(workflow_result, Err):
            return workflow_result

        # Log activity
        await self._log_rate_activity(
            admin_user_id,
            "create_rate_version",
            version.id,
            {"table_name": table_name, "version": version.version_number},
        )

        return Ok(
            {
                "version_id": version.id,
                "version_number": version.version_number,
                "status": "pending_approval",
                "approval_workflow_id": workflow_result.value,
                "effective_date": effective_date,
            }
        )

    @beartype
    async def approve_rate_version(
        self,
        version_id: UUID,
        admin_user_id: UUID,
        approval_notes: str | None = None,
    ) -> Result[bool, str]:
        """Approve rate table version."""
        # Check approval permissions
        has_permission = await self._check_permission(admin_user_id, "rate:approve")
        if not has_permission:
            return Err(
                "Insufficient permissions for rate approval. "
                "Required permission: rate:approve"
            )

        # Cannot approve own submissions (segregation of duties)
        creator_check = await self._check_rate_creator(version_id, admin_user_id)
        if creator_check:
            return Err(
                "Cannot approve your own rate submission. "
                "Another authorized user must approve this change."
            )

        # Approve through rate table service
        result = await self._rate_table_service.approve_rate_version(
            version_id, admin_user_id, approval_notes
        )

        if isinstance(result, Err):
            return result

        # Update workflow
        await self._update_approval_workflow(version_id, admin_user_id, "approved")

        # Log activity
        await self._log_rate_activity(
            admin_user_id,
            "approve_rate_version",
            version_id,
            {"approval_notes": approval_notes},
        )

        # Send notifications
        await self._send_rate_approval_notifications(version_id, admin_user_id)

        return Ok(True)

    @beartype
    async def reject_rate_version(
        self,
        version_id: UUID,
        admin_user_id: UUID,
        rejection_reason: str,
    ) -> Result[bool, str]:
        """Reject rate table version."""
        # Check approval permissions
        has_permission = await self._check_permission(admin_user_id, "rate:approve")
        if not has_permission:
            return Err("Insufficient permissions for rate rejection")

        # Update status
        query = """
            UPDATE rate_table_versions
            SET status = 'rejected',
                approved_by = $2,
                approved_at = $3,
                approval_notes = $4
            WHERE id = $1 AND status = 'pending'
        """

        result = await self._db.execute(
            query, version_id, admin_user_id, datetime.utcnow(), rejection_reason
        )

        if result == "UPDATE 0":
            return Err("Rate version not found or not in pending status")

        # Update workflow
        await self._update_approval_workflow(version_id, admin_user_id, "rejected")

        # Log activity
        await self._log_rate_activity(
            admin_user_id,
            "reject_rate_version",
            version_id,
            {"rejection_reason": rejection_reason},
        )

        return Ok(True)

    @beartype
    async def get_rate_comparison(self, version_id_1: UUID, version_id_2: UUID) -> dict:
        """Compare two rate table versions with impact analysis."""
        comparison_result = await self._rate_table_service.compare_rate_versions(
            version_id_1, version_id_2
        )

        if isinstance(comparison_result, Err):
            return comparison_result

        comparison = comparison_result.value

        # Add business impact analysis
        impact_analysis = await self._analyze_rate_impact(comparison["differences"])
        comparison["business_impact"] = impact_analysis

        return Ok(comparison)

    @beartype
    async def schedule_ab_test(
        self,
        control_version_id: UUID,
        test_version_id: UUID,
        traffic_split: float,
        start_date: date,
        end_date: date,
        admin_user_id: UUID,
    ) -> Result[UUID, str]:
        """Schedule A/B test between rate versions."""
        # Validate inputs
        if not 0.1 <= traffic_split <= 0.5:
            return Err(
                "Traffic split must be between 10% and 50% for safety. "
                "Higher splits require executive approval."
            )

        if end_date <= start_date:
            return Err("End date must be after start date")

        if (end_date - start_date).days > 90:
            return Err("A/B tests cannot run longer than 90 days")

        # Check both versions are approved
        for version_id in [control_version_id, test_version_id]:
            version = await self._rate_table_service.get_rate_version(version_id)
            if isinstance(version, Err):
                return version
            if version.value.status not in ["approved", "active"]:
                return Err(f"Version {version_id} must be approved before A/B testing")

        # Create A/B test
        test_id = uuid4()
        query = """
            INSERT INTO rate_ab_tests (
                id, control_version_id, test_version_id,
                traffic_split, start_date, end_date,
                created_by, status
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'scheduled')
            RETURNING id
        """

        await self._db.execute(
            query,
            test_id,
            control_version_id,
            test_version_id,
            traffic_split,
            start_date,
            end_date,
            admin_user_id,
        )

        # Set up test routing configuration
        await self._configure_ab_test_routing(test_id)

        # Log activity
        await self._log_rate_activity(
            admin_user_id,
            "schedule_ab_test",
            test_id,
            {
                "control_version": control_version_id,
                "test_version": test_version_id,
                "traffic_split": traffic_split,
            },
        )

        return Ok(test_id)

    @beartype
    async def get_rate_analytics(
        self, table_name: str, date_from: date, date_to: date
    ) -> dict:
        """Get comprehensive rate analytics for admin dashboards."""
        try:
            # Get quote volume by rate version
            quote_analytics = await self._get_quote_analytics_by_rate(
                table_name, date_from, date_to
            )

            # Get conversion metrics
            conversion_metrics = await self._get_conversion_metrics(
                table_name, date_from, date_to
            )

            # Get A/B test results if any
            ab_test_results = await self._get_ab_test_performance(
                table_name, date_from, date_to
            )

            # Get competitive analysis
            competitive_analysis = await self._get_competitive_position(table_name)

            # Calculate summary metrics
            summary = await self._calculate_rate_summary(
                quote_analytics, conversion_metrics
            )

            return Ok(
                {
                    "period": {"from": date_from, "to": date_to},
                    "quote_analytics": quote_analytics,
                    "conversion_metrics": conversion_metrics,
                    "ab_test_results": ab_test_results,
                    "competitive_analysis": competitive_analysis,
                    "summary": summary,
                    "generated_at": datetime.utcnow(),
                }
            )

        except Exception as e:
            return Err(f"Analytics generation failed: {str(e)}")

    @beartype
    async def get_pending_approvals(self, admin_user_id: UUID) -> dict:
        """Get pending rate approvals for admin user."""
        query = """
            SELECT
                rtv.id,
                rtv.table_name,
                rtv.version_number,
                rtv.effective_date,
                rtv.created_at,
                rtv.created_by,
                u.email as creator_email,
                rtv.notes
            FROM rate_table_versions rtv
            JOIN admin_users u ON u.id = rtv.created_by
            WHERE rtv.status = 'pending'
                AND rtv.created_by != $1  -- Cannot approve own submissions
            ORDER BY rtv.created_at DESC
        """

        rows = await self._db.fetch(query, admin_user_id)

        approvals = []
        for row in rows:
            approvals.append(
                {
                    "version_id": row["id"],
                    "table_name": row["table_name"],
                    "version_number": row["version_number"],
                    "effective_date": row["effective_date"],
                    "created_at": row["created_at"],
                    "created_by": row["created_by"],
                    "creator_email": row["creator_email"],
                    "notes": row["notes"],
                    "days_pending": (datetime.utcnow() - row["created_at"]).days,
                }
            )

        return Ok(approvals)

    @beartype
    async def _check_permission(self, admin_user_id: UUID, permission: str) -> bool:
        """Check if admin user has specific permission."""
        query = """
            SELECT COUNT(*) > 0 as has_permission
            FROM admin_user_permissions
            WHERE user_id = $1 AND permission = $2 AND active = true
        """

        row = await self._db.fetchrow(query, admin_user_id, permission)
        return row["has_permission"] if row else False

    @beartype
    async def _check_rate_creator(self, version_id: UUID, admin_user_id: UUID) -> bool:
        """Check if admin user created the rate version."""
        query = """
            SELECT created_by = $2 as is_creator
            FROM rate_table_versions
            WHERE id = $1
        """

        row = await self._db.fetchrow(query, version_id, admin_user_id)
        return row["is_creator"] if row else False

    @beartype
    async def _create_approval_workflow(
        self, version_id: UUID, created_by: UUID
    ) -> None:
        """Create approval workflow for rate version."""
        workflow_id = uuid4()
        query = """
            INSERT INTO rate_approval_workflows (
                id, version_id, created_by, status, created_at
            ) VALUES ($1, $2, $3, 'pending', $4)
            RETURNING id
        """

        await self._db.execute(
            query, workflow_id, version_id, created_by, datetime.utcnow()
        )

        return Ok(workflow_id)

    @beartype
    async def _update_approval_workflow(
        self, version_id: UUID, approved_by: UUID, status: str
    ) -> None:
        """Update approval workflow status."""
        query = """
            UPDATE rate_approval_workflows
            SET status = $2,
                approved_by = $3,
                approved_at = $4
            WHERE version_id = $1
        """

        await self._db.execute(
            query, version_id, status, approved_by, datetime.utcnow()
        )

    @beartype
    async def _configure_ab_test_routing(self, test_id: UUID) -> None:
        """Configure routing for A/B test."""
        # Store routing configuration in cache for fast lookups
        test_data = await self._db.fetchrow(
            "SELECT * FROM rate_ab_tests WHERE id = $1", test_id
        )

        if test_data:
            config = {
                "test_id": str(test_id),
                "control_version": str(test_data["control_version_id"]),
                "test_version": str(test_data["test_version_id"]),
                "traffic_split": float(test_data["traffic_split"]),
                "start_date": test_data["start_date"].isoformat(),
                "end_date": test_data["end_date"].isoformat(),
            }

            # Cache for quick routing decisions
            await self._cache.set(
                f"ab_test:config:{test_id}",
                json.dumps(config),
                86400 * 90,  # 90 days max
            )

    @beartype
    async def _log_rate_activity(
        self,
        admin_user_id: UUID,
        action: str,
        target_id: UUID,
        details: dict[str, Any],
    ) -> None:
        """Log rate management activity for audit trail."""
        query = """
            INSERT INTO admin_activity_logs (
                id, user_id, action, target_type, target_id,
                details, created_at
            ) VALUES ($1, $2, $3, 'rate', $4, $5, $6)
        """

        await self._db.execute(
            query,
            uuid4(),
            admin_user_id,
            action,
            target_id,
            json.dumps(details),
            datetime.utcnow(),
        )

    @beartype
    async def _send_rate_approval_notifications(
        self, version_id: UUID, approved_by: UUID
    ) -> None:
        """Send notifications for rate approval."""
        # In production, this would integrate with notification service
        # For now, just log the notification
        print(f"Rate version {version_id} approved by {approved_by}")

    @beartype
    async def _analyze_rate_impact(self, differences: dict[str, Any]) -> dict[str, Any]:
        """Analyze business impact of rate changes."""
        modified = differences.get("modified", {})

        if not modified:
            return {
                "estimated_premium_impact": 0,
                "affected_policies": 0,
                "revenue_impact": 0,
            }

        # Calculate average rate change
        total_change = 0
        for coverage, change_data in modified.items():
            total_change += change_data["change_pct"]

        avg_change = total_change / len(modified) if modified else 0

        # Estimate impact (simplified - in production would be more sophisticated)
        return {
            "estimated_premium_impact": f"{avg_change:+.1f}%",
            "affected_policies": "All new and renewal quotes",
            "revenue_impact": f"Estimated {avg_change:+.1f}% change in premium revenue",
            "recommendation": self._get_rate_change_recommendation(avg_change),
        }

    @beartype
    def _get_rate_change_recommendation(self, avg_change: float) -> str:
        """Get recommendation based on rate change magnitude."""
        if avg_change > 10:
            return "Large increase - consider phased implementation"
        elif avg_change > 5:
            return "Moderate increase - monitor conversion impact"
        elif avg_change < -10:
            return "Large decrease - verify profitability maintained"
        elif avg_change < -5:
            return "Moderate decrease - opportunity for growth"
        else:
            return "Minor adjustment - proceed with standard deployment"

    @beartype
    async def _get_quote_analytics_by_rate(
        self, table_name: str, date_from: date, date_to: date
    ) -> list[dict[str, Any]]:
        """Get quote analytics grouped by rate version."""
        query = """
            SELECT
                rv.version_number,
                rv.effective_date,
                COUNT(q.id) as quote_count,
                AVG(q.total_premium) as avg_premium,
                MIN(q.total_premium) as min_premium,
                MAX(q.total_premium) as max_premium,
                COUNT(*) FILTER (WHERE q.status = 'bound') as conversions,
                CAST(COUNT(*) FILTER (WHERE q.status = 'bound') AS FLOAT) /
                    NULLIF(COUNT(q.id), 0) as conversion_rate
            FROM rate_table_versions rv
            LEFT JOIN quotes q ON q.rate_version = rv.table_name || '_v' || rv.version_number
            WHERE rv.table_name = $1
                AND q.created_at BETWEEN $2 AND $3
            GROUP BY rv.version_number, rv.effective_date
            ORDER BY rv.version_number DESC
        """

        rows = await self._db.fetch(query, table_name, date_from, date_to)
        return [dict(row) for row in rows]

    @beartype
    async def _get_conversion_metrics(
        self, table_name: str, date_from: date, date_to: date
    ) -> dict[str, Any]:
        """Get conversion funnel metrics."""
        query = """
            SELECT
                COUNT(*) FILTER (WHERE status = 'draft') as drafts,
                COUNT(*) FILTER (WHERE status = 'quoted') as quoted,
                COUNT(*) FILTER (WHERE status = 'bound') as bound,
                COUNT(*) FILTER (WHERE status = 'expired') as expired,
                COUNT(*) FILTER (WHERE status = 'declined') as declined,
                AVG(EXTRACT(EPOCH FROM (updated_at - created_at))/3600)
                    FILTER (WHERE status = 'bound') as avg_hours_to_bind
            FROM quotes
            WHERE created_at BETWEEN $1 AND $2
        """

        row = await self._db.fetchrow(query, date_from, date_to)

        if not row:
            return {}

        total = sum(
            row[k] or 0 for k in ["drafts", "quoted", "bound", "expired", "declined"]
        )

        return {
            "total_quotes": total,
            "conversion_funnel": {
                "draft": row["drafts"] or 0,
                "quoted": row["quoted"] or 0,
                "bound": row["bound"] or 0,
                "expired": row["expired"] or 0,
                "declined": row["declined"] or 0,
            },
            "conversion_rate": (row["bound"] or 0) / total if total > 0 else 0,
            "avg_hours_to_bind": round(row["avg_hours_to_bind"] or 0, 1),
        }

    @beartype
    async def _get_ab_test_performance(
        self, table_name: str, date_from: date, date_to: date
    ) -> list[dict[str, Any]]:
        """Get A/B test performance metrics."""
        query = """
            SELECT
                t.id as test_id,
                t.traffic_split,
                t.start_date,
                t.end_date,
                -- Control metrics
                COUNT(*) FILTER (WHERE q.ab_test_group = 'control') as control_quotes,
                AVG(q.total_premium) FILTER (WHERE q.ab_test_group = 'control') as control_avg_premium,
                COUNT(*) FILTER (WHERE q.ab_test_group = 'control' AND q.status = 'bound') as control_conversions,
                -- Test metrics
                COUNT(*) FILTER (WHERE q.ab_test_group = 'test') as test_quotes,
                AVG(q.total_premium) FILTER (WHERE q.ab_test_group = 'test') as test_avg_premium,
                COUNT(*) FILTER (WHERE q.ab_test_group = 'test' AND q.status = 'bound') as test_conversions
            FROM rate_ab_tests t
            LEFT JOIN quotes q ON q.ab_test_id = t.id
            WHERE t.start_date <= $2 AND t.end_date >= $1
            GROUP BY t.id, t.traffic_split, t.start_date, t.end_date
        """

        rows = await self._db.fetch(query, date_from, date_to)

        results = []
        for row in rows:
            control_rate = (
                row["control_conversions"] / row["control_quotes"]
                if row["control_quotes"] > 0
                else 0
            )
            test_rate = (
                row["test_conversions"] / row["test_quotes"]
                if row["test_quotes"] > 0
                else 0
            )

            results.append(
                {
                    "test_id": row["test_id"],
                    "traffic_split": float(row["traffic_split"]),
                    "date_range": {
                        "start": row["start_date"],
                        "end": row["end_date"],
                    },
                    "control_performance": {
                        "quotes": row["control_quotes"],
                        "avg_premium": float(row["control_avg_premium"] or 0),
                        "conversions": row["control_conversions"],
                        "conversion_rate": control_rate,
                    },
                    "test_performance": {
                        "quotes": row["test_quotes"],
                        "avg_premium": float(row["test_avg_premium"] or 0),
                        "conversions": row["test_conversions"],
                        "conversion_rate": test_rate,
                    },
                    "lift": {
                        "conversion_lift": (
                            (test_rate - control_rate) / control_rate * 100
                            if control_rate > 0
                            else 0
                        ),
                        "premium_lift": (
                            (row["test_avg_premium"] - row["control_avg_premium"])
                            / row["control_avg_premium"]
                            * 100
                            if row["control_avg_premium"] > 0
                            else 0
                        ),
                    },
                }
            )

        return results

    @beartype
    async def _get_competitive_position(self, table_name: str) -> dict[str, Any]:
        """Get competitive positioning analysis."""
        # In production, this would pull from competitive intelligence data
        # For now, return mock data
        return {
            "market_position": "competitive",
            "vs_market_average": "-5%",
            "recommendation": "Current rates are competitive",
        }

    @beartype
    async def _calculate_rate_summary(
        self,
        quote_analytics: list[dict[str, Any]],
        conversion_metrics: dict[str, Any],
    ) -> dict[str, Any]:
        """Calculate summary statistics."""
        if not quote_analytics:
            return {
                "total_quotes": 0,
                "total_premium": 0,
                "avg_premium": 0,
                "conversion_rate": 0,
            }

        total_quotes = sum(qa["quote_count"] for qa in quote_analytics)
        total_premium = sum(
            qa["quote_count"] * qa["avg_premium"] for qa in quote_analytics
        )

        return {
            "total_quotes": total_quotes,
            "total_premium": round(total_premium, 2),
            "avg_premium": (
                round(total_premium / total_quotes, 2) if total_quotes > 0 else 0
            ),
            "conversion_rate": conversion_metrics.get("conversion_rate", 0),
            "performance_trend": self._calculate_trend(quote_analytics),
        }

    @beartype
    def _calculate_trend(self, quote_analytics: list[dict[str, Any]]) -> str:
        """Calculate performance trend."""
        if len(quote_analytics) < 2:
            return "insufficient_data"

        # Compare most recent to previous
        recent = quote_analytics[0]
        previous = quote_analytics[1]

        if recent["avg_premium"] > previous["avg_premium"] * 1.05:
            return "increasing"
        elif recent["avg_premium"] < previous["avg_premium"] * 0.95:
            return "decreasing"
        else:
            return "stable"
