# 에이전트 설계

## 에이전트 목록

| 에이전트 | Phase | 역할 | 입력 | 출력 |
|----------|-------|------|------|------|
| **Architect** | 1 | 기획서 + 프로젝트 컨텍스트 → N개 구현 접근법 설계 | `planning-spec.md`, `project-context.md` | `architect/approaches.json` |
| **Implementer × N** | 2 | 각 approach를 독립 git worktree에서 구현 + 커밋 | `approaches.json[i]`, `project-context.md` | 커밋된 코드, `.multi-agent/summary.json` |
| **Reviewer × N** | 3 | 구현체 코드 리뷰 (5가지 관점) | `impl-N/` worktree | `review-N/review.md` |
| **Tester × N** | 3 | 테스트 작성·실행·결과 분석 | `impl-N/` worktree | `test-N/test-results.json` |
| **Comparator** | 4 | N개 구현 비교·순위·추천 (alternative 모드, N≥2) | 리뷰 + 테스트 결과 전체 | `comparator/comparison.md`, `evaluation-result.md` |
| **Integrator** | 4 | N개 구현 통합·충돌 해결·글루 코드 (concern 모드) | 모든 impl 브랜치 | `integrated/` worktree, `evaluation-result.md` |
| **Simplifier** | 후처리 | 선택된 구현 코드 정리·최적화 | 선택된 impl worktree | 정리된 코드 (in-place) |

Phase 3의 Reviewer와 Tester는 각 구현체(N)에 대해 ThreadPoolExecutor로 병렬 실행된다.
Phase 4는 파이프라인 모드에 따라 Comparator(alternative) 또는 Integrator(concern) 중 하나만 실행된다.

---

## 공통 구조 (BaseAgent)

모든 에이전트는 `BaseAgent`를 상속한다.

```python
class BaseAgent:
    def __init__(self, name: str, workspace: Path, executor: ClaudeExecutor):
        self.name = name
        self.workspace = workspace
        self.executor = executor

    def run(self, context: dict) -> dict:
        """에이전트 실행. 성공/실패 결과 딕셔너리 반환."""
        ...

    def load_prompt(self, prompt_file: Path, **kwargs) -> str:
        """prompts/ 디렉토리의 템플릿을 로드하고 변수 치환."""
        ...

    def execute_claude(self, prompt: str, working_dir: Path, output_file: Path) -> dict:
        """ClaudeExecutor를 통해 Claude Code CLI 실행."""
        ...
```

### 에이전트 실행 흐름

```
1. 입력 파일 존재 확인 (없으면 ValueError)
2. prompts/{agent}.md 템플릿 로드 + 변수 치환
3. ClaudeExecutor.run() → Claude Code CLI 실행 (--output-format stream-json)
4. 출력 파일 존재 확인 (없으면 RuntimeError)
5. 결과 반환
```

---

## 에이전트 간 통신

- **파일 기반**: 모든 데이터 교환은 파일로 이루어진다. 에이전트끼리 직접 호출하지 않는다
- **Orchestrator 중재**: 각 Phase 완료 후 Orchestrator가 다음 Phase에 필요한 파일 경로를 전달한다
- **원자적 쓰기**: 모든 출력 파일은 `.tmp` → `rename` 패턴으로 원자적으로 기록한다 (중간 읽기 방지)

---

## git Worktree 격리

각 Implementer는 독립된 git worktree에서 실행된다.

```
.cache/{repo}/                          ← bare clone 또는 로컬 init 저장소
    └── .git/

workspaces/{service}/work/task-{id}/implementations/
    ├── impl-1/                         ← git worktree (브랜치: task-{id}/impl-1)
    │   ├── (프로젝트 코드 전체)
    │   └── .multi-agent/
    │       └── summary.json
    └── impl-2/                         ← git worktree (브랜치: task-{id}/impl-2)
        ├── (프로젝트 코드 전체)
        └── .multi-agent/
            └── summary.json
```

