# Planning Guide (Phase 0)

## Overview

Phase 0 is the only human-driven phase. The user works with skill-planner to produce `requirements.json`, then skill-pm creates `execution-plan.json`.

**Principle**: Define **what** (requirements) and **why** (business value). The **how** (classes, patterns, algorithms) is decided by agents.

---

## Planning Flow

### Step 1: skill-planner Conversation

The user describes what they need. skill-planner asks clarifying questions:

```
1. Service context   → Who uses it? What service is it?
2. Core feature scope → What are we building? Where are the boundaries?
3. Edge cases         → What happens on failure? Constraints?
4. AC verification    → Is each feature testable?
```

Exit criteria (all must be met):
- Every user story has >= 2 acceptance criteria
- Each AC is testable (no vague "good UX")
- in-scope / out-of-scope clearly separated
- Deferred items don't block core features
- User has confirmed requirements

Output: `requirements.json`

### Step 2: skill-pm Analysis

skill-pm reads `requirements.json` and determines:
- **Complexity**: simple / medium / complex
- **N-value**: 1 / 2 / 3
- **Pipeline mode**: alternative / concern
- **Stage activation**: which agents to enable/disable

Output: `execution-plan.json`

### Step 3: Pipeline Execution

Orchestrator reads `execution-plan.json` and runs the configured pipeline.

---

## N-value Guide

| N | When to use | Examples |
|---|-------------|---------|
| 1 | Clear single solution, bug fix | Simple CRUD, config change |
| 2 | Standard feature, alternatives worth comparing | Auth method choice, library selection |
| 3 | Major architecture decision | DB choice, communication patterns, multi-stack comparison |

---

## Pipeline Mode Guide

### Alternative (default)

N approaches solve the **same problem differently**. One is chosen.

Use when:
- "JWT vs Session — which is better?"
- "ORM direct query vs QueryDSL — which is more maintainable?"

### Concern

N approaches cover **different concerns**. All are merged.

Use when:
- approach-1 = auth module, approach-2 = business logic
- approach-1 = backend API, approach-2 = frontend UI

---

## Common Mistakes

### Missing N-value
```markdown
# Bad
### Method 1: JWT
### Method 2: Session

# Good — skill-pm determines N from requirements complexity
# No need to specify N manually; skill-pm handles it
```

### Specifying implementation details (How)
```markdown
# Bad (constrains agent autonomy)
- Create JwtAuthenticationFilter class and register in SecurityFilterChain

# Good (What/Why only)
- API access must be authenticated and authorized via JWT tokens
- Tokens must auto-refresh on expiration
```

### Unmeasurable criteria
```markdown
# Bad
- Good performance
- Fast response

# Good
- API response time p95 < 200ms
- Handle 1,000 concurrent users
```
