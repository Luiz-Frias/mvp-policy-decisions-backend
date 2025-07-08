#!/usr/bin/env python3
"""Comprehensive load testing framework for 10,000 concurrent user validation."""

import asyncio
import json
import random
import statistics
import time
from dataclasses import dataclass
from typing import Any, Dict, List

import aiohttp


@dataclass
class LoadTestConfig:
    """Load test configuration."""

    base_url: str = "http://localhost:8000"
    max_concurrent_users: int = 10000
    test_duration_seconds: int = 300  # 5 minutes
    ramp_up_seconds: int = 60  # 1 minute to reach max users
    think_time_min: float = 0.5  # Minimum wait between requests
    think_time_max: float = 2.0  # Maximum wait between requests
    request_timeout: float = 30.0  # Request timeout
    target_rps: int = 1000  # Target requests per second


@dataclass
class TestScenario:
    """Individual test scenario definition."""

    name: str
    weight: int  # Relative weight for scenario selection
    endpoint: str
    method: str = "GET"
    payload: dict[str, Any] | None = None
    headers: dict[str, str] | None = None
    expected_status: int = 200
    max_response_time_ms: float = 100.0


@dataclass
class RequestResult:
    """Individual request result."""

    scenario_name: str
    status_code: int
    response_time_ms: float
    success: bool
    error: str | None = None
    response_size_bytes: int = 0
    timestamp: float = 0.0


@dataclass
class LoadTestResults:
    """Comprehensive load test results."""

    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_response_time_ms: float
    p50_response_time_ms: float
    p95_response_time_ms: float
    p99_response_time_ms: float
    max_response_time_ms: float
    min_response_time_ms: float
    requests_per_second: float
    errors_per_second: float
    success_rate: float
    concurrent_users_achieved: int
    test_duration_actual: float
    scenarios_executed: dict[str, int]
    errors_by_type: dict[str, int]
    performance_grade: str
    meets_requirements: bool


