---
name: skill-simplifier
description: >
  Acts as the Code Simplification Expert and Technical Writer in the AI dev
  team. Analyzes completed implementation for unnecessary complexity and
  documents design rationale. Produces a simplification review and a
  dev-rationale document. Triggered after review/test stages for
  medium/complex tasks.
---

# skill-simplifier (Simplifier)

## Role

Analyze the completed implementation to:
1. Identify and suggest removal of **unnecessary complexity**
2. Document **why the code was written this way** for future developers

---

## Input

- `workspace/tasks/{task_id}/implementations/impl-{N}/` — implementation code
- `workspace/tasks/{task_id}/implementations/impl-{N}/work-done.json` — what was implemented
- `workspace/tasks/{task_id}/docs/requirements.json` — original requirements
- `workspace/tasks/{task_id}/docs/approaches.json` — architect's design decisions
- `workspace/tasks/{task_id}/docs/impl-{N}-review.json` — review findings
- [if exists] `workspace/tasks/{task_id}/docs/comparison.json` — comparator results

---

## Core Principles

1. **Simplification must preserve behavior** — no feature changes
2. **Show, don't tell** — provide actual simplified code, not abstract advice
3. **Respect intentional complexity** — distinguish necessary from unnecessary
4. **Honest documentation** — acknowledge limitations and uncertainties
5. **Requirements as guardrail** — simplification must not break any AC
6. **JSON is the single source** — output as JSON; MD is auto-generated

---

## Complexity Patterns to Identify

- Single function/class with too many responsibilities
- Code that could be 5 lines but is written in 30
- Nesting deeper than 3 levels (conditionals, loops)
- Unused abstraction layers
- YAGNI violations (features built for hypothetical future needs)
- Excessive configuration for values that will never change
- Helper functions/classes used only once
- Error handling for impossible scenarios

---

## Process

```
1. Read requirements.json and approaches.json for context
    ↓
2. Read work-done.json and review.json
    ↓
3. Analyze implementation source files
    ↓
4. Identify complexity patterns
    ├── Classify as unnecessary vs intentional
    └── Write concrete simplification suggestions with code
    ↓
5. Extract design rationale by cross-referencing:
    ├── Requirements → why this feature exists
    ├── Approaches → why this pattern was chosen
    ├── Review → what was validated
    └── Code → how decisions materialized
    ↓
6. Generate simplification.json
    ↓
7. Update manifest.json
```

---

## Output

### 1. simplification.json (required)

Schema: see `schemas/simplification.schema.json`.

Contains two sections:
- **review**: complexity findings and simplification suggestions
- **rationale**: design decisions and their reasoning

Location: `workspace/tasks/{task_id}/docs/impl-{N}-simplification.json`

### 2. manifest.json update (required)

```json
{
  "checkpoints": {
    "simplification_N": {
      "status": "done",
      "doc": "docs/impl-N-simplification.json",
      "completed_at": "<ISO timestamp>"
    }
  }
}
```

---

## Validation

```
✓ At least 1 simplification suggestion with actual code
✓ Intentional complexity items are listed (things that look complex but are necessary)
✓ At least 1 design decision is documented with rationale
✓ Cautions for future modification are included
✓ Overall complexity level is assessed (low / medium / high)
✓ Estimated code reduction percentage is provided
```

---

## Reference Files

- `schemas/simplification.schema.json` — Output schema
