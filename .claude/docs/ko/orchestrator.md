# Orchestrator 설계

## 역할

파이프라인 전체의 제어 흐름을 담당하는 시스템 코어.
에이전트 생성/실행, Phase 전환, 상태 관리, 체크포인트, 에러 핸들링 수행.

---

## 핵심 컴포넌트

| 파일 | 역할 |
|------|------|
| `orchestrator/main.py` | Orchestrator 클래스. 파이프라인 전체 실행 |
| `orchestrator/executor.py` | ClaudeExecutor. Claude Code CLI 서브프로세스 관리 |
| `orchestrator/stream_processor.py` | Claude CLI의 NDJSON 출력 파싱 |
| `orchestrator/permission_handler.py` | 도구 권한 평가 (allow/deny/ask) |
| `orchestrator/skill_loader.py` | `skills/*.md`에서 스킬 정의 로드 |
| `orchestrator/schema_validator.py` | JSON 출력을 스키마로 검증 |
| `orchestrator/agent_registry.py` | 에이전트 ↔ 스킬 ↔ 스키마 매핑 |
| `orchestrator/watcher.py` | `planning/completed/` 폴더 감시 |
| `orchestrator/queue/` | 질문 큐 시스템 (thread-safe, file-backed) |
| `orchestrator/tui/` | TUI 대시보드 (Textual 기반) |
| `orchestrator/utils/` | git 관리, 프로젝트 분석, 기획서 파싱 등 |

---

## Harness 모듈

### SkillLoader (`orchestrator/skill_loader.py`)

`skills/skill-{name}.md`에서 스킬 정의를 로드하고 캐싱.

```python
loader = SkillLoader(Path("skills"))
skill = loader.load("architect")
# skill.name, skill.description, skill.body, skill.path
```

- YAML frontmatter (name, description) + markdown body 파싱
- 세션 내 캐싱
- 파일 미존재 시 `FileNotFoundError`, frontmatter 오류 시 `ValueError`

### SchemaValidator (`orchestrator/schema_validator.py`)

`schemas/*.schema.json` 기반으로 JSON 데이터 검증.

```python
validator = SchemaValidator(Path("schemas"), mode="warn")
result = validator.validate(data, "approaches")
# result.valid, result.errors, result.schema_name
```

- **warn 모드**: 검증 오류 로깅 후 계속
- **strict 모드**: `jsonschema.ValidationError` 발생
- `jsonschema` 패키지 미설치 시 graceful skip

### AgentRegistry (`orchestrator/agent_registry.py`)

에이전트 이름 ↔ 스킬 파일 ↔ 출력 스키마 ↔ 프롬프트 경로 매핑.

```python
registry = AgentRegistry(skills_dir, schemas_dir, prompts_dir)
registry.get_prompt_path("architect")      # skills/skill-architect.md
registry.validate_output("architect", data) # ValidationResult
registry.list_pipeline_order()             # ['planner', 'pm', 'architect', ...]
```

프롬프트 해석 우선순위: skill 파일 → 레거시 프롬프트 fallback.

---

## 파이프라인 실행 흐름

```python
# Orchestrator.run_from_spec(spec_path) 내부 흐름

1. validate_spec(spec_path)                    # 기획서 검증
2. git_manager.setup(project_config)           # clone/fetch 또는 git init
3. project_analyzer.analyze(repo_path)         # 정적 분석 → project-context.md
4. architect_agent.run(spec, context)          # Phase 1
5. checkpoint(approaches_json)                 # 사용자 승인 대기
6. ThreadPoolExecutor: implementer x N         # Phase 2 병렬
7. ThreadPoolExecutor: reviewer + tester x N   # Phase 3 병렬
8. comparator.run() 또는 integrator.run()      # Phase 4
9. simplifier.run() (선택적)                   # Phase 5
10. write(evaluation-result.md)                # 최종 결과
```

---

## 실행 모드

### Watch 모드
```bash
python3 cli.py watch
```
`watch.dirs`에 등록된 경로 감시. `completed/`에 기획서 도착 시 자동 실행.

### Run 모드 (직접 실행)
```bash
python3 cli.py run -s {spec경로} [--workspace {서비스}] [--project {키}]
```

### TUI 대시보드
```bash
python3 cli.py run -s {spec경로} -v
```
`-v` 플래그로 Textual 기반 대화형 터미널 UI 활성화.

---

## config.yaml

```yaml
github_tokens:
  personal: "ghp_xxx"

workspaces:
  {서비스}:
    path: ./workspaces/{서비스}
    projects:
      {키}:
        target_repo: "https://github.com/user/repo.git"
        default_branch: "main"
        github_token: "personal"

prompts:
  directory: ./prompts

skills:
  directory: ./skills

schemas:
  directory: ./schemas
  validation_mode: warn            # "strict" 또는 "warn"

execution:
  timeout: 600
  max_retries: 3

pipeline:
  checkpoint_phase1: true
  num_approaches: 1
  enable_review: true
  enable_test: true
  enable_simplifier: true

watch:
  dirs:
    - workspace: "{서비스}"
      path: ./workspaces/{서비스}/planning/completed

validation:
  enabled: true
  strict_mode: false

permissions:
  allow: ["Read(*)", "Glob(*)", "Grep(*)"]
  deny: ["Bash(rm -rf *)", "Bash(sudo *)"]
  ask: ["Bash(*)", "Write(*)"]
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

## 상태 추적

### manifest.json

`work/task-{id}/manifest.json`에 태스크 실행 상태 기록.

```json
{
  "task_id": "task-20260317-143000",
  "stage": "phase2_implementation",
  "phases": {
    "validation": { "status": "completed" },
    "phase1": { "status": "completed", "num_approaches": 2 },
    "phase2": { "status": "in_progress" }
  },
  "checkpoints": {
    "requirements": { "status": "done", "doc": "docs/requirements.json" },
    "execution_plan": { "status": "done", "doc": "docs/execution-plan.json" },
    "approaches": { "status": "done", "doc": "docs/approaches.json" }
  }
}
```

### timeline.log

```
2026-03-17T14:30:00 [PHASE] validation_start
2026-03-17T14:30:01 [PHASE] validation_done
2026-03-17T14:30:17 [PHASE] phase1_architect_start
2026-03-17T14:35:20 [PHASE] phase1_architect_done {"approaches_count": 2}
2026-03-17T14:38:45 [EVENT] user_approved {"approaches": [1, 2]}
```

---

## 체크포인트 시스템

`checkpoint_phase1: true`일 때 Phase 1 완료 후 대기.

```bash
python3 cli.py approve {task-id}
python3 cli.py approve {task-id} --approaches 1,2
python3 cli.py approve {task-id} --reject 3
```

`checkpoint_timeout` 초과 시 파이프라인 자동 중단 (기본 3600초).

---

## 권한 관리

규칙 평가 순서: `deny` → `allow` → `ask` → 기본값(`ask`).

| 도구 | 매칭 필드 |
|------|-----------|
| `Bash` | `command` |
| `Write`, `Edit`, `Read` | `file_path` |
| `Glob`, `Grep` | `pattern` |

---

## 질문 큐

N개 병렬 에이전트의 모든 질문을 단일 큐로 통합.

| 유형 | 발생 시점 | 기본 타임아웃 |
|------|-----------|---------------|
| `permission` | 도구 사용 승인 | 300초 |
| `checkpoint` | Phase 전환 승인 | 3600초 |
| `error` | 에이전트 오류 | 3600초 |

파일 기반 큐 (`work/task-{id}/queue/`) → TUI/CLI 재시작 후에도 유지.
