# Multi-Agent Dev System - 시스템 개요

## 목적

여러 AI 에이전트가 협업하여 소프트웨어 개발 작업을 자동으로 수행하는 파이프라인 시스템.

사람은 기획 단계(Phase 0)에서 Claude Code와 대화하며 `planning-spec.md`를 작성하고, 이후 모든 구현·리뷰·테스트·비교·통합은 에이전트들이 자동으로 수행한다. 결과물로 생성된 브랜치를 사람이 확인 후 수동으로 머지한다.

---

## 전체 파이프라인

```
[Phase 0]  사람 + Claude Code → planning-spec.md 작성
    |
    | (completed/ 로 이동 또는 run 명령 직접 실행)
    v
[Validation]
    - 기획서 형식 검증 (규칙 기반, AI 비용 없음)
    - strict_mode: true이면 실패 시 파이프라인 중단
    |
    v
[Git Setup]
    - target_repo 있음: git clone / git fetch + reset --hard
    - target_repo 없음: .cache/{project}/ 에 git init + 빈 초기 커밋
    |
    v
[Project Analysis]
    - Python 정적 분석, AI 비용 없음, ~1초 소요
    - 프로젝트 구조·기술 스택·모듈 목록 분석
    - .project-profile.json 생성 (commit SHA 기반 캐싱)
    - 기획서 키워드와 연관된 모듈의 핵심 코드 추출
    - project-context.md 저장 (에이전트가 Read 도구로 참조)
    |
    v
[Phase 1: Architect]
    - 입력: planning-spec.md + project-context.md
    - N개 구현 접근법 상세 설계
    - 출력: architect/approaches.json
    |
    v
[Checkpoint]                        ← checkpoint_phase1: true 일 때 활성화
    - approaches.json 사용자 검토
    - 개별 approach 승인/반려 가능 (N≥2)
    - python3 cli.py approve {task-id} 로 승인
    |
    v
[Phase 2: Implementer × N]          ← ThreadPoolExecutor 병렬 실행
    - 각 approach를 독립 git worktree에서 구현
    - 브랜치: task-{id}/impl-1, task-{id}/impl-2, ...
    - 구현 완료 후 변경 사항 커밋
    - 출력: 코드 커밋 + .multi-agent/summary.json
    |
    v
[Phase 3: Reviewer + Tester × N]    ← ThreadPoolExecutor 병렬 실행
    - enable_review: true → Reviewer 실행
    - enable_test: true  → Tester 실행
    - 둘 다 false이면 Phase 3 건너뜀
    - Reviewer 출력: review-N/review.md
    - Tester 출력:  test-N/test-results.json
    |
    v
[Phase 4: Comparator 또는 Integrator]
    - alternative 모드 (N≥2): Comparator → comparison.md
    - concern 모드:            Integrator → integrated/ worktree
    - N=1 alternative:         Phase 4 건너뛰고 바로 evaluation-result.md
    |
    v
[Simplifier]                        ← enable_simplifier: true 일 때 실행
    - 선택된 구현의 코드 정리·최적화
    - 중복 제거, 불필요한 주석 삭제, 스타일 통일
    |
    v
[완료]
    - evaluation-result.md 생성
    - 사용자가 수동으로 원하는 브랜치 머지
```

---

## Phase 별 상세

### Phase 0: 기획 (사람 + Claude Code)

`planning/in-progress/{기능명}/` 디렉토리에서 Claude Code와 대화하며 기획서를 작성한다. 완성 후 `completed/`로 이동하면 파이프라인이 시작된다.

- **역할**: 무엇을(What)과 왜(Why)를 정의. 어떻게(How)는 에이전트가 결정
- **출력**: `planning-spec.md`

### Phase 1: 설계 (Architect)

기획서와 프로젝트 컨텍스트를 분석하여 N개 구현 접근법을 상세 설계한다.

- **입력**: `planning-spec.md`, `project-context.md`
- **결정 사항**: 각 approach의 기술 스택, 파일 구조, 핵심 설계 포인트
- **출력**: `architect/approaches.json`

`approaches.json` 구조:
```json
{
  "n": 2,
  "pipeline_mode": "alternative",
  "approaches": [
    {
      "id": 1,
      "name": "방법명",
      "summary": "한 문장 요약",
      "tech_stack": ["Spring Security", "JJWT"],
      "key_decisions": ["결정1", "결정2"],
      "estimated_complexity": "medium"
    }
  ]
}
```

### Phase 2: 구현 (Implementer × N)

N개의 Implementer가 각자 독립된 git worktree에서 병렬로 구현한다.

- **격리**: 각 구현체는 `task-{id}/impl-N` 브랜치에서 작업 → 파일 충돌 없음
- **컨텍스트**: `project-context.md`를 Read 도구로 참조 (프롬프트 직접 삽입 대신 파일 참조로 토큰 절감)
- **출력**: 커밋된 코드 + `.multi-agent/summary.json`

### Phase 3: 리뷰 + 테스트 (Reviewer + Tester × N)

각 구현체에 대해 Reviewer와 Tester가 병렬로 실행된다. 각각 `enable_review`, `enable_test`로 독립 제어.

