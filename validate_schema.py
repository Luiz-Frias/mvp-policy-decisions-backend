#!/usr/bin/env python3
"""Validate that all referenced tables will be created by migrations."""

import re
import os
from pathlib import Path

def find_table_references(code_dir: Path) -> set[str]:
    """Find all table references in SQL queries."""
    table_refs = set()
    
    sql_patterns = [
        r'FROM\s+(\w+)',
        r'JOIN\s+(\w+)',
        r'UPDATE\s+(\w+)',
        r'INSERT\s+INTO\s+(\w+)',
        r'DELETE\s+FROM\s+(\w+)',
    ]
    
    for py_file in code_dir.rglob('*.py'):
        try:
            with open(py_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            for pattern in sql_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    if match not in ['VALUES', 'SELECT', 'WHERE', 'ORDER', 'GROUP']:
                        table_refs.add(match.lower())
        except Exception as e:
            print(f"Error reading {py_file}: {e}")
    
    return table_refs

def find_created_tables(migrations_dir: Path) -> set[str]:
    """Find all tables created by migrations."""
    created_tables = set()
    
    for migration_file in migrations_dir.glob('*.py'):
        try:
            with open(migration_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Look for create_table calls
            table_matches = re.findall(r'create_table\s*\(\s*["\']([^"\']+)["\']', content)
            for table in table_matches:
                created_tables.add(table.lower())
                
            # Look for direct SQL table creation
            sql_matches = re.findall(r'CREATE\s+TABLE\s+(\w+)', content, re.IGNORECASE)
            for table in sql_matches:
                created_tables.add(table.lower())
                
        except Exception as e:
            print(f"Error reading {migration_file}: {e}")
    
    return created_tables

def main():
    """Main validation function."""
    project_root = Path(__file__).parent
    src_dir = project_root / 'src'
    migrations_dir = project_root / 'alembic' / 'versions'
    
    print("🔍 Analyzing table references in source code...")
    referenced_tables = find_table_references(src_dir)
    
    print("🔍 Analyzing tables created by migrations...")
    created_tables = find_created_tables(migrations_dir)
    
    print(f"\n📊 Found {len(referenced_tables)} referenced tables:")
    for table in sorted(referenced_tables):
        print(f"  - {table}")
    
    print(f"\n📊 Found {len(created_tables)} created tables:")
    for table in sorted(created_tables):
        print(f"  - {table}")
    
    print("\n✅ Validation Results:")
    missing_tables = referenced_tables - created_tables
    
    if missing_tables:
        print(f"❌ Missing tables: {sorted(missing_tables)}")
        return 1
    else:
        print("✅ All referenced tables are created by migrations!")
        
    # Check for potential issues
    extra_tables = created_tables - referenced_tables
    if extra_tables:
        print(f"ℹ️  Extra tables (not referenced in code): {sorted(extra_tables)}")
    
    return 0

if __name__ == '__main__':
    exit(main())