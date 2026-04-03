# Development Planning Template

## Overview

Template for requirements conversation with skill-planner.
The output `requirements.json` drives the entire pipeline.

**Agent pre-requisites**:
1. Read `tech-stack.md` before writing any code
2. If the spec introduces tech not in `tech-stack.md`, update it first
3. Only define **What** and **Why** — agents decide **How**

---

## Requirements Conversation Guide

skill-planner conducts the conversation in this order:

```
1. Service context    → Who uses it? What service?
2. Feature scope      → What exactly are we building?
3. Constraints        → What integrates with existing systems?
4. Edge cases         → What happens on failure? Limits?
5. AC verification    → Is each item testable?
```

Exit when all acceptance criteria are in verb+condition form:
- ✅ "Account is locked after 5 failed login attempts"
- ❌ "Security should be good" (re-ask)

---

## requirements.json Output Structure

```json
{
  "task_id": "task-001",
  "created_at": "2026-04-03T00:00:00Z",
  "user_stories": [
    {
      "id": "US-001",
      "as_a": "admin user",
      "i_want": "manage user roles via web",
      "so_that": "I can control access without developer assistance",
      "acceptance_criteria": [
        "Admin can view a paginated user list",
        "Admin can change a user's role and the change takes effect immediately",
        "Non-admin cannot access the admin API (returns 403)"
      ],
      "priority": "must"
    }
  ],
  "scope": {
    "in": ["User list view", "Role change API", "Admin auth guard"],
    "out": ["User creation", "Password reset"]
  },
  "deferred": ["Audit log for role changes"],
  "conversation_summary": "Admin panel to manage user roles. Focus on role change flow and access control.",
  "pipeline_hint": {
    "complexity": "medium",
    "requires_design": true,
    "notes": "Needs auth integration with existing Spring Security config"
  }
}
```

Schema: `schemas/requirements.schema.json`

---

## execution-plan.json Output Structure

skill-pm generates this from requirements.json:

```json
{
  "task_id": "task-001",
  "created_at": "2026-04-03T00:00:00Z",
  "requirements_ref": "docs/requirements.json",
  "pipeline": {
    "mode": "alternative",
    "num_approaches": 2,
    "complexity": "medium"
  },
  "stages": {
    "architect":   { "enabled": true, "focus": "Role-based access control patterns" },
    "implementer": { "enabled": true, "guidelines": ["Use existing UserService", "Follow existing API response format"] },
    "reviewer":    { "enabled": true, "focus_areas": ["Security", "API consistency"] },
    "tester":      { "enabled": true, "test_strategy": "mixed" },
    "comparator":  { "enabled": true, "criteria": ["Security", "Code quality", "Maintainability"] },
    "integrator":  { "enabled": false },
    "simplifier":  { "enabled": true }
  },
  "risk_notes": ["Must not break existing auth flow"],
  "summary": "Medium complexity. 2 alternative approaches comparing different RBAC strategies. Full pipeline with review, test, and comparison."
}
```

Schema: `schemas/execution-plan.schema.json`

---

## Writing Good Requirements

### DO
- Write ACs in "verb + condition" form
- Specify measurable technical criteria (p95 < 200ms)
- List integration points with existing code
- Separate in-scope from out-of-scope explicitly

### DO NOT
- Name specific classes, methods, or design patterns
- Specify file structure
- Write code snippets
- Use vague terms: "appropriate", "fast", "good"

### Good vs Bad Examples

| Bad | Good |
|-----|------|
| "Good security" | "Unauthorized access returns 403" |
| "Fast response" | "List API p95 < 200ms" |
| "Use JwtFilter class" | "API requests must be authenticated via JWT" |
| "Appropriate tech stack" | "Spring Security 6, JJWT 0.12" |
