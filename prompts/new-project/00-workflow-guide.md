# 신규 프로젝트 시작 워크플로우 가이드

Claude Code + Gemini를 활용한 프로젝트 기획 → 개발 계획 수립 전 과정입니다.

---

## 전체 흐름

```
[사람의 아이디어]
      ↓
  STEP 1: 청사진 작성 (Claude Code)
      ↓ blueprint.md
  STEP 2: 개발 문서 작성 (Claude Code)
      ↓ dev-spec.md
  STEP 3: Gemini 리뷰 (사람이 Gemini에 붙여넣기)
      ↓ gemini-feedback.md (사람이 정리)
  STEP 4: 개발 계획 수립 (Claude Code)
      ↓ dev-plan.md
  STEP 5: 병렬 구현 (Multi-Agent)
```

---

## 디렉토리 구조

새 프로젝트를 시작할 때 아래 구조를 만드세요:

```
workspaces/{service-name}/
├── planning/
│   └── in-progress/
│       ├── blueprint.md          ← STEP 1 산출물
│       ├── dev-spec.md           ← STEP 2 산출물
│       ├── gemini-feedback.md    ← STEP 3 산출물 (사람이 작성)
│       └── dev-plan.md           ← STEP 4 산출물
└── work/                         ← STEP 5 구현 디렉토리
```

---

## STEP 1: 청사진 작성

**사용 프롬프트**: `prompts/new-project/01-blueprint.md`

**입력**: 프로젝트 설명, 핵심 기능 목록
**출력**: `blueprint.md`

포함 내용:
- 시장 분석 (타겟 사용자, 경쟁 서비스, 차별점)
- 핵심 가치 제안
- 기능 목록 (Must Have / Should Have / Nice to Have)
- 기술 방향성 (스택 후보)
- 성공 지표

---

## STEP 2: 개발 문서 작성

**사용 프롬프트**: `prompts/new-project/02-dev-spec.md`

**입력**: `blueprint.md`
**출력**: `dev-spec.md`

포함 내용:
- 아키텍처 결정
- 모듈/서비스 분리 구조
- 데이터 모델
- API 계약 (초안)
- 기술 스택 확정
- 비기능 요구사항

---

## STEP 3: Gemini 리뷰

**사용 프롬프트**: `prompts/new-project/03-gemini-review-prompt.md`

**방법**:
1. `03-gemini-review-prompt.md`를 열어 프롬프트 복사
2. `blueprint.md`와 `dev-spec.md` 내용을 함께 붙여넣기
3. Gemini (gemini.google.com 또는 AI Studio)에 제출
4. 피드백을 `gemini-feedback.md`에 정리

**얻을 수 있는 것**:
- 놓친 엣지 케이스
- 대안적 아키텍처 제안
- 시장/경쟁 관점의 추가 인사이트
- 기술 선택의 리스크 지적

---

## STEP 4: 개발 계획 수립 (병렬 분업)

**사용 프롬프트**: `prompts/new-project/04-dev-plan-parallel.md`

**입력**: `dev-spec.md` + `gemini-feedback.md`
**출력**: `dev-plan.md`

핵심 원칙:
- **간섭 없는 분업**: 각 Agent가 작업하는 영역이 파일 수준에서 겹치지 않아야 함
- **계약 우선**: 공유 인터페이스(API, 이벤트, 데이터 모델)를 먼저 확정
- **의존성 순서**: 공유 모듈 → 독립 모듈 → 통합 순으로 진행

---

## STEP 5: 병렬 구현

**구현 전략 선택**:

### 전략 A: git worktree (권장, 독립 브랜치)
```bash
git worktree add ../work/module-auth feature/module-auth
git worktree add ../work/module-post feature/module-post
# 각 Agent가 별도 worktree에서 작업
```

### 전략 B: 독립 디렉토리 (빠른 시작)
```
work/task-{id}/
├── implementations/
│   ├── impl-1/   ← Agent 1 (예: module-auth)
│   ├── impl-2/   ← Agent 2 (예: module-post)
│   └── impl-3/   ← Agent 3 (예: module-frontend)
```

### 전략 선택 기준

| 상황 | 전략 |
|------|------|
| 같은 저장소, 독립 모듈 | A (worktree) |
| 완전히 다른 서비스/저장소 | B (독립 디렉토리) |
| 대안 비교가 목적 | B (impl-N 패턴) |
| 최종 통합이 필요한 협업 | A (worktree, PR 방식) |
