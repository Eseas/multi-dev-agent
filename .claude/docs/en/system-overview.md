# System Overview

## Purpose

A pipeline system where multiple AI agents collaborate to automatically perform software development tasks.

Humans define **what** and **why** during Phase 0 (via skill-planner conversation). All subsequent design, implementation, review, testing, comparison, and integration are performed automatically by agents. The result is a set of git branches that the human reviews and merges manually.

---

## Pipeline

```
[skill-planner]  Human + Claude Code → requirements.json
    |
    v
[skill-pm]  Analyze requirements → execution-plan.json
    |
    v
[Orchestrator]  Load execution plan and run pipeline
    |
    v
[Validation]
    - Validate requirements and execution plan against JSON schemas
    - Schema validation mode: strict (fail) or warn (continue)
    |
    v
[Git Setup]
    - target_repo present: git clone / git fetch + reset --hard
    - target_repo empty: .cache/{project}/ with git init + empty commit
    |
    v
[Project Analysis]
    - Python static analysis, no AI cost, ~1s
    - .project-profile.json (cached by commit SHA)
    - project-context.md (keyword-matched relevant code)
    |
    v
[Phase 1: Architect]                    ← stages.architect.enabled
    - Input: requirements.json + project-context.md
    - Design N approaches
    - Output: approaches.json (+ api-contract.json for concern mode)
    |
    v
[Checkpoint]                            ← checkpoint_phase1: true
    - User reviews approaches.json
    - Approve/reject individual approaches (N>=2)
    |
    v
[Phase 2: Implementer x N]             ← ThreadPoolExecutor parallel
    - Each approach in independent git worktree
    - Branch: task-{id}/impl-1, task-{id}/impl-2, ...
    - Output: committed code + work-done.json
    |
    v
[Phase 3: Reviewer + Tester x N]       ← ThreadPoolExecutor parallel
    - Reviewer → review.json (per impl)
    - Tester → test-results.json (per impl)
    |
    v
[Phase 4: Comparator or Integrator]
    - alternative mode (N>=2): Comparator → comparison.json
    - concern mode: Integrator → integration-report.json
    - N=1 alternative: skip Phase 4
    |
    v
[Simplifier]                            ← stages.simplifier.enabled
    - Output: simplification.json
    |
    v
[Done]
    - evaluation-result.md generated
    - User manually merges desired branch
```

---

## Data Flow (JSON-first)

All inter-skill communication uses JSON as the single source of truth.
Markdown files are auto-generated from JSON for human review only.

```
skill-planner     → requirements.json
skill-pm          → execution-plan.json
skill-architect   → approaches.json (+ api-contract.json)
skill-implementer → work-done.json + committed code
skill-reviewer    → review.json
skill-tester      → test-results.json
skill-comparator  → comparison.json        (alternative mode)
skill-integrator  → integration-report.json (concern mode)
skill-simplifier  → simplification.json
```

Each JSON output is validated against its schema in `schemas/*.schema.json`.

---

## Adaptive N-value

| Complexity | N | Behavior |
|------------|---|----------|
| simple | 1 | Single implementation. Architect skipped. Phase 4 skipped |
| medium | 2 | Two parallel implementations + Comparator/Integrator |
| complex | 3 | Three parallel implementations + Comparator/Integrator |

Criteria:
- **simple**: user_stories <= 2, scope.in <= 3, single clear solution
- **medium**: user_stories 3~5, standard feature development
- **complex**: user_stories >= 6, architecture decisions required

---

## Pipeline Modes

### Alternative Mode (default)

Each approach independently solves the same problem differently.
Comparator ranks and recommends the best one.

### Concern Mode

Each approach handles a different concern (e.g. frontend vs backend).
Integrator merges all into one working project.

---

## State Files

All state files stored in `work/task-{id}/docs/`.

| File | Description |
|------|-------------|
| `manifest.json` | Task metadata: current stage, N, mode, checkpoints |
| `timeline.log` | Phase transition timeline |
| `requirements.json` | Requirements from skill-planner |
| `execution-plan.json` | Pipeline config from skill-pm |
| `approaches.json` | N approaches from skill-architect |
| `impl-N-review.json` | Review results per impl |
| `impl-N-test-results.json` | Test results per impl |
| `comparison.json` | Comparison report (alternative mode) |
| `integration-report.json` | Integration report (concern mode) |
| `impl-N-simplification.json` | Simplification + rationale |
| `evaluation-result.md` | Final evaluation and merge guide |

---

## Error Handling

- **Phase failure**: logged to timeline.log, notification sent, manifest → failed, pipeline halted
- **Claude timeout**: auto-retry up to max_retries, then phase fails
- **Checkpoint timeout**: pipeline halts after checkpoint_timeout (default 3600s)
