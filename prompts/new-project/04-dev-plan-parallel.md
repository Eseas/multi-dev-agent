# STEP 4: 병렬 개발 계획 수립 프롬프트

> **사용 방법**:
> 1. `dev-spec.md`와 `gemini-feedback.md`가 완성된 후 사용
> 2. 아래 프롬프트를 Claude Code에 붙여넣기

---

## 프롬프트

```
당신은 시니어 소프트웨어 아키텍트이자 프로젝트 리드입니다.
아래 문서들을 기반으로 병렬 개발이 가능한 상세 개발 계획을 수립해주세요.

## 개발 문서 (dev-spec.md)

{dev-spec.md 내용을 여기에 붙여넣기}

## Gemini 피드백 (gemini-feedback.md)

{gemini-feedback.md 내용을 여기에 붙여넣기}

---

## 작업

다음 제약 조건을 최우선으로 지키며 개발 계획(dev-plan.md)을 작성하세요:

### 핵심 제약 조건

1. **파일 수준 격리**: 각 Agent(또는 개발자)는 서로 다른 파일을 수정합니다.
   - 같은 파일을 두 Agent가 동시에 수정하면 충돌 발생 → 절대 허용하지 않음

2. **계약 우선**: 공유 인터페이스를 모든 독립 작업 전에 완성합니다.
   - API 스펙, 공유 타입, 이벤트 스키마를 Phase 0에서 확정

3. **최소 직렬, 최대 병렬**: 반드시 직렬이어야 하는 것만 직렬로 처리합니다.

4. **명확한 완료 조건**: 각 작업의 완료 기준을 명확히 합니다.

파일 경로: workspaces/[service-name]/planning/in-progress/dev-plan.md

---

## 출력 형식 (dev-plan.md)

# 개발 계획: [PROJECT_NAME]

> **참조**: dev-spec.md, gemini-feedback.md
> **작성일**: YYYY-MM-DD
> **버전**: 1.0

---

## 1. Gemini 피드백 반영 사항

dev-spec.md에서 수정된 주요 내용:
- ...

---

## 2. 작업 분해 (Task Breakdown)

### Phase 0: 공유 기반 설정 (직렬 — 모든 병렬 작업 전에 완료)

**담당**: 리드 / Agent-Lead
**예상 시간**: [X]시간
**완료 조건**: 모든 공유 파일이 생성되고, 다른 Agent가 참조 가능한 상태

#### 0-1. 공유 타입 및 인터페이스 정의
```
생성할 파일:
- src/shared/types.ts (또는 해당 언어의 타입 파일)
- src/shared/api-contract.json
- src/shared/error-codes.ts
- src/shared/constants.ts
```

#### 0-2. 데이터베이스 스키마
```
생성할 파일:
- migrations/001_init.sql
- migrations/002_[테이블명].sql
```

#### 0-3. 프로젝트 기반 설정
```
생성할 파일:
- [설정 파일들]
- docker-compose.yml
- .env.example
```

**⚠️ Phase 0 완료 후 이 파일들은 읽기 전용입니다.**
**수정이 필요하면 모든 Agent와 합의 후 진행합니다.**

---

### Phase 1: 독립 모듈 개발 (병렬 ✅)

Phase 0 완료 후 아래 작업들은 동시에 시작 가능합니다.

---

#### Agent 1: [모듈명 A]

**전략**: git worktree / 독립 디렉토리
```bash
# worktree 사용 시
git worktree add ../worktree/agent-1 feature/[모듈명-a]

