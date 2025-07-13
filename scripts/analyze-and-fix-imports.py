#!/usr/bin/env python3
"""
Deploy 5 analysis agents to comprehensively analyze the codebase
while fixing import issues as they go.
"""

import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple
import ast


@dataclass
class AnalysisResult:
    """Results from analyzing a file."""
    file_path: Path
    has_pydantic_models: bool
    has_frozen_true: bool
    has_beartype: bool
    uses_dict_types: bool
    uses_any_types: bool
    has_result_pattern: bool
    import_issues: List[str] = field(default_factory=list)
    compliance_issues: List[str] = field(default_factory=list)
    data_model_usage: Dict[str, int] = field(default_factory=dict)
    

@dataclass 
class AgentReport:
    """Report from each analysis agent."""
    agent_id: str
    files_analyzed: int
    imports_fixed: int
    compliance_violations: Dict[str, int]
    data_model_findings: Dict[str, any]
    recommendations: List[str]


class ImportFixer:
    """Fixes import issues in Python files."""
    
    def __init__(self):
        self.import_mappings = {
            r'from \.\.\.(\.)?models\.base import': 'from pd_prime_demo.models.base import',
            r'from \.\.\.\.(\.)?models\.base import': 'from pd_prime_demo.models.base import',
            r'from \.\.\.\.(\.)?core\.cache import': 'from pd_prime_demo.core.cache import',
            r'from \.\.\.\.(\.)?core\.database import': 'from pd_prime_demo.core.database import',
            r'from \.\.\.\.(\.)?core\.config import': 'from pd_prime_demo.core.config import',
        }
        
    def fix_imports(self, file_path: Path) -> List[str]:
        """Fix imports in a file and return list of fixes made."""
        fixes = []
        try:
            content = file_path.read_text()
            original = content
            
            # Fix relative imports
            for pattern, replacement in self.import_mappings.items():
                if re.search(pattern, content):
                    content = re.sub(pattern, replacement, content)
                    fixes.append(f"Fixed relative import: {pattern}")
            
            # Fix missing Field imports
            if 'Field(' in content and 'from pydantic import' in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if line.startswith('from pydantic import') and 'Field' not in line:
                        if line.endswith(')'):
                            lines[i] = line[:-1] + ', Field)'
                        else:
                            parts = line.split('import', 1)
                            if len(parts) == 2:
                                lines[i] = f"{parts[0]}import {parts[1]}, Field"
                        fixes.append("Added missing Field import")
                        content = '\n'.join(lines)
                        break
            
            # Fix syntax errors in imports
            content = re.sub(r',\s*\.\.models\.base,\s*from,\s*import,', ',\n)', content)
            if '..models.base,' in content:
                fixes.append("Fixed syntax error in import statement")
            
            if content != original:
                file_path.write_text(content)
                
        except Exception as e:
            fixes.append(f"Error: {str(e)}")
            
        return fixes


