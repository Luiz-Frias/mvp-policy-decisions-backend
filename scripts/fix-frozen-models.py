#!/usr/bin/env python3
"""Fix models missing frozen=True in their ConfigDict."""

import re
from pathlib import Path
from typing import List, Tuple

def fix_frozen_in_file(file_path: Path) -> Tuple[bool, int]:
    """Fix models missing frozen=True in a single file."""
    content = file_path.read_text()
    original_content = content
    fixes = 0
    
    # Find all ConfigDict blocks
    config_pattern = re.compile(
        r'(model_config\s*=\s*ConfigDict\s*\()([^)]+)(\))',
        re.MULTILINE | re.DOTALL
    )
    
    for match in config_pattern.finditer(content):
        config_content = match.group(2)
        
        # Check if frozen=True already exists
        if 'frozen=True' not in config_content:
            # Add frozen=True as the first parameter
            new_config = match.group(1) + '\n        frozen=True,' + config_content + match.group(3)
            content = content.replace(match.group(0), new_config)
            fixes += 1
    
    if content != original_content:
        file_path.write_text(content)
        return True, fixes
    
    return False, 0

def main():
    """Fix all models missing frozen=True."""
    # Find all files with models missing frozen=True
    src_path = Path("src")
    files_to_fix = []
    
    for py_file in src_path.rglob("*.py"):
        if "test" in str(py_file):
            continue
            
        content = py_file.read_text()
        # Check for both BaseModel and BaseModelConfig
        if "class" in content and ("BaseModel" in content or "BaseModelConfig" in content):
            # Look for model_config without frozen=True
            if re.search(r'model_config\s*=\s*ConfigDict\s*\([^)]*\)', content) and "frozen=True" not in content:
                files_to_fix.append(py_file)
    
    print(f"Found {len(files_to_fix)} files with models missing frozen=True")
    
    total_fixes = 0
    fixed_files = 0
    
    for file_path in files_to_fix:
        fixed, count = fix_frozen_in_file(file_path)
        if fixed:
            fixed_files += 1
            total_fixes += count
            print(f"✓ Fixed {count} model(s) in {file_path}")
    
    print(f"\nFixed {total_fixes} models in {fixed_files} files")

if __name__ == "__main__":
    main()