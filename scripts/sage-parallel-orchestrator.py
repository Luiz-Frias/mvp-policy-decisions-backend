#!/usr/bin/env python3
"""
SAGE Parallel Agent Orchestrator
Manages multiple Claude Code agents working in parallel using git worktrees
to avoid conflicts and maximize throughput.
"""

import asyncio
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from enum import Enum

try:
    from claude_code_sdk import query, ClaudeCodeOptions, Message, AssistantMessage, TextBlock
except ImportError:
    print("Error: claude-code-sdk not installed. Run: pip install claude-code-sdk")
    exit(1)


class AgentStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class AgentTask:
    """Represents a task for a specific agent."""
    agent_id: str
    description: str
    files: List[str]
    prompt: str
    dependencies: List[str] = field(default_factory=list)
    branch_name: Optional[str] = None
    worktree_path: Optional[Path] = None
    status: AgentStatus = AgentStatus.PENDING
    result: Optional[Dict] = None
    

@dataclass
class WaveDeployment:
    """Represents a wave of parallel agent deployments."""
    wave_number: int
    agents: List[AgentTask]
    objective: str
    max_parallelization: int = 5
    

class SAGEOrchestrator:
    """
    Orchestrates parallel Claude Code agents following SAGE system principles.
    Uses git worktrees to avoid conflicts between agents.
    """
    
    def __init__(self, base_dir: Path, project_name: str = "mvp_policy_decision"):
        self.base_dir = base_dir
        self.project_name = project_name
        self.sage_dir = base_dir / ".sage"
        self.communication_dir = self.sage_dir / "core" / "communication"
        self.message_queue = self.communication_dir / "message-queue"
        self.agent_registry = self.communication_dir / "agent-registry.json"
        self.worktrees_dir = base_dir.parent / f"{project_name}_worktrees"
        
        # Ensure directories exist
        self.message_queue.mkdir(parents=True, exist_ok=True)
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)
        
    def create_worktree(self, agent_task: AgentTask) -> Path:
        """Create a git worktree for an agent to work in."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        branch_name = f"agent/{agent_task.agent_id}-{timestamp}"
        worktree_path = self.worktrees_dir / f"agent_{agent_task.agent_id}"
        
        # Remove existing worktree if it exists
        if worktree_path.exists():
            subprocess.run(["git", "worktree", "remove", "--force", str(worktree_path)], 
                         cwd=self.base_dir, capture_output=True)
        
        # Create new worktree
        subprocess.run([
            "git", "worktree", "add", "-b", branch_name, 
            str(worktree_path), "HEAD"
        ], cwd=self.base_dir, check=True)
        
        agent_task.branch_name = branch_name
        agent_task.worktree_path = worktree_path
        
        return worktree_path
    
    def write_agent_message(self, agent_id: str, message: str, status: AgentStatus):
        """Write a message to the SAGE communication system."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        message_file = self.message_queue / f"agent-{agent_id}-{status.value}-{timestamp}.md"
        
        content = f"""# Agent {agent_id} Status Update
Timestamp: {datetime.now().isoformat()}
Status: {status.value}

## Message
{message}
"""
        message_file.write_text(content)
    
    def update_agent_registry(self, agent_task: AgentTask):
        """Update the agent registry with current status."""
        registry = {}
        if self.agent_registry.exists():
            registry = json.loads(self.agent_registry.read_text())
        
        registry[agent_task.agent_id] = {
            "status": agent_task.status.value,
            "branch": agent_task.branch_name,
            "worktree": str(agent_task.worktree_path),
            "files": agent_task.files,
            "last_update": datetime.now().isoformat()
        }
        
        self.agent_registry.write_text(json.dumps(registry, indent=2))
    
    def check_dependencies(self, agent_task: AgentTask, completed_agents: Set[str]) -> bool:
        """Check if all dependencies for an agent are satisfied."""
        return all(dep in completed_agents for dep in agent_task.dependencies)
    
    async def run_agent(self, agent_task: AgentTask) -> Dict:
        """Run a single agent with Claude Code SDK."""
        # Create worktree for this agent
        worktree_path = self.create_worktree(agent_task)
        
        # Update status
        agent_task.status = AgentStatus.RUNNING
        self.update_agent_registry(agent_task)
        self.write_agent_message(
            agent_task.agent_id, 
            f"Starting work on: {agent_task.description}", 
            AgentStatus.RUNNING
        )
        
        # Prepare the full prompt with SAGE context
        full_prompt = f"""You are Agent {agent_task.agent_id} working on a specific task.

## Your Task
{agent_task.description}

## Working Directory
You are working in: {worktree_path}
This is your isolated git worktree on branch: {agent_task.branch_name}

## Files to Modify
Focus on these files:
{json.dumps(agent_task.files, indent=2)}

## Communication Protocol
1. You are part of a parallel agent system
2. Other agents are working on different parts simultaneously
3. Do NOT modify files outside your assigned list
4. Write status updates periodically

## Instructions
{agent_task.prompt}

## Completion
When done:
1. Ensure all changes are committed to your branch
2. Summarize what you accomplished
3. Note any issues or blockers encountered
"""
        
        try:
            # Configure Claude Code options
            options = ClaudeCodeOptions(
                max_turns=10,
                cwd=worktree_path,
                allowed_tools=["Read", "Write", "Edit", "MultiEdit", "Bash", "Grep", "Glob"],
                permission_mode="acceptEdits"
            )
            
            # Collect all messages from the agent
            messages = []
            async for message in query(prompt=full_prompt, options=options):
                messages.append(message)
                
                # Extract text from assistant messages for logging
                if isinstance(message, AssistantMessage):
                    for block in message.content:
                        if isinstance(block, TextBlock):
                            self.write_agent_message(
                                agent_task.agent_id,
                                block.text[:500],  # First 500 chars
                                AgentStatus.RUNNING
                            )
            
            # Mark as completed
            agent_task.status = AgentStatus.COMPLETED
            agent_task.result = {"messages": len(messages), "branch": agent_task.branch_name}
            
            self.write_agent_message(
                agent_task.agent_id,
                f"Completed successfully. Branch: {agent_task.branch_name}",
                AgentStatus.COMPLETED
            )
            
        except Exception as e:
            agent_task.status = AgentStatus.FAILED
            agent_task.result = {"error": str(e)}
            
            self.write_agent_message(
                agent_task.agent_id,
                f"Failed with error: {str(e)}",
                AgentStatus.FAILED
            )
        
        finally:
            self.update_agent_registry(agent_task)
        
        return agent_task.result or {}
    
    async def run_wave(self, wave: WaveDeployment) -> Dict[str, Dict]:
        """Run a complete wave of agents with dependency management."""
        print(f"\n🌊 Starting Wave {wave.wave_number}: {wave.objective}")
        print(f"   Deploying {len(wave.agents)} agents (max {wave.max_parallelization} parallel)")
        
        results = {}
        completed_agents = set()
        running_tasks = {}
        
        while len(completed_agents) < len(wave.agents):
            # Find agents that can run
            ready_agents = [
                agent for agent in wave.agents
                if agent.agent_id not in completed_agents
                and agent.agent_id not in running_tasks
                and self.check_dependencies(agent, completed_agents)
            ]
            
            # Limit parallelization
            slots_available = wave.max_parallelization - len(running_tasks)
            agents_to_run = ready_agents[:slots_available]
            
            # Start new agents
            for agent in agents_to_run:
                print(f"   🚀 Starting agent: {agent.agent_id}")
                task = asyncio.create_task(self.run_agent(agent))
                running_tasks[agent.agent_id] = (agent, task)
            
            # Wait for at least one to complete
            if running_tasks:
                done, pending = await asyncio.wait(
                    [task for _, task in running_tasks.values()],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                # Process completed tasks
                for agent_id, (agent, task) in list(running_tasks.items()):
                    if task in done:
                        try:
                            result = await task
                            results[agent_id] = result
                            completed_agents.add(agent_id)
                            print(f"   ✅ Completed: {agent_id}")
                        except Exception as e:
                            results[agent_id] = {"error": str(e)}
                            completed_agents.add(agent_id)
                            print(f"   ❌ Failed: {agent_id}: {e}")
                        finally:
                            del running_tasks[agent_id]
            
            # Small delay to prevent busy waiting
            await asyncio.sleep(1)
        
        print(f"   Wave {wave.wave_number} complete!")
        return results
    
    def merge_agent_work(self, agent_task: AgentTask):
        """Merge an agent's work back to main branch."""
        if not agent_task.branch_name or agent_task.status != AgentStatus.COMPLETED:
            return
        
        try:
            # Create PR using gh CLI
            pr_title = f"feat(agent-{agent_task.agent_id}): {agent_task.description}"
            pr_body = f"""## Agent Task Completion

**Agent ID**: {agent_task.agent_id}
**Task**: {agent_task.description}
**Branch**: {agent_task.branch_name}

### Files Modified
{chr(10).join(f'- {f}' for f in agent_task.files)}

### Status
✅ Completed successfully

---
Generated by SAGE Parallel Orchestrator
"""
            
            result = subprocess.run([
                "gh", "pr", "create",
                "--title", pr_title,
                "--body", pr_body,
                "--head", agent_task.branch_name
            ], cwd=self.base_dir, capture_output=True, text=True)
            
            if result.returncode == 0:
                print(f"✅ PR created for {agent_task.agent_id}: {result.stdout.strip()}")
            else:
                print(f"❌ Failed to create PR for {agent_task.agent_id}: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Error creating PR for {agent_task.agent_id}: {e}")


# Example usage
async def example_deployment():
    """Example of deploying parallel agents for different tasks."""
    
    orchestrator = SAGEOrchestrator(Path.cwd())
    
    # Define Wave 1: Security Hardening (from CLAUDE.md Phase 6)
    wave1 = WaveDeployment(
        wave_number=1,
        objective="Security Hardening - Fix authentication and encryption",
        agents=[
            AgentTask(
                agent_id="security-auth",
                description="Fix demo authentication bypasses",
                files=[
                    "src/policy_core/core/auth/dependencies.py",
                    "src/policy_core/core/auth/demo_auth.py",
                    "src/policy_core/api/dependencies.py"
                ],
                prompt="""Fix all demo authentication bypasses by:
1. Implementing proper feature flag system for DEMO_MODE
2. Create safe demo authentication flow with sandboxed data
3. Replace get_demo_user() with proper auth middleware
4. Add demo mode indicators
5. Ensure demo operations are read-only"""
            ),
            
            AgentTask(
                agent_id="security-encryption", 
                description="Fix weak encryption and integrate Doppler",
                files=[
                    "src/policy_core/core/security/encryption.py",
                    "src/policy_core/services/sso/config_manager.py",
                    "src/policy_core/core/config.py"
                ],
                prompt="""Replace weak encryption with proper implementation:
1. Replace base64 'encryption' with cryptography library (Fernet)
2. Create DopplerEncryptionProvider class
3. Fix SSO config encryption
4. Ensure all secrets use environment variables
5. No hardcoded keys or salts"""
            ),
            
            AgentTask(
                agent_id="security-ratelimit",
                description="Implement rate limiting",
                files=[
                    "src/policy_core/api/middleware/rate_limit.py",
                    "src/policy_core/main.py"
                ],
                prompt="""Add comprehensive rate limiting:
1. Use slowapi for Redis-based rate limiting
2. Add per-endpoint limits (login: 5/min, API: 100/min)
3. Implement IP-based and user-based limits
4. Add rate limit headers
5. Include circuit breakers for external calls""",
                dependencies=[]  # Can run in parallel
            )
        ],
        max_parallelization=3
    )
    
    # Run the wave
    results = await orchestrator.run_wave(wave1)
    
    # Create PRs for completed agents
    for agent in wave1.agents:
        if agent.status == AgentStatus.COMPLETED:
            orchestrator.merge_agent_work(agent)
    
    return results


if __name__ == "__main__":
    # Run example deployment
    asyncio.run(example_deployment())