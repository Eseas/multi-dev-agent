# Question Queue 시스템 구현 문서

## 1. 개요

### 배경

다중 에이전트 파이프라인에서 여러 Claude 서브프로세스가 `ThreadPoolExecutor`로 동시 실행된다. 실행 중 사용자 입력이 필요한 상황(도구 권한 승인, 체크포인트 결정, 런타임 오류 등)이 발생하면, 기존에는 각각 별도의 파일 기반 시그널링을 사용했다:

- **Checkpoint**: `checkpoint-decision.json` 파일 폴링 (`main.py`)
- **Permission**: `permission-request.json` → `permission-decision.json` 파일 폴링 (`permission_handler.py`)

**문제**: 에이전트가 병렬 실행 중 여러 질문이 동시에 발생해도, 사용자가 이를 일괄 확인하고 자기 페이스로 처리할 수 없었음.

### 해결

모든 유형의 질문을 하나의 **스레드 안전 큐**로 통합하고, **Textual 기반 TUI 대시보드**에서 실시간으로 확인/응답할 수 있도록 구현.

---

## 2. 아키텍처

```
┌─────────────────────────────────┐
│  TUI Dashboard (main thread)    │
│  ┌───────────┐ ┌──────────────┐ │
│  │ 파이프라인 │ │ 질문 목록    │ │
│  │ 상태 패널 │ │ + 답변 입력  │ │
│  └───────────┘ └──────────────┘ │
└────────────┬────────────────────┘
             │ read/write
      ┌──────┴──────┐
      │ QuestionQueue│  (thread-safe, file-backed)
      └──────┬──────┘
             │ submit + wait_for_answer
┌────────────┴────────────────────┐
│  Pipeline (worker thread)       │
│  ┌──────┐ ┌──────┐ ┌────────┐  │
│  │Agent1│ │Agent2│ │Executor│  │
│  └──────┘ └──────┘ └────────┘  │
└─────────────────────────────────┘
```

### 스레딩 모델

| 스레드 | 역할 | 블로킹 여부 |
|--------|------|-------------|
| Main thread | Textual App 이벤트 루프 | 논블로킹 (이벤트 기반) |
| Worker thread | 파이프라인 실행 (`run_worker`) | 체크포인트에서 블로킹 |
| Agent threads | ThreadPoolExecutor 내부 | 질문 대기 시 개별 블로킹 |

### 동기화 메커니즘

- `threading.Lock`: 큐 내부 상태 보호 (동시 접근 방지)
- `threading.Event`: 질문별 블로킹/해제 (에이전트 스레드가 `Event.wait()`, TUI가 `Event.set()`)

---

## 3. 파일 구조

### 신규 파일 (6개)

| 파일 | 라인 수 | 설명 |
|------|---------|------|
| `orchestrator/queue/__init__.py` | 12 | 큐 패키지 export |
| `orchestrator/queue/models.py` | 108 | Question, Answer, Enum 데이터 모델 |
| `orchestrator/queue/question_queue.py` | 238 | 핵심 큐 로직 (thread-safe, file-backed) |
| `orchestrator/tui/__init__.py` | 9 | TUI 패키지 (graceful fallback) |
| `orchestrator/tui/app.py` | 346 | Textual 대시보드 앱 |
| `orchestrator/tui/widgets.py` | 117 | 커스텀 위젯 (QuestionCard, StatusPanel, QuestionDetail) |

### 수정 파일 (5개)

| 파일 | 변경 내용 |
|------|-----------|
| `orchestrator/permission_handler.py` | `question_queue` 파라미터 + 큐/파일 이중 경로 |
| `orchestrator/main.py` | QuestionQueue lazy init + checkpoint 큐 통합 |
| `cli.py` | `--no-tui` 플래그, `questions`/`answer` 커맨드 |
| `requirements.txt` | `textual>=0.40.0` 추가 |
| `config.yaml` | `queue` 섹션 추가 |

---

## 4. 핵심 모듈 상세

### 4.1 QuestionQueue (`orchestrator/queue/question_queue.py`)

#### 주요 메서드

| 메서드 | 시그니처 | 동작 |
|--------|---------|------|
| `ask()` | `ask(question: Question) -> Answer` | **블로킹**. 에이전트 스레드에서 호출. 답변 올 때까지 해당 스레드만 대기. |
| `answer()` | `answer(question_id: str, response: str) -> bool` | **논블로킹**. TUI/CLI에서 호출. `Event.set()`으로 대기 스레드 해제. |
| `cancel()` | `cancel(question_id: str) -> bool` | 질문 취소 + 대기 스레드 해제 |
| `get_pending()` | `get_pending() -> List[Question]` | PENDING 상태 질문 목록 |
| `get_all()` | `get_all() -> List[Question]` | 전체 질문 목록 |

