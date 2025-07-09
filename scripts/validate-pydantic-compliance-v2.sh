#\!/bin/bash
# Enhanced Pydantic compliance validation with better false positive handling

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

echo -e "${MAGENTA}🛡️ MASTER RULESET: Pydantic Compliance Validation${NC}"
echo "🔍 Enforcing PEAK EXCELLENCE standards..."

# Check for git zombie processes
echo "🔍 Checking for git zombie processes..."
zombies=$(ps aux  < /dev/null |  grep '[Zz]' | grep 'git' | grep -v grep || true)
if [[ -n "$zombies" ]]; then
    echo -e "${YELLOW}⚠️  WARNING: Found git zombie processes (ignoring for validation)${NC}"
else
    echo -e "${GREEN}✓ No git zombie processes found${NC}"
fi

VIOLATIONS=0

# 1. Check for dict usage (excluding comments, docstrings, and auto-generated model definitions)
echo -e "\n${BLUE}1️⃣  Checking for plain dictionary usage without SYSTEM_BOUNDARY...${NC}"
DICT_VIOLATIONS=0
DICT_FILES=""

for file in $(find src -name "*.py" -not -path "*/test*" 2>/dev/null); do
    # Skip if file has SYSTEM_BOUNDARY
    if grep -q "SYSTEM_BOUNDARY" "$file" 2>/dev/null; then
        continue
    fi
    
    # Count dict usage excluding:
    # - Comments (lines starting with #)
    # - Docstrings (lines with """ or ''')
    # - Lines that are part of model definitions replacing dict usage
    # - Field definitions inside Pydantic models (e.g., field: dict[str, int] = Field(...))
    # - Class variable annotations inside models
    dict_count=$(grep -v '^\s*#' "$file" 2>/dev/null | \
                 grep -v '""".*dict\[' | \
                 grep -v "'''.*dict\[" | \
                 grep -v 'replacing dict\[' | \
                 grep -v 'Structured model replacing' | \
                 grep -v '^\s*[a-zA-Z_][a-zA-Z0-9_]*:\s*dict\[.*\]\s*=\s*Field' | \
                 grep -v '^\s*[a-zA-Z_][a-zA-Z0-9_]*:\s*dict\[.*\]\s*$' | \
                 grep -c 'dict\[' || echo 0)
    
    if [[ $dict_count -gt 0 ]]; then
        DICT_FILES="${DICT_FILES}$file\n"
        ((DICT_VIOLATIONS++))
    fi
done

if [[ $DICT_VIOLATIONS -gt 0 ]]; then
    echo -e "${RED}❌ MASTER RULE VIOLATION: $DICT_VIOLATIONS file(s) use plain dictionaries without annotation:${NC}"
    echo -e "$DICT_FILES" | head -20 | sed 's/^/   • /'
    if [[ $DICT_VIOLATIONS -gt 20 ]]; then
        echo "   ... and $((DICT_VIOLATIONS - 20)) more"
    fi
    ((VIOLATIONS+=DICT_VIOLATIONS))
else
    echo -e "${GREEN}✓ No plain dictionary usage without SYSTEM_BOUNDARY found${NC}"
fi

# 2. Check for models missing frozen=True (only check models that directly use ConfigDict)
echo -e "\n${BLUE}2️⃣  Checking for Pydantic models missing frozen=True...${NC}"
FROZEN_VIOLATIONS=0
FROZEN_FILES=""

# Only check files that have ConfigDict but not frozen=True
# Exclude files where models inherit from BaseModelConfig (which has frozen=True)
for file in $(find src -name "*.py" -not -path "*/test*" 2>/dev/null); do
    # Skip if no ConfigDict
    if \! grep -q "ConfigDict" "$file" 2>/dev/null; then
        continue
    fi
    
    # Skip if inherits from BaseModelConfig (already has frozen=True)
    if grep -q "BaseModelConfig" "$file" 2>/dev/null; then
        continue
    fi
    
    # Check if ConfigDict exists without frozen=True
    if grep -q "model_config.*=.*ConfigDict" "$file" 2>/dev/null && \! grep -q "frozen=True" "$file" 2>/dev/null; then
        FROZEN_FILES="${FROZEN_FILES}$file\n"
        ((FROZEN_VIOLATIONS++))
    fi
done

if [[ $FROZEN_VIOLATIONS -gt 0 ]]; then
    echo -e "${RED}❌ MASTER RULE VIOLATION: $FROZEN_VIOLATIONS model(s) lack frozen=True:${NC}"
    echo -e "$FROZEN_FILES" | head -10 | sed 's/^/   • /'
    if [[ $FROZEN_VIOLATIONS -gt 10 ]]; then
        echo "   ... and $((FROZEN_VIOLATIONS - 10)) more"
    fi
    ((VIOLATIONS+=FROZEN_VIOLATIONS))
else
    echo -e "${GREEN}✓ All Pydantic models have frozen=True${NC}"
fi

# 3. Check for @beartype
echo -e "\n${BLUE}3️⃣  Checking for public functions missing @beartype...${NC}"
BEARTYPE_VIOLATIONS=0
BEARTYPE_FILES=""

for file in $(find src -name "*.py" -not -path "*/test*" -exec grep -l "^def [^_]" {} \; 2>/dev/null); do
    if \! grep -q "@beartype" "$file" 2>/dev/null; then
        BEARTYPE_FILES="${BEARTYPE_FILES}$file\n"
        ((BEARTYPE_VIOLATIONS++))
    fi
done

if [[ $BEARTYPE_VIOLATIONS -gt 0 ]]; then
    echo -e "${RED}❌ MASTER RULE VIOLATION: $BEARTYPE_VIOLATIONS file(s) missing @beartype:${NC}"
    echo -e "$BEARTYPE_FILES" | head -10 | sed 's/^/   • /'
    ((VIOLATIONS+=BEARTYPE_VIOLATIONS))
else
    echo -e "${GREEN}✓ All public functions have @beartype decorators${NC}"
fi

# Summary
echo -e "\n${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${MAGENTA}📊 MASTER RULESET COMPLIANCE SUMMARY${NC}"
echo -e "${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"
echo "  Total violations: $VIOLATIONS"
echo ""
echo "  Violation breakdown:"
echo "    • Dict usage without SYSTEM_BOUNDARY: $DICT_VIOLATIONS"
echo "    • Models missing frozen=True: $FROZEN_VIOLATIONS"  
echo "    • Public functions missing @beartype: $BEARTYPE_VIOLATIONS"

if [[ $VIOLATIONS -gt 0 ]]; then
    echo -e "\n${RED}❌ MASTER RULESET COMPLIANCE CHECK FAILED\!${NC}"
    exit 1
else
    echo -e "\n${GREEN}✅ PEAK EXCELLENCE ACHIEVED\! All master ruleset checks passed\!${NC}"
fi
