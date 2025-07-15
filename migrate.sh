#!/bin/bash
set -e

echo "🚀 Running database migrations with Celery queue..."
echo "📅 Migration timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

# Doppler provides DATABASE_URL and REDIS_URL
if [ -n "$DATABASE_URL" ]; then
    echo "🔄 Using Celery-based migration queue..."
    
    # Use Celery migration runner
    uv run python /app/celery_migrate.py || {
        echo "❌ Celery migration failed, trying fallback..."
        
        # Fallback to direct migration if Celery fails
        echo "🔄 Fallback: Running direct migrations..."
        uv run python /app/run-migrations.py || {
            echo "❌ Database migrations failed completely"
            exit 1
        }
    }
    
    echo "✅ All migrations completed successfully!"
else
    echo "⚠️ DATABASE_URL not set, skipping migrations"
    exit 1
fi