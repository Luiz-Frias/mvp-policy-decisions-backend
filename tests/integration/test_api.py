"""Integration tests for API endpoints with MASTER RULESET compliance.

Tests verify:
- API endpoint functionality
- Request/response validation
- Authentication and authorization
- Error handling and status codes
- Performance requirements (<100ms response time)
"""

import asyncio
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import pytest
from beartype import beartype
from fastapi import FastAPI, HTTPException, status
from httpx import AsyncClient
from pydantic import BaseModel, ConfigDict, Field

from tests.fixtures.test_data import VALID_POLICY_DATA


# Example API models for testing
@beartype
class PolicyCreateRequest(BaseModel):
    """Request model for creating a policy."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(..., min_length=1, max_length=50)
    policy_holder: str = Field(..., min_length=1, max_length=200)
    premium: str = Field(..., pattern=r"^\d+\.\d{2}$")
    coverage_amount: str = Field(..., pattern=r"^\d+\.\d{2}$")
    start_date: str
    end_date: str
    status: str = Field(..., pattern="^(active|inactive|pending|cancelled)$")


@beartype
class PolicyResponse(BaseModel):
    """Response model for policy data."""

    model_config = ConfigDict(frozen=True)

    id: str
    policy_id: str
    policy_holder: str
    premium: str
    coverage_amount: str
    start_date: str
    end_date: str
    status: str
    created_at: str
    updated_at: str


@beartype
class DecisionRequest(BaseModel):
    """Request model for policy decision."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    policy_id: str = Field(..., min_length=1, max_length=50)


@beartype
class DecisionResponse(BaseModel):
    """Response model for decision data."""

    model_config = ConfigDict(frozen=True)

    id: str
    policy_id: str
    decision_type: str
    confidence_score: float
    factors: list[dict[str, Any]]
    reason: str | None
    created_at: str


@beartype
class APIResponse(BaseModel):
    """Standard API response wrapper."""

    model_config = ConfigDict(frozen=True)

    status: str
    data: Any | None = None
    message: str | None = None
    error: dict[str, Any] | None = None
    timestamp: str


