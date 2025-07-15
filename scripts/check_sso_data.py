#!/usr/bin/env python3
"""Check SSO table contents."""

import asyncio
import sys
from pathlib import Path

# Add project root and src to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from policy_core.core.database import Database
from policy_core.core.config import get_settings


async def check_sso_data():
    """Check SSO table contents."""
    db = Database()
    
    try:
        await db.connect()
        
        # Check sso_providers table structure
        print("Table: sso_providers")
        print("=" * 60)
        
        columns = await db.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'sso_providers'
            ORDER BY ordinal_position
        """)
        
        if columns:
            print("Columns:")
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"  - {col['column_name']:30} {col['data_type']:20} {nullable}")
            
            # Check data
            count = await db.fetchval("SELECT COUNT(*) FROM sso_providers")
            print(f"\nRow count: {count}")
            
            if count > 0:
                print("\nData:")
                rows = await db.fetch("SELECT * FROM sso_providers LIMIT 5")
                for row in rows:
                    print(f"  Provider: {row.get('provider', 'N/A')}")
        else:
            print("  Table exists but no column info available")
        
        print("\n" + "="*60)
        
        # Check sso_provider_configs table
        print("\nTable: sso_provider_configs")
        print("=" * 60)
        
        columns = await db.fetch("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'sso_provider_configs'
            ORDER BY ordinal_position
        """)
        
        if columns:
            print("Columns:")
            for col in columns:
                nullable = "NULL" if col['is_nullable'] == 'YES' else "NOT NULL"
                print(f"  - {col['column_name']:30} {col['data_type']:20} {nullable}")
        
        config_count = await db.fetchval("SELECT COUNT(*) FROM sso_provider_configs")
        print(f"\nRow count: {config_count}")
        
        if config_count > 0:
            configs = await db.fetch("""
                SELECT provider_name, provider_type, is_enabled 
                FROM sso_provider_configs
            """)
            for cfg in configs:
                status = "✅" if cfg['is_enabled'] else "❌"
                print(f"  {status} {cfg['provider_name']:10} ({cfg['provider_type']})")
        
    finally:
        await db.disconnect()


if __name__ == "__main__":
    asyncio.run(check_sso_data())