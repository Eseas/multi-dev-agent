# Orchestrator 설계

## 역할

전체 파이프라인의 제어 흐름을 담당하는 시스템 코어.
에이전트를 생성·실행하고, Phase 간 전환, 상태 관리, 체크포인트, 에러 핸들링을 수행한다.

---

## 핵심 컴포넌트

| 파일 | 역할 |
|------|------|
| `orchestrator/main.py` | Orchestrator 클래스. 파이프라인 전체 실행 |
| `orchestrator/executor.py` | ClaudeExecutor. Claude Code CLI 프로세스 실행 및 스트림 처리 |
| `orchestrator/permission_handler.py` | 도구 권한 평가 (allow/deny/ask) 및 사용자 승인 흐름 |
| `orchestrator/stream_processor.py` | Claude CLI의 NDJSON 출력 파싱 |
| `orchestrator/watcher.py` | `planning/completed/` 폴더 파일 감시 |
| `orchestrator/queue/` | 질문 큐 시스템 (thread-safe, file-backed) |
| `orchestrator/tui/` | TUI 대시보드 (Textual 기반) |
| `orchestrator/utils/` | git 관리, 프로젝트 분석, 기획서 파싱 등 |

---

## 파이프라인 실행 흐름

```python
# Orchestrator.run_task(spec_path) 내부 흐름

1. spec_validator.validate(spec_path)          # 기획서 검증
2. git_manager.setup(project_config)           # clone/fetch 또는 git init
3. project_analyzer.analyze(repo_path)         # 정적 분석 → project-context.md
4. architect_agent.run(spec, context)          # Phase 1
5. checkpoint(approaches_json)                 # 사용자 승인 대기
6. ThreadPoolExecutor: implementer × N         # Phase 2 병렬
7. ThreadPoolExecutor: reviewer + tester × N   # Phase 3 병렬
8. comparator.run() 또는 integrator.run()      # Phase 4
9. simplifier.run() (선택적)                   # 후처리
10. write(evaluation-result.md)                # 최종 결과
```

Phase 2, 3은 `concurrent.futures.ThreadPoolExecutor`로 병렬 실행된다.
각 Phase 시작·완료 시 `timeline.log`에 기록하고 시스템 알림을 발송한다.
Phase 실패 시 `manifest.json`을 `failed`로 업데이트하고 파이프라인을 중단한다.

---

## 실행 모드

### Watch 모드
```bash
python3 cli.py watch
```
`config.yaml`의 `watch.dirs`에 등록된 경로를 주기적으로 감시한다.
`planning/completed/`에 새 기획서가 생기면 해당 워크스페이스의 프로젝트 설정으로 자동 실행한다.

### Run 모드 (직접 실행)
```bash
python3 cli.py run -s {spec경로} [--workspace {서비스명}] [--project {프로젝트키}]
```
특정 기획서를 직접 지정하여 실행한다.
`--workspace`, `--project`를 생략하면 spec 경로에서 워크스페이스를 자동 추론한다.

### TUI 대시보드 활성화
```bash
python3 cli.py run -s {spec경로} -v
python3 cli.py watch -v
```
`-v` 플래그로 Textual 기반 대화형 터미널 UI를 활성화한다.

---

## config.yaml 전체 스키마

