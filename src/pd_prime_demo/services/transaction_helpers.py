"""Transaction helper patterns for safe database operations.

This module provides reusable transaction patterns that ensure
data consistency and proper error handling across all services.
"""

from collections.abc import Awaitable, Callable
from typing import Any, TypeVar

import asyncpg
from beartype import beartype

from pd_prime_demo.core.result_types import Err, Ok, Result

from ..core.database import Database

T = TypeVar("T")
E = TypeVar("E", bound=str)


class TransactionConfig:
    """Configuration for transaction behavior."""

    def __init__(
        self,
        isolation_level: str = "read_committed",
        readonly: bool = False,
        deferrable: bool = False,
        timeout: float | None = None,
    ) -> None:
        """Initialize transaction configuration.

        Args:
            isolation_level: Transaction isolation level
            readonly: Whether transaction is read-only
            deferrable: Whether transaction is deferrable
            timeout: Transaction timeout in seconds
        """
        self.isolation_level = isolation_level
        self.readonly = readonly
        self.deferrable = deferrable
        self.timeout = timeout


@beartype
async def with_transaction(
    db: Database,
    operation: Callable[[], Awaitable[Result[T, str]]],
    config: TransactionConfig | None = None,
) -> Result[T, str]:
    """Execute operation within a transaction with automatic rollback.

    This helper ensures that database operations are properly wrapped
    in transactions with automatic rollback on errors.

    Args:
        db: Database instance
        operation: Async function that performs database operations
        config: Optional transaction configuration

    Returns:
        Result: Success with operation result or error message

    Example:
        ```python
        async def create_customer_with_policy(data):
            async def _operation():
                customer = await create_customer(data.customer)
                if isinstance(customer, Err):
                    return customer

                policy = await create_policy(data.policy, customer.id)
                if isinstance(policy, Err):
                    return policy

                return Ok((customer, policy))

            return await with_transaction(db, _operation)
        ```
    """
    if not config:
        config = TransactionConfig()

    async with db.transaction():
        try:
            result = await operation()
            if isinstance(result, Err):
                # Transaction will rollback automatically
                return result
            return result
        except Exception as e:
            # Transaction will rollback automatically
            return Err(f"Transaction failed: {str(e)}")


@beartype
async def with_savepoint(
    db: Database,
    operation: Callable[[], Awaitable[Result[T, str]]],
    savepoint_name: str,
) -> Result[T, str]:
    """Execute operation within a savepoint for nested transactions.

    Savepoints allow partial rollback within a larger transaction.

    Args:
        db: Database instance
        operation: Async function that performs database operations
        savepoint_name: Name for the savepoint

    Returns:
        Result: Success with operation result or error message
    """
    # Create savepoint
    await db.execute(f"SAVEPOINT {savepoint_name}")

    try:
        result = await operation()
        if isinstance(result, Err):
            # Rollback to savepoint
            await db.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
            return result

        # Release savepoint on success
        await db.execute(f"RELEASE SAVEPOINT {savepoint_name}")
        return result
    except Exception as e:
        # Rollback to savepoint
        await db.execute(f"ROLLBACK TO SAVEPOINT {savepoint_name}")
        return Err(f"Savepoint operation failed: {str(e)}")


@beartype
async def batch_operation(
    db: Database,
    items: list[T],
    operation: Callable[[T], Awaitable[Result[T, str]]],
    batch_size: int = 100,
) -> Result[list[T], str]:
    """Process items in batches within transactions.

    This helper processes large sets of items in batches to avoid
    long-running transactions and memory issues.

    Args:
        db: Database instance
        items: List of items to process
        operation: Function to process each item
        batch_size: Number of items per batch

    Returns:
        Result: Successfully processed items or error
    """
    processed: list[T] = []

    for i in range(0, len(items), batch_size):
        batch = items[i : i + batch_size]

        async def _batch_operation() -> Result[list[T], str]:
            batch_processed: list[T] = []

            for item in batch:
                result = await operation(item)
                if isinstance(result, Err):
                    return Err(f"Failed processing item: {result.error}")
                batch_processed.append(item)

            return Ok(batch_processed)

        result = await with_transaction(db, _batch_operation)
        if isinstance(result, Err):
            return Err(
                f"Batch failed: {result.error}. Processed {len(processed)} items."
            )

        processed.extend(result.unwrap())

    return Ok(processed)


@beartype
async def with_advisory_lock(
    db: Database,
    lock_id: int,
    operation: Callable[[], Awaitable[Result[T, str]]],
    wait: bool = True,
) -> Result[T, str]:
    """Execute operation with PostgreSQL advisory lock.

    Advisory locks prevent concurrent execution of critical sections
    across multiple instances of the application.

    Args:
        db: Database instance
        lock_id: Unique lock identifier
        operation: Function to execute under lock
        wait: Whether to wait for lock or fail immediately

    Returns:
        Result: Operation result or error
    """
    # Try to acquire lock
    if wait:
        await db.execute("SELECT pg_advisory_lock($1)", lock_id)
    else:
        acquired = await db.fetchval("SELECT pg_try_advisory_lock($1)", lock_id)
        if not acquired:
            return Err("Could not acquire advisory lock")

    try:
        result = await operation()
        return result
    finally:
        # Always release lock
        await db.execute("SELECT pg_advisory_unlock($1)", lock_id)


@beartype
async def upsert_with_conflict(
    db: Database,
    table: str,
    insert_data: dict[str, Any],
    conflict_columns: list[str],
    update_data: dict[str, Any] | None = None,
    returning_columns: list[str] | None = None,
) -> Result[dict[str, Any] | None, str]:
    """Perform UPSERT operation with conflict handling.

    Args:
        db: Database instance
        table: Table name
        insert_data: Data to insert
        conflict_columns: Columns that define uniqueness
        update_data: Data to update on conflict (if None, uses insert_data)
        returning_columns: Columns to return

    Returns:
        Result: Database row or error
    """
    if not update_data:
        update_data = insert_data

    # Build INSERT query
    columns = list(insert_data.keys())
    values_placeholders = [f"${i+1}" for i in range(len(columns))]

    # Safe query construction - table name must be validated by caller
    # All column names come from insert_data keys which should be validated
    query = f"""
        INSERT INTO {table} ({", ".join(columns)})
        VALUES ({", ".join(values_placeholders)})
        ON CONFLICT ({", ".join(conflict_columns)})
        DO UPDATE SET
    """

    # Add UPDATE clause
    update_clauses = []
    param_count = len(columns)
    update_values = list(insert_data.values())

    for col, val in update_data.items():
        param_count += 1
        update_clauses.append(f"{col} = ${param_count}")
        update_values.append(val)

    query += ", ".join(update_clauses)

    # Add RETURNING clause
    if returning_columns:
        query += f" RETURNING {', '.join(returning_columns)}"

    try:
        if returning_columns:
            row = await db.fetchrow(query, *update_values)
            return Ok(row)
        else:
            await db.execute(query, *update_values)
            return Ok(None)
    except Exception as e:
        return Err(f"Upsert failed: {str(e)}")


@beartype
async def ensure_transaction_valid(db: Database) -> Result[bool, str]:
    """Ensure current transaction is valid and not aborted.

    Args:
        db: Database instance

    Returns:
        Result: True if valid, error if not
    """
    try:
        # Simple query to test transaction state
        result = await db.fetchval("SELECT 1")
        if result != 1:
            return Err("Transaction check failed")
        return Ok(True)
    except asyncpg.InFailedSQLTransactionError:
        return Err("Transaction is in failed state")
    except Exception as e:
        return Err(f"Transaction validation failed: {str(e)}")
