#!/bin/bash
set -e

echo "🔍 SIMPLE MIGRATION - Just alembic, no orchestration"
echo "📅 Migration timestamp: $(date -u +"%Y-%m-%d %H:%M:%S UTC")"

if [ -n "$DATABASE_URL" ]; then
    echo "🚀 Running basic alembic upgrade:"
    uv run alembic upgrade head || {
        echo "❌ Alembic upgrade failed"
        exit 1
    }
    echo "✅ Migration completed!"
    
    # CRITICAL: Verify tables actually exist after migration
    echo "🔍 Verifying tables exist..."
    cat << 'EOF' > /tmp/verify_tables.py
import asyncio
import asyncpg
import os
import sys

async def verify_tables():
    """Verify that critical tables exist after migration."""
    database_url = os.getenv('DATABASE_URL')
    if not database_url:
        print("❌ DATABASE_URL not set")
        sys.exit(1)
    
    try:
        conn = await asyncpg.connect(database_url)
        
        # Check for critical tables
        tables_to_check = ['customers', 'policies', 'quotes', 'claims', 'alembic_version']
        
        for table in tables_to_check:
            exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = $1)", 
                table
            )
            if exists:
                print(f"✅ Table '{table}' exists")
            else:
                print(f"❌ Table '{table}' missing")
                await conn.close()
                sys.exit(1)
        
        # Check alembic version
        version = await conn.fetchval("SELECT version_num FROM alembic_version")
        print(f"✅ Current migration version: {version}")
        
        # Count tables
        count = await conn.fetchval(
            "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public'"
        )
        print(f"✅ Total tables in database: {count}")
        
        await conn.close()
        print("✅ All critical tables verified!")
        
    except Exception as e:
        print(f"❌ Verification failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify_tables())
EOF
    
    uv run python /tmp/verify_tables.py || {
        echo "❌ Table verification failed"
        exit 1
    }
    
    echo "✅ Migration and verification completed successfully!"
else
    echo "⚠️ DATABASE_URL not set"
    exit 1
fi