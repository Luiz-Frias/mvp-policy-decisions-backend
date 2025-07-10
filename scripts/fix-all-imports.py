#!/usr/bin/env python3
"""Fix all missing imports across the codebase to get the app running."""

import ast
import re
from pathlib import Path
from typing import Set

class ImportChecker(ast.NodeVisitor):
    """AST visitor to check for missing imports."""
    
    def __init__(self):
        self.imports = set()
        self.used_names = set()
        self.missing_field = False
        
    def visit_ImportFrom(self, node):
        if node.module:
            for alias in node.names:
                name = alias.asname if alias.asname else alias.name
                self.imports.add(name)
        self.generic_visit(node)
        
    def visit_Import(self, node):
        for alias in node.names:
            name = alias.asname if alias.asname else alias.name
            self.imports.add(name)
        self.generic_visit(node)
    
    def visit_Call(self, node):
        if isinstance(node.func, ast.Name) and node.func.id == 'Field':
            if 'Field' not in self.imports:
                self.missing_field = True
        self.generic_visit(node)


def check_and_fix_file(file_path: Path) -> bool:
    """Check and fix missing imports in a Python file."""
    try:
        content = file_path.read_text()
        
        # Quick check for Field usage without proper import
        if 'Field(' in content and 'Field' not in content:
            # Field is used but not imported anywhere
            needs_field = True
        else:
            # Parse AST to check more carefully
            try:
                tree = ast.parse(content)
                checker = ImportChecker()
                checker.visit(tree)
                needs_field = checker.missing_field
            except:
                # If AST parsing fails, do simple text check
                needs_field = ('Field(' in content and 
                             'from pydantic import' in content and
                             'Field' not in content.split('from pydantic import')[1].split('\n')[0])
        
        if needs_field:
            # Add Field to pydantic imports
            if 'from pydantic import' in content:
                # Find existing pydantic import and add Field
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith('from pydantic import'):
                        # Check if Field is already there
                        if 'Field' not in line:
                            # Add Field to the import
                            if line.endswith(')'):
                                # Multi-line import
                                lines[i] = line[:-1] + ', Field)'
                            else:
                                # Single line import
                                parts = line.split('import', 1)
                                if len(parts) == 2:
                                    imports = parts[1].strip()
                                    if imports:
                                        lines[i] = f"{parts[0]}import {imports}, Field"
                                    else:
                                        lines[i] = f"{parts[0]}import Field"
                            content = '\n'.join(lines)
                            file_path.write_text(content)
                            print(f"✅ Added Field import to: {file_path}")
                            return True
                        break
            else:
                # No pydantic import, add one
                lines = content.split('\n')
                # Find where to add the import (after other imports)
                import_end = 0
                for i, line in enumerate(lines):
                    if line.startswith('import ') or line.startswith('from '):
                        import_end = i + 1
                    elif import_end > 0 and line and not line.startswith(' '):
                        # End of imports section
                        break
                
                lines.insert(import_end, 'from pydantic import Field')
                content = '\n'.join(lines)
                file_path.write_text(content)
                print(f"✅ Added pydantic Field import to: {file_path}")
                return True
                
        return False
        
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False


def fix_specific_files_with_errors():
    """Fix specific files we know have issues."""
    specific_fixes = [
        ("src/pd_prime_demo/services/admin/sso_admin_service.py", "from pydantic import ConfigDict", "from pydantic import ConfigDict, Field"),
        ("src/pd_prime_demo/services/admin/rate_management_service.py", "from pydantic import ConfigDict", "from pydantic import ConfigDict, Field"),
        ("src/pd_prime_demo/services/admin/pricing_override_service.py", "from pydantic import ConfigDict", "from pydantic import ConfigDict, Field"),
        ("src/pd_prime_demo/services/admin/system_settings_service.py", "from pydantic import ConfigDict", "from pydantic import ConfigDict, Field"),
        ("src/pd_prime_demo/services/admin/activity_logger.py", "from pydantic import ConfigDict", "from pydantic import ConfigDict, Field"),
    ]
    
    for file_path, old_import, new_import in specific_fixes:
        path = Path(file_path)
        if path.exists():
            content = path.read_text()
            if old_import in content and "Field" not in content.split(old_import)[0]:
                content = content.replace(old_import, new_import)
                path.write_text(content)
                print(f"✅ Fixed import in: {file_path}")


def main():
    """Fix all import issues in the codebase."""
    src_dir = Path("src")
    
    if not src_dir.exists():
        print("Error: src directory not found!")
        return
    
    print("🔧 Fixing specific known import issues...")
    fix_specific_files_with_errors()
    
    print("\n🔍 Scanning for Field usage without imports...")
    fixed_count = 0
    total_files = 0
    
    # Find all Python files
    for py_file in src_dir.rglob("*.py"):
        total_files += 1
        if check_and_fix_file(py_file):
            fixed_count += 1
    
    print(f"\n📊 Summary:")
    print(f"   Total files scanned: {total_files}")
    print(f"   Files fixed: {fixed_count}")
    
    print("\n✅ Import fixing complete!")


if __name__ == "__main__":
    main()