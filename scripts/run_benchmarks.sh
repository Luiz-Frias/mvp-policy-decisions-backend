#!/bin/bash
# Performance benchmark runner for MVP Policy Decision Backend

set -euo pipefail

echo "🚀 Running performance benchmarks (Wave 3 feature)..."

# Check if pytest-benchmark is installed
if ! uv run python -c "import pytest_benchmark" 2>/dev/null; then
    echo "⚠️  pytest-benchmark not installed. Performance testing is a Wave 3 feature."
    echo "💡 To enable: uv add --dev pytest-benchmark"
    echo "📋 Skipping benchmark tests for now..."
    exit 0
fi

# Run benchmark validation
echo "📊 Validating benchmark requirements..."
uv run python scripts/benchmark_validation.py

# Run benchmark tests
echo "⏱️  Running benchmark tests..."
uv run pytest -c pytest-benchmark.ini -m benchmark --benchmark-only -v

echo "✅ Benchmark tests completed!"
