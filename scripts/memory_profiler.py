"""Memory profiling utilities with memray integration."""

import functools
import tracemalloc  # Built-in Python module since 3.4
from collections.abc import Callable
from typing import Any

# Try to import memray (may not be available on all platforms)
try:
    import memray

    HAS_MEMRAY = True
except ImportError:
    HAS_MEMRAY = False


def memory_profile(func: Callable[..., Any]) -> Callable[..., Any]:
    """Profile memory usage with tracemalloc."""

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        tracemalloc.start()

        result = func(*args, **kwargs)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        print(f"🧠 Memory Profile for {func.__name__}:")
        print(f"  Current: {current / 1024:.2f} KB")
        print(f"  Peak: {peak / 1024:.2f} KB")

        return result

    return wrapper


def memray_profile(
    output_file: str,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Profile memory comprehensively with memray."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if HAS_MEMRAY:
                with memray.Tracker(output_file):
                    result = func(*args, **kwargs)

                print(f"📁 Memray profile saved to: {output_file}")
                print(f"🔍 Generate flamegraph: memray flamegraph {output_file}")
            else:
                print("⚠️ Memray not available, running without advanced profiling")
                result = func(*args, **kwargs)

            return result

        return wrapper

    return decorator


# Example usage
@memory_profile
@memray_profile("example_profile.bin")
def example_function() -> int:
    """Demonstrate memory profiling functionality."""
    # Simulate memory usage
    data = [i for i in range(100000)]
    return sum(data)


if __name__ == "__main__":
    result = example_function()
    print(f"Result: {result}")
