#!/usr/bin/env python3
"""Validate migration files for common issues and completeness.

This script validates migration files without requiring a database connection.
It checks for syntax errors, missing functions, proper revision sequences, and more.
"""

import ast
import re
from pathlib import Path
from typing import Any


def extract_migration_info(file_path: Path) -> dict[str, Any]:
    """Extract migration information from a migration file."""
    with open(file_path) as f:
        content = f.read()

    info = {
        "file_path": file_path,
        "revision": None,
        "down_revision": None,
        "has_upgrade": False,
        "has_downgrade": False,
        "tables_created": [],
        "tables_dropped": [],
        "indexes_created": [],
        "constraints_created": [],
        "functions_created": [],
        "triggers_created": [],
    }

    # Extract revision info using regex (more reliable than AST for this purpose)
    revision_match = re.search(r'revision:\s*str\s*=\s*["\']([^"\']+)["\']', content)
    if revision_match:
        info["revision"] = revision_match.group(1)

    # Handle both quoted and None values for down_revision - try multiple patterns
    patterns = [
        r'down_revision:\s*str\s*\|\s*None\s*=\s*["\']([^"\']+)["\']',  # str | None = "001"
        r'down_revision:\s*str\s*=\s*["\']([^"\']+)["\']',  # str = "001"
        r'down_revision\s*=\s*["\']([^"\']+)["\']',  # = "001"
    ]

    down_revision_found = False
    for pattern in patterns:
        down_revision_match = re.search(pattern, content)
        if down_revision_match:
            info["down_revision"] = down_revision_match.group(1)
            down_revision_found = True
            break

    if not down_revision_found:
        # Check for None values
        none_patterns = [
            r"down_revision:\s*str\s*\|\s*None\s*=\s*None",
            r"down_revision:\s*str\s*=\s*None",
            r"down_revision\s*=\s*None",
        ]
        for pattern in none_patterns:
            if re.search(pattern, content):
                info["down_revision"] = None
                break

    # Check for function presence
    info["has_upgrade"] = "def upgrade(" in content
    info["has_downgrade"] = "def downgrade(" in content

    # Parse the Python AST for detailed analysis
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if node.name == "upgrade":
                    info.update(analyze_migration_function(node, "upgrade"))
                elif node.name == "downgrade":
                    info.update(analyze_migration_function(node, "downgrade"))
    except SyntaxError as e:
        info["error"] = f"Syntax error: {e}"

    return info


def analyze_migration_function(
    node: ast.FunctionDef, func_type: str
) -> dict[str, list[str]]:
    """Analyze an upgrade or downgrade function for database operations."""
    result = {
        f"tables_{'created' if func_type == 'upgrade' else 'dropped'}": [],
        f"indexes_{'created' if func_type == 'upgrade' else 'dropped'}": [],
        f"constraints_{'created' if func_type == 'upgrade' else 'dropped'}": [],
        f"functions_{'created' if func_type == 'upgrade' else 'dropped'}": [],
        f"triggers_{'created' if func_type == 'upgrade' else 'dropped'}": [],
    }

    for stmt in ast.walk(node):
        if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Attribute):
            if stmt.func.attr == "create_table" and func_type == "upgrade":
                if stmt.args and isinstance(stmt.args[0], ast.Constant):
                    result["tables_created"].append(stmt.args[0].value)
            elif stmt.func.attr == "drop_table" and func_type == "downgrade":
                if stmt.args and isinstance(stmt.args[0], ast.Constant):
                    result["tables_dropped"].append(stmt.args[0].value)
            elif stmt.func.attr == "create_index" and func_type == "upgrade":
                if stmt.args and isinstance(stmt.args[0], ast.Constant):
                    result["indexes_created"].append(stmt.args[0].value)
            elif stmt.func.attr == "execute":
                # Look for CREATE/DROP statements in execute calls
                if stmt.args and isinstance(stmt.args[0], ast.Constant):
                    sql = stmt.args[0].value.upper()
                    if "CREATE FUNCTION" in sql and func_type == "upgrade":
                        # Extract function name
                        match = re.search(r"CREATE.*FUNCTION\s+(\w+)", sql)
                        if match:
                            result["functions_created"].append(match.group(1))
                    elif "CREATE TRIGGER" in sql and func_type == "upgrade":
                        # Extract trigger name
                        match = re.search(r"CREATE TRIGGER\s+(\w+)", sql)
                        if match:
                            result["triggers_created"].append(match.group(1))

    return result


