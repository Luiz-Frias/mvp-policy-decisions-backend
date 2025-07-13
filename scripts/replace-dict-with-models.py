#\!/usr/bin/env python3
"""Replace dict[str, X] usage with the auto-generated Pydantic models."""

import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional

def find_generated_models(content: str) -> Dict[str, str]:
    """Find all auto-generated models in a file."""
    models = {}

    # Pattern to find auto-generated model classes
    pattern = re.compile(
        r'@beartype\s*\n\s*class\s+(\w+)\(BaseModelConfig\):\s*\n\s*"""Structured model replacing (dict\[[^\]]+\]) usage',
        re.MULTILINE
    )

    for match in pattern.finditer(content):
        model_name = match.group(1)
        dict_pattern = match.group(2)
        models[dict_pattern] = model_name

    return models

def analyze_dict_usage(file_path: Path) -> List[Tuple[int, str, str]]:
    """Analyze dict usage in a file and suggest replacements."""
    content = file_path.read_text()
    lines = content.split('\n')

    # Find generated models
    generated_models = find_generated_models(content)

    replacements = []
    dict_pattern = re.compile(r'dict\[[^\]]+\]')

    for i, line in enumerate(lines):
        if 'dict[' in line and 'SYSTEM_BOUNDARY' not in line and '"""' not in line:
            # Find all dict patterns in this line
            for match in dict_pattern.finditer(line):
                dict_usage = match.group(0)

                # Try to find a matching generated model
                suggested_model = None
                for pattern, model in generated_models.items():
                    if pattern == dict_usage or pattern.replace('Any', 'str') == dict_usage:
                        suggested_model = model
                        break

                if not suggested_model:
                    # Generate a suggestion based on context
                    if 'dict[str, Any]' in dict_usage:
                        suggested_model = 'DataModel'  # Generic suggestion
                    elif 'dict[str, str]' in dict_usage:
                        suggested_model = 'StringMapping'
                    elif 'dict[str, int]' in dict_usage:
                        suggested_model = 'IntMapping'
                    elif 'dict[str, float]' in dict_usage:
                        suggested_model = 'FloatMapping'
                    else:
                        suggested_model = None

                replacements.append((i + 1, dict_usage, suggested_model))

    return replacements

def main():
    """Analyze all files and suggest dict replacements."""
    src_path = Path("src")

    # Get list of files with dict violations
    violation_files = []
    for py_file in src_path.rglob("*.py"):
        if "test" not in str(py_file):
            content = py_file.read_text()
            if 'dict[' in content and 'SYSTEM_BOUNDARY' not in content:
                violation_files.append(py_file)

    print(f"Analyzing {len(violation_files)} files with dict usage...\n")

    # Group by directory for better organization
    by_directory = {}
    for file_path in violation_files:
        dir_path = file_path.parent
        if dir_path not in by_directory:
            by_directory[dir_path] = []
        by_directory[dir_path].append(file_path)

    # Analyze each directory
    for dir_path, files in sorted(by_directory.items()):
        print(f"\n{'='*60}")
        print(f"Directory: {dir_path}")
        print(f"{'='*60}")

        for file_path in sorted(files):
            replacements = analyze_dict_usage(file_path)
            if replacements:
                print(f"\n{file_path}:")
                for line_num, dict_usage, suggested_model in replacements:
                    if suggested_model:
                        print(f"  Line {line_num}: Replace '{dict_usage}' with '{suggested_model}'")
                    else:
                        print(f"  Line {line_num}: '{dict_usage}' - needs custom model")

if __name__ == "__main__":
    main()
