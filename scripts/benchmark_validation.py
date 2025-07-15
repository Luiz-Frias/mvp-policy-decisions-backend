"""Performance benchmarking for defensive programming patterns."""

import time
import tracemalloc
from typing import Any

# ---------------------------------------------------------------------------
# Logging Setup (replaces legacy ``print`` output with structured logging)
# ---------------------------------------------------------------------------
from policy_core.core.logging_utils import configure_logging, patch_print

configure_logging()
patch_print()

# Conditional imports for type checking to resolve mypy import issues
try:
    from beartype import beartype
    from pydantic import BaseModel, Field

    DEPS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Some dependencies not available: {e}")

    # Fallback for missing dependencies
    class BaseModel:  # type: ignore[no-redef]
        """Fallback BaseModel class for when pydantic is not available."""

        pass

    def Field(*args: Any, **kwargs: Any) -> Any:  # type: ignore[no-redef]
        """Fallback Field function for when pydantic is not available."""
        return None

    def beartype(x: Any) -> Any:  # type: ignore[no-redef]
        """Fallback beartype decorator for when beartype is not available."""
        return x

    DEPS_AVAILABLE = False

try:
    import memray  # noqa: F401

    HAS_MEMRAY = True
except ImportError:
    HAS_MEMRAY = False


class BenchmarkPersonModel(BaseModel):
    """Person model for benchmarking."""

    name: str = Field(..., min_length=1, max_length=100)
    age: int = Field(..., ge=0, le=150)
    email: str = Field(
        ..., pattern=r"^[^@]+@[^@]+\.[^@]+$"
    )  # Use 'pattern' instead of 'regex'


@beartype
def pydantic_validation_benchmark(
    data: list[dict[str, Any]],
) -> list[BenchmarkPersonModel]:
    """Benchmark Pydantic validation performance."""
    return [BenchmarkPersonModel(**item) for item in data]


def generate_test_data(size: int) -> list[dict[str, Any]]:
    """Generate test data for benchmarking."""
    return [
        {"name": f"Person{i}", "age": 25 + (i % 50), "email": f"person{i}@example.com"}
        for i in range(size)
    ]


def run_pydantic_benchmarks() -> None:
    """Run comprehensive Pydantic performance benchmarks."""
    print("🚀 Running Pydantic Performance Benchmarks")
    print("=" * 50)

    test_sizes = [100, 1000, 10000]

    for size in test_sizes:
        print(f"\n📊 Testing with {size} records:")

        # Generate test data
        test_data = generate_test_data(size)

        # Memory profiling
        tracemalloc.start()
        start_time = time.perf_counter()

        # Run validation
        validated_data = pydantic_validation_benchmark(test_data)

        end_time = time.perf_counter()
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Results
        execution_time = end_time - start_time
        print(f"  ⚡ Execution time: {execution_time:.4f} seconds")
        print(f"  🧠 Peak memory: {peak / 1024 / 1024:.2f} MB")
        print(f"  📈 Records/second: {size / execution_time:.0f}")
        print(f"  ✅ Successfully validated: {len(validated_data)} records")


def pytest_benchmark_example() -> None:
    """Demonstrate pytest benchmark with MASTER RULESET compliance."""
    test_data = generate_test_data(1000)

    def test_pydantic_validation(benchmark: Any) -> None:
        result = benchmark(pydantic_validation_benchmark, test_data)
        expected_length = 1000
        actual_length = len(result)
        if actual_length != expected_length:  # nosec B101
            raise ValueError(f"Expected {expected_length} results, got {actual_length}")


if __name__ == "__main__":
    run_pydantic_benchmarks()
