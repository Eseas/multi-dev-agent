# Skills & Agents

## Skill Pipeline

| Skill | Phase | Role | Input | Output (JSON) | Schema |
|-------|-------|------|-------|----------------|--------|
| **skill-planner** | 0 | Refine user needs into requirements | User conversation | `requirements.json` | `requirements.schema.json` |
| **skill-pm** | 0 | Determine pipeline configuration | `requirements.json` | `execution-plan.json` | `execution-plan.schema.json` |
| **skill-architect** | 1 | Design N implementation approaches | `requirements.json`, `execution-plan.json`, project code | `approaches.json` | `approaches.schema.json` |
| **skill-implementer** x N | 2 | Write actual code for each approach | `approaches.json[i]`, project worktree | `work-done.json` + code | `work-done.schema.json` |
| **skill-reviewer** x N | 3 | Review implementation code | `impl-N/`, `work-done.json` | `review.json` | `review.schema.json` |
| **skill-tester** x N | 3 | Write and run tests | `impl-N/`, `work-done.json` | `test-results.json` | `test-results.schema.json` |
| **skill-comparator** | 4 | Compare implementations (alternative mode) | reviews + test results | `comparison.json` | `comparison.schema.json` |
| **skill-integrator** | 4 | Merge implementations (concern mode) | impl branches + api-contract | `integration-report.json` | `integration-report.schema.json` |
| **skill-simplifier** | 5 | Simplify code + document rationale | implementation + reviews | `simplification.json` | `simplification.schema.json` |

---

## Agent Architecture

### BaseAgent

All agents inherit from `BaseAgent` (`orchestrator/agents/base.py`).

```python
class BaseAgent:
    def __init__(self, name, workspace, executor)
    def run(self, context: dict) -> dict       # Main execution
    def load_prompt(self, prompt_file, **kwargs) # Load + substitute template
    def execute_claude(self, prompt, working_dir) # Invoke Claude Code CLI
    def write_output(self, filename, content)    # Atomic file write
    def read_input(self, filename)               # Read from workspace
```

### Execution Flow

```
1. Load skill definition (skills/skill-{name}.md)
2. Substitute context variables into prompt
3. Execute Claude Code CLI (stream-json mode)
4. Parse output and extract JSON
5. Validate output against schema (schemas/{name}.schema.json)
6. Write output to docs/ directory
7. Update manifest.json checkpoint
```

### Inter-Agent Communication

- **File-based**: all data exchange via JSON files in `docs/`
- **Orchestrator-mediated**: Orchestrator passes file paths between phases
- **Atomic writes**: all outputs use `.tmp` → `rename` pattern

---

## Skill Definitions

Skill definitions live in `skills/skill-{name}.md` with YAML frontmatter:

```yaml
---
name: skill-{name}
description: >
  What this skill does and when it triggers.
---

# Skill body (prompt instructions)
```

### Resolution Priority

When resolving prompts for an agent, the system checks:
1. `skills/skill-{name}.md` (new skill-based prompt)
2. `prompts/{name}.md` (legacy prompt fallback)

---

## Schema Validation

Every agent output is validated against its JSON Schema (`schemas/*.schema.json`).

- **warn mode** (default): log validation errors, continue pipeline
- **strict mode**: raise error, halt pipeline

Validation is handled by `SchemaValidator` via `AgentRegistry.validate_output()`.

---

## Phase Details

### Phase 0: Planning (skill-planner + skill-pm)

**skill-planner** refines user needs through conversation:
- One question at a time
- Follows priority: service context → feature scope → edge cases → AC verification
- Exits when all ACs are testable and scope is clear
- Output: `requirements.json`

**skill-pm** analyzes requirements and creates execution plan:
- Determines complexity (simple/medium/complex)
- Sets N-value (1/2/3)
- Chooses pipeline mode (alternative/concern)
- Enables/disables stages per rules
- Output: `execution-plan.json`

### Phase 1: Architecture (skill-architect)

Analyzes requirements + target project codebase to design N approaches.

- Each approach: name, description, key decisions, libraries, trade-offs, complexity, effort
- **Alternative mode**: approaches are independent alternatives
- **Concern mode**: approaches are complementary + generates `api-contract.json`

### Phase 2: Implementation (skill-implementer x N)

Each implementer works in an isolated git worktree.

- Writes actual code using Write/Edit tools
- Follows existing project conventions
- No TODO comments or placeholder code
- Commits all changes to branch `task-{id}/impl-N`
- Output: `work-done.json` listing all created/modified files

### Phase 3: Review + Test (parallel)

**skill-reviewer** reviews across 5 perspectives (weighted):
1. Code quality (30%)
2. Architecture & design (25%)
3. Security (20%)
4. Performance (15%)
5. Testability (10%)

Findings classified as Critical / Major / Minor.

**skill-tester** writes and executes tests:
- Test pyramid: unit (70%) > integration (20%) > E2E (10%)
- Frontend projects: Playwright for E2E
- Reports coverage, discovered bugs, untestable areas

### Phase 4: Evaluation

**skill-comparator** (alternative mode, N>=2):
- Weighted scoring across criteria
- Scenario-based recommendations
- Ranked comparison with final recommendation

**skill-integrator** (concern mode):
- Sequential branch merging
- Conflict resolution (preserve all concerns)
- Glue code (CORS, routing, shared types, build scripts)
- Build verification

### Phase 5: Simplification (skill-simplifier)

- Identifies unnecessary complexity patterns
- Provides concrete simplified code suggestions
- Documents design rationale (why the code was written this way)
- Lists intentional complexity with justification

---

## git Worktree Isolation

Each implementer runs in an independent git worktree:

```
.cache/{repo}/                          ← bare clone or local init
    └── .git/

work/task-{id}/implementations/
    ├── impl-1/                         ← worktree (branch: task-{id}/impl-1)
    │   └── (full project code)
    └── impl-2/                         ← worktree (branch: task-{id}/impl-2)
        └── (full project code)
```

- Separate branches → no file system conflicts
- Reviewer/Tester read worktrees read-only
- Integrator creates `task-{id}/integrated` branch for merging