**Reviewer** — 5가지 관점으로 코드 리뷰:
1. 코드 품질 (가독성, 일관성, 구조)
2. 설계 (SOLID, 패턴, 아키텍처 적합성)
3. 보안 (인젝션, 인증/인가, 민감 데이터)
4. 성능 (N+1, 불필요한 연산, 캐싱)
5. 테스트 용이성

**Tester** — 테스트 작성·실행·결과 분석:
- 단위 테스트 작성 및 실행
- 실행 결과와 커버리지 분석
- 실패 케이스 원인 파악

### Phase 4: 비교 또는 통합

**Alternative 모드** (N≥2):
- Comparator가 N개 구현을 리뷰·테스트 결과 기반으로 비교·순위·추천
- 출력: `comparator/comparison.md`, `evaluation-result.md`

**Concern 모드**:
- Integrator가 N개 구현을 하나의 통합 브랜치(`task-{id}/integrated`)로 합침
- 충돌 해결, 글루 코드 작성, 인터페이스 통일
- 출력: `integrated/` worktree, `evaluation-result.md`

---

## 적응형 N값

기획서의 `탐색할 방법 개수` 항목 또는 `config.yaml`의 `pipeline.num_approaches`로 결정된다. 기획서 값이 우선한다.

| 값 | 동작 |
|----|------|
| `1` | 단일 구현. Phase 4 생략 |
| `2` | 2개 병렬 구현 + Comparator/Integrator |
| `3` | 3개 병렬 구현 + Comparator/Integrator |
| `자동` | Architect가 기획서 복잡도 기반으로 1~3 자동 결정 |

복잡도 판단 기준:

| 상황 | 권장 N |
|------|--------|
| 버그 수정, 단순 변경 | 1 |
| 일반 기능 개발 | 2 |
| 아키텍처 결정, 기술 스택 선택, 시스템 간 통합 | 3 |

---

## 파이프라인 모드

기획서의 `파이프라인 모드` 항목으로 지정. 미지정 시 `alternative`.

### Alternative 모드 (기본)

각 approach가 동일한 목표를 다른 방식으로 구현하는 독립적 대안. Comparator가 최적을 선택한다.

```
Architect (N개 설계) → Implementer × N (독립 구현) → Reviewer/Tester × N → Comparator → 1개 추천
```

### Concern 모드

각 approach가 서로 다른 관심사를 담당하는 보완적 구현. Integrator가 모두 합친다.

예: approach-1 = 인증 모듈, approach-2 = 비즈니스 로직 모듈

```
Architect (N개 관심사 설계) → Implementer × N (각 관심사 구현) → Reviewer/Tester × N → Integrator → 통합 코드
```

---

## 프로젝트 사전 분석

Python 기반 정적 분석, AI 토큰 소모 없음.

**Static Profile** (`.project-profile.json`):
- 커밋 SHA 기반 캐싱 → 코드 변경 없으면 재분석 없음
- 프로젝트 구조, 기술 스택, 주요 모듈 목록
- 언어·프레임워크 자동 감지

**Dynamic Context** (`project-context.md`):
- 기획서 키워드로 연관 모듈 탐색
- 해당 모듈의 핵심 코드·인터페이스만 추출
- 에이전트 프롬프트에 직접 삽입하지 않고 파일 경로로 전달 (토큰 절감)

---

## 신규 프로젝트 지원

`config.yaml`의 `target_repo`를 비워두면 GitHub 레포 없이 새 프로젝트를 시작할 수 있다.

```yaml
projects:
  new-module:
    target_repo: ""   # 빈 값 → 로컬 git 저장소 자동 초기화
    default_branch: "main"
```

1. 첫 실행 시 `.cache/{project}/`에 `git init` + 빈 초기 커밋 생성
2. 이후 동일한 worktree 기반 파이프라인 실행
3. 구현 완료 후 사용자가 원하는 원격 레포에 수동 push

---

## 상태 관리 파일

파이프라인 실행 중 생성되는 상태 파일들은 모두 `work/task-{id}/`에 저장된다.

| 파일 | 설명 |
|------|------|
| `manifest.json` | 태스크 메타데이터. 현재 단계, N값, 파이프라인 모드, 각 Phase 상태 |
| `timeline.log` | Phase 전환 타임라인. `[PHASE] phase1_start`, `[ERROR] ...` 형식 |
| `project-profile.json` | 프로젝트 정적 분석 결과 캐시 |
| `project-context.md` | 에이전트에게 전달되는 프로젝트 컨텍스트 |
| `architect/approaches.json` | Architect가 설계한 N개 접근법 |
| `evaluation-result.md` | 최종 평가 결과 및 추천 |

파일 기반 상태 관리이므로 프로세스가 재시작되어도 복구 가능하다.

---

## 에러 핸들링

### Phase 실패 시
1. `timeline.log`에 에러 기록
2. 시스템 알림 발송 (`notifications.enabled: true` 설정 시)
3. `manifest.json`의 해당 Phase 상태를 `failed`로 업데이트
4. 파이프라인 중단

재실행은 수동으로: `python3 cli.py run -s {spec경로}`

### Claude 실행 타임아웃
- `execution.timeout` 초 초과 시 프로세스 종료
- `execution.max_retries` 횟수까지 자동 재시도
- 재시도 소진 시 해당 Phase 실패 처리

### 체크포인트 타임아웃
- `queue.checkpoint_timeout` 초 동안 승인 없으면 파이프라인 중단
- 기본값: 3600초 (1시간)
