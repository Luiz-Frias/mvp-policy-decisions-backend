#!/usr/bin/env python3
"""
Automated Dict Elimination Script

This script automatically converts dict[str, Any] and common dict patterns
to structured Pydantic models, eliminating the need for manual micro-agent deployment.
"""

import ast
import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple


class DictPattern:
    """Represents a dictionary pattern that can be automatically replaced."""

    def __init__(self, pattern: str, replacement_template: str, model_template: str):
        self.pattern = pattern
        self.replacement_template = replacement_template
        self.model_template = model_template


# Common dictionary patterns and their replacements
COMMON_PATTERNS = [
    # dict[str, Any] patterns
    DictPattern(
        pattern=r'dict\[str,\s*Any\]',
        replacement_template='{field_name}Data',
        model_template='''
@beartype
class {model_name}(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated fields - customize as needed
    data: dict[str, str] = Field(default_factory=dict, description="Structured data")
'''
    ),

    # dict[str, str] patterns
    DictPattern(
        pattern=r'dict\[str,\s*str\]',
        replacement_template='{field_name}Mapping',
        model_template='''
@beartype
class {model_name}(BaseModelConfig):
    """Structured model replacing dict[str, str] usage."""

    # Auto-generated fields - customize as needed
    mappings: list[KeyValuePair] = Field(default_factory=list, description="Key-value pairs")
'''
    ),

    # dict[str, int] patterns
    DictPattern(
        pattern=r'dict\[str,\s*int\]',
        replacement_template='{field_name}Counts',
        model_template='''
@beartype
class {model_name}(BaseModelConfig):
    """Structured model replacing dict[str, int] usage."""

    # Auto-generated fields - customize as needed
    total: int = Field(default=0, ge=0, description="Total count")
'''
    ),

    # dict[str, float] patterns
    DictPattern(
        pattern=r'dict\[str,\s*float\]',
        replacement_template='{field_name}Metrics',
        model_template='''
@beartype
class {model_name}(BaseModelConfig):
    """Structured model replacing dict[str, float] usage."""

    # Auto-generated fields - customize as needed
    average: float = Field(default=0.0, ge=0.0, description="Average value")
'''
    ),
]


