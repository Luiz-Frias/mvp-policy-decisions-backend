#!/usr/bin/env python3
"""Fix Response parameter ordering in FastAPI endpoints.

Response parameters must come before parameters with defaults in Python.
"""

import ast
import re
from pathlib import Path


def fix_response_ordering_in_file(file_path: Path) -> bool:
    """Fix Response parameter ordering in a single file."""
    content = file_path.read_text()
    original = content
    
    # Find all async def function signatures that have response: Response
    # This regex finds function definitions that might have Response parameter issues
    pattern = r'(async def \w+\([^)]*?)(response: Response,)([^)]*?\))'
    
    def reorder_params(match):
        prefix = match.group(1)
        response_param = match.group(2)
        suffix = match.group(3)
        
        # Check if there are non-default params before response
        # Look for parameters without = in the prefix
        prefix_lines = prefix.split('\n')
        params_before = []
        
        for line in prefix_lines:
            # Check if this line has a parameter without default
            if '=' not in line and ':' in line and 'async def' not in line:
                params_before.append(line.strip())
        
        # If we have non-default params, Response should come after them
        if params_before:
            # Find the last non-default param position
            # For now, let's just ensure Response comes early in the signature
            # Split the prefix to get function def and first params
            parts = prefix.split('(', 1)
            if len(parts) == 2:
                func_def = parts[0] + '('
                params = parts[1]
                
                # Simple approach: put Response after path/request params
                if '\n    request: Request,' in params:
                    # Put Response after Request
                    new_prefix = params.replace(
                        'request: Request,',
                        'request: Request,\n    response: Response,'
                    )
                    return func_def + new_prefix + suffix.replace('\n    response: Response,', '')
                elif params.strip():
                    # Put Response after first param
                    lines = params.split('\n')
                    if len(lines) > 1:
                        new_lines = [lines[0]] + ['    response: Response,'] + lines[1:]
                        new_prefix = '\n'.join(new_lines)
                        return func_def + new_prefix + suffix.replace('\n    response: Response,', '')
        
        return match.group(0)
    
    # Apply the fix
    content = re.sub(pattern, reorder_params, content, flags=re.MULTILINE | re.DOTALL)
    
    if content != original:
        file_path.write_text(content)
        return True
    return False


def main():
    """Fix Response parameter ordering in all API files."""
    api_dir = Path("src/pd_prime_demo/api/v1")
    
    files_to_fix = [
        api_dir / "sso_auth.py",
        api_dir / "auth.py",
        api_dir / "oauth2.py",
    ]
    
    fixed_files = []
    
    for py_file in files_to_fix:
        if py_file.exists() and fix_response_ordering_in_file(py_file):
            fixed_files.append(py_file)
    
    if fixed_files:
        print(f"Fixed {len(fixed_files)} files:")
        for f in fixed_files:
            print(f"  - {f}")
    else:
        print("No files needed fixing.")


if __name__ == "__main__":
    main()