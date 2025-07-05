# Agent 08: WebSocket Engineer

## YOUR MISSION

Build comprehensive real-time infrastructure with WebSocket support for live quote updates, collaborative editing, analytics dashboards, and push notifications.

## CRITICAL: NO SILENT FALLBACKS PRINCIPLE

### Real-Time System Requirements (NON-NEGOTIABLE)

1. **EXPLICIT CONNECTION VALIDATION**:
   - NO default connection timeouts without explicit business rules
   - NO silent connection recovery attempts without logging
   - NO assumed user permissions for room access
   - ALL connection states MUST be explicitly tracked

2. **FAIL FAST ON CONNECTION ISSUES**:

   ```python
   # ❌ FORBIDDEN - Silent reconnection attempts
   async def handle_disconnect():
       try:
           await reconnect()  # Silent retry
       except:
           pass  # Swallow errors

   # ✅ REQUIRED - Explicit connection management
   async def handle_disconnect(connection_id: str) -> Result[None, str]:
       if connection_id not in active_connections:
           return Err(
               f"Connection {connection_id} not found in active pool. "
               "Required action: Check connection state in admin dashboard. "
               "System will not attempt automatic reconnection."
           )
   ```

3. **REAL-TIME MESSAGE VALIDATION**:

   ```python
   # ❌ FORBIDDEN - Assume message structure
   user_id = message.get("user_id", "anonymous")  # Silent fallback

   # ✅ REQUIRED - Explicit message validation
   if "user_id" not in message:
       await send_error(connection_id,
           "Message validation error: user_id is required. "
           "Required action: Include user_id in all WebSocket messages."
       )
       return Err("Invalid message structure")
   ```

4. **ROOM ACCESS CONTROL**: Never grant default room access without explicit permissions

## MANDATORY PRE-WORK

1. Read ALL documents listed in AGENT_TEMPLATE.md FIRST
2. Specifically study:
   - FastAPI WebSocket documentation (30-second search if needed)
   - `.sage/source_documents/DEMO_OVERALL_ARCHITECTURE.md` for real-time requirements
   - Existing API structure in `src/pd_prime_demo/api/`

## SPECIFIC TASKS

### 1. Create WebSocket Manager (`src/pd_prime_demo/websocket/manager.py`)

