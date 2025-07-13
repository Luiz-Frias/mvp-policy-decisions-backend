#!/bin/bash
# scripts/git-commit-safe.sh - Safe commit with proper GPG environment

set -e

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Set GPG home to project directory
export GNUPGHOME="$PROJECT_ROOT/.gpg"

# Ensure we're in the project root
cd "$PROJECT_ROOT"

# Remove any stale lock files
rm -f .git/index.lock

# Check if we have staged changes
if git diff --cached --quiet; then
    echo "⚠️  No staged changes found. Staging all changes..."
    git add -A
fi

# Check if we still have no changes
if git diff --cached --quiet; then
    echo "❌ No changes to commit."
    exit 1
fi

# Get commit message from first argument
if [ -z "$1" ]; then
    echo "❌ Usage: $0 'commit message'"
    exit 1
fi

COMMIT_MSG="$1"

echo "🔧 Setting up GPG environment..."
echo "📁 Project root: $PROJECT_ROOT"
echo "🔑 GPG home: $GNUPGHOME"

# Restart GPG agent to ensure it's using the right directory
gpg-connect-agent --homedir "$GNUPGHOME" reloadagent /bye 2>/dev/null || true

echo "🧪 Running pre-commit checks..."
# Run pre-commit hook manually first
if ! uv run .githooks/pre-commit; then
    echo "❌ Pre-commit checks failed. Fix issues and try again."
    exit 1
fi

echo "📝 Committing with message: $COMMIT_MSG"

# Use git cp alias which should now have the correct key
git cp "$COMMIT_MSG"

echo "✅ Commit successful!"
# Test change