class CodebaseAnalyzer:
    """Analyzes Python files for compliance and data model usage."""
    
    def __init__(self):
        self.import_fixer = ImportFixer()
        
    def analyze_file(self, file_path: Path) -> AnalysisResult:
        """Analyze a single Python file."""
        result = AnalysisResult(file_path=file_path)
        
        try:
            content = file_path.read_text()
            
            # Fix imports first
            import_fixes = self.import_fixer.fix_imports(file_path)
            if import_fixes:
                result.import_issues = import_fixes
                # Re-read content after fixes
                content = file_path.read_text()
            
            # Check for Pydantic models
            result.has_pydantic_models = 'class ' in content and 'BaseModel' in content
            
            # Check for frozen=True
            result.has_frozen_true = 'frozen=True' in content
            
            # Check for @beartype
            result.has_beartype = '@beartype' in content
            
            # Check for dict usage without SYSTEM_BOUNDARY
            if 'SYSTEM_BOUNDARY' not in content:
                dict_matches = re.findall(r'dict\[.*?\]', content)
                result.uses_dict_types = len(dict_matches) > 0
                if result.uses_dict_types:
                    result.compliance_issues.append(f"Uses dict types without SYSTEM_BOUNDARY: {len(dict_matches)} occurrences")
            
            # Check for Any types
            any_matches = re.findall(r'\bAny\b', content)
            result.uses_any_types = len(any_matches) > 0
            if result.uses_any_types:
                result.compliance_issues.append(f"Uses Any type: {len(any_matches)} occurrences")
            
            # Check for Result pattern
            result.has_result_pattern = 'Result[' in content
            
            # Analyze data model usage
            model_imports = re.findall(r'from pd_prime_demo\.models\.(\w+) import', content)
            for model in model_imports:
                result.data_model_usage[model] = result.data_model_usage.get(model, 0) + 1
                
            # Check for proper error handling
            if 'raise HTTPException' in content:
                result.compliance_issues.append("Uses HTTPException instead of Result pattern")
                
            # Check for public functions without beartype
            if re.search(r'^def [^_].*\(', content, re.MULTILINE) and '@beartype' not in content:
                result.compliance_issues.append("Has public functions without @beartype")
                
        except Exception as e:
            result.import_issues.append(f"Analysis error: {str(e)}")
            
        return result


async def analyze_directory(agent_id: str, directory: Path, file_pattern: str) -> AgentReport:
    """Agent function to analyze a directory."""
    print(f"🔍 Agent {agent_id} starting analysis of {directory}")
    
    analyzer = CodebaseAnalyzer()
    report = AgentReport(
        agent_id=agent_id,
        files_analyzed=0,
        imports_fixed=0,
        compliance_violations={},
        data_model_findings={},
        recommendations=[]
    )
    
    # Find all Python files
    files = list(directory.rglob(file_pattern))
    
    for file_path in files:
        if '__pycache__' in str(file_path) or 'test' in str(file_path):
            continue
            
        result = analyzer.analyze_file(file_path)
        report.files_analyzed += 1
        
        # Count import fixes
        if result.import_issues:
            report.imports_fixed += len(result.import_issues)
            
        # Track compliance violations
        for issue in result.compliance_issues:
            issue_type = issue.split(':')[0]
            report.compliance_violations[issue_type] = report.compliance_violations.get(issue_type, 0) + 1
            
        # Track data model usage
        for model, count in result.data_model_usage.items():
            key = f"models.{model}"
            report.data_model_findings[key] = report.data_model_findings.get(key, 0) + count
    
    # Generate recommendations
    if report.compliance_violations.get("Uses dict types without SYSTEM_BOUNDARY", 0) > 0:
        report.recommendations.append("Replace dict[str, Any] with proper Pydantic models")
        
    if report.compliance_violations.get("Uses HTTPException instead of Result pattern", 0) > 0:
        report.recommendations.append("Convert HTTPException to Result[T, E] pattern")
        
    if report.compliance_violations.get("Has public functions without @beartype", 0) > 0:
        report.recommendations.append("Add @beartype decorators to all public functions")
    
    print(f"✅ Agent {agent_id} completed: {report.files_analyzed} files, {report.imports_fixed} imports fixed")
    return report


