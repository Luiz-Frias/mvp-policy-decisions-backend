#!/bin/bash
set -e

echo "🚀 Running database migrations BEFORE starting the app..."
echo "📅 Migration timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

# Doppler provides DATABASE_URL in uppercase
if [ -n "$DATABASE_URL" ]; then
    echo "🔄 Running migrations with detailed debugging..."
    
    # Use our custom migration runner that handles everything
    uv run python /app/run-migrations.py || {
        echo "❌ Database migrations failed"
        exit 1
    }
    
    echo "✅ All migrations completed successfully!"
else
    echo "⚠️ DATABASE_URL not set, skipping migrations"
    exit 1
fi