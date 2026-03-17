# Orchestrator 설계

## 역할

전체 파이프라인의 제어 흐름을 담당하는 시스템 코어.
에이전트를 생성·실행하고, Phase 간 전환과 상태 관리를 수행한다.

## 핵심 기능

### 1. 워크스페이스 관리
- 등록된 워크스페이스 목록 관리
- 각 워크스페이스의 root project 경로 파악
- planning/completed/ 폴더 감시하여 신규 기획서 감지

### 2. 파이프라인 실행
```
감지 → Phase 1 → Phase 2 (×N 병렬) → Phase 3 → Phase 4 → Phase 5 → Phase 6
```
- 각 Phase 시작/완료 시 상태 기록
- Phase 실패 시 재시도 또는 중단 결정
- N값은 기획서에서 추출하거나 자동 판단

### 3. 상태 추적
- `manifest.json`: 작업 메타데이터 (현재 Phase, N값, 시작시간 등)
- `timeline.log`: 이벤트 타임라인
- 파일 기반 상태 → 프로세스 재시작 시 복구 가능

### 4. 알림
- Phase 전환 시 알림 발송
- 에러 발생 시 즉시 알림
- 사용자 승인 필요 시 대기 + 알림

## 실행 모드

### 자동 모드
- completed/ 폴더 감시
- 기획서 감지 시 자동으로 파이프라인 시작
- Phase 6 완료 후 사용자에게 결과 알림

### 수동 모드
- CLI 명령으로 특정 기획서 실행
- 특정 Phase만 재실행 가능
- 디버깅·테스트 용도

## manifest.json 스키마

```json
{
  "task_id": "task-20260317-143000",
  "service": "my-social-app",
  "workspace_path": "workspaces/my-social-app",
  "planning_spec": "planning/completed/add-notification/planning-spec.md",
  "root_projects": [
    "my-social-app-FE",
    "my-social-app-BE"
  ],
  "n_implementations": 2,
  "current_phase": "implementation",
  "phase_history": [
    {"phase": "architect", "status": "completed", "started": "...", "ended": "..."},
    {"phase": "implementation", "status": "in_progress", "started": "..."}
  ],
  "created_at": "2026-03-17T14:30:00",
  "updated_at": "2026-03-17T14:35:00"
}
```

## 에러 핸들링

### Phase 실패 시
1. 에러 로그 기록 (timeline.log)
2. 알림 발송
3. manifest 상태 업데이트
4. 설정에 따라 재시도 또는 대기

### 에이전트 타임아웃
- Phase별 타임아웃 설정 (config.yaml)
- 타임아웃 시 에이전트 종료 + 에러 처리

## 설정 (config.yaml)

```yaml
orchestrator:
  watch_interval: 5          # 기획서 감시 주기 (초)
  max_retries: 2             # Phase 실패 시 재시도 횟수

workspaces:
  - name: my-social-app
    path: workspaces/my-social-app
    root_projects:
      - my-social-app-FE
      - my-social-app-BE

agents:
  architect:
    timeout: 300              # 초
  implementer:
    timeout: 600
  reviewer:
    timeout: 300
  tester:
    timeout: 300
  comparator:
    timeout: 300
  integrator:
    timeout: 600

notifications:
  type: webhook              # webhook, slack, terminal
  url: https://...
```
