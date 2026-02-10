# 구현 과제 및 개선 제안

> **작성일**: 2025-02-10
> **목적**: 기획서를 구현 관점에서 분석하고, 실제 구현 시 어려운 부분과 개선이 필요한 부분을 식별

---

## 📋 목차

1. [핵심 발견사항 요약](#1-핵심-발견사항-요약)
2. [구현이 어려운 부분](#2-구현이-어려운-부분)
3. [모호하거나 불명확한 부분](#3-모호하거나-불명확한-부분)
4. [다양한 프로젝트 타입 지원](#4-다양한-프로젝트-타입-지원)
5. [개선 제안](#5-개선-제안)
6. [우선순위별 구현 로드맵](#6-우선순위별-구현-로드맵)

---

## 1. 핵심 발견사항 요약

### 🔴 심각한 문제
1. **백엔드 중심 설계**: 기획서가 백엔드 개발만 고려하고 있음 (프론트엔드, 모바일, CLI 등 미고려)
2. **프로젝트 타입 감지 메커니즘 부재**: 어떤 유형의 프로젝트인지 감지하는 방법이 명시되지 않음
3. **Claude Code CLI 통합 방식 불명확**: 실제로 어떻게 에이전트를 실행할지 구체적이지 않음

### 🟡 중간 수준 문제
1. **병렬 실행 메커니즘 복잡도**: N개의 독립적인 Claude Code 세션을 관리하는 방법이 복잡함
2. **상태 관리 복잡도**: 개별 승인/수정/반려 시 상태 전이가 복잡함
3. **환경 격리 전략**: 심볼릭 링크 전략이 모든 언어/프레임워크에 적용 가능한지 불명확

### 🟢 경미한 문제
1. **에러 복구 전략**: 추상적으로만 설명되어 있음
2. **비용 추적 메커니즘**: API 비용을 실시간으로 추적하고 제한하는 방법 부재
3. **로그 및 상태 파일 포맷**: 구체적인 JSON 스키마가 명시되지 않음

---

## 2. 구현이 어려운 부분

### 2.1 Claude Code CLI 통합

#### 문제
기획서에서는 "Claude Code CLI를 사용한다"고만 명시되어 있으나, 실제 통합 방식이 불명확합니다.

**구체적 질문**:
- Claude Code를 프로그래밍 방식으로 실행할 수 있는가?
- 각 에이전트의 프롬프트를 어떻게 전달하는가?
- 실행 결과를 어떻게 캡처하는가?
- 대화형이 아닌 자동 실행이 가능한가?

#### 현재 가능성 분석

**방법 1: CLI 래퍼 사용**
```python
# 예상 구현
import subprocess

result = subprocess.run(
    ["claude", "--session", session_id, "--prompt-file", "prompt.txt"],
    cwd=working_dir,
    capture_output=True,
    timeout=300
)
```

**문제점**:
- Claude Code CLI가 이런 방식의 비대화형 실행을 지원하는지 불명확
- 세션 관리 방법 불명확
- 출력 파싱 방법 불명확

**방법 2: API 직접 사용**
```python
# Anthropic API 직접 사용
import anthropic

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
response = client.messages.create(
    model="claude-sonnet-4-5",
    messages=[{"role": "user", "content": prompt}]
)
```

**문제점**:
- Claude Code의 파일 시스템 접근, 도구 사용 기능을 직접 구현해야 함
- 복잡도 매우 높음

**권장 해결책**:
1. Claude Code CLI 문서를 상세히 조사하여 자동화 가능 여부 확인
2. 불가능하다면 Anthropic API + 커스텀 도구 구현
3. 또는 기획서를 "Claude Code 대화형 사용" 중심으로 수정

### 2.2 병렬 실행 메커니즘

#### 문제
N개의 구현을 병렬로 실행한다고 했으나, 실제 구현 방법이 복잡합니다.

**도전 과제**:
1. N개의 독립적인 Claude Code 세션 생성 및 관리
2. 각 세션의 진행 상황 모니터링
3. 일부 실패 시 부분 성공 처리
4. 리소스 제한 (동시 실행 수, 메모리, API 호출)

#### 구현 복잡도

```python
# 예상 구현 (AsyncIO 사용)
async def run_implementations(approaches: List[Approach]) -> List[Result]:
    tasks = []
    for i, approach in enumerate(approaches):
        working_dir = task_dir / f"impl-{i+1}"
        task = asyncio.create_task(
            run_claude_session(
                prompt=approach.implementation_guide,
                working_dir=working_dir,
                session_id=f"impl-{i+1}"
            )
        )
        tasks.append(task)

    # 부분 성공 허용
    results = await asyncio.gather(*tasks, return_exceptions=True)

    # 성공한 것만 필터링
    successful = [r for r in results if not isinstance(r, Exception)]
    return successful
```

**복잡도 요소**:
- ⚠️ 동시성 제어 (너무 많은 병렬 실행 방지)
- ⚠️ 타임아웃 관리 (각 세션별로)
- ⚠️ 에러 격리 (한 세션의 실패가 다른 세션에 영향 X)
- ⚠️ 진행 상황 모니터링 (실시간 로그)

**권장 해결책**:
1. 초기 구현은 순차 실행으로 시작 (복잡도 낮춤)
2. 병렬 실행은 2단계로 추가
3. 동시 실행 수 제한 (예: 최대 3개)

### 2.3 체크포인트 일시정지 메커니즘

#### 문제
"시스템이 자동으로 일시정지"한다고 했으나, 구현 방법이 불명확합니다.

**시나리오**:
```
Phase 1 완료 → approaches.json 생성 → 시스템 일시정지
→ 사용자 확인 → CLI 명령어로 승인
→ Phase 2 시작
```

**구현 방식 옵션**:

**방법 1: 폴링 (Polling)**
```python
# Orchestrator가 특정 파일을 기다림
def wait_for_approval(task_id: str):
    decision_file = task_dir / "checkpoint-decision.json"

    while True:
        if decision_file.exists():
            decision = json.loads(decision_file.read_text())
            return decision

        time.sleep(5)  # 5초마다 확인
```

**장점**: 구현 간단
**단점**: CPU 낭비, 즉시 반응 안 함

**방법 2: 파일 감시 (watchdog)**
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class CheckpointHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.endswith("checkpoint-decision.json"):
            self.handle_decision(event.src_path)
```

**장점**: 효율적, 즉시 반응
**단점**: 복잡도 증가

**방법 3: 별도 프로세스 + IPC**
```python
# Orchestrator는 백그라운드 데몬으로 실행
# CLI 명령어는 Unix socket으로 통신
```

**장점**: 가장 깔끔한 아키텍처
**단점**: 구현 복잡도 가장 높음

**권장 해결책**:
- MVP: 방법 1 (폴링)
- V2: 방법 2 (watchdog)

### 2.4 개별 승인/수정/반려 상태 관리

#### 문제
N≥2일 때 각 approach를 독립적으로 제어하는 로직이 복잡합니다.

**상태 전이도**:
```
pending → approved → (Phase 2 실행)
pending → in_revision → (Phase 1 재실행) → pending → approved
pending → rejected → (제거)
```

**복잡한 시나리오**:
```
초기: N=3 (모두 pending)

사용자 액션:
- Approach 1: approve
- Approach 2: revise (피드백: "Redis → PostgreSQL")
- Approach 3: reject

결과:
- Approach 1: Phase 2로 바로 진행
- Approach 2: Phase 1 재실행 (수정된 프롬프트로)
- Approach 3: 완전히 제거
- N = 2로 축소
```

**구현 이슈**:
1. **동시성**: Approach 1이 Phase 2 실행 중일 때, Approach 2가 Phase 1 재실행 중
2. **상태 일관성**: 여러 approach가 서로 다른 Phase에 있을 때 전체 상태 관리
3. **재합류**: Approach 2가 수정 완료 후 Phase 2로 합류하는 메커니즘

#### 예상 구현

```python
class ApproachStateMachine:
    """각 approach의 상태를 독립적으로 관리"""

    def __init__(self, approach_id: int):
        self.id = approach_id
        self.state = "pending"
        self.phase = 1
        self.revision_count = 0

    def approve(self):
        if self.state != "pending":
            raise InvalidStateTransition()
        self.state = "approved"

    def revise(self, feedback: str):
        if self.state != "pending":
            raise InvalidStateTransition()
        self.state = "in_revision"
        self.feedback = feedback

    def reject(self):
        if self.state != "pending":
            raise InvalidStateTransition()
        self.state = "rejected"

    async def execute_revision(self):
        """Phase 1 재실행"""
        if self.state != "in_revision":
            raise InvalidStateTransition()

        # Architect Agent 재실행 (피드백 포함)
        new_approach = await run_architect(
            planning_spec=...,
            previous_approach=self,
            feedback=self.feedback
        )

        # 완료되면 다시 pending으로
        self.state = "pending"
        self.revision_count += 1
        return new_approach

class TaskOrchestrator:
    """전체 task의 여러 approach 관리"""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.approaches: Dict[int, ApproachStateMachine] = {}

    async def run_phase2(self):
        """Phase 2 실행 (승인된 것만)"""
        approved = [a for a in self.approaches.values() if a.state == "approved"]

        # 병렬 실행
        tasks = [self.run_implementation(a) for a in approved]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return results

    async def handle_revisions(self):
        """수정 요청된 것들 처리"""
        in_revision = [a for a in self.approaches.values() if a.state == "in_revision"]

        for approach in in_revision:
            await approach.execute_revision()
            # 재실행 완료 후 다시 사용자 확인 필요
            await self.notify_user(f"Approach {approach.id} 수정 완료")
```

**복잡도 완화 방안**:
1. 초기에는 "전체 승인" 또는 "전체 수정"만 지원
2. 개별 제어는 V2에 추가
3. 수정된 approach의 재합류는 다음 체크포인트에서 처리

---

## 3. 모호하거나 불명확한 부분

### 3.1 기획서 파싱

#### 문제
"Architect Agent가 기획서를 파싱하여 N을 추출한다"고 했으나, 구체적 방법이 불명확합니다.

**예시 기획서**:
```markdown
## 구현 방법 (2개 비교)

### 방법 1: JWT 기반 인증
...

### 방법 2: 세션 기반 인증
...
```

**파싱 방법**:
1. **구조적 파싱**: 마크다운 헤더 개수 세기
   - 문제: 형식이 다양할 수 있음
2. **LLM 기반 파싱**: Claude에게 N 추출 요청
   - 문제: 비용, 정확도
3. **명시적 메타데이터**: YAML 프론트매터 사용
   - 장점: 가장 명확함

**권장 해결책**:
```markdown
---
task_name: "user-authentication"
num_approaches: 2
project_type: "backend"  # 추가 (다음 섹션 참조)
---

# 사용자 인증 기능

## 구현 방법

### 방법 1: JWT 기반 인증
...

### 방법 2: 세션 기반 인증
...
```

### 3.2 `approaches.json` 스키마

#### 문제
출력 형식이 예시로만 설명되어 있고, 정확한 JSON 스키마가 없습니다.

**권장 스키마**:
```json
{
  "task_id": "task-20250210-153045",
  "created_at": "2025-02-10T15:30:45Z",
  "approaches": [
    {
      "id": 1,
      "name": "JWT 토큰 기반 인증",
      "description": "JWT를 사용한 stateless 인증 시스템",
      "tech_stack": ["Node.js", "jsonwebtoken", "bcrypt", "Redis"],
      "implementation_guide": {
        "steps": [
          "1. Express 서버 설정",
          "2. JWT 미들웨어 구현",
          "3. 로그인/로그아웃 엔드포인트",
          "4. 토큰 검증 미들웨어"
        ],
        "key_files": [
          "src/auth/jwt.js",
          "src/middleware/auth.js",
          "src/routes/auth.js"
        ]
      },
      "pros": [
        "확장성 좋음",
        "MSA 친화적",
        "서버 부하 낮음"
      ],
      "cons": [
        "토큰 무효화 복잡",
        "Refresh token 관리 필요"
      ],
      "complexity": "medium",
      "estimated_time_minutes": 120
    },
    {
      "id": 2,
      "name": "세션 기반 인증",
      "description": "전통적인 서버 세션 기반 인증",
      "tech_stack": ["Node.js", "express-session", "Redis", "bcrypt"],
      "implementation_guide": {
        "steps": [
          "1. Express 서버 설정",
          "2. Session store (Redis) 설정",
          "3. 로그인/로그아웃 엔드포인트",
          "4. Session 검증 미들웨어"
        ],
        "key_files": [
          "src/auth/session.js",
          "src/middleware/auth.js",
          "src/routes/auth.js"
        ]
      },
      "pros": [
        "구현 단순",
        "즉시 무효화 가능",
        "서버에서 완전한 제어"
      ],
      "cons": [
        "서버 메모리 사용",
        "확장성 제한",
        "CORS 복잡"
      ],
      "complexity": "low",
      "estimated_time_minutes": 90
    }
  ],
  "checkpoint": {
    "phase": 1,
    "status": "awaiting_approval",
    "created_at": "2025-02-10T15:31:20Z"
  }
}
```

### 3.3 에이전트 프롬프트 설계

#### 문제
각 에이전트의 프롬프트가 "구체적으로" 어떻게 작성되어야 하는지 불명확합니다.

**예시: Implementer Agent 프롬프트**

**너무 추상적인 예시** (기획서):
```
당신은 숙련된 개발자입니다.
다음 구현 가이드를 따라 코드를 작성하세요.
```

**구체적이어야 하는 프롬프트**:
```markdown
# Implementer Agent - Approach 1 (JWT 기반 인증)

## 역할
당신은 백엔드 개발자입니다. 주어진 구현 가이드를 따라 JWT 기반 인증 시스템을 구현합니다.

## 프로젝트 컨텍스트
- 프로젝트 타입: Node.js Express 백엔드
- 기술 스택: Node.js, Express, jsonwebtoken, bcrypt, Redis
- 작업 디렉토리: {working_dir}

## 구현 요구사항
{implementation_guide}

## 필수 출력물
1. 실행 가능한 코드 (src/ 디렉토리)
2. 테스트 코드 (tests/ 디렉토리, 최소한의 테스트)
3. work-done.md (구현 내용 설명)

### work-done.md 형식
\`\`\`markdown
# 구현 완료: JWT 토큰 기반 인증

## 구현 요약
[3-5문장으로 핵심 설명]

## 생성된 파일
- src/auth/jwt.js: JWT 생성/검증
- src/middleware/auth.js: 인증 미들웨어
- ...

## 실행 방법
\`\`\`bash
npm install
npm start
\`\`\`

## 테스트 방법
\`\`\`bash
npm test
\`\`\`

## 기술적 결정
- bcrypt 사용 이유: ...
- Redis 사용 이유: ...

## 알려진 제한사항
- Refresh token 미구현
- Rate limiting 미구현
\`\`\`

## 제약사항
- 타임아웃: 300초
- 외부 API 호출 금지 (필요시 mock 사용)
- 민감 정보 하드코딩 금지

## 품질 기준
- 코드는 실행 가능해야 함
- 기본적인 에러 처리 포함
- 주요 함수에 JSDoc 주석 포함
```

**권장 해결책**:
1. `prompts/` 디렉토리에 각 에이전트별 템플릿 작성
2. 변수 치환 방식으로 동적 프롬프트 생성
3. 프로젝트 타입별로 다른 템플릿 사용

---

## 4. 다양한 프로젝트 타입 지원

### 4.1 현재 문제점

기획서의 모든 예시가 **백엔드 중심**입니다:
- JWT, 세션, Express, Redis (백엔드)
- Node.js, Python 언급만 있음
- 프론트엔드, 모바일, CLI, 라이브러리 등 미고려

### 4.2 지원해야 하는 프로젝트 타입

| 타입 | 예시 기술 스택 | 특수 고려사항 |
|------|---------------|--------------|
| **Backend API** | Node.js, Python, Go, Rust | 서버 실행, API 테스트, 데이터베이스 |
| **Frontend Web** | React, Vue, Angular, Svelte | 브라우저 렌더링, 컴포넌트 테스트, 접근성 |
| **Mobile App** | React Native, Flutter | 시뮬레이터/에뮬레이터, 네이티브 API |
| **CLI Tool** | Python Click, Node.js Commander | 입출력 테스트, 사용자 경험 |
| **Library/Package** | npm 패키지, PyPI 패키지 | API 테스트, 문서, 예제 |
| **Data Analysis** | Jupyter, pandas, matplotlib | 노트북 실행, 시각화 검증 |
| **ML Model** | TensorFlow, PyTorch | 학습, 평가, 추론 테스트 |
| **Desktop App** | Electron, Tauri | GUI 테스트, 패키징 |

### 4.3 프로젝트 타입별 차이점

#### 4.3.1 환경 설정

**Backend (Node.js)**:
```bash
npm install
node src/server.js
```

**Frontend (React)**:
```bash
npm install
npm run build
npm run dev  # 개발 서버
```

**Python CLI**:
```bash
python -m venv venv
source venv/bin/activate
pip install -e .
my-cli --help
```

**Rust CLI**:
```bash
cargo build --release
./target/release/my-cli --help
```

#### 4.3.2 테스트 방식

**Backend**:
```javascript
// API 테스트
describe('POST /auth/login', () => {
  it('should return JWT token', async () => {
    const response = await request(app)
      .post('/auth/login')
      .send({ username: 'test', password: 'pass' });

    expect(response.status).toBe(200);
    expect(response.body.token).toBeDefined();
  });
});
```

**Frontend**:
```javascript
// 컴포넌트 테스트
import { render, screen } from '@testing-library/react';
import LoginForm from './LoginForm';

test('renders login form', () => {
  render(<LoginForm />);
  expect(screen.getByLabelText('Username')).toBeInTheDocument();
  expect(screen.getByLabelText('Password')).toBeInTheDocument();
});
```

**CLI**:
```python
# 입출력 테스트
def test_cli_help():
    result = runner.invoke(cli, ['--help'])
    assert result.exit_code == 0
    assert 'Usage:' in result.output
```

#### 4.3.3 리뷰 기준

**Backend**:
- 보안 (SQL injection, XSS, CSRF)
- 성능 (쿼리 최적화, 캐싱)
- 확장성 (수평 확장 가능성)
- API 설계 (RESTful, GraphQL)

**Frontend**:
- 접근성 (a11y, ARIA)
- 성능 (Core Web Vitals, 번들 크기)
- 반응형 디자인 (모바일, 태블릿)
- SEO (메타 태그, 시맨틱 HTML)
- 사용자 경험 (로딩 상태, 에러 처리)

**CLI**:
- 사용자 경험 (명확한 도움말, 진행 표시)
- 에러 메시지 품질
- 플랫폼 호환성 (Windows, Linux, macOS)
- 성능 (시작 시간, 응답성)

**Library**:
- API 설계 (직관성, 일관성)
- 문서 품질 (API 문서, 예제)
- 하위 호환성
- 의존성 최소화

#### 4.3.4 환경 격리 전략

**Node.js (Backend/Frontend)**:
```
implementations/
├── impl-1/
│   ├── src/
│   ├── package.json
│   └── node_modules/ → ../../../shared/node_modules (symlink)
└── impl-2/
    ├── src/
    ├── package.json
    └── node_modules/ → ../../../shared/node_modules (symlink)
```

**Python**:
```
implementations/
├── impl-1/
│   ├── src/
│   ├── requirements.txt
│   └── venv/ (독립적)
└── impl-2/
    ├── src/
    ├── requirements.txt
    └── venv/ (독립적)
```

**Rust**:
```
implementations/
├── impl-1/
│   ├── src/
│   ├── Cargo.toml
│   └── target/ → ../../../shared/target (symlink)
└── impl-2/
    ├── src/
    ├── Cargo.toml
    └── target/ → ../../../shared/target (symlink)
```

### 4.4 프로젝트 타입 감지

#### 방법 1: 파일 기반 감지

```python
def detect_project_type(project_root: Path) -> ProjectType:
    """프로젝트 타입 자동 감지"""

    # Package.json 확인
    if (project_root / "package.json").exists():
        pkg = json.loads((project_root / "package.json").read_text())

        # React 프로젝트
        if "react" in pkg.get("dependencies", {}):
            return ProjectType.FRONTEND_REACT

        # Express 프로젝트
        if "express" in pkg.get("dependencies", {}):
            return ProjectType.BACKEND_NODE

        # CLI 프로젝트
        if "bin" in pkg:
            return ProjectType.CLI_NODE

        return ProjectType.BACKEND_NODE  # 기본값

    # Python 프로젝트
    if (project_root / "pyproject.toml").exists() or \
       (project_root / "setup.py").exists():
        pyproject = project_root / "pyproject.toml"

        if pyproject.exists():
            content = pyproject.read_text()
            if "click" in content or "typer" in content:
                return ProjectType.CLI_PYTHON
            if "fastapi" in content or "flask" in content:
                return ProjectType.BACKEND_PYTHON
            if "jupyter" in content:
                return ProjectType.DATA_ANALYSIS

        return ProjectType.BACKEND_PYTHON

    # Rust 프로젝트
    if (project_root / "Cargo.toml").exists():
        cargo = toml.loads((project_root / "Cargo.toml").read_text())

        if "bin" in cargo:
            return ProjectType.CLI_RUST
        if "lib" in cargo:
            return ProjectType.LIBRARY_RUST

        return ProjectType.BACKEND_RUST

    # Go 프로젝트
    if (project_root / "go.mod").exists():
        return ProjectType.BACKEND_GO

    # Flutter 프로젝트
    if (project_root / "pubspec.yaml").exists():
        return ProjectType.MOBILE_FLUTTER

    # 기본값
    return ProjectType.UNKNOWN
```

#### 방법 2: 기획서에 명시

```markdown
---
task_name: "user-authentication"
project_type: "frontend-react"  # 명시적 지정
num_approaches: 2
---
```

**권장**: 두 가지 병행
- 기획서에 명시되어 있으면 그것을 사용
- 없으면 자동 감지

### 4.5 프로젝트 타입별 에이전트 전략

#### Implementer Agent

각 프로젝트 타입별로 다른 프롬프트 템플릿 사용:

```
prompts/
├── implementer/
│   ├── backend-node.md
│   ├── backend-python.md
│   ├── frontend-react.md
│   ├── frontend-vue.md
│   ├── cli-python.md
│   ├── cli-rust.md
│   └── mobile-flutter.md
```

**예시: `prompts/implementer/frontend-react.md`**:
```markdown
# React Frontend Implementer

## 역할
당신은 React 개발자입니다. 주어진 구현 가이드를 따라 React 컴포넌트를 작성합니다.

## 프로젝트 컨텍스트
- 프로젝트 타입: React Frontend
- 기술 스택: {tech_stack}
- 작업 디렉토리: {working_dir}

## 구현 요구사항
{implementation_guide}

## 필수 출력물
1. React 컴포넌트 (src/components/)
2. 스타일 파일 (CSS/SCSS/Styled-components)
3. 테스트 코드 (React Testing Library)
4. work-done.md

## 품질 기준
- 접근성 고려 (semantic HTML, ARIA)
- 반응형 디자인
- 적절한 에러 처리 (Error Boundary)
- 로딩 상태 표시
- PropTypes 또는 TypeScript 타입

## 제약사항
- 외부 API는 mock 사용
- 이미지는 placeholder 사용
- 브라우저 호환성: 최신 2개 버전
```

#### Reviewer Agent

프로젝트 타입별 리뷰 체크리스트:

```
prompts/
├── reviewer/
│   ├── backend-checklist.md
│   ├── frontend-checklist.md
│   ├── cli-checklist.md
│   └── library-checklist.md
```

**예시: `prompts/reviewer/frontend-checklist.md`**:
```markdown
# React Frontend 리뷰 체크리스트

## 1. 코드 품질 (20%)
- [ ] 컴포넌트 구조가 명확한가?
- [ ] 재사용 가능한 컴포넌트로 분리되었는가?
- [ ] PropTypes 또는 TypeScript 타입이 정의되었는가?
- [ ] 불필요한 re-render가 없는가? (useMemo, useCallback)

## 2. 접근성 (20%)
- [ ] Semantic HTML 사용 (button, nav, main, article)
- [ ] ARIA 속성 적절히 사용
- [ ] 키보드 네비게이션 지원
- [ ] 스크린 리더 고려
- [ ] 색상 대비 충분 (WCAG AA)

## 3. 성능 (20%)
- [ ] 번들 크기 고려 (불필요한 라이브러리 제거)
- [ ] 이미지 최적화 (lazy loading)
- [ ] Code splitting 적용 (React.lazy)
- [ ] 불필요한 API 호출 제거

## 4. 사용자 경험 (20%)
- [ ] 로딩 상태 표시 (Spinner, Skeleton)
- [ ] 에러 상태 처리 (Error Boundary)
- [ ] 빈 상태 처리 (Empty state)
- [ ] 반응형 디자인 (모바일, 태블릿)

## 5. 보안 (10%)
- [ ] XSS 방지 (dangerouslySetInnerHTML 사용 자제)
- [ ] CSRF 토큰 사용 (API 호출 시)
- [ ] 민감 정보 노출 방지

## 6. 테스트 (10%)
- [ ] 주요 컴포넌트 테스트 존재
- [ ] 사용자 인터랙션 테스트
- [ ] 에러 케이스 테스트

## 점수 산정
각 항목별 가중치 적용하여 1-5점 스케일로 평가
```

#### Tester Agent

프로젝트 타입별 테스트 전략:

**Backend**:
- API 테스트 (Jest + Supertest)
- 통합 테스트 (실제 DB 또는 mock)
- 부하 테스트 (선택)

**Frontend**:
- 컴포넌트 테스트 (React Testing Library)
- E2E 테스트 (Playwright, 선택)
- 시각적 회귀 테스트 (선택)

**CLI**:
- 입출력 테스트
- Exit code 검증
- 에러 메시지 검증

### 4.6 구현 로드맵

#### Phase 1: 백엔드 우선 (MVP)
- Node.js, Python 백엔드 프로젝트 지원
- 기본 구현 → 리뷰 → 테스트 파이프라인

#### Phase 2: 프론트엔드 추가
- React, Vue 프로젝트 지원
- 접근성, 성능 리뷰 추가
- 컴포넌트 테스트

#### Phase 3: CLI 및 라이브러리
- CLI 도구 지원
- 라이브러리/패키지 지원
- 사용자 경험 리뷰

#### Phase 4: 모바일 및 데이터 분석
- React Native, Flutter 지원
- Jupyter 노트북 지원
- 시각화 검증

---

## 5. 개선 제안

### 5.1 기획서 템플릿 개선

#### 현재 템플릿 (추정)
```markdown
# 기획서: [기능명]

## 1. 목표
[목표 설명]

## 2. 요구사항
[요구사항 나열]

## 3. 구현 방법 (N개)
### 방법 1: [이름]
[설명]

### 방법 2: [이름]
[설명]
```

#### 개선된 템플릿

```markdown
---
task_name: "user-authentication"
project_type: "backend-node"  # 명시적 지정
project_root: "."  # 상대 경로
num_approaches: 2
priority: "medium"
estimated_complexity: "medium"
---

# 사용자 인증 기능

## 1. 목표
사용자가 안전하게 로그인/로그아웃할 수 있는 인증 시스템 구축

## 2. 프로젝트 컨텍스트
- **기존 코드베이스**: Express 기반 REST API 서버
- **사용 중인 DB**: PostgreSQL (User 테이블 존재)
- **배포 환경**: AWS ECS (컨테이너)
- **팀 기술 스택**: Node.js, TypeScript, Jest

## 3. 기능 요구사항
- [ ] 사용자 로그인 (이메일 + 비밀번호)
- [ ] 사용자 로그아웃
- [ ] 인증 토큰 발급
- [ ] 인증 미들웨어 (보호된 엔드포인트)
- [ ] 비밀번호 해싱 (bcrypt)

## 4. 비기능 요구사항
- 성능: 로그인 응답 시간 < 500ms
- 보안: OWASP Top 10 준수
- 확장성: 수평 확장 가능해야 함
- 테스트: 커버리지 > 80%

## 5. 제약사항
- Redis 사용 금지 (인프라 제약)
- AWS Secrets Manager 사용 (환경변수)
- TypeScript 필수

## 6. 성공 기준
- [ ] 모든 테스트 통과
- [ ] Postman 컬렉션으로 수동 테스트 성공
- [ ] 코드 리뷰 점수 > 4.0/5.0
- [ ] 보안 취약점 0개

## 7. 구현 방법 (2개 비교)

### 방법 1: JWT 기반 인증
- **핵심 아이디어**: Stateless 토큰 기반 인증
- **기술 스택**: jsonwebtoken, bcrypt
- **예상 장점**:
  - 서버 확장 용이 (stateless)
  - 마이크로서비스 친화적
- **예상 단점**:
  - 토큰 무효화 복잡 (blacklist 필요)
  - Refresh token 별도 관리 필요

### 방법 2: 세션 기반 인증
- **핵심 아이디어**: 전통적인 서버 세션
- **기술 스택**: express-session, connect-pg-simple (PostgreSQL session store)
- **예상 장점**:
  - 구현 단순
  - 즉시 무효화 가능
  - 서버에서 완전한 제어
- **예상 단점**:
  - DB 부하 증가 (session 저장)
  - 서버 확장 시 sticky session 필요

## 8. 참고 자료
- 기존 User 모델: `src/models/User.ts`
- API 라우팅 구조: `src/routes/`
- 테스트 예시: `tests/auth.test.ts` (기존)
```

**개선 사항**:
1. ✅ YAML 프론트매터로 메타데이터 명시
2. ✅ 프로젝트 타입 명시
3. ✅ 프로젝트 컨텍스트 (기존 코드, 인프라, 팀 스택)
4. ✅ 제약사항 명확히
5. ✅ 성공 기준 체크리스트

### 5.2 `approaches.json` 스키마 정의

#### JSON Schema 정의

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["task_id", "project_type", "approaches", "checkpoint"],
  "properties": {
    "task_id": {
      "type": "string",
      "pattern": "^task-[0-9]{8}-[0-9]{6}$"
    },
    "project_type": {
      "type": "string",
      "enum": [
        "backend-node",
        "backend-python",
        "backend-go",
        "backend-rust",
        "frontend-react",
        "frontend-vue",
        "frontend-angular",
        "frontend-svelte",
        "cli-python",
        "cli-node",
        "cli-rust",
        "mobile-react-native",
        "mobile-flutter",
        "library-npm",
        "library-pypi",
        "data-analysis",
        "ml-model",
        "desktop-electron"
      ]
    },
    "project_root": {
      "type": "string",
      "description": "Relative path to project root"
    },
    "created_at": {
      "type": "string",
      "format": "date-time"
    },
    "approaches": {
      "type": "array",
      "minItems": 1,
      "maxItems": 10,
      "items": {
        "$ref": "#/definitions/approach"
      }
    },
    "checkpoint": {
      "$ref": "#/definitions/checkpoint"
    }
  },
  "definitions": {
    "approach": {
      "type": "object",
      "required": ["id", "name", "status", "tech_stack", "implementation_guide"],
      "properties": {
        "id": {
          "type": "integer",
          "minimum": 1
        },
        "name": {
          "type": "string",
          "maxLength": 100
        },
        "status": {
          "type": "string",
          "enum": ["pending", "approved", "in_revision", "rejected", "completed"]
        },
        "description": {
          "type": "string",
          "maxLength": 500
        },
        "tech_stack": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "implementation_guide": {
          "type": "object",
          "properties": {
            "steps": {
              "type": "array",
              "items": {
                "type": "string"
              }
            },
            "key_files": {
              "type": "array",
              "items": {
                "type": "string"
              }
            }
          }
        },
        "pros": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "cons": {
          "type": "array",
          "items": {
            "type": "string"
          }
        },
        "complexity": {
          "type": "string",
          "enum": ["low", "medium", "high"]
        },
        "estimated_time_minutes": {
          "type": "integer",
          "minimum": 1
        },
        "revision_history": {
          "type": "array",
          "items": {
            "type": "object",
            "properties": {
              "revision_number": {
                "type": "integer"
              },
              "feedback": {
                "type": "string"
              },
              "revised_at": {
                "type": "string",
                "format": "date-time"
              }
            }
          }
        }
      }
    },
    "checkpoint": {
      "type": "object",
      "required": ["phase", "status", "created_at"],
      "properties": {
        "phase": {
          "type": "integer",
          "minimum": 0,
          "maximum": 6
        },
        "status": {
          "type": "string",
          "enum": ["awaiting_approval", "approved", "in_progress", "completed"]
        },
        "created_at": {
          "type": "string",
          "format": "date-time"
        },
        "approved_at": {
          "type": "string",
          "format": "date-time"
        },
        "approved_approaches": {
          "type": "array",
          "items": {
            "type": "integer"
          }
        }
      }
    }
  }
}
```

### 5.3 에러 복구 전략 구체화

#### 현재 문제
기획서에서 "자동 재시도", "타임아웃", "부분 성공"이라고만 언급되어 있음.

#### 구체화된 전략

```python
class ExecutionError(Exception):
    """실행 중 발생하는 에러 기본 클래스"""
    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.retryable = retryable

class TimeoutError(ExecutionError):
    """타임아웃 에러 (재시도 가능)"""
    def __init__(self, message: str):
        super().__init__(message, retryable=True)

class ClaudeAPIError(ExecutionError):
    """Claude API 에러"""
    def __init__(self, message: str, status_code: int):
        super().__init__(message, retryable=status_code >= 500)
        self.status_code = status_code

class ValidationError(ExecutionError):
    """출력 검증 실패 (재시도 불가)"""
    def __init__(self, message: str):
        super().__init__(message, retryable=False)

async def execute_with_retry(
    func: Callable,
    max_retries: int = 3,
    timeout: float = 300.0,
    backoff_factor: float = 2.0
) -> Any:
    """재시도 로직이 포함된 실행 함수"""

    for attempt in range(max_retries + 1):
        try:
            # 타임아웃 적용
            result = await asyncio.wait_for(
                func(),
                timeout=timeout
            )

            return result

        except asyncio.TimeoutError:
            if attempt < max_retries:
                wait_time = backoff_factor ** attempt
                logger.warning(f"Timeout on attempt {attempt+1}, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
            else:
                raise TimeoutError(f"Exceeded {max_retries} retries due to timeout")

        except ClaudeAPIError as e:
            if e.retryable and attempt < max_retries:
                wait_time = backoff_factor ** attempt
                logger.warning(f"API error on attempt {attempt+1}: {e}, retrying in {wait_time}s")
                await asyncio.sleep(wait_time)
            else:
                raise

        except ValidationError:
            # 검증 에러는 재시도 안 함
            raise

        except Exception as e:
            # 알 수 없는 에러는 로그만 남기고 재시도 안 함
            logger.error(f"Unexpected error: {e}")
            raise

# 사용 예시
async def run_implementation(approach: Approach) -> Result:
    """구현 실행 (재시도 포함)"""

    try:
        result = await execute_with_retry(
            func=lambda: _run_implementation_internal(approach),
            max_retries=3,
            timeout=300.0
        )
        return result

    except TimeoutError as e:
        # 타임아웃: 사용자에게 알림 + 수동 개입 필요
        await notifier.send(
            title="구현 타임아웃",
            message=f"Approach {approach.id}가 5분 내에 완료되지 않았습니다.",
            level="error"
        )
        return Result(status="timeout", error=str(e))

    except ValidationError as e:
        # 검증 실패: 구현 결과가 요구사항 미충족
        await notifier.send(
            title="구현 검증 실패",
            message=f"Approach {approach.id}의 출력이 요구사항을 충족하지 않습니다.",
            level="error"
        )
        return Result(status="validation_failed", error=str(e))

    except Exception as e:
        # 알 수 없는 에러: 로그 + 알림
        logger.exception(f"Unknown error in approach {approach.id}")
        await notifier.send(
            title="예상치 못한 오류",
            message=f"Approach {approach.id} 실행 중 오류: {str(e)}",
            level="error"
        )
        return Result(status="error", error=str(e))
```

#### 부분 성공 처리

```python
async def run_all_implementations(approaches: List[Approach]) -> Dict[int, Result]:
    """모든 구현 실행 (부분 성공 허용)"""

    # 병렬 실행
    tasks = {
        approach.id: asyncio.create_task(run_implementation(approach))
        for approach in approaches
    }

    # 모두 완료될 때까지 대기 (에러도 결과로 반환)
    results = {}
    for approach_id, task in tasks.items():
        try:
            result = await task
            results[approach_id] = result
        except Exception as e:
            # 예외를 결과로 변환
            logger.error(f"Approach {approach_id} failed: {e}")
            results[approach_id] = Result(
                status="error",
                error=str(e)
            )

    # 성공/실패 통계
    successful = [r for r in results.values() if r.status == "completed"]
    failed = [r for r in results.values() if r.status in ["error", "timeout", "validation_failed"]]

    # 알림
    await notifier.send(
        title="구현 완료",
        message=f"성공: {len(successful)}개, 실패: {len(failed)}개",
        level="info" if failed else "success"
    )

    # 실패한 것이 있어도 성공한 것들은 다음 단계로 진행
    return results
```

### 5.4 비용 추적 및 제한

#### 현재 문제
API 비용이 N에 비례한다고만 언급되어 있고, 실제 추적/제한 메커니즘이 없음.

#### 구현 제안

```python
from dataclasses import dataclass
from typing import Dict
import anthropic

@dataclass
class TokenUsage:
    """토큰 사용량"""
    input_tokens: int
    output_tokens: int
    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def estimate_cost_usd(self) -> float:
        """비용 추정 (Claude Sonnet 4.5 기준)"""
        # 2025년 2월 기준 가격
        INPUT_PRICE = 3.00 / 1_000_000  # $3 per MTok
        OUTPUT_PRICE = 15.00 / 1_000_000  # $15 per MTok
        CACHE_WRITE_PRICE = 3.75 / 1_000_000
        CACHE_READ_PRICE = 0.30 / 1_000_000

        return (
            self.input_tokens * INPUT_PRICE +
            self.output_tokens * OUTPUT_PRICE +
            self.cache_creation_tokens * CACHE_WRITE_PRICE +
            self.cache_read_tokens * CACHE_READ_PRICE
        )

class CostTracker:
    """비용 추적기"""

    def __init__(self, budget_usd: float = 10.0):
        self.budget_usd = budget_usd
        self.usage_by_phase: Dict[int, TokenUsage] = {}
        self.usage_by_approach: Dict[int, TokenUsage] = {}
        self.total_usage = TokenUsage(0, 0)

    def record_usage(
        self,
        usage: TokenUsage,
        phase: int,
        approach_id: Optional[int] = None
    ):
        """사용량 기록"""
        # 전체 합산
        self.total_usage.input_tokens += usage.input_tokens
        self.total_usage.output_tokens += usage.output_tokens

        # Phase별 합산
        if phase not in self.usage_by_phase:
            self.usage_by_phase[phase] = TokenUsage(0, 0)
        self.usage_by_phase[phase].input_tokens += usage.input_tokens
        self.usage_by_phase[phase].output_tokens += usage.output_tokens

        # Approach별 합산
        if approach_id:
            if approach_id not in self.usage_by_approach:
                self.usage_by_approach[approach_id] = TokenUsage(0, 0)
            self.usage_by_approach[approach_id].input_tokens += usage.input_tokens
            self.usage_by_approach[approach_id].output_tokens += usage.output_tokens

        # 예산 초과 체크
        current_cost = self.total_usage.estimate_cost_usd()
        if current_cost > self.budget_usd:
            raise BudgetExceededError(
                f"Budget exceeded: ${current_cost:.2f} > ${self.budget_usd:.2f}"
            )

    def get_report(self) -> str:
        """비용 리포트 생성"""
        total_cost = self.total_usage.estimate_cost_usd()

        report = f"""
=== 비용 리포트 ===

전체 사용량:
  - 입력 토큰: {self.total_usage.input_tokens:,}
  - 출력 토큰: {self.total_usage.output_tokens:,}
  - 총 토큰: {self.total_usage.total_tokens:,}
  - 추정 비용: ${total_cost:.4f}
  - 예산 대비: {(total_cost / self.budget_usd * 100):.1f}%

Phase별 사용량:
"""
        for phase, usage in sorted(self.usage_by_phase.items()):
            cost = usage.estimate_cost_usd()
            report += f"  Phase {phase}: {usage.total_tokens:,} tokens (${cost:.4f})\n"

        if self.usage_by_approach:
            report += "\nApproach별 사용량:\n"
            for app_id, usage in sorted(self.usage_by_approach.items()):
                cost = usage.estimate_cost_usd()
                report += f"  Approach {app_id}: {usage.total_tokens:,} tokens (${cost:.4f})\n"

        return report
```

#### config.yaml에 예산 설정 추가

```yaml
execution:
  timeout: 300
  max_retries: 3
  budget_usd: 10.0  # 작업당 예산 (달러)
  warn_at_percentage: 80  # 예산의 80% 사용 시 경고

notifications:
  enabled: true
  budget_warning: true  # 예산 경고 알림
```

---

## 6. 우선순위별 구현 로드맵

### Phase 0: 기반 작업 (1-2주)

**목표**: 기본 구조 구축 및 단일 백엔드 프로젝트 지원

**작업**:
1. ✅ 프로젝트 구조 생성
   - orchestrator/ 디렉토리 구조
   - config.yaml 파싱
   - 로깅 시스템
2. ✅ Claude Code CLI 통합 조사
   - 실제 사용 가능 여부 확인
   - 대안 (Anthropic API) 평가
3. ✅ 기획서 파싱
   - YAML 프론트매터 지원
   - N 추출
   - 프로젝트 타입 감지 (Node.js만)
4. ✅ approaches.json 스키마 정의
   - JSON Schema 작성
   - 검증 로직

**결과물**:
- 동작하는 기본 프레임워크
- Node.js 백엔드 프로젝트 타입 지원
- 기획서 → approaches.json 변환 가능

### Phase 1: MVP - 단일 구현 (N=1) (2-3주)

**목표**: N=1인 경우의 완전한 파이프라인 구축

**작업**:
1. ✅ Phase 1: Architect Agent
   - 기획서 → 1개 approach
   - 프롬프트 템플릿 (backend-node.md)
2. ✅ Phase 1 체크포인트
   - 파일 폴링 방식으로 구현
   - CLI 명령어: approve, revise, abort
3. ✅ Phase 2: Implementer Agent
   - 1개 구현 실행
   - work-done.md 생성 확인
4. ✅ Phase 3: Reviewer + Tester Agent
   - 코드 리뷰 (backend 체크리스트)
   - API 테스트 작성 및 실행
5. ✅ Phase 6: Integrator Agent (Phase 4, 5 생략)
   - 구현을 메인 프로젝트에 통합
   - integration-report.md 생성
6. ✅ 알림 시스템
   - macOS 네이티브 알림 (plyer)
   - 콘솔 로그
7. ✅ 에러 처리
   - 재시도 로직
   - 타임아웃 처리

**결과물**:
- N=1인 경우 완전한 자동화
- 백엔드 Node.js 프로젝트에서 동작
- 실제 사용 가능한 MVP

### Phase 2: 다중 구현 (N≥2) (3-4주)

**목표**: 여러 구현을 병렬로 실행하고 비교

**작업**:
1. ✅ Phase 1 개별 승인/수정/반려
   - 상태 관리 (ApproachStateMachine)
   - CLI 명령어 확장
2. ✅ Phase 2 병렬 실행
   - AsyncIO로 N개 동시 실행
   - 환경 격리 (symlink)
   - 동시 실행 수 제한
3. ✅ Phase 3 병렬 리뷰/테스트
   - 2N개 Agent 동시 실행
4. ✅ Phase 4: Comparator Agent
   - N개 구현 비교
   - 순위 산정
5. ✅ Phase 5: Human Selection
   - 비교 보고서 제공
   - 사용자 선택 대기
6. ✅ 부분 성공 처리
   - 일부 실패 시에도 성공한 것들끼리 비교

**결과물**:
- N≥2 완전 지원
- 병렬 실행 및 비교
- 백엔드 프로젝트에서 동작

### Phase 3: 다양한 프로젝트 타입 (4-6주)

**목표**: 프론트엔드, CLI 등 다양한 타입 지원

**작업**:
1. ✅ 프로젝트 타입 감지 강화
   - React, Vue, Angular
   - Python CLI, Rust CLI
2. ✅ 프론트엔드 지원
   - 프롬프트 템플릿 (frontend-react.md 등)
   - 리뷰 체크리스트 (접근성, 성능)
   - 컴포넌트 테스트
3. ✅ CLI 지원
   - 프롬프트 템플릿 (cli-python.md 등)
   - 입출력 테스트
   - UX 리뷰
4. ✅ Python 백엔드 지원
   - FastAPI, Flask
   - venv 격리
   - pytest

**결과물**:
- 5가지 이상 프로젝트 타입 지원
- 타입별 맞춤 리뷰/테스트

### Phase 4: 고급 기능 (3-4주)

**목표**: 사용성 및 안정성 향상

**작업**:
1. ✅ 비용 추적
   - TokenUsage 추적
   - 예산 제한
   - 비용 리포트
2. ✅ watchdog 기반 파일 감시
   - 폴링 → 이벤트 기반
   - 즉시 반응
3. ✅ 대화형 모드
   - CLI에서 각 approach를 순차적으로 검토
4. ✅ 웹 대시보드 (선택)
   - 실시간 진행 상황
   - 비용 모니터링
   - 비교 보고서 시각화

**결과물**:
- 프로덕션 레벨 안정성
- 비용 제어
- 향상된 UX

### Phase 5: 확장 및 최적화 (진행 중)

**목표**: 성능 최적화 및 추가 기능

**작업**:
- 캐싱 (프롬프트 캐싱)
- 증분 실행 (변경된 부분만 재실행)
- 플러그인 시스템
- 팀 협업 기능 (Slack 통합 등)
- 학습 기능 (과거 선택 패턴 학습)

---

## 7. 결론

### 7.1 핵심 발견사항 재확인

1. **백엔드 중심 설계**: 가장 심각한 문제. 다양한 프로젝트 타입 지원이 필수
2. **Claude Code 통합 불명확**: 실제 구현 가능 여부 확인 필요
3. **병렬 실행 복잡도**: 순차 실행으로 시작 후 점진적 개선 권장
4. **상태 관리 복잡도**: 개별 승인/수정은 V2로 미루고 MVP는 단순화

### 7.2 권장 접근 방식

#### MVP 스코프 (Phase 0-1)
- N=1만 지원
- Node.js 백엔드만 지원
- 전체 승인/수정/중단만 지원
- 순차 실행 (병렬 X)
- 파일 폴링 방식

**이유**: 복잡도를 낮춰 빠르게 동작하는 버전 확보

#### V2 확장 (Phase 2-3)
- N≥2 지원 추가
- 병렬 실행 추가
- 개별 승인/수정/반려
- 프론트엔드, CLI 타입 추가

#### V3 고도화 (Phase 4-5)
- 비용 추적 및 최적화
- 웹 대시보드
- 플러그인 시스템

### 7.3 다음 단계

1. **즉시 조사 필요**:
   - Claude Code CLI의 비대화형/자동화 사용 가능 여부
   - 불가능하다면 Anthropic API 직접 사용 방안

2. **기획서 업데이트**:
   - 프로젝트 타입 지원 섹션 추가
   - 기획서 템플릿에 YAML 프론트매터 추가
   - 프로젝트 타입별 에이전트 전략 추가

3. **MVP 구현 시작**:
   - Phase 0-1 로드맵 따라 구현
   - Node.js 백엔드 프로젝트로 POC
   - 실제 프로젝트에서 테스트

---

**문서 끝**
