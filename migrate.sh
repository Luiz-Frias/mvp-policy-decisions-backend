#!/bin/bash
set -e

echo "🚀 Running database migrations BEFORE starting the app..."
echo "📅 Migration timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

# Doppler provides DATABASE_URL in uppercase
if [ -n "$DATABASE_URL" ]; then
    echo "🔄 Running database migrations..."
    
    # First, clean up any stuck migration state
    echo "🧹 Cleaning migration state..."
    uv run python -c "
import asyncio
import asyncpg
import os

async def reset_migrations():
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print('❌ No DATABASE_URL found')
        return
    
    try:
        conn = await asyncpg.connect(db_url)
        
        # Check if alembic_version exists
        exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'alembic_version'
            )
        ''')
        
        if exists:
            print('🗑️  Dropping alembic_version table to force fresh migration...')
            await conn.execute('DROP TABLE alembic_version CASCADE')
            print('✅ alembic_version table dropped')
        else:
            print('ℹ️  No alembic_version table found')
        
        await conn.close()
        
    except Exception as e:
        print(f'⚠️  Error resetting migrations: {e}')

asyncio.run(reset_migrations())
"
    
    echo "📊 Current migration status:"
    uv run python -m alembic current || echo "No current migration"
    
    echo "🔄 Upgrading to head..."
    uv run python -m alembic upgrade head || {
        echo "❌ Database migrations failed"
        exit 1
    }
    
    echo "📊 Migration status after upgrade:"
    uv run python -m alembic current
    
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
        
        # Check if critical tables exist
        critical_tables = ['customers', 'policies', 'quotes', 'users']
        for table_name in critical_tables:
            exists = await conn.fetchval(f'''
                SELECT EXISTS (
                    SELECT 1 
                    FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table_name}'
                )
            ''')
            
            if exists:
                print(f'✅ {table_name} table exists')
            else:
                print(f'❌ {table_name} table NOT FOUND')
        
        await conn.close()
        
    except Exception as e:
        print(f'❌ Error checking tables: {e}')

asyncio.run(check_tables())
"
    
    echo "✅ All migrations completed successfully!"
else
    echo "⚠️ DATABASE_URL not set, skipping migrations"
    exit 1
fi