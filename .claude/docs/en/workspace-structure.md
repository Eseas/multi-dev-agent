# Workspace Structure

## Concept

One **service** = one **workspace**.

A service is a business unit, not a technical unit (FE/BE). Frontend, backend, DB, notification server, etc. are all sub-projects (Root Projects) within the same service.

---

## Directory Layout

```
multi-agent-dev-system/
│
├── orchestrator/              # Pipeline core
├── skills/                    # Skill definitions (skill-*.md)
├── schemas/                   # JSON Schema definitions (*.schema.json)
├── scripts/                   # Utility scripts (json_to_md.py, etc.)
├── prompts/                   # Legacy agent prompts (fallback)
├── config.yaml                # System configuration
│
└── workspaces/
    └── {service}/
        │
        ├── {service}-BE/              # Root Project: backend repo clone
        ├── {service}-FE/              # Root Project: frontend repo clone (optional)
        │
        ├── .cache/                    # Auto-managed (do not edit)
        │   └── {service}-BE/.git/     #   bare clone or local init
        │
        ├── planning/
        │   ├── in-progress/           # Specs being drafted
        │   │   └── {feature}/
        │   │       └── planning-spec.md
        │   └── completed/             # Completed specs (auto-triggers pipeline)
        │       └── {feature}/
        │           └── planning-spec.md
        │
        └── work/
            └── task-{timestamp}/      # Task execution directory
                ├── manifest.json
                ├── timeline.log
                ├── docs/              # All JSON artifacts
                │   ├── requirements.json
                │   ├── execution-plan.json
                │   ├── approaches.json
                │   ├── api-contract.json        (concern mode)
                │   ├── impl-1-review.json
                │   ├── impl-1-test-results.json
                │   ├── impl-2-review.json
                │   ├── impl-2-test-results.json
                │   ├── comparison.json           (alternative mode)
                │   ├── integration-report.json   (concern mode)
                │   └── impl-N-simplification.json
                ├── implementations/
                │   ├── impl-1/        # git worktree (branch: task-{id}/impl-1)
                │   │   └── (full project code + work-done.json)
                │   └── impl-2/        # git worktree (branch: task-{id}/impl-2)
                │       └── (full project code + work-done.json)
                └── evaluation-result.md
```

---

## Root Project Folders

Cloned from the actual GitHub repository's main/master branch.

- Naming: `{service}-{component}` (e.g. `myapp-BE`, `myapp-FE`)
- Always synced with remote (auto `git fetch + reset --hard` before task)
- Agents reference these files for code context

### Monorepo
Single folder `{service}/` with FE/BE as subdirectories.

### Multiple repos
```
workspaces/{service}/
├── {service}-BE/
├── {service}-FE-Web/
├── {service}-FE-Admin/
└── {service}-Worker/
```

---

## .cache Folder

Auto-managed git repository cache. **Do not edit manually.**

- Existing repo: `git clone --bare` → `git fetch` + `git reset --hard`
- New project (`target_repo: ""`): `git init` + empty commit

---

## Planning Folder Lifecycle

```
planning/in-progress/{feature}/planning-spec.md   ← Drafting
    |
    | mv to completed/
    v
planning/completed/{feature}/planning-spec.md     ← Orchestrator detects
    |
    v
work/task-{timestamp}/                             ← Pipeline starts
```

---

## Workspace Setup

### Adding a new service

1. Create directories:
```bash
mkdir -p workspaces/{service}/planning/{in-progress,completed}
```

2. Clone repos (if existing):
```bash
git clone {be-repo-url} workspaces/{service}/{service}-BE
```

3. Update config.yaml:
```yaml
workspaces:
  {service}:
    path: ./workspaces/{service}
    projects:
      be:
        target_repo: "{be-repo-url}"
        default_branch: "main"
        github_token: "personal"
```

4. New project (no repo): set `target_repo: ""`.