#### ask/answer 흐름

```python
# 에이전트 스레드 (블로킹)
event = threading.Event()
self._questions[q.id] = question
self._events[q.id] = event
self._persist()            # question-queue.json에 저장
self._on_question(question) # TUI 콜백
event.wait(timeout=...)     # 블로킹 대기

# TUI/CLI 스레드 (논블로킹)
q.answer = response
q.status = ANSWERED
self._persist()            # 파일 업데이트
event.set()                # 에이전트 스레드 깨움
```

#### 파일 영속성

- 모든 상태 변경 시 `atomic_write()`로 `question-queue.json` 저장
- 초기화 시 파일에서 pending 질문 복구 (크래시 복구)

### 4.2 데이터 모델 (`orchestrator/queue/models.py`)

#### QuestionType

| 값 | 용도 | 출처 |
|----|------|------|
| `PERMISSION` | 도구 사용 승인 | PermissionHandler |
| `CHECKPOINT` | 파이프라인 체크포인트 | Orchestrator |
| `ERROR` | 런타임 오류 | 에이전트 |
| `DECISION` | 커스텀 결정 | 에이전트/확장용 |

#### QuestionStatus

| 값 | 의미 |
|----|------|
| `PENDING` | 대기 중 (사용자 응답 필요) |
| `ANSWERED` | 답변 완료 |
| `EXPIRED` | 타임아웃 만료 |
| `CANCELLED` | 취소됨 |

#### Question 필드

```python
@dataclass
class Question:
    type: QuestionType          # 질문 유형
    source: str                 # 출처 ("orchestrator", "impl-1" 등)
    phase: str                  # 파이프라인 단계
    title: str                  # 짧은 제목 (목록 표시용)
    detail: str                 # 상세 내용
    options: List[str]          # 선택지 (비어있으면 자유 텍스트)
    default: Optional[str]      # 타임아웃 시 기본값
    timeout: float              # 대기 제한 시간 (초)
    id: str                     # 고유 ID (q-xxxxxxxx)
    status: QuestionStatus      # 현재 상태
    created_at: str             # 생성 시각
    answer: Optional[str]       # 사용자 답변
    answered_at: Optional[str]  # 답변 시각
```

### 4.3 TUI 대시보드 (`orchestrator/tui/app.py`)

#### 레이아웃

```
┌─ Header (시계) ──────────────────────────────────────┐
│                                                       │
│ ┌─ 좌측 (30칸) ─┐ ┌─ 우측 (유동) ──────────────────┐ │
│ │                │ │ 대기 중인 질문  3개             │ │
│ │ 파이프라인 상태│ │ ┌────────────────────────────┐  │ │
│ │                │ │ │> PERM  Bash 도구 승인      │  │ │
│ │ 태스크:        │ │ │  CHKP  Phase 1 체크포인트  │  │ │
│ │   task-2026... │ │ │  PERM  Write 도구 승인     │  │ │
│ │ 단계:          │ │ └────────────────────────────┘  │ │
│ │   Phase 2      │ │ ┌─ 상세 ─────────────────────┐  │ │
│ │                │ │ │ PERM  Bash 도구 사용 승인   │  │ │
│ │                │ │ │ 출처: executor | 단계: exec │  │ │
│ │                │ │ │ 인자: npm run build         │  │ │
│ │                │ │ │ 선택지: 1. allow  2. deny   │  │ │
│ │                │ │ └────────────────────────────┘  │ │
│ │                │ │ [1. allow] [2. deny]            │ │
│ │                │ │ [답변을 입력하세요...]           │ │
│ └────────────────┘ └────────────────────────────────┘ │
│                                                       │
├─ Footer (키 바인딩) ─────────────────────────────────┤
│  enter: 선택/답변  |  q: 종료                         │
└───────────────────────────────────────────────────────┘
```

#### 키 바인딩

| 키 | 동작 |
|----|------|
| `↑` / `k` | 질문 목록 위로 이동 |
| `↓` / `j` | 질문 목록 아래로 이동 |
| `Enter` | 답변 입력으로 포커스 |
| `1` / `2` / `3` | 선택지 번호로 빠른 답변 |
| `q` | TUI 종료 |

#### 파이프라인 실행 방식

