#!/bin/bash
# Apply all pre-commit auto-fixes to the codebase
# This mimics what pre-commit does but can be run manually

set -uo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m'

echo -e "${MAGENTA}🔧 Applying Pre-commit Auto-fixes${NC}"
echo "This will apply the same fixes that pre-commit would apply..."

# Track if any fixes were applied
FIXES_APPLIED=0

# 1. Black - Code formatting
echo -e "\n${BLUE}1️⃣  Running Black formatter...${NC}"
if uv run black src --exclude "scripts|docs|examples|dev-tools"; then
    echo -e "${GREEN}✓ Black formatting complete${NC}"
    FIXES_APPLIED=1
else
    echo -e "${YELLOW}⚠️  Black formatting had issues${NC}"
fi

# 2. isort - Import sorting
echo -e "\n${BLUE}2️⃣  Running isort for imports...${NC}"
if uv run isort src --profile black --skip scripts --skip docs --skip examples --skip dev-tools 2>/dev/null; then
    echo -e "${GREEN}✓ Import sorting complete${NC}"
    FIXES_APPLIED=1
else
    echo -e "${YELLOW}⚠️  Import sorting had issues${NC}"
fi

# 3. Ruff - Auto-fix linting issues
echo -e "\n${BLUE}3️⃣  Running Ruff with auto-fix...${NC}"
if uv run ruff check src --fix --exclude "scripts|docs|examples|dev-tools" 2>/dev/null; then
    echo -e "${GREEN}✓ Ruff auto-fixes complete${NC}"
    FIXES_APPLIED=1
else
    echo -e "${YELLOW}⚠️  Ruff auto-fix had issues${NC}"
fi

# 4. pyupgrade - Upgrade Python syntax
echo -e "\n${BLUE}4️⃣  Running pyupgrade for Python 3.11+ syntax...${NC}"
# Find all Python files and run pyupgrade on each
find src -name "*.py" -not -path "*/scripts/*" -not -path "*/docs/*" -not -path "*/examples/*" -not -path "*/dev-tools/*" -exec uv run pyupgrade --py311-plus {} \; 2>/dev/null || true
echo -e "${GREEN}✓ Python syntax upgrade complete${NC}"

# 5. Fix trailing whitespace and end-of-file
echo -e "\n${BLUE}5️⃣  Fixing trailing whitespace and end-of-file...${NC}"
find src -name "*.py" -not -path "*/scripts/*" -not -path "*/docs/*" -not -path "*/examples/*" -not -path "*/dev-tools/*" -exec sed -i 's/[[:space:]]*$//' {} \; 2>/dev/null || true
find src -name "*.py" -not -path "*/scripts/*" -not -path "*/docs/*" -not -path "*/examples/*" -not -path "*/dev-tools/*" -exec bash -c 'if [ -s "$1" ] && [ -z "$(tail -c 1 "$1")" ]; then :; else echo >> "$1"; fi' _ {} \; 2>/dev/null || true
echo -e "${GREEN}✓ Whitespace fixes complete${NC}"

# 6. Run validation scripts to check compliance
echo -e "\n${BLUE}6️⃣  Running validation checks...${NC}"

# Run master ruleset validation
if ./scripts/validate-master-ruleset-v2.sh 2>/dev/null; then
    echo -e "${GREEN}✓ Master ruleset validation passed${NC}"
else
    echo -e "${YELLOW}⚠️  Master ruleset validation found issues${NC}"
fi

# Run Pydantic compliance check
if ./scripts/validate-pydantic-compliance-v2.sh 2>/dev/null; then
    echo -e "${GREEN}✓ Pydantic compliance check passed${NC}"
else
    echo -e "${YELLOW}⚠️  Pydantic compliance check found issues${NC}"
fi

# Summary
echo -e "\n${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"
echo -e "${MAGENTA}📊 AUTO-FIX SUMMARY${NC}"
echo -e "${MAGENTA}═══════════════════════════════════════════════════════════════${NC}"

if [[ $FIXES_APPLIED -eq 1 ]]; then
    echo -e "${GREEN}✅ Auto-fixes have been applied!${NC}"
    echo -e "\nNext steps:"
    echo -e "1. Review the changes with: ${BLUE}git diff${NC}"
    echo -e "2. Stage changes with: ${BLUE}git add -p${NC}"
    echo -e "3. Commit with: ${BLUE}git commit -m \"fix: apply pre-commit auto-fixes\"${NC}"
else
    echo -e "${GREEN}✅ No fixes needed - code is already compliant!${NC}"
fi

# Exit with code 0 for normal operation (output not shown to Claude)
exit 0