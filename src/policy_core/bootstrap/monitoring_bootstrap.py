"""Utilities to ensure monitoring database artifacts (pg_stat_statements + admin materialized views) are present.

This is called once on application startup; it is idempotent and SAFE to run on every boot.
"""

from __future__ import annotations

import logging

from beartype import beartype

from ..core.admin_query_optimizer import AdminQueryOptimizer
from ..core.database import Database

logger = logging.getLogger(__name__)


@beartype
async def ensure_monitoring_artifacts(db: Database) -> None:  # noqa: D401 (simple)
    """Create pg_stat_statements extension and materialised admin views if missing."""

    # 1. Enable pg_stat_statements if we have the privilege
    try:
        async with db.acquire_admin() as conn:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS pg_stat_statements")
            logger.info("✅ pg_stat_statements extension ensured")
    except Exception as exc:  # pragma: no cover – depends on server perms
        logger.warning(
            "⚠️ Could not enable pg_stat_statements – continuing without: %s", exc
        )

    # 2. Create / refresh materialised views necessary for admin monitoring
    optimizer = AdminQueryOptimizer(db)
    result = await optimizer.create_materialized_views()
    if result.is_err():
        logger.warning(
            "⚠️ Failed to create admin materialised views: %s", result.err_value
        )
    else:
        from typing import cast

        logger.info(
            "✅ Monitoring materialised views ensured: %s",
            ", ".join(cast(list[str], result.ok_value)),
        )
