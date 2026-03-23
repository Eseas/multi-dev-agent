# 에이전트 설계

## 에이전트 목록

| 에이전트 | Phase | 역할 | 입력 | 출력 |
|----------|-------|------|------|------|
| Architect | 1 | N개 구현 접근법 설계 | planning-spec.md + project-context | approaches.json |
| Implementer (×N) | 2 | 각 접근법을 git worktree에서 독립 구현 | approaches.json[i] | 커밋된 코드 + summary.json |
| Reviewer (×N) | 3 | 구현체 코드 리뷰 (5가지 관점) | impl-N/ worktree | review.md |
| Tester (×N) | 3 | 테스트 작성·실행·결과 분석 | impl-N/ worktree | test-results.json |
| Comparator | 4 | N개 구현 비교·순위·추천 (alternative 모드) | review + test 결과 전체 | comparison.md |
| Integrator | 4 | N개 구현 통합·충돌 해결·글루 코드 (concern 모드) | impl 브랜치 전체 | integrated/ 코드 |
| Simplifier | 후처리 | 선택된 구현 코드 품질 개선 | 선택된 impl worktree | 정리된 코드 |

> Phase 3의 Reviewer와 Tester는 각 구현체(N)에 대해 병렬로 실행된다.
> Phase 4는 파이프라인 모드에 따라 Comparator(alternative) 또는 Integrator(concern) 중 하나만 실행된다.

## Orchestrator

에이전트가 아닌 **시스템 코어**. 전체 파이프라인을 제어한다.

### 책임
- `planning/completed/` 폴더 감시 → 기획서 감지 시 파이프라인 자동 시작
- Phase 순차 실행 및 병렬 처리 관리 (Phase 2, 3은 ThreadPoolExecutor 병렬)
- 상태 추적 (`manifest.json`, `timeline.log`)
- 체크포인트: Phase 1 완료 후 사용자 승인 대기
- 에러 핸들링 및 시스템 알림

## 에이전트 공통 구조

```python
class BaseAgent:
    def __init__(self, name: str, workspace: Path, executor: ClaudeExecutor):
        ...

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

## 에이전트 간 통신

- **파일 기반**: 모든 에이전트 간 데이터는 파일로 교환 (approaches.json, review.md 등)
- **직접 통신 없음**: 에이전트끼리 서로 호출하지 않음. Orchestrator가 중재
- **원자적 파일 쓰기**: 모든 출력 파일은 tmp → rename 패턴으로 원자적으로 기록

## git Worktree 격리

각 구현체(impl-N)는 독립된 git worktree에서 실행된다.

```
.cache/{repo-name}/          ← bare clone (또는 로컬 init)
    ├── .git/
    └── (main 브랜치 파일)

workspaces/{service}/work/task-{id}/implementations/
    ├── impl-1/              ← worktree (브랜치: task-{id}/impl-1)
    └── impl-2/              ← worktree (브랜치: task-{id}/impl-2)
```

- 구현체들은 서로 다른 브랜치에서 작업 → 파일 충돌 없음
- Implementer 완료 후 변경 사항이 해당 브랜치에 커밋됨
- Integrator는 통합 브랜치(`task-{id}/integrated`)를 별도 생성하여 머지

## Phase 3 개별 제어

```yaml
pipeline:
  enable_review: true    # Reviewer ON/OFF
  enable_test: true      # Tester ON/OFF
```

둘 다 false이면 Phase 3을 건너뛰고 Phase 4로 직행.

## Simplifier

```yaml
pipeline:
  enable_simplifier: true
```

Phase 4 완료 후 선택된 구현의 worktree에서 코드 정리 수행.
코드 중복 제거, 불필요한 주석 삭제, 스타일 통일 등을 AI가 자율 수행.
