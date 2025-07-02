#!/bin/bash
# scripts/generate-gpg-keys-simple.sh - Generate project-level GPG keys (Railway-friendly)

set -e  # Exit on any error

echo "🔑 Generating project-level GPG keys for Railway..."

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
gpg --batch --generate-key << EOG
%no-protection
Key-Type: RSA
Key-Length: 4096
Name-Real: Luiz Frias (Automated)
Name-Email: luizf35@gmail.com
Expire-Date: 2y
%commit
EOG

echo "✅ Automated key generated!"

# Generate personal key (no passphrase for Railway simplicity)
echo "👤 Generating personal key (no passphrase for Railway)..."
gpg --batch --generate-key << EOG
%no-protection
Key-Type: RSA
Key-Length: 4096
Name-Real: Luiz Frias (Personal)
Name-Email: luizf35@gmail.com
Expire-Date: 2y
%commit
EOG

echo "✅ Personal key generated!"

# Wait a moment for key generation to complete
sleep 2

# List all keys
echo ""
echo "📋 Generated keys:"
gpg --list-secret-keys --keyid-format=long

# Get key IDs - more robust extraction
echo ""
echo "🔍 Extracting key IDs..."

# Get all key IDs
ALL_KEYS=$(gpg --list-secret-keys --keyid-format=long --with-colons | grep "^sec" | cut -d: -f5)
AUTO_KEY=$(echo "$ALL_KEYS" | head -1)
PERSONAL_KEY=$(echo "$ALL_KEYS" | tail -1)

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
    echo "�� GPG setup complete! You can now use:"
    echo "   git ca \"message\"  # Automated commits"
    echo "   git cp \"message\"  # Personal commits"
    echo "   git cn \"message\"  # No signing"
else
    echo "❌ Could not extract key IDs."
    echo "Available keys: $ALL_KEYS"
    exit 1
fi
