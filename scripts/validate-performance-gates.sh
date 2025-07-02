#!/bin/bash
# Validate performance quality gates

set -euo pipefail

echo "⚡ Validating performance quality gates..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track violations
VIOLATIONS=0
WARNINGS=0

# Function to count lines in a Python function
count_function_lines() {
    local file=$1
    local func_name=$2

    # Get the function definition and count lines until next function or class
    awk "/^def $func_name\(/{flag=1; count=0} flag{count++} /^def |^class /{if(flag && NR>1) exit} END{if(flag) print count}" "$file"
}

# Check 1: Functions > 10 lines must have benchmarks
echo "📏 Checking function sizes and benchmarks..."

# Find all Python files with functions
while IFS= read -r -d '' file; do
    # Skip test files and scripts
    if [[ "$file" == *"/tests/"* ]] || [[ "$file" == *"/scripts/"* ]]; then
        continue
    fi

    # Extract function names
    while IFS= read -r func_def; do
        if [[ -n "$func_def" ]]; then
            func_name=$(echo "$func_def" | sed -E 's/def ([a-zA-Z_][a-zA-Z0-9_]*)\(.*/\1/')

            # Count lines in function
            lines=$(count_function_lines "$file" "$func_name")

            if [[ $lines -gt 10 ]]; then
                # Check if there's a corresponding benchmark test
                benchmark_found=false

                # Look for benchmark in test files
                if find tests -name "*.py" -type f -exec grep -l "benchmark.*$func_name\|test_.*$func_name.*benchmark" {} \; | grep -q .; then
                    benchmark_found=true
                fi

                if ! $benchmark_found; then
                    echo -e "${YELLOW}⚠️  WARNING: Function '$func_name' in $file has $lines lines but no benchmark test${NC}"
                    ((WARNINGS++))
                fi
            fi
        fi
    done < <(grep -E "^def [a-zA-Z_]" "$file" || true)
done < <(find src -name "*.py" -type f -print0)

# Check 2: Memory usage validation
echo "🧠 Checking memory usage constraints..."

# Check if memory profiler decorators are used
if ! grep -r "@memory_profile\|@memray_profile" src/ > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  WARNING: No memory profiling decorators found in codebase${NC}"
    ((WARNINGS++))
fi

# Check 3: Performance regression tests
echo "📊 Checking for performance regression tests..."

if [ -f "tests/test_performance.py" ]; then
    echo -e "${GREEN}✓ Performance test file found${NC}"
else
    if ! find tests -name "*benchmark*.py" -o -name "*performance*.py" | grep -q .; then
        echo -e "${RED}❌ ERROR: No performance or benchmark test files found${NC}"
        ((VIOLATIONS++))
    fi
fi

# Check 4: Beartype decorators on public functions
echo "🐻 Checking @beartype decorator usage..."

beartype_missing=0
while IFS= read -r -d '' file; do
    # Skip test files
    if [[ "$file" == *"/tests/"* ]]; then
        continue
    fi

    # Check for public functions without beartype
    if grep -E "^def [a-zA-Z][^_]" "$file" > /dev/null 2>&1; then
        func_count=$(grep -cE "^def [a-zA-Z][^_]" "$file" || echo 0)
        beartype_count=$(grep -B1 -E "^def [a-zA-Z][^_]" "$file" | grep -c "@beartype" || echo 0)

        if [[ $func_count -gt $beartype_count ]]; then
            missing=$((func_count - beartype_count))
            echo -e "${YELLOW}⚠️  WARNING: $file has $missing public function(s) without @beartype${NC}"
            ((beartype_missing+=missing))
        fi
    fi
done < <(find src -name "*.py" -type f -print0)

if [[ $beartype_missing -gt 0 ]]; then
    ((WARNINGS++))
fi

# Summary
echo ""
echo "📊 Performance Gates Summary:"
echo "  Critical violations: $VIOLATIONS"
echo "  Warnings: $WARNINGS"
echo ""

if [ $VIOLATIONS -gt 0 ]; then
    echo -e "${RED}❌ Performance quality gates FAILED!${NC}"
    echo ""
    echo "Required fixes:"
    echo "  - Add performance/benchmark tests"
    echo "  - Ensure functions >10 lines have benchmarks"
    echo "  - Add @beartype decorators to all public functions"
    echo "  - Implement memory profiling for data processing"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Performance gates passed with warnings${NC}"
    echo "Consider addressing the warnings above for better compliance."
    exit 0
else
    echo -e "${GREEN}✅ All performance quality gates passed!${NC}"
fi
