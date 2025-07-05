# Agent Instruction Template

## MANDATORY PRE-WORK READING (NON-NEGOTIABLE)

Before beginning ANY work, you MUST read and understand these documents in order:

1. **Master Ruleset**: `.cursor/rules/master-ruleset.mdc`
   - This contains NON-NEGOTIABLE principles
   - If confidence < 95% on any rule, search online for clarification
   - Set 30-second timeout for searches

2. **SAGE Master Instructions**: `.sage/MASTER_INSTRUCTION_SET.md`
   - Understand the wave-based approach
   - Learn the communication protocol
   - Review quality gates

3. **Project Context**: `CLAUDE.md`
   - Current Wave 1 status
   - Wave 2 full production requirements
   - Technology stack and patterns

4. **Source Documents**: `.sage/source_documents/`
   - Read ALL files to understand business requirements
   - Pay special attention to compliance needs

5. **Existing Code Structure**:
   - Review `src/pd_prime_demo/` structure
   - Understand existing patterns (Result types, frozen models)
   - Check for TODOs in your area of responsibility

## CONFIDENCE VALIDATION PROTOCOL

For EVERY decision or implementation:

1. Rate your confidence (0-100%)
2. If confidence < 95%:
   - Search online for best practices (30-second timeout)
   - Check existing codebase for patterns
   - Document uncertainty in comments
   - Add to communication queue for review

## COMMUNICATION REQUIREMENTS

**IMPORTANT**: First create these directories if they don't exist:

```bash
mkdir -p .sage/wave_contexts/wave_2/AGENT_PROGRESS
mkdir -p .sage/wave_contexts/wave_2/BLOCKERS
mkdir -p .sage/wave_contexts/wave_2/COMPLETIONS
```

1. **Status Updates**: Every 30 minutes
   - Write to: `.sage/wave_contexts/wave_2/AGENT_PROGRESS/agent_[ID]_status.md`
   - Format: timestamp, current task, blockers, next steps

2. **Blocker Reporting**: IMMEDIATE
   - Write to: `.sage/wave_contexts/wave_2/BLOCKERS/agent_[ID]_blocker.md`
   - Include: blocker description, attempted solutions, help needed

3. **Completion Report**: When done
   - Write to: `.sage/wave_contexts/wave_2/COMPLETIONS/agent_[ID]_complete.md`
   - Include: files created/modified, tests added, integration points

## QUALITY REQUIREMENTS

1. **Code Standards**:
   - ALL models MUST use `frozen=True`
   - ALL functions MUST have `@beartype` decorator
   - NO `Any` types except at system boundaries
   - NO exceptions for control flow - use Result[T, E]

2. **Testing**:
   - Unit tests for ALL new functions
   - Integration tests for service interactions
   - Performance benchmarks for functions >10 lines

3. **Documentation**:
   - Docstrings for all public functions
   - Type hints for everything
   - Comments for complex logic only

## PARALLELIZATION AWARENESS

You are working in parallel with other agents. To avoid conflicts:

1. **Check File Ownership**: Before modifying any file
   - Look for comments like `# Agent X working on this`
   - Check git status for uncommitted changes
   - Use file locking comments when starting work

2. **Declare Dependencies**: In your status updates
   - List files you're creating
   - List files you're modifying
   - List services you depend on

3. **Integration Points**: Document clearly
   - API contracts you expect
   - Database tables you need
   - Services you'll call

## FAILURE RECOVERY

If you encounter issues:

1. Document the exact error
2. Try alternative approaches (max 3 attempts then zoom out, regroup, analyze and then implement)
3. If still failing, create blocker report
4. Move to secondary tasks while waiting for help
5. NEVER leave work half-done - either complete or rollback
