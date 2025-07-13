#!/bin/bash
# Quick MyPy validation for changed files only

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "🔍 Running quick MyPy validation on changed files..."

# Get list of changed Python files
CHANGED_FILES=$(git diff --name-only --cached --diff-filter=ACM | grep '\.py$' || true)

if [[ -z "$CHANGED_FILES" ]]; then
    echo -e "${GREEN}✓ No Python files changed${NC}"
    exit 0
fi

echo "Files to check:"
echo "$CHANGED_FILES"

# Run MyPy on changed files only
ERROR_COUNT=0
for file in $CHANGED_FILES; do
    if [[ -f "$file" ]]; then
        echo -n "Checking $file... "
        if uv run mypy --strict "$file" 2>&1 | grep -q "error:"; then
            echo -e "${RED}❌ ERRORS${NC}"
            uv run mypy --strict "$file" 2>&1 | grep "error:" | head -5
            ((ERROR_COUNT++))
        else
            echo -e "${GREEN}✓${NC}"
        fi
    fi
done

if [[ $ERROR_COUNT -gt 0 ]]; then
    echo -e "${RED}❌ Found MyPy errors in $ERROR_COUNT files${NC}"
    exit 1
else
    echo -e "${GREEN}✓ All changed files pass MyPy strict mode${NC}"
fi