```python
"""WebSocket connection and room management."""

import asyncio
import json
from datetime import datetime
from typing import Dict, Set, List, Optional, Any
from uuid import UUID

from fastapi import WebSocket, WebSocketDisconnect
from beartype import beartype

from ..core.cache import Cache
from ..core.database import Database


class ConnectionManager:
    """Manage WebSocket connections and rooms."""

    def __init__(self, cache: Cache, db: Database) -> None:
        """Initialize connection manager."""
        self._cache = cache
        self._db = db

        # Active connections by connection ID
        self._connections: Dict[str, WebSocket] = {}

        # User to connection mapping
        self._user_connections: Dict[UUID, Set[str]] = {}

        # Room subscriptions
        self._room_subscriptions: Dict[str, Set[str]] = {}

        # Connection metadata
        self._connection_metadata: Dict[str, Dict[str, Any]] = {}

        # Heartbeat tracking
        self._last_ping: Dict[str, datetime] = {}

        # Start heartbeat task
        self._heartbeat_task = None

    async def start(self) -> None:
        """Start background tasks."""
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop(self) -> None:
        """Stop background tasks and close all connections."""
        if self._heartbeat_task:
            self._heartbeat_task.cancel()

        # Close all connections
        for conn_id in list(self._connections.keys()):
            await self.disconnect(conn_id)

    @beartype
    async def connect(
        self,
        websocket: WebSocket,
        connection_id: str,
        user_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()

        # Store connection
        self._connections[connection_id] = websocket
        self._connection_metadata[connection_id] = metadata or {}
        self._last_ping[connection_id] = datetime.now()

        # Map user to connection
        if user_id:
            if user_id not in self._user_connections:
                self._user_connections[user_id] = set()
            self._user_connections[user_id].add(connection_id)
            self._connection_metadata[connection_id]['user_id'] = user_id

        # Store in database for distributed systems
        await self._store_connection(connection_id, user_id, metadata)

        # Send welcome message
        await self.send_personal_message(
            connection_id,
            {
                'type': 'connection',
                'status': 'connected',
                'connection_id': connection_id,
                'timestamp': datetime.now().isoformat(),
            }
        )

    @beartype
    async def disconnect(self, connection_id: str) -> None:
        """Disconnect and cleanup a WebSocket connection."""
        if connection_id not in self._connections:
            return

        # Get user ID if exists
        metadata = self._connection_metadata.get(connection_id, {})
        user_id = metadata.get('user_id')

        # Remove from user connections
        if user_id and user_id in self._user_connections:
            self._user_connections[user_id].discard(connection_id)
            if not self._user_connections[user_id]:
                del self._user_connections[user_id]

        # Remove from all rooms
        for room_id in list(self._room_subscriptions.keys()):
            self._room_subscriptions[room_id].discard(connection_id)
            if not self._room_subscriptions[room_id]:
                del self._room_subscriptions[room_id]

        # Close WebSocket
        websocket = self._connections[connection_id]
        try:
            await websocket.close()
        except Exception:
            pass  # Already closed

        # Cleanup
        del self._connections[connection_id]
        del self._connection_metadata[connection_id]
        self._last_ping.pop(connection_id, None)

        # Remove from database
        await self._remove_connection(connection_id)

    @beartype
    async def subscribe_to_room(
        self,
        connection_id: str,
        room_id: str,
    ) -> None:
        """Subscribe a connection to a room."""
        if connection_id not in self._connections:
            raise ValueError(f"Connection {connection_id} not found")

        if room_id not in self._room_subscriptions:
            self._room_subscriptions[room_id] = set()

        self._room_subscriptions[room_id].add(connection_id)

        # Store subscription in cache for distributed systems
        await self._cache.sadd(f"room:{room_id}:connections", connection_id)

        # Notify room of new member
        await self.send_to_room(
            room_id,
            {
                'type': 'room_event',
                'event': 'member_joined',
                'room_id': room_id,
                'connection_id': connection_id,
                'timestamp': datetime.now().isoformat(),
            },
            exclude=[connection_id],
        )

    @beartype
    async def unsubscribe_from_room(
        self,
        connection_id: str,
        room_id: str,
    ) -> None:
        """Unsubscribe a connection from a room."""
        if room_id in self._room_subscriptions:
            self._room_subscriptions[room_id].discard(connection_id)
            if not self._room_subscriptions[room_id]:
                del self._room_subscriptions[room_id]

        # Remove from cache
        await self._cache.srem(f"room:{room_id}:connections", connection_id)

        # Notify room of member leaving
        await self.send_to_room(
            room_id,
            {
                'type': 'room_event',
                'event': 'member_left',
                'room_id': room_id,
                'connection_id': connection_id,
                'timestamp': datetime.now().isoformat(),
            }
        )

    @beartype
    async def send_personal_message(
        self,
        connection_id: str,
        message: Dict[str, Any],
    ) -> None:
        """Send a message to a specific connection."""
        if connection_id in self._connections:
            websocket = self._connections[connection_id]
            try:
                await websocket.send_json(message)
            except Exception as e:
                # Connection failed, disconnect
                await self.disconnect(connection_id)

    @beartype
    async def send_to_user(
        self,
        user_id: UUID,
        message: Dict[str, Any],
    ) -> None:
        """Send a message to all connections of a user."""
        if user_id in self._user_connections:
            tasks = []
            for conn_id in self._user_connections[user_id]:
                tasks.append(self.send_personal_message(conn_id, message))

            await asyncio.gather(*tasks, return_exceptions=True)

    @beartype
    async def send_to_room(
        self,
        room_id: str,
        message: Dict[str, Any],
        exclude: Optional[List[str]] = None,
    ) -> None:
        """Send a message to all connections in a room."""
        if room_id not in self._room_subscriptions:
            return

        exclude = exclude or []
        tasks = []

        for conn_id in self._room_subscriptions[room_id]:
            if conn_id not in exclude:
                tasks.append(self.send_personal_message(conn_id, message))

        await asyncio.gather(*tasks, return_exceptions=True)

    @beartype
    async def broadcast(
        self,
        message: Dict[str, Any],
        exclude: Optional[List[str]] = None,
    ) -> None:
        """Broadcast a message to all connections."""
        exclude = exclude or []
        tasks = []

        for conn_id in self._connections:
            if conn_id not in exclude:
                tasks.append(self.send_personal_message(conn_id, message))

        await asyncio.gather(*tasks, return_exceptions=True)

    @beartype
    async def handle_message(
        self,
        connection_id: str,
        message: Dict[str, Any],
    ) -> None:
        """Handle incoming WebSocket message."""
        message_type = message.get('type')

        if message_type == 'ping':
            # Update last ping time
            self._last_ping[connection_id] = datetime.now()

            # Send pong
            await self.send_personal_message(
                connection_id,
                {'type': 'pong', 'timestamp': datetime.now().isoformat()}
            )

        elif message_type == 'subscribe':
            room_id = message.get('room_id')
            if room_id:
                await self.subscribe_to_room(connection_id, room_id)

        elif message_type == 'unsubscribe':
            room_id = message.get('room_id')
            if room_id:
                await self.unsubscribe_from_room(connection_id, room_id)

        else:
            # Delegate to specific handlers
            pass

    async def _heartbeat_loop(self) -> None:
        """Send periodic heartbeats and check connection health."""
        while True:
            try:
                await asyncio.sleep(30)  # 30 second intervals

                now = datetime.now()
                disconnected = []

                # Check all connections
                for conn_id, last_ping in self._last_ping.items():
                    # If no ping in 90 seconds, consider dead
                    if (now - last_ping).total_seconds() > 90:
                        disconnected.append(conn_id)
                    else:
                        # Send heartbeat
                        await self.send_personal_message(
                            conn_id,
                            {'type': 'heartbeat', 'timestamp': now.isoformat()}
                        )

                # Disconnect dead connections
                for conn_id in disconnected:
                    await self.disconnect(conn_id)

            except asyncio.CancelledError:
                break
            except Exception as e:
                # Log error but continue
                pass

    async def _store_connection(
        self,
        connection_id: str,
        user_id: Optional[UUID],
        metadata: Optional[Dict[str, Any]],
    ) -> None:
        """Store connection info in database."""
        await self._db.execute(
            """
            INSERT INTO websocket_connections
            (connection_id, user_id, connected_at, ip_address, user_agent)
            VALUES ($1, $2, $3, $4, $5)
            """,
            connection_id,
            user_id,
            datetime.now(),
            metadata.get('ip_address') if metadata else None,
            metadata.get('user_agent') if metadata else None,
        )

    async def _remove_connection(self, connection_id: str) -> None:
        """Remove connection from database."""
        await self._db.execute(
            """
            UPDATE websocket_connections
            SET disconnected_at = $2
            WHERE connection_id = $1
            """,
            connection_id,
            datetime.now(),
        )
```

