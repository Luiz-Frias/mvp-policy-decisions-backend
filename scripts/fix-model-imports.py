#!/usr/bin/env python3
"""Fix all incorrect relative imports for models.base across the codebase."""

import re
from pathlib import Path

def fix_imports_in_file(file_path: Path) -> bool:
    """Fix imports in a single file."""
    try:
        content = file_path.read_text()
        original_content = content
        
        # Pattern to match relative imports of models.base
        patterns = [
            (r'from \.\.\.models\.base import', 'from policy_core.models.base import'),
            (r'from \.\.\.\.models\.base import', 'from policy_core.models.base import'),
            (r'from \.\.models\.base import', 'from policy_core.models.base import'),
            # Also fix other common incorrect imports
            (r'from \.\.\.\.core\.cache import', 'from policy_core.core.cache import'),
            (r'from \.\.\.\.core\.database import', 'from policy_core.core.database import'),
            (r'from \.\.\.\.core\.config import', 'from policy_core.core.config import'),
            (r'from \.\.\.core\.cache import', 'from policy_core.core.cache import'),
            (r'from \.\.\.core\.database import', 'from policy_core.core.database import'),
            (r'from \.\.\.core\.config import', 'from policy_core.core.config import'),
        ]
        
        for pattern, replacement in patterns:
            content = re.sub(pattern, replacement, content)
        
        if content != original_content:
            file_path.write_text(content)
            print(f"✅ Fixed imports in: {file_path}")
            return True
        return False
        
    except Exception as e:
        print(f"❌ Error processing {file_path}: {e}")
        return False


def main():
    """Fix all import issues in the codebase."""
    src_dir = Path("src")
    
    if not src_dir.exists():
        print("Error: src directory not found!")
        return
    
    fixed_count = 0
    total_files = 0
    
    # Find all Python files
    for py_file in src_dir.rglob("*.py"):
        total_files += 1
        if fix_imports_in_file(py_file):
            fixed_count += 1
    
    print(f"\n📊 Summary:")
    print(f"   Total files scanned: {total_files}")
    print(f"   Files fixed: {fixed_count}")
    
    if fixed_count > 0:
        print(f"\n✅ Fixed {fixed_count} files with incorrect imports!")
    else:
        print("\n✅ No import issues found!")


if __name__ == "__main__":
    main()