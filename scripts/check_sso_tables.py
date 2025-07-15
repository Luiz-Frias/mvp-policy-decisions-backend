#!/usr/bin/env python3
"""Check if SSO tables exist in the database."""

import asyncio
import sys
from pathlib import Path

# Add project root and src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from policy_core.core.database import Database
from policy_core.core.config import get_settings


async def check_tables():
    """Check which SSO-related tables exist."""
    db = Database()
    
    try:
        await db.connect()
        
        # List of tables to check
        tables_to_check = [
            'sso_provider_configs',
            'sso_providers',  # Old name
            'user_sso_links',
            'sso_group_mappings',
            'auth_logs',
            'users',
            'admin_users'
        ]
        
        print("Checking for SSO-related tables:")
        print("=" * 40)
        
        for table in tables_to_check:
            exists = await db.fetchval(f"""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = '{table}'
                )
            """)
            
            status = "✅ EXISTS" if exists else "❌ NOT FOUND"
            print(f"  {table:30} {status}")
        
        # Check if migrations table exists
        print("\nChecking Alembic migrations:")
        print("=" * 40)
        
        alembic_exists = await db.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables 
                WHERE table_schema = 'public' 
                AND table_name = 'alembic_version'
            )
        """)
        
        if alembic_exists:
            current_revision = await db.fetchval("SELECT version_num FROM alembic_version")
            print(f"  Current revision: {current_revision}")
        else:
            print("  ❌ Alembic version table not found")
        
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(check_tables())