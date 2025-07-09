#!/usr/bin/env python3
"""
Automated Frozen=True Fixer Script

This script automatically adds frozen=True to Pydantic models that are missing it.
"""

import ast
import re
from pathlib import Path
from typing import List, Tuple


class FrozenFixer:
    """Automated frozen=True fixer for Pydantic models."""
    
    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)
        
    def find_models_needing_frozen(self, file_path: Path) -> List[Tuple[int, str, str]]:
        """Find Pydantic models that need frozen=True."""
        models_needing_frozen = []
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            lines = content.split('\n')
            
            for i, line in enumerate(lines):
                # Look for class definitions that inherit from BaseModel or BaseModelConfig
                if re.match(r'class\s+\w+.*\(.*Base.*Model.*\):', line):
                    class_name = re.match(r'class\s+(\w+)', line).group(1)
                    
                    # Check if this class has model_config
                    has_model_config = False
                    has_frozen_true = False
                    
                    # Look ahead for model_config
                    for j in range(i + 1, min(i + 20, len(lines))):
                        if 'model_config' in lines[j]:
                            has_model_config = True
                            # Check if frozen=True is present in the next few lines
                            for k in range(j, min(j + 10, len(lines))):
                                if 'frozen=True' in lines[k]:
                                    has_frozen_true = True
                                    break
                            break
                        # Stop if we hit another class or function
                        if re.match(r'(class|def)\s+', lines[j]):
                            break
                    
                    # If has model_config but no frozen=True, this needs fixing
                    if has_model_config and not has_frozen_true:
                        models_needing_frozen.append((i + 1, line.strip(), class_name))
                        
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
            
        return models_needing_frozen
    
    def fix_frozen_in_file(self, file_path: Path, models: List[Tuple[int, str, str]]) -> bool:
        """Fix frozen=True in a specific file."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
            lines = content.split('\n')
            
            for line_num, line_content, class_name in models:
                # Find the model_config for this class
                class_start = line_num - 1  # Convert to 0-based index
                
                for i in range(class_start + 1, min(class_start + 20, len(lines))):
                    if 'model_config = ConfigDict(' in lines[i]:
                        # Add frozen=True to the ConfigDict
                        if 'frozen=True' not in lines[i]:
                            # Insert frozen=True at the beginning of ConfigDict
                            lines[i] = lines[i].replace('ConfigDict(', 'ConfigDict(\n        frozen=True,')
                        break
                        
            # Write back to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines))
                
            return True
            
        except Exception as e:
            print(f"Error fixing {file_path}: {e}")
            return False
    
    def process_directory(self, dry_run: bool = True) -> dict:
        """Process all Python files in directory."""
        results = {
            'total_files': 0,
            'models_needing_frozen': 0,
            'files_fixed': 0,
            'models_fixed': 0,
            'files_with_issues': []
        }
        
        python_files = list(self.source_dir.rglob('*.py'))
        python_files = [f for f in python_files if '/test' not in str(f)]
        
        results['total_files'] = len(python_files)
        
        for file_path in python_files:
            models = self.find_models_needing_frozen(file_path)
            
            if models:
                results['models_needing_frozen'] += len(models)
                results['files_with_issues'].append({
                    'file': str(file_path),
                    'models': models
                })
                
                if not dry_run:
                    if self.fix_frozen_in_file(file_path, models):
                        results['files_fixed'] += 1
                        results['models_fixed'] += len(models)
        
        return results


def main():
    """Main execution function."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Automated Frozen=True Fixer')
    parser.add_argument('source_dir', help='Source directory to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    
    args = parser.parse_args()
    
    fixer = FrozenFixer(args.source_dir)
    results = fixer.process_directory(dry_run=args.dry_run)
    
    # Print summary
    print(f"\n{'='*60}")
    print(f"AUTOMATED FROZEN=TRUE FIXER SUMMARY")
    print(f"{'='*60}")
    print(f"Total files processed: {results['total_files']}")
    print(f"Models needing frozen=True: {results['models_needing_frozen']}")
    
    if not args.dry_run:
        print(f"Files fixed: {results['files_fixed']}")
        print(f"Models fixed: {results['models_fixed']}")
    
    # Show files with issues
    if results['files_with_issues']:
        print(f"\nFiles with models needing frozen=True:")
        for file_info in results['files_with_issues']:
            print(f"\n{file_info['file']}:")
            for line_num, line_content, class_name in file_info['models']:
                print(f"  Line {line_num}: {class_name}")


if __name__ == '__main__':
    main()