class LoadTestRunner:
    """Comprehensive load testing framework."""

    def __init__(self, config: LoadTestConfig):
        """Initialize load test runner."""
        self.config = config
        self.scenarios = self._create_test_scenarios()
        self.results: list[RequestResult] = []
        self.active_users = 0
        self.test_start_time = 0.0
        self.session: aiohttp.ClientSession | None = None

    def _create_test_scenarios(self) -> list[TestScenario]:
        """Create realistic test scenarios based on insurance workflows."""
        return [
            # Health check - high frequency
            TestScenario(
                name="health_check",
                weight=10,
                endpoint="/api/v1/health",
                max_response_time_ms=50.0,
            ),
            # Quote creation - primary workflow
            TestScenario(
                name="create_auto_quote",
                weight=25,
                endpoint="/api/v1/quotes",
                method="POST",
                payload={
                    "customer_id": None,  # Will be randomized
                    "product_type": "auto",
                    "state": "CA",
                    "zip_code": "94105",
                    "effective_date": "2025-07-15",
                    "email": "test@example.com",
                    "phone": "14155551234",
                    "vehicle_info": {
                        "vin": "1HGBH41JXMN109186",
                        "year": 2022,
                        "make": "Tesla",
                        "model": "Model 3",
                        "body_style": "sedan",
                    },
                    "drivers": [
                        {
                            "first_name": "John",
                            "last_name": "Doe",
                            "date_of_birth": "1985-05-15",
                            "gender": "M",
                            "license_number": "D1234567",
                            "license_state": "CA",
                        }
                    ],
                    "coverage_selections": [
                        {"coverage_type": "liability", "limit": "100000.00"},
                        {
                            "coverage_type": "collision",
                            "limit": "50000.00",
                            "deductible": "500.00",
                        },
                    ],
                },
                headers={"Content-Type": "application/json"},
                expected_status=201,
                max_response_time_ms=100.0,
            ),
            # Home insurance quote
            TestScenario(
                name="create_home_quote",
                weight=15,
                endpoint="/api/v1/quotes",
                method="POST",
                payload={
                    "customer_id": None,  # Will be randomized
                    "product_type": "home",
                    "state": "CA",
                    "zip_code": "94105",
                    "effective_date": "2025-07-15",
                    "email": "test@example.com",
                    "phone": "14155551234",
                    "property_info": {
                        "property_type": "single_family",
                        "year_built": 1995,
                        "square_footage": 2000,
                        "stories": 2,
                        "roof_type": "composition",
                    },
                    "coverage_selections": [
                        {"coverage_type": "dwelling", "limit": "400000.00"},
                        {"coverage_type": "personal_property", "limit": "200000.00"},
                    ],
                },
                headers={"Content-Type": "application/json"},
                expected_status=201,
                max_response_time_ms=100.0,
            ),
            # Rate calculation - performance critical
            TestScenario(
                name="calculate_rate",
                weight=20,
                endpoint="/api/v1/rates/calculate",
                method="POST",
                payload={
                    "state": "CA",
                    "policy_type": "auto",
                    "coverage": {"liability": 100000},
                    "driver_factors": {"age": 30, "experience_years": 10},
                    "vehicle_factors": {
                        "year": 2020,
                        "make": "TOYOTA",
                        "model": "CAMRY",
                    },
                },
                headers={"Content-Type": "application/json"},
                max_response_time_ms=50.0,  # Strict requirement for rating
            ),
            # Quote retrieval
            TestScenario(
                name="get_quote",
                weight=15,
                endpoint="/api/v1/quotes/12345",  # Will be randomized
                max_response_time_ms=75.0,
            ),
            # Customer lookup
            TestScenario(
                name="get_customer",
                weight=10,
                endpoint="/api/v1/customers/12345",  # Will be randomized
                max_response_time_ms=75.0,
            ),
            # Policy search
            TestScenario(
                name="search_policies",
                weight=8,
                endpoint="/api/v1/policies?customer_id=12345&limit=10",
                max_response_time_ms=100.0,
            ),
            # Performance monitoring
            TestScenario(
                name="performance_metrics",
                weight=5,
                endpoint="/api/v1/monitoring/performance/summary",
                max_response_time_ms=100.0,
            ),
            # Database health check
            TestScenario(
                name="db_health",
                weight=2,
                endpoint="/api/v1/monitoring/health/database",
                max_response_time_ms=150.0,
            ),
        ]

    def _randomize_scenario(self, scenario: TestScenario) -> TestScenario:
        """Randomize scenario data for realistic load testing."""
        if scenario.payload:
            payload = scenario.payload.copy()

            # Randomize customer ID
            if "customer_id" in payload:
                payload["customer_id"] = f"cust_{random.randint(1000, 99999)}"

            # Randomize states
            if "state" in payload:
                payload["state"] = random.choice(["CA", "TX", "NY", "FL", "IL"])

            # Randomize zip codes
            if "zip_code" in payload:
                payload["zip_code"] = f"{random.randint(10000, 99999)}"

            # Randomize driver age for rate calculations
            if "driver_factors" in payload and "age" in payload["driver_factors"]:
                payload["driver_factors"]["age"] = random.randint(18, 75)

            scenario.payload = payload

        # Randomize endpoint IDs
        if "{id}" in scenario.endpoint or "12345" in scenario.endpoint:
            random_id = f"test_{random.randint(1000, 99999)}"
            scenario.endpoint = scenario.endpoint.replace("12345", random_id)

        return scenario

    async def _execute_request(self, scenario: TestScenario) -> RequestResult:
        """Execute a single request and return results."""
        if self.session is None:
            raise RuntimeError("Session not initialized")

        start_time = time.perf_counter()
        timestamp = time.time()

        try:
            # Randomize scenario for this request
            randomized_scenario = self._randomize_scenario(scenario)

            url = f"{self.config.base_url}{randomized_scenario.endpoint}"

            async with self.session.request(
                method=randomized_scenario.method,
                url=url,
                json=randomized_scenario.payload,
                headers=randomized_scenario.headers,
                timeout=aiohttp.ClientTimeout(total=self.config.request_timeout),
            ) as response:
                response_time_ms = (time.perf_counter() - start_time) * 1000
                response_text = await response.text()
                response_size = len(response_text.encode("utf-8"))

                success = (
                    response.status == randomized_scenario.expected_status
                    and response_time_ms <= randomized_scenario.max_response_time_ms
                )

                return RequestResult(
                    scenario_name=scenario.name,
                    status_code=response.status,
                    response_time_ms=response_time_ms,
                    success=success,
                    response_size_bytes=response_size,
                    timestamp=timestamp,
                )

        except Exception as e:
            response_time_ms = (time.perf_counter() - start_time) * 1000
            return RequestResult(
                scenario_name=scenario.name,
                status_code=0,
                response_time_ms=response_time_ms,
                success=False,
                error=str(e),
                timestamp=timestamp,
            )

    async def _user_session(self, user_id: int) -> None:
        """Simulate a single user session."""
        self.active_users += 1

        try:
            while (
                time.time() - self.test_start_time < self.config.test_duration_seconds
            ):
                # Select scenario based on weights
                scenario = self._select_weighted_scenario()

                # Execute request
                result = await self._execute_request(scenario)
                self.results.append(result)

                # Think time between requests
                think_time = random.uniform(
                    self.config.think_time_min, self.config.think_time_max
                )
                await asyncio.sleep(think_time)

        finally:
            self.active_users -= 1

    def _select_weighted_scenario(self) -> TestScenario:
        """Select scenario based on weights."""
        total_weight = sum(scenario.weight for scenario in self.scenarios)
        random_value = random.randint(1, total_weight)

        current_weight = 0
        for scenario in self.scenarios:
            current_weight += scenario.weight
            if random_value <= current_weight:
                return scenario

        return self.scenarios[0]  # Fallback

    async def run_load_test(self) -> LoadTestResults:
        """Execute comprehensive load test."""
        print("🚀 Starting comprehensive load test...")
        print(f"Target: {self.config.max_concurrent_users} concurrent users")
        print(f"Duration: {self.config.test_duration_seconds} seconds")
        print(f"Target RPS: {self.config.target_rps}")
        print("=" * 80)

        # Initialize session
        connector = aiohttp.TCPConnector(
            limit=self.config.max_concurrent_users * 2,
            limit_per_host=self.config.max_concurrent_users,
            ttl_dns_cache=300,
            use_dns_cache=True,
        )

        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=aiohttp.ClientTimeout(total=self.config.request_timeout),
        )

        try:
            self.test_start_time = time.time()

            # Gradual ramp-up of users
            user_tasks = []
            users_per_second = (
                self.config.max_concurrent_users / self.config.ramp_up_seconds
            )

            for user_id in range(self.config.max_concurrent_users):
                # Calculate when this user should start
                start_delay = user_id / users_per_second

                # Create user task with delay
                user_tasks.append(self._delayed_user_start(user_id, start_delay))

            # Wait for all users to complete
            await asyncio.gather(*user_tasks, return_exceptions=True)

            # Calculate and return results
            return self._calculate_results()

        finally:
            await self.session.close()

    async def _delayed_user_start(self, user_id: int, delay: float) -> None:
        """Start user session after delay for gradual ramp-up."""
        await asyncio.sleep(delay)
        await self._user_session(user_id)

    def _calculate_results(self) -> LoadTestResults:
        """Calculate comprehensive test results."""
        if not self.results:
            return LoadTestResults(
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                avg_response_time_ms=0.0,
                p50_response_time_ms=0.0,
                p95_response_time_ms=0.0,
                p99_response_time_ms=0.0,
                max_response_time_ms=0.0,
                min_response_time_ms=0.0,
                requests_per_second=0.0,
                errors_per_second=0.0,
                success_rate=0.0,
                concurrent_users_achieved=0,
                test_duration_actual=0.0,
                scenarios_executed={},
                errors_by_type={},
                performance_grade="F",
                meets_requirements=False,
            )

        # Basic statistics
        total_requests = len(self.results)
        successful_requests = sum(1 for r in self.results if r.success)
        failed_requests = total_requests - successful_requests

        # Response time statistics
        response_times = [r.response_time_ms for r in self.results]
        response_times.sort()

        avg_response_time = statistics.mean(response_times)
        p50_response_time = response_times[int(0.50 * len(response_times))]
        p95_response_time = response_times[int(0.95 * len(response_times))]
        p99_response_time = response_times[int(0.99 * len(response_times))]

        # Throughput calculations
        test_duration = time.time() - self.test_start_time
        requests_per_second = total_requests / test_duration if test_duration > 0 else 0
        errors_per_second = failed_requests / test_duration if test_duration > 0 else 0

        # Success rate
        success_rate = successful_requests / total_requests if total_requests > 0 else 0

        # Scenario breakdown
        scenarios_executed = {}
        for result in self.results:
            scenarios_executed[result.scenario_name] = (
                scenarios_executed.get(result.scenario_name, 0) + 1
            )

        # Error analysis
        errors_by_type = {}
        for result in self.results:
            if not result.success:
                error_key = result.error or f"HTTP_{result.status_code}"
                errors_by_type[error_key] = errors_by_type.get(error_key, 0) + 1

        # Performance grading
        performance_grade = self._calculate_performance_grade(
            p99_response_time, success_rate, requests_per_second
        )

        # Requirements validation
        meets_requirements = (
            p99_response_time < 100.0  # <100ms P99 requirement
            and success_rate > 0.99  # >99% success rate
            and requests_per_second
            >= self.config.target_rps * 0.8  # At least 80% of target RPS
        )

        return LoadTestResults(
            total_requests=total_requests,
            successful_requests=successful_requests,
            failed_requests=failed_requests,
            avg_response_time_ms=avg_response_time,
            p50_response_time_ms=p50_response_time,
            p95_response_time_ms=p95_response_time,
            p99_response_time_ms=p99_response_time,
            max_response_time_ms=max(response_times),
            min_response_time_ms=min(response_times),
            requests_per_second=requests_per_second,
            errors_per_second=errors_per_second,
            success_rate=success_rate,
            concurrent_users_achieved=self.config.max_concurrent_users,
            test_duration_actual=test_duration,
            scenarios_executed=scenarios_executed,
            errors_by_type=errors_by_type,
            performance_grade=performance_grade,
            meets_requirements=meets_requirements,
        )

    def _calculate_performance_grade(
        self, p99_response_time: float, success_rate: float, rps: float
    ) -> str:
        """Calculate overall performance grade."""
        # Scoring system (0-100)
        response_time_score = max(0, 100 - (p99_response_time - 50))  # 50ms target
        success_rate_score = success_rate * 100
        throughput_score = min(100, (rps / self.config.target_rps) * 100)

        overall_score = (
            response_time_score + success_rate_score + throughput_score
        ) / 3

        if overall_score >= 90:
            return "A"
        elif overall_score >= 80:
            return "B"
        elif overall_score >= 70:
            return "C"
        elif overall_score >= 60:
            return "D"
        else:
            return "F"

    def print_results(self, results: LoadTestResults) -> None:
        """Print comprehensive test results."""
        print("\n" + "=" * 80)
        print("🎯 COMPREHENSIVE LOAD TEST RESULTS")
        print("=" * 80)

        # Summary
        print("\n📊 TEST SUMMARY:")
        print(f"   Total Requests: {results.total_requests:,}")
        print(
            f"   Successful: {results.successful_requests:,} ({results.success_rate:.1%})"
        )
        print(f"   Failed: {results.failed_requests:,}")
        print(f"   Test Duration: {results.test_duration_actual:.1f}s")
        print(f"   Concurrent Users: {results.concurrent_users_achieved:,}")

        # Performance Metrics
        print("\n⚡ PERFORMANCE METRICS:")
        print(f"   Requests/sec: {results.requests_per_second:.1f}")
        print(f"   Avg Response: {results.avg_response_time_ms:.1f}ms")
        print(f"   P50 Response: {results.p50_response_time_ms:.1f}ms")
        print(f"   P95 Response: {results.p95_response_time_ms:.1f}ms")
        print(f"   P99 Response: {results.p99_response_time_ms:.1f}ms")
        print(f"   Max Response: {results.max_response_time_ms:.1f}ms")

        # Performance Grade
        grade_emoji = {"A": "🏆", "B": "🥈", "C": "🥉", "D": "⚠️", "F": "❌"}
        print(
            f"\n🎯 PERFORMANCE GRADE: {grade_emoji.get(results.performance_grade, '❓')} {results.performance_grade}"
        )

        # Requirements Check
        status_emoji = "✅" if results.meets_requirements else "❌"
        print(f"\n{status_emoji} PRODUCTION READINESS:")
        print(
            f"   P99 < 100ms: {'✅' if results.p99_response_time_ms < 100 else '❌'} ({results.p99_response_time_ms:.1f}ms)"
        )
        print(
            f"   Success > 99%: {'✅' if results.success_rate > 0.99 else '❌'} ({results.success_rate:.1%})"
        )
        print(
            f"   RPS Target: {'✅' if results.requests_per_second >= self.config.target_rps * 0.8 else '❌'} ({results.requests_per_second:.1f}/{self.config.target_rps})"
        )

        # Scenario Breakdown
        print("\n📈 SCENARIO BREAKDOWN:")
        for scenario, count in sorted(
            results.scenarios_executed.items(), key=lambda x: x[1], reverse=True
        ):
            percentage = (count / results.total_requests) * 100
            print(f"   {scenario}: {count:,} ({percentage:.1f}%)")

        # Error Analysis
        if results.errors_by_type:
            print("\n🚨 ERROR ANALYSIS:")
            for error_type, count in sorted(
                results.errors_by_type.items(), key=lambda x: x[1], reverse=True
            ):
                percentage = (count / results.total_requests) * 100
                print(f"   {error_type}: {count:,} ({percentage:.1f}%)")

        # Recommendations
        print("\n💡 RECOMMENDATIONS:")
        if results.p99_response_time_ms > 100:
            print("   🔴 Critical: P99 response time exceeds 100ms requirement")
        if results.success_rate < 0.99:
            print("   🔴 Critical: Success rate below 99% requirement")
        if results.requests_per_second < self.config.target_rps * 0.8:
            print("   🟡 Warning: Throughput below target")
        if results.meets_requirements:
            print("   🎉 System meets all production requirements!")


