# 스킬 & 에이전트

## 스킬 파이프라인

| 스킬 | Phase | 역할 | 입력 | 출력 (JSON) | 스키마 |
|------|-------|------|------|-------------|--------|
| **skill-planner** | 0 | 사용자 니즈를 요구사항으로 정제 | 사용자 대화 | `requirements.json` | `requirements.schema.json` |
| **skill-pm** | 0 | 파이프라인 구성 결정 | `requirements.json` | `execution-plan.json` | `execution-plan.schema.json` |
| **skill-architect** | 1 | N개 구현 접근법 설계 | `requirements.json`, `execution-plan.json`, 프로젝트 코드 | `approaches.json` | `approaches.schema.json` |
| **skill-implementer** x N | 2 | 각 접근법의 실제 코드 작성 | `approaches.json[i]`, 프로젝트 worktree | `work-done.json` + 코드 | `work-done.schema.json` |
| **skill-reviewer** x N | 3 | 구현 코드 리뷰 | `impl-N/`, `work-done.json` | `review.json` | `review.schema.json` |
| **skill-tester** x N | 3 | 테스트 작성 및 실행 | `impl-N/`, `work-done.json` | `test-results.json` | `test-results.schema.json` |
| **skill-comparator** | 4 | 구현 비교 (alternative 모드) | 리뷰 + 테스트 결과 | `comparison.json` | `comparison.schema.json` |
| **skill-integrator** | 4 | 구현 통합 (concern 모드) | impl 브랜치 + api-contract | `integration-report.json` | `integration-report.schema.json` |
| **skill-simplifier** | 5 | 코드 간소화 + 설계 근거 문서화 | 구현 + 리뷰 결과 | `simplification.json` | `simplification.schema.json` |

---

## 에이전트 아키텍처

### BaseAgent

모든 에이전트는 `BaseAgent`를 상속 (`orchestrator/agents/base.py`).

```python
class BaseAgent:
    def __init__(self, name, workspace, executor)
    def run(self, context: dict) -> dict       # 메인 실행
    def load_prompt(self, prompt_file, **kwargs) # 템플릿 로드 + 변수 치환
    def execute_claude(self, prompt, working_dir) # Claude Code CLI 호출
    def write_output(self, filename, content)    # 원자적 파일 쓰기
    def read_input(self, filename)               # 워크스페이스에서 읽기
```

### 실행 흐름

```
1. 스킬 정의 로드 (skills/skill-{name}.md)
2. 컨텍스트 변수를 프롬프트에 치환
3. Claude Code CLI 실행 (stream-json 모드)
4. 출력 파싱 및 JSON 추출
5. 스키마 검증 (schemas/{name}.schema.json)
6. docs/ 디렉토리에 출력 저장
7. manifest.json 체크포인트 업데이트
```

### 에이전트 간 통신

- **파일 기반**: 모든 데이터 교환은 `docs/`의 JSON 파일로 수행
- **Orchestrator 중재**: Orchestrator가 Phase 간 파일 경로를 전달
- **원자적 쓰기**: 모든 출력은 `.tmp` → `rename` 패턴

---

## 스킬 정의

스킬 정의는 `skills/skill-{name}.md`에 YAML frontmatter와 함께 위치:

```yaml
---
name: skill-{name}
description: >
  이 스킬의 역할과 트리거 조건.
---

# 스킬 본문 (프롬프트 지시사항)
```

### 프롬프트 해석 우선순위

1. `skills/skill-{name}.md` (새 스킬 기반 프롬프트)
2. `prompts/{name}.md` (레거시 프롬프트 fallback)

---

## 스키마 검증

모든 에이전트 출력은 JSON Schema (`schemas/*.schema.json`)로 검증.

- **warn 모드** (기본): 검증 오류 로깅, 파이프라인 계속
- **strict 모드**: 오류 발생 시 파이프라인 중단

`SchemaValidator`가 `AgentRegistry.validate_output()`을 통해 검증 수행.

---

## Phase 상세

### Phase 0: 기획 (skill-planner + skill-pm)

**skill-planner**: 대화를 통해 사용자 니즈 정제
- 한 번에 하나의 질문
- 우선순위: 서비스 컨텍스트 → 기능 범위 → 엣지케이스 → AC 검증
- 모든 AC가 테스트 가능하고 범위가 명확할 때 종료
- 출력: `requirements.json`

**skill-pm**: 요구사항 분석 후 실행 계획 수립
- 복잡도 판정 (simple/medium/complex)
- N값 결정 (1/2/3)
- 파이프라인 모드 선택 (alternative/concern)
- 단계별 활성화/비활성화
- 출력: `execution-plan.json`

### Phase 1: 설계 (skill-architect)

요구사항 + 타겟 프로젝트 코드베이스를 분석하여 N개 접근법 설계.

- 각 접근법: 이름, 설명, 핵심 결정, 라이브러리, 트레이드오프, 복잡도, 공수
- **Alternative 모드**: 접근법은 독립적 대안
- **Concern 모드**: 접근법은 상호 보완적 + `api-contract.json` 생성

### Phase 2: 구현 (skill-implementer x N)

각 구현자는 독립된 git worktree에서 작업.

- Write/Edit 도구로 실제 코드 작성
- 기존 프로젝트 컨벤션 준수
- TODO 주석이나 플레이스홀더 코드 없이 완전한 구현
- `task-{id}/impl-N` 브랜치에 커밋
- 출력: `work-done.json`

### Phase 3: 리뷰 + 테스트 (병렬)

**skill-reviewer** 5가지 관점으로 리뷰 (가중치):
1. 코드 품질 (30%)
2. 아키텍처 & 설계 (25%)
3. 보안 (20%)
4. 성능 (15%)
5. 테스트 용이성 (10%)

발견 사항: Critical / Major / Minor 분류.

**skill-tester** 테스트 작성 및 실행:
- 테스트 피라미드: 단위(70%) > 통합(20%) > E2E(10%)
- FE 프로젝트: Playwright E2E
- 커버리지, 발견된 버그, 테스트 불가 영역 보고

### Phase 4: 평가

**skill-comparator** (alternative 모드, N>=2):
- 기준별 가중 점수
- 시나리오별 추천
- 순위 비교 + 최종 추천

**skill-integrator** (concern 모드):
- 순차적 브랜치 머지
- 충돌 해결 (모든 관심사 보존)
- 글루 코드 작성 (CORS, 라우팅, 공유 타입, 빌드 스크립트)
- 빌드 검증

### Phase 5: 간소화 (skill-simplifier)

- 불필요한 복잡도 패턴 식별
- 구체적인 간소화 코드 제안
- 설계 근거 문서화 (코드가 왜 이렇게 작성되었는지)
- 의도적 복잡도는 정당성과 함께 기록

---

## git Worktree 격리

각 구현자는 독립된 git worktree에서 실행:

```
.cache/{repo}/                          ← bare clone 또는 local init
    └── .git/

work/task-{id}/implementations/
    ├── impl-1/                         ← worktree (브랜치: task-{id}/impl-1)
    │   └── (전체 프로젝트 코드)
    └── impl-2/                         ← worktree (브랜치: task-{id}/impl-2)
        └── (전체 프로젝트 코드)
```

- 별도 브랜치 → 파일 시스템 충돌 없음
- Reviewer/Tester는 worktree를 읽기 전용으로 접근
- Integrator는 `task-{id}/integrated` 브랜치를 생성하여 머지
