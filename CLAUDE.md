# Multi-Agent Development System - Claude Code 설정

이 프로젝트는 **다중 AI 에이전트 기반 개발 시스템**입니다. 인간-AI 협업 기획과 AI 자동 구현을 결합하여, 여러 구현 방향을 병렬로 탐색하고 최적의 솔루션을 선택합니다.

## 🎯 프로젝트 목표

- **Phase 0**: 사람과 Claude Code의 대화로 명확한 기획서 작성
- **Phase 1-6**: AI 에이전트들이 자동으로 구현, 리뷰, 테스트, 비교, 통합
- **적응형 파이프라인**: 문제 복잡도에 따라 구현 개수(N) 자동 조정 (1~3개)
- **하이브리드 모드**: 기본 N=2로 일상 작업에도 효율적

## 📁 프로젝트 구조

```
project/
├── orchestrator/          # 메인 오케스트레이터 시스템
│   ├── main.py           # CLI 진입점
│   ├── agents/           # 각 에이전트 구현
│   ├── watcher.py        # 파일 감시
│   ├── executor.py       # Claude Code 실행기
│   ├── notifier.py       # 알림 시스템
│   └── utils/            # 유틸리티
├── workspace/
│   ├── planning/         # 기획 단계
│   │   ├── in-progress/  # 기획 작성 중 (여기서 대화)
│   │   └── completed/    # 완성된 기획서 (자동 실행)
│   └── tasks/            # 실행 중인 작업들
├── prompts/              # 에이전트별 프롬프트 템플릿
└── config.yaml           # 설정 파일
```

## 🧠 현재 컨텍스트 파악

**항상 먼저 확인하세요:**

1. **현재 위치 확인**: `pwd`로 현재 디렉토리 확인
2. **작업 유형 파악**:
   - `planning/in-progress/` 안에 있다면 → **기획 단계**
   - `orchestrator/` 안에 있다면 → **시스템 개발**
   - `tasks/task-XXX/implementations/impl-N/` 안에 있다면 → **구현 단계**

## 📝 Phase 0: 기획 단계 가이드라인

### 작업 중인 경로: `workspace/planning/in-progress/[task-name]/`

**당신의 역할**: 사람과 대화하며 명확한 기획서를 작성하는 **기획 파트너**

### 기획서 작성 원칙

1. **명확성이 최우선**: 애매한 표현 사용 금지
2. **구현 방법 개수 명시**: "탐색할 방법 개수: N개"
   - **적응형 모드** (권장): 시스템이 자동 판단 (N=1~3)
   - **수동 지정**: 기획서에서 명시적으로 지정 가능
   - **기본값**: N=2 (하이브리드 모드)
3. **각 방법의 차별점 명확화**: 왜 이 방법들이 다른지 설명
4. **성공 기준 구체화**: 측정 가능한 기준 사용

### 적응형 파이프라인 이해하기

시스템은 다음 기준으로 복잡도를 자동 판단합니다:
- **N=1 (단순)**: 명확한 단일 해법, 간단한 작업
- **N=2 (보통, 기본값)**: 일반적인 개발 작업, 대안 하나 필요
- **N=3 (복잡)**: 중요한 아키텍처 결정, 여러 선택지 비교

사용자가 기획서에서 명시적으로 지정하면 그 값을 우선 사용합니다.

### 대화 흐름 가이드

```
1. 요구사항 이해
   → 질문: "이 기능이 정확히 무엇을 해결하나요?"
   → 질문: "성공을 어떻게 측정할 건가요?"

2. 제약사항 파악
   → 질문: "기존 시스템과 어떻게 통합되나요?"
   → 질문: "성능/보안 요구사항은?"

3. 구현 방법 제안
   → "다음 N개 방법을 고려해볼 수 있습니다..."
   → 각 방법의 장단점 설명
   → 사용자 의견 수렴

4. 기획서 작성
   → planning-spec.md 업데이트
   → 사용자 확인 후 completed/로 이동 안내
```

### 기획서 형식 (엄격히 준수)

