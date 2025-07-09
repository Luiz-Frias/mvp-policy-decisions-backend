#!/bin/bash
# Validate that all Pydantic models use frozen=True and follow master ruleset

# Colors for output declared EARLY so they are available to any echo -e prior to later re-declarations
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

set -euo pipefail

echo "🔍 Checking Pydantic model compliance..."

# Check for git zombie processes first
echo "🔍 Checking for git zombie processes..."
zombies=$(ps aux | grep '[Zz]' | grep 'git' | grep -v grep || true)
if [[ -n "$zombies" ]]; then
    echo -e "${YELLOW}⚠️  WARNING: Found git zombie processes, attempting automatic cleanup...${NC}"
    # Extract PIDs and attempt to kill parent processes gracefully
    pids=$(echo "$zombies" | awk '{print $2}')
    for pid in $pids; do
        # Get parent process id (PPID)
        ppid=$(ps -o ppid= -p "$pid" | tr -d ' ')
        if [[ -n "$ppid" ]]; then
            kill -HUP "$ppid" 2>/dev/null || true
        fi
    done
    sleep 2
    # Re-check for zombies after attempted cleanup
    zombies_post=$(ps aux | grep '[Zz]' | grep 'git' | grep -v grep || true)
    if [[ -n "$zombies_post" ]]; then
        echo -e "${RED}❌ ERROR: Zombie git processes persist after cleanup attempt:${NC}"
        echo "$zombies_post"
        echo "Please identify and terminate parent processes before committing."
        exit 1
    else
        echo -e "${GREEN}✓ Zombie processes cleaned up successfully${NC}"
    fi
else
    echo -e "${GREEN}✓ No git zombie processes found${NC}"
fi

# Track violations
VIOLATIONS=0
FILES_CHECKED=0

# Find all Python files in src/
# Temporarily disable `set -e` so that non-zero exit codes from grep inside the
# scanning loop don't abort the entire script prematurely; we still record
# violations and will exit with non-zero at the end if any were found.
set +e

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
done < <(find src -name "*.py" -type f -not -path "*/example_elite_pattern.py" -print0)

# Re-enable strict error handling for the remainder of the script.
set -e

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
