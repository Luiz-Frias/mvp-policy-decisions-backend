#!/usr/bin/env python3
"""Fix Response = Depends() syntax errors in FastAPI endpoints."""

import re
from pathlib import Path

def fix_response_depends(file_path: Path) -> bool:
    """Fix Response = Depends() syntax in a file."""
    content = file_path.read_text()
    original = content
    
    # Pattern to match response: Response = Depends(...)
    pattern = r'response:\s*Response\s*=\s*Depends\([^)]*\)'
    
    # Replace with just response: Response
    content = re.sub(pattern, 'response: Response', content)
    
    if content != original:
        file_path.write_text(content)
        return True
    return False

def main():
    """Fix all Response = Depends() issues in API files."""
    api_dir = Path("src/policy_core/api/v1")
    
    fixed_files = []
    
    # Process all Python files in API directory
    for py_file in api_dir.rglob("*.py"):
        if fix_response_depends(py_file):
            fixed_files.append(py_file)
    
    if fixed_files:
        print(f"Fixed {len(fixed_files)} files:")
        for f in fixed_files:
            print(f"  - {f}")
    else:
        print("No files needed fixing.")

if __name__ == "__main__":
    main()