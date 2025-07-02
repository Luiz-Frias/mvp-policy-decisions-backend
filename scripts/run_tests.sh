#!/bin/bash
# Test runner script for MVP Policy Decision Backend

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
COVERAGE_THRESHOLD=80
TEST_PATH="tests"
VERBOSE=""
BENCHMARK=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE="-v"
            shift
            ;;
        -vv|--very-verbose)
            VERBOSE="-vv"
            shift
            ;;
        --benchmark)
            BENCHMARK="--benchmark-only"
            shift
            ;;
        --unit)
            TEST_PATH="tests/unit"
            shift
            ;;
        --integration)
            TEST_PATH="tests/integration"
            shift
            ;;
        --coverage-threshold)
            COVERAGE_THRESHOLD="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [options]"
            echo "Options:"
            echo "  -v, --verbose          Verbose output"
            echo "  -vv, --very-verbose    Very verbose output"
            echo "  --benchmark            Run only benchmark tests"
            echo "  --unit                 Run only unit tests"
            echo "  --integration          Run only integration tests"
            echo "  --coverage-threshold   Set coverage threshold (default: 80)"
            echo "  -h, --help             Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

echo -e "${GREEN}🧪 Running tests for MVP Policy Decision Backend${NC}"
echo -e "${YELLOW}Test path: ${TEST_PATH}${NC}"

# Check if uv is available
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv is not installed. Please install uv first.${NC}"
    exit 1
fi

# Install dependencies if needed
echo -e "${YELLOW}📦 Ensuring dependencies are installed...${NC}"
uv sync --dev

# Run type checking
echo -e "${YELLOW}🔍 Running type checking with mypy...${NC}"
if uv run mypy src --strict; then
    echo -e "${GREEN}✅ Type checking passed${NC}"
else
    echo -e "${RED}❌ Type checking failed${NC}"
    exit 1
fi

# Run tests with coverage
if [ -n "$BENCHMARK" ]; then
    echo -e "${YELLOW}📊 Running benchmark tests...${NC}"
    uv run pytest $VERBOSE $BENCHMARK "$TEST_PATH"
else
    echo -e "${YELLOW}🧪 Running tests with coverage...${NC}"
    if uv run pytest $VERBOSE \
        --cov=src \
        --cov-report=term-missing:skip-covered \
        --cov-report=html \
        --cov-report=xml \
        --cov-fail-under=$COVERAGE_THRESHOLD \
        "$TEST_PATH"; then
        echo -e "${GREEN}✅ All tests passed!${NC}"

        # Show coverage report location
        echo -e "${YELLOW}📊 Coverage report generated:${NC}"
        echo "   - HTML: htmlcov/index.html"
        echo "   - XML: coverage.xml"
        echo "   - Terminal: See above"
    else
        echo -e "${RED}❌ Tests failed!${NC}"
        exit 1
    fi
fi

# Run security checks
echo -e "${YELLOW}🔒 Running security checks...${NC}"
if uv run bandit -r src -f json -o bandit-report.json; then
    echo -e "${GREEN}✅ Security checks passed${NC}"
else
    echo -e "${YELLOW}⚠️  Security issues found (see bandit-report.json)${NC}"
fi

# Performance check reminder
echo -e "${YELLOW}💡 Reminder: Functions >10 lines must have benchmark tests${NC}"
echo -e "${YELLOW}💡 Run './scripts/run_tests.sh --benchmark' to verify performance${NC}"
