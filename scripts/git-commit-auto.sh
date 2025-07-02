#!/bin/bash
# Automated GPG-signed commits using Doppler secrets

set -e

# Get environment from first argument or default to dev
ENV=${1:-dev}
shift || true  # Remove first argument if it exists

# Get commit message
if [ $# -eq 0 ]; then
    echo "Usage: $0 [env] <commit_message>"
    echo "Example: $0 dev 'feat: add new feature'"
    echo "Example: $0 'feat: add new feature'  # defaults to dev"
    exit 1
fi

COMMIT_MSG="$*"

echo "🔐 Retrieving GPG passphrase from Doppler ($ENV environment)..."
export GPG_PASSPHRASE=$(doppler secrets get GPG_PASSPHRASE --plain --project mvp-policy-decision-backend --config $ENV)

if [ -z "$GPG_PASSPHRASE" ]; then
    echo "❌ Failed to retrieve GPG passphrase from Doppler"
    exit 1
fi

export GPG_TTY=$(tty)
export GNUPGHOME=${GNUPGHOME:-$HOME/.gnupg}

echo "✅ GPG environment configured"
echo "🎯 Committing with message: $COMMIT_MSG"

# Use git cp alias (personal key) with passphrase piped in
echo "$GPG_PASSPHRASE" | git commit --gpg-sign=9E6E57847F99FEE0 -m "$COMMIT_MSG" --pinentry-mode loopback --passphrase-fd 0

echo "🎉 Commit successful with GPG signature!"
