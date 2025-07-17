#!/bin/bash
set -e

echo "⏳ Waiting for database to be ready after migrations..."

# Maximum wait time (in seconds)
MAX_WAIT=60
WAIT_INTERVAL=2
ELAPSED=0

while [ $ELAPSED -lt $MAX_WAIT ]; do
    echo "🔍 Checking if critical tables exist (attempt $((ELAPSED/WAIT_INTERVAL + 1)))..."
    
    # Check if tables exist
    TABLES_READY=$(uv run python -c "
import asyncio
import asyncpg
import os
import sys

async def check_tables():
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print('ERROR: No DATABASE_URL')
        sys.exit(1)
    
    try:
        conn = await asyncpg.connect(db_url)
        
        # Check critical tables
        critical_tables = ['customers', 'policies', 'quotes', 'users', 'websocket_system_metrics']
        missing_tables = []
        
        for table_name in critical_tables:
            exists = await conn.fetchval(f'''
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table_name}'
                )
            ''')
            
            if not exists:
                missing_tables.append(table_name)
        
        await conn.close()
        
        if missing_tables:
            print(f'MISSING: {','.join(missing_tables)}')
            sys.exit(1)
        else:
            print('SUCCESS')
            sys.exit(0)
        
    except Exception as e:
        print(f'ERROR: {e}')
        sys.exit(1)

asyncio.run(check_tables())
" 2>&1)
    
    if [ "$TABLES_READY" = "SUCCESS" ]; then
        echo "✅ All critical tables are ready!"
        echo "🚀 Proceeding to start the application..."
        exit 0
    else
        echo "⚠️  Tables not ready yet: $TABLES_READY"
        echo "⏳ Waiting $WAIT_INTERVAL seconds before next check..."
        sleep $WAIT_INTERVAL
        ELAPSED=$((ELAPSED + WAIT_INTERVAL))
    fi
done

echo "❌ Timeout waiting for database tables after $MAX_WAIT seconds"
echo "🔍 Final database state check:"
uv run python -c "
import asyncio
import asyncpg
import os

async def final_check():
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print('❌ No DATABASE_URL found')
        return
    
    try:
        conn = await asyncpg.connect(db_url)
        
        tables = await conn.fetch('''
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        ''')
        
        print(f'📋 Found {len(tables)} tables in public schema:')
        for table in tables:
            print(f'   ✓ {table[\"tablename\"]}')
        
        await conn.close()
        
    except Exception as e:
        print(f'❌ Error checking tables: {e}')

asyncio.run(final_check())
"

exit 1