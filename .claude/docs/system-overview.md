# Multi-Agent Dev System - 시스템 개요

## 시스템 목적

여러 AI 에이전트가 협업하여 소프트웨어 개발 작업을 수행하는 자동화 시스템.
사람은 기획 단계에서 방향을 잡고, 이후 에이전트들이 구현·리뷰·테스트·비교·통합을 자동 수행한다.

## 전체 흐름

```
[사람 + AI 기획] → planning-spec.md 완성
    ↓ (completed/ 로 이동)
[Validation] 기획서 검증 (규칙 기반, AI 비용 없음)
    ↓
[Git Setup] 타겟 프로젝트 clone/fetch OR 로컬 저장소 초기화 (신규 프로젝트)
    ↓
[Project Analysis] 프로젝트 사전 분석 (Python 기반, AI 비용 없음)
    ↓
[Phase 1] Architect: 기획서 + 프로젝트 컨텍스트 → N개 구현 설계
    ↓ (체크포인트: 사용자 승인)
[Phase 2] Implementer × N: git worktree 격리 환경에서 병렬 구현
    ↓
[Phase 3] Reviewer + Tester × N: 병렬 리뷰/테스트 (개별 ON/OFF 가능)
    ↓
[Phase 4] Comparator (alternative 모드, N≥2) 또는 Integrator (concern 모드)
    ↓
[Simplifier] 선택된 구현의 코드 품질 개선 (선택적)
    ↓
evaluation-result.md → 사용자가 수동으로 브랜치 선택·머지
```

## Phase 상세

### Phase 1: 설계 (Architect Agent)
- 기획서와 프로젝트 컨텍스트를 분석하여 N개의 구현 접근법 상세 설계
- 각 접근법의 기술 스택, 구조, 핵심 결정 사항 정의
- 출력: `architect/approaches.json`

### Phase 2: 구현 (Implementer Agents × N)
- N개의 에이전트가 각각 독립된 **git worktree**에서 병렬 구현
- 각 에이전트는 할당된 접근법만 구현 후 커밋
- 출력: git worktree 내 코드 + `.multi-agent/summary.json`

### Phase 3: 리뷰 + 테스트 (Reviewer + Tester Agents × N, 병렬)
- Reviewer: 5가지 관점(품질/설계/보안/성능/테스트용이성) 코드 리뷰
- Tester: 테스트 작성·실행·결과 분석
- 각각 `enable_review`, `enable_test` 설정으로 개별 ON/OFF 가능
- 출력: `review-{N}/review.md`, `test-{N}/test-results.json`

### Phase 4: 비교 또는 통합

**Alternative 모드** (기본, N≥2):
- Comparator: N개 구현을 비교·순위·추천
- 출력: `comparator/comparison.md`, `evaluation-result.md`

**Concern 모드**:
- Integrator: N개 구현을 하나로 통합, 충돌 해결, 글루 코드 작성
- 출력: `integrated/` (통합된 코드), `evaluation-result.md`

### Simplifier (선택적 후처리)
- 선택된 구현의 코드를 정리·최적화
- `enable_simplifier: true` 설정 시 활성화

## 파이프라인 모드

### Alternative 모드
각 approach가 독립적인 대안. 최적의 하나를 선택한다.

```
Phase 2: N개 독립 구현 → Phase 3: N개 리뷰/테스트 → Phase 4: Comparator
```

### Concern 모드
각 approach가 보완적 관심사 (예: FE/BE, 인증/로직). 모두 통합한다.

```
Phase 2: N개 관심사별 구현 → Phase 3: N개 리뷰/테스트 → Phase 4: Integrator
```

## 적응형 파이프라인 (N값 결정)

구현 개수 N은 기획서에 명시하거나, 시스템이 자동 판단한다.

| 복잡도 | N | 기준 |
|--------|---|------|
| 단순 | 1 | 단일 해법이 명확, 버그 수정 등 |
| 보통 | 2 | 일반 기능 개발 (기본값) |
| 복잡 | 3 | 아키텍처 결정, 기술 스택 선택 |

기획서에 `탐색할 방법 개수: N개` 또는 `탐색할 방법 개수: 자동`으로 명시.

## 신규 프로젝트 지원

GitHub 레포지토리 없이 처음부터 새 프로젝트를 만드는 경우:
- `config.yaml`의 `target_repo`를 비워두면 자동 감지
- `.cache/{project-name}/` 에 로컬 git 저장소 초기화
- 이후 동일한 파이프라인 실행 (worktree 기반 구현 격리 유지)
- 구현 완료 후 사용자가 원하는 레포에 수동 push

## 프로젝트 사전 분석

Python 기반 정적 분석, AI 비용 없음, 1~2초 소요.

- **정적 프로필**: 프로젝트 구조, 기술 스택, 모듈 목록 분석 → `.project-profile.json` 캐싱 (commit SHA 기반)
- **동적 컨텍스트**: 기획서 키워드와 연관된 모듈의 핵심 코드만 추출 → 에이전트 프롬프트에 파일 참조로 전달 (토큰 절감)
