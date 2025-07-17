#!/bin/bash
set -e

# ---------------------------------------------------------------------------
# Construct DATABASE_URL from individual PG* env vars if it is not already
# provided (useful when Doppler only supplies PGHOST, PGUSER, etc.).
# ---------------------------------------------------------------------------

if [ -z "$DATABASE_URL" ] && [ -n "$PGHOST" ] && [ -n "$PGPASSWORD" ] && [ -n "$PGUSER" ] && [ -n "$PGDATABASE" ]; then
  export DATABASE_URL="postgresql://${PGUSER}:${PGPASSWORD}@${PGHOST}:${PGPORT:-5432}/${PGDATABASE}"
  echo "🔗 Synthesised DATABASE_URL from PG* variables -> ${DATABASE_URL%%@*}@${PGHOST}:${PGPORT:-5432}/${PGDATABASE}"
fi

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