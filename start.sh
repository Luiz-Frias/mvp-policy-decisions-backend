#!/bin/bash
set -e

echo "🚀 Starting MVP Policy Decision Backend - Production"
echo "Environment: $APP_ENV"
echo "API Port: $API_PORT"
echo "WebSocket Port: $WEBSOCKET_PORT"

# Debug: Show environment variables
echo "📊 Environment check:"
echo "  database_url: ${database_url:-NOT SET}"
echo "  DATABASE_URL: ${DATABASE_URL:-NOT SET}"

# Run database migrations if database_url is available
if [ -n "$database_url" ]; then
    echo "🔄 Running database migrations..."
    export DATABASE_URL=$database_url
    uv run alembic upgrade head || {
        echo "❌ Database migrations failed"
        exit 1
    }
    echo "✅ Database migrations completed"
else
    echo "⚠️ database_url not set, skipping migrations"
fi

# Start the application with proper signal handling
echo "🌐 Starting FastAPI server..."
export DATABASE_URL=$database_url
exec uv run uvicorn src.policy_core.main:app \
    --host ${API_HOST:-0.0.0.0} \
    --port ${API_PORT:-8080} \
    --workers ${WORKERS:-1} \
    --log-level ${LOG_LEVEL:-info} \
    --access-log \
    --use-colors \
    --loop uvloop \
    --http httptools