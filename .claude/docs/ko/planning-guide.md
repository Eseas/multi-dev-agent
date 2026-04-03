# 기획 가이드 (Phase 0)

## 개요

Phase 0은 유일하게 사람이 주도하는 단계. 사용자가 skill-planner와 대화하여 `requirements.json`을 생성하고, skill-pm이 `execution-plan.json`을 작성한다.

**원칙**: **무엇을(What)**과 **왜(Why)**를 정의. **어떻게(How)** (클래스명, 패턴, 알고리즘)는 에이전트가 결정.

---

## 기획 흐름

### 1단계: skill-planner 대화

사용자가 필요한 것을 설명하면 skill-planner가 질문:

```
1. 서비스 컨텍스트   → 누가 쓰는가? 어떤 서비스인가?
2. 핵심 기능 범위    → 무엇을 만드는가? 범위는?
3. 엣지케이스        → 실패 시 어떻게 되는가? 제한 조건은?
4. AC 검증           → 각 기능이 테스트 가능한 형태인가?
```

종료 조건 (모두 충족):
- 모든 유저 스토리에 AC 2개 이상
- 각 AC가 테스트 가능 ("좋은 UX" 같은 표현 금지)
- in-scope / out-of-scope 명확 구분
- 보류 항목이 핵심 기능을 블로킹하지 않음
- 사용자가 요구사항 확인

출력: `requirements.json`

### 2단계: skill-pm 분석

skill-pm이 `requirements.json`을 읽고 결정:
- **복잡도**: simple / medium / complex
- **N값**: 1 / 2 / 3
- **파이프라인 모드**: alternative / concern
- **단계 활성화**: 어떤 에이전트를 활성화/비활성화할지

출력: `execution-plan.json`

### 3단계: 파이프라인 실행

Orchestrator가 `execution-plan.json`을 읽고 구성된 파이프라인을 실행.

---

## N값 가이드

| N | 사용 시점 | 예시 |
|---|-----------|------|
| 1 | 명확한 단일 해법, 버그 수정 | 단순 CRUD, 설정 변경 |
| 2 | 일반 기능, 대안 비교 가치 있음 | 인증 방식 선택, 라이브러리 선택 |
| 3 | 주요 아키텍처 결정 | DB 선택, 통신 패턴, 멀티 스택 비교 |

---

## 파이프라인 모드 가이드

### Alternative (기본)

N개 접근법이 **같은 문제를 다른 방식으로** 해결. 하나를 선택.

사용 시:
- "JWT vs Session — 어느 것이 더 나은가?"
- "ORM 직접 쿼리 vs QueryDSL — 유지보수성은?"

### Concern

N개 접근법이 **서로 다른 관심사를** 담당. 모두 합쳐짐.

사용 시:
- approach-1 = 인증 모듈, approach-2 = 비즈니스 로직
- approach-1 = 백엔드 API, approach-2 = 프론트엔드 UI

---

## 자주 하는 실수

### 구현 방법(How) 지정
```markdown
# 나쁜 예 (에이전트 자율성 침해)
- JwtAuthenticationFilter 클래스를 만들어 SecurityFilterChain에 등록

# 좋은 예 (What/Why만)
- JWT 토큰 기반으로 API 접근을 인증/인가할 수 있어야 한다
- 토큰 만료 시 자동 갱신되어야 한다
```

### 측정 불가능한 기준
```markdown
# 나쁜 예
- 좋은 성능
- 빠른 응답

# 좋은 예
- API 응답 시간 p95 < 200ms
- 동시 접속자 1,000명 처리 가능
```
