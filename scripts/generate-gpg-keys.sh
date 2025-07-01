#!/bin/bash
# scripts/generate-gpg-keys.sh - Generate project-level GPG keys

set -e  # Exit on any error

echo "🔑 Generating project-level GPG keys..."

# Get the project root directory
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Set GPG home to project directory
export GNUPGHOME="$PROJECT_ROOT/.gpg"

# Ensure GPG directory exists with proper permissions
mkdir -p "$GNUPGHOME"
chmod 700 "$GNUPGHOME"

echo "📍 Using GPG home: $GNUPGHOME"

# Generate automated key (no passphrase for CI/CD)
echo "🤖 Generating automated key (no passphrase)..."
gpg --batch --generate-key << EOF
%no-protection
Key-Type: RSA
Key-Length: 4096
Name-Real: Luiz Frias (Automated)
Name-Email: luizf35@gmail.com
Expire-Date: 2y
%commit
EOF

echo "✅ Automated key generated!"

# Generate personal key (with passphrase) - interactive
echo "👤 Generating personal key (with passphrase)..."
echo "⚠️  You will be prompted to enter a passphrase for your personal key."
echo "💡 This key is for manual commits that require extra security."
echo ""

gpg --full-generate-key << EOF
1
4096
2y
y
Luiz Frias (Personal)
luizf35@gmail.com
Strong passphrase for personal commits
EOF

echo "✅ Personal key generated!"

# List all keys
echo ""
echo "📋 Generated keys:"
gpg --list-secret-keys --keyid-format=long

# Get key IDs
echo ""
echo "🔍 Extracting key IDs..."
AUTO_KEY=$(gpg --list-secret-keys --keyid-format=long | grep -A1 "Luiz Frias (Automated)" | grep "sec" | awk '{print $2}' | cut -d'/' -f2 | head -1)
PERSONAL_KEY=$(gpg --list-secret-keys --keyid-format=long | grep -A1 "Luiz Frias (Personal)" | grep "sec" | awk '{print $2}' | cut -d'/' -f2 | head -1)

if [ -n "$AUTO_KEY" ] && [ -n "$PERSONAL_KEY" ]; then
    echo "🔑 Automated key ID: $AUTO_KEY"
    echo "🔑 Personal key ID: $PERSONAL_KEY"

    # Update git aliases with specific key IDs
    echo "⚙️  Updating git aliases with key IDs..."
    cd "$PROJECT_ROOT"
    git config --local alias.ca "commit --gpg-sign=$AUTO_KEY -m"
    git config --local alias.cp "commit --gpg-sign=$PERSONAL_KEY -m"

    echo "✅ Git aliases updated!"
    echo ""
    echo "🎉 GPG setup complete! You can now use:"
    echo "   git ca \"message\"  # Automated commits (no passphrase)"
    echo "   git cp \"message\"  # Personal commits (with passphrase)"
    echo "   git cn \"message\"  # No signing"
else
    echo "❌ Could not extract key IDs. Please check key generation."
    exit 1
fi
