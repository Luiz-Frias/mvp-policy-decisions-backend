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
git config --local core.hooksPath .githooks

# Check if GPG keys exist and get their IDs
if [ -f "$GNUPGHOME/pubring.kbx" ]; then
    echo "🔍 Detecting existing GPG keys..."

    # Get the most recent automated and personal keys
    AUTO_KEY=$(gpg --list-secret-keys --keyid-format=long | grep -A1 "Luiz Frias (Automated)" | grep "sec" | awk '{print $2}' | cut -d'/' -f2 | tail -1)
    PERSONAL_KEY=$(gpg --list-secret-keys --keyid-format=long | grep -A1 "Luiz Frias (Personal)" | grep "sec" | awk '{print $2}' | cut -d'/' -f2 | tail -1)

    if [ -n "$AUTO_KEY" ] && [ -n "$PERSONAL_KEY" ]; then
        echo "🔑 Found automated key: $AUTO_KEY"
        echo "🔑 Found personal key: $PERSONAL_KEY"

        # Set up git aliases with detected keys
        git config --local alias.ca "commit --gpg-sign=$AUTO_KEY -m"
        git config --local alias.cp "commit --gpg-sign=$PERSONAL_KEY -m"
        git config --local alias.cn "commit --no-gpg-sign -m"

        echo "✅ Git aliases configured with existing keys!"
    else
        echo "⚠️  GPG keys exist but couldn't detect key IDs properly"
        echo "🔧 Setting up basic aliases without specific keys..."
        git config --local alias.ca "commit --gpg-sign -m"
        git config --local alias.cp "commit --gpg-sign -m"
        git config --local alias.cn "commit --no-gpg-sign -m"
    fi
else
    echo "🔧 No GPG keys found, setting up basic aliases..."
    git config --local alias.ca "commit --gpg-sign -m"
    git config --local alias.cp "commit --gpg-sign -m"
    git config --local alias.cn "commit --no-gpg-sign -m"
fi

# Ensure GPG agent is using the correct directory
echo "🔄 Restarting GPG agent for project directory..."
gpg-connect-agent --homedir "$GNUPGHOME" reloadagent /bye 2>/dev/null || true

# Export GPG home for current session and future sessions
echo "export GNUPGHOME=\"$PROJECT_ROOT/.gpg\"" >> ~/.bashrc

echo ""
echo "✅ Development environment configured!"
echo "🔑 GPG directory: $GNUPGHOME"
echo "📝 Git aliases configured for this project:"
echo "   git ca \"message\"  # Automated commits"
echo "   git cp \"message\"  # Personal commits"
echo "   git cn \"message\"  # No signing"
echo ""
echo "Next steps:"
echo "1. Run 'source ~/.bashrc' or restart your shell"
if [ ! -f "$GNUPGHOME/pubring.kbx" ]; then
    echo "2. Generate GPG keys with './scripts/generate-gpg-keys.sh'"
fi
echo "3. Test with: git cp 'test: commit message'"
