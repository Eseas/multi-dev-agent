# Multi-Agent Development System

**하나의 기획서, N개의 AI 구현, 최적의 선택**

인간-AI 협업 기획과 AI 자동 구현을 결합한 다중 에이전트 개발 시스템입니다.
여러 구현 방향을 병렬로 탐색하고, AI가 자동으로 리뷰/테스트/비교하여 최적의 솔루션을 찾습니다.

---

## 핵심 개념

```
당신의 아이디어 (planning-spec.md)
    ↓
프로젝트 자동 분석 (Python, 1-2초, AI 비용 없음)
    ↓
Phase 1-4: AI 에이전트 자동 실행
    ├─ Architect: 기획서 → N개 구현 설계
    ├─ Implementer x N: 병렬 구현 (git worktree 격리)
    ├─ Reviewer + Tester x N: 병렬 리뷰/테스트 (개별 ON/OFF 가능)
    ├─ Comparator: N개 비교 분석 (N≥2, alternative 모드)
    └─ Integrator: N개 통합 (concern 모드)
    ↓
evaluation-result.md → 사용자가 수동으로 브랜치 머지
```

### 왜 이 시스템을 사용하나요?

- **적응형 탐색**: 문제 복잡도에 맞춰 1~3가지 방법 자동 조정
- **다중 프로젝트 지원**: `projects` 레지스트리에 여러 프로젝트를 등록하고 독립 관리
- **프로젝트 사전 분석**: Claude가 대규모 프로젝트를 탐색하는 시간 대폭 단축
- **토큰 최적화**: 프로젝트 컨텍스트를 파일 참조로 전달하여 프롬프트 크기 절감
- **객관적 비교**: AI가 각 방법의 장단점을 리뷰, 테스트, 비교
- **위험 감소**: 한 가지 방법에 올인하지 않고 대안 확보
- **도구 권한 관리**: allow/deny/ask 규칙으로 Claude의 도구 사용을 세밀하게 제어
- **TUI 대시보드**: Textual 기반 대화형 터미널 UI로 질문 큐 실시간 관리
- **질문 큐 시스템**: 병렬 에이전트의 모든 질문(권한/체크포인트/오류)을 통합 큐로 관리

---

## 빠른 시작

### 1. 설치

```bash
# 의존성 설치
pip3 install -r requirements.txt

# 또는 패키지로 설치 (권장)
pip3 install -e .
```

**사전 요구사항**:
- Python 3.8+
- Git
- **Claude Code CLI** (시스템 PATH에 `claude` 명령)

### 2. 초기화

```bash
# 설정 파일 생성
python3 cli.py init

# config.yaml 편집: projects 레지스트리에 프로젝트 등록 필수!
```

### 3. config.yaml 설정

```yaml
github_tokens:
  personal: "ghp_xxxxxxxxxxxx"

projects:
  my-project:
    target_repo: "https://github.com/user/repo.git"
    default_branch: "main"
    github_token: "personal"    # github_tokens의 키 이름

watch:
  dirs:
    - path: ./workspace/planning/completed
      project: "my-project"     # projects의 키 이름
```

### 4. 기획서 작성

`planning-spec.md` 파일을 작성합니다.

**예시**:
```markdown
# 기획서: 관리자 로그인 시스템

## 요구사항
- Spring Security 기반 ID/PW 인증
- BCrypt 비밀번호 암호화
- JWT 토큰 발급

## 구현 방법

기술 스택: Spring Security, JJWT, BCrypt

### 방법 1: Spring Security + JWT
- **핵심 아이디어**: SecurityFilterChain에서 JWT 검증
- **기술 스택**: Spring Security, JJWT, BCrypt
...
```

### 5. 파이프라인 실행

```bash
# TUI 대시보드와 함께 실행 (기본)
python3 cli.py run -s planning-spec.md -v

# TUI 없이 기존 방식으로 실행
python3 cli.py run -s planning-spec.md -v --no-tui
```

**자동 진행**:
1. 기획서 검증
2. Git clone/fetch (타겟 프로젝트)
3. **프로젝트 분석** (~1-2초, Python 기반)
4. Phase 1 (Architect) → **체크포인트** (사용자 승인 대기)
5. Phase 2 (Implementer) → Phase 3 (Review + Test) → Phase 4 (Comparator/Integrator)
6. `evaluation-result.md` 생성