def validate_migration_sequence(migrations: list[dict[str, Any]]) -> list[str]:
    """Validate the migration sequence is correct."""
    errors = []

    # Sort by filename to check revision sequence
    migrations.sort(key=lambda m: m["file_path"].name)

    # Check for missing revisions
    revisions = {m["revision"] for m in migrations if m["revision"]}
    down_revisions = {m["down_revision"] for m in migrations if m["down_revision"]}

    # Find the base migration (no down_revision)
    base_migrations = [m for m in migrations if not m["down_revision"]]
    if len(base_migrations) != 1:
        errors.append(
            f"Expected exactly 1 base migration, found {len(base_migrations)}"
        )

    # Check that each down_revision exists
    for migration in migrations:
        if migration["down_revision"] and migration["down_revision"] not in revisions:
            errors.append(
                f"Migration {migration['file_path'].name} references non-existent "
                f"down_revision '{migration['down_revision']}'"
            )

    # Check for circular dependencies
    revision_graph = {}
    for migration in migrations:
        rev = migration["revision"]
        down_rev = migration["down_revision"]
        if rev:
            revision_graph[rev] = down_rev

    if has_circular_dependency(revision_graph):
        errors.append("Circular dependency detected in migration sequence")

    return errors


def has_circular_dependency(graph: dict[str, str | None]) -> bool:
    """Check for circular dependencies in migration graph."""
    visited = set()
    rec_stack = set()

    def visit(node: str | None) -> bool:
        if node is None:
            return False
        if node in rec_stack:
            return True
        if node in visited:
            return False

        visited.add(node)
        rec_stack.add(node)

        if visit(graph.get(node)):
            return True

        rec_stack.remove(node)
        return False

    for node in graph:
        if visit(node):
            return True
    return False


def validate_table_operations(migrations: list[dict[str, Any]]) -> list[str]:
    """Validate table creation and dropping operations."""
    errors = []

    all_created_tables = set()
    all_dropped_tables = set()

    for migration in migrations:
        # Check upgrade function
        created = migration.get("tables_created", [])
        all_created_tables.update(created)

        # Check downgrade function
        dropped = migration.get("tables_dropped", [])
        all_dropped_tables.update(dropped)

        # Validate that downgrade reverses upgrade
        if set(created) != set(dropped):
            errors.append(
                f"Migration {migration['file_path'].name}: "
                f"Tables created in upgrade ({created}) don't match "
                f"tables dropped in downgrade ({dropped})"
            )

    return errors


def check_required_tables() -> list[str]:
    """Check that all required tables for Wave 2 are present."""
    required_tables = {
        # Core tables
        "customers",
        "policies",
        "claims",
        "users",
        # Quote system
        "quotes",
        # Rating engine
        "rate_tables",
        "discount_rules",
        "surcharge_rules",
        "territory_factors",
        # Security & compliance
        "sso_providers",
        "oauth2_clients",
        "user_mfa_settings",
        "audit_logs",
        # Real-time & analytics
        "websocket_connections",
        "analytics_events",
        # Admin system
        "admin_users",
        "admin_roles",
        "admin_permissions",
        "system_settings",
        "admin_activity_logs",
        "admin_dashboards",
        "admin_rate_approvals",
    }

    # Get all migration files
    versions_dir = Path("alembic/versions")
    migration_files = list(versions_dir.glob("*.py"))

    migrations = []
    for file_path in migration_files:
        info = extract_migration_info(file_path)
        if "error" not in info:
            migrations.append(info)

    # Collect all tables that will be created
    all_tables = set()
    for migration in migrations:
        all_tables.update(migration.get("tables_created", []))

    missing_tables = required_tables - all_tables
    errors = []

    if missing_tables:
        errors.append(f"Missing required tables: {missing_tables}")

    extra_tables = all_tables - required_tables
    if extra_tables:
        print(f"ℹ️ Additional tables found: {extra_tables}")

    return errors