### 2. Create Quote Real-Time Handler (`src/pd_prime_demo/websocket/handlers/quotes.py`)

```python
"""Real-time quote updates handler."""

from typing import Dict, Any
from uuid import UUID
from decimal import Decimal

from beartype import beartype

from ...services.quote_service import QuoteService
from ..manager import ConnectionManager


class QuoteWebSocketHandler:
    """Handle real-time quote operations."""

    def __init__(
        self,
        manager: ConnectionManager,
        quote_service: QuoteService,
    ) -> None:
        """Initialize quote handler."""
        self._manager = manager
        self._quote_service = quote_service

    @beartype
    async def handle_quote_subscribe(
        self,
        connection_id: str,
        quote_id: UUID,
    ) -> None:
        """Subscribe to real-time quote updates."""
        room_id = f"quote:{quote_id}"
        await self._manager.subscribe_to_room(connection_id, room_id)

        # Send current quote state
        quote_result = await self._quote_service.get_quote(quote_id)
        if quote_result.is_ok():
            quote = quote_result.unwrap()
            if quote:
                await self._manager.send_personal_message(
                    connection_id,
                    {
                        'type': 'quote_state',
                        'quote': quote.model_dump(),
                        'timestamp': datetime.now().isoformat(),
                    }
                )

    @beartype
    async def broadcast_quote_update(
        self,
        quote_id: UUID,
        update_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Broadcast quote update to all subscribers."""
        room_id = f"quote:{quote_id}"

        message = {
            'type': 'quote_update',
            'update_type': update_type,
            'quote_id': str(quote_id),
            'data': data,
            'timestamp': datetime.now().isoformat(),
        }

        await self._manager.send_to_room(room_id, message)

    @beartype
    async def handle_collaborative_edit(
        self,
        connection_id: str,
        quote_id: UUID,
        field: str,
        value: Any,
    ) -> None:
        """Handle collaborative quote editing."""
        # Validate edit permission
        metadata = self._manager._connection_metadata.get(connection_id, {})
        user_id = metadata.get('user_id')

        # Broadcast change to other users
        room_id = f"quote:{quote_id}"
        await self._manager.send_to_room(
            room_id,
            {
                'type': 'field_update',
                'quote_id': str(quote_id),
                'field': field,
                'value': value,
                'updated_by': str(user_id) if user_id else 'anonymous',
                'timestamp': datetime.now().isoformat(),
            },
            exclude=[connection_id],
        )

    @beartype
    async def stream_calculation_progress(
        self,
        quote_id: UUID,
        progress: float,
        stage: str,
    ) -> None:
        """Stream calculation progress to subscribers."""
        room_id = f"quote:{quote_id}"

        await self._manager.send_to_room(
            room_id,
            {
                'type': 'calculation_progress',
                'quote_id': str(quote_id),
                'progress': progress,
                'stage': stage,
                'timestamp': datetime.now().isoformat(),
            }
        )
```