```python
def on_mount(self):
    self.orchestrator._on_question_callback = self._on_new_question
    self.run_worker(self._run_pipeline, thread=True)  # 워커 스레드
    self.set_interval(1.0, self._refresh_questions)    # 주기적 갱신
```

- `run_worker(thread=True)`: Textual의 워커 스레드에서 파이프라인 실행
- `call_from_thread()`: 워커 → 메인 스레드 통신 (TUI 업데이트)
- `set_interval(1.0)`: 1초마다 큐 상태 갱신

---

## 5. 통합 포인트

### 5.1 Permission → Queue 통합

**파일**: `orchestrator/permission_handler.py`

```python
# __init__에 question_queue 파라미터 추가
def __init__(self, rules, notifier=None, ask_timeout=300.0, question_queue=None):
    self.question_queue = question_queue

# request_human_decision에서 분기
def request_human_decision(self, tool_name, tool_input, working_dir):
    if self.question_queue:
        return self._request_via_queue(tool_name, argument, tool_input)
    return self._request_via_file(tool_name, argument, tool_input, working_dir)
```

기존 `_request_via_file()` 메서드는 그대로 유지하여 **하위 호환성** 보장.

### 5.2 Checkpoint → Queue 통합

**파일**: `orchestrator/main.py`

```python
def _wait_for_checkpoint(self, task_dir, checkpoint_name, timeout=3600):
    if self.question_queue:
        return self._wait_for_checkpoint_via_queue(task_dir, checkpoint_name, timeout)
    return self._wait_for_checkpoint_via_file(task_dir, checkpoint_name, timeout)
```

큐 경로에서는 응답 형식을 파싱하여 기존 딕셔너리 형식과 호환:
- `"approve"` → `{"action": "approve"}`
- `"approve:1,2"` → `{"action": "approve", "approved_approaches": [1, 2]}`
- `"revise:피드백"` → `{"action": "revise", "feedback": "피드백"}`

### 5.3 QuestionQueue Lazy Init

**파일**: `orchestrator/main.py`의 `run_from_spec()`

```python
# task_dir 생성 후 QuestionQueue 초기화
if self.question_queue is None and self._on_question_callback:
    from .queue import QuestionQueue
    self.question_queue = QuestionQueue(task_dir, on_question=self._on_question_callback)
    if hasattr(self.executor, 'permission_handler') and self.executor.permission_handler:
        self.executor.permission_handler.question_queue = self.question_queue
```

**Lazy init 이유**: TUI 모드에서 `Orchestrator.__init__()` 시점에는 `task_dir`이 아직 없음. `run_from_spec()`에서 `task_dir` 생성 후 큐를 초기화하고, PermissionHandler에도 주입.

### 5.4 CLI 통합

**파일**: `cli.py`

```python
# run 커맨드: TUI 우선, fallback
def cmd_run(args):
    if not args.no_tui:
        try:
            from orchestrator.tui import TUI_AVAILABLE
            if TUI_AVAILABLE:
                return _run_with_tui(args, spec_path)
        except ImportError:
            pass
    # 기존 방식
    ...
```

새 커맨드:
- `questions <task_id>`: `question-queue.json` 읽어서 대기 중 질문 표시
- `answer <task_id> <question_id> <response>`: 직접 파일에 답변 기록

---

## 6. 데이터 흐름

### Permission 질문 흐름

```
1. Claude 서브프로세스 → tool_use 이벤트 발생
2. StreamEventProcessor → PermissionHandler.evaluate() → "ask"
3. PermissionHandler._request_via_queue()
   └→ Question(type=PERMISSION, options=["allow","deny"])
4. QuestionQueue.ask(q)
   ├→ question-queue.json에 저장 (atomic_write)
   ├→ on_question 콜백 → TUI._refresh_questions()
   └→ Event.wait() (에이전트 스레드 블로킹)
5. TUI에서 사용자가 "allow" 선택
   └→ QuestionQueue.answer(q.id, "allow")
      ├→ question-queue.json 업데이트
      └→ Event.set() (에이전트 스레드 깨움)
6. queue.ask() 반환 → Answer(response="allow")
7. PermissionHandler → "allow" 반환
8. 에이전트 실행 계속
```

### Checkpoint 질문 흐름

```
1. Phase 1 완료 → _checkpoint_after_architect() 호출
2. _wait_for_checkpoint_via_queue()
   └→ Question(type=CHECKPOINT, options=["approve","revise","abort"])
3. QuestionQueue.ask(q) → 블로킹
4. TUI에서 사용자가 "approve" 선택
5. queue.ask() 반환 → {"action": "approve"}
6. 파이프라인 Phase 2로 진행
```

---

## 7. 파일 형식

