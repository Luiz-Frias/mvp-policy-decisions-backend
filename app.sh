#!/bin/bash
set -e

echo "🌐 Starting FastAPI server..."
echo "📅 Startup timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "Environment: $APP_ENV"
echo "API Port: ${PORT:-${API_PORT:-8000}}"
echo "WebSocket Port: ${WEBSOCKET_PORT:-8001}"

# Start the application with proper signal handling
exec uv run python -m uvicorn src.policy_core.main:app \
    --host ${API_HOST:-0.0.0.0} \
    --port 8000 \
    --workers ${WORKERS:-1} \
    --log-level ${LOG_LEVEL:-info} \
    --access-log \
    --use-colors \
    --loop uvloop \
    --http httptools