### 6. 체크포인트 승인

다른 터미널에서:
```bash
# 전체 승인
python3 cli.py approve <task-id>

# N≥2: 특정 approach만 승인
python3 cli.py approve <task-id> --approaches 1,2
```

### 7. 결과 확인 및 통합

```bash
# 평가 결과 확인
python3 cli.py status <task-id>
cat workspace/tasks/<task-id>/evaluation-result.md

# 비교 보고서 (N≥2)
cat workspace/tasks/<task-id>/comparator/comparison.md

# 원하는 브랜치 머지
cd <타겟-프로젝트>
git merge <task-id>/impl-<N>
```

---

## 프로젝트 구조

```
multi-agent-dev-system/
├── cli.py                         # CLI 진입점
├── config.yaml                    # 설정 파일 (git ignore됨)
├── requirements.txt               # Python 의존성
├── setup.py                       # 패키지 설정
│
├── orchestrator/                  # 핵심 오케스트레이터
│   ├── main.py                    #   Orchestrator 클래스
│   ├── executor.py                #   ClaudeExecutor (stream-json 프로토콜)
│   ├── permission_handler.py      #   도구 권한 관리 (allow/deny/ask)
│   ├── stream_processor.py        #   NDJSON 스트림 파싱
│   ├── watcher.py                 #   FileWaitHelper (파일 대기)
│   ├── agents/                    #   AI 에이전트
│   │   ├── base.py                #     BaseAgent (공통 기반)
│   │   ├── architect.py           #     Phase 1: 구현 설계
│   │   ├── implementer.py         #     Phase 2: 코드 구현
│   │   ├── reviewer.py            #     Phase 3: 코드 리뷰
│   │   ├── tester.py              #     Phase 3: 테스트
│   │   ├── comparator.py          #     Phase 4: 비교 분석 (alternative 모드)
│   │   └── integrator.py          #     Phase 4: 통합 (concern 모드)
│   ├── queue/                     #   질문 큐 시스템
│   │   ├── models.py              #     Question, Answer, Enum 데이터 모델
│   │   └── question_queue.py      #     Thread-safe 질문 큐
│   ├── tui/                       #   TUI 대시보드
│   │   ├── app.py                 #     Textual 기반 대시보드 앱
│   │   └── widgets.py             #     커스텀 위젯 (QuestionCard, StatusPanel 등)
│   └── utils/                     #   유틸리티
│       ├── atomic_write.py        #     원자적 파일 쓰기
│       ├── git_manager.py         #     Git clone/worktree
│       ├── logger.py              #     로깅 설정
│       ├── notifier.py            #     시스템 알림 (macOS/Linux/Windows)
│       ├── project_analyzer.py    #     프로젝트 사전 분석
│       ├── spec_parser.py         #     기획서 파싱
│       └── spec_validator.py      #     기획서 검증
│
├── prompts/                       # 에이전트 프롬프트 템플릿
│   ├── architect.md
│   ├── implementer.md
│   ├── reviewer.md
│   ├── tester.md
│   ├── comparator.md
│   └── integrator.md
│
└── workspace/                     # 런타임 워크스페이스
    ├── .cache/                    #   Git clone 캐시
    ├── planning/                  #   기획 단계
    │   ├── in-progress/           #     기획 작성 중
    │   └── completed/             #     완성된 기획서 (자동 실행)
    └── tasks/                     #   실행 중/완료 태스크
        └── task-YYYYMMDD-HHMMSS/
            ├── manifest.json      #     태스크 상태
            ├── planning-spec.md   #     기획서 복사본
            ├── project-context.md #     프로젝트 컨텍스트 (에이전트 참조)
            ├── question-queue.json #    질문 큐 상태 (런타임)
            ├── architect/         #     Architect 출력
            ├── implementations/   #     구현들 (git worktree)
            └── comparator/        #     비교 결과 (N≥2)
```

---

## 파이프라인 모드

### Alternative 모드 (기본)

각 approach가 독립적인 대안. 최적의 하나를 선택합니다.

```
Phase 1: Architect → N개 독립 설계
Phase 2: Implementer x N (병렬)
Phase 3: Reviewer + Tester x N (병렬, 개별 ON/OFF)
Phase 4: Comparator → 비교/순위/추천
→ evaluation-result.md
```

### Concern 모드

