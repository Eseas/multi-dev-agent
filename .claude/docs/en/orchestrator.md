# Orchestrator Design

## Role

System core that controls the entire pipeline flow.
Creates and executes agents, manages phase transitions, state tracking,
checkpoints, and error handling.

---

## Core Components

| File | Role |
|------|------|
| `orchestrator/main.py` | Orchestrator class. Full pipeline execution |
| `orchestrator/executor.py` | ClaudeExecutor. Claude Code CLI subprocess management |
| `orchestrator/stream_processor.py` | NDJSON stream parser for Claude CLI output |
| `orchestrator/permission_handler.py` | Tool permission evaluation (allow/deny/ask) |
| `orchestrator/skill_loader.py` | Loads skill definitions from `skills/*.md` |
| `orchestrator/schema_validator.py` | Validates JSON outputs against schemas |
| `orchestrator/agent_registry.py` | Maps agents to skills, schemas, and prompts |
| `orchestrator/watcher.py` | File watcher for `planning/completed/` |
| `orchestrator/queue/` | Question queue (thread-safe, file-backed) |
| `orchestrator/tui/` | TUI dashboard (Textual-based) |
| `orchestrator/utils/` | Git management, project analysis, spec parsing |

---

## Harness Modules

### SkillLoader (`orchestrator/skill_loader.py`)

Loads and caches skill definitions from `skills/skill-{name}.md`.

```python
loader = SkillLoader(Path("skills"))
skill = loader.load("architect")
# skill.name, skill.description, skill.body, skill.path

loader.list_skills()   # ['architect', 'comparator', 'implementer', ...]
loader.load_all()      # Dict[str, SkillDefinition]
```

- Parses YAML frontmatter (name, description) and markdown body
- Caches loaded skills per session
- Raises `FileNotFoundError` if skill file missing, `ValueError` if frontmatter invalid

### SchemaValidator (`orchestrator/schema_validator.py`)

Validates JSON data against JSON Schema files in `schemas/*.schema.json`.

```python
validator = SchemaValidator(Path("schemas"), mode="warn")
result = validator.validate(data, "approaches")
# result.valid, result.errors, result.schema_name

validator.validate_file(Path("docs/approaches.json"), "approaches")
```

- **warn mode**: logs validation errors, continues
- **strict mode**: raises `jsonschema.ValidationError`
- Gracefully skips if `jsonschema` package not installed

### AgentRegistry (`orchestrator/agent_registry.py`)

Central mapping between agent names, skill files, output schemas, and prompt paths.

```python
registry = AgentRegistry(
    skills_dir=Path("skills"),
    schemas_dir=Path("schemas"),
    prompts_dir=Path("prompts"),
    validation_mode="warn",
)

registry.get_prompt_path("architect")      # skills/skill-architect.md
registry.get_skill("architect")            # SkillDefinition
registry.validate_output("architect", data) # ValidationResult
registry.get_checkpoint_key("architect")   # "approaches"
registry.list_pipeline_order()             # ['planner', 'pm', 'architect', ...]
```

Prompt resolution priority: skill file → legacy prompt fallback.

---

## Pipeline Execution Flow

```python
# Orchestrator.run_from_spec(spec_path) internal flow

1. validate_spec(spec_path)                    # Spec validation
2. git_manager.setup(project_config)           # Clone/fetch or git init
3. project_analyzer.analyze(repo_path)         # Static analysis → project-context.md
4. architect_agent.run(spec, context)          # Phase 1
5. checkpoint(approaches_json)                 # User approval
6. ThreadPoolExecutor: implementer x N         # Phase 2 parallel
7. ThreadPoolExecutor: reviewer + tester x N   # Phase 3 parallel
8. comparator.run() or integrator.run()        # Phase 4
9. simplifier.run() (optional)                 # Phase 5
10. write(evaluation-result.md)                # Final result
```

Phase 2 and 3 use `concurrent.futures.ThreadPoolExecutor` for parallel execution.
Each phase start/completion is logged to `timeline.log` and triggers system notifications.

---

## Execution Modes

### Watch Mode
```bash
python3 cli.py watch
```
Monitors `watch.dirs` paths. Auto-triggers pipeline when specs appear in `completed/`.

### Run Mode (direct)
```bash
python3 cli.py run -s {spec_path} [--workspace {service}] [--project {key}]
```

### TUI Dashboard
```bash
python3 cli.py run -s {spec_path} -v
python3 cli.py watch -v
```
`-v` flag activates Textual-based interactive terminal UI.

