# 시스템 개요

## 목적

여러 AI 에이전트가 협업하여 소프트웨어 개발 작업을 자동으로 수행하는 파이프라인 시스템.

사람은 Phase 0에서 skill-planner와 대화하며 **무엇을(What)**과 **왜(Why)**를 정의한다. 이후 설계, 구현, 리뷰, 테스트, 비교, 통합은 에이전트가 자동 수행한다. 결과물로 생성된 git 브랜치를 사람이 확인 후 수동으로 머지한다.

---

## 파이프라인

```
[skill-planner]  사람 + Claude Code → requirements.json
    |
    v
[skill-pm]  요구사항 분석 → execution-plan.json
    |
    v
[Orchestrator]  실행 계획 로드 후 파이프라인 실행
    |
    v
[Validation]
    - requirements, execution plan을 JSON 스키마로 검증
    - 검증 모드: strict (실패 시 중단) / warn (경고 후 계속)
    |
    v
[Git Setup]
    - target_repo 있음: git clone / git fetch + reset --hard
    - target_repo 없음: .cache/{project}/에 git init + 빈 커밋
    |
    v
[Project Analysis]
    - Python 정적 분석, AI 비용 없음, ~1초
    - .project-profile.json (커밋 SHA 기반 캐싱)
    - project-context.md (키워드 매칭으로 관련 코드 추출)
    |
    v
[Phase 1: Architect]                    ← stages.architect.enabled
    - 입력: requirements.json + project-context.md
    - N개 구현 접근법 설계
    - 출력: approaches.json (+ concern 모드: api-contract.json)
    |
    v
[Checkpoint]                            ← checkpoint_phase1: true
    - 사용자가 approaches.json 검토
    - 개별 approach 승인/반려 (N>=2)
    |
    v
[Phase 2: Implementer x N]             ← ThreadPoolExecutor 병렬
    - 각 approach를 독립 git worktree에서 구현
    - 브랜치: task-{id}/impl-1, task-{id}/impl-2, ...
    - 출력: 커밋된 코드 + work-done.json
    |
    v
[Phase 3: Reviewer + Tester x N]       ← ThreadPoolExecutor 병렬
    - Reviewer → review.json (구현별)
    - Tester → test-results.json (구현별)
    |
    v
[Phase 4: Comparator 또는 Integrator]
    - alternative 모드 (N>=2): Comparator → comparison.json
    - concern 모드: Integrator → integration-report.json
    - N=1 alternative: Phase 4 건너뜀
    |
    v
[Simplifier]                            ← stages.simplifier.enabled
    - 출력: simplification.json
    |
    v
[완료]
    - evaluation-result.md 생성
    - 사용자가 원하는 브랜치 수동 머지
```

---

## 데이터 흐름 (JSON 우선)

모든 스킬 간 통신은 JSON을 단일 소스로 사용한다.
마크다운 파일은 JSON으로부터 자동 생성되며 사람 검토용이다.

```
skill-planner     → requirements.json
skill-pm          → execution-plan.json
skill-architect   → approaches.json (+ api-contract.json)
skill-implementer → work-done.json + 커밋된 코드
skill-reviewer    → review.json
skill-tester      → test-results.json
skill-comparator  → comparison.json        (alternative 모드)
skill-integrator  → integration-report.json (concern 모드)
skill-simplifier  → simplification.json
```

각 JSON 출력은 `schemas/*.schema.json`의 스키마로 검증된다.

---

## 적응형 N값

| 복잡도 | N | 동작 |
|--------|---|------|
| simple | 1 | 단일 구현. Architect 생략. Phase 4 생략 |
| medium | 2 | 2개 병렬 구현 + Comparator/Integrator |
| complex | 3 | 3개 병렬 구현 + Comparator/Integrator |

판단 기준:
- **simple**: user_stories <= 2, scope.in <= 3, 명확한 단일 해법
- **medium**: user_stories 3~5, 일반적인 기능 개발
- **complex**: user_stories >= 6, 아키텍처 결정 필요

---

## 파이프라인 모드

### Alternative 모드 (기본)

각 approach가 같은 문제를 다른 방식으로 독립적으로 구현.
Comparator가 순위를 매기고 최적을 추천.

### Concern 모드

각 approach가 서로 다른 관심사를 담당 (예: 프론트엔드 vs 백엔드).
Integrator가 모두 합쳐 하나의 동작하는 프로젝트로 통합.

---

## 상태 파일

모든 상태 파일은 `work/task-{id}/docs/`에 저장.

| 파일 | 설명 |
|------|------|
| `manifest.json` | 태스크 메타데이터: 현재 단계, N, 모드, 체크포인트 |
| `timeline.log` | Phase 전환 타임라인 |
| `requirements.json` | skill-planner의 요구사항 |
| `execution-plan.json` | skill-pm의 파이프라인 설정 |
| `approaches.json` | skill-architect의 N개 접근법 |
| `impl-N-review.json` | 구현별 리뷰 결과 |
| `impl-N-test-results.json` | 구현별 테스트 결과 |
| `comparison.json` | 비교 보고서 (alternative 모드) |
| `integration-report.json` | 통합 보고서 (concern 모드) |
| `impl-N-simplification.json` | 간소화 리뷰 + 설계 근거 |
| `evaluation-result.md` | 최종 평가 및 머지 가이드 |

---

## 에러 처리

- **Phase 실패**: timeline.log 기록, 알림 발송, manifest → failed, 파이프라인 중단
- **Claude 타임아웃**: max_retries까지 자동 재시도, 소진 시 Phase 실패
- **체크포인트 타임아웃**: checkpoint_timeout(기본 3600초) 초과 시 파이프라인 중단