각 approach가 보완적 관심사 (예: frontend/backend). 모두 통합합니다.

```
Phase 1: Architect → N개 관심사별 설계 + API 계약
Phase 2: Implementer x N (병렬, API 계약 준수)
Phase 3: Reviewer + Tester x N (병렬, 개별 ON/OFF)
Phase 4: Integrator → 통합/충돌 해결/글루 코드
→ evaluation-result.md
```

---

## AI 에이전트

| 에이전트 | Phase | 역할 |
|---------|-------|------|
| **Architect** | 1 | 기획서 + 프로젝트 컨텍스트 분석 → N개 구현 설계 (JSON) |
| **Implementer** | 2 | 할당된 설계를 독립 git worktree에서 구현 + work-done.md 작성 |
| **Reviewer** | 3 | 5가지 관점 코드 리뷰 (품질/설계/보안/성능/테스트용이성) |
| **Tester** | 3 | 테스트 작성 + 실행 + 결과 분석 (test_results.json) |
| **Comparator** | 4 | N개 구현 비교/순위/추천 (alternative 모드, N≥2) |
| **Integrator** | 4 | N개 구현 통합/충돌 해결/글루 코드 (concern 모드) |

---

## 설정 (config.yaml)

```yaml
workspace:
  root: ./workspace

github_tokens:                       # 토큰 레지스트리 (이름: 값)
  personal: "ghp_xxxxxxxxxxxx"

projects:                            # 프로젝트 레지스트리 (이름: 설정)
  my-project:
    target_repo: "https://github.com/user/repo.git"  # 필수
    default_branch: "main"
    github_token: "personal"         # github_tokens의 키 이름

execution:
  timeout: 600                       # Claude 실행 타임아웃 (초)
  max_retries: 3

pipeline:
  checkpoint_phase1: true            # Phase 1 후 체크포인트 활성화
  num_approaches: 1                  # 기본 구현 개수
  enable_review: true                # Phase 3: Review 활성화/비활성화
  enable_test: true                  # Phase 3: Test 활성화/비활성화

watch:
  dirs:                              # 감시할 디렉토리 목록
    - path: ./workspace/planning/completed
      project: "my-project"          # projects의 키 이름

validation:
  enabled: true
  auto_revalidate: true
  strict_mode: false

permissions:                         # 도구 권한 규칙
  allow:                             # 자동 허용
    - "Read(*)"
    - "Glob(*)"
    - "Grep(*)"
  deny:                              # 자동 거부
    - "Bash(rm -rf *)"
    - "Bash(sudo *)"
  ask:                               # 사용자 승인 필요
    - "Bash(*)"
    - "Write(*)"
  ask_timeout: 300

queue:
  default_timeout: 3600              # 기본 질문 타임아웃 (초)
  permission_timeout: 300            # 권한 질문 타임아웃
  checkpoint_timeout: 3600           # 체크포인트 타임아웃

notifications:
  enabled: true
  sound: true
```

---

## CLI 명령어

| 명령어 | 설명 |
|--------|------|
| `init` | config.yaml 생성 |
| `run -s <spec>` | 파이프라인 실행 |
| `approve <task-id>` | 체크포인트 승인 |
| `approve <task-id> --approaches 1,2` | 개별 approach 승인 (N≥2) |
| `approve <task-id> --reject 3` | 개별 approach 반려 (N≥2) |
| `select <task-id> <impl-id>` | 구현 선택 (N≥2) |
| `revise <task-id> -f "피드백"` | 수정 요청 |
| `abort <task-id>` | 태스크 중단 |
| `status [task-id]` | 상태 확인 |
| `watch` | 감시 모드 (다중 프로젝트/경로 지원) |
| `questions <task-id>` | 대기 중인 질문 확인 |
| `answer <task-id> <q-id> <응답>` | 질문에 답변 (CLI에서 직접) |

자세한 사용법은 [USAGE.md](USAGE.md)를 참고하세요.

---

## 문서

- **[USAGE.md](USAGE.md)** — 상세 사용 가이드, CLI 레퍼런스, 실전 시나리오, 트러블슈팅
- **[CLAUDE.md](CLAUDE.md)** — Claude Code 설정 및 에이전트 가이드라인
- **[question-queue-system.md](question-queue-system.md)** — 질문 큐 시스템 상세 설계 문서

---

**v2.00** | MIT License