```markdown
# 기획서: [명확한 기능명]

## 3. 구현 방법 탐색

**탐색할 방법 개수: 2개**  ← 명시 (또는 "자동"으로 적응형 사용)

### 방법 1: [방법명]
- **핵심 아이디어**: 한 문장으로 요약
- **예상 장점**: 구체적으로
- **예상 단점**: 솔직하게
- **기술 스택 제안**: 실제 라이브러리명

### 방법 2: [방법명]
...
```

**기획서에서 N 지정 방법**:
- `탐색할 방법 개수: 2개` - 정확히 2개 구현
- `탐색할 방법 개수: 3개` - 정확히 3개 구현
- `탐색할 방법 개수: 자동` - 시스템이 자동 판단 (적응형)

### 금지사항

- ❌ "여러 방법이 있습니다" → ✅ "2개 방법을 제안합니다" 또는 "자동"
- ❌ "적절한 기술 스택" → ✅ "React, Redux, TypeScript"
- ❌ "좋은 성능" → ✅ "응답 시간 < 500ms"

### 복잡도별 권장 N 값

사용자와 대화할 때 다음을 고려하여 제안:

**N=1 권장**:
- 간단한 버그 수정
- 명확한 단일 해법이 있는 문제
- "빨리 끝내고 싶어요"

**N=2 권장 (기본값)**:
- 일반적인 기능 추가
- 표준적인 구현 패턴
- "대안은 하나 정도 보고 싶어요"

**N=3+ 권장**:
- 중요한 아키텍처 결정
- 여러 기술 스택 중 선택
- "여러 옵션을 깊이 비교하고 싶어요"

---

## 🔧 Phase 1-6: 구현 단계 가이드라인

### 작업 중인 경로: `workspace/tasks/task-XXX/implementations/impl-N/`

**당신의 역할**: 기획서의 특정 방법을 구현하는 **숙련된 개발자**

### 구현 원칙

1. **기획서 준수**: 할당된 방법의 핵심 아이디어를 정확히 구현
2. **독립성**: 다른 구현체와 독립적으로 동작
3. **완전성**: 실제로 실행 가능한 코드 작성
4. **문서화**: work-done.md에 구현 내용 상세 기록

### 구현 체크리스트

```
[ ] 기획서의 기술 스택 사용
[ ] 핵심 기능 구현 완료
[ ] 에러 처리 포함
[ ] 기본 테스트 작성 (또는 테스트 가능하도록)
[ ] work-done.md 작성
[ ] 실행 방법 문서화
```

### work-done.md 형식

```markdown
# 구현 완료: [방법명]

## 구현 요약
- 핵심 아이디어를 어떻게 구현했는지 3-5줄로 설명

## 생성된 파일
- src/main.py: 진입점
- src/auth.py: 인증 로직
- tests/test_auth.py: 테스트

## 실행 방법
\`\`\`bash
python src/main.py
\`\`\`

## 기술적 결정
- 왜 이 라이브러리를 선택했는지
- 중요한 설계 결정 이유

## 알려진 제한사항
- 솔직하게 미구현 부분이나 개선점 명시
```

---

## 💻 시스템 개발 가이드라인

### 작업 중인 경로: `orchestrator/`

**당신의 역할**: 오케스트레이터 시스템을 개발하는 **시스템 아키텍트**

### 코딩 스타일 (Python)

```python
# 좋은 예
async def run_task(self, planning_spec_path: Path) -> str:
    """단일 작업 실행 (기획서 기반)

    Args:
        planning_spec_path: 기획서 경로

    Returns:
        생성된 task_id

    Raises:
        ValueError: 기획서가 유효하지 않을 때
    """
    task_dir = planning_spec_path.parent

    logger = TaskLogger(task_dir / "timeline.log")
    manifest = TaskManifest(task_dir / "manifest.json")

    try:
        await self.notifier.send("Phase 1", "시작")
        # ...
    except Exception as e:
        await self.notifier.send("오류", str(e), level="error")
        raise
```

