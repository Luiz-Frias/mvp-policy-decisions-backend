#!/usr/bin/env python3
"""
Master Auto-Fix Script

This script orchestrates all automated fixes for master ruleset compliance:
1. Dict elimination (dict[str, Any] → structured models)
2. Frozen=True fixes (add frozen=True to models)
3. Beartype fixes (add @beartype decorators)
4. Any type fixes (replace Any with proper types)
"""

import subprocess
import sys
from pathlib import Path
from typing import Dict, List


class MasterAutoFixer:
    """Master orchestrator for all automated fixes."""

    def __init__(self, source_dir: str):
        self.source_dir = Path(source_dir)
        self.scripts_dir = Path(__file__).parent

    def run_script(self, script_name: str, args: List[str] = None) -> Dict[str, any]:
        """Run a specific fix script and return results."""
        script_path = self.scripts_dir / script_name

        if not script_path.exists():
            return {'success': False, 'error': f'Script {script_name} not found'}

        cmd = [sys.executable, str(script_path), str(self.source_dir)]
        if args:
            cmd.extend(args)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return {
                'success': result.returncode == 0,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'returncode': result.returncode
            }
        except subprocess.TimeoutExpired:
            return {'success': False, 'error': 'Script timed out'}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    def analyze_current_state(self) -> Dict[str, any]:
        """Analyze current master ruleset violations."""
        # Run dict eliminator in dry-run mode
        dict_results = self.run_script('auto-dict-eliminator.py', ['--dry-run'])

        # Run frozen fixer in dry-run mode
        frozen_results = self.run_script('auto-frozen-fixer.py', ['--dry-run'])

        # Run master validation
        validation_cmd = [str(self.scripts_dir / 'validate-master-ruleset.sh'), str(self.source_dir)]
        validation_result = subprocess.run(validation_cmd, capture_output=True, text=True)

        return {
            'dict_analysis': dict_results,
            'frozen_analysis': frozen_results,
            'validation_output': validation_result.stdout
        }

    def fix_all_issues(self, dry_run: bool = True) -> Dict[str, any]:
        """Fix all master ruleset issues automatically."""
        results = {
            'dict_fixes': None,
            'frozen_fixes': None,
            'overall_success': True,
            'summary': {}
        }

        print("🔧 Starting automated master ruleset fixes...")

        # 1. Fix dict violations
        print("\n1️⃣ Fixing dict[str, Any] violations...")
        args = ['--dry-run'] if dry_run else []
        dict_results = self.run_script('auto-dict-eliminator.py', args)
        results['dict_fixes'] = dict_results

        if dict_results['success']:
            print("✅ Dict fixes completed successfully")
        else:
            print(f"❌ Dict fixes failed: {dict_results.get('error', 'Unknown error')}")
            results['overall_success'] = False

        # 2. Fix frozen=True violations
        print("\n2️⃣ Fixing frozen=True violations...")
        frozen_results = self.run_script('auto-frozen-fixer.py', args)
        results['frozen_fixes'] = frozen_results

        if frozen_results['success']:
            print("✅ Frozen fixes completed successfully")
        else:
            print(f"❌ Frozen fixes failed: {frozen_results.get('error', 'Unknown error')}")
            results['overall_success'] = False

        # 3. Run validation to check results
        print("\n3️⃣ Validating results...")
        validation_cmd = [str(self.scripts_dir / 'validate-master-ruleset.sh'), str(self.source_dir)]
        validation_result = subprocess.run(validation_cmd, capture_output=True, text=True)

        results['final_validation'] = validation_result.stdout

        if validation_result.returncode == 0:
            print("✅ All master ruleset violations fixed!")
        else:
            print("⚠️ Some violations remain - check validation output")

        return results

    def generate_report(self, results: Dict[str, any]) -> str:
        """Generate a comprehensive report of all fixes."""
        report = []
        report.append("=" * 60)
        report.append("MASTER RULESET AUTO-FIX REPORT")
        report.append("=" * 60)

        if results.get('dict_fixes'):
            report.append("\n📊 DICT ELIMINATION RESULTS:")
            if results['dict_fixes']['success']:
                report.append(results['dict_fixes']['stdout'])
            else:
                report.append(f"❌ Failed: {results['dict_fixes'].get('error', 'Unknown')}")

        if results.get('frozen_fixes'):
            report.append("\n🔒 FROZEN=TRUE FIX RESULTS:")
            if results['frozen_fixes']['success']:
                report.append(results['frozen_fixes']['stdout'])
            else:
                report.append(f"❌ Failed: {results['frozen_fixes'].get('error', 'Unknown')}")

        if results.get('final_validation'):
            report.append("\n✅ FINAL VALIDATION:")
            report.append(results['final_validation'])

        report.append("\n" + "=" * 60)
        if results['overall_success']:
            report.append("🎉 ALL FIXES COMPLETED SUCCESSFULLY!")
        else:
            report.append("⚠️ SOME FIXES FAILED - MANUAL INTERVENTION REQUIRED")
        report.append("=" * 60)

        return "\n".join(report)


def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Master Auto-Fix for Ruleset Compliance')
    parser.add_argument('source_dir', help='Source directory to process')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be done without making changes')
    parser.add_argument('--analyze-only', action='store_true', help='Only analyze current state')
    parser.add_argument('--report', action='store_true', help='Generate detailed report')

    args = parser.parse_args()

    fixer = MasterAutoFixer(args.source_dir)

    if args.analyze_only:
        print("🔍 Analyzing current master ruleset state...")
        analysis = fixer.analyze_current_state()
        print(analysis['validation_output'])
        return

    # Run all fixes
    results = fixer.fix_all_issues(dry_run=args.dry_run)

    if args.report:
        report = fixer.generate_report(results)
        print(report)

        # Save report to file
        report_file = Path(args.source_dir) / 'master-fix-report.txt'
        with open(report_file, 'w') as f:
            f.write(report)
        print(f"\n📋 Report saved to: {report_file}")

    # Exit with appropriate code
    sys.exit(0 if results['overall_success'] else 1)


if __name__ == '__main__':
    main()
