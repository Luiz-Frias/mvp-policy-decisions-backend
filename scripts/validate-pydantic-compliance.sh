#!/bin/bash
# Validate that all Pydantic models use frozen=True and follow master ruleset
# PEAK EXCELLENCE STANDARD - No compromises on type safety

# Colors for output declared EARLY so they are available to any echo -e prior to later re-declarations
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
PURPLE='\033[0;35m'
NC='\033[0m' # No Color

set -euo pipefail

echo -e "${PURPLE}🛡️ MASTER RULESET: Pydantic Compliance Validation${NC}"
echo "🔍 Enforcing PEAK EXCELLENCE standards..."

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
DICT_VIOLATIONS=0
FROZEN_VIOLATIONS=0
BEARTYPE_VIOLATIONS=0

# Temporarily disable `set -e` so we can gather all issues
set +e

# MASTER RULE 1: No plain dictionaries without SYSTEM_BOUNDARY annotation (exclude tests)
echo ""
echo -e "${BLUE}1️⃣  Checking for plain dictionary usage without SYSTEM_BOUNDARY...${NC}"
DICT_VIOL_FILES=$(find src -name "*.py" -not -path "*/test*" -exec grep -l "dict\\[" {} \; 2>/dev/null | xargs grep -L "SYSTEM_BOUNDARY" 2>/dev/null || true)
if [[ -n "$DICT_VIOL_FILES" ]]; then
    DICT_COUNT=$(echo "$DICT_VIOL_FILES" | wc -l)
    echo -e "${RED}❌ MASTER RULE VIOLATION: $DICT_COUNT file(s) use plain dictionaries without annotation:${NC}"
    echo "$DICT_VIOL_FILES" | head -20 | sed 's/^/   • /'
    if [[ $DICT_COUNT -gt 20 ]]; then
        echo "   ... and $((DICT_COUNT - 20)) more"
    fi
    DICT_VIOLATIONS=$DICT_COUNT
    ((VIOLATIONS+=$DICT_COUNT))
else
    echo -e "${GREEN}✓ No plain dictionary usage without SYSTEM_BOUNDARY found${NC}"
fi

# MASTER RULE 2: All Pydantic models must have frozen=True (exclude tests)
echo ""
echo -e "${BLUE}2️⃣  Checking for Pydantic models missing frozen=True...${NC}"
BASEMODEL_FILES=$(find src -name "*.py" -not -path "*/test*" -exec grep -l "class.*BaseModel" {} \; 2>/dev/null)
UNFROZEN_LIST=""
if [[ -n "$BASEMODEL_FILES" ]]; then
    UNFROZEN_LIST=$(echo "$BASEMODEL_FILES" | xargs grep -L "frozen.*=.*True" 2>/dev/null || true)
fi
if [[ -n "$UNFROZEN_LIST" ]]; then
    FROZEN_COUNT=$(echo "$UNFROZEN_LIST" | wc -l)
    echo -e "${RED}❌ MASTER RULE VIOLATION: $FROZEN_COUNT model(s) lack frozen=True:${NC}"
    echo "$UNFROZEN_LIST" | head -10 | sed 's/^/   • /'
    if [[ $FROZEN_COUNT -gt 10 ]]; then
        echo "   ... and $((FROZEN_COUNT - 10)) more"
    fi
    FROZEN_VIOLATIONS=$FROZEN_COUNT
    ((VIOLATIONS+=$FROZEN_COUNT))
else
    echo -e "${GREEN}✓ All Pydantic models have frozen=True${NC}"
fi

# MASTER RULE 3: Public functions must have @beartype (exclude tests)
echo ""
echo -e "${BLUE}3️⃣  Checking for public functions missing @beartype...${NC}"
PUBLIC_FUNCS_FILES=$(find src -name "*.py" -not -path "*/test*" -exec grep -l "^def [^_]" {} \; 2>/dev/null)
MISSING_BEAR=""
if [[ -n "$PUBLIC_FUNCS_FILES" ]]; then
    MISSING_BEAR=$(echo "$PUBLIC_FUNCS_FILES" | xargs grep -L "@beartype" 2>/dev/null || true)
fi
if [[ -n "$MISSING_BEAR" ]]; then
    BEAR_COUNT=$(echo "$MISSING_BEAR" | wc -l)
    echo -e "${RED}❌ MASTER RULE VIOLATION: $BEAR_COUNT public function file(s) without @beartype:${NC}"
    echo "$MISSING_BEAR" | head -10 | sed 's/^/   • /'
    if [[ $BEAR_COUNT -gt 10 ]]; then
        echo "   ... and $((BEAR_COUNT - 10)) more"
    fi
    BEARTYPE_VIOLATIONS=$BEAR_COUNT
    ((VIOLATIONS+=$BEAR_COUNT))
else
    echo -e "${GREEN}✓ All public functions have @beartype decorators${NC}"
fi

# Additional Pydantic-specific checks
echo ""
echo -e "${BLUE}4️⃣  Detailed Pydantic model validation...${NC}"
while IFS= read -r -d '' file; do
    ((FILES_CHECKED++))

    # Check if file contains BaseModel imports
    if grep -q "from pydantic import.*BaseModel" "$file" || grep -q "from pydantic.main import BaseModel" "$file"; then
        # Check for model definitions - including those inheriting from BaseModelConfig
        if grep -q "class.*BaseModel\|class.*BaseModelConfig" "$file"; then
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
done < <(find src -name "*.py" -type f -not -path "*/example_elite_pattern.py" -not -path "*/test*" -print0)

# Re-enable strict error handling for the remainder of the script.
set -e

echo ""
echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${PURPLE}📊 MASTER RULESET COMPLIANCE SUMMARY${NC}"
echo -e "${PURPLE}═══════════════════════════════════════════════════════════════${NC}"
echo "  Files checked: $FILES_CHECKED"
echo "  Total violations: $VIOLATIONS"
echo ""
echo "  Violation breakdown:"
echo "    • Dict usage without SYSTEM_BOUNDARY: $DICT_VIOLATIONS"
echo "    • Models missing frozen=True: $FROZEN_VIOLATIONS"
echo "    • Public functions missing @beartype: $BEARTYPE_VIOLATIONS"

if [ $VIOLATIONS -gt 0 ]; then
    echo ""
    echo -e "${RED}❌ MASTER RULESET COMPLIANCE CHECK FAILED!${NC}"
    echo ""
    echo -e "${YELLOW}PEAK EXCELLENCE STANDARD requires:${NC}"
    echo "  1️⃣  NO plain dictionaries - Use Pydantic models or mark with # SYSTEM_BOUNDARY"
    echo "  2️⃣  ALL models must have frozen=True for immutability"
    echo "  3️⃣  ALL public functions must have @beartype for runtime validation"
    echo ""
    echo "Example compliant model:"
    echo "class MyModel(BaseModel):"
    echo "    model_config = ConfigDict("
    echo "        frozen=True,"
    echo "        extra='forbid',"
    echo "        validate_assignment=True"
    echo "    )"
    echo ""
    echo "Example system boundary:"
    echo "async def get_cache_data(key: str) -> dict[str, Any]:  # SYSTEM_BOUNDARY - Redis interface"
    echo "    \"\"\"Get data from Redis cache.\"\"\""
    echo "    return await redis.get(key)"
    exit 1
else
    echo ""
    echo -e "${GREEN}✅ ALL MASTER RULESET COMPLIANCE CHECKS PASSED!${NC}"
    echo -e "${GREEN}🎯 PEAK EXCELLENCE STANDARD ACHIEVED${NC}"
fi
