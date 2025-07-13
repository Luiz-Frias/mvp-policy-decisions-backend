#!/usr/bin/env python3
"""
Scale DataData Fix Script

This script provides an automated approach to identify and fix DataData compound naming issues 
across the entire codebase. It can be used to systematically address these issues at scale.

Usage:
    python scripts/scale-datadata-fix.py --scan         # Scan for issues
    python scripts/scale-datadata-fix.py --fix          # Fix issues automatically
    python scripts/scale-datadata-fix.py --validate     # Validate fixes
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple


class DataDataFixer:
    """Automated DataData compound name fixer."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.src_path = base_path / "src"
        
        # Patterns to identify DataData issues
        self.patterns = {
            'compound_datadata': re.compile(r'\b([A-Z][a-z]+)DataData\b'),
            'simple_datadata': re.compile(r'\bDataData\b'),
            'compound_data_class': re.compile(r'class\s+([A-Z][a-z]+Data[A-Z][a-z]+)\('),
            'compound_data_usage': re.compile(r'\b([A-Z][a-z]+Data[A-Z][a-z]+)\b'),
        }
        
        # Name transformation rules
        self.transformations = {
            'InputDataData': 'InputData',
            'QuoteDataData': 'QuoteData',
            'StepDataData': 'StepData',
            'RateDataData': 'RateData', 
            'InitialDataData': 'InitialData',
            'AllDataData': 'AllData',
            'RateData1Data': 'RateComparisonData',
            'CacheDataData': 'CacheData',
            'DataData': 'BaseData',
        }
    
    def scan_codebase(self) -> Dict[str, List[Tuple[int, str]]]:
        """Scan the entire codebase for DataData issues."""
        issues = {}
        
        # Find all Python files
        py_files = list(self.src_path.rglob("*.py"))
        
        for file_path in py_files:
            file_issues = []
            
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                    
                for line_num, line in enumerate(lines, 1):
                    # Check for compound DataData patterns
                    for pattern_name, pattern in self.patterns.items():
                        matches = pattern.findall(line)
                        if matches:
                            file_issues.append((line_num, f"{pattern_name}: {line.strip()}"))
                
                if file_issues:
                    issues[str(file_path)] = file_issues
                    
            except Exception as e:
                print(f"Error scanning {file_path}: {e}")
        
        return issues
    
    def suggest_fixes(self, issues: Dict[str, List[Tuple[int, str]]]) -> Dict[str, List[str]]:
        """Suggest fixes for identified issues."""
        suggestions = {}
        
        for file_path, file_issues in issues.items():
            file_suggestions = []
            
            # Read the file content
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Identify compound names that need fixing
                compound_names = set()
                for _, issue_line in file_issues:
                    if 'compound_' in issue_line:
                        # Extract the compound name
                        match = re.search(r'([A-Z][a-z]+Data[A-Z][a-z]+)', issue_line)
                        if match:
                            compound_names.add(match.group(1))
                
                # Generate suggestions for each compound name
                for compound_name in compound_names:
                    if compound_name in self.transformations:
                        suggested_name = self.transformations[compound_name]
                    else:
                        # Auto-generate suggestion by removing duplicate 'Data'
                        suggested_name = re.sub(r'Data([A-Z][a-z]+)', r'\1', compound_name)
                    
                    file_suggestions.append(f"Replace '{compound_name}' with '{suggested_name}'")
                
                # Check for simple DataData patterns
                if 'DataData' in content:
                    file_suggestions.append("Replace 'DataData' with more specific names like 'BaseData', 'CacheData', etc.")
                
                suggestions[file_path] = file_suggestions
                
            except Exception as e:
                print(f"Error analyzing {file_path}: {e}")
        
        return suggestions
    
    def apply_fixes(self, issues: Dict[str, List[Tuple[int, str]]], dry_run: bool = True) -> Dict[str, bool]:
        """Apply fixes to files with DataData issues."""
        results = {}
        
        for file_path, file_issues in issues.items():
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                original_content = content
                
                # Apply transformations
                for old_name, new_name in self.transformations.items():
                    # Replace class definitions
                    content = re.sub(
                        rf'\bclass\s+{re.escape(old_name)}\(',
                        f'class {new_name}(',
                        content
                    )
                    
                    # Replace type annotations
                    content = re.sub(
                        rf'\b{re.escape(old_name)}\b',
                        new_name,
                        content
                    )
                
                # Check if changes were made
                if content != original_content:
                    if not dry_run:
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(content)
                        print(f"Fixed: {file_path}")
                    else:
                        print(f"Would fix: {file_path}")
                    
                    results[file_path] = True
                else:
                    results[file_path] = False
                    
            except Exception as e:
                print(f"Error fixing {file_path}: {e}")
                results[file_path] = False
        
        return results
    
    def validate_fixes(self) -> bool:
        """Validate that fixes were applied correctly by testing imports."""
        try:
            # Test key imports
            cmd = [
                sys.executable, "-c",
                """
import sys
sys.path.insert(0, 'src')
try:
    from policy_core.services.rating.cache_strategy import RatingCacheStrategy
    from policy_core.services.rating.performance import RatingPerformanceOptimizer
    from policy_core.services.rating.rate_tables import RateTableService
    from policy_core.services.quote_wizard import QuoteWizardService
    print('✅ All imports successful')
except ImportError as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"""
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.base_path)
            
            if result.returncode == 0:
                print("✅ Validation successful - all imports work")
                return True
            else:
                print(f"❌ Validation failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Validation error: {e}")
            return False
    
    def generate_report(self, issues: Dict[str, List[Tuple[int, str]]], 
                       suggestions: Dict[str, List[str]]) -> str:
        """Generate a comprehensive report of DataData issues."""
        report = []
        report.append("# DataData Issues Analysis Report")
        report.append("=" * 50)
        report.append("")
        
        # Summary
        total_files = len(issues)
        total_issues = sum(len(file_issues) for file_issues in issues.values())
        
        report.append(f"## Summary")
        report.append(f"- Files with issues: {total_files}")
        report.append(f"- Total issues found: {total_issues}")
        report.append("")
        
        # Issues by category
        pattern_counts = {}
        for file_issues in issues.values():
            for _, issue_line in file_issues:
                pattern = issue_line.split(':')[0]
                pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
        
        report.append("## Issues by Category")
        for pattern, count in sorted(pattern_counts.items()):
            report.append(f"- {pattern}: {count} occurrences")
        report.append("")
        
        # Detailed breakdown
        report.append("## Detailed Breakdown")
        for file_path, file_issues in sorted(issues.items()):
            report.append(f"### {file_path}")
            report.append(f"Issues found: {len(file_issues)}")
            
            for line_num, issue_line in file_issues:
                report.append(f"  Line {line_num}: {issue_line}")
            
            if file_path in suggestions:
                report.append("Suggested fixes:")
                for suggestion in suggestions[file_path]:
                    report.append(f"  - {suggestion}")
            
            report.append("")
        
        # Recommended approach
        report.append("## Recommended Fix Approach")
        report.append("1. Run with --fix flag to apply automatic transformations")
        report.append("2. Review changes and test imports")
        report.append("3. Run with --validate to verify all fixes work correctly")
        report.append("4. Commit changes with descriptive message")
        report.append("")
        
        return "\n".join(report)