- 각 worktree는 별도 브랜치 → 파일 시스템 충돌 없음
- Implementer 완료 후 변경 사항을 해당 브랜치에 커밋
- Comparator는 모든 worktree를 읽기 전용으로 접근
- Integrator는 `task-{id}/integrated` 브랜치를 새로 생성하여 머지

---

## Architect

### 역할
기획서와 프로젝트 컨텍스트를 분석하여 N개 구현 접근법을 설계한다. 각 접근법의 기술 스택, 파일 구조, 핵심 설계 결정 사항을 정의한다.

### 입력
- `planning-spec.md`: 목표, 제약사항, N값, 파이프라인 모드
- `project-context.md`: 기존 프로젝트 구조 및 관련 모듈 코드

### 출력: `architect/approaches.json`

```json
{
  "n": 2,
  "pipeline_mode": "alternative",
  "approaches": [
    {
      "id": 1,
      "name": "방법명",
      "summary": "한 문장 요약",
      "tech_stack": ["라이브러리A", "라이브러리B"],
      "key_decisions": ["핵심 설계 결정1", "핵심 설계 결정2"],
      "file_structure": ["src/auth/JwtFilter.java", "src/auth/AuthService.java"],
      "estimated_complexity": "medium"
    },
    {
      "id": 2,
      "name": "방법명2",
      ...
    }
  ]
}
```

### 체크포인트
Architect 완료 후 `checkpoint_phase1: true`이면 파이프라인이 일시 중단되고 사용자 승인을 기다린다. `approaches.json`을 검토한 후 CLI로 승인한다.

---

## Implementer

### 역할
할당된 approach(`approaches.json[i]`)를 독립 git worktree에서 실제로 구현하고 커밋한다.

### 핵심 원칙
- **기획서 준수**: 할당된 approach의 핵심 아이디어를 정확히 구현
- **독립성**: 다른 구현체 코드를 참조하거나 수정하지 않음
- **완전성**: 실제로 실행 가능한 상태로 구현
- **기록**: `.multi-agent/summary.json`에 구현 내용 요약

### 입력
- `approaches.json[i]`: 담당 approach 상세 설계
- `project-context.md`: 프로젝트 컨텍스트 (Read 도구로 참조)
- `impl-N/`: 작업 대상 git worktree

### 출력

**커밋된 코드** (impl-N 브랜치)

**`.multi-agent/summary.json`**:
```json
{
  "approach_id": 1,
  "approach_name": "방법명",
  "files_created": ["src/auth/JwtFilter.java"],
  "files_modified": ["src/config/SecurityConfig.java"],
  "key_decisions": "구현 중 내린 주요 결정 설명",
  "known_limitations": "알려진 미구현 부분이나 개선점"
}
```

---

## Reviewer

### 역할
구현체 코드를 5가지 관점에서 검토하고 강점·약점·개선 제안을 문서화한다.

### 5가지 리뷰 관점

1. **코드 품질**: 가독성, 네이밍, 일관성, 구조적 명확성
2. **설계**: SOLID 원칙, 패턴 적합성, 모듈 경계, 기존 아키텍처와의 통합
3. **보안**: SQL 인젝션, XSS, 인증/인가 결함, 민감 데이터 노출
4. **성능**: N+1 쿼리, 불필요한 루프, 캐싱 기회, 메모리 사용
5. **테스트 용이성**: 의존성 주입 가능 여부, 모킹 용이성, 경계 조건

### 출력: `review-N/review.md`

```markdown
# 코드 리뷰: Approach N - {방법명}

## 전체 평가
{총평 2~3줄}

## 1. 코드 품질
### 강점
### 개선 필요

## 2. 설계
...

## 5. 테스트 용이성
...

## 우선 개선 항목
1. {가장 중요한 개선 사항}
2. ...
```

---

## Tester

### 역할
구현체에 대한 테스트를 작성하고 실행한 뒤, 결과를 분석하고 문서화한다.

