#!/usr/bin/env python3
"""Analyze specific quality gate violations to understand the actual issues."""

import ast
import sys
from pathlib import Path

def check_file_for_violations(file_path: Path):
    """Check a specific file for quality violations."""
    print(f"\n🔍 Analyzing: {file_path.relative_to(Path.cwd())}")
    
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            
        # Check for plain dict usage
        dict_patterns = [
            'dict[str, Any]', 
            'Dict[str, Any]',
            'dict[str, any]',
            'Dict[str, any]'
        ]
        
        for i, line in enumerate(content.split('\n'), 1):
            for pattern in dict_patterns:
                if pattern in line and not line.strip().startswith('#'):
                    print(f"  📍 Line {i}: Plain dict usage: {line.strip()}")
        
        # Check for missing frozen=True in Pydantic models
        tree = ast.parse(content)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                # Check if it's a Pydantic model
                has_basemodel = any(
                    (isinstance(base, ast.Name) and 'BaseModel' in base.id) or
                    (isinstance(base, ast.Attribute) and 'BaseModel' in getattr(base, 'attr', ''))
                    for base in node.bases
                )
                
                if has_basemodel:
                    print(f"  📋 Found Pydantic model: {node.name} (line {node.lineno})")
                    
                    # Look for model_config
                    has_frozen = False
                    for item in node.body:
                        if isinstance(item, ast.Assign):
                            for target in item.targets:
                                if isinstance(target, ast.Name) and target.id == 'model_config':
                                    # Check if frozen=True is in the config
                                    has_frozen = 'frozen=True' in ast.unparse(item.value)
                                    break
                    
                    if not has_frozen:
                        print(f"    ❌ Missing frozen=True in {node.name}")
                    else:
                        print(f"    ✅ Has frozen=True in {node.name}")
        
    except Exception as e:
        print(f"  ❌ Error analyzing file: {e}")

# Analyze key business logic files
key_files = [
    "src/policy_core/models/quote.py",
    "src/policy_core/models/admin.py", 
    "src/policy_core/models/base.py",
    "src/policy_core/schemas/rating.py",
    "src/policy_core/core/database_config.py"
]

for file_path in key_files:
    path = Path(file_path)
    if path.exists():
        check_file_for_violations(path)
    else:
        print(f"❌ File not found: {file_path}")

print("\n📊 Analysis complete!")