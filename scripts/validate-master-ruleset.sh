#!/bin/bash
# Validate master ruleset compliance

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "📋 Validating master ruleset compliance..."

# Check for git zombie processes first
echo "🔍 Checking for git zombie processes..."
zombies=$(ps aux | grep '[Zz]' | grep 'git' | grep -v grep || true)
if [[ -n "$zombies" ]]; then
    echo -e "${RED}❌ ERROR: Found git zombie processes that may block commits:${NC}"
    echo "$zombies"
    echo "Run: sudo kill -9 <pid> to clean up zombies"
    exit 1
else
    echo -e "${GREEN}✓ No git zombie processes found${NC}"
fi

# Track violations
VIOLATIONS=0
WARNINGS=0

# Master Ruleset Core Principles
echo -e "${BLUE}=== MASTER RULESET VALIDATION ===${NC}"
echo "1️⃣  NO QUICK FIXES OR WORKAROUNDS"
echo "2️⃣  SEARCH BEFORE CREATING"
echo "3️⃣  PEAK EXCELLENCE STANDARD"
echo ""

# Check 1: No TODO/FIXME/HACK comments (indicates quick fixes)
echo "🔍 Checking for quick fixes and workarounds..."
if grep -r "TODO\|FIXME\|HACK\|XXX\|REFACTOR" src/ --include="*.py" 2>/dev/null | grep -v "test_"; then
    echo -e "${RED}❌ ERROR: Found TODO/FIXME/HACK comments indicating quick fixes${NC}"
    ((VIOLATIONS++))
else
    echo -e "${GREEN}✓ No quick fix indicators found${NC}"
fi

# Check 2: All data models use Pydantic (no plain dicts without SYSTEM_BOUNDARY)
echo "🔍 MASTER RULE: Validating Pydantic model compliance..."

# 2a: Plain dictionary usage without SYSTEM_BOUNDARY annotation (exclude tests)
DICT_VIOL_FILES=$(find src -name "*.py" -not -path "*/test*" -exec grep -l "dict\\[" {} \; 2>/dev/null | xargs grep -L "SYSTEM_BOUNDARY" 2>/dev/null || true)
if [[ -n "$DICT_VIOL_FILES" ]]; then
    COUNT=$(echo "$DICT_VIOL_FILES" | wc -l)
    echo -e "${RED}❌ MASTER RULE VIOLATION: $COUNT file(s) use plain dictionaries without annotation:${NC}"
    echo "$DICT_VIOL_FILES" | head -20 | sed 's/^/   • /'
    if [[ $COUNT -gt 20 ]]; then
        echo "   ... and $((COUNT - 20)) more"
    fi
    ((VIOLATIONS+=$COUNT))
else
    echo -e "${GREEN}✓ No plain dictionary usage without SYSTEM_BOUNDARY found${NC}"
fi

# 2b: Pydantic models missing frozen=True (exclude tests)
BASEMODEL_FILES=$(find src -name "*.py" -not -path "*/test*" -exec grep -l "class.*BaseModel" {} \; 2>/dev/null)
UNFROZEN_LIST=""
if [[ -n "$BASEMODEL_FILES" ]]; then
    UNFROZEN_LIST=$(echo "$BASEMODEL_FILES" | xargs grep -L "frozen.*=.*True" 2>/dev/null || true)
fi
if [[ -n "$UNFROZEN_LIST" ]]; then
    COUNT=$(echo "$UNFROZEN_LIST" | wc -l)
    echo -e "${RED}❌ MASTER RULE VIOLATION: $COUNT model(s) lack frozen=True:${NC}"
    echo "$UNFROZEN_LIST" | head -10 | sed 's/^/   • /'
    if [[ $COUNT -gt 10 ]]; then
        echo "   ... and $((COUNT - 10)) more"
    fi
    ((VIOLATIONS+=$COUNT))
else
    echo -e "${GREEN}✓ All Pydantic models have frozen=True${NC}"
fi

# 2c: Public functions missing @beartype (exclude tests)
PUBLIC_FUNCS_FILES=$(find src -name "*.py" -not -path "*/test*" -exec grep -l "^def [^_]" {} \; 2>/dev/null)
MISSING_BEAR=""
if [[ -n "$PUBLIC_FUNCS_FILES" ]]; then
    MISSING_BEAR=$(echo "$PUBLIC_FUNCS_FILES" | xargs grep -L "@beartype" 2>/dev/null || true)
fi
if [[ -n "$MISSING_BEAR" ]]; then
    COUNT=$(echo "$MISSING_BEAR" | wc -l)
    echo -e "${RED}❌ MASTER RULE VIOLATION: $COUNT public function file(s) without @beartype:${NC}"
    echo "$MISSING_BEAR" | head -10 | sed 's/^/   • /'
    if [[ $COUNT -gt 10 ]]; then
        echo "   ... and $((COUNT - 10)) more"
    fi
    ((VIOLATIONS+=$COUNT))