---

## config.yaml

```yaml
github_tokens:
  personal: "ghp_xxx"

workspaces:
  {service}:
    path: ./workspaces/{service}
    projects:
      {key}:
        target_repo: "https://github.com/user/repo.git"
        default_branch: "main"
        github_token: "personal"

prompts:
  directory: ./prompts

skills:
  directory: ./skills

schemas:
  directory: ./schemas
  validation_mode: warn            # "strict" or "warn"

execution:
  timeout: 600
  max_retries: 3

pipeline:
  checkpoint_phase1: true
  num_approaches: 1                # Default N (execution-plan overrides)
  enable_review: true
  enable_test: true
  enable_simplifier: true

watch:
  dirs:
    - workspace: "{service}"
      path: ./workspaces/{service}/planning/completed

validation:
  enabled: true
  auto_revalidate: true
  strict_mode: false

permissions:
  allow:
    - "Read(*)"
    - "Glob(*)"
    - "Grep(*)"
  deny:
    - "Bash(rm -rf *)"
    - "Bash(sudo *)"
  ask:
    - "Bash(*)"
    - "Write(*)"
  ask_timeout: 300

queue:
  default_timeout: 3600
  permission_timeout: 300
  checkpoint_timeout: 3600

notifications:
  enabled: true
  sound: true
```

---

## State Tracking

### manifest.json

Tracks task execution state in `work/task-{id}/manifest.json`.

```json
{
  "task_id": "task-20260317-143000",
  "spec_path": "...",
  "created_at": "2026-03-17T14:30:00",
  "stage": "phase2_implementation",
  "phases": {
    "validation": { "status": "completed" },
    "phase1": { "status": "completed", "num_approaches": 2, "pipeline_mode": "alternative" },
    "phase2": { "status": "in_progress", "implementations": [...] },
    "phase3": { "status": "pending" },
    "phase4": { "status": "pending" }
  },
  "checkpoints": {
    "requirements":    { "status": "done", "doc": "docs/requirements.json" },
    "execution_plan":  { "status": "done", "doc": "docs/execution-plan.json" },
    "approaches":      { "status": "done", "doc": "docs/approaches.json" }
  },
  "updated_at": "2026-03-17T14:35:00"
}
```

### timeline.log

```
2026-03-17T14:30:00 [PHASE] validation_start
2026-03-17T14:30:01 [PHASE] validation_done
2026-03-17T14:30:17 [PHASE] phase1_architect_start
2026-03-17T14:35:20 [PHASE] phase1_architect_done {"approaches_count": 2}
2026-03-17T14:38:45 [EVENT] user_approved {"approaches": [1, 2]}
2026-03-17T14:38:45 [PHASE] phase2_impl_start
...
```

---

## Checkpoint System

When `checkpoint_phase1: true`, pipeline pauses after Phase 1.

### Approval Flow
1. Architect generates `approaches.json`
2. Orchestrator sets manifest to `checkpoint_pending`
3. System notification sent
4. User approves via CLI

```bash
python3 cli.py approve {task-id}
python3 cli.py approve {task-id} --approaches 1,2
python3 cli.py approve {task-id} --reject 3
```

5. Orchestrator detects approval and starts Phase 2

### Timeout
`queue.checkpoint_timeout` seconds without response → pipeline halts.

---

## ClaudeExecutor

Executes Claude Code CLI as subprocess with stream-json protocol.

```bash
claude --input-format stream-json --output-format stream-json --verbose
```

### Stream Processing
NDJSON events: `content_block_start`, `content_block_delta`, `tool_use`, `result`.
StreamEventProcessor parses events, accumulates text, tracks tool usage.

### Permission Handler
Rule evaluation order: `deny` → `allow` → `ask` → default (`ask`).
More specific deny always overrides broader allow.

| Tool | Match field |
|------|-------------|
| `Bash` | `command` |
| `Write`, `Edit`, `Read` | `file_path` |
| `Glob`, `Grep` | `pattern` |

---

## Question Queue

Unifies all questions from N parallel agents into a single queue.

| Type | Trigger | Default timeout |
|------|---------|-----------------|
| `permission` | Tool use approval | 300s |
| `checkpoint` | Phase transition | 3600s |
| `error` | Agent execution error | 3600s |

Queue is file-backed (`work/task-{id}/queue/`), survives TUI/CLI restart.
