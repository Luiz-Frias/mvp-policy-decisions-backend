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
        max_wait = 120  # 2 minute timeout for multiple containers
        wait_time = 0
        while wait_time < max_wait:
            try:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                print('✅ Migration lock acquired')
                break
            except BlockingIOError:
                print('⏳ Another migration process is running, waiting...')
                time.sleep(5)  # Longer wait between attempts
                wait_time += 5
        else:
            print('❌ Timeout waiting for migration lock')
            return False
        
        # Add a small delay to let any previous transactions commit
        print('🕐 Waiting for database transaction isolation...')
        time.sleep(3)
        
        # Run the actual migration process
        return await run_migrations_process()

async def run_migrations_process():
    db_url = os.environ.get('DATABASE_URL', '')
    
    # Use PostgreSQL advisory lock to ensure only ONE container runs migrations
    print('\n🔒 Acquiring PostgreSQL advisory lock for migrations...')
    try:
        conn = await asyncpg.connect(db_url)
        
        # Try to acquire advisory lock (key: 123456789)
        # This is database-level locking that works across containers
        lock_acquired = await conn.fetchval('SELECT pg_try_advisory_lock(123456789)')
        
        if not lock_acquired:
            print('⏳ Another container is running migrations, waiting...')
            await conn.close()
            
            # Wait and check if migrations completed
            import asyncio
            for i in range(24):  # Wait up to 2 minutes
                await asyncio.sleep(5)
                try:
                    conn = await asyncpg.connect(db_url)
                    # Check if migrations are complete by looking for quotes table
                    quotes_exists = await conn.fetchval('''
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_schema = 'public' 
                            AND table_name = 'quotes'
                        )
                    ''')
                    await conn.close()
                    if quotes_exists:
                        print('✅ Migrations completed by another container')
                        return True
                except:
                    pass
            
            print('❌ Timeout waiting for migrations from another container')
            return False
        
        print('✅ Advisory lock acquired - this container will run migrations')
        
        # Check current migration state
        print('\n🧹 Checking migration state...')
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
                    print(f'ℹ️  Current version: {current_version} - checking if upgrade needed...')
                else:
                    print('⚠️  alembic_version table exists but has NULL version')
            except:
                print('⚠️  alembic_version table exists but empty')
        else:
            print('ℹ️  No alembic_version table found - fresh database')
        
        # Don't close connection yet - keep the advisory lock
        
    except Exception as e:
        print(f'⚠️  Error checking migrations: {e}')
        return False
    
    try:
        # Check initial state
        await check_database_state("before")
        
        # Close the connection before running subprocess commands
        await conn.close()
        
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
            return False
        
        print('\n✅ Migrations completed!')
        
        # Check final state
        await check_database_state("after")
        
        return True
        
    finally:
        # Always release the advisory lock
        try:
            conn = await asyncpg.connect(db_url)
            await conn.fetchval('SELECT pg_advisory_unlock(123456789)')
            await conn.close()
            print('🔓 PostgreSQL advisory lock released')
        except Exception as e:
            print(f'⚠️  Error releasing lock: {e}')

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
    
    print('✅ Migration process completed successfully')
    print('🔓 File lock will be automatically released')

if __name__ == "__main__":
    asyncio.run(main())