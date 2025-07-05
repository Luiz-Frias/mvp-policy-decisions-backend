#!/bin/bash
# scripts/git-commit-robust.sh - Bulletproof commit with debugging

set -e

# Debug mode - set DEBUG=1 for verbose output
DEBUG=${DEBUG:-0}

debug_log() {
    if [ "$DEBUG" = "1" ]; then
        echo "🔍 DEBUG: $*" >&2
    fi
}

info_log() {
    echo "ℹ️  INFO: $*"
}

error_log() {
    echo "❌ ERROR: $*" >&2
}

success_log() {
    echo "✅ SUCCESS: $*"
}

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
debug_log "Project root: $PROJECT_ROOT"

# Ensure we're in the project root
cd "$PROJECT_ROOT"
debug_log "Changed to project root"

# Set GPG home to project directory (should already be set, but ensure it)
export GNUPGHOME="$PROJECT_ROOT/.gpg"
debug_log "GNUPGHOME set to: $GNUPGHOME"

# Get commit message from first argument
if [ -z "$1" ]; then
    error_log "Usage: $0 'commit message'"
    exit 1
fi

COMMIT_MSG="$1"
debug_log "Commit message: $COMMIT_MSG"

info_log "Starting robust commit process..."

# Step 1: Clean up any stale locks
debug_log "Checking for stale git locks..."
if [ -f ".git/index.lock" ]; then
    info_log "Removing stale git index lock"
    rm -f .git/index.lock
    debug_log "Removed .git/index.lock"
fi

# Step 2: Check current git state
debug_log "Checking git status..."
if git diff --cached --quiet && git diff --quiet; then
    error_log "No changes to commit (working tree and index both clean)"
    exit 1
fi

# Step 3: Stage any unstaged changes
if ! git diff --quiet; then
    info_log "Staging unstaged changes..."
    git add -A
    debug_log "Staged all changes"
fi

# Step 4: Verify GPG setup
debug_log "Verifying GPG setup..."
debug_log "Current git cp alias: $(git config --get alias.cp)"
debug_log "GPG processes running: $(ps aux | grep -c '[g]pg-agent' || echo '0')"

# Step 5: Run pre-commit hooks SEPARATELY first
info_log "Running pre-commit validation (separate from git commit)..."
debug_log "Starting pre-commit hook execution..."

# Capture pre-commit output for debugging
if [ "$DEBUG" = "1" ]; then
    if ! uv run .githooks/pre-commit; then
        error_log "Pre-commit hooks failed during separate run"
        exit 1
    fi
else
    if ! uv run .githooks/pre-commit > /tmp/precommit.log 2>&1; then
        error_log "Pre-commit hooks failed. Check /tmp/precommit.log for details"
        cat /tmp/precommit.log
        exit 1
    fi
fi

success_log "Pre-commit hooks passed successfully"

# Step 6: Check if pre-commit modified any files and stage them
debug_log "Checking if pre-commit modified files..."
if ! git diff --quiet; then
    info_log "Pre-commit hooks modified files, staging changes..."
    git add -A
    debug_log "Staged pre-commit modifications"
fi

# Step 7: Verify we still have changes to commit
if git diff --cached --quiet; then
    error_log "No staged changes after pre-commit hooks ran"
    exit 1
fi

# Step 8: Perform the actual commit
info_log "Performing git commit..."
debug_log "Running: git cp '$COMMIT_MSG'"

# Use --no-verify to skip hooks since we already ran them
if [ "$DEBUG" = "1" ]; then
    git commit --no-verify --gpg-sign=60ECAB400532ADB9 -m "$COMMIT_MSG"
else
    git commit --no-verify --gpg-sign=60ECAB400532ADB9 -m "$COMMIT_MSG" > /tmp/commit.log 2>&1
fi

success_log "Commit completed successfully!"
debug_log "Commit process finished"

# Step 9: Show final status
info_log "Final git status:"
git log --oneline -1
debug_log "Script completed successfully"
