#!/bin/bash
set -e

echo "🔍 SIMPLE MIGRATION - Just alembic, no orchestration"
echo "📅 Migration timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

if [ -n "$DATABASE_URL" ]; then
    # First, clear any existing alembic version
    echo "🧹 Clearing existing alembic version..."
    uv run alembic stamp --purge || true
    
    # Now stamp as latest
    echo "🔧 Stamping database as revision 012 (latest)"
    uv run alembic stamp 012
    echo "✅ Database stamped as current - ready for FastAPI!"
else
    echo "⚠️ DATABASE_URL not set"
    exit 1
fi