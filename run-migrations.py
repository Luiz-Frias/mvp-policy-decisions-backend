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

async def run_migrations_with_lock():
    # Use file-based lock to prevent concurrent migrations
    import fcntl
    import time
    
    print('\n🔒 Acquiring file-based migration lock...')
    with open('/tmp/migration.lock', 'w') as lock_file:
        # Try to acquire exclusive lock with timeout
        max_wait = 60  # 1 minute timeout
        wait_time = 0
        while wait_time < max_wait:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                print('✅ Migration lock acquired')
                break
            except BlockingIOError:
                print('⏳ Another migration process is running, waiting...')
                time.sleep(2)
                wait_time += 2
        else:
            print('❌ Timeout waiting for migration lock')
            return False
        
        # Run the actual migration process
        return await run_migrations_process()

async def run_migrations_process():
    db_url = os.environ.get('DATABASE_URL', '')
    
    # Check migration state
    print('\n🧹 Checking migration state...')
    try:
        conn = await asyncpg.connect(db_url)
        exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'alembic_version'
            )
        ''')
        
        if exists:
            try:
                current_version = await conn.fetchval('SELECT version_num FROM alembic_version')
                print(f'ℹ️  Found existing alembic_version with version: {current_version}')
                if current_version:
                    print('🎯 Migrations already complete, skipping')
                    await conn.close()
                    return True
            except:
                print('⚠️  alembic_version table exists but empty')
        else:
            print('ℹ️  No alembic_version table found - fresh database')
        
        await conn.close()
        
    except Exception as e:
        print(f'⚠️  Error checking migrations: {e}')
        return False

async def main():
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print('❌ No DATABASE_URL found')
        sys.exit(1)
    
    print(f"📊 Database URL: {db_url[:50]}...")
    
    # Run migrations with file lock
    success = await run_migrations_with_lock()
    if not success:
        print('❌ Migration process failed')
        sys.exit(1)
    
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
    
    print('✅ Migration process completed successfully')
    print('🔓 File lock will be automatically released')

if __name__ == "__main__":
    asyncio.run(main())