async def main():
    """Run comprehensive load test."""
    # Test configurations for different scales
    test_configs = [
        # Quick smoke test
        LoadTestConfig(
            max_concurrent_users=100,
            test_duration_seconds=30,
            ramp_up_seconds=10,
            target_rps=100,
        ),
        # Medium scale test
        LoadTestConfig(
            max_concurrent_users=1000,
            test_duration_seconds=120,
            ramp_up_seconds=30,
            target_rps=500,
        ),
        # Full scale test (10,000 users)
        LoadTestConfig(
            max_concurrent_users=10000,
            test_duration_seconds=300,
            ramp_up_seconds=60,
            target_rps=1000,
        ),
    ]

    print("🧪 Load Testing Framework - Wave 2.5 Performance Validation")
    print("Choose test scale:")
    print("1. Smoke Test (100 users, 30s)")
    print("2. Medium Test (1,000 users, 2m)")
    print("3. Full Scale Test (10,000 users, 5m)")

    choice = input("Enter choice (1-3) or press Enter for smoke test: ").strip() or "1"

    try:
        config_index = int(choice) - 1
        if 0 <= config_index < len(test_configs):
            config = test_configs[config_index]
        else:
            config = test_configs[0]  # Default to smoke test
    except ValueError:
        config = test_configs[0]  # Default to smoke test

    # Run load test
    runner = LoadTestRunner(config)
    results = await runner.run_load_test()

    # Print results
    runner.print_results(results)

    # Save results to file
    results_file = f"load_test_results_{int(time.time())}.json"
    with open(results_file, "w") as f:
        json.dump(
            {
                "config": {
                    "max_concurrent_users": config.max_concurrent_users,
                    "test_duration_seconds": config.test_duration_seconds,
                    "target_rps": config.target_rps,
                },
                "results": {
                    "total_requests": results.total_requests,
                    "success_rate": results.success_rate,
                    "p99_response_time_ms": results.p99_response_time_ms,
                    "requests_per_second": results.requests_per_second,
                    "performance_grade": results.performance_grade,
                    "meets_requirements": results.meets_requirements,
                    "scenarios_executed": results.scenarios_executed,
                    "errors_by_type": results.errors_by_type,
                },
            },
            indent=2,
        )

    print(f"\n💾 Results saved to: {results_file}")

    # Exit with appropriate code
    exit_code = 0 if results.meets_requirements else 1
    print(f"\n🏁 Test completed with exit code: {exit_code}")
    return exit_code


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)