### 3. Create Analytics Dashboard Handler (`src/pd_prime_demo/websocket/handlers/analytics.py`)

```python
"""Real-time analytics dashboard handler."""

import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List

from beartype import beartype

from ...core.database import Database
from ..manager import ConnectionManager


class AnalyticsWebSocketHandler:
    """Stream real-time analytics data."""

    def __init__(
        self,
        manager: ConnectionManager,
        db: Database,
    ) -> None:
        """Initialize analytics handler."""
        self._manager = manager
        self._db = db
        self._streaming_tasks = {}

    @beartype
    async def start_analytics_stream(
        self,
        connection_id: str,
        dashboard_type: str,
        filters: Dict[str, Any],
    ) -> None:
        """Start streaming analytics data to connection."""
        # Subscribe to analytics room
        room_id = f"analytics:{dashboard_type}"
        await self._manager.subscribe_to_room(connection_id, room_id)

        # Start streaming task
        task_key = f"{connection_id}:{dashboard_type}"
        if task_key in self._streaming_tasks:
            self._streaming_tasks[task_key].cancel()

        self._streaming_tasks[task_key] = asyncio.create_task(
            self._stream_dashboard_data(connection_id, dashboard_type, filters)
        )

    @beartype
    async def stop_analytics_stream(
        self,
        connection_id: str,
        dashboard_type: str,
    ) -> None:
        """Stop streaming analytics data."""
        task_key = f"{connection_id}:{dashboard_type}"
        if task_key in self._streaming_tasks:
            self._streaming_tasks[task_key].cancel()
            del self._streaming_tasks[task_key]

        room_id = f"analytics:{dashboard_type}"
        await self._manager.unsubscribe_from_room(connection_id, room_id)

    async def _stream_dashboard_data(
        self,
        connection_id: str,
        dashboard_type: str,
        filters: Dict[str, Any],
    ) -> None:
        """Stream dashboard data at regular intervals."""
        try:
            while True:
                if dashboard_type == 'quotes':
                    data = await self._get_quote_analytics(filters)
                elif dashboard_type == 'conversion':
                    data = await self._get_conversion_analytics(filters)
                elif dashboard_type == 'performance':
                    data = await self._get_performance_analytics(filters)
                else:
                    data = {}

                await self._manager.send_personal_message(
                    connection_id,
                    {
                        'type': 'analytics_update',
                        'dashboard': dashboard_type,
                        'data': data,
                        'timestamp': datetime.now().isoformat(),
                    }
                )

                # Update every 5 seconds
                await asyncio.sleep(5)

        except asyncio.CancelledError:
            pass

    @beartype
    async def _get_quote_analytics(
        self,
        filters: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Get real-time quote analytics."""
        # Time range
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=filters.get('hours', 24))

        # Query metrics
        metrics = await self._db.fetchrow(
            """
            SELECT
                COUNT(*) as total_quotes,
                COUNT(DISTINCT customer_id) as unique_customers,
                AVG(total_premium) as avg_premium,
                COUNT(*) FILTER (WHERE status = 'quoted') as quoted_count,
                COUNT(*) FILTER (WHERE status = 'bound') as bound_count,
                COUNT(*) FILTER (WHERE status = 'expired') as expired_count
            FROM quotes
            WHERE created_at BETWEEN $1 AND $2
            """,
            start_time,
            end_time,
        )

        # Quote timeline
        timeline = await self._db.fetch(
            """
            SELECT
                date_trunc('hour', created_at) as hour,
                COUNT(*) as count,
                AVG(total_premium) as avg_premium
            FROM quotes
            WHERE created_at BETWEEN $1 AND $2
            GROUP BY hour
            ORDER BY hour
            """,
            start_time,
            end_time,
        )

        # State distribution
        state_dist = await self._db.fetch(
            """
            SELECT
                state,
                COUNT(*) as count,
                AVG(total_premium) as avg_premium
            FROM quotes
            WHERE created_at BETWEEN $1 AND $2
            GROUP BY state
            ORDER BY count DESC
            LIMIT 10
            """,
            start_time,
            end_time,
        )

        return {
            'summary': dict(metrics),
            'timeline': [dict(row) for row in timeline],
            'state_distribution': [dict(row) for row in state_dist],
            'period': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
            }
        }

    @beartype
    async def broadcast_event(
        self,
        event_type: str,
        data: Dict[str, Any],
    ) -> None:
        """Broadcast analytics event to all dashboard subscribers."""
        # Determine which dashboards care about this event
        affected_dashboards = []

        if event_type in ['quote_created', 'quote_converted']:
            affected_dashboards.append('quotes')
            affected_dashboards.append('conversion')
        elif event_type in ['api_response', 'calculation_complete']:
            affected_dashboards.append('performance')

        # Broadcast to relevant rooms
        for dashboard in affected_dashboards:
            room_id = f"analytics:{dashboard}"
            await self._manager.send_to_room(
                room_id,
                {
                    'type': 'analytics_event',
                    'event_type': event_type,
                    'data': data,
                    'timestamp': datetime.now().isoformat(),
                }
            )
```