### 작업 순서
1. `.multi-agent/summary.json`으로 구현 내용 파악
2. 핵심 기능에 대한 단위 테스트 작성
3. 테스트 실행 (프로젝트의 기존 테스트 러너 사용)
4. 실행 결과·커버리지·실패 원인 분석

### 출력: `test-N/test-results.json`

```json
{
  "approach_id": 1,
  "framework": "JUnit5",
  "total": 15,
  "passed": 13,
  "failed": 2,
  "coverage": 78.5,
  "failures": [
    {
      "test": "테스트명",
      "reason": "실패 원인"
    }
  ],
  "summary": "전반적인 테스트 결과 요약"
}
```

---

## Comparator

### 역할 (alternative 모드, N≥2)
N개 구현체의 리뷰·테스트 결과를 종합하여 객관적으로 비교·순위를 매기고 최적 구현을 추천한다.

### 입력
- `architect/approaches.json`
- `review-1/review.md` ~ `review-N/review.md`
- `test-1/test-results.json` ~ `test-N/test-results.json`
- `.multi-agent/summary.json` (각 impl)

### 평가 기준
- 코드 품질 (리뷰 결과 기반)
- 테스트 통과율 및 커버리지
- 설계 적합성 (기존 아키텍처와의 통합성)
- 보안 및 성능 이슈
- 유지보수성

### 출력: `comparator/comparison.md`

```markdown
# 구현 비교 결과

## 요약 테이블
| 항목 | Approach 1 | Approach 2 |
|------|------------|------------|
| 코드 품질 | ★★★★☆ | ★★★☆☆ |
| 테스트 통과율 | 93% | 87% |
| 보안 | 이슈 없음 | 경미한 이슈 1건 |

## 상세 비교
...

## 최종 추천
**추천: Approach 1 ({방법명})**
이유: ...
```

`evaluation-result.md`에 최종 결과 요약 저장.

---

## Integrator

### 역할 (concern 모드)
N개 구현체(각자 다른 관심사 담당)를 하나의 통합 브랜치로 합친다. 충돌을 해결하고 글루 코드를 작성하여 전체가 하나의 일관된 시스템으로 동작하게 한다.

### 입력
- `architect/approaches.json` (각 approach의 관심사 정의)
- 모든 impl 브랜치 코드

### 작업
1. `task-{id}/integrated` 브랜치 생성
2. 각 impl 브랜치를 순서대로 머지
3. 충돌 해결 (각 approach의 관심사 경계 기준)
4. 인터페이스 불일치 수정 (글루 코드 작성)
5. 전체 빌드·테스트 확인

### 출력: `integrated/` worktree (task-{id}/integrated 브랜치)

---

## Simplifier

### 역할 (선택적 후처리)
파이프라인이 선택한 구현체의 코드를 정리·최적화한다. `enable_simplifier: true`일 때 활성화.

### 작업
- 중복 코드 추출·공통화
- 불필요한 주석, 디버그 코드, dead code 제거
- 스타일·네이밍 통일
- 과도한 복잡성 단순화

### 주의
- 기능 변경 없이 코드 품질만 개선
- 변경 사항을 동일 브랜치에 추가 커밋

---

## Phase 3 개별 제어

```yaml
pipeline:
  enable_review: true    # false이면 Reviewer 건너뜀
  enable_test: true      # false이면 Tester 건너뜀
```

둘 다 `false`이면 Phase 3 전체를 건너뛰고 Phase 4로 직행한다.
Comparator/Integrator는 리뷰·테스트 결과 없이도 구현 코드만으로 동작한다.

---

## 프롬프트 템플릿

각 에이전트의 프롬프트는 `prompts/` 디렉토리에서 관리한다.

```
prompts/
├── architect.md
├── implementer.md
├── reviewer.md
├── tester.md
├── comparator.md
├── integrator.md
└── simplifier.md
```

Orchestrator가 실행 시점에 컨텍스트 변수를 치환하여 최종 프롬프트를 생성한다. 프롬프트 수정으로 에이전트 동작을 커스터마이징할 수 있다.
