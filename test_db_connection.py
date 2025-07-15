#!/usr/bin/env python3
"""Test database connection to diagnose hanging issue."""

import asyncio
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.policy_core.core.database_enhanced import Database
from src.policy_core.core.config import get_settings


async def test_connection():
    """Test database connection."""
    print("Testing database connection...")
    
    settings = get_settings()
    print(f"Database URL: {settings.effective_database_url[:50]}...")
    
    db = Database()
    
    try:
        print("Attempting to connect...")
        await db.connect()
        print("✅ Connection successful!")
        
        # Test a simple query
        print("Testing query...")
        result = await db.fetchval("SELECT 1")
        print(f"Query result: {result}")
        
        # Check pool stats
        stats = await db.get_pool_stats()
        print(f"Pool stats: size={stats.size}, free={stats.free_size}")
        
    except Exception as e:
        print(f"❌ Connection failed: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("Disconnecting...")
        await db.disconnect()
        print("Disconnected.")


if __name__ == "__main__":
    asyncio.run(test_connection())