# 독립 디렉토리 사용 시
work/task-{id}/implementations/impl-1/
```

**작업 범위 (이 경계 밖 파일은 절대 수정 금지)**:
```
담당 파일:
  src/[모듈A]/**
  tests/[모듈A]/**

읽기 전용 (수정 금지):
  src/shared/**
  migrations/**
```

**세부 작업**:
- [ ] 1-1. [기능 구현 세부사항]
- [ ] 1-2. [기능 구현 세부사항]
- [ ] 1-3. 단위 테스트 작성
- [ ] 1-4. README 또는 work-done.md 작성

**완료 조건**:
- [ ] 모든 기능이 단위 테스트 통과
- [ ] 공유 인터페이스 계약 준수 확인
- [ ] 독립 실행 가능 (다른 모듈 없이도 테스트 가능)

---

#### Agent 2: [모듈명 B]

**전략**: git worktree / 독립 디렉토리
```bash
git worktree add ../worktree/agent-2 feature/[모듈명-b]
```

**작업 범위**:
```
담당 파일:
  src/[모듈B]/**
  tests/[모듈B]/**

읽기 전용:
  src/shared/**
```

**세부 작업**:
- [ ] 2-1. [기능 구현 세부사항]
- [ ] 2-2. [기능 구현 세부사항]
- [ ] 2-3. 단위 테스트 작성
- [ ] 2-4. work-done.md 작성

**완료 조건**:
- [ ] 모든 기능이 단위 테스트 통과
- [ ] API 계약 준수 확인

---

#### Agent 3: [모듈명 C]

(위와 동일한 형식으로 작성)

---

### Phase 2: 의존 모듈 개발 (Phase 1 완료 후)

Phase 1의 어떤 모듈에 의존하는지 명시:

#### Agent 1 (계속): [Phase 1 결과물에 의존하는 작업]
**선행 조건**: Agent 2의 [특정 기능] 완료
...

---

### Phase 3: 통합 및 테스트 (직렬)

**담당**: 통합 담당 Agent 또는 리드

#### 3-1. 코드 통합
```bash
# worktree 전략의 경우
git merge feature/[모듈A]
git merge feature/[모듈B]
git merge feature/[모듈C]
```

#### 3-2. 통합 테스트
- [ ] 모듈 간 API 호출 테스트
- [ ] 이벤트 흐름 테스트
- [ ] E2E 시나리오 테스트

#### 3-3. 통합 파일 작성
공유되어 Phase 1에서 건드리지 않았던 파일들:
```
수정할 파일:
  src/app.ts (라우팅 통합)
  src/main.ts (모듈 등록)
  [기타 통합 파일]
```

---

## 3. 충돌 방지 체크리스트

각 Phase 시작 전 확인:

### Phase 1 시작 전
- [ ] Phase 0의 모든 공유 파일이 생성되었는가?
- [ ] 각 Agent의 담당 파일 범위가 겹치지 않는가?
- [ ] 각 Agent가 공유 파일을 수정하지 않겠다고 확인했는가?

### Phase 1 진행 중
- [ ] 공유 파일 수정이 필요한 경우 → 리드와 합의 후 처리
- [ ] 다른 Agent의 영역이 필요한 경우 → Mock 또는 인터페이스로 대체

### Phase 3 (통합) 시작 전
- [ ] 모든 Agent의 단위 테스트가 통과했는가?
- [ ] 각 Agent가 API 계약을 준수했는가?

---

## 4. 빠른 시작 체크리스트

새 프로젝트를 시작하는 Agent에게:

```bash
# 1. 현재 계획 확인
cat dev-plan.md

# 2. 담당 Phase와 Agent 번호 확인
# (예: Phase 1, Agent 2)

# 3. worktree 설정 (해당되는 경우)
git worktree add ../worktree/agent-{N} feature/{모듈명}

# 4. 공유 파일 읽기 (수정 금지)
cat src/shared/types.ts
cat src/shared/api-contract.json

# 5. 담당 영역에서만 작업 시작
cd src/[담당모듈]/
```

---

## 5. 의존성 그래프

```
Phase 0 (공유 기반)
    │
    ├──────────────────────────────────┐
    │                                  │
Phase 1-A (Agent 1)        Phase 1-B (Agent 2)   ...
    │                                  │
    └──────────────────────────────────┘
                     │
              Phase 3 (통합)
```
```

개발 계획 작성 후 다음을 확인해주세요:
1. 각 Phase에서 병렬로 진행 가능한 작업 수
2. 가장 긴 직렬 의존성 체인 (Critical Path)
3. 충돌 가능성이 있는 파일 목록
