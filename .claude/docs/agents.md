# 에이전트 설계

## 에이전트 목록

| 에이전트 | Phase | 역할 | 입력 | 출력 |
|----------|-------|------|------|------|
| Planner | 0 | 사람과 대화하며 기획서 작성 | 사용자 요구사항 | planning-spec.md |
| Architect | 1 | N개 구현 접근법 설계 | planning-spec.md | approaches.json |
| Implementer (×N) | 2 | 각 접근법 독립 구현 | approaches.json[i] | 코드 + work-done.md |
| Reviewer | 3 | 구현체 코드 리뷰 | impl-1..N/ | review-report.md |
| Tester | 4 | 구현체 테스트 실행 | impl-1..N/ | test-report.md |
| Comparator | 5 | 구현체 비교·추천 | review + test 결과 | comparison-report.md |
| Integrator | 6 | 선택된 구현체를 root project에 통합 | 선택된 impl + root project | 통합된 코드 |

## Orchestrator

에이전트가 아닌 **시스템 코어**. 전체 파이프라인을 관리한다.

### 책임
- 기획서 감지 (completed/ 폴더 워치)
- Phase 순차 실행
- 에이전트 생성·관리
- 상태 추적 (manifest.json, timeline.log)
- 에러 핸들링 및 알림

### 워크스페이스 인식
- 어떤 서비스의 어떤 기획서인지 파악
- 해당 서비스의 root project 경로를 에이전트에게 전달
- 통합 Phase에서 올바른 root project에 코드 반영

## 에이전트 공통 인터페이스

```python
class BaseAgent:
    async def execute(self, context: AgentContext) -> AgentResult:
        """에이전트 실행"""
        pass

class AgentContext:
    workspace_path: Path      # 워크스페이스 루트
    task_path: Path           # work/task-{id}/
    root_projects: list[Path] # root project 폴더 목록
    planning_spec: Path       # 기획서 경로
    phase_input: dict         # 이전 Phase 출력물
```

## 에이전트 간 통신

- 파일 기반 통신 (approaches.json, work-done.md 등)
- 에이전트 간 직접 통신 없음
- Orchestrator가 중재

## Root Project 접근

### 읽기 (Phase 1~5)
- Architect: root project 코드를 참조하여 호환되는 접근법 설계
- Implementer: root project의 기존 코드 스타일/패턴 참조
- Reviewer: root project 기준으로 코드 리뷰

### 쓰기 (Phase 6만)
- Integrator만 root project에 코드를 쓸 수 있음
- 브랜치 생성 후 작업 → PR 생성 또는 직접 병합
