#!/bin/bash
# scripts/setup-dev-env.sh - Persistent development environment setup for Railway

set -e  # Exit on any error

echo "🔧 Setting up persistent development environment for Railway..."

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
echo "📁 Project root: $PROJECT_ROOT"

# Set project-level GPG home (persists in Railway volume)
export GNUPGHOME="$PROJECT_ROOT/.gpg"
echo "🔐 GPG home: $GNUPGHOME"

# Ensure GPG directory exists with proper permissions
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"

# Configure git for this project (persists in project .git/config)
echo "⚙️  Configuring project-level git settings..."
git config --local user.name "Luiz Frias"
git config --local user.email "luizf35@gmail.com"
git config --local commit.gpgsign true

# Set up initial git aliases (will be updated with key IDs later)
git config --local alias.ca 'commit --gpg-sign -m'
git config --local alias.cp 'commit --gpg-sign -m'
git config --local alias.cn 'commit --no-gpg-sign -m'

# Export GPG home for current session
echo "export GNUPGHOME=\"$PROJECT_ROOT/.gpg\"" >> ~/.bashrc

echo "✅ Development environment configured!"
echo "🔑 GPG directory: $GNUPGHOME"
echo "📝 Git aliases configured for this project"
echo ""
echo "Next steps:"
echo "1. Run 'source ~/.bashrc' or restart your shell"
echo "2. Generate GPG keys with './scripts/generate-gpg-keys.sh'"
echo "3. Update git aliases with key IDs"