def validate_migration_files():
    """Validate all migration files."""
    print("🔍 Validating migration files...")
    print("=" * 60)

    versions_dir = Path("alembic/versions")
    if not versions_dir.exists():
        print("❌ Alembic versions directory not found!")
        return False

    migration_files = list(versions_dir.glob("*.py"))
    if not migration_files:
        print("❌ No migration files found!")
        return False

    print(f"📁 Found {len(migration_files)} migration files")

    migrations = []
    errors = []

    # Parse each migration file
    for file_path in migration_files:
        print(f"📄 Parsing {file_path.name}...")
        info = extract_migration_info(file_path)

        if "error" in info:
            errors.append(f"{file_path.name}: {info['error']}")
            continue

        migrations.append(info)

        # Validate individual file
        if not info["revision"]:
            errors.append(f"{file_path.name}: Missing revision ID")

        if not info["has_upgrade"]:
            errors.append(f"{file_path.name}: Missing upgrade() function")

        if not info["has_downgrade"]:
            errors.append(f"{file_path.name}: Missing downgrade() function")

        # Report what this migration does
        print(
            f"  📋 Revision: {info['revision']}, Down revision: {info['down_revision']}"
        )
        if info["tables_created"]:
            print(f"  ✅ Creates tables: {info['tables_created']}")
        if info["indexes_created"]:
            print(f"  🔍 Creates indexes: {len(info['indexes_created'])} indexes")
        if info["functions_created"]:
            print(f"  ⚙️ Creates functions: {info['functions_created']}")
        if info["triggers_created"]:
            print(f"  🔧 Creates triggers: {info['triggers_created']}")

    print("-" * 60)

    # Validate migration sequence
    print("🔗 Validating migration sequence...")
    sequence_errors = validate_migration_sequence(migrations)
    errors.extend(sequence_errors)

    # Validate table operations
    print("🗃️ Validating table operations...")
    table_errors = validate_table_operations(migrations)
    errors.extend(table_errors)

    # Check required tables
    print("📋 Checking required tables...")
    required_table_errors = check_required_tables()
    errors.extend(required_table_errors)

    print("-" * 60)

    if errors:
        print("❌ Validation failed with errors:")
        for error in errors:
            print(f"  • {error}")
        return False
    else:
        print("✅ All migration files validated successfully!")
        print("📊 Summary:")
        print(f"  • {len(migrations)} migration files")
        print(
            f"  • {len(set().union(*[m.get('tables_created', []) for m in migrations]))} total tables"
        )
        print(
            f"  • {sum(len(m.get('indexes_created', [])) for m in migrations)} total indexes"
        )
        print(
            f"  • {sum(len(m.get('functions_created', [])) for m in migrations)} total functions"
        )
        print(
            f"  • {sum(len(m.get('triggers_created', [])) for m in migrations)} total triggers"
        )
        return True


def main():
    """Main validation function."""
    print("🚀 Starting migration file validation...")

    try:
        success = validate_migration_files()
        if success:
            print("\n🎉 Migration validation completed successfully!")
            return 0
        else:
            print("\n💥 Migration validation failed!")
            return 1
    except Exception as e:
        print(f"💥 Validation error: {e}")
        return 1


if __name__ == "__main__":
    exit(main())
