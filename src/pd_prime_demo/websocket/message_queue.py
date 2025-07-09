"""Redis-backed message queue for WebSocket message processing."""

import asyncio
import logging
from datetime import datetime
from uuid import UUID, uuid4

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

from pd_prime_demo.core.result_types import Err, Ok, Result

from ..core.cache import Cache
from .manager import MessagePriority, WebSocketMessage

logger = logging.getLogger(__name__)


class QueueStats(BaseModel):
    """Statistics for message queue."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    queue_name: str = Field(...)
    total_messages: int = Field(default=0, ge=0)
    pending_messages: int = Field(default=0, ge=0)
    processing_messages: int = Field(default=0, ge=0)
    failed_messages: int = Field(default=0, ge=0)
    avg_processing_time_ms: float = Field(default=0.0, ge=0.0)
    last_processed: datetime | None = Field(default=None)


class MessageQueueConfig(BaseModel):
    """Configuration for message queue."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    redis_key_prefix: str = Field(default="ws_queue")
    max_retries: int = Field(default=3, ge=0, le=10)
    retry_delay_seconds: int = Field(default=1, ge=1, le=60)
    message_ttl_seconds: int = Field(default=300, ge=60, le=3600)  # 5 minutes
    batch_size: int = Field(default=10, ge=1, le=100)
    processing_timeout_seconds: int = Field(default=30, ge=10, le=300)
    dead_letter_queue_enabled: bool = Field(default=True)
    metrics_enabled: bool = Field(default=True)


