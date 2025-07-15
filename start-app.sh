#!/bin/bash
set -e

echo "🚀 Starting application (migrations already completed by migrator service)"
echo "📅 App startup timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

# Wait a moment to ensure migrations are definitely done
echo "⏳ Waiting 5 seconds for migrator service to complete..."
sleep 5

# Check if database is ready
echo "🔍 Verifying database is ready..."
if [ -n "$DATABASE_URL" ]; then
    # Quick database connectivity test
    uv run python -c "
import asyncio
import asyncpg
import os
import sys

async def check_db():
    try:
        conn = await asyncpg.connect(os.environ['DATABASE_URL'])
        # Check if quotes table exists (indicates migrations completed)
        exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'quotes'
            )
        ''')
        await conn.close()
        
        if exists:
            print('✅ Database ready - quotes table exists')
            sys.exit(0)
        else:
            print('❌ Database not ready - quotes table missing')
            sys.exit(1)
    except Exception as e:
        print(f'❌ Database check failed: {e}')
        sys.exit(1)

asyncio.run(check_db())
    " || {
        echo "❌ Database not ready, cannot start app"
        exit 1
    }
fi

echo "🚀 Starting FastAPI application..."
exec uv run python -m pd_prime_demo.main