```yaml
# ─── GitHub 토큰 레지스트리 ───────────────────────────────────────────────────
github_tokens:
  personal: "ghp_xxxxxxxxxxxx"      # 토큰 키: 이름 (workspaces에서 참조)
  work: "ghp_yyyyyyyyyyyy"

# ─── 워크스페이스(서비스) 레지스트리 ─────────────────────────────────────────
workspaces:
  {서비스명}:
    path: ./workspaces/{서비스명}   # 워크스페이스 루트 경로

    projects:
      {프로젝트키}:                  # 프로젝트 식별자 (config 내 고유)
        target_repo: "https://github.com/user/repo.git"
        default_branch: "main"
        github_token: "personal"    # github_tokens의 키 이름

      {신규프로젝트키}:
        target_repo: ""             # 비워두면 로컬 git init (신규 프로젝트)
        default_branch: "main"

# ─── 에이전트 프롬프트 ───────────────────────────────────────────────────────
prompts:
  directory: ./prompts              # 프롬프트 템플릿 디렉토리

# ─── Claude 실행 설정 ────────────────────────────────────────────────────────
execution:
  timeout: 600                      # 에이전트 1회 실행 타임아웃 (초)
  max_retries: 3                    # 실패 시 자동 재시도 횟수

# ─── 파이프라인 설정 ─────────────────────────────────────────────────────────
pipeline:
  checkpoint_phase1: true           # Phase 1 후 체크포인트 활성화 여부
  num_approaches: 2                 # 기본 구현 개수 (기획서 값이 우선)
  enable_review: true               # Phase 3: Reviewer 실행 여부
  enable_test: true                 # Phase 3: Tester 실행 여부
  enable_simplifier: false          # Simplifier 후처리 실행 여부

# ─── Watch 모드 감시 경로 ────────────────────────────────────────────────────
watch:
  dirs:
    - workspace: "{서비스명}"       # workspaces의 키 이름
      path: ./workspaces/{서비스명}/planning/completed
    # 여러 서비스를 동시에 감시 가능
    - workspace: "{다른서비스명}"
      path: ./workspaces/{다른서비스명}/planning/completed

# ─── 기획서 검증 ─────────────────────────────────────────────────────────────
validation:
  enabled: true
  auto_revalidate: true             # 기획서 변경 시 자동 재검증
  strict_mode: false                # true이면 검증 실패 시 파이프라인 중단

# ─── 도구 권한 규칙 ──────────────────────────────────────────────────────────
permissions:
  allow:                            # 자동 허용 (사용자 확인 없이)
    - "Read(*)"
    - "Glob(*)"
    - "Grep(*)"
  deny:                             # 자동 거부
    - "Bash(rm -rf *)"
    - "Bash(sudo *)"
  ask:                              # 사용자 승인 필요
    - "Bash(*)"
    - "Write(*)"
  ask_timeout: 300                  # 승인 대기 시간 (초). 초과 시 deny

# ─── 질문 큐 타임아웃 ────────────────────────────────────────────────────────
queue:
  default_timeout: 3600             # 일반 질문 타임아웃 (초)
  permission_timeout: 300           # 권한 질문 타임아웃 (초)
  checkpoint_timeout: 3600          # 체크포인트 타임아웃 (초)

# ─── 시스템 알림 ─────────────────────────────────────────────────────────────
notifications:
  enabled: true                     # macOS/Linux/Windows 네이티브 알림
  sound: true                       # 알림 소리 여부
```

---

## 상태 추적

### manifest.json

태스크 실행 중 `work/task-{id}/manifest.json`에 상태를 기록한다.
프로세스 재시작 시 복구에 사용한다.

```json
{
  "task_id": "task-20260317-143000",
  "spec_path": "workspaces/{서비스}/planning/completed/{기능}/planning-spec.md",
  "workspace": "{서비스명}",
  "project": "{프로젝트키}",
  "created_at": "2026-03-17T14:30:00",
  "updated_at": "2026-03-17T14:35:00",
  "stage": "phase2_implementation",
  "n_implementations": 2,
  "pipeline_mode": "alternative",
  "phases": {
    "validation":           { "status": "completed", "completed_at": "..." },
    "git_setup":            { "status": "completed", "completed_at": "..." },
    "project_analysis":     { "status": "completed", "completed_at": "..." },
    "phase1_architect":     { "status": "completed", "approaches_count": 2 },
    "checkpoint":           { "status": "completed", "approved_approaches": [1, 2] },
    "phase2_implementation":{ "status": "in_progress" },
    "phase3_review_test":   { "status": "pending" },
    "phase4_compare":       { "status": "pending" }
  }
}
```

