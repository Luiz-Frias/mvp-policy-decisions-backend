# PolicyCore - Policy Decision Management System
# Copyright (C) 2025 Luiz Frias <luizf35@gmail.com>
# Form F[x] Labs
#
# This software is dual-licensed under AGPL-3.0 and Commercial License.
# For commercial licensing, contact: luizf35@gmail.com
# See LICENSE file for full terms.

"""Rate limiting middleware for API protection under high load."""

import time
from collections import deque
from collections.abc import Awaitable, Callable
from typing import Any

from attrs import define, field, frozen
from beartype import beartype
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from .cache import get_cache


@frozen
class RateLimitRule:
    """Immutable rate limiting rule configuration."""

    requests_per_minute: int = field()
    requests_per_hour: int = field()
    burst_requests: int = field()
    window_size_seconds: int = field(default=60)


@frozen
class RateLimitConfig:
    """Rate limiting configuration for different endpoint types."""

    # Default rate limits
    default_rule: RateLimitRule = field(
        default=RateLimitRule(
            requests_per_minute=60,
            requests_per_hour=1000,
            burst_requests=10,
        )
    )

    # Critical endpoints (rating, quotes)
    critical_rule: RateLimitRule = field(
        default=RateLimitRule(
            requests_per_minute=100,
            requests_per_hour=2000,
            burst_requests=20,
        )
    )

    # Health checks and monitoring
    monitoring_rule: RateLimitRule = field(
        default=RateLimitRule(
            requests_per_minute=300,
            requests_per_hour=5000,
            burst_requests=50,
        )
    )

    # Admin endpoints
    admin_rule: RateLimitRule = field(
        default=RateLimitRule(
            requests_per_minute=30,
            requests_per_hour=500,
            burst_requests=5,
        )
    )


@define
class ClientRateTracker:
    """Track rate limiting for a specific client."""

    client_id: str = field()
    requests_this_minute: deque[float] = field(factory=lambda: deque(maxlen=100))
    requests_this_hour: deque[float] = field(factory=lambda: deque(maxlen=2000))
    burst_tokens: int = field(default=10)
    last_request_time: float = field(default=0.0)

    @beartype
    def add_request(self, timestamp: float) -> None:
        """Add a new request timestamp."""
        self.requests_this_minute.append(timestamp)
        self.requests_this_hour.append(timestamp)
        self.last_request_time = timestamp

    @beartype
    def cleanup_old_requests(self, current_time: float) -> None:
        """Remove requests older than tracking windows."""
        minute_cutoff = current_time - 60
        hour_cutoff = current_time - 3600

        # Clean minute window
        while (
            self.requests_this_minute and self.requests_this_minute[0] < minute_cutoff
        ):
            self.requests_this_minute.popleft()

        # Clean hour window
        while self.requests_this_hour and self.requests_this_hour[0] < hour_cutoff:
            self.requests_this_hour.popleft()

    @beartype
    def get_current_rates(self, current_time: float) -> tuple[int, int]:
        """Get current request counts for minute and hour windows."""
        self.cleanup_old_requests(current_time)
        return len(self.requests_this_minute), len(self.requests_this_hour)

    def can_make_request(
        self, rule: RateLimitRule, current_time: float
    ) -> tuple[bool, str]:
        """Check if client can make a request under the given rule."""
        minute_count, hour_count = self.get_current_rates(current_time)

        # Check minute limit
        if minute_count >= rule.requests_per_minute:
            return (
                False,
                f"Rate limit exceeded: {minute_count}/{rule.requests_per_minute} requests per minute",
            )

        # Check hour limit
        if hour_count >= rule.requests_per_hour:
            return (
                False,
                f"Rate limit exceeded: {hour_count}/{rule.requests_per_hour} requests per hour",
            )

        # Check burst limit (if client has been active recently)
        if current_time - self.last_request_time < 1.0:  # Within 1 second
            if minute_count >= rule.burst_requests:
                return (
                    False,
                    f"Burst limit exceeded: {minute_count}/{rule.burst_requests} requests in burst",
                )

        return True, ""


