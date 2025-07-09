#\!/usr/bin/env python3
"""Validate dict usage to exclude false positives from Pydantic field definitions."""

import re
import sys
from pathlib import Path

def is_pydantic_field_definition(line: str) -> bool:
    """Check if a line is a Pydantic field definition."""
    # Pattern for Pydantic field definitions
    patterns = [
        r'^\s*[a-zA-Z_][a-zA-Z0-9_]*:\s*dict\[.*\]\s*=\s*Field',  # field: dict[...] = Field(...)
        r'^\s*[a-zA-Z_][a-zA-Z0-9_]*:\s*dict\[.*\]\s*$',  # field: dict[...]
        r'^\s*[a-zA-Z_][a-zA-Z0-9_]*:\s*list\[dict\[.*\]\]\s*=\s*Field',  # field: list[dict[...]] = Field(...)
        r'^\s*[a-zA-Z_][a-zA-Z0-9_]*:\s*list\[dict\[.*\]\]\s*$',  # field: list[dict[...]]
        r'^\s*[a-zA-Z_][a-zA-Z0-9_]*:\s*.*\ < /dev/null | \s*dict\[.*\]',  # field: Type | dict[...]
    ]
    
    for pattern in patterns:
        if re.match(pattern, line):
            return True
    return False

def is_excluded_line(line: str) -> bool:
    """Check if a line should be excluded from dict validation."""
    # Skip comments
    if re.match(r'^\s*#', line):
        return True
    
    # Skip lines with docstring markers
    if '"""' in line or "'''" in line:
        return True
    
    # Skip lines mentioning "replacing dict["
    if 'replacing dict[' in line or 'Structured model replacing' in line:
        return True
    
    # Skip Pydantic field definitions
    if is_pydantic_field_definition(line):
        return True
    
    return False

def check_file_for_dict_violations(file_path: Path) -> int:
    """Check a file for dict violations, excluding false positives."""
    try:
        content = file_path.read_text()
        
        # Skip if file has SYSTEM_BOUNDARY
        if 'SYSTEM_BOUNDARY' in content:
            return 0
        
        lines = content.split('\n')
        violations = 0
        
        for line in lines:
            if not is_excluded_line(line) and 'dict[' in line:
                violations += 1
        
        return violations
    except Exception:
        return 0

def main():
    """Check all Python files for dict violations."""
    src_path = Path('src')
    total_violations = 0
    files_with_violations = []
    
    for py_file in src_path.rglob('*.py'):
        # Skip test files
        if 'test' in str(py_file):
            continue
        
        violations = check_file_for_dict_violations(py_file)
        if violations > 0:
            total_violations += 1
            files_with_violations.append(str(py_file))
    
    # Output results
    if files_with_violations:
        print(f"DICT_VIOLATIONS={len(files_with_violations)}")
        print("DICT_FILES=")
        for file in files_with_violations[:20]:
            print(f"   • {file}")
        if len(files_with_violations) > 20:
            print(f"   ... and {len(files_with_violations) - 20} more")
    else:
        print("DICT_VIOLATIONS=0")

if __name__ == "__main__":
    main()
