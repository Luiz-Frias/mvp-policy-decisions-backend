#!/usr/bin/env python
"""Migration runner using Celery queue."""

import sys
import time
import os
from celery_app import app
from migration_tasks import run_migrations, get_migration_status

def main():
    """Run migrations through Celery queue."""
    print('🚀 Starting Celery-based migration process...')
    
    # Check if Redis is available
    try:
        from redis import Redis
        redis_url = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
        redis_client = Redis.from_url(redis_url)
        redis_client.ping()
        print('✅ Redis connection successful')
    except Exception as e:
        print(f'❌ Redis connection failed: {e}')
        print('⚠️  Falling back to direct migration...')
        # Fallback to direct migration if Redis unavailable
        import asyncio
        from migration_tasks import run_migration_process
        result = asyncio.run(run_migration_process())
        sys.exit(0 if result else 1)
    
    # Check if migration is already running
    status, task_id = get_migration_status()
    if status == 'RUNNING':
        print(f'⏳ Migration already running in task {task_id}, waiting...')
        # Wait for existing task to complete
        task_result = app.AsyncResult(task_id)
        result = task_result.get(timeout=600)  # 10 minute timeout
        print(f'✅ Existing migration completed: {result}')
        sys.exit(0 if result.get('status') == 'SUCCESS' else 1)
    
    # Submit new migration task
    print('📤 Submitting migration task to queue...')
    task = run_migrations.delay()
    print(f'📋 Migration task submitted: {task.id}')
    
    # Wait for task completion
    print('⏳ Waiting for migration to complete...')
    try:
        result = task.get(timeout=600)  # 10 minute timeout
        print(f'📊 Migration result: {result}')
        
        if result.get('status') == 'SUCCESS':
            print('✅ Migrations completed successfully!')
            sys.exit(0)
        else:
            print('❌ Migrations failed!')
            sys.exit(1)
            
    except Exception as e:
        print(f'💥 Migration task failed: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()