### 4. Create WebSocket App (`src/pd_prime_demo/websocket/app.py`)

```python
"""WebSocket application setup."""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from uuid import uuid4

from ..api.dependencies import get_current_user_optional
from ..core.config import get_settings
from .manager import ConnectionManager
from .handlers.quotes import QuoteWebSocketHandler
from .handlers.analytics import AnalyticsWebSocketHandler


# Create WebSocket app
websocket_app = FastAPI()

# Add CORS middleware
settings = get_settings()
websocket_app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.api_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize manager
manager = ConnectionManager(cache, db)  # Injected dependencies

# Initialize handlers
quote_handler = QuoteWebSocketHandler(manager, quote_service)
analytics_handler = AnalyticsWebSocketHandler(manager, db)


@websocket_app.on_event("startup")
async def startup():
    """Start WebSocket manager."""
    await manager.start()


@websocket_app.on_event("shutdown")
async def shutdown():
    """Stop WebSocket manager."""
    await manager.stop()


@websocket_app.websocket("/ws")
async def websocket_endpoint(
    websocket: WebSocket,
    token: Optional[str] = None,
):
    """Main WebSocket endpoint."""
    connection_id = str(uuid4())
    user = None

    # Optional authentication
    if token:
        # Validate token and get user
        pass

    # Accept connection
    await manager.connect(
        websocket,
        connection_id,
        user_id=user.id if user else None,
        metadata={
            'ip_address': websocket.client.host,
            'user_agent': websocket.headers.get('user-agent'),
        }
    )

    try:
        while True:
            # Receive message
            data = await websocket.receive_json()

            # Handle message
            await manager.handle_message(connection_id, data)

            # Route to specific handlers
            if data.get('type') == 'quote_subscribe':
                await quote_handler.handle_quote_subscribe(
                    connection_id,
                    UUID(data['quote_id'])
                )
            elif data.get('type') == 'start_analytics':
                await analytics_handler.start_analytics_stream(
                    connection_id,
                    data['dashboard'],
                    data.get('filters', {})
                )

    except WebSocketDisconnect:
        await manager.disconnect(connection_id)
```