### timeline.log

```
2026-03-17T14:30:00 [PHASE] validation_start
2026-03-17T14:30:01 [PHASE] validation_done
2026-03-17T14:30:05 [PHASE] git_setup_start
2026-03-17T14:30:15 [PHASE] git_setup_done
2026-03-17T14:30:16 [PHASE] project_analysis_start
2026-03-17T14:30:17 [PHASE] project_analysis_done
2026-03-17T14:30:17 [PHASE] phase1_architect_start
2026-03-17T14:35:20 [PHASE] phase1_architect_done {"approaches_count": 2}
2026-03-17T14:35:20 [PHASE] checkpoint_start
2026-03-17T14:38:45 [EVENT] user_approved {"approaches": [1, 2]}
2026-03-17T14:38:45 [PHASE] phase2_impl_start
2026-03-17T15:05:10 [PHASE] phase2_impl_done
2026-03-17T15:05:10 [PHASE] phase3_review_test_start
2026-03-17T15:20:30 [PHASE] phase3_review_test_done
2026-03-17T15:20:30 [PHASE] phase4_compare_start
2026-03-17T15:25:00 [PHASE] phase4_compare_done
2026-03-17T15:25:00 [PHASE] pipeline_complete
```

---

## 체크포인트 시스템

`checkpoint_phase1: true`일 때 Phase 1 완료 후 파이프라인이 대기 상태가 된다.

### 승인 흐름
1. Architect가 `approaches.json` 생성
2. Orchestrator가 `manifest.json`을 `checkpoint_pending`으로 업데이트
3. 시스템 알림 발송
4. 사용자가 CLI로 승인

```bash
# 전체 승인
python3 cli.py approve {task-id}

# N≥2: 특정 approach만 승인
python3 cli.py approve {task-id} --approaches 1,2

# N≥2: 특정 approach 반려
python3 cli.py approve {task-id} --reject 3
```

5. Orchestrator가 승인 신호를 감지하고 Phase 2 시작

### 타임아웃
`queue.checkpoint_timeout` 초 동안 응답 없으면 파이프라인 자동 중단.
기본값 3600초(1시간).

---

## 권한 관리 시스템 (PermissionHandler)

### 규칙 평가 순서
`deny` → `allow` → `ask` → 기본값(`ask`)

더 구체적인 deny가 더 넓은 allow보다 항상 우선한다.

### 규칙 형식

```yaml
permissions:
  allow:
    - "Read(*)"              # Read 도구 전체 허용
    - "Bash(npm run *)"      # 특정 패턴만 허용
    - "Write(src/**)"        # 특정 경로만 허용
  deny:
    - "Bash(rm -rf *)"
    - "Bash(sudo *)"
  ask:
    - "Bash(*)"              # Bash 전체 → 사용자 승인
```

### 도구별 매칭 인자

| 도구 | 매칭 대상 필드 |
|------|---------------|
| `Bash` | `command` |
| `Write`, `Edit`, `Read` | `file_path` |
| `Glob`, `Grep` | `pattern` |
| 기타 | 첫 번째 문자열 값 |

### ask 처리 흐름

1. 에이전트가 도구 사용 요청 (`stream-json` 이벤트)
2. PermissionHandler가 `ask`로 평가
3. QuestionQueue에 질문 등록
4. TUI 또는 CLI로 사용자에게 알림
5. 사용자 응답(`allow`/`deny`) 수신
6. 응답을 에이전트에 반환

`ask_timeout` 초 초과 시 자동 `deny`.

---

## 질문 큐 (QuestionQueue)

병렬로 실행되는 N개의 에이전트가 발생시키는 모든 질문을 단일 큐로 통합하여 순차 처리한다.

### 질문 유형

