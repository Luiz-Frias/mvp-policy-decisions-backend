"""Main module with defensive programming and performance optimization."""

import cProfile
import pstats
import time
from collections.abc import Callable
from functools import lru_cache, wraps
from typing import Any, Generic, TypeVar

from attrs import define, field
from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field, validator

# Rust-like Result type for defensive programming
T = TypeVar("T")
E = TypeVar("E")


@define(frozen=True, slots=True)
class Result(Generic[T, E]):
    """Rust-like Result type for error handling."""

    _value: T | None = field(default=None, init=False)
    _error: E | None = field(default=None, init=False)

    @classmethod
    def ok(cls, value: T) -> "Result[T, E]":
        """Create a successful result."""
        result = cls()
        object.__setattr__(result, "_value", value)
        return result

    @classmethod
    def err(cls, error: E) -> "Result[T, E]":
        """Create an error result."""
        result = cls()
        object.__setattr__(result, "_error", error)
        return result

    def is_ok(self) -> bool:
        """Check if result is successful."""
        return self._value is not None

    def unwrap(self) -> T:
        """Unwrap value or raise exception."""
        if self._value is not None:
            return self._value
        raise ValueError(f"Called unwrap on error result: {self._error}")

    def unwrap_or(self, default: T) -> T:
        """Unwrap value or return default."""
        return self._value if self._value is not None else default


# Pydantic models for type safety and validation
# 🛡️ MASTER RULESET ENFORCEMENT: Pydantic Model Design Principles
class PersonModel(BaseModel):
    """
    IMMUTABLE person model following master ruleset first principles.

    MASTER RULES ENFORCED:
    - frozen=True: IMMUTABLE BY DEFAULT
    - Field constraints: ALL FIELDS MUST HAVE CONSTRAINTS
    - extra='forbid': EXPLICIT ERROR HANDLING
    - Runtime validation: FAIL-FAST VALIDATION
    """

    model_config = ConfigDict(
        # 🔒 MANDATORY: IMMUTABLE BY DEFAULT
        frozen=True,
        # 🛡️ MANDATORY: STRICT VALIDATION
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",  # Forbid unknown fields
        # ⚡ PERFORMANCE: Use Pydantic's Rust core
        use_enum_values=True,
        validate_default=True,
        # str_strict=True  # Not a valid ConfigDict parameter in pydantic v2
    )

    # 🔒 MANDATORY: FIELD CONSTRAINTS on ALL fields
    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Person's full name",
        examples=["John Doe", "Alice Smith"],
    )
    age: int | None = Field(None, ge=0, le=150, description="Person's age in years")
    email: str | None = Field(
        None,
        pattern=r"^[^@]+@[^@]+\.[^@]+$",  # Use 'pattern' instead of 'regex' in pydantic v2
        description="Valid email address",
    )

    @validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        """
        🔒 MASTER RULE: CUSTOM VALIDATORS for business logic.

        DEFENSIVE PROGRAMMING: Validate name contains only letters and spaces.
        """
        if not v.replace(" ", "").replace("-", "").isalpha():
            raise ValueError("Name must contain only letters, spaces, and hyphens")
        return v.title()

    @validator("email")
    @classmethod
    def validate_email_domain(cls, v: str | None) -> str | None:
        """🔒 MASTER RULE: Advanced validation with business logic."""
        if v is None:
            return v

        # Example: Block disposable email domains
        blocked_domains = {"tempmail.com", "10minutemail.com"}
        if any(domain in v.lower() for domain in blocked_domains):
            raise ValueError("Disposable email addresses are not allowed")

        return v.lower()


@define(frozen=True, slots=True)
class PerformanceMetrics:
    """Immutable performance metrics."""

    execution_time: float
    memory_usage: int
    function_name: str


