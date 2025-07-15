#!/bin/bash
set -e

echo "🔍 SIMPLE MIGRATION - Just alembic, no orchestration"
echo "📅 Migration timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

if [ -n "$DATABASE_URL" ]; then
    echo "🧹 Resetting Alembic version table (if present)..."
    # Stamp the database to 'base' and purge the version table so we can run real migrations.
    uv run alembic stamp base --purge || true

    # Apply all migrations up to the latest head revision.
    echo "🔄 Upgrading database to latest revision (head)..."
    uv run alembic upgrade head
    echo "✅ Database schema upgraded to latest revision!"
else
    echo "⚠️ DATABASE_URL not set"
    exit 1
fi