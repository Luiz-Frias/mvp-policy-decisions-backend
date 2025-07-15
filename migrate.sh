#!/bin/bash
set -e

echo "🔍 SIMPLE MIGRATION - Just alembic, no orchestration"
echo "📅 Migration timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

if [ -n "$DATABASE_URL" ]; then
    echo "🚀 Running basic alembic upgrade:"
    uv run alembic upgrade head || {
        echo "❌ Alembic upgrade failed"
        exit 1
    }
    echo "✅ Migration completed!"
else
    echo "⚠️ DATABASE_URL not set"
    exit 1
fi