## SEARCH TRIGGERS (30-second timeout)

If confidence < 95% on:

- WebSocket patterns → Search: "fastapi websocket best practices"
- Room management → Search: "websocket room pattern implementation"
- Real-time analytics → Search: "streaming analytics websocket"

## DELIVERABLES

1. **Connection Manager**: Full connection and room management
2. **Quote Handler**: Real-time quote updates and collaboration
3. **Analytics Handler**: Streaming dashboard data
4. **WebSocket App**: Complete WebSocket application
5. **Client Examples**: JavaScript client code examples

## SUCCESS CRITERIA

1. Support 10,000 concurrent connections
2. <50ms message latency
3. Automatic reconnection handling
4. Room-based broadcasting works
5. Graceful degradation on disconnect

## PARALLEL COORDINATION

- Agent 05 triggers quote updates you broadcast
- Agent 06/07 send calculation progress
- Agent 09-11 may add security to WebSocket
- Agent 01 created your connection tables

Ensure all real-time features degrade gracefully!

## ADDITIONAL REQUIREMENT: Admin Real-Time Dashboards

**IMPORTANT**: You must ALSO read `.sage/wave_contexts/wave_2/AGENT_DEPLOYMENT_SUMMARY.md` to understand the full system context.

### 5. Create Admin Dashboard WebSocket Handler (`src/pd_prime_demo/websocket/handlers/admin_dashboard.py`)

You must also implement comprehensive admin real-time dashboard features:

