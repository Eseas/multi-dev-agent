# Claude Code 내부 로직 분석 및 활용 가이드

> **출처**: [Claude Code 소스코드 분석 문서](https://vineetagarwal-code-claude-code.mintlify.app/introduction) (2026-03-31 공개)
> **분석 목적**: Multi-Agent Dev System 자동화 프로젝트에서 활용 가능한 내부 메커니즘 파악

---

## 목차

1. [Agentic Loop 아키텍처](#1-agentic-loop-아키텍처)
2. [Sub-Agent 시스템 (Task Tool)](#2-sub-agent-시스템-task-tool)
3. [Hook 시스템](#3-hook-시스템)
4. [Skill 시스템](#4-skill-시스템)
5. [Permission 시스템](#5-permission-시스템)
6. [Memory / CLAUDE.md 계층 구조](#6-memory--claudemd-계층-구조)
7. [SDK Control Protocol](#7-sdk-control-protocol)
8. [환경변수 및 설정](#8-환경변수-및-설정)
9. [도구(Tool) 내부 동작](#9-도구tool-내부-동작)
10. [자동화 프로젝트 적용 방안](#10-자동화-프로젝트-적용-방안)

---

## 1. Agentic Loop 아키텍처

Claude Code는 6단계 연속 루프로 동작한다:

```
┌─────────────────────────────────────────────────────────┐
│  1. Message Ingestion (터미널/stdin/--print)             │
│  2. Context Assembly (시스템 프롬프트 + git + CLAUDE.md)  │
│  3. Model Reasoning (tool_use 블록 생성)                 │
│  4. Permission Evaluation (allow/ask/deny)               │
│  5. Tool Execution & Result Collection                   │
│  6. Loop Continuation (tool_use 없을 때까지 반복)         │
└─────────────────────────────────────────────────────────┘
```

### 핵심 포인트

- **로컬 실행 전용**: 원격 실행 서버 없음. 파일, 셸, 인증정보는 로컬에서만 처리
- **Context Assembly 시 수집하는 정보**:
  - Git branch, default branch, username, `git status --short` (최대 2000자)
  - 최근 5개 커밋 (`git log --oneline`)
  - CLAUDE.md 파일들 (4단계 계층)
  - 현재 날짜
- **Memoization**: `getSystemContext()`와 `getUserContext()`는 `lodash/memoize`로 대화 세션 동안 캐싱
- **Compaction**: 긴 대화는 오래된 메시지를 주기적으로 요약. 원본 transcript는 디스크에 보존
- **query.ts**: 각 루프 턴을 구동하며, 실시간 토큰 스트리밍, tool_use 디스패치, 턴당 토큰/도구호출 예산 적용
- **결과 크기 제한**: 각 도구는 `maxResultSizeChars`를 지정. 초과 시 임시 파일 저장 후 프리뷰만 모델에 전달

### 🔧 자동화 활용

오케스트레이터가 Claude Code 프로세스를 제어할 때, 이 루프의 동작을 이해하면:
- `--print` 모드로 비대화형 실행 시 UI 렌더링 없이 stdout 출력 캡처 가능
- `--max-turns`로 에이전트의 루프 횟수 제한 가능
- `--max-budget-usd`로 비용 상한 설정 가능

---

## 2. Sub-Agent 시스템 (Task Tool)

### Agent Tool 파라미터

| 파라미터 | 타입 | 필수 | 설명 |
|---------|------|------|------|
| `prompt` | string | ✅ | 완전히 자기 포함적인 작업 설명 |
| `description` | string | ✅ | 3-5단어 요약 (UI 표시용) |
| `subagent_type` | string | - | 전문 에이전트 타입 (기본: general-purpose) |
| `model` | string | - | 모델 오버라이드 (sonnet, opus, haiku) |
| `run_in_background` | boolean | - | 비동기 실행 |
| `isolation` | string | - | `"worktree"` 설정 시 독립 git worktree 생성 |
| `cwd` | string | - | 작업 디렉토리 (worktree와 상호 배타적) |
| `name` | string | - | SendMessage로 참조 가능한 이름 |

### Sub-Agent 특성

- **Context Isolation**: 부모 대화 히스토리 **자동 전달 없음** → 프롬프트가 완전히 자기 포함적이어야 함
- **기본 Permission**: `acceptEdits` 모드 (파일 편집 자동 승인, bash 명령은 여전히 확인)
- **결과 크기 제한**: 최대 100,000자
- **중첩 제한**: Sub-agent가 다른 sub-agent 생성 불가 (1단계만)
- **Worktree 격리**: `isolation: "worktree"` 사용 시 독립 git worktree에서 작업 → 메인 작업 디렉토리에 영향 없음

### 효과적인 프롬프트 패턴

```
❌ 나쁜 예: "Based on your findings, fix the bug."

✅ 좋은 예: "Fix the null reference bug in UserService.getProfile() in
src/services/user.ts:247. The bug occurs when the user has no associated
profile record — getProfile() calls profile.preferences without checking
if profile is null first. Add a null check and return a default preferences
object { theme: 'light', notifications: true }. Run npm test afterward to
confirm the fix passes existing tests."
```

### 🔧 자동화 활용

**병렬 구현 실행**:
- 각 impl-N을 별도 sub-agent로 실행
- `isolation: "worktree"` 사용 → 구현체 간 파일 충돌 방지
- `run_in_background: true`로 병렬 실행

**SDK를 통한 커스텀 에이전트 정의**:
```json
{
  "agents": {
    "architect": {
      "description": "기획서를 분석하여 구현 방법을 설계",
      "prompt": "당신은 소프트웨어 아키텍트입니다...",
      "model": "opus",
      "tools": ["Read", "Glob", "Grep", "Write"],
      "maxTurns": 20
    },
    "implementer": {
      "description": "설계에 따라 코드를 구현",
      "prompt": "당신은 숙련된 개발자입니다...",
      "model": "sonnet",
      "permissionMode": "acceptEdits"
    },
    "reviewer": {
      "description": "구현된 코드를 리뷰",
      "prompt": "당신은 코드 리뷰어입니다...",
      "model": "opus",
      "tools": ["Read", "Glob", "Grep"],
      "disallowedTools": ["Write", "Edit", "Bash"]
    }
  }
}
```

---

## 3. Hook 시스템

Hook은 Claude Code의 라이프사이클 이벤트에 자동으로 실행되는 자동화 메커니즘이다.

### Hook 이벤트 전체 목록

| 이벤트 | 타이밍 | 매처 대상 | 핵심 용도 |
|--------|--------|----------|----------|
| **PreToolUse** | 도구 실행 전 | tool_name | 도구 호출 차단/수정 |
| **PostToolUse** | 도구 실행 후 | tool_name | 포매터, 린터, 테스트 실행 |
| **PostToolUseFailure** | 도구 실패 시 | tool_name | 에러 로깅 |
| **Stop** | 응답 완료 전 | - | 작업 완료 검증 |
| **SubagentStart** | 서브에이전트 시작 | agent_type | 컨텍스트 주입 |
| **SubagentStop** | 서브에이전트 종료 | agent_type | 결과 검증 |
| **SessionStart** | 세션 시작 | source | 초기 컨텍스트 설정 |
| **SessionEnd** | 세션 종료 | reason | 정리 작업 |
| **UserPromptSubmit** | 프롬프트 제출 시 | - | 프롬프트 필터링/보강 |
| **PreCompact** | 컨텍스트 압축 전 | trigger | 커스텀 압축 지침 |
| **PostCompact** | 컨텍스트 압축 후 | trigger | 압축 결과 처리 |
| **PermissionRequest** | 권한 요청 시 | tool_name | 프로그래밍적 승인/거부 |
| **PermissionDenied** | 권한 거부 후 | tool_name | 재시도 허용 |
| **Setup** | 초기화/유지보수 | trigger | 환경 설정 |
| **Notification** | 알림 발생 | notification_type | 이벤트 모니터링 |
| **CwdChanged** | 작업 디렉토리 변경 | - | 환경변수 주입 |
| **FileChanged** | 감시 파일 변경 | filename 패턴 | 파일 변경 반응 |
| **ConfigChange** | 설정 변경 | source | 설정 변경 감시 |
| **TaskCreated** | 태스크 생성 | - | 태스크 라이프사이클 |
| **TaskCompleted** | 태스크 완료 | - | 태스크 라이프사이클 |
| **WorktreeCreate** | worktree 생성 | - | 격리 환경 설정 |
| **WorktreeRemove** | worktree 제거 | - | 정리 |

### Hook 타입 4가지

#### 1. Command (셸 실행)
```json
{
  "type": "command",
  "command": "npm test",
  "timeout": 60,
  "shell": "bash",
  "async": false,
  "statusMessage": "테스트 실행 중..."
}
```

#### 2. HTTP (원격 엔드포인트)
```json
{
  "type": "http",
  "url": "https://hooks.example.com/claude-event",
  "headers": {"Authorization": "Bearer $MY_TOKEN"},
  "allowedEnvVars": ["MY_TOKEN"],
  "timeout": 10
}
```

#### 3. Prompt (LLM 평가)
```json
{
  "type": "prompt",
  "prompt": "Review tool call for security: $ARGUMENTS",
  "model": "claude-haiku-4-5",
  "timeout": 30
}
```

#### 4. Agent (에이전트 검증)
```json
{
  "type": "agent",
  "prompt": "Verify unit tests in $ARGUMENTS passed",
  "timeout": 60
}
```

### Exit Code 의미

| Exit Code | 의미 |
|-----------|------|
| `0` | 성공. stdout은 이벤트 타입에 따라 표시 |
| `2` | 차단/주입. stderr가 Claude에게 표시 |
| 기타 | stderr가 사용자에게만 표시. 실행 계속 |

### Hook Output JSON 스키마

```json
{
  "continue": true,
  "suppressOutput": false,
  "decision": "approve",
  "reason": "설명 텍스트",
  "systemMessage": "주입할 컨텍스트",
  "hookSpecificOutput": {}
}
```

### 🔧 자동화 활용

**오케스트레이터 → Claude Code 연동**:

```json
// .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [{
          "type": "command",
          "command": "python orchestrator/permission_handler.py",
          "timeout": 30
        }]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "Write",
        "hooks": [{
          "type": "command",
          "command": "python orchestrator/watcher.py --on-file-change",
          "async": true
        }]
      }
    ],
    "Stop": [
      {
        "hooks": [{
          "type": "command",
          "command": "python orchestrator/agents/completion_checker.py",
          "timeout": 30
        }]
      }
    ],
    "PermissionRequest": [
      {
        "hooks": [{
          "type": "command",
          "command": "python orchestrator/queue/auto_approve.py",
          "timeout": 10
        }]
      }
    ]
  }
}
```

**핵심 활용 시나리오**:
1. **PermissionRequest Hook**: 권한 요청을 자동 승인/거부 → `permission_handler.py`와 연동
2. **PostToolUse Hook**: 파일 생성/수정 시 오케스트레이터에 알림
3. **Stop Hook**: 에이전트 작업 완료 시 결과 검증 (exit code 2로 계속 진행 가능)
4. **SubagentStop Hook**: 서브에이전트 완료 시 transcript 경로 수집
5. **SessionStart Hook**: 에이전트 시작 시 초기 컨텍스트 자동 주입

---

## 4. Skill 시스템

### 구조

```
.claude/skills/
├── implement/
│   └── SKILL.md      →  /implement 명령
├── review/
│   └── SKILL.md      →  /review 명령
├── architect/
│   └── SKILL.md      →  /architect 명령
└── compare/
    └── SKILL.md      →  /compare 명령
```

### SKILL.md 프론트매터

```yaml
---
description: "구현 방법에 따라 코드를 구현합니다"
argument-hint: "<planning-spec-path>"
allowed-tools: "Read,Write,Edit,Bash,Glob,Grep"
when_to_use: "사용자가 구현을 요청할 때"
model: "claude-sonnet-4-6"
user-invocable: true
context: "fork"          # fork = 격리된 서브에이전트에서 실행
paths: "**/*.py"         # 파일 패턴 기반 활성화
version: "1.0"
hooks:                   # 스킬 범위 후크
  PostToolUse:
    - matcher: "Write"
      hooks:
        - type: command
          command: "python lint_check.py"
---
```

### 인라인 셸 명령

스킬 본문에서 `!` 접두사 + 백틱으로 호출 시점에 셸 명령 실행:
```markdown
## 현재 브랜치 상태
!`git log --oneline -10`

## 변경된 파일
!`git diff --name-only`
```

### 🔧 자동화 활용

**Phase별 커스텀 스킬 정의**:

```markdown
<!-- .claude/skills/phase-implement/SKILL.md -->
---
description: "기획서의 특정 방법을 구현하는 구현 에이전트"
argument-hint: "<task-dir> <impl-number>"
allowed-tools: "Read,Write,Edit,Bash,Glob,Grep"
model: "claude-sonnet-4-6"
context: "fork"
---

# 구현 에이전트

## 입력 정보
!`cat $1/architect/approaches.json`

## 기획서
!`cat $1/planning-spec.md`

## 작업 지시
구현 번호 $2에 해당하는 방법을 구현하세요.
작업 디렉토리: $1/implementations/impl-$2/

## 출력 요구사항
1. 실행 가능한 코드
2. work-done.md 작성
3. 기본 테스트 작성
```

---

## 5. Permission 시스템

### 6가지 Permission 모드

| 모드 | 읽기 | 편집 | Bash | 용도 |
|------|------|------|------|------|
| `default` | ✅ 자동 | ⚠️ 확인 | ⚠️ 확인 | 대화형 기본값 |
| `acceptEdits` | ✅ 자동 | ✅ 자동 | ⚠️ 확인 | Sub-agent 기본값 |
| `plan` | ✅ 자동 | ❌ 차단 | ❌ 차단 | 읽기 전용 분석 |
| `bypassPermissions` | ✅ 자동 | ✅ 자동 | ✅ 자동 | 완전 자동화 |
| `dontAsk` | ✅ 자동 | ❌ 차단* | ❌ 차단* | allow 규칙만 허용 |
| `auto` | ✅ 자동 | 🤖 AI판단 | 🤖 AI판단 | 실험적 |

*`dontAsk`: 명시적 allow 규칙이 있는 도구만 실행

### Permission 규칙 문법

```json
{
  "permissions": {
    "allow": [
      "Read",                          // 도구 전체
      "Bash(git *)",                   // 패턴 매칭
      "Write(src/**)",                 // 파일 경로 패턴
      "mcp__myserver__query_database", // MCP 도구
      "Agent(Explore)"                 // 에이전트 타입
    ],
    "deny": [
      "Bash(rm -rf *)",
      "Write(/etc/**)",
      "mcp__dangerous_server"
    ]
  }
}
```

### Permission 결정 파이프라인 (7단계)

```
1. Deny 규칙 확인          → deny면 즉시 차단
2. Ask 규칙 확인            → ask면 확인 요청
3. 도구의 checkPermissions  → 도구 자체 검사
4. Safety 검사              → .git/, .claude/ 등 보호
5. Mode 검사               → 현재 모드 정책 적용
6. Allow 규칙 확인          → allow면 허용
7. 기본 동작               → 사용자에게 확인 요청
```

### 🔧 자동화 활용

**완전 자동화 실행 설정**:
```bash
# 방법 1: bypassPermissions (Docker/Sandbox 내부에서만)
claude --permission-mode bypassPermissions --print "구현을 완료하세요"

# 방법 2: dontAsk + 명시적 allow 규칙 (더 안전)
claude --permission-mode dontAsk \
  --allowed-tools "Read,Write,Edit,Bash(npm *),Bash(python *),Bash(git *),Glob,Grep" \
  --print "구현을 완료하세요"
```

**PermissionRequest Hook으로 동적 승인**:
```json
{
  "hooks": {
    "PermissionRequest": [{
      "hooks": [{
        "type": "command",
        "command": "python orchestrator/permission_handler.py"
      }]
    }]
  }
}
```

`permission_handler.py`가 stdout으로 JSON 출력:
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PermissionRequest",
    "decision": {
      "behavior": "allow",
      "updatedPermissions": [
        { "toolName": "Bash", "ruleContent": "npm test", "behavior": "allow" }
      ]
    }
  }
}
```

---

## 6. Memory / CLAUDE.md 계층 구조

### 4단계 메모리 계층

```
우선순위 낮음 → 높음

1. Managed  (/etc/claude-code/CLAUDE.md)       — 관리자 정책
2. User     (~/.claude/CLAUDE.md, rules/*.md)   — 개인 설정
3. Project  (CLAUDE.md, .claude/rules/*.md)     — 팀 공유
4. Local    (CLAUDE.local.md)                   — 개인 프로젝트 오버라이드
```

### 파일 탐색 알고리즘

`getMemoryFiles()`가 CWD에서 루트까지 상향 탐색. 하위 디렉토리가 상위보다 우선.

### @include 지시자

```markdown
@filename              — 현재 파일 디렉토리 기준 상대 경로
@./relative/path       — 명시적 상대 경로
@~/home/path           — 홈 디렉토리 기준
@/absolute/path        — 절대 경로
```

제약사항:
- 최대 5단계 중첩
- 순환 참조 감지/방지
- 존재하지 않는 파일은 무시
- 텍스트 파일만 지원 (.md, .ts, .py, .json)
- 코드 블록 내 @include 무시

### Path-Scoped Rules

`.claude/rules/*.md`에서 YAML 프론트매터로 경로 기반 규칙 적용:

```yaml
---
paths:
  - "src/api/**"
  - "src/services/**"
---
API 서비스 코드는 반드시 에러 핸들링을 포함해야 합니다.
```

매칭 파일 작업 시에만 로드 → 컨텍스트 효율화

### 🔧 자동화 활용

**서비스별 CLAUDE.md 자동 생성**:
```
workspaces/my-service/
├── CLAUDE.md                    ← 서비스 전체 규칙
├── .claude/
│   └── rules/
│       ├── backend.md           ← paths: ["*-BE/**"]
│       ├── frontend.md          ← paths: ["*-FE/**"]
│       └── testing.md           ← paths: ["**/tests/**"]
├── CLAUDE.local.md              ← 로컬 오버라이드
└── planning/
    └── completed/
        └── feature-x/
            └── CLAUDE.md        ← @../../../planning-spec.md 참조
```

---

## 7. SDK Control Protocol

Claude Code는 라이브러리 API가 아닌 **stdin/stdout JSON 프로토콜**로 외부 앱과 통신한다.

### 프로세스 생성

```bash
claude --output-format stream-json --print
```

### 초기화 프로토콜

**Host → CLI (초기화 요청)**:
```json
{
  "type": "control_request",
  "request_id": "init-001",
  "request": {
    "subtype": "initialize",
    "systemPrompt": "당신은 구현 에이전트입니다...",
    "hooks": {},
    "agents": {
      "architect": {
        "description": "설계 에이전트",
        "prompt": "...",
        "model": "opus",
        "tools": ["Read", "Glob", "Grep"],
        "maxTurns": 15
      }
    }
  }
}
```

**CLI → Host (초기화 응답)**:
```json
{
  "type": "control_response",
  "response": {
    "subtype": "success",
    "request_id": "init-001",
    "response": {
      "commands": [...],
      "agents": [...],
      "models": [...],
      "account": { "email": "...", "subscriptionType": "..." }
    }
  }
}
```

### 메시지 스트림 타입

| 타입 | 설명 |
|------|------|
| `system (init)` | 세션 초기화 정보 |
| `assistant` | 모델 응답 (tool_use 블록 포함) |
| `stream_event` | 부분 스트리밍 토큰 |
| `tool_progress` | 장기 실행 도구 상태 |
| `result` | 최종 턴 요약 (비용, 시간, 성공/실패) |

### Result Subtypes

| subtype | 의미 |
|---------|------|
| `success` | 정상 완료 |
| `error_during_execution` | 실행 중 에러 |
| `error_max_turns` | 최대 턴 초과 |
| `error_max_budget_usd` | 예산 초과 |

### 제어 요청 목록

| 요청 | 방향 | 용도 |
|------|------|------|
| `interrupt` | host→CLI | 현재 턴 중단 |
| `set_permission_mode` | host→CLI | 권한 모드 변경 |
| `set_model` | host→CLI | 모델 전환 |
| `can_use_tool` | CLI→host | 권한 요청 (SDK 핸들러) |
| `mcp_status` | host→CLI | MCP 서버 상태 |
| `mcp_set_servers` | host→CLI | MCP 서버 동적 교체 |
| `get_context_usage` | host→CLI | 컨텍스트 윈도우 사용량 |
| `get_settings` | host→CLI | 현재 설정 읽기 |
| `rewind_files` | host→CLI | 특정 메시지 이후 파일 변경 되돌리기 |
| `hook_callback` | CLI→host | 훅 이벤트 전달 |
| `reload_plugins` | host→CLI | 플러그인 리로드 |

### TypeScript 세션 관리 API

```typescript
query()              // 프롬프트 실행 → async iterable<SDKMessage>
listSessions()       // 저장된 세션 목록
getSessionMessages() // JSONL transcript 파싱
forkSession()        // 세션 복사 (새 UUID)
renameSession()      // 세션 이름 변경
tagSession()         // 세션 태그 관리
```

### 🔧 자동화 활용

**오케스트레이터에서 SDK 프로토콜 활용**:

```python
import subprocess
import json

class ClaudeCodeSDK:
    """Claude Code SDK Control Protocol 래퍼"""

    def __init__(self):
        self.process = subprocess.Popen(
            ["claude", "--output-format", "stream-json", "--print"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

    def initialize(self, system_prompt: str, agents: dict):
        """초기화 요청"""
        request = {
            "type": "control_request",
            "request_id": "init-001",
            "request": {
                "subtype": "initialize",
                "systemPrompt": system_prompt,
                "agents": agents
            }
        }
        self._send(request)
        return self._read_response()

    def send_message(self, content: str):
        """사용자 메시지 전송"""
        message = {
            "type": "user",
            "message": {
                "role": "user",
                "content": content
            }
        }
        self._send(message)

    def stream_results(self):
        """결과 스트림 읽기"""
        for line in self.process.stdout:
            event = json.loads(line)
            yield event
            if event.get("type") == "result":
                break

    def interrupt(self):
        """현재 작업 중단"""
        self._send({
            "type": "control_request",
            "request_id": "interrupt-001",
            "request": {"subtype": "interrupt"}
        })

    def get_context_usage(self):
        """컨텍스트 윈도우 사용량 확인"""
        self._send({
            "type": "control_request",
            "request_id": "ctx-001",
            "request": {"subtype": "get_context_usage"}
        })
        return self._read_response()

    def _send(self, data):
        self.process.stdin.write(json.dumps(data).encode() + b"\n")
        self.process.stdin.flush()

    def _read_response(self):
        line = self.process.stdout.readline()
        return json.loads(line)
```

---

## 8. 환경변수 및 설정

### 자동화에 핵심적인 환경변수

#### 인증
| 변수 | 용도 |
|------|------|
| `ANTHROPIC_API_KEY` | API 키 직접 인증 |
| `CLAUDE_CODE_OAUTH_TOKEN` | OAuth 토큰 직접 제공 |
| `CLAUDE_CODE_USE_BEDROCK=1` | AWS Bedrock 사용 |
| `CLAUDE_CODE_USE_VERTEX=1` | GCP Vertex AI 사용 |

#### 모델 선택
| 변수 | 용도 |
|------|------|
| `ANTHROPIC_MODEL` | 기본 모델 오버라이드 |
| `CLAUDE_CODE_SUBAGENT_MODEL` | 서브에이전트 모델 지정 |

#### 동작 제어
| 변수 | 용도 |
|------|------|
| `CLAUDE_CODE_REMOTE=1` | 원격/컨테이너 모드 (타임아웃 확장, 프롬프트 억제) |
| `CLAUDE_CODE_SIMPLE=1` | 최소 모드 (Hook, LSP, 플러그인 등 비활성화) |
| `DISABLE_AUTO_COMPACT=1` | 자동 컨텍스트 압축 비활성화 |
| `CLAUDE_CODE_DISABLE_THINKING=1` | 확장 사고 비활성화 |
| `CLAUDE_CODE_MAX_OUTPUT_TOKENS` | 응답 최대 토큰 수 |
| `CLAUDE_CODE_MAX_CONTEXT_TOKENS` | 컨텍스트 윈도우 크기 오버라이드 |
| `BASH_MAX_OUTPUT_LENGTH` | Bash 출력 최대 문자 수 |
| `API_TIMEOUT_MS` | API 요청 타임아웃 (기본 300000ms) |

#### 관찰성
| 변수 | 용도 |
|------|------|
| `CLAUDE_CODE_ENABLE_TELEMETRY=1` | OpenTelemetry 활성화 |
| `CLAUDE_CODE_JSONL_TRANSCRIPT` | 세션 JSONL 트랜스크립트 파일 경로 |

### Settings 파일 우선순위

```
Plugin defaults → User (~/.claude/settings.json)
  → Project (.claude/settings.json)
  → Local (.claude/settings.local.json)
  → Managed (enterprise)
```

배열값은 스코프 간 연결(concatenate) + 중복 제거. 스칼라값은 높은 우선순위가 오버라이드.

### 🔧 자동화 활용

**오케스트레이터 실행 환경 설정**:
```python
import os

def get_claude_env(task_config):
    """Claude Code 실행 환경변수 구성"""
    return {
        **os.environ,
        "ANTHROPIC_API_KEY": task_config.api_key,
        "ANTHROPIC_MODEL": task_config.model or "claude-sonnet-4-6",
        "CLAUDE_CODE_SUBAGENT_MODEL": "claude-haiku-4-5",
        "CLAUDE_CODE_MAX_OUTPUT_TOKENS": "8192",
        "API_TIMEOUT_MS": "600000",  # 10분
        "CLAUDE_CODE_JSONL_TRANSCRIPT": str(task_config.log_path),
        "CLAUDE_CODE_REMOTE": "1",  # 프롬프트 억제
    }
```

---

## 9. 도구(Tool) 내부 동작

### 도구 가용성 제어

| 조건 | 영향 |
|------|------|
| `CLAUDE_CODE_SIMPLE=1` | Bash, Read, Edit만 사용 가능 |
| Permission deny 규칙 | 차단된 도구 제거 |
| `isEnabled()` 체크 | WebSearch 지역 게이팅 등 |
| MCP 서버 연결 상태 | MCP 도구 가용성 결정 |
| `--tools` 플래그 | 명시적 도구 세트 지정 |

### Bash 도구 상세

- **세션 지속**: 작업 디렉토리만 유지 (변수, alias, 함수는 비지속)
- **타임아웃**: 기본 120초, 최대 600초 (환경변수로 오버라이드 가능)
- **복합 명령**: `&&`, `||`, `;`, `|` 각각 독립적으로 권한 검사
- **안전 래퍼**: `timeout`, `time`, `nice`, `nohup`은 권한 검사 전 제거
- **보안 제한**: 명령 치환, 프로세스 치환, 의심스러운 리다이렉션 등에 승인 필요

### Read 도구 상세

- 기본 2000줄 읽기, `offset`과 `limit`으로 부분 읽기
- 이미지(PNG, JPG), PDF(20페이지 제한), Jupyter 노트북 지원
- 변경되지 않은 파일은 캐시된 stub 반환

### Grep 도구 상세

- ripgrep 기반, 정규표현식 지원
- 출력 모드: `files_with_matches` (기본), `content`, `count`
- `multiline: true`로 여러 줄 패턴 매칭
- 기본 결과 제한: 250줄 (head_limit)
- 자동 제외: `.git`, `.svn`, `.hg`, `.bzr`, `.jj`, `.sl`

---

## 10. 자동화 프로젝트 적용 방안

### 방안 1: SDK Protocol 기반 오케스트레이터 (권장)

```
┌──────────────────────┐
│   Orchestrator       │
│   (Python)           │
│                      │
│  ┌─────────────────┐ │     stdin/stdout (stream-json)
│  │ ClaudeCodeSDK   │◄├─────────────────────────────────┐
│  └────────┬────────┘ │                                  │
│           │          │     ┌──────────────────────┐     │
│  ┌────────▼────────┐ │     │  Claude Code Process  │     │
│  │ TaskManager     │ │     │  (--print mode)       │     │
│  └────────┬────────┘ │     │                       │     │
│           │          │     │  ┌─ Agent: Architect  │     │
│  ┌────────▼────────┐ │     │  ├─ Agent: Impl-1    │     │
│  │ ResultCollector │ │     │  ├─ Agent: Impl-2    │     │
│  └─────────────────┘ │     │  └─ Agent: Reviewer  │     │
└──────────────────────┘     └──────────────────────┘
```

**장점**:
- 세밀한 프로세스 제어 (interrupt, model 전환, context 사용량 모니터링)
- 커스텀 에이전트 정의 (architect, implementer, reviewer 등)
- 실시간 스트리밍 이벤트 처리
- 비용 모니터링 (`result.total_cost_usd`)

### 방안 2: Hook 기반 이벤트 드리븐 연동

```
┌──────────────────────┐     Hook Events (stdin JSON)
│   Orchestrator       │◄────────────────────────────────┐
│   (Python)           │                                  │
│                      │     ┌──────────────────────┐     │
│  ┌─────────────────┐ │     │  Claude Code          │     │
│  │ Hook Handler    │ │     │                       │     │
│  │ (HTTP server)   │◄├─────┤  hooks:               │     │
│  └─────────────────┘ │     │    PreToolUse → HTTP  │     │
│                      │     │    PostToolUse → HTTP  │     │
│  ┌─────────────────┐ │     │    Stop → HTTP        │     │
│  │ Permission      │ │     │    PermissionReq → cmd│     │
│  │ Auto-Approver   │ │     └──────────────────────┘     │
│  └─────────────────┘ │                                  │
└──────────────────────┘
```

**장점**:
- Claude Code 자체 기능만으로 구현 가능
- 설정 파일만으로 연동 (코드 변경 최소)
- HTTP 훅으로 외부 서비스 (Slack, 대시보드) 연동 용이

### 방안 3: CLI 기반 단순 실행

```bash
# 각 에이전트를 독립 Claude Code 프로세스로 실행
claude --print \
  --permission-mode dontAsk \
  --allowed-tools "Read,Write,Edit,Bash(npm *),Bash(python *),Glob,Grep" \
  --max-turns 30 \
  --max-budget-usd 5.0 \
  --output-format json \
  --model claude-sonnet-4-6 \
  --system-prompt "$(cat prompts/implementer.md)" \
  "기획서 $(cat workspace/planning/completed/feature-x/planning-spec.md)에 따라 방법 1을 구현하세요"
```

**장점**:
- 가장 단순한 구현
- 각 실행이 완전히 독립적
- `--output-format json`으로 결과 파싱 용이

### 방안 4: Worktree 격리 + 병렬 실행

```bash
# 구현 1 (background)
claude --print --worktree impl-1 \
  --system-prompt "$(cat prompts/implementer.md)" \
  "방법 1을 구현하세요" &

# 구현 2 (background)
claude --print --worktree impl-2 \
  --system-prompt "$(cat prompts/implementer.md)" \
  "방법 2를 구현하세요" &

# 대기 후 결과 수집
wait
```

**장점**:
- Git worktree로 완전한 파일 시스템 격리
- OS 수준 병렬 실행
- 각 구현체가 독립된 브랜치에서 작업

---

## 부록 A: 인증 우선순위

```
1. ANTHROPIC_AUTH_TOKEN 환경변수
2. CLAUDE_CODE_OAUTH_TOKEN 환경변수
3. 파일 디스크립터의 OAuth 토큰
4. apiKeyHelper (settings.json)
5. 저장된 claude.ai OAuth 토큰
6. ANTHROPIC_API_KEY 환경변수
```

CI/비대화형 환경에서는 `ANTHROPIC_API_KEY` 또는 `CLAUDE_CODE_OAUTH_TOKEN` 사용.

## 부록 B: MCP 서버 설정

```json
// .mcp.json (프로젝트 레벨)
{
  "mcpServers": {
    "database": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres"],
      "env": {
        "POSTGRES_CONNECTION_STRING": "$DATABASE_URL"
      }
    },
    "remote-api": {
      "type": "http",
      "url": "https://mcp.example.com/v1",
      "headers": {
        "Authorization": "Bearer $API_TOKEN"
      }
    }
  }
}
```

**권한 제어**:
- 전체 서버 차단: `"mcp__servername"`
- 특정 도구 허용: `"mcp__servername__toolname"`

## 부록 C: 주요 CLI 플래그 요약

| 플래그 | 용도 |
|--------|------|
| `--print` / `-p` | 비대화형 실행 |
| `--output-format stream-json` | SDK 통합용 스트리밍 |
| `--output-format json` | 결과 JSON 출력 |
| `--permission-mode` | 권한 모드 설정 |
| `--dangerously-skip-permissions` | 권한 우회 (Docker만) |
| `--allowed-tools` | 허용 도구 목록 |
| `--disallowed-tools` | 차단 도구 목록 |
| `--max-turns N` | 최대 턴 수 |
| `--max-budget-usd N` | 최대 비용 |
| `--model` | 모델 지정 |
| `--system-prompt` | 시스템 프롬프트 오버라이드 |
| `--append-system-prompt` | 시스템 프롬프트 추가 |
| `--worktree [name]` | Git worktree 격리 |
| `--add-dir` | 추가 디렉토리 접근 |
| `--mcp-config` | MCP 설정 파일 |
| `--agents` | 인라인 커스텀 에이전트 정의 |
| `--json-schema` | 구조화된 출력 스키마 |
| `--effort` | 사고 수준 (low/medium/high/max) |
| `--fallback-model` | 오버로드 시 대체 모델 |
| `--bare` | 최소 모드 |
| `--resume` / `-r` | 세션 재개 |
| `--continue` / `-c` | 최근 세션 계속 |
| `--fork-session` | 세션 분기 |

## 부록 D: 슬래시 명령어

| 명령 | 용도 |
|------|------|
| `/init` | CLAUDE.md 생성 |
| `/memory` | 메모리 파일 편집 |
| `/config` | 설정 패널 |
| `/hooks` | 훅 설정 보기 |
| `/mcp` | MCP 서버 관리 |
| `/permissions` | 권한 규칙 관리 |
| `/plan` | 플랜 모드 |
| `/model` | 모델 전환 |
| `/commit` | AI 커밋 |
| `/review` | PR 리뷰 |
| `/skills` | 스킬 목록 |
| `/compact` | 대화 압축 |
| `/clear` | 대화 초기화 |
