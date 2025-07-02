#!/bin/bash
# Validate that all Pydantic models use frozen=True and follow master ruleset

set -euo pipefail

echo "🔍 Checking Pydantic model compliance..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track violations
VIOLATIONS=0
FILES_CHECKED=0

# Find all Python files in src/
while IFS= read -r -d '' file; do
    ((FILES_CHECKED++))

    # Check if file contains BaseModel imports
    if grep -q "from pydantic import.*BaseModel" "$file" || grep -q "from pydantic.main import BaseModel" "$file"; then
        echo "📄 Checking: $file"

        # Check for model definitions - including those inheriting from BaseModelConfig
        if grep -q "class.*BaseModel\|class.*BaseModelConfig" "$file"; then
            # Check for frozen=True in ConfigDict or if inheriting from BaseModelConfig
            if ! grep -q "BaseModelConfig" "$file" && ! grep -A 10 "class.*BaseModel" "$file" | grep -q "frozen=True"; then
                # Also check for model_config with frozen
                if ! grep -A 15 "class.*BaseModel" "$file" | grep -q "frozen.*=.*True"; then
                    echo -e "${RED}❌ ERROR: Model in $file missing frozen=True${NC}"
                    ((VIOLATIONS++))
                fi
            fi

            # Check for ConfigDict usage
            if ! grep -A 10 "class.*BaseModel" "$file" | grep -q "ConfigDict\|model_config"; then
                echo -e "${YELLOW}⚠️  WARNING: Model in $file missing explicit ConfigDict${NC}"
            fi

            # Check for extra="forbid"
            if grep -A 10 "class.*BaseModel" "$file" | grep -q "ConfigDict"; then
                if ! grep -A 10 "ConfigDict" "$file" | grep -q 'extra.*=.*"forbid"'; then
                    echo -e "${YELLOW}⚠️  WARNING: Model in $file missing extra='forbid'${NC}"
                fi
            fi
        fi
    fi
done < <(find src -name "*.py" -type f -print0)

echo ""
echo "📊 Summary:"
echo "  Files checked: $FILES_CHECKED"
echo "  Violations found: $VIOLATIONS"

if [ $VIOLATIONS -gt 0 ]; then
    echo -e "${RED}❌ Pydantic compliance check FAILED!${NC}"
    echo ""
    echo "All Pydantic models MUST use:"
    echo "  - frozen=True (for immutability)"
    echo "  - extra='forbid' (for strict validation)"
    echo "  - explicit ConfigDict configuration"
    echo ""
    echo "Example:"
    echo "class MyModel(BaseModel):"
    echo "    model_config = ConfigDict("
    echo "        frozen=True,"
    echo "        extra='forbid',"
    echo "        validate_assignment=True"
    echo "    )"
    exit 1
else
    echo -e "${GREEN}✅ All Pydantic models are compliant!${NC}"
fi