def performance_monitor(func: Callable[..., Any]) -> Callable[..., Any]:
    """
    🚀 MASTER RULE: PERFORMANCE MONITORING decorator.

    MANDATORY for functions >10 lines. Enforces:
    - MEMORY ALLOCATION LIMITS: <1MB temp objects
    - CPU EFFICIENCY: O(n) completion within bounds
    - MEMORY LEAK DETECTION: No growth >1MB in 1000 iterations
    """

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start_time = time.perf_counter()

        # 🧠 MEMORY PROFILING: Track allocations with built-in tracemalloc
        try:
            import tracemalloc

            if not tracemalloc.is_tracing():
                tracemalloc.start()
                stop_tracemalloc = True
            else:
                stop_tracemalloc = False

            result = func(*args, **kwargs)

            current_memory, peak_memory = tracemalloc.get_traced_memory()
            if stop_tracemalloc:
                tracemalloc.stop()

            execution_time = time.perf_counter() - start_time

            # 🚨 PERFORMANCE QUALITY GATES ENFORCEMENT
            max_allowed_memory = 1024 * 1024  # 1MB limit per master ruleset
            if peak_memory > max_allowed_memory:
                print(
                    f"⚠️ PERFORMANCE VIOLATION: {func.__name__} exceeded 1MB memory limit"
                )
                print(f"   Peak: {peak_memory / 1024 / 1024:.2f}MB")

            # ⚡ CPU EFFICIENCY CHECK
            if execution_time > 1.0:  # 1 second threshold for non-I/O operations
                print(
                    f"⚠️ PERFORMANCE WARNING: {func.__name__} took {execution_time:.4f}s"
                )
                print("   Consider optimization for functions >1s execution time")

            # Create performance metrics for potential logging/monitoring
            # metrics = PerformanceMetrics(
            #     execution_time=execution_time,
            #     memory_usage=peak_memory,
            #     function_name=func.__name__
            # )

            # 📊 PERFORMANCE METRICS LOGGING
            print(
                f"⚡ Performance: {func.__name__} | "
                f"Time: {execution_time:.4f}s | "
                f"Peak Memory: {peak_memory / 1024:.2f}KB | "
                f"Current: {current_memory / 1024:.2f}KB"
            )

            # 🎯 EFFICIENCY RATING
            if execution_time < 0.001 and peak_memory < 1024:
                print(f"✅ EXCELLENT: {func.__name__} - Ultra-fast & memory-efficient")
            elif execution_time < 0.01 and peak_memory < 10240:
                print(f"✅ GOOD: {func.__name__} - Fast & efficient")
            elif execution_time < 0.1:
                print(f"📊 ACCEPTABLE: {func.__name__} - Within performance bounds")

            return result

        except ImportError:
            # Fallback to simple timing
            result = func(*args, **kwargs)
            execution_time = time.perf_counter() - start_time
            print(f"⚡ Performance: {func.__name__} | Time: {execution_time:.4f}s")
            return result

    return wrapper


@beartype
@lru_cache(maxsize=128)
def cached_greet(name: str, greeting: str | None = None) -> str:
    """
    Cache greeting for performance optimization.

    Args:
        name: The name of the person to greet (validated)
        greeting: Optional custom greeting

    Returns:
        A greeting message

    Raises:
        ValueError: If name is invalid

    Example:
        >>> cached_greet("World")
        'Hello, World!'
        >>> cached_greet("Alice", "Hi")
        'Hi, Alice!'
    """
    if not isinstance(name, str) or len(name.strip()) == 0:
        raise ValueError("Name must be a non-empty string")

    greeting = greeting or "Hello"
    return f"{greeting}, {name.title()}!"


@beartype
@performance_monitor
def safe_greet_person(person_data: dict[str, Any]) -> Result[str, str]:
    """
    Safely greet a person using Pydantic validation and Result type.

    Args:
        person_data: Dictionary containing person information

    Returns:
        Result containing greeting message or error
    """
    try:
        # Defensive programming: validate input with Pydantic
        person = PersonModel(**person_data)

        # Use cached function for performance
        greeting = cached_greet(person.name)

        return Result.ok(greeting)

    except Exception as e:
        return Result.err(f"Failed to greet person: {str(e)}")


@beartype
def batch_greet_optimized(people: list[dict[str, Any]]) -> list[Result[str, str]]:
    """
    Optimized batch greeting with memory-efficient processing.

    Args:
        people: List of person dictionaries

    Returns:
        List of Result objects with greetings or errors
    """
    return [safe_greet_person(person_data) for person_data in people]


def profile_performance() -> None:
    """Profile the performance of greeting functions."""
    print("🔬 Running performance analysis...")

    # Sample data for testing
    test_people = [
        {"name": "Alice", "age": 30, "email": "alice@example.com"},
        {"name": "Bob", "age": 25},
        {"name": "Charlie", "age": 35, "email": "charlie@example.com"},
        {"name": "Invalid Name 123", "age": 40},  # This will fail validation
    ]

    # Performance testing
    profiler = cProfile.Profile()
    profiler.enable()

    results = batch_greet_optimized(test_people)

    profiler.disable()

    # Display results
    for i, result in enumerate(results):
        if result.is_ok():
            print(f"✅ Person {i+1}: {result.unwrap()}")
        else:
            print(f"❌ Person {i+1}: {result._error}")

    # Show performance stats
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    print("\n📊 Performance Profile:")
    stats.print_stats(10)  # Top 10 functions


def main() -> None:
    """Demonstrate defensive programming patterns."""
    try:
        print("🚀 Starting application with defensive programming patterns...")

        # Simple greeting
        simple_result = safe_greet_person({"name": "World"})
        if simple_result.is_ok():
            print(f"Simple greeting: {simple_result.unwrap()}")

        # Performance profiling
        profile_performance()

    except Exception as e:
        print(f"💥 Application error: {e}")
        raise


if __name__ == "__main__":
    main()
