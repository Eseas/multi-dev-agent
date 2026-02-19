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
    └─ Comparator: N개 비교 분석 (N≥2)
    ↓
evaluation-result.md → 사용자가 수동으로 브랜치 머지
```

### 왜 이 시스템을 사용하나요?

- **적응형 탐색**: 문제 복잡도에 맞춰 1~3가지 방법 자동 조정
- **프로젝트 사전 분석**: Claude가 대규모 프로젝트를 탐색하는 시간 대폭 단축
- **토큰 최적화**: 프로젝트 컨텍스트를 파일 참조로 전달하여 프롬프트 크기 절감
- **객관적 비교**: AI가 각 방법의 장단점을 리뷰, 테스트, 비교
- **위험 감소**: 한 가지 방법에 올인하지 않고 대안 확보

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

# config.yaml 편집: project.target_repo 설정 필수!
```

### 3. 기획서 작성

`planning-spec.md` 파일을 작성합니다.

**필수 요소**:
- `## 구현 방법` 섹션
- 각 방법의 차별점 명확화

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

### 4. 파이프라인 실행

```bash
python3 cli.py run -s planning-spec.md -v
```

**자동 진행**:
1. 기획서 검증
2. Git clone/fetch (타겟 프로젝트)
3. **프로젝트 분석** (~1-2초, Python 기반)
4. Phase 1 (Architect) → **체크포인트** (사용자 승인 대기)
5. Phase 2 (Implementer) → Phase 3 (Review + Test) → Phase 4 (Comparator, N≥2)
6. `evaluation-result.md` 생성

### 5. 체크포인트 승인

다른 터미널에서:
```bash
# 전체 승인
python3 cli.py approve <task-id>

# N≥2: 특정 approach만 승인
python3 cli.py approve <task-id> --approaches 1,2
```

### 6. 결과 확인 및 통합

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
│   ├── executor.py                #   ClaudeExecutor (Claude Code 실행)
│   ├── watcher.py                 #   FileWaitHelper (파일 대기)
│   ├── agents/                    #   AI 에이전트
│   │   ├── base.py                #     BaseAgent (공통 기반)
│   │   ├── architect.py           #     Phase 1: 구현 설계
│   │   ├── implementer.py         #     Phase 2: 코드 구현
│   │   ├── reviewer.py            #     Phase 3: 코드 리뷰
│   │   ├── tester.py              #     Phase 3: 테스트
│   │   └── comparator.py          #     Phase 4: 비교 분석
│   └── utils/                     #   유틸리티
│       ├── project_analyzer.py    #     프로젝트 사전 분석
│       ├── git_manager.py         #     Git clone/worktree
│       ├── notifier.py            #     시스템 알림
│       ├── spec_parser.py         #     기획서 파싱
│       └── spec_validator.py      #     기획서 검증
│
├── prompts/                       # 에이전트 프롬프트 템플릿
│   ├── architect.md
│   ├── implementer.md
│   ├── reviewer.md
│   ├── tester.md
│   └── comparator.md
│
└── workspace/                     # 런타임 워크스페이스
    ├── tasks/                     #   실행 중/완료 태스크
    │   └── task-YYYYMMDD-HHMMSS/
    │       ├── planning-spec.md   #     기획서 복사본
    │       ├── manifest.json      #     태스크 상태
    │       ├── project-context.md #     프로젝트 컨텍스트 (에이전트 참조)
    │       ├── architect/         #     Architect 출력
    │       └── implementations/   #     구현들 (git worktree)
    └── .cache/                    #   Git clone 캐시
```

---

## 파이프라인 흐름

### N=1 (단일 구현)

```
기획서 → 검증 → Git clone/fetch → 프로젝트 분석
    → Phase 1: Architect
    → [Checkpoint]
    → Phase 2: Implementer (1개)
    → Phase 3: Reviewer + Tester (config로 개별 ON/OFF)
    → evaluation-result.md 생성
```

### N≥2 (복수 구현)

```
기획서 → 검증 → Git clone/fetch → 프로젝트 분석
    → Phase 1: Architect (N개 설계)
    → [Checkpoint]
    → Phase 2: Implementer x N (병렬)
    → Phase 3: Reviewer + Tester x N (병렬, config로 개별 ON/OFF)
    → Phase 4: Comparator (비교 분석)
    → evaluation-result.md 생성
```

---

## 설정 (config.yaml)

```yaml
workspace:
  root: ./workspace

project:
  target_repo: "https://github.com/your-org/your-project.git"  # 필수
  default_branch: "main"
  github_token: ""                 # private repo용

execution:
  timeout: 600                     # Claude 실행 타임아웃 (초)
  max_retries: 3

pipeline:
  checkpoint_phase1: true          # Phase 1 후 체크포인트 활성화
  num_approaches: 1                # 기본 구현 개수
  enable_review: true              # Phase 3: Review 활성화/비활성화
  enable_test: true                # Phase 3: Test 활성화/비활성화

watch:
  dirs:                            # 감시할 디렉토리 목록 (완전한 경로)
    - ./workspace/planning/completed
    # - /other/project/planning/completed  # 여러 경로 추가 가능

validation:
  enabled: true
  auto_revalidate: true            # watch 모드에서 기획서 수정 시 자동 재실행
  strict_mode: false

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
| `select <task-id> <impl-id>` | 구현 선택 (N≥2) |
| `revise <task-id> -f "피드백"` | 수정 요청 |
| `abort <task-id>` | 태스크 중단 |
| `status [task-id]` | 상태 확인 |
| `watch` | 감시 모드 (다중 경로 지원) |

자세한 사용법은 [USAGE.md](USAGE.md)를 참고하세요.

---

## 문서

- **[USAGE.md](USAGE.md)** - 상세 사용 가이드
- **[CLAUDE.md](CLAUDE.md)** - Claude Code 설정 및 가이드라인
- **[multi-agent-dev-system-implementation-guide.md](multi-agent-dev-system-implementation-guide.md)** - 구현 가이드

---

**MIT License**