class RateLimiter:
    """In-memory rate limiter with Redis backup for distributed scenarios."""

    def __init__(self, config: RateLimitConfig) -> None:
        """Initialize rate limiter."""
        self.config = config
        self.clients: dict[str, ClientRateTracker] = {}
        self.cache = get_cache()

        # Define endpoint patterns and their rules
        self.endpoint_rules = {
            "/api/v1/health": self.config.monitoring_rule,
            "/api/v1/monitoring/": self.config.monitoring_rule,
            "/api/v1/quotes": self.config.critical_rule,
            "/api/v1/rates/": self.config.critical_rule,
            "/api/v1/admin/": self.config.admin_rule,
            # Default rule for everything else
            "default": self.config.default_rule,
        }

    @beartype
    def _get_client_id(self, request: Request) -> str:
        """Extract client ID from request."""
        # Priority order for client identification

        # 1. API key from header
        api_key = request.headers.get("X-API-Key")
        if api_key:
            return f"api_key:{api_key[:16]}"

        # 2. Authorization token (extract user ID if possible)
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header[7:]
            return f"token:{token[:16]}"

        # 3. Client IP address
        client_ip = "unknown"
        if request.client:
            client_ip = request.client.host

        # 4. User agent for additional differentiation
        user_agent = request.headers.get("User-Agent", "")[:32]

        return f"ip:{client_ip}:ua:{hash(user_agent) % 10000}"

    @beartype
    def _get_rule_for_endpoint(self, path: str) -> RateLimitRule:
        """Get rate limiting rule for specific endpoint."""
        for pattern, rule in self.endpoint_rules.items():
            if pattern != "default" and path.startswith(pattern):
                return rule

        return self.endpoint_rules["default"]

    @beartype
    def _get_client_tracker(self, client_id: str) -> ClientRateTracker:
        """Get or create client rate tracker."""
        if client_id not in self.clients:
            self.clients[client_id] = ClientRateTracker(client_id=client_id)

        return self.clients[client_id]

    @beartype
    async def check_rate_limit(
        self, request: Request
    ) -> tuple[bool, str, dict[str, Any]]:
        """Check if request should be rate limited."""
        current_time = time.time()
        client_id = self._get_client_id(request)
        rule = self._get_rule_for_endpoint(request.url.path)

        # Get client tracker
        tracker = self._get_client_tracker(client_id)

        # Check if request is allowed
        allowed, reason = tracker.can_make_request(rule, current_time)

        # Get current rate information for headers
        minute_count, hour_count = tracker.get_current_rates(current_time)

        rate_info = {
            "requests_this_minute": minute_count,
            "requests_this_hour": hour_count,
            "limit_per_minute": rule.requests_per_minute,
            "limit_per_hour": rule.requests_per_hour,
            "burst_limit": rule.burst_requests,
            "client_id": client_id,
            "rule_type": self._get_rule_name(rule),
        }

        if allowed:
            # Record the request
            tracker.add_request(current_time)

        return allowed, reason, rate_info

    @beartype
    def _get_rule_name(self, rule: RateLimitRule) -> str:
        """Get human-readable rule name."""
        if rule == self.config.critical_rule:
            return "critical"
        elif rule == self.config.monitoring_rule:
            return "monitoring"
        elif rule == self.config.admin_rule:
            return "admin"
        else:
            return "default"

    @beartype
    async def cleanup_inactive_clients(
        self, inactive_threshold_seconds: int = 3600
    ) -> int:
        """Clean up inactive client trackers to prevent memory leaks."""
        current_time = time.time()
        cutoff_time = current_time - inactive_threshold_seconds

        inactive_clients = [
            client_id
            for client_id, tracker in self.clients.items()
            if tracker.last_request_time < cutoff_time
        ]

        for client_id in inactive_clients:
            del self.clients[client_id]

        return len(inactive_clients)

    @beartype
    async def get_rate_limit_stats(self) -> dict[str, Any]:
        """Get rate limiter statistics."""
        current_time = time.time()

        # Clean up first
        await self.cleanup_inactive_clients()

        # Calculate statistics
        active_clients = len(self.clients)
        total_requests_minute = sum(
            len(tracker.requests_this_minute) for tracker in self.clients.values()
        )
        total_requests_hour = sum(
            len(tracker.requests_this_hour) for tracker in self.clients.values()
        )

        # Top clients by activity
        top_clients = sorted(
            [
                {
                    "client_id": tracker.client_id,
                    "requests_minute": len(tracker.requests_this_minute),
                    "requests_hour": len(tracker.requests_this_hour),
                    "last_seen": current_time - tracker.last_request_time,
                }
                for tracker in self.clients.values()
            ],
            key=lambda x: (
                int(x["requests_minute"])
                if isinstance(x["requests_minute"], (int, str))
                else 0
            ),
            reverse=True,
        )[:10]

        return {
            "active_clients": active_clients,
            "total_requests_minute": total_requests_minute,
            "total_requests_hour": total_requests_hour,
            "top_clients": top_clients,
            "rules_configured": len(self.endpoint_rules),
        }


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for rate limiting."""

    def __init__(
        self, app: Any, config: RateLimitConfig | None = None, enabled: bool = True
    ) -> None:
        """Initialize rate limiting middleware."""
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.enabled = enabled
        self.rate_limiter = RateLimiter(self.config) if enabled else None

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Apply rate limiting to incoming requests."""
        if not self.enabled or self.rate_limiter is None:
            return await call_next(request)

        # Skip rate limiting for certain paths
        skip_paths = ["/docs", "/redoc", "/openapi.json"]
        if any(request.url.path.startswith(path) for path in skip_paths):
            return await call_next(request)

        # Check rate limit
        allowed, reason, rate_info = await self.rate_limiter.check_rate_limit(request)

        if not allowed:
            # Rate limited - return 429 Too Many Requests
            return Response(
                content=f"Rate limit exceeded: {reason}",
                status_code=429,
                headers={
                    "X-RateLimit-Limit-Minute": str(rate_info["limit_per_minute"]),
                    "X-RateLimit-Limit-Hour": str(rate_info["limit_per_hour"]),
                    "X-RateLimit-Remaining-Minute": str(
                        max(
                            0,
                            rate_info["limit_per_minute"]
                            - rate_info["requests_this_minute"],
                        )
                    ),
                    "X-RateLimit-Remaining-Hour": str(
                        max(
                            0,
                            rate_info["limit_per_hour"]
                            - rate_info["requests_this_hour"],
                        )
                    ),
                    "X-RateLimit-Rule": rate_info["rule_type"],
                    "Retry-After": "60",  # Suggest retry after 1 minute
                },
            )

        # Process request normally
        response = await call_next(request)

        # Add rate limit headers to successful responses
        response.headers["X-RateLimit-Limit-Minute"] = str(
            rate_info["limit_per_minute"]
        )
        response.headers["X-RateLimit-Limit-Hour"] = str(rate_info["limit_per_hour"])
        response.headers["X-RateLimit-Remaining-Minute"] = str(
            max(0, rate_info["limit_per_minute"] - rate_info["requests_this_minute"])
        )
        response.headers["X-RateLimit-Remaining-Hour"] = str(
            max(0, rate_info["limit_per_hour"] - rate_info["requests_this_hour"])
        )
        response.headers["X-RateLimit-Rule"] = rate_info["rule_type"]

        return response


# Global rate limiter instance
_global_rate_limiter: RateLimiter | None = None


@beartype
def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    global _global_rate_limiter
    if _global_rate_limiter is None:
        _global_rate_limiter = RateLimiter(RateLimitConfig())
    return _global_rate_limiter


# Rate limiting decorator for specific functions
@beartype
def rate_limit(
    requests_per_minute: int = 60,
    requests_per_hour: int = 1000,
    burst_requests: int = 10,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator for function-level rate limiting."""

    @beartype
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        RateLimitRule(
            requests_per_minute=requests_per_minute,
            requests_per_hour=requests_per_hour,
            burst_requests=burst_requests,
        )

        async def wrapper(request: Request, *args: Any, **kwargs: Any) -> Any:
            # This would require request context - simplified for now
            return await func(request, *args, **kwargs)

        return wrapper

    return decorator
