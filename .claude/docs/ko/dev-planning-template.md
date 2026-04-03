# 개발 기획 템플릿

## 개요

skill-planner와의 요구사항 대화를 위한 가이드.
결과물인 `requirements.json`이 전체 파이프라인의 입력이 된다.

**에이전트 필수 사전 작업**:
1. 코드 작성 전 `tech-stack.md` 확인
2. 기획에 `tech-stack.md`에 없는 새 기술 등장 시, 구현 전 먼저 수정
3. **무엇을(What)**과 **왜(Why)**만 정의 — **어떻게(How)**는 에이전트가 결정

---

## 요구사항 대화 가이드

skill-planner는 다음 순서로 질문:

```
1. 서비스 컨텍스트   → 누가 쓰는가? 어떤 서비스인가?
2. 기능 범위          → 정확히 무엇을 만드는가?
3. 제약사항           → 기존 시스템과 어떻게 연결되는가?
4. 엣지케이스         → 실패 시 어떻게 되는가? 제한 조건은?
5. AC 검증            → 각 항목이 테스트 가능한가?
```

모든 AC가 동사+조건 형태가 될 때 종료:
- ✅ "로그인 5회 실패 시 계정이 잠긴다"
- ❌ "보안이 좋아야 한다" (재질문)

---

## requirements.json 출력 구조

```json
{
  "task_id": "task-001",
  "created_at": "2026-04-03T00:00:00Z",
  "user_stories": [
    {
      "id": "US-001",
      "as_a": "관리자",
      "i_want": "웹에서 사용자 역할을 관리",
      "so_that": "개발자 도움 없이 접근 권한을 제어할 수 있다",
      "acceptance_criteria": [
        "관리자가 페이지네이션된 사용자 목록을 조회할 수 있다",
        "관리자가 역할을 변경하면 즉시 반영된다",
        "비관리자가 관리자 API에 접근하면 403을 반환한다"
      ],
      "priority": "must"
    }
  ],
  "scope": {
    "in": ["사용자 목록 조회", "역할 변경 API", "관리자 인증 가드"],
    "out": ["사용자 생성", "비밀번호 초기화"]
  },
  "deferred": ["역할 변경 감사 로그"],
  "conversation_summary": "관리자가 사용자 역할을 관리하는 어드민 패널. 역할 변경 흐름과 접근 제어에 집중.",
  "pipeline_hint": {
    "complexity": "medium",
    "requires_design": true,
    "notes": "기존 Spring Security 설정과 인증 통합 필요"
  }
}
```

스키마: `schemas/requirements.schema.json`

---

## execution-plan.json 출력 구조

skill-pm이 requirements.json으로부터 생성:

```json
{
  "task_id": "task-001",
  "created_at": "2026-04-03T00:00:00Z",
  "requirements_ref": "docs/requirements.json",
  "pipeline": {
    "mode": "alternative",
    "num_approaches": 2,
    "complexity": "medium"
  },
  "stages": {
    "architect":   { "enabled": true, "focus": "역할 기반 접근 제어 패턴" },
    "implementer": { "enabled": true, "guidelines": ["기존 UserService 활용", "기존 API 응답 형식 준수"] },
    "reviewer":    { "enabled": true, "focus_areas": ["보안", "API 일관성"] },
    "tester":      { "enabled": true, "test_strategy": "mixed" },
    "comparator":  { "enabled": true, "criteria": ["보안", "코드 품질", "유지보수성"] },
    "integrator":  { "enabled": false },
    "simplifier":  { "enabled": true }
  },
  "risk_notes": ["기존 인증 흐름을 깨트리면 안 됨"],
  "summary": "medium 복잡도. RBAC 전략이 다른 2개 alternative 접근법 비교. 리뷰, 테스트, 비교 포함 전체 파이프라인."
}
```

스키마: `schemas/execution-plan.schema.json`

---

## 좋은 요구사항 작성법

### 해야 할 것
- AC를 "동사+조건" 형태로 작성
- 측정 가능한 기술 기준 명시 (p95 < 200ms)
- 기존 코드와의 통합 지점 명시
- in-scope와 out-of-scope 명확히 구분

### 하지 말아야 할 것
- 특정 클래스명, 메서드명, 디자인 패턴 지정
- 파일 구조 지정
- 코드 스니펫 작성
- 모호한 표현: "적절한", "빠른", "좋은"

### 좋은 예 vs 나쁜 예

| 나쁜 예 | 좋은 예 |
|---------|---------|
| "보안이 좋아야 한다" | "미인증 접근 시 403 반환" |
| "빠른 응답" | "목록 API p95 < 200ms" |
| "JwtFilter 클래스 사용" | "API 요청은 JWT로 인증되어야 한다" |
| "적절한 기술 스택" | "Spring Security 6, JJWT 0.12" |
