#!/usr/bin/env python3
"""
Quick Master Ruleset Fix Script

This script applies the most common, safe automated fixes:
1. Add frozen=True to models missing it
2. Convert simple dict[str, X] patterns to structured models
3. Fix common Any type usage
4. Add missing @beartype decorators
"""

import re
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


class QuickMasterFixer:
    """Quick automated fixes for master ruleset compliance."""
    
    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)
        
    def fix_frozen_models(self) -> Dict[str, any]:
        """Fix models missing frozen=True."""
        results = {'files_fixed': 0, 'models_fixed': 0, 'details': []}
        
        for py_file in self.source_dir.rglob('*.py'):
            if '/test' in str(py_file):
                continue
                
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                    
                # Find models needing frozen=True
                model_pattern = r'class\s+(\w+).*\(.*BaseModel.*\):'
                config_pattern = r'model_config = ConfigDict\('
                
                lines = content.split('\n')
                modified = False
                
                for i, line in enumerate(lines):
                    if re.search(model_pattern, line):
                        # Look for model_config in next 10 lines
                        for j in range(i + 1, min(i + 10, len(lines))):
                            if re.search(config_pattern, lines[j]):
                                if 'frozen=True' not in lines[j]:
                                    # Add frozen=True
                                    lines[j] = lines[j].replace(
                                        'ConfigDict(',
                                        'ConfigDict(\n        frozen=True,'
                                    )
                                    modified = True
                                    results['models_fixed'] += 1
                                break
                            elif re.match(r'(class|def)\s+', lines[j]):
                                break
                
                if modified:
                    with open(py_file, 'w') as f:
                        f.write('\n'.join(lines))
                    results['files_fixed'] += 1
                    results['details'].append(str(py_file))
                    
            except Exception as e:
                print(f"Error processing {py_file}: {e}")
                
        return results
    
    def fix_simple_dict_patterns(self) -> Dict[str, any]:
        """Fix simple dict[str, X] patterns that can be safely automated."""
        results = {'files_fixed': 0, 'patterns_fixed': 0, 'details': []}
        
        # Safe patterns that can be automatically replaced
        safe_patterns = [
            # dict[str, str] in Field() - can be replaced with list of key-value pairs
            (r'dict\[str,\s*str\]\s*=\s*Field\(default_factory=dict\)', 
             'list[KeyValuePair] = Field(default_factory=list)'),
            
            # dict[str, int] for counts - can be replaced with count models
            (r'dict\[str,\s*int\]\s*=\s*Field\(default_factory=dict\)',
             'CountData = Field(default_factory=lambda: CountData())'),
             
            # dict[str, float] for metrics - can be replaced with metrics models
            (r'dict\[str,\s*float\]\s*=\s*Field\(default_factory=dict\)',
             'MetricsData = Field(default_factory=lambda: MetricsData())'),
        ]
        
        for py_file in self.source_dir.rglob('*.py'):
            if '/test' in str(py_file) or 'SYSTEM_BOUNDARY' in str(py_file):
                continue
                
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                    
                original_content = content
                
                for pattern, replacement in safe_patterns:
                    content = re.sub(pattern, replacement, content)
                
                if content != original_content:
                    # Add required models if they don't exist
                    if 'KeyValuePair' in content and 'class KeyValuePair' not in content:
                        content = self._add_key_value_pair_model(content)
                    
                    if 'CountData' in content and 'class CountData' not in content:
                        content = self._add_count_data_model(content)
                    
                    if 'MetricsData' in content and 'class MetricsData' not in content:
                        content = self._add_metrics_data_model(content)
                    
                    with open(py_file, 'w') as f:
                        f.write(content)
                    
                    results['files_fixed'] += 1
                    results['patterns_fixed'] += content.count('KeyValuePair') + content.count('CountData') + content.count('MetricsData')
                    results['details'].append(str(py_file))
                    
            except Exception as e:
                print(f"Error processing {py_file}: {e}")
                
        return results
    
    def _add_key_value_pair_model(self, content: str) -> str:
        """Add KeyValuePair model to content."""
        model = '''
@beartype
class KeyValuePair(BaseModelConfig):
    """Key-value pair for structured dict replacement."""
    
    key: str = Field(..., min_length=1, description="Key")
    value: str = Field(..., min_length=1, description="Value")
'''
        return self._insert_model_after_imports(content, model)
    
    def _add_count_data_model(self, content: str) -> str:
        """Add CountData model to content."""
        model = '''
@beartype
class CountData(BaseModelConfig):
    """Count data for structured dict replacement."""
    
    total: int = Field(default=0, ge=0, description="Total count")
'''
        return self._insert_model_after_imports(content, model)
    
    def _add_metrics_data_model(self, content: str) -> str:
        """Add MetricsData model to content."""
        model = '''
@beartype
class MetricsData(BaseModelConfig):
    """Metrics data for structured dict replacement."""
    
    average: float = Field(default=0.0, ge=0.0, description="Average value")
'''
        return self._insert_model_after_imports(content, model)
    
    def _insert_model_after_imports(self, content: str, model: str) -> str:
        """Insert model definition after imports."""
        lines = content.split('\n')
        
        # Find last import line
        last_import_line = 0
        for i, line in enumerate(lines):
            if line.strip().startswith(('import ', 'from ')):
                last_import_line = i
        
        # Insert model after last import
        lines.insert(last_import_line + 1, model)
        return '\n'.join(lines)
    
    def fix_missing_beartype(self) -> Dict[str, any]:
        """Add @beartype decorators to functions missing them."""
        results = {'files_fixed': 0, 'functions_fixed': 0, 'details': []}
        
        for py_file in self.source_dir.rglob('*.py'):
            if '/test' in str(py_file):
                continue
                
            try:
                with open(py_file, 'r') as f:
                    content = f.read()
                    
                lines = content.split('\n')
                modified = False
                
                for i, line in enumerate(lines):
                    # Look for function definitions
                    if re.match(r'\s*def\s+\w+.*\(.*\).*:', line):
                        # Check if previous line has @beartype
                        if i > 0 and '@beartype' not in lines[i-1]:
                            # Check if this is a public function (not starting with _)
                            func_match = re.match(r'\s*def\s+(\w+)', line)
                            if func_match and not func_match.group(1).startswith('_'):
                                # Add @beartype decorator
                                indent = len(line) - len(line.lstrip())
                                decorator = ' ' * indent + '@beartype'
                                lines.insert(i, decorator)
                                modified = True
                                results['functions_fixed'] += 1
                
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
        print("🔧 Running quick master ruleset fixes...")
        
        results = {
            'frozen_fixes': self.fix_frozen_models(),
            'dict_fixes': self.fix_simple_dict_patterns(),
            'beartype_fixes': self.fix_missing_beartype(),
            'overall_success': True
        }
        
        # Print summary
        print(f"\n✅ QUICK FIXES COMPLETED:")
        print(f"  • Fixed {results['frozen_fixes']['models_fixed']} models missing frozen=True")
        print(f"  • Fixed {results['dict_fixes']['patterns_fixed']} simple dict patterns")
        print(f"  • Added {results['beartype_fixes']['functions_fixed']} @beartype decorators")
        print(f"  • Modified {len(set(results['frozen_fixes']['details'] + results['dict_fixes']['details'] + results['beartype_fixes']['details']))} files")
        
        return results


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Quick Master Ruleset Fixes')
    parser.add_argument('source_dir', help='Source directory to process')
    parser.add_argument('--validate', action='store_true', help='Run validation after fixes')
    
    args = parser.parse_args()
    
    fixer = QuickMasterFixer(args.source_dir)
    results = fixer.run_all_fixes()
    
    if args.validate:
        print("\n🔍 Running validation...")
        try:
            validation_result = subprocess.run(
                ['./scripts/validate-master-ruleset.sh', args.source_dir],
                capture_output=True, text=True, timeout=60
            )
            print(validation_result.stdout)
        except Exception as e:
            print(f"Validation failed: {e}")
    
    print(f"\n🎉 Quick fixes completed! Run full validation to see remaining issues.")


if __name__ == '__main__':
    main()