```python
"""Admin dashboard WebSocket handler for real-time monitoring."""

from typing import Dict, List, Any, Optional
from uuid import UUID
from datetime import datetime, timedelta
import asyncio

from beartype import beartype

from ...core.database import Database
from ...core.cache import Cache
from ..manager import ConnectionManager

class AdminDashboardHandler:
    """Handle admin dashboard real-time updates."""

    def __init__(self, manager: ConnectionManager, db: Database, cache: Cache) -> None:
        """Initialize admin dashboard handler."""
        self._manager = manager
        self._db = db
        self._cache = cache
        self._active_streams: Dict[str, asyncio.Task] = {}

    @beartype
    async def start_system_monitoring(
        self,
        connection_id: str,
        admin_user_id: UUID,
        dashboard_config: Dict[str, Any],
    ) -> None:
        """Start real-time system monitoring for admin."""
        # Verify admin permissions
        if not await self._check_admin_permissions(admin_user_id, "analytics:read"):
            await self._manager.send_error(
                connection_id,
                "Insufficient permissions for system monitoring"
            )
            return

        # Subscribe to admin monitoring room
        room_id = f"admin:system_monitoring:{admin_user_id}"
        await self._manager.subscribe_to_room(connection_id, room_id)

        # Start monitoring streams
        stream_key = f"admin_monitor_{connection_id}"
        self._active_streams[stream_key] = asyncio.create_task(
            self._system_monitoring_stream(connection_id, dashboard_config)
        )

    @beartype
    async def start_user_activity_monitoring(
        self,
        connection_id: str,
        admin_user_id: UUID,
        filters: Dict[str, Any],
    ) -> None:
        """Start real-time user activity monitoring."""
        if not await self._check_admin_permissions(admin_user_id, "audit:read"):
            await self._manager.send_error(
                connection_id,
                "Insufficient permissions for user activity monitoring"
            )
            return

        room_id = f"admin:user_activity:{admin_user_id}"
        await self._manager.subscribe_to_room(connection_id, room_id)

        stream_key = f"user_activity_{connection_id}"
        self._active_streams[stream_key] = asyncio.create_task(
            self._user_activity_stream(connection_id, filters)
        )

    @beartype
    async def start_performance_monitoring(
        self,
        connection_id: str,
        admin_user_id: UUID,
        metrics: List[str],
    ) -> None:
        """Start real-time performance monitoring."""
        room_id = f"admin:performance:{admin_user_id}"
        await self._manager.subscribe_to_room(connection_id, room_id)

        stream_key = f"performance_{connection_id}"
        self._active_streams[stream_key] = asyncio.create_task(
            self._performance_monitoring_stream(connection_id, metrics)
        )

    @beartype
    async def _system_monitoring_stream(
        self,
        connection_id: str,
        config: Dict[str, Any],
    ) -> None:
        """Stream system health metrics."""
        try:
            while True:
                # Collect system metrics
                metrics = await self._collect_system_metrics()

                # Send update
                await self._manager.send_to_connection(
                    connection_id,
                    {
                        'type': 'system_metrics',
                        'data': metrics,
                        'timestamp': datetime.now().isoformat(),
                    }
                )

                # Wait for next update
                await asyncio.sleep(config.get('update_interval', 5))

        except asyncio.CancelledError:
            pass

    @beartype
    async def _user_activity_stream(
        self,
        connection_id: str,
        filters: Dict[str, Any],
    ) -> None:
        """Stream user activity events."""
        try:
            while True:
                # Get recent activity
                activities = await self._get_recent_user_activity(filters)

                await self._manager.send_to_connection(
                    connection_id,
                    {
                        'type': 'user_activity',
                        'data': activities,
                        'timestamp': datetime.now().isoformat(),
                    }
                )

                await asyncio.sleep(2)  # 2-second updates

        except asyncio.CancelledError:
            pass

    @beartype
    async def _performance_monitoring_stream(
        self,
        connection_id: str,
        metrics: List[str],
    ) -> None:
        """Stream performance metrics."""
        try:
            while True:
                # Collect performance data
                perf_data = await self._collect_performance_metrics(metrics)

                await self._manager.send_to_connection(
                    connection_id,
                    {
                        'type': 'performance_metrics',
                        'data': perf_data,
                        'timestamp': datetime.now().isoformat(),
                    }
                )

                await asyncio.sleep(1)  # 1-second updates for performance

        except asyncio.CancelledError:
            pass

    @beartype
    async def _collect_system_metrics(self) -> Dict[str, Any]:
        """Collect current system health metrics."""
        # Database connections
        db_stats = await self._db.get_pool_stats()

        # Active WebSocket connections
        ws_stats = await self._manager.get_connection_stats()

        # Cache performance
        cache_stats = await self._cache.get_stats()

        # Recent error rates
        error_stats = await self._get_error_statistics()

        return {
            'database': db_stats,
            'websockets': ws_stats,
            'cache': cache_stats,
            'errors': error_stats,
            'timestamp': datetime.now().isoformat(),
        }

    @beartype
    async def _get_recent_user_activity(
        self,
        filters: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Get recent user activity events."""
        # Get activity from last 30 seconds
        since = datetime.now() - timedelta(seconds=30)

        query = """
            SELECT
                aal.admin_user_id,
                au.email,
                aal.action,
                aal.resource_type,
                aal.status,
                aal.created_at,
                aal.ip_address
            FROM admin_activity_logs aal
            JOIN admin_users au ON aal.admin_user_id = au.id
            WHERE aal.created_at > $1
            ORDER BY aal.created_at DESC
            LIMIT 50
        """

        rows = await self._db.fetch(query, since)
        return [dict(row) for row in rows]

    @beartype
    async def _collect_performance_metrics(
        self,
        metrics: List[str],
    ) -> Dict[str, Any]:
        """Collect performance metrics."""
        data = {}

        if 'api_response_times' in metrics:
            data['api_response_times'] = await self._get_api_response_times()

        if 'quote_calculation_times' in metrics:
            data['quote_calculation_times'] = await self._get_calculation_times()

        if 'active_sessions' in metrics:
            data['active_sessions'] = await self._get_active_session_count()

        if 'error_rates' in metrics:
            data['error_rates'] = await self._get_current_error_rates()

        return data

    @beartype
    async def broadcast_admin_alert(
        self,
        alert_type: str,
        message: str,
        severity: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Broadcast alert to all admin users."""
        alert = {
            'type': 'admin_alert',
            'alert_type': alert_type,
            'message': message,
            'severity': severity,  # 'low', 'medium', 'high', 'critical'
            'data': data or {},
            'timestamp': datetime.now().isoformat(),
        }

        # Send to all admin monitoring rooms
        await self._manager.send_to_room_pattern(
            "admin:system_monitoring:*",
            alert
        )

    @beartype
    async def handle_admin_disconnect(self, connection_id: str) -> None:
        """Clean up when admin disconnects."""
        # Cancel active streams
        streams_to_cancel = [
            key for key in self._active_streams.keys()
            if connection_id in key
        ]

        for stream_key in streams_to_cancel:
            task = self._active_streams.pop(stream_key)
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
```

