#!/bin/bash
set -e

echo "🔍 SIMPLE MIGRATION - Just alembic, no orchestration"
echo "📅 Migration timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

if [ -n "$DATABASE_URL" ]; then
    # Tables already exist, just stamp as current
    echo "🔧 Stamping database as current version (tables exist from manual migration)"
    uv run alembic stamp head
    echo "✅ Database stamped as current - ready for FastAPI!"
else
    echo "⚠️ DATABASE_URL not set"
    exit 1
fi