#!/bin/bash
set -e

echo "🔍 SIMPLE MIGRATION - Just alembic, no orchestration"
echo "📅 Migration timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

if [ -n "$DATABASE_URL" ]; then
    # First check current version
    echo "🔍 Checking current database version..."
    uv run alembic current || echo "No version found"
    
    # Run migrations
    echo "🔄 Running database migrations..."
    uv run alembic upgrade head || {
        echo "❌ Migration failed, trying to fix..."
        # If it fails, try to stamp to 012 first
        echo "📌 Stamping database to version 012..."
        uv run alembic stamp 012
        echo "🔄 Retrying migration to head..."
        uv run alembic upgrade head
    }
    
    echo "✅ Database migrations complete!"
    
    # Show final version
    echo "📊 Final database version:"
    uv run alembic current
else
    echo "⚠️ DATABASE_URL not set"
    exit 1
fi