| 유형 | 발생 시점 | 기본 타임아웃 |
|------|-----------|---------------|
| `permission` | 도구 사용 승인 요청 | `permission_timeout` (300s) |
| `checkpoint` | Phase 전환 시 승인 필요 | `checkpoint_timeout` (3600s) |
| `error` | 에이전트 실행 오류 | `default_timeout` (3600s) |
| `decision` | 분기 결정 필요 | `default_timeout` (3600s) |

### 큐 처리

**TUI 대시보드** (`-v` 플래그):
- 실시간 큐 목록 표시
- 키보드로 질문 선택 및 답변 입력

**CLI**:
```bash
python3 cli.py questions {task-id}           # 대기 중인 질문 목록
python3 cli.py answer {task-id} {q-id} allow  # 답변
```

큐는 파일 기반(`work/task-{id}/queue/`)으로 저장되어 TUI/CLI 재시작 후에도 유지된다.

---

## ClaudeExecutor

Claude Code CLI를 서브프로세스로 실행하고 출력을 처리하는 컴포넌트.

### 실행 방식
```bash
claude \
  --output-format stream-json \
  --allowedTools "{허용 도구 목록}" \
  --max-turns {max_turns} \
  -p "{프롬프트}"
```

### 스트림 처리 (StreamProcessor)
Claude CLI는 NDJSON 형식으로 이벤트를 출력한다.

```
{"type": "tool_use", "name": "Bash", "input": {"command": "..."}}
{"type": "tool_result", "content": "..."}
{"type": "text", "text": "..."}
{"type": "result", "stop_reason": "end_turn"}
```

StreamProcessor가 각 이벤트를 파싱하여:
- `tool_use` → PermissionHandler로 권한 평가
- `result` → 실행 완료 처리
- 오류 이벤트 → 에러 핸들링

---

## git 관리 (GitManager)

### 기존 레포가 있는 경우

```
1. git clone --bare {target_repo} .cache/{project}/
   (이미 있으면 git fetch origin)
2. git reset --hard origin/{default_branch}
3. 각 구현체마다:
   git worktree add implementations/impl-N task-{id}/impl-N
```

### 신규 프로젝트 (target_repo 비어있는 경우)

```
1. git init .cache/{project}/
2. git commit --allow-empty -m "Initial commit"
3. 이후 동일하게 worktree 생성
```

### 작업 완료 후

구현 완료 브랜치는 그대로 유지된다. 사용자가 직접:
```bash
cd workspaces/{서비스}/root-project/
git merge task-{id}/impl-1   # 원하는 브랜치 선택
```

---

## 프로젝트 분석 (ProjectAnalyzer)

Python 정적 분석, AI 토큰 소모 없음.

### Static Profile (캐싱)
- 커밋 SHA가 변경된 경우에만 재분석
- `project-profile.json` 포함 항목:
  - 디렉토리 구조 (depth 3까지)
  - 감지된 언어·프레임워크
  - 주요 설정 파일 목록
  - 모듈(패키지) 구조

### Dynamic Context (매 실행 시)
- 기획서의 키워드로 연관 모듈 탐색
- 연관 모듈의 주요 파일(인터페이스, 서비스, 컨트롤러 등) 추출
- `project-context.md`로 저장
- 에이전트 프롬프트에 경로만 전달 → 에이전트가 Read 도구로 직접 참조

---

## 기획서 검증 (SpecValidator)

기획서 형식이 파이프라인 실행에 필요한 조건을 갖추었는지 규칙 기반으로 검증한다. AI 비용 없음.

### 검증 항목
- 필수 섹션 존재 여부 (목표, 구현 방법 탐색)
- `탐색할 방법 개수` 또는 `num_approaches` 명시 여부
- N값이 1~3 범위 내인지 확인
- `파이프라인 모드`가 `alternative` 또는 `concern`인지 확인
- 각 방법(approach)에 핵심 아이디어 포함 여부

### 검증 실패 처리
- `strict_mode: false` (기본): 경고 출력 후 계속 진행
- `strict_mode: true`: 검증 실패 시 파이프라인 중단
