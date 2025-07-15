#!/bin/bash
set -e

echo "🚀 Starting MVP Policy Decision Backend - Production"
echo "📅 Deployment timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"
echo "🔖 Git commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'unknown')"
echo "Environment: $APP_ENV"
echo "API Port: $API_PORT"
echo "WebSocket Port: $WEBSOCKET_PORT"

# Debug: Show environment variables
echo "📊 Environment check:"
echo "  DATABASE_URL: ${DATABASE_URL:-NOT SET}"
echo "  database_url: ${database_url:-NOT SET}"
echo "  PATH: $PATH"
echo "  Which uv: $(which uv || echo 'uv not found in PATH')"
echo "  uv location: $(ls -la /bin/uv 2>&1 || echo '/bin/uv not found')"

# Test what Pydantic Settings actually sees
echo "🔍 Testing Pydantic Settings resolution:"
uv run python -c "
import os
print(f'  OS env DATABASE_URL: {os.environ.get(\"DATABASE_URL\", \"NOT SET\")}')
print(f'  OS env database_url: {os.environ.get(\"database_url\", \"NOT SET\")}')

# Import settings
from src.policy_core.core.config import get_settings
settings = get_settings()
print(f'  Settings.database_url: {settings.database_url[:50]}...' if len(settings.database_url) > 50 else f'  Settings.database_url: {settings.database_url}')
print(f'  Settings.effective_database_url: {settings.effective_database_url[:50]}...' if len(settings.effective_database_url) > 50 else f'  Settings.effective_database_url: {settings.effective_database_url}')
"

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
    
    # Verify tables actually exist
    echo "🔍 Verifying database tables..."
    uv run python -c "
import asyncio
import asyncpg
import os

async def check_tables():
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print('❌ No DATABASE_URL found')
        return
    
    try:
        conn = await asyncpg.connect(db_url)
        
        # Check what tables exist
        tables = await conn.fetch('''
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        ''')
        
        print(f'📋 Found {len(tables)} tables in public schema:')
        for table in tables:
            print(f'   ✓ {table[\"tablename\"]}')
        
        # Check if quotes table specifically exists
        quotes_exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1 
                FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'quotes'
            )
        ''')
        
        if quotes_exists:
            print('✅ quotes table exists')
            # Check column count
            col_count = await conn.fetchval('''
                SELECT COUNT(*) 
                FROM information_schema.columns 
                WHERE table_schema = 'public' 
                AND table_name = 'quotes'
            ''')
            print(f'   → Has {col_count} columns')
        else:
            print('❌ quotes table NOT FOUND')
        
        await conn.close()
        
    except Exception as e:
        print(f'❌ Error checking tables: {e}')

asyncio.run(check_tables())
"
    
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