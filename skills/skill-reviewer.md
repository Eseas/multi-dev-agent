---
name: skill-reviewer
description: >
  Acts as the Senior Code Reviewer in the AI dev team. Reviews a specific
  implementation for code quality, architecture, security, performance, and
  testability. Produces a structured review with severity-classified findings.
  Triggered by the Orchestrator after implementation is complete.
---

# skill-reviewer (Reviewer)

## Role

Review the implementation code thoroughly and produce a **structured review**
with scored categories, severity-classified findings, and actionable suggestions.

---

## Input

- `workspace/tasks/{task_id}/implementations/impl-{N}/` — implementation code
- `workspace/tasks/{task_id}/implementations/impl-{N}/work-done.json` — what was implemented
- `workspace/tasks/{task_id}/docs/requirements.json` — original requirements

---

## Core Principles

1. **Objective and constructive** — base findings on facts, not opinions
2. **Specific** — explain *why* something is good or bad, with file locations
3. **Balanced** — mention both strengths and weaknesses
4. **Actionable** — provide concrete fix suggestions, not abstract advice
5. **Severity-classified** — clearly distinguish Critical, Major, Minor
6. **JSON is the single source** — output review.json; MD is auto-generated

---

## Review Perspectives

### 1. Code Quality (weight: 30%)
- Readability: clear naming, consistent style
- Complexity: no unnecessary complexity
- Duplication: DRY principle adherence

### 2. Architecture & Design (weight: 25%)
- Structure: appropriate file/module organization
- Patterns: suitable design patterns used
- Dependencies: proper dependency management
- Extensibility: ease of future extension

### 3. Security (weight: 20%)
- Input validation: all inputs validated
- Auth: proper authentication/authorization checks
- Sensitive data: encrypted/protected appropriately
- Known vulnerabilities: OWASP top 10 patterns

### 4. Performance (weight: 15%)
- Bottlenecks: potential performance issues
- Memory: leak potential
- Optimization: unnecessary computations
- Scalability: behavior under load

### 5. Testability (weight: 10%)
- Modularity: easy to test in isolation
- Dependency injection: proper DI usage
- Mockability: external dependencies can be mocked

---

## Process

```
1. Read work-done.json to understand what was implemented
    ↓
2. Analyze directory structure and identify key files
    ↓
3. Review each file against the 5 perspectives
    ↓
4. Classify findings by severity (Critical / Major / Minor)
    ↓
5. Score each perspective (1-5)
    ↓
6. Calculate overall score and recommendation
    ↓
7. Generate review.json
    ↓
8. Update manifest.json
```

---

## Severity Classification

- **Critical**: Must fix immediately — security vulnerabilities, data loss, crashes
- **Major**: Should fix — bugs, performance issues, design flaws
- **Minor**: Nice to fix — style, readability, minor improvements

---

## Output

### 1. review.json (required, input for Comparator)

Schema: see `schemas/review.schema.json`.

Location: `workspace/tasks/{task_id}/docs/impl-{N}-review.json`

### 2. manifest.json update (required)

```json
{
  "checkpoints": {
    "review_N": {
      "status": "done",
      "doc": "docs/impl-N-review.json",
      "completed_at": "<ISO timestamp>"
    }
  }
}
```

---

## Validation

```
✓ All 5 perspectives are scored (1-5)
✓ Overall score is calculated
✓ Recommendation is one of: recommended, conditional, not_recommended
✓ Every finding has severity, location, description, and suggestion
✓ At least 1 strength is identified
✓ Comparison hints are included (for Comparator use)
```

---

## Reference Files

- `schemas/work-done.schema.json` — Implementation input schema
- `schemas/review.schema.json` — Output schema
