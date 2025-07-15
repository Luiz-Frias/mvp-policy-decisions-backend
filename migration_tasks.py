#!/usr/bin/env python
"""Celery tasks for database migrations."""

from celery import current_task
from celery_app import app
import subprocess
import asyncpg
import asyncio
import os
import sys

@app.task(bind=True, name='migration_tasks.run_migrations')
def run_migrations(self):
    """Run database migrations as a Celery task.
    
    This ensures only ONE migration runs across all Railway containers.
    """
    task_id = self.request.id
    print(f'🚀 Migration task {task_id} started')
    
    # Update task state
    self.update_state(
        state='PROGRESS',
        meta={'status': 'Starting migration process...'}
    )
    
    try:
        # Run the migration process
        result = asyncio.run(run_migration_process())
        
        if result:
            print(f'✅ Migration task {task_id} completed successfully')
            return {
                'status': 'SUCCESS',
                'message': 'All migrations completed successfully'
            }
        else:
            print(f'❌ Migration task {task_id} failed')
            return {
                'status': 'FAILED',
                'message': 'Migration process failed'
            }
            
    except Exception as e:
        print(f'💥 Migration task {task_id} crashed: {e}')
        return {
            'status': 'ERROR',
            'message': f'Migration task crashed: {str(e)}'
        }

async def run_migration_process():
    """Actually run the migration process."""
    db_url = os.environ.get('DATABASE_URL', '')
    if not db_url:
        print('❌ No DATABASE_URL found')
        return False
    
    print(f"📊 Database URL: {db_url[:50]}...")
    
    try:
        # Check if migrations are already complete
        conn = await asyncpg.connect(db_url)
        
        # Check if quotes table exists (indicates complete migration)
        quotes_exists = await conn.fetchval('''
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'quotes'
            )
        ''')
        
        if quotes_exists:
            print('✅ Migrations already complete - quotes table exists')
            await conn.close()
            return True
        
        # Check current state
        print('🔍 Checking current migration state...')
        tables = await conn.fetch('''
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        ''')
        
        print(f'📋 Found {len(tables)} tables before migration:')
        for table in tables:
            print(f'   ✓ {table["tablename"]}')
        
        await conn.close()
        
        # Run alembic migrations
        print('\n🔄 Running Alembic migrations...')
        
        # Show current revision
        print('📍 Current revision:')
        result = subprocess.run(
            ["uv", "run", "python", "-m", "alembic", "current"],
            capture_output=True,
            text=True,
            cwd="/app"
        )
        print(result.stdout)
        if result.stderr:
            print(f"⚠️  Stderr: {result.stderr}")
        
        # Run upgrade to head
        print('🚀 Upgrading to head...')
        result = subprocess.run(
            ["uv", "run", "python", "-m", "alembic", "upgrade", "head"],
            capture_output=True,
            text=True,
            cwd="/app"
        )
        
        print(result.stdout)
        if result.stderr:
            print(f"⚠️  Stderr: {result.stderr}")
        
        if result.returncode != 0:
            print(f'❌ Migration failed with exit code: {result.returncode}')
            return False
        
        # Verify migrations completed
        conn = await asyncpg.connect(db_url)
        
        tables = await conn.fetch('''
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename
        ''')
        
        print(f'📋 Found {len(tables)} tables after migration:')
        for table in tables:
            print(f'   ✓ {table["tablename"]}')
        
        # Check for critical tables
        critical_tables = ['customers', 'policies', 'quotes', 'users']
        missing_tables = []
        
        table_names = [t["tablename"] for t in tables]
        for table_name in critical_tables:
            if table_name not in table_names:
                missing_tables.append(table_name)
        
        await conn.close()
        
        if missing_tables:
            print(f'❌ Missing critical tables: {missing_tables}')
            return False
        
        print('✅ All critical tables created successfully!')
        return True
        
    except Exception as e:
        print(f'💥 Migration process failed: {e}')
        return False

# Helper function to check task status
def get_migration_status():
    """Get the status of the current migration task."""
    # Check if there's an active migration task
    active_tasks = app.control.inspect().active()
    if active_tasks:
        for worker, tasks in active_tasks.items():
            for task in tasks:
                if task['name'] == 'migration_tasks.run_migrations':
                    return 'RUNNING', task['id']
    
    return 'IDLE', None