### `question-queue.json`

```json
{
  "questions": [
    {
      "id": "q-a1b2c3d4",
      "type": "permission",
      "source": "executor",
      "phase": "execution",
      "title": "Bash 도구 사용 승인",
      "detail": "인자: npm run build\n입력: {\"command\": \"npm run build\"}",
      "options": ["allow", "deny"],
      "default": "deny",
      "timeout": 300.0,
      "status": "pending",
      "created_at": "2026-02-27T14:30:00.123456",
      "answer": null,
      "answered_at": null
    },
    {
      "id": "q-e5f6g7h8",
      "type": "checkpoint",
      "source": "orchestrator",
      "phase": "checkpoint",
      "title": "체크포인트: phase1_review",
      "detail": "approve: 승인하여 다음 단계로 진행\nrevise: 수정 요청\nabort: 중단",
      "options": ["approve", "revise", "abort"],
      "default": null,
      "timeout": 3600.0,
      "status": "answered",
      "created_at": "2026-02-27T14:25:00.123456",
      "answer": "approve",
      "answered_at": "2026-02-27T14:28:15.654321"
    }
  ]
}
```

---

## 8. 하위 호환성

| 시나리오 | 동작 |
|----------|------|
| `--no-tui` 플래그 | 기존 파일 기반 방식 그대로 사용 |
| `textual` 미설치 | `TUI_AVAILABLE = False`, 자동 fallback |
| `question_queue = None` | PermissionHandler, Orchestrator 모두 기존 경로 사용 |
| 기존 CLI 커맨드 (`approve`, `revise`, `abort`) | 그대로 동작 (checkpoint-decision.json) |
| 새 CLI 커맨드 (`questions`, `answer`) | question-queue.json 직접 읽기/쓰기 |

---

## 9. 사용 방법

### TUI 모드 (기본)

```bash
# TUI 대시보드와 함께 파이프라인 실행
multi-agent-dev run -s planning-spec.md

# TUI에서:
# - ↑↓로 질문 선택
# - 1/2/3으로 빠른 답변
# - Enter → 텍스트 입력 → Enter로 답변
# - q로 종료
```

### 기존 방식 (No TUI)

```bash
# TUI 없이 실행
multi-agent-dev run -s planning-spec.md --no-tui

# 다른 터미널에서 질문 확인
multi-agent-dev questions task-20260227-143000

# 답변
multi-agent-dev answer task-20260227-143000 q-a1b2c3d4 allow

# 모든 질문 보기 (완료/만료 포함)
multi-agent-dev questions task-20260227-143000 --all
```

### config.yaml 설정

```yaml
queue:
  default_timeout: 3600       # 기본 질문 타임아웃 (초)
  permission_timeout: 300     # 권한 질문 타임아웃 (초)
  checkpoint_timeout: 3600    # 체크포인트 타임아웃 (초)
```

---

## 10. 테스트 결과

### 단위 테스트 (멀티스레드)

| 테스트 | 결과 |
|--------|------|
| 3개 스레드 동시 ask → 순차 answer | PASS |
| 타임아웃 시 기본값 반환 | PASS |
| 파일 영속성/크래시 복구 | PASS |
| cancel → 대기 스레드 해제 | PASS |
| on_question 콜백 호출 | PASS |

### 구문 검증

| 대상 | 결과 |
|------|------|
| orchestrator/queue/ (3개 파일) | PASS |
| orchestrator/tui/ (3개 파일) | PASS |
| orchestrator/permission_handler.py | PASS |
| orchestrator/main.py | PASS |
| cli.py | PASS |

### Import 검증

| import | 결과 |
|--------|------|
| `from orchestrator.queue import QuestionQueue, Question` | OK |
| `from orchestrator.tui import TUI_AVAILABLE, DashboardApp` | OK |
| `from cli import cmd_questions, cmd_answer` | OK |

---

## 11. 향후 과제

| # | 항목 | 우선순위 |
|---|------|----------|
| 1 | TUI에 파이프라인 Phase 진행 상태 실시간 표시 | Medium |
| 2 | 질문 우선순위(critical/high/normal/low) 지원 | Low |
| 3 | 에이전트 코드에서 커스텀 질문 제출 API | Medium |
| 4 | 일괄 답변 (같은 타입 질문에 동일 응답) | Low |
| 5 | TUI 테마/색상 커스터마이징 | Low |
| 6 | `question-queue.json` 외부 변경 감지 (watchdog) | Medium |
| 7 | Textual의 `pilot` 프레임워크로 TUI 자동 테스트 | Medium |