### 핵심 패턴

#### 1. 원자적 파일 쓰기 (필수)

```python
def _atomic_write(self, path: Path, content: str):
    """항상 이 패턴 사용"""
    tmp_path = path.with_suffix(".tmp")
    tmp_path.write_text(content)
    tmp_path.rename(path)  # Atomic operation
```

#### 2. 알림 통합 (모든 중요 단계)

```python
# Phase 시작
await self.notifier.send("Phase N", "작업 설명")

# Phase 완료
await self.notifier.send("Phase N 완료", "결과 요약", level="success")

# 에러
await self.notifier.send("오류", str(e), level="error")
```

#### 3. 에러 처리

```python
try:
    result = await some_operation()
except SpecificError as e:
    # 구체적 에러 처리
    logger.log("error", f"작업 실패: {e}")
    manifest.update(phase="failed", error=str(e))
    await self.notifier.send("실패", str(e), level="error")
    raise  # 또는 복구 시도
```

### 에이전트 개발 규칙

각 에이전트는 `BaseAgent`를 상속하고:

1. **`_default_prompt()` 구현**: 명확하고 구체적인 프롬프트
2. **입력 검증**: 필수 파일 존재 확인
3. **출력 검증**: 예상 파일 생성 확인
4. **타임아웃 고려**: 긴 작업은 중간 체크포인트

```python
class NewAgent(BaseAgent):
    def _default_prompt(self) -> str:
        return """
당신은 [역할]입니다.

## 입력
{input_description}

## 작업
1. 구체적 단계
2. 구체적 단계

## 출력
output-file.md에 다음 형식으로:
- 항목1
- 항목2
"""

    async def execute(self, input_path: Path) -> Path:
        # 입력 검증
        if not input_path.exists():
            raise ValueError(f"입력 없음: {input_path}")

        # 실행
        prompt = self._build_prompt(...)
        await self._execute(prompt, working_dir=...)

        # 출력 검증
        output = working_dir / "output-file.md"
        if not output.exists():
            raise RuntimeError("출력 생성 실패")

        return output
```

---

## 🧪 테스트 가이드라인

### 단위 테스트

```python
import pytest
from pathlib import Path

@pytest.fixture
def temp_workspace(tmp_path):
    """임시 워크스페이스"""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return workspace

async def test_orchestrator_run_task(temp_workspace):
    """Orchestrator.run_task 테스트"""
    # Given
    orchestrator = Orchestrator(config_path="test_config.yaml")
    planning_spec = temp_workspace / "planning-spec.md"
    planning_spec.write_text("...")

    # When
    task_id = await orchestrator.run_task(planning_spec)

    # Then
    assert task_id.startswith("task-")
    assert (temp_workspace / "tasks" / task_id).exists()
```

### 통합 테스트

실제 Claude Code 실행은 비용이 높으므로:
- Mock 사용: `ClaudeExecutor`를 mock
- 시나리오 테스트: 전체 흐름 검증

---

## 🔒 보안 고려사항

### 1. Claude Code 실행 격리

```python
# 각 구현체는 독립된 디렉토리에서 실행
working_dir = task_dir / "implementations" / f"impl-{i}"
await self.executor.execute(prompt, working_dir=working_dir)
```

### 2. 기획서 검증

```python
# 악의적 경로 주입 방지
planning_spec_path = Path(planning_spec_path).resolve()
if not str(planning_spec_path).startswith(str(workspace)):
    raise ValueError("잘못된 경로")
```

### 3. 웹훅 URL 검증

```python
# config.yaml의 webhook_url 검증
if webhook_url and not webhook_url.startswith("https://"):
    raise ValueError("HTTPS 필수")
```

---

## 📊 로깅 규칙

### TaskLogger 사용

```python
logger = TaskLogger(task_dir / "timeline.log")

# Phase 전환
logger.log("phase", "architect_start")
logger.log("phase", "architect_done", extra={"count": len(approaches)})

# 에러
logger.log("error", str(e), extra={"phase": "implementation"})

# 중요 이벤트
logger.log("event", "user_approval", extra={"selected": "impl-2"})
```

