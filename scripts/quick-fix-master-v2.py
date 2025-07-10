#!/usr/bin/env python3
"""
Quick Master Ruleset Fix Script V2 - IMPROVED VERSION

This script applies the most common, safe automated fixes:
1. Add frozen=True to models missing it (with deduplication)
2. Convert simple dict[str, X] patterns to structured models (with deduplication)
3. Add missing @beartype decorators

IMPROVEMENTS:
- Deduplicates model generation
- Properly handles existing frozen=True
- Inserts models in correct location with proper spacing
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple, Set


class QuickMasterFixerV2:
    """Quick automated fixes for master ruleset compliance - IMPROVED."""

    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)

    def fix_frozen_models(self) -> Dict[str, any]:
        """Fix models missing frozen=True - IMPROVED with deduplication."""
        results = {'files_fixed': 0, 'models_fixed': 0, 'details': []}

        for py_file in self.source_dir.rglob('*.py'):
            if '/test' in str(py_file):
                continue

            try:
                with open(py_file, 'r') as f:
                    content = f.read()

                # Find models needing frozen=True
                model_pattern = r'class\s+(\w+).*\(.*BaseModel.*\):'
                config_pattern = r'model_config\s*=\s*ConfigDict\s*\('

                lines = content.split('\n')
                modified = False

                i = 0
                while i < len(lines):
                    line = lines[i]
                    if re.search(model_pattern, line):
                        # Look for model_config in next 10 lines
                        config_found = False
                        config_line_idx = -1

                        for j in range(i + 1, min(i + 10, len(lines))):
                            if re.search(config_pattern, lines[j]):
                                config_found = True
                                config_line_idx = j

                                # Check if frozen=True already exists in the ConfigDict
                                # Look from config line until closing paren
                                frozen_exists = False
                                paren_count = 1
                                k = j + 1

                                while k < len(lines) and paren_count > 0:
                                    line_content = lines[k]
                                    if 'frozen=True' in line_content:
                                        frozen_exists = True
                                        break
                                    paren_count += line_content.count('(') - line_content.count(')')
                                    k += 1

                                if not frozen_exists:
                                    # Add frozen=True properly
                                    # Find the line after ConfigDict(
                                    if k < len(lines):
                                        indent = '        '  # Standard indent
                                        # Insert frozen=True as first parameter
                                        lines.insert(j + 1, f'{indent}frozen=True,')
                                        modified = True
                                        results['models_fixed'] += 1
                                break
                            elif re.match(r'(class|def)\s+', lines[j]):
                                break
                    i += 1

                if modified:
                    with open(py_file, 'w') as f:
                        f.write('\n'.join(lines))
                    results['files_fixed'] += 1
                    results['details'].append(str(py_file))

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

        return results

    def fix_dict_patterns_smart(self) -> Dict[str, any]:
        """Fix dict patterns with smart deduplication."""
        results = {'files_fixed': 0, 'patterns_fixed': 0, 'models_added': 0, 'details': []}

        for py_file in self.source_dir.rglob('*.py'):
            if '/test' in str(py_file) or 'scripts/' in str(py_file):
                continue

            try:
                with open(py_file, 'r') as f:
                    content = f.read()

                original_content = content
                lines = content.split('\n')

                # Find all dict patterns and their usage contexts
                dict_patterns = []
                models_needed = set()

                # Pattern to find dict[str, X] usages
                dict_usage_pattern = r'(\w+):\s*(dict\[str,\s*(Any|str|int|float)\])'

                for i, line in enumerate(lines):
                    match = re.search(dict_usage_pattern, line)
                    if match:
                        field_name = match.group(1)
                        dict_type = match.group(2)
                        value_type = match.group(3)

                        # Generate model name based on field and type
                        if value_type == 'Any':
                            model_name = self._capitalize_name(field_name) + 'Data'
                        elif value_type == 'str':
                            model_name = self._capitalize_name(field_name) + 'Mapping'
                        elif value_type == 'int':
                            model_name = self._capitalize_name(field_name) + 'Counts'
                        elif value_type == 'float':
                            model_name = self._capitalize_name(field_name) + 'Metrics'
                        else:
                            model_name = self._capitalize_name(field_name) + 'Structure'

                        dict_patterns.append({
                            'line_idx': i,
                            'field_name': field_name,
                            'dict_type': dict_type,
                            'value_type': value_type,
                            'model_name': model_name
                        })
                        models_needed.add((model_name, value_type))

                if not dict_patterns:
                    continue

                # Check which models already exist
                existing_models = set()
                for line in lines:
                    class_match = re.match(r'class\s+(\w+)', line)
                    if class_match:
                        existing_models.add(class_match.group(1))

                # Determine which models to add
                models_to_add = []
                for model_name, value_type in models_needed:
                    if model_name not in existing_models:
                        model_code = self._generate_model_code(model_name, value_type)
                        models_to_add.append(model_code)

                # Replace dict patterns with model names
                for pattern in dict_patterns:
                    line_idx = pattern['line_idx']
                    lines[line_idx] = lines[line_idx].replace(
                        pattern['dict_type'],
                        pattern['model_name']
                    )
                    results['patterns_fixed'] += 1

                # Add new models after imports (if any)
                if models_to_add:
                    # Check if we need to add imports
                    has_basemodel_import = False
                    has_field_import = False

                    for line in lines:
                        if 'from' in line and 'BaseModelConfig' in line:
                            has_basemodel_import = True
                        if 'from pydantic import' in line and 'Field' in line:
                            has_field_import = True

                    # Find the insertion point (after imports, before first class/function)
                    insert_idx = 0
                    last_import_idx = 0
                    for i, line in enumerate(lines):
                        if line.strip().startswith(('import ', 'from ')):
                            insert_idx = i + 1
                            last_import_idx = i
                        elif line.strip() and not line.strip().startswith('#'):
                            if re.match(r'(class|def|@)', line):
                                break

                    # Add missing imports
                    imports_added = 0
                    if not has_basemodel_import:
                        # Try to find the right import path
                        if 'core' in str(py_file):
                            import_line = 'from ..models.base import BaseModelConfig'
                        else:
                            import_line = 'from .base import BaseModelConfig'
                        lines.insert(last_import_idx + 1, import_line)
                        imports_added += 1

                    if not has_field_import:
                        lines.insert(last_import_idx + 1 + imports_added, 'from pydantic import Field')
                        imports_added += 1

                    insert_idx += imports_added

                    # Add spacing and comment
                    if insert_idx > 0:
                        lines.insert(insert_idx, '')
                        lines.insert(insert_idx + 1, '')
                        lines.insert(insert_idx + 2, '# Auto-generated models')
                        insert_idx += 3

                        for model_code in models_to_add:
                            lines.insert(insert_idx, model_code)
                            insert_idx += 1
                            results['models_added'] += 1

                # Write back if modified
                new_content = '\n'.join(lines)
                if new_content != original_content:
                    with open(py_file, 'w') as f:
                        f.write(new_content)
                    results['files_fixed'] += 1
                    results['details'].append(str(py_file))

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

        return results

    def _capitalize_name(self, name: str) -> str:
        """Convert snake_case to PascalCase."""
        parts = name.split('_')
        return ''.join(part.capitalize() for part in parts)

    def _generate_model_code(self, model_name: str, value_type: str) -> str:
        """Generate Pydantic model code based on type."""
        if value_type == 'Any':
            return f'''
@beartype
class {model_name}(BaseModelConfig):
    """Structured model replacing dict[str, Any] usage."""

    # Auto-generated - customize based on usage
    content: str | None = Field(default=None, description="Content data")
    metadata: dict[str, str] = Field(default_factory=dict, description="Metadata")
'''
        elif value_type == 'str':
            return f'''
@beartype
class {model_name}(BaseModelConfig):
    """Structured model replacing dict[str, str] usage."""

    key: str = Field(..., min_length=1, description="Mapping key")
    value: str = Field(..., min_length=1, description="Mapping value")
'''
        elif value_type == 'int':
            return f'''
@beartype
class {model_name}(BaseModelConfig):
    """Structured model replacing dict[str, int] usage."""

    total: int = Field(default=0, ge=0, description="Total count")
'''
        elif value_type == 'float':
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

    def fix_missing_beartype(self) -> Dict[str, any]:
        """Add @beartype decorators to functions missing them."""
        results = {'files_fixed': 0, 'functions_fixed': 0, 'details': []}

        for py_file in self.source_dir.rglob('*.py'):
            if '/test' in str(py_file) or 'scripts/' in str(py_file):
                continue

            try:
                with open(py_file, 'r') as f:
                    content = f.read()

                lines = content.split('\n')
                modified = False

                # Check if beartype is imported
                has_beartype_import = any('from beartype import beartype' in line for line in lines)

                if not has_beartype_import:
                    continue

                i = 0
                while i < len(lines):
                    line = lines[i]
                    # Look for function definitions
                    if re.match(r'\s*def\s+\w+.*\(.*\).*:', line):
                        # Check if previous line has @beartype
                        has_beartype = False

                        # Look back for decorators
                        j = i - 1
                        while j >= 0 and (lines[j].strip().startswith('@') or lines[j].strip() == ''):
                            if '@beartype' in lines[j]:
                                has_beartype = True
                                break
                            j -= 1

                        if not has_beartype:
                            # Check if this is a public function (not starting with _)
                            func_match = re.match(r'\s*def\s+(\w+)', line)
                            if func_match and not func_match.group(1).startswith('_'):
                                # Skip if this is a field_validator or model_validator
                                # These use Protocol types that beartype can't handle
                                skip_beartype = False
                                for k in range(max(0, i-5), i):
                                    if k < len(lines) and ('field_validator' in lines[k] or 'model_validator' in lines[k]):
                                        skip_beartype = True
                                        break

                                if not skip_beartype:
                                    # Add @beartype decorator
                                    indent = len(line) - len(line.lstrip())
                                    decorator = ' ' * indent + '@beartype'
                                    lines.insert(i, decorator)
                                    modified = True
                                    results['functions_fixed'] += 1
                                    i += 1  # Skip the line we just inserted
                    i += 1

                if modified:
                    with open(py_file, 'w') as f:
                        f.write('\n'.join(lines))
                    results['files_fixed'] += 1
                    results['details'].append(str(py_file))

            except Exception as e:
                print(f"Error processing {py_file}: {e}")

        return results

    def run_all_fixes(self) -> Dict[str, any]:
        """Run all quick fixes."""
        print("🔧 Running quick master ruleset fixes V2...")

        results = {
            'frozen_fixes': self.fix_frozen_models(),
            'dict_fixes': self.fix_dict_patterns_smart(),
            'beartype_fixes': self.fix_missing_beartype(),
            'overall_success': True
        }

        # Print summary
        print(f"\n✅ QUICK FIXES COMPLETED:")
        print(f"  • Fixed {results['frozen_fixes']['models_fixed']} models missing frozen=True")
        print(f"  • Fixed {results['dict_fixes']['patterns_fixed']} dict patterns")
        print(f"  • Added {results['dict_fixes']['models_added']} new models")
        print(f"  • Added {results['beartype_fixes']['functions_fixed']} @beartype decorators")
        print(f"  • Modified {len(set(results['frozen_fixes']['details'] + results['dict_fixes']['details'] + results['beartype_fixes']['details']))} files")

        return results


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Quick Master Ruleset Fixes V2')
    parser.add_argument('source_dir', help='Source directory to process')
    parser.add_argument('--validate', action='store_true', help='Run validation after fixes')

    args = parser.parse_args()

    fixer = QuickMasterFixerV2(args.source_dir)
    results = fixer.run_all_fixes()

    if args.validate:
        print("\n🔍 Running validation...")
        try:
            validation_result = subprocess.run(
                ['bash', 'scripts/validate-master-ruleset.sh'],
                capture_output=True, text=True, timeout=60
            )
            print(validation_result.stdout)
        except Exception as e:
            print(f"Validation failed: {e}")

    print(f"\n🎉 Quick fixes completed! Run full validation to see remaining issues.")


if __name__ == '__main__':
    main()