### 6. Create Admin Analytics API (`src/pd_prime_demo/api/v1/admin/analytics.py`)

```python
"""Admin analytics and monitoring endpoints."""

from fastapi import APIRouter, Depends, WebSocket, HTTPException
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from uuid import UUID

from beartype import beartype

from ....websocket.handlers.admin_dashboard import AdminDashboardHandler
from ...dependencies import get_current_admin_user, get_admin_dashboard_handler
from ....models.admin import AdminUser

router = APIRouter()

@router.websocket("/ws/admin-dashboard")
async def admin_dashboard_websocket(
    websocket: WebSocket,
    dashboard_handler: AdminDashboardHandler = Depends(get_admin_dashboard_handler),
    admin_user: AdminUser = Depends(get_current_admin_user),
):
    """WebSocket endpoint for admin real-time dashboards."""
    await websocket.accept()

    connection_id = str(uuid4())

    try:
        while True:
            data = await websocket.receive_json()

            if data.get('type') == 'start_monitoring':
                await dashboard_handler.start_system_monitoring(
                    connection_id,
                    admin_user.id,
                    data.get('config', {})
                )
            elif data.get('type') == 'start_user_activity':
                await dashboard_handler.start_user_activity_monitoring(
                    connection_id,
                    admin_user.id,
                    data.get('filters', {})
                )
            elif data.get('type') == 'start_performance':
                await dashboard_handler.start_performance_monitoring(
                    connection_id,
                    admin_user.id,
                    data.get('metrics', [])
                )

    except WebSocketDisconnect:
        await dashboard_handler.handle_admin_disconnect(connection_id)

@router.get("/system-health")
@beartype
async def get_system_health(
    admin_user: AdminUser = Depends(get_current_admin_user),
) -> Dict[str, Any]:
    """Get current system health snapshot."""
    if "analytics:read" not in admin_user.effective_permissions:
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    # Return system health data
    return {
        "status": "healthy",
        "checks": {
            "database": "healthy",
            "cache": "healthy",
            "websockets": "healthy"
        },
        "metrics": {
            "active_connections": 150,
            "avg_response_time": 45,
            "error_rate": 0.02
        }
    }
```

### 7. Add Admin Monitoring Tables

Tell Agent 01 to also create:

```sql
-- Admin dashboard configurations
CREATE TABLE admin_dashboards (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    admin_user_id UUID REFERENCES admin_users(id),
    dashboard_name VARCHAR(100) NOT NULL,
    configuration JSONB NOT NULL,
    is_default BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- System alerts and notifications
CREATE TABLE system_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL, -- 'low', 'medium', 'high', 'critical'
    message TEXT NOT NULL,
    details JSONB,
    resolved BOOLEAN DEFAULT false,
    resolved_at TIMESTAMPTZ,
    resolved_by UUID REFERENCES admin_users(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- WebSocket connection tracking for admin monitoring
CREATE TABLE websocket_connections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    connection_id VARCHAR(100) UNIQUE NOT NULL,
    user_id UUID REFERENCES customers(id),
    admin_user_id UUID REFERENCES admin_users(id),
    ip_address INET,
    user_agent TEXT,
    connected_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    disconnected_at TIMESTAMPTZ,
    last_activity TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
```

Make sure admin WebSocket connections are properly secured and monitored!
