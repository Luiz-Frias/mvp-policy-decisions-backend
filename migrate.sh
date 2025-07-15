#!/bin/bash
set -e

echo "🔍 SIMPLE MIGRATION - Just alembic, no orchestration"
echo "📅 Migration timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

if [ -n "$DATABASE_URL" ]; then
    # Display current version (informational only)
    echo "🔍 Current database version (if any)…"
    uv run alembic current || echo "No version found"

    # Reset alembic_version table (if present) and ensure clean slate
    echo "🧹 Stamping database to base with purge…"
    uv run alembic stamp base --purge || true

    # Apply full migration chain up to latest head revision
    echo "🚀 Upgrading database to latest revision (head)…"
    uv run alembic upgrade head

    echo "✅ Database migrations complete!"

    # Show final version
    echo "📊 Final database version:"
    uv run alembic current
else
    echo "⚠️ DATABASE_URL not set"
    exit 1
fi