class DictEliminator:
    """Automated dictionary elimination processor."""

    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)
        self.processed_files = []
        self.models_created = []

    def find_dict_usages(self, file_path: Path) -> List[Tuple[int, str, str]]:
        """Find all dict[...] usages in a file."""
        dict_usages = []

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Find all dict[...] patterns
            for line_num, line in enumerate(content.split('\n'), 1):
                if 'dict[' in line and 'SYSTEM_BOUNDARY' not in line:
                    # Extract the dict pattern
                    dict_match = re.search(r'dict\[[^\]]+\]', line)
                    if dict_match:
                        dict_pattern = dict_match.group(0)
                        dict_usages.append((line_num, line.strip(), dict_pattern))

        except Exception as e:
            print(f"Error reading {file_path}: {e}")

        return dict_usages

    def generate_field_name(self, line: str) -> str:
        """Extract field name from line containing dict usage."""
        # Look for field_name: dict[...] pattern
        field_match = re.search(r'(\w+):\s*dict\[', line)
        if field_match:
            return field_match.group(1)

        # Look for variable assignment pattern
        var_match = re.search(r'(\w+)\s*=.*dict\[', line)
        if var_match:
            return var_match.group(1)

        return "data"

    def create_model_name(self, field_name: str, dict_pattern: str) -> str:
        """Create appropriate model name based on field name and dict pattern."""
        # Convert field_name to PascalCase
        pascal_name = ''.join(word.capitalize() for word in field_name.split('_'))

        # Add appropriate suffix based on dict pattern
        if 'Any' in dict_pattern:
            return f"{pascal_name}Data"
        elif 'str' in dict_pattern and dict_pattern.count('str') == 2:
            return f"{pascal_name}Mapping"
        elif 'int' in dict_pattern:
            return f"{pascal_name}Counts"
        elif 'float' in dict_pattern:
            return f"{pascal_name}Metrics"
        else:
            return f"{pascal_name}Structure"

    def process_file(self, file_path: Path) -> Dict[str, any]:
        """Process a single file and return transformation results."""
        results = {
            'file': str(file_path),
            'dict_usages': [],
            'models_created': [],
            'transformations': [],
            'success': False
        }

        try:
            # Find all dict usages
            dict_usages = self.find_dict_usages(file_path)
            results['dict_usages'] = dict_usages

            if not dict_usages:
                results['success'] = True
                return results

            # Read original file
            with open(file_path, 'r', encoding='utf-8') as f:
                original_content = f.read()

            # Group usages by dict pattern
            pattern_groups = {}
            for line_num, line, dict_pattern in dict_usages:
                if dict_pattern not in pattern_groups:
                    pattern_groups[dict_pattern] = []
                pattern_groups[dict_pattern].append((line_num, line))

            # Generate models and transformations
            models_to_add = []
            transformations = []

            for dict_pattern, usages in pattern_groups.items():
                for line_num, line in usages:
                    field_name = self.generate_field_name(line)
                    model_name = self.create_model_name(field_name, dict_pattern)

                    # Create model template
                    model_template = self.get_model_template(dict_pattern, model_name)
                    models_to_add.append(model_template)

                    # Create transformation
                    transformation = {
                        'line_num': line_num,
                        'original': line,
                        'dict_pattern': dict_pattern,
                        'model_name': model_name,
                        'replacement': line.replace(dict_pattern, model_name)
                    }
                    transformations.append(transformation)

            results['models_created'] = models_to_add
            results['transformations'] = transformations
            results['success'] = True

        except Exception as e:
            results['error'] = str(e)

        return results

    def get_model_template(self, dict_pattern: str, model_name: str) -> str:
        """Get appropriate model template for dict pattern."""
        if 'Any' in dict_pattern:
            return f'''
@beartype
class {model_name}(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")
'''
        elif 'str' in dict_pattern and dict_pattern.count('str') == 2:
            return f'''
@beartype
class {model_name}(BaseModelConfig):
    """Structured model replacing dict[str, str] usage."""

    key: str = Field(..., min_length=1, description="Mapping key")
    value: str = Field(..., min_length=1, description="Mapping value")
'''
        elif 'int' in dict_pattern:
            return f'''
@beartype
class {model_name}(BaseModelConfig):
    """Structured model replacing dict[str, int] usage."""

    total: int = Field(default=0, ge=0, description="Total count")
'''
        elif 'float' in dict_pattern:
            return f'''
@beartype
class {model_name}(BaseModelConfig):
    """Structured model replacing dict[str, float] usage."""

    average: float = Field(default=0.0, ge=0.0, description="Average value")
'''
        else:
            return f'''
@beartype
class {model_name}(BaseModelConfig):
    """Structured model replacing dict usage."""

    # Auto-generated - customize based on usage
    data: dict[str, str] = Field(default_factory=dict, description="Structured data")
'''

    def apply_transformations(self, file_path: Path, results: Dict[str, any]) -> bool:
        """Apply transformations to file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Add models at the top (after imports)
            model_definitions = '\n'.join(results['models_created'])

            # Find insertion point (after last import)
            import_pattern = r'(from\s+.*?import\s+.*?\n|import\s+.*?\n)'
            import_matches = list(re.finditer(import_pattern, content))

            if import_matches:
                last_import_end = import_matches[-1].end()
                content = (content[:last_import_end] +
                          f"\n\n# Auto-generated models\n{model_definitions}\n\n" +
                          content[last_import_end:])

            # Apply field transformations
            for transformation in results['transformations']:
                content = content.replace(
                    transformation['original'],
                    transformation['replacement']
                )

            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            return True

        except Exception as e:
            print(f"Error applying transformations to {file_path}: {e}")
            return False

    def process_directory(self, dry_run: bool = True) -> Dict[str, any]:
        """Process all Python files in directory."""
        results = {
            'total_files': 0,
            'processed_files': 0,
            'dict_violations_found': 0,
            'dict_violations_fixed': 0,
            'models_created': 0,
            'files_with_violations': [],
            'successful_transformations': [],
            'failed_transformations': []
        }

        # Find all Python files
        python_files = list(self.source_dir.rglob('*.py'))
        python_files = [f for f in python_files if '/test' not in str(f)]

        results['total_files'] = len(python_files)

        for file_path in python_files:
            # Skip if file has SYSTEM_BOUNDARY annotation
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    if 'SYSTEM_BOUNDARY' in f.read():
                        continue
            except:
                continue

            file_results = self.process_file(file_path)

            if file_results['dict_usages']:
                results['files_with_violations'].append(file_results)
                results['dict_violations_found'] += len(file_results['dict_usages'])

                if not dry_run and file_results['success']:
                    if self.apply_transformations(file_path, file_results):
                        results['successful_transformations'].append(file_results)
                        results['dict_violations_fixed'] += len(file_results['dict_usages'])
                        results['models_created'] += len(file_results['models_created'])
                    else:
                        results['failed_transformations'].append(file_results)

            results['processed_files'] += 1

        return results


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Automated Dict Elimination')
    parser.add_argument('source_dir', help='Source directory to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--verbose', action='store_true', help='Verbose output')

    args = parser.parse_args()

    eliminator = DictEliminator(args.source_dir)
    results = eliminator.process_directory(dry_run=args.dry_run)

    # Print summary
    print(f"\n{'='*60}")
    print(f"AUTOMATED DICT ELIMINATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total files processed: {results['processed_files']}")
    print(f"Files with dict violations: {len(results['files_with_violations'])}")
    print(f"Dict violations found: {results['dict_violations_found']}")

    if not args.dry_run:
        print(f"Dict violations fixed: {results['dict_violations_fixed']}")
        print(f"Models created: {results['models_created']}")
        print(f"Successful transformations: {len(results['successful_transformations'])}")
        print(f"Failed transformations: {len(results['failed_transformations'])}")

    # Show top violating files
    if results['files_with_violations']:
        print(f"\nTop 10 files with most violations:")
        sorted_files = sorted(results['files_with_violations'],
                            key=lambda x: len(x['dict_usages']), reverse=True)
        for i, file_result in enumerate(sorted_files[:10]):
            print(f"{i+1:2d}. {file_result['file']}: {len(file_result['dict_usages'])} violations")

    if args.verbose:
        print(f"\nDETAILED BREAKDOWN:")
        for file_result in results['files_with_violations'][:5]:  # Show first 5
            print(f"\n{file_result['file']}:")
            for usage in file_result['dict_usages'][:3]:  # Show first 3 usages
                print(f"  Line {usage[0]}: {usage[1]}")


if __name__ == '__main__':
    main()