def main():
    parser = argparse.ArgumentParser(description="Scale DataData Fix Tool")
    parser.add_argument('--scan', action='store_true', help='Scan codebase for DataData issues')
    parser.add_argument('--fix', action='store_true', help='Apply fixes to DataData issues')
    parser.add_argument('--validate', action='store_true', help='Validate fixes by testing imports')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be fixed without making changes')
    parser.add_argument('--report', type=str, help='Save report to specified file')
    
    args = parser.parse_args()
    
    # Default to scan if no specific action provided
    if not any([args.scan, args.fix, args.validate]):
        args.scan = True
    
    base_path = Path(__file__).parent.parent
    fixer = DataDataFixer(base_path)
    
    if args.scan or args.fix:
        print("🔍 Scanning codebase for DataData issues...")
        issues = fixer.scan_codebase()
        
        if not issues:
            print("✅ No DataData issues found!")
            return
        
        print(f"Found issues in {len(issues)} files")
        
        # Generate suggestions
        suggestions = fixer.suggest_fixes(issues)
        
        if args.scan:
            # Generate and display report
            report = fixer.generate_report(issues, suggestions)
            print(report)
            
            if args.report:
                with open(args.report, 'w') as f:
                    f.write(report)
                print(f"Report saved to {args.report}")
        
        if args.fix:
            print("🔧 Applying fixes...")
            results = fixer.apply_fixes(issues, dry_run=args.dry_run)
            
            successful = sum(1 for success in results.values() if success)
            print(f"Successfully {'would fix' if args.dry_run else 'fixed'} {successful}/{len(results)} files")
    
    if args.validate:
        print("✅ Validating fixes...")
        if fixer.validate_fixes():
            print("All validations passed!")
        else:
            print("Validation failed - please review the fixes")
            sys.exit(1)


if __name__ == "__main__":
    main()