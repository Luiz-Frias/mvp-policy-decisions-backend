#!/bin/bash
set -e

echo "🚀 Starting MVP Policy Decision Backend - Production"
echo "Environment: $APP_ENV"
echo "API Port: $API_PORT"
echo "WebSocket Port: $WEBSOCKET_PORT"

# Debug: Show environment variables
echo "📊 Environment check:"
echo "  DATABASE_URL: ${DATABASE_URL:-NOT SET}"
echo "  PATH: $PATH"
echo "  Which uv: $(which uv || echo 'uv not found in PATH')"
echo "  uv location: $(ls -la /bin/uv 2>&1 || echo '/bin/uv not found')"

# Doppler provides DATABASE_URL in uppercase
# Run database migrations if DATABASE_URL is available
if [ -n "$DATABASE_URL" ]; then
    echo "🔄 Running database migrations..."
    echo "📊 Current migration status:"
    uv run python -m alembic current || echo "Failed to get current migration"
    
    echo "🔄 Upgrading to head..."
    uv run python -m alembic upgrade head || {
        echo "❌ Database migrations failed"
        exit 1
    }
    
    echo "📊 Migration status after upgrade:"
    uv run python -m alembic current || echo "Failed to get current migration"
    
    echo "✅ Database migrations completed"
    
    # Wait for migrations to fully settle and ensure all constraints are applied
    echo "⏳ Waiting 30 seconds for database schema to fully settle..."
    echo "   This ensures all tables, indexes, and constraints are properly created"
    sleep 30
    echo "✅ Migration settling period complete"
else
    echo "⚠️ DATABASE_URL not set, skipping migrations"
fi

# Start the application with proper signal handling
echo "🌐 Starting FastAPI server..."
exec uv run python -m uvicorn src.policy_core.main:app \
    --host ${API_HOST:-0.0.0.0} \
    --port ${API_PORT:-8080} \
    --workers ${WORKERS:-1} \
    --log-level ${LOG_LEVEL:-info} \
    --access-log \
    --use-colors \
    --loop uvloop \
    --http httptools