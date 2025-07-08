#!/usr/bin/env python3
"""Script to fix Python 3.12+ type annotations in test files for Python 3.11 compatibility."""

import re
from pathlib import Path

# Patterns to replace
REPLACEMENTS = [
    # Generic collection types
    (r"\blist\[", "List["),
    (r"\bdict\[", "Dict["),
    (r"\bset\[", "Set["),
    (r"\btuple\[", "Tuple["),
]

# Files to check imports
IMPORT_PATTERNS = {
    "List": "from typing import List",
    "Dict": "from typing import Dict",
    "Set": "from typing import Set",
    "Tuple": "from typing import Tuple",
}


def fix_file(filepath):
    """Fix type annotations in a single file."""
    with open(filepath) as f:
        content = f.read()

    original_content = content

    # Track which types we're using
    used_types = set()

    # Apply replacements
    for old_pattern, new_pattern in REPLACEMENTS:
        if re.search(old_pattern, content):
            # Extract the type name from the replacement
            type_name = new_pattern.rstrip("[")
            used_types.add(type_name)
            content = re.sub(old_pattern, new_pattern, content)

    # Check if we need to add imports
    if used_types and content != original_content:
        # Find existing typing imports
        import_match = re.search(r"^from typing import (.+)$", content, re.MULTILINE)

        if import_match:
            # Parse existing imports
            existing_imports = [imp.strip() for imp in import_match.group(1).split(",")]

            # Add missing imports
            missing_imports = []
            for type_name in used_types:
                if type_name not in existing_imports:
                    missing_imports.append(type_name)

            if missing_imports:
                # Combine and sort all imports
                all_imports = sorted(existing_imports + missing_imports)
                new_import_line = f"from typing import {', '.join(all_imports)}"
                content = re.sub(
                    r"^from typing import .+$",
                    new_import_line,
                    content,
                    count=1,
                    flags=re.MULTILINE,
                )
        else:
            # No typing imports found, add new import after other imports
            # First check if typing is imported at all
            if "from typing import" not in content and "import typing" not in content:
                # Find where to insert the import
                import_section_match = re.search(
                    r"^((?:from .+ import .+|import .+)\n)+", content, re.MULTILINE
                )
                if import_section_match:
                    # Add after existing imports
                    insert_pos = import_section_match.end()
                    needed_imports = sorted(used_types)
                    new_import = f"from typing import {', '.join(needed_imports)}\n"
                    content = content[:insert_pos] + new_import + content[insert_pos:]
                else:
                    # Add after docstring or at the beginning
                    lines = content.split("\n")
                    insert_line = 0

                    # Skip shebang
                    if lines[0].startswith("#!"):
                        insert_line = 1

                    # Skip module docstring
                    if insert_line < len(lines) and lines[
                        insert_line
                    ].strip().startswith('"""'):
                        # Find end of docstring
                        for i in range(insert_line + 1, len(lines)):
                            if '"""' in lines[i]:
                                insert_line = i + 1
                                break

                    # Add empty line if needed
                    if insert_line < len(lines) and lines[insert_line].strip():
                        lines.insert(insert_line, "")
                        insert_line += 1

                    needed_imports = sorted(used_types)
                    lines.insert(
                        insert_line, f"from typing import {', '.join(needed_imports)}"
                    )
                    content = "\n".join(lines)

    # Write back if changed
    if content != original_content:
        with open(filepath, "w") as f:
            f.write(content)
        return True
    return False


def main():
    """Fix all Python files in the tests and scripts directories."""
    root_dir = Path(__file__).parent.parent

    fixed_files = []

    # Fix test files
    tests_dir = root_dir / "tests"
    if tests_dir.exists():
        for py_file in tests_dir.rglob("*.py"):
            if fix_file(py_file):
                fixed_files.append(py_file)

    # Fix script files (except this one)
    scripts_dir = root_dir / "scripts"
    if scripts_dir.exists():
        for py_file in scripts_dir.glob("*.py"):
            if py_file.name not in [
                "fix_python311_types.py",
                "fix_test_python311_types.py",
            ]:
                if fix_file(py_file):
                    fixed_files.append(py_file)

    if fixed_files:
        print(f"Fixed {len(fixed_files)} files:")
        for f in sorted(fixed_files):
            print(f"  - {f.relative_to(root_dir)}")
    else:
        print("No files needed fixing.")


if __name__ == "__main__":
    main()
