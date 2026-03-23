# Orchestrator 설계

## 역할

전체 파이프라인의 제어 흐름을 담당하는 시스템 코어.
에이전트를 생성·실행하고, Phase 간 전환과 상태 관리를 수행한다.

## 핵심 기능

### 1. 워크스페이스 관리
- `config.yaml`의 `workspaces` 레지스트리에서 서비스·프로젝트 정보 로드
- `watch.dirs` 설정의 경로를 감시하여 신규 기획서 감지
- 각 워크스페이스의 `planning/completed/` 폴더에 파일이 생기면 자동 실행

### 2. 파이프라인 실행

```
Validation → Git Setup → Project Analysis
→ Phase 1 (Architect)
→ [Checkpoint]
→ Phase 2 (Implementer × N, 병렬)
→ Phase 3 (Reviewer + Tester × N, 병렬)
→ Phase 4 (Comparator 또는 Integrator)
→ [Simplifier]
→ evaluation-result.md 생성
```

- Phase 2, 3은 `ThreadPoolExecutor`로 병렬 실행
- 각 Phase 시작/완료 시 상태 기록 + 시스템 알림
- Phase 실패 시 에러 로그 기록 후 중단

### 3. 상태 추적
- `manifest.json`: 작업 메타데이터 (현재 단계, N값, Phase 이력 등)
- `timeline.log`: Phase 전환 타임라인
- 파일 기반 상태 → 프로세스 재시작 시 복구 가능

### 4. 체크포인트 (Phase 1 후)
- Architect 완료 후 `approaches.json` 생성
- 파일 감시로 사용자 승인 신호 대기
- CLI에서 `python3 cli.py approve <task-id>` 로 승인
- N≥2인 경우 개별 approach 승인/반려 가능

## 실행 모드

### 자동 모드 (Watch)
```bash
python3 cli.py watch
```
- `watch.dirs` 경로를 주기적으로 감시
- 기획서 감지 시 해당 워크스페이스의 프로젝트 설정으로 자동 실행

### 수동 모드 (Run)
```bash
python3 cli.py run -s <planning-spec.md 경로> [--workspace <name>] [--project <name>]
```
- 특정 기획서를 직접 실행
- `--workspace`, `--project`로 대상 프로젝트 명시 가능

## config.yaml 스키마

```yaml
github_tokens:                         # 토큰 레지스트리 (키: 토큰값)
  personal: "ghp_xxxxxxxxxxxx"
  work: "ghp_yyyyyyyyyyyy"

workspaces:                            # 서비스 레지스트리
  my-service:                          #   서비스명
    path: ./workspaces/my-service      #   워크스페이스 경로
    projects:                          #   프로젝트(레포) 목록
      be:                              #     프로젝트 키
        target_repo: "https://github.com/user/my-service-BE.git"
        default_branch: "main"
        github_token: "personal"       #     github_tokens의 키 이름
      fe:
        target_repo: "https://github.com/user/my-service-FE.git"
        default_branch: "main"
        github_token: "personal"
      new-module:
        target_repo: ""               #     비워두면 신규 프로젝트 모드 (로컬 git init)
        default_branch: "main"

prompts:
  directory: ./prompts                 # 에이전트 프롬프트 템플릿 경로

execution:
  timeout: 600                         # Claude 실행 타임아웃 (초)
  max_retries: 3

pipeline:
  checkpoint_phase1: true              # Phase 1 후 체크포인트 활성화
  num_approaches: 1                    # 기본 구현 개수 (기획서에서 오버라이드 가능)
  enable_review: true                  # Phase 3: Reviewer 활성화
  enable_test: true                    # Phase 3: Tester 활성화
  enable_simplifier: true             # Simplifier 활성화

watch:
  dirs:
    - workspace: "my-service"          # workspaces 키 이름
      path: ./workspaces/my-service/planning/completed

validation:
  enabled: true
  auto_revalidate: true
  strict_mode: false                   # true이면 검증 실패 시 중단

permissions:                           # Claude 도구 권한 규칙
  allow:                               #   자동 허용
    - "Read(*)"
    - "Glob(*)"
    - "Grep(*)"
  deny:                                #   자동 거부
    - "Bash(rm -rf *)"
    - "Bash(sudo *)"
  ask:                                 #   사용자 승인 필요
    - "Bash(*)"
    - "Write(*)"
  ask_timeout: 300

queue:
  default_timeout: 3600               # 기본 질문 타임아웃 (초)
  permission_timeout: 300             # 권한 질문 타임아웃
  checkpoint_timeout: 3600           # 체크포인트 타임아웃

notifications:
  enabled: true
  sound: true
```

## manifest.json 스키마

```json
{
  "task_id": "task-20260317-143000",
  "spec_path": "workspaces/my-service/planning/completed/add-auth/planning-spec.md",
  "created_at": "2026-03-17T14:30:00",
  "updated_at": "2026-03-17T14:35:00",
  "stage": "phase2_implementation",
  "n_implementations": 2,
  "pipeline_mode": "alternative",
  "phases": {
    "validation": { "status": "completed" },
    "git_setup": { "status": "completed" },
    "project_analysis": { "status": "completed" },
    "phase1_architect": { "status": "completed", "approaches_count": 2 },
    "phase2_implementation": { "status": "in_progress" },
    "phase3_review_test": { "status": "pending" },
    "phase4_compare": { "status": "pending" }
  }
}
```

## 에러 핸들링

### Phase 실패 시
1. 에러 로그 기록 (`timeline.log`)
2. 시스템 알림 발송
3. `manifest.json` 상태를 `failed`로 업데이트
4. 파이프라인 중단 (재시도는 수동으로)

### Claude 실행 타임아웃
- `execution.timeout` 초과 시 프로세스 종료 + 에러 처리
- `execution.max_retries` 횟수만큼 자동 재시도 후 실패 처리

### 체크포인트 타임아웃
- `queue.checkpoint_timeout` 초 동안 승인 없으면 파이프라인 중단