else
    echo -e "${GREEN}✓ All public functions have @beartype decorators${NC}"
fi

# Check 3: No bare 'Any' types
echo "🔍 Checking for Any type usage..."
any_usage=$(grep -r "Any\|typing.Any" src/ --include="*.py" 2>/dev/null | grep -v "test_" | grep -v "__pycache__" | grep -v "# type: ignore" | grep -v "example_elite_pattern.py" || true)
if [[ -n "$any_usage" ]]; then
    echo -e "${RED}❌ ERROR: Found 'Any' type usage without proper boundaries:${NC}"
    echo "$any_usage" | head -5
    ((VIOLATIONS++))
else
    echo -e "${GREEN}✓ No uncontrolled 'Any' types found${NC}"
fi

# Check 4: Result type pattern usage (no exceptions for control flow)
echo "🔍 Checking for Result type pattern..."
# Check if Result type is defined
if ! grep -r "class Result" src/ --include="*.py" > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  WARNING: Result type pattern not found in codebase${NC}"
    ((WARNINGS++))
fi

# Check for exception usage in non-error scenarios
exception_raises=$(grep -r "raise\s" src/ --include="*.py" 2>/dev/null | grep -v "test_" | grep -v "__pycache__" || true)
if [[ -n "$exception_raises" ]]; then
    raise_count=$(echo "$exception_raises" | wc -l)
    if [[ $raise_count -gt 10 ]]; then
        echo -e "${YELLOW}⚠️  WARNING: Found $raise_count raise statements. Consider using Result types for control flow${NC}"
        ((WARNINGS++))
    fi
fi

# Check 5: Type coverage (MyPy strict mode)
echo "🔍 Checking type coverage..."
if [ -f "pyproject.toml" ]; then
    if ! grep -q "strict.*=.*true\|strict_optional.*=.*true" pyproject.toml; then
        echo -e "${RED}❌ ERROR: MyPy not configured in strict mode${NC}"
        ((VIOLATIONS++))
    else
        echo -e "${GREEN}✓ MyPy strict mode enabled${NC}"
    fi
fi

# Check 6: Security validation tools
echo "🔍 Checking security tooling..."
security_tools=("bandit" "safety" "pip-audit")
missing_tools=()

for tool in "${security_tools[@]}"; do
    if ! grep -q "$tool" pyproject.toml 2>/dev/null && ! grep -q "$tool" Makefile 2>/dev/null; then
        missing_tools+=("$tool")
    fi
done

if [ ${#missing_tools[@]} -gt 0 ]; then
    echo -e "${YELLOW}⚠️  WARNING: Missing security tools: ${missing_tools[*]}${NC}"
    ((WARNINGS++))
else
    echo -e "${GREEN}✓ All security tools configured${NC}"
fi

# Check 7: Defensive programming patterns
echo "🔍 Checking defensive programming patterns..."

# Check for frozen Pydantic models
frozen_models=$(grep -r "frozen=True" src/ --include="*.py" 2>/dev/null | wc -l || echo 0)
total_models=$(grep -r "class.*BaseModel" src/ --include="*.py" 2>/dev/null | wc -l || echo 0)

if [[ $total_models -gt 0 && $frozen_models -lt $total_models ]]; then
    echo -e "${RED}❌ ERROR: Not all Pydantic models are immutable (frozen=True)${NC}"
    echo "  Found $frozen_models frozen models out of $total_models total"
    ((VIOLATIONS++))
fi

# Check 8: Documentation quality
echo "🔍 Checking documentation quality..."
modules_without_docstrings=0

while IFS= read -r -d '' file; do
    # Check module docstring
    if ! head -10 "$file" | grep -q '"""'; then
        ((modules_without_docstrings++))
    fi
done < <(find src -name "*.py" -type f -print0)

if [[ $modules_without_docstrings -gt 0 ]]; then
    echo -e "${YELLOW}⚠️  WARNING: $modules_without_docstrings module(s) missing docstrings${NC}"
    ((WARNINGS++))
fi

# Summary
echo ""
echo -e "${BLUE}=== MASTER RULESET COMPLIANCE SUMMARY ===${NC}"
echo "  🚨 Critical violations: $VIOLATIONS"
echo "  ⚠️  Warnings: $WARNINGS"
echo ""

if [ $VIOLATIONS -gt 0 ]; then
    echo -e "${RED}❌ Master ruleset compliance FAILED!${NC}"
    echo ""
    echo "Required fixes:"
    echo "  - Remove all TODO/FIXME/HACK comments"
    echo "  - Replace 'Any' types with specific types"
    echo "  - Enable MyPy strict mode"
    echo "  - Ensure all Pydantic models use frozen=True"
    echo "  - Implement Result type pattern for error handling"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠️  Master ruleset passed with warnings${NC}"
    echo "Peak excellence requires addressing all warnings!"
    exit 0
else
    echo -e "${GREEN}✅ PEAK EXCELLENCE ACHIEVED! All master ruleset checks passed!${NC}"
fi