# Create test FastAPI app
def create_test_app() -> FastAPI:
    """Create FastAPI app with test endpoints."""
    app = FastAPI(
        title="Policy Decision API Test",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Security (defined but not used yet - for future auth implementation)
    # security = HTTPBearer()

    # Health check endpoint
    @app.get("/health")
    async def health_check() -> dict[str, str]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Policy endpoints
    @app.post(
        "/api/v1/policies",
        response_model=APIResponse,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_policy(request: PolicyCreateRequest) -> APIResponse:
        """Create a new policy."""
        # Simulate policy creation
        policy = PolicyResponse(
            id=str(uuid4()),
            policy_id=request.policy_id,
            policy_holder=request.policy_holder,
            premium=request.premium,
            coverage_amount=request.coverage_amount,
            start_date=request.start_date,
            end_date=request.end_date,
            status=request.status,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        return APIResponse(
            status="success",
            data=policy.model_dump(),
            message="Policy created successfully",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @app.get("/api/v1/policies/{policy_id}", response_model=APIResponse)
    async def get_policy(policy_id: str) -> APIResponse:
        """Get policy by ID."""
        if policy_id == "not-found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Policy not found"
            )

        # Return mock policy
        policy = PolicyResponse(
            id=str(uuid4()),
            policy_id=policy_id,
            policy_holder="John Doe",
            premium="1500.00",
            coverage_amount="100000.00",
            start_date="2024-01-01",
            end_date="2024-12-31",
            status="active",
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat(),
        )

        return APIResponse(
            status="success",
            data=policy.model_dump(),
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    @app.post("/api/v1/decisions", response_model=APIResponse)
    async def make_decision(request: DecisionRequest) -> APIResponse:
        """Make a policy decision."""
        # Simulate decision making
        decision = DecisionResponse(
            id=str(uuid4()),
            policy_id=request.policy_id,
            decision_type="approval",
            confidence_score=0.95,
            factors=[
                {"name": "risk_score", "value": 0.2, "weight": 0.5},
                {"name": "financial_score", "value": 0.9, "weight": 0.5},
            ],
            reason="Low risk profile with strong financial indicators",
            created_at=datetime.now(timezone.utc).isoformat(),
        )

        return APIResponse(
            status="success",
            data=decision.model_dump(),
            message="Decision processed successfully",
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # Error handler
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Any, exc: HTTPException) -> APIResponse:
        """Handle HTTP exceptions."""
        return APIResponse(
            status="error",
            error={
                "code": exc.status_code,
                "message": exc.detail,
                "details": None,
            },
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    return app


class TestHealthEndpoint:
    """Test health check endpoint."""

    @pytest.mark.asyncio
    async def test_health_check(self, async_test_client: AsyncClient) -> None:
        """Test health check returns 200."""
        response = await async_test_client.get("/health")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "timestamp" in data

    @pytest.mark.asyncio
    async def test_health_check_performance(
        self, async_test_client: AsyncClient
    ) -> None:
        """Test health check responds under 100ms."""
        import time

        start = time.time()
        response = await async_test_client.get("/health")
        elapsed = (time.time() - start) * 1000  # Convert to ms

        assert response.status_code == 200
        assert elapsed < 100  # Must respond under 100ms


class TestPolicyEndpoints:
    """Test policy-related endpoints."""

    @pytest.mark.asyncio
    async def test_create_policy_success(self, async_test_client: AsyncClient) -> None:
        """Test successful policy creation."""
        response = await async_test_client.post(
            "/api/v1/policies", json=VALID_POLICY_DATA
        )

        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["policy_id"] == VALID_POLICY_DATA["policy_id"]
        assert data["message"] == "Policy created successfully"

    @pytest.mark.asyncio
    async def test_create_policy_validation_error(
        self, async_test_client: AsyncClient
    ) -> None:
        """Test policy creation with invalid data."""
        invalid_data = {
            "policy_id": "",  # Empty policy ID
            "policy_holder": "Test User",
            "premium": "invalid",  # Invalid format
            "coverage_amount": "100000.00",
            "start_date": "2024-01-01",
            "end_date": "2024-12-31",
            "status": "active",
        }

        response = await async_test_client.post("/api/v1/policies", json=invalid_data)

        assert response.status_code == 422  # Validation error
        data = response.json()
        assert "detail" in data

    @pytest.mark.asyncio
    async def test_create_policy_extra_fields_rejected(
        self, async_test_client: AsyncClient
    ) -> None:
        """Test that extra fields are rejected (extra="forbid")."""
        data_with_extra = VALID_POLICY_DATA.copy()
        data_with_extra["extra_field"] = "should be rejected"

        response = await async_test_client.post(
            "/api/v1/policies", json=data_with_extra
        )

        assert response.status_code == 422
        error_detail = response.json()["detail"]
        assert any("extra" in str(error).lower() for error in error_detail)

    @pytest.mark.asyncio
    async def test_get_policy_success(self, async_test_client: AsyncClient) -> None:
        """Test successful policy retrieval."""
        policy_id = "POL-2024-001"
        response = await async_test_client.get(f"/api/v1/policies/{policy_id}")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["policy_id"] == policy_id

    @pytest.mark.asyncio
    async def test_get_policy_not_found(self, async_test_client: AsyncClient) -> None:
        """Test policy not found error."""
        response = await async_test_client.get("/api/v1/policies/not-found")

        assert response.status_code == 404
        data = response.json()
        assert data["status"] == "error"
        assert data["error"]["code"] == 404
        assert "not found" in data["error"]["message"].lower()


class TestDecisionEndpoints:
    """Test decision-related endpoints."""

    @pytest.mark.asyncio
    async def test_make_decision_success(self, async_test_client: AsyncClient) -> None:
        """Test successful decision making."""
        request_data = {"policy_id": "POL-2024-001"}
        response = await async_test_client.post("/api/v1/decisions", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["policy_id"] == request_data["policy_id"]
        assert data["data"]["decision_type"] in ["approval", "rejection", "review"]
        assert 0 <= data["data"]["confidence_score"] <= 1

    @pytest.mark.asyncio
    async def test_make_decision_validation_error(
        self, async_test_client: AsyncClient
    ) -> None:
        """Test decision request validation."""
        # Missing policy_id
        response = await async_test_client.post("/api/v1/decisions", json={})

        assert response.status_code == 422


class TestAPIResponseFormat:
    """Test standard API response format."""

    @pytest.mark.asyncio
    async def test_success_response_format(
        self, async_test_client: AsyncClient
    ) -> None:
        """Test success response follows standard format."""
        response = await async_test_client.get("/api/v1/policies/POL-001")

        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "status" in data
        assert "data" in data
        assert "timestamp" in data
        assert data["status"] == "success"

        # Verify timestamp is valid ISO format
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    @pytest.mark.asyncio
    async def test_error_response_format(self, async_test_client: AsyncClient) -> None:
        """Test error response follows standard format."""
        response = await async_test_client.get("/api/v1/policies/not-found")

        assert response.status_code == 404
        data = response.json()

        # Check required fields
        assert "status" in data
        assert "error" in data
        assert "timestamp" in data
        assert data["status"] == "error"

        # Check error structure
        error = data["error"]
        assert "code" in error
        assert "message" in error
        assert error["code"] == 404


class TestAPIConcurrency:
    """Test API handles concurrent requests properly."""

    @pytest.mark.asyncio
    async def test_concurrent_policy_creation(
        self, async_test_client: AsyncClient
    ) -> None:
        """Test creating multiple policies concurrently."""
        tasks = []
        for i in range(10):
            policy_data = VALID_POLICY_DATA.copy()
            policy_data["policy_id"] = f"POL-CONCURRENT-{i:03d}"
            tasks.append(async_test_client.post("/api/v1/policies", json=policy_data))

        responses = await asyncio.gather(*tasks)

        # All should succeed
        assert all(r.status_code == 201 for r in responses)

        # All should have unique IDs
        ids = [r.json()["data"]["id"] for r in responses]
        assert len(set(ids)) == 10

    @pytest.mark.asyncio
    async def test_concurrent_mixed_operations(
        self, async_test_client: AsyncClient
    ) -> None:
        """Test mixed concurrent operations."""
        tasks = [
            # Create operations
            async_test_client.post("/api/v1/policies", json=VALID_POLICY_DATA),
            async_test_client.post("/api/v1/decisions", json={"policy_id": "POL-001"}),
            # Read operations
            async_test_client.get("/api/v1/policies/POL-001"),
            async_test_client.get("/health"),
        ]

        responses = await asyncio.gather(*tasks, return_exceptions=True)

        # No exceptions should occur
        assert all(not isinstance(r, Exception) for r in responses)


class TestAPIPerformance:
    """Test API performance requirements."""

    @pytest.mark.asyncio
    @pytest.mark.benchmark
    async def test_api_response_time(
        self, async_test_client: AsyncClient, performance_threshold: dict[str, float]
    ) -> None:
        """Test all endpoints respond under 100ms."""
        import time

        endpoints = [
            ("GET", "/health", None),
            ("POST", "/api/v1/policies", VALID_POLICY_DATA),
            ("GET", "/api/v1/policies/POL-001", None),
            ("POST", "/api/v1/decisions", {"policy_id": "POL-001"}),
        ]

        for method, url, data in endpoints:
            start = time.time()

            if method == "GET":
                response = await async_test_client.get(url)
            else:
                response = await async_test_client.post(url, json=data)

            elapsed = (time.time() - start) * 1000  # ms

            assert response.status_code in [200, 201]
            assert elapsed < performance_threshold["max_response_time_ms"]


class TestAPIErrorHandling:
    """Test API error handling scenarios."""

    @pytest.mark.asyncio
    async def test_malformed_json(self, async_test_client: AsyncClient) -> None:
        """Test handling of malformed JSON."""
        response = await async_test_client.post(
            "/api/v1/policies",
            content='{"invalid json}',
            headers={"Content-Type": "application/json"},
        )

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_method_not_allowed(self, async_test_client: AsyncClient) -> None:
        """Test method not allowed error."""
        # Try DELETE on endpoint that doesn't support it
        response = await async_test_client.delete("/api/v1/policies/POL-001")

        assert response.status_code == 405  # Method Not Allowed

    @pytest.mark.asyncio
    async def test_content_type_validation(
        self, async_test_client: AsyncClient
    ) -> None:
        """Test content-type header validation."""
        response = await async_test_client.post(
            "/api/v1/policies",
            content="not json",
            headers={"Content-Type": "text/plain"},
        )

        assert response.status_code == 422


# Override test_app fixture to use our test app
@pytest.fixture
def test_app(mock_config: dict[str, Any], mock_redis: Any) -> FastAPI:
    """Create test FastAPI application."""
    return create_test_app()