async def main():
    """Deploy 5 analysis agents in parallel."""
    
    # Define agent assignments
    agents = [
        ("agent-1-core", Path("src/pd_prime_demo/core"), "*.py"),
        ("agent-2-services", Path("src/pd_prime_demo/services"), "*.py"),
        ("agent-3-api", Path("src/pd_prime_demo/api"), "*.py"),
        ("agent-4-models-schemas", Path("src/pd_prime_demo/models"), "*.py"),
        ("agent-5-websocket-compliance", Path("src/pd_prime_demo/websocket"), "*.py"),
    ]
    
    print("🚀 Deploying 5 analysis agents to analyze codebase and fix imports...")
    print("=" * 60)
    
    # Run all agents in parallel
    tasks = [analyze_directory(agent_id, directory, pattern) for agent_id, directory, pattern in agents]
    reports = await asyncio.gather(*tasks)
    
    # Aggregate results
    total_files = sum(r.files_analyzed for r in reports)
    total_fixes = sum(r.imports_fixed for r in reports)
    all_violations = {}
    all_models = {}
    
    for report in reports:
        for violation, count in report.compliance_violations.items():
            all_violations[violation] = all_violations.get(violation, 0) + count
        for model, count in report.data_model_findings.items():
            all_models[model] = all_models.get(model, 0) + count
    
    # Generate comprehensive report
    print("\n" + "=" * 60)
    print("📊 COMPREHENSIVE CODEBASE ANALYSIS REPORT")
    print("=" * 60)
    
    print(f"\n📈 Overall Statistics:")
    print(f"   Total files analyzed: {total_files}")
    print(f"   Import issues fixed: {total_fixes}")
    
    print(f"\n❌ Compliance Violations Summary:")
    for violation, count in sorted(all_violations.items(), key=lambda x: x[1], reverse=True):
        print(f"   {violation}: {count}")
    
    print(f"\n📦 Data Model Usage:")
    for model, count in sorted(all_models.items(), key=lambda x: x[1], reverse=True):
        print(f"   {model}: used {count} times")
    
    print(f"\n💡 Top Recommendations:")
    all_recommendations = set()
    for report in reports:
        all_recommendations.update(report.recommendations)
    
    for i, rec in enumerate(all_recommendations, 1):
        print(f"   {i}. {rec}")
    
    # Calculate compliance score
    dict_violations = all_violations.get("Uses dict types without SYSTEM_BOUNDARY", 0)
    any_violations = all_violations.get("Uses Any type", 0)
    http_violations = all_violations.get("Uses HTTPException instead of Result pattern", 0)
    beartype_violations = all_violations.get("Has public functions without @beartype", 0)
    
    total_violations = dict_violations + any_violations + http_violations + beartype_violations
    compliance_score = max(0, 100 - (total_violations * 2))  # Deduct 2 points per violation
    
    print(f"\n🎯 Master Ruleset Compliance Score: {compliance_score}%")
    
    # Save detailed report
    report_data = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_files": total_files,
            "imports_fixed": total_fixes,
            "compliance_score": compliance_score
        },
        "violations": all_violations,
        "data_models": all_models,
        "agent_reports": [
            {
                "agent_id": r.agent_id,
                "files_analyzed": r.files_analyzed,
                "imports_fixed": r.imports_fixed,
                "violations": r.compliance_violations
            }
            for r in reports
        ]
    }
    
    report_path = Path("codebase_analysis_report.json")
    report_path.write_text(json.dumps(report_data, indent=2))
    print(f"\n📄 Detailed report saved to: {report_path}")
    
    # Final assessment
    print("\n" + "=" * 60)
    print("🏁 FINAL ASSESSMENT")
    print("=" * 60)
    
    if compliance_score >= 90:
        print("✅ Codebase is in EXCELLENT shape for production!")
    elif compliance_score >= 70:
        print("🟡 Codebase is GOOD but needs some compliance work")
    else:
        print("🔴 Codebase needs SIGNIFICANT compliance improvements")
    
    print(f"\n🔧 FastAPI Readiness:")
    if total_fixes > 0:
        print(f"   ✅ Fixed {total_fixes} import issues - app should start better now")
    else:
        print("   ✅ No import issues found")
    
    if dict_violations > 0:
        print(f"   ⚠️  {dict_violations} files still use dict types - may affect type safety")
    
    if http_violations > 0:
        print(f"   ⚠️  {http_violations} files use HTTPException - not following Result pattern")


if __name__ == "__main__":
    asyncio.run(main())