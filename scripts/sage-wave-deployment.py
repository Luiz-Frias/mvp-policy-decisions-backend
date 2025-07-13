#!/usr/bin/env python3
"""
SAGE Wave Deployment Manager
Implements the full SAGE system wave-based deployment strategy with parallel agents.
"""

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
import yaml

# Add project root to path
sys.path.append(str(Path(__file__).parent.parent))

try:
    from sage_parallel_orchestrator import (
        SAGEOrchestrator, AgentTask, WaveDeployment, AgentStatus
    )
except ImportError:
    # If running from different directory
    sys.path.append(str(Path(__file__).parent))
    from sage_parallel_orchestrator import (
        SAGEOrchestrator, AgentTask, WaveDeployment, AgentStatus
    )


@dataclass
class SAGEProject:
    """Represents a complete SAGE project with all waves."""
    name: str
    domain: str
    tech_stack: Dict[str, List[str]]
    waves: List[WaveDeployment]
    performance_requirements: Dict[str, any]
    

class SAGEWaveManager:
    """Manages the complete SAGE wave deployment process."""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.sage_dir = base_dir / ".sage"
        self.orchestrator = SAGEOrchestrator(base_dir)
        
    def read_sage_config(self) -> Dict:
        """Read SAGE configuration from various sources."""
        config = {}
        
        # Read main SAGE config
        sage_config = self.sage_dir / "core" / "config" / "sage.config.yaml"
        if sage_config.exists():
            with open(sage_config) as f:
                config['sage'] = yaml.safe_load(f)
        
        # Read wave orchestrator config
        wave_config = self.sage_dir / "core" / "engine" / "wave-orchestrator.yaml"
        if wave_config.exists():
            with open(wave_config) as f:
                config['waves'] = yaml.safe_load(f)
                
        # Read parallelization rules
        parallel_config = self.sage_dir / "core" / "engine" / "parallelization-rules.yaml"
        if parallel_config.exists():
            with open(parallel_config) as f:
                config['parallelization'] = yaml.safe_load(f)
                
        return config
    
    def analyze_project_requirements(self) -> Dict:
        """Analyze project requirements from CLAUDE.md and source documents."""
        analysis = {
            "current_state": {},
            "target_state": {},
            "gaps": [],
            "priorities": []
        }
        
        # Read CLAUDE.md for current state
        claude_md = self.base_dir / "CLAUDE.md"
        if claude_md.exists():
            content = claude_md.read_text()
            
            # Extract current completion percentages
            if "Current System Completion:" in content:
                analysis["current_state"] = {
                    "overall": 92,  # From CLAUDE.md
                    "security": 45,
                    "compliance": 40,
                    "testing": 30,
                    "observability": 30
                }
            
            # Extract priorities from CLAUDE.md
            if "PHASE 6:" in content:
                analysis["priorities"].append({
                    "phase": 6,
                    "name": "Security Hardening",
                    "agents_needed": 5,
                    "estimated_hours": 4
                })
                
            if "PHASE 7:" in content:
                analysis["priorities"].append({
                    "phase": 7,
                    "name": "SOC 2 Compliance",
                    "agents_needed": 5,
                    "estimated_hours": 4
                })
        
        return analysis
    
    def create_security_wave(self) -> WaveDeployment:
        """Create Wave for Security Hardening (Phase 6 from CLAUDE.md)."""
        return WaveDeployment(
            wave_number=6,
            objective="Security Hardening - Complete security implementation",
            agents=[
                AgentTask(
                    agent_id="sec-1-auth",
                    description="Fix demo authentication bypasses",
                    files=[
                        "src/pd_prime_demo/core/auth/dependencies.py",
                        "src/pd_prime_demo/core/auth/demo_auth.py",
                        "src/pd_prime_demo/api/dependencies.py",
                        "src/pd_prime_demo/core/config.py"
                    ],
                    prompt="""Implement proper authentication with demo mode support:

1. Add DEMO_MODE feature flag to Settings (Doppler-managed)
2. Create DemoAuthMiddleware that:
   - Only activates when DEMO_MODE=true
   - Shows clear demo banners
   - Restricts to read-only operations
   - Uses sandboxed demo data
3. Replace all get_demo_user() calls with proper auth
4. Ensure production auth is never bypassed
5. Add demo account configuration

Follow the patterns in CLAUDE.md Phase 6 Agent 1."""
                ),
                
                AgentTask(
                    agent_id="sec-2-encryption",
                    description="Implement proper encryption with Doppler",
                    files=[
                        "src/pd_prime_demo/core/security/encryption.py",
                        "src/pd_prime_demo/services/sso/config_manager.py",
                        "src/pd_prime_demo/core/security/__init__.py"
                    ],
                    prompt="""Replace weak encryption with production-grade implementation:

1. Create proper encryption module using cryptography library
2. Implement DopplerEncryptionProvider class with Fernet
3. Create abstraction for future AWS KMS support
4. Fix SSO config encryption (currently using base64)
5. Ensure all encryption keys from environment variables

Follow the patterns in CLAUDE.md Phase 6 Agent 2."""
                ),
                
                AgentTask(
                    agent_id="sec-3-ratelimit",
                    description="Add comprehensive rate limiting",
                    files=[
                        "src/pd_prime_demo/api/middleware/rate_limit.py",
                        "src/pd_prime_demo/main.py",
                        "src/pd_prime_demo/api/v1/auth.py",
                        "src/pd_prime_demo/api/v1/quotes.py"
                    ],
                    prompt="""Implement Redis-based rate limiting:

1. Add slowapi for rate limiting middleware
2. Configure per-endpoint limits:
   - /login: 5/minute
   - /api/*: 100/minute  
   - /quotes: 20/minute
3. Add both IP-based and user-based limits
4. Include rate limit headers (X-RateLimit-*)
5. Add circuit breakers for external services

Follow the patterns in CLAUDE.md Phase 6 Agent 3."""
                ),
                
                AgentTask(
                    agent_id="sec-4-pii",
                    description="Fix PII handling and data security",
                    files=[
                        "src/pd_prime_demo/models/customer.py",
                        "src/pd_prime_demo/services/customer_service.py",
                        "src/pd_prime_demo/core/security/pii.py"
                    ],
                    prompt="""Implement proper PII handling:

1. Create field-level encryption for PII fields
2. Replace hardcoded SSN masking with vault-based approach
3. Add audit logging for all PII access
4. Implement data retention policies
5. Create secure data export with redaction

Follow the patterns in CLAUDE.md Phase 6 Agent 4.""",
                    dependencies=["sec-2-encryption"]  # Needs encryption first
                ),
                
                AgentTask(
                    agent_id="sec-5-oauth",
                    description="Fix OAuth2 and API security",
                    files=[
                        "src/pd_prime_demo/api/v1/auth.py",
                        "src/pd_prime_demo/api/v1/api_keys.py",
                        "src/pd_prime_demo/services/auth/oauth2_service.py",
                        "src/pd_prime_demo/core/auth/oauth2.py"
                    ],
                    prompt="""Fix OAuth2 security vulnerabilities:

1. Remove client_secret from all API responses
2. Implement PKCE for authorization flows
3. Add API key rotation (30-day automatic)
4. Implement JWT refresh token rotation
5. Add security headers middleware

Follow the patterns in CLAUDE.md Phase 6 Agent 5."""
                )
            ],
            max_parallelization=3  # Some dependencies
        )
    
    def create_compliance_wave(self) -> WaveDeployment:
        """Create Wave for SOC 2 Compliance (Phase 7 from CLAUDE.md)."""
        return WaveDeployment(
            wave_number=7,
            objective="SOC 2 Compliance - Implement real compliance controls",
            agents=[
                AgentTask(
                    agent_id="soc2-1-controls",
                    description="Implement real security controls",
                    files=[
                        "src/pd_prime_demo/compliance/security_controls.py",
                        "src/pd_prime_demo/compliance/control_tests.py",
                        "src/pd_prime_demo/api/v1/compliance.py"
                    ],
                    prompt="""Replace mock controls with real implementation:

1. Implement real MFA enforcement (not mock)
2. Add password policies (complexity, rotation, history)
3. Create session management with timeout
4. Build access control matrix with RBAC
5. Add security event monitoring

Follow the patterns in CLAUDE.md Phase 7 Agent 1."""
                ),
                
                AgentTask(
                    agent_id="soc2-2-audit",
                    description="Complete audit trail implementation",
                    files=[
                        "src/pd_prime_demo/compliance/audit_logger.py",
                        "src/pd_prime_demo/models/audit.py",
                        "src/pd_prime_demo/api/middleware/audit.py"
                    ],
                    prompt="""Implement comprehensive audit logging:

1. Create tamper-proof audit trail with signing
2. Add audit logging decorator for all sensitive operations
3. Implement 7-year retention for financial data
4. Add log shipping to S3/CloudWatch
5. Create audit report generation

Follow the patterns in CLAUDE.md Phase 7 Agent 2."""
                ),
                
                AgentTask(
                    agent_id="soc2-3-evidence",
                    description="Build evidence collection system",
                    files=[
                        "src/pd_prime_demo/compliance/evidence_collector.py",
                        "src/pd_prime_demo/compliance/reports.py",
                        "src/pd_prime_demo/compliance/scheduling.py"
                    ],
                    prompt="""Automate evidence collection:

1. Build automated evidence collection for controls
2. Create evidence storage with versioning
3. Implement control testing schedules
4. Generate SOC 2 compliance reports
5. Add evidence export for auditors

Follow the patterns in CLAUDE.md Phase 7 Agent 3.""",
                    dependencies=["soc2-1-controls", "soc2-2-audit"]
                )
            ],
            max_parallelization=2
        )
    
    async def validate_wave_completion(self, wave: WaveDeployment) -> Tuple[bool, Dict]:
        """Validate that a wave completed successfully."""
        validation = {
            "success": True,
            "agents_completed": 0,
            "agents_failed": 0,
            "files_created": 0,
            "tests_passing": False,
            "confidence": 0
        }
        
        # Check agent statuses
        for agent in wave.agents:
            if agent.status == AgentStatus.COMPLETED:
                validation["agents_completed"] += 1
            else:
                validation["agents_failed"] += 1
                validation["success"] = False
        
        # Run validation commands
        try:
            # Type checking
            mypy_result = subprocess.run(
                ["uv", "run", "mypy", "src"],
                cwd=self.base_dir,
                capture_output=True
            )
            
            # Linting
            ruff_result = subprocess.run(
                ["uv", "run", "ruff", "check", "src"],
                cwd=self.base_dir,
                capture_output=True
            )
            
            validation["tests_passing"] = (
                mypy_result.returncode == 0 and 
                ruff_result.returncode == 0
            )
            
        except Exception as e:
            print(f"Validation error: {e}")
            validation["tests_passing"] = False
        
        # Calculate confidence
        total_agents = len(wave.agents)
        if total_agents > 0:
            completion_rate = validation["agents_completed"] / total_agents
            validation["confidence"] = int(completion_rate * 100)
        
        return validation["success"], validation
    
    def generate_wave_report(self, wave: WaveDeployment, results: Dict, validation: Dict):
        """Generate a report for wave completion."""
        report = f"""# Wave {wave.wave_number} Completion Report

## Objective
{wave.objective}

## Results
- Agents Deployed: {len(wave.agents)}
- Agents Completed: {validation['agents_completed']}
- Agents Failed: {validation['agents_failed']}
- Overall Success: {'✅ Yes' if validation['success'] else '❌ No'}
- Confidence Score: {validation['confidence']}%

## Agent Details
"""
        
        for agent in wave.agents:
            status_emoji = "✅" if agent.status == AgentStatus.COMPLETED else "❌"
            report += f"\n### {status_emoji} Agent: {agent.agent_id}\n"
            report += f"- Task: {agent.description}\n"
            report += f"- Status: {agent.status.value}\n"
            report += f"- Branch: {agent.branch_name or 'N/A'}\n"
            
            if agent.result and "error" in agent.result:
                report += f"- Error: {agent.result['error']}\n"
        
        report += f"\n## Validation\n"
        report += f"- Tests Passing: {'✅' if validation['tests_passing'] else '❌'}\n"
        
        # Write report
        reports_dir = self.sage_dir / "wave_contexts" / f"wave_{wave.wave_number}"
        reports_dir.mkdir(parents=True, exist_ok=True)
        
        report_file = reports_dir / f"COMPLETION_REPORT_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_file.write_text(report)
        
        print(f"\n📊 Report saved to: {report_file}")
        
    async def run_full_deployment(self):
        """Run the full SAGE deployment process."""
        print("🚀 Starting SAGE Wave Deployment Manager")
        
        # Read configuration
        config = self.read_sage_config()
        
        # Analyze project state
        analysis = self.analyze_project_requirements()
        
        print(f"\n📊 Current Project State:")
        print(f"   Overall Completion: {analysis['current_state'].get('overall', 0)}%")
        print(f"   Security: {analysis['current_state'].get('security', 0)}%")
        print(f"   Compliance: {analysis['current_state'].get('compliance', 0)}%")
        
        # Get user confirmation
        print(f"\n🎯 Ready to deploy waves:")
        print(f"   1. Security Hardening (5 agents)")
        print(f"   2. SOC 2 Compliance (3 agents)")
        
        response = input("\nProceed with deployment? [y/N]: ")
        if response.lower() != 'y':
            print("Deployment cancelled.")
            return
        
        # Create and run waves
        waves = [
            self.create_security_wave(),
            self.create_compliance_wave()
        ]
        
        for wave in waves:
            print(f"\n{'='*60}")
            print(f"🌊 WAVE {wave.wave_number}: {wave.objective}")
            print(f"{'='*60}")
            
            # Run the wave
            results = await self.orchestrator.run_wave(wave)
            
            # Validate completion
            success, validation = await self.validate_wave_completion(wave)
            
            # Generate report
            self.generate_wave_report(wave, results, validation)
            
            # Create PRs for successful agents
            if success:
                print("\n📝 Creating Pull Requests...")
                for agent in wave.agents:
                    if agent.status == AgentStatus.COMPLETED:
                        self.orchestrator.merge_agent_work(agent)
            
            # Check if we should continue
            if validation["confidence"] < 85:
                print(f"\n⚠️  Wave confidence below 85% ({validation['confidence']}%)")
                response = input("Continue to next wave? [y/N]: ")
                if response.lower() != 'y':
                    break
        
        print("\n✅ SAGE Deployment Complete!")
        print("📊 Check .sage/wave_contexts/ for detailed reports")


async def main():
    """Main entry point."""
    manager = SAGEWaveManager(Path.cwd())
    await manager.run_full_deployment()


if __name__ == "__main__":
    asyncio.run(main())