### 로그 포맷

```
2025-02-10T15:30:45 [PHASE] architect_start
2025-02-10T15:31:20 [PHASE] architect_done {"count": 3}
2025-02-10T15:35:10 [ERROR] Implementation failed: timeout
```

---

## 🎨 UI/UX 원칙 (알림 및 출력)

### 콘솔 출력

```python
# 좋은 예: 구조화되고 색상 사용
print(f"\n✅ [SUCCESS] Phase 2 완료")
print(f"   모든 구현 완료: 3개\n")

# 나쁜 예: 단조롭고 정보 부족
print("done")
```

### 알림 레벨 사용

- `info`: 일반 진행 상황
- `success`: 단계 완료
- `warning`: 경고 (계속 진행 가능)
- `error`: 오류 (중단)

---

## 📚 참고 문서

- 기술 제안서: [multi-agent-dev-system-proposal.md](multi-agent-dev-system-proposal.md)
- 구현 가이드: [multi-agent-dev-system-implementation-guide.md](multi-agent-dev-system-implementation-guide.md)

---

## ⚡ 빠른 참조

### 현재 작업이 기획 단계인가?

```bash
# 현재 경로 확인
pwd  # planning/in-progress/* 라면 → 기획 단계

# 해야 할 것:
# 1. 사용자와 대화
# 2. planning-spec.md 작성/수정
# 3. "탐색할 방법 개수: N개" 명확히 명시
# 4. 완성 후 안내: mv planning-spec.md ../../completed/
```

### 현재 작업이 구현 단계인가?

```bash
# 현재 경로 확인
pwd  # tasks/*/implementations/impl-*/ 라면 → 구현 단계

# 해야 할 것:
# 1. 상위 디렉토리의 approaches.json 확인
# 2. 할당된 방법 구현
# 3. work-done.md 작성
# 4. 실행 가능한 코드 작성
```

### 현재 작업이 시스템 개발인가?

```bash
# 현재 경로 확인
pwd  # orchestrator/* 라면 → 시스템 개발

# 해야 할 것:
# 1. 이 CLAUDE.md의 코딩 스타일 준수
# 2. 원자적 파일 쓰기 사용
# 3. 알림 통합
# 4. 단위 테스트 작성
```

---

## 🚨 일반적인 실수 및 해결

### 실수 1: 기획서에서 방법 개수 누락

```markdown
❌ 나쁜 예:
### 방법 1: JWT
### 방법 2: Session

✅ 좋은 예:
**탐색할 방법 개수: 2개**

### 방법 1: JWT
### 방법 2: Session
```

### 실수 2: 파일 쓰기 시 atomic write 미사용

```python
❌ 나쁜 예:
path.write_text(content)  # 중간에 읽으면 깨진 데이터

✅ 좋은 예:
self._atomic_write(path, content)
```

### 실수 3: 에러 발생 시 알림 누락

```python
❌ 나쁜 예:
try:
    result = await operation()
except Exception as e:
    logger.log("error", str(e))
    raise

✅ 좋은 예:
try:
    result = await operation()
except Exception as e:
    logger.log("error", str(e))
    await self.notifier.send("오류", str(e), level="error")
    raise
```

---

## 🎯 성공 기준

좋은 작업의 지표:

- ✅ **기획 단계**: 기획서가 명확하고, 방법 개수가 명시되어 있음
- ✅ **구현 단계**: work-done.md가 완전하고, 코드가 실행됨
- ✅ **시스템 개발**: 테스트가 통과하고, 알림이 올바르게 동작함
- ✅ **모든 단계**: 다음 단계로 진행 가능한 완전한 출력 생성

---

**마지막 조언**: 이 시스템은 **여러 AI 에이전트가 협업**하는 구조입니다. 당신이 작성한 출력물을 다른 에이전트가 읽게 됩니다. 명확하고, 완전하고, 구조화된 출력을 생성하세요.
