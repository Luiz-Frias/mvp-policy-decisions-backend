#!/usr/bin/env python
"""Celery app for handling async tasks like migrations."""

from celery import Celery
import os

# Redis URL from Doppler
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# Create Celery app
app = Celery(
    'migration_queue',
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=['migration_tasks']
)

# Celery configuration
app.conf.update(
    # Task routing
    task_routes={
        'migration_tasks.run_migrations': {'queue': 'migrations'},
    },
    
    # Only allow one migration task at a time
    task_annotations={
        'migration_tasks.run_migrations': {
            'rate_limit': '1/m',  # Only 1 migration per minute max
        }
    },
    
    # Task settings
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='UTC',
    enable_utc=True,
    
    # Ensure tasks don't run concurrently
    worker_concurrency=1,
    worker_prefetch_multiplier=1,
    
    # Task timeout
    task_time_limit=600,  # 10 minutes max
    task_soft_time_limit=540,  # 9 minute soft limit
)

if __name__ == '__main__':
    app.start()