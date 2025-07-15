#!/usr/bin/env python
"""Run Alembic migrations with detailed debugging."""

import subprocess
import asyncpg
import asyncio
import os
import sys

async def check_database_state(when="before"):
    """Check database state before or after migrations."""
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print('❌ No DATABASE_URL found')
        return
    
    try:
        conn = await asyncpg.connect(db_url)
        
        # Check existing tables
        tables = await conn.fetch('''
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        ''')
        
        print(f'\n📋 Tables {when} migration: {len(tables)}')
        for table in tables:
            print(f'   ✓ {table["tablename"]}')
        
        # If after migration, check alembic version
        if when == "after" and any(t["tablename"] == "alembic_version" for t in tables):
            version = await conn.fetchval('SELECT version_num FROM alembic_version')
            print(f'\n🏷️  Alembic version: {version}')
        
        await conn.close()
        
    except Exception as e:
        print(f'❌ Error checking {when} state: {e}')

async def main():
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print('❌ No DATABASE_URL found')
        sys.exit(1)
    
    print(f"📊 Database URL: {db_url[:50]}...")
    
    # Use database advisory lock to prevent concurrent migrations
    print('\n🔒 Acquiring migration lock...')
    try:
        conn = await asyncpg.connect(db_url)
        
        # Try to acquire advisory lock (blocking, 30 second timeout)
        # Using lock ID 123456 for migrations
        lock_acquired = await conn.fetchval('''
            SELECT pg_try_advisory_lock(123456)
        ''')
        
        if not lock_acquired:
            print('⏳ Another migration process is running, waiting...')
            # Wait for lock with timeout
            await conn.execute('SELECT pg_advisory_lock(123456)')
            print('✅ Migration lock acquired')
        else:
            print('✅ Migration lock acquired immediately')
        
        # Check migration state
        print('\n🧹 Checking migration state...')
        exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'alembic_version'
            )
        ''')
        
        if exists:
            current_version = await conn.fetchval('SELECT version_num FROM alembic_version')
            print(f'ℹ️  Found existing alembic_version with version: {current_version}')
        else:
            print('ℹ️  No alembic_version table found - fresh database')
        
        await conn.close()
        
    except Exception as e:
        print(f'⚠️  Error checking migrations: {e}')
    
    # Check initial state
    await check_database_state("before")
    
    # Run migrations using subprocess to avoid async conflicts
    print('\n🔄 Running Alembic migrations...')
    
    # First show current state
    print('\n📍 Current revision:')
    result = subprocess.run(
        ["uv", "run", "python", "-m", "alembic", "current"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print(f"⚠️  Stderr: {result.stderr}")
    
    # Show what will be upgraded
    print('\n📜 Checking upgrade path:')
    result = subprocess.run(
        ["uv", "run", "python", "-m", "alembic", "history"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    
    # Run the actual upgrade
    print('\n🚀 Upgrading to head...')
    result = subprocess.run(
        ["uv", "run", "python", "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True
    )
    
    print(result.stdout)
    if result.stderr:
        print(f"⚠️  Stderr: {result.stderr}")
    
    if result.returncode != 0:
        print(f'\n❌ Migration failed with exit code: {result.returncode}')
        sys.exit(1)
    
    print('\n✅ Migrations completed!')
    
    # Check final state
    await check_database_state("after")
    
    # Release the migration lock
    print('\n🔓 Releasing migration lock...')
    try:
        conn = await asyncpg.connect(db_url)
        await conn.execute('SELECT pg_advisory_unlock(123456)')
        await conn.close()
        print('✅ Migration lock released')
    except Exception as e:
        print(f'⚠️  Error releasing lock: {e}')

if __name__ == "__main__":
    asyncio.run(main())