class QueuedMessage(BaseModel):
    """A message in the queue with metadata."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        validate_assignment=True,
        str_strip_whitespace=True,
        validate_default=True,
    )

    id: UUID = Field(default_factory=uuid4)
    message: WebSocketMessage = Field(...)
    connection_id: str = Field(...)
    enqueued_at: datetime = Field(default_factory=datetime.now)
    retry_count: int = Field(default=0, ge=0)
    processing_started_at: datetime | None = Field(default=None)
    last_error: str | None = Field(default=None)

    def is_expired(self, ttl_seconds: int) -> bool:
        """Check if message has expired."""
        return (datetime.now() - self.enqueued_at).total_seconds() > ttl_seconds

    def should_retry(self, max_retries: int) -> bool:
        """Check if message should be retried."""
        return self.retry_count < max_retries

    def get_retry_delay(self, base_delay: int) -> int:
        """Get exponential backoff delay for retry."""
        return int(min(base_delay * (2**self.retry_count), 60))  # Max 60 seconds


class RedisMessageQueue:
    """Redis-backed message queue with priority support and reliability features."""

    def __init__(self, cache: Cache, config: MessageQueueConfig | None = None) -> None:
        """Initialize Redis message queue."""
        self._cache = cache
        self._config = config or MessageQueueConfig()

        # Queue names by priority
        self._queue_names = {
            MessagePriority.CRITICAL: f"{self._config.redis_key_prefix}:critical",
            MessagePriority.HIGH: f"{self._config.redis_key_prefix}:high",
            MessagePriority.NORMAL: f"{self._config.redis_key_prefix}:normal",
            MessagePriority.LOW: f"{self._config.redis_key_prefix}:low",
        }

        # Processing and dead letter queues
        self._processing_queue = f"{self._config.redis_key_prefix}:processing"
        self._dead_letter_queue = f"{self._config.redis_key_prefix}:dead_letter"

        # Metrics
        self._metrics_key = f"{self._config.redis_key_prefix}:metrics"

        # Background tasks
        self._cleanup_task: asyncio.Task[None] | None = None
        self._metrics_task: asyncio.Task[None] | None = None

        # Performance tracking
        self._processing_times: dict[str, list[float]] = {}

    async def start(self) -> None:
        """Start background tasks."""
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        if self._config.metrics_enabled:
            self._metrics_task = asyncio.create_task(self._metrics_loop())

    async def stop(self) -> None:
        """Stop background tasks."""
        for task in [self._cleanup_task, self._metrics_task]:
            if task and not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    @beartype
    async def enqueue(
        self, message: WebSocketMessage, connection_id: str
    ) -> Result[UUID, str]:
        """Enqueue a message for processing."""
        try:
            # Create queued message
            queued_msg = QueuedMessage(message=message, connection_id=connection_id)

            # Determine queue based on priority
            queue_name = self._queue_names.get(
                message.priority, self._queue_names[MessagePriority.NORMAL]
            )

            # Serialize message
            message_data = queued_msg.model_dump_json()

            # Add to queue
            await self._cache.lpush(queue_name, message_data)

            # Update metrics
            if self._config.metrics_enabled:
                await self._update_enqueue_metrics(queue_name)

            logger.debug(f"Enqueued message {queued_msg.id} to {queue_name}")
            return Ok(queued_msg.id)

        except Exception as e:
            logger.error(f"Failed to enqueue message: {e}")
            return Err(f"Failed to enqueue message: {str(e)}")

    @beartype
    async def dequeue(
        self, timeout_seconds: int = 1
    ) -> Result[QueuedMessage | None, str]:
        """Dequeue a message for processing with priority order."""
        try:
            # Try queues in priority order
            for priority in [
                MessagePriority.CRITICAL,
                MessagePriority.HIGH,
                MessagePriority.NORMAL,
                MessagePriority.LOW,
            ]:
                queue_name = self._queue_names[priority]

                # Try to get message from this priority queue
                result = await self._cache.brpoplpush(
                    queue_name, self._processing_queue, timeout=timeout_seconds
                )

                if result:
                    # Deserialize message
                    queued_msg = QueuedMessage.model_validate_json(result)

                    # Update processing started time
                    queued_msg = queued_msg.model_copy(
                        update={"processing_started_at": datetime.now()}
                    )

                    # Update processing queue with updated message
                    await self._cache.lrem(self._processing_queue, 1, result)
                    await self._cache.lpush(
                        self._processing_queue, queued_msg.model_dump_json()
                    )

                    logger.debug(f"Dequeued message {queued_msg.id} from {queue_name}")
                    return Ok(queued_msg)

            # No messages available
            return Ok(None)

        except Exception as e:
            logger.error(f"Failed to dequeue message: {e}")
            return Err(f"Failed to dequeue message: {str(e)}")

    @beartype
    async def acknowledge(self, message_id: UUID) -> Result[None, str]:
        """Acknowledge successful processing of a message."""
        try:
            # Find and remove message from processing queue
            processing_messages = await self._cache.lrange(
                self._processing_queue, 0, -1
            )

            for msg_data in processing_messages:
                queued_msg = QueuedMessage.model_validate_json(msg_data)
                if queued_msg.id == message_id:
                    # Remove from processing queue
                    await self._cache.lrem(self._processing_queue, 1, msg_data)

                    # Update metrics
                    if self._config.metrics_enabled:
                        await self._update_ack_metrics(queued_msg)

                    logger.debug(f"Acknowledged message {message_id}")
                    return Ok(None)

            return Err(f"Message {message_id} not found in processing queue")

        except Exception as e:
            logger.error(f"Failed to acknowledge message {message_id}: {e}")
            return Err(f"Failed to acknowledge message: {str(e)}")

    @beartype
    async def reject(
        self, message_id: UUID, error: str, retry: bool = True
    ) -> Result[None, str]:
        """Reject a message and optionally retry or send to dead letter queue."""
        try:
            # Find message in processing queue
            processing_messages = await self._cache.lrange(
                self._processing_queue, 0, -1
            )

            for msg_data in processing_messages:
                queued_msg = QueuedMessage.model_validate_json(msg_data)
                if queued_msg.id == message_id:
                    # Remove from processing queue
                    await self._cache.lrem(self._processing_queue, 1, msg_data)

                    # Update retry count and error
                    queued_msg = queued_msg.model_copy(
                        update={
                            "retry_count": queued_msg.retry_count + 1,
                            "last_error": error,
                            "processing_started_at": None,
                        }
                    )

                    if retry and queued_msg.should_retry(self._config.max_retries):
                        # Schedule retry with exponential backoff
                        delay = queued_msg.get_retry_delay(
                            self._config.retry_delay_seconds
                        )
                        await asyncio.sleep(delay)

                        # Re-enqueue with updated retry count
                        queue_name = self._queue_names.get(
                            queued_msg.message.priority,
                            self._queue_names[MessagePriority.NORMAL],
                        )
                        await self._cache.lpush(
                            queue_name, queued_msg.model_dump_json()
                        )

                        logger.debug(
                            f"Retrying message {message_id} (attempt {queued_msg.retry_count})"
                        )
                    else:
                        # Send to dead letter queue
                        if self._config.dead_letter_queue_enabled:
                            await self._cache.lpush(
                                self._dead_letter_queue, queued_msg.model_dump_json()
                            )
                            logger.warning(
                                f"Message {message_id} sent to dead letter queue: {error}"
                            )

                    # Update metrics
                    if self._config.metrics_enabled:
                        await self._update_reject_metrics(queued_msg)

                    return Ok(None)

            return Err(f"Message {message_id} not found in processing queue")

        except Exception as e:
            logger.error(f"Failed to reject message {message_id}: {e}")
            return Err(f"Failed to reject message: {str(e)}")

    @beartype
    async def get_stats(self) -> Result[list[QueueStats], str]:
        """Get statistics for all queues."""
        try:
            stats = []

            for priority, queue_name in self._queue_names.items():
                # Get queue lengths
                pending_count = await self._cache.llen(queue_name)

                # Get processing time stats
                avg_time = 0.0
                if queue_name in self._processing_times:
                    times = self._processing_times[queue_name]
                    avg_time = sum(times) / len(times) if times else 0.0

                # Get metrics from Redis
                metrics_data = await self._cache.hgetall(
                    f"{self._metrics_key}:{queue_name}"
                )

                stats.append(
                    QueueStats(
                        queue_name=queue_name,
                        total_messages=int(metrics_data.get("total_messages", 0)),
                        pending_messages=pending_count,
                        processing_messages=int(
                            metrics_data.get("processing_messages", 0)
                        ),
                        failed_messages=int(metrics_data.get("failed_messages", 0)),
                        avg_processing_time_ms=avg_time,
                        last_processed=(
                            datetime.fromisoformat(metrics_data["last_processed"])
                            if metrics_data.get("last_processed")
                            else None
                        ),
                    )
                )

            return Ok(stats)

        except Exception as e:
            logger.error(f"Failed to get queue stats: {e}")
            return Err(f"Failed to get queue stats: {str(e)}")

    async def _cleanup_loop(self) -> None:
        """Background task to clean up expired messages."""
        while True:
            try:
                await asyncio.sleep(60)  # Run every minute

                # Clean up expired messages in processing queue
                processing_messages = await self._cache.lrange(
                    self._processing_queue, 0, -1
                )

                for msg_data in processing_messages:
                    try:
                        queued_msg = QueuedMessage.model_validate_json(msg_data)

                        # Check if message has been processing too long
                        if (
                            queued_msg.processing_started_at
                            and (
                                datetime.now() - queued_msg.processing_started_at
                            ).total_seconds()
                            > self._config.processing_timeout_seconds
                        ):
                            # Remove from processing queue and reject
                            await self._cache.lrem(self._processing_queue, 1, msg_data)
                            await self.reject(
                                queued_msg.id, "Processing timeout", retry=True
                            )

                        # Check if message is expired
                        elif queued_msg.is_expired(self._config.message_ttl_seconds):
                            await self._cache.lrem(self._processing_queue, 1, msg_data)
                            logger.warning(
                                f"Expired message {queued_msg.id} removed from processing queue"
                            )

                    except Exception as e:
                        logger.error(f"Error processing message during cleanup: {e}")
                        # Remove malformed message
                        await self._cache.lrem(self._processing_queue, 1, msg_data)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}")

    async def _metrics_loop(self) -> None:
        """Background task to update metrics."""
        while True:
            try:
                await asyncio.sleep(30)  # Update every 30 seconds

                # Update processing times
                for queue_name, times in self._processing_times.items():
                    if times:
                        avg_time = sum(times) / len(times)
                        await self._cache.hset(
                            f"{self._metrics_key}:{queue_name}",
                            "avg_processing_time_ms",
                            str(avg_time),
                        )

                        # Keep only recent times (last 100)
                        self._processing_times[queue_name] = times[-100:]

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in metrics loop: {e}")

    async def _update_enqueue_metrics(self, queue_name: str) -> None:
        """Update metrics when message is enqueued."""
        await self._cache.hincrby(
            f"{self._metrics_key}:{queue_name}", "total_messages", 1
        )

    async def _update_ack_metrics(self, queued_msg: QueuedMessage) -> None:
        """Update metrics when message is acknowledged."""
        if queued_msg.processing_started_at:
            processing_time = (
                datetime.now() - queued_msg.processing_started_at
            ).total_seconds() * 1000

            queue_name = self._queue_names.get(
                queued_msg.message.priority, self._queue_names[MessagePriority.NORMAL]
            )

            # Add to processing times
            if queue_name not in self._processing_times:
                self._processing_times[queue_name] = []
            self._processing_times[queue_name].append(processing_time)

            # Update last processed time
            await self._cache.hset(
                f"{self._metrics_key}:{queue_name}",
                "last_processed",
                datetime.now().isoformat(),
            )

    async def _update_reject_metrics(self, queued_msg: QueuedMessage) -> None:
        """Update metrics when message is rejected."""
        queue_name = self._queue_names.get(
            queued_msg.message.priority, self._queue_names[MessagePriority.NORMAL]
        )

        await self._cache.hincrby(
            f"{self._metrics_key}:{queue_name}", "failed_messages", 1
        )
