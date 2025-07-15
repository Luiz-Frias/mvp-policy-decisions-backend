#!/usr/bin/env python3
"""Clean up idle database connections."""

import asyncio
import asyncpg
import os


async def cleanup_connections():
    """Clean up idle database connections."""
    url = os.environ.get('DATABASE_PUBLIC_URL', os.environ.get('DATABASE_URL'))
    
    conn = await asyncpg.connect(url)
    try:
        # Check current state
        result = await conn.fetch("""
            SELECT 
                state,
                count(*) as count
            FROM pg_stat_activity 
            GROUP BY state
            ORDER BY count DESC
        """)
        
        print("Current connection states:")
        total = 0
        for row in result:
            state = row["state"] or "null"
            count = row["count"]
            print(f"  {state}: {count}")
            total += count
        
        max_conn = await conn.fetchval("SHOW max_connections")
        print(f"\nTotal: {total}/{max_conn}")
        
        # Find and terminate idle connections
        idle_connections = await conn.fetch("""
            SELECT 
                pid, 
                usename, 
                application_name,
                state,
                query_start,
                state_change,
                EXTRACT(EPOCH FROM (now() - state_change)) as idle_seconds
            FROM pg_stat_activity
            WHERE state = 'idle'
            AND pid != pg_backend_pid()
            ORDER BY state_change
        """)
        
        print(f"\nFound {len(idle_connections)} idle connections")
        
        terminated = 0
        for conn_info in idle_connections:
            idle_time = conn_info["idle_seconds"] or 0
            # Only terminate connections idle for more than 60 seconds
            if idle_time > 60:
                try:
                    await conn.execute(
                        "SELECT pg_terminate_backend($1)",
                        conn_info["pid"]
                    )
                    terminated += 1
                    print(f"  Terminated PID {conn_info['pid']} (idle for {int(idle_time)}s)")
                except Exception as e:
                    print(f"  Failed to terminate PID {conn_info['pid']}: {e}")
        
        print(f"\nTerminated {terminated} connections")
        
        # Check final state
        await asyncio.sleep(1)  # Give it a moment to clean up
        
        final_count = await conn.fetchval("""
            SELECT count(*) FROM pg_stat_activity
        """)
        
        print(f"\nFinal connection count: {final_count}/{max_conn}")
        
        return terminated > 0
        
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(cleanup_connections())