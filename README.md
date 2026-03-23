# Multi-Agent Development System

**하나의 기획서, N개의 AI 구현, 최적의 선택**

인간-AI 협업 기획과 AI 자동 구현을 결합한 다중 에이전트 개발 시스템입니다.
여러 구현 방향을 병렬로 탐색하고, AI가 자동으로 리뷰/테스트/비교하여 최적의 솔루션을 찾습니다.

---

## 핵심 개념

```
planning-spec.md (기획서)
    ↓
[Validation] 기획서 검증 (AI 비용 없음)
    ↓
[Git Setup] 타겟 레포 clone/fetch  또는  신규 프로젝트 로컬 git init
    ↓
[Project Analysis] 프로젝트 정적 분석 (Python, 1~2초, AI 비용 없음)
    ↓
Phase 1: Architect → N개 구현 설계
    ↓ [체크포인트: 사용자 승인]
Phase 2: Implementer × N (git worktree 격리, 병렬)
    ↓
Phase 3: Reviewer + Tester × N (병렬, 개별 ON/OFF 가능)
    ↓
Phase 4: Comparator (N≥2, alternative 모드)
         또는 Integrator (concern 모드)
    ↓ [Simplifier: 코드 품질 개선, 선택적]
    ↓
evaluation-result.md → 사용자가 수동으로 브랜치 머지
```

### 왜 이 시스템을 사용하나요?

- **적응형 탐색**: 문제 복잡도에 맞춰 N=1~3 자동 조정
- **신규/기존 프로젝트 모두 지원**: GitHub 레포가 없어도 로컬 git으로 동일한 파이프라인 실행
- **다중 서비스 지원**: `workspaces` 레지스트리에 여러 서비스를 등록하고 독립 관리
- **프로젝트 사전 분석**: Claude가 대규모 프로젝트를 탐색하는 시간 대폭 단축
- **토큰 최적화**: 프로젝트 컨텍스트를 파일 참조로 전달하여 프롬프트 크기 절감
- **객관적 비교**: AI가 각 구현의 장단점을 리뷰, 테스트, 비교
- **git worktree 격리**: 각 구현이 독립 브랜치에서 실행되어 서로 간섭 없음
- **도구 권한 관리**: allow/deny/ask 규칙으로 Claude의 도구 사용을 세밀하게 제어
- **TUI 대시보드**: Textual 기반 대화형 터미널 UI로 질문 큐 실시간 관리

---

## 빠른 시작

### 1. 설치

```bash
pip3 install -r requirements.txt
# 또는
pip3 install -e .
```

**사전 요구사항**: Python 3.8+, Git, Claude Code CLI (`claude` 명령이 PATH에 있어야 함)

### 2. config.yaml 설정

```yaml
github_tokens:
  personal: "ghp_xxxxxxxxxxxx"

workspaces:
  my-service:
    path: ./workspaces/my-service
    projects:
      be:
        target_repo: "https://github.com/user/my-service-BE.git"
        default_branch: "main"
        github_token: "personal"
      new-module:
        target_repo: ""          # 비워두면 신규 프로젝트 모드 (로컬 git init)
        default_branch: "main"

watch:
  dirs:
    - workspace: "my-service"
      path: ./workspaces/my-service/planning/completed

pipeline:
  checkpoint_phase1: true
  num_approaches: 1
  enable_review: true
  enable_test: true
  enable_simplifier: true
```

### 3. 기획서 작성

`workspaces/my-service/planning/in-progress/{기능명}/planning-spec.md` 작성:

```markdown
# 기획서: 관리자 로그인 시스템

## 달성 목표
- Spring Security 기반 ID/PW 인증
- JWT 토큰 발급

## 구현 방법 탐색

**탐색할 방법 개수: 2개**

### 방법 1: Spring Security + JWT
- **핵심 아이디어**: SecurityFilterChain에서 JWT 검증
- **기술 스택**: Spring Security, JJWT, BCrypt
...
```

### 4. 파이프라인 실행

```bash
# TUI 대시보드와 함께 실행
python3 cli.py run -s workspaces/my-service/planning/in-progress/add-auth/planning-spec.md -v

# 또는 Watch 모드 (completed/로 이동 시 자동 실행)
python3 cli.py watch
```

기획서를 `completed/`로 이동하면 Watch 모드에서 자동 감지:
```bash
mv workspaces/my-service/planning/in-progress/add-auth \
   workspaces/my-service/planning/completed/add-auth
```

### 5. 체크포인트 승인

```bash
python3 cli.py approve <task-id>                     # 전체 승인
python3 cli.py approve <task-id> --approaches 1,2   # 개별 승인 (N≥2)
python3 cli.py approve <task-id> --reject 3          # 개별 반려
```

### 6. 결과 확인 및 머지

```bash
cat workspaces/my-service/work/<task-id>/evaluation-result.md

# 원하는 구현 브랜치 머지
cd workspaces/my-service/my-service-BE
git merge <task-id>/impl-1
```

---

## 프로젝트 구조

```
multi-agent-dev-system/
├── cli.py                          # CLI 진입점
├── config.yaml                     # 설정 파일
├── requirements.txt
│
├── orchestrator/                   # 핵심 오케스트레이터
│   ├── main.py                     #   Orchestrator 클래스
│   ├── executor.py                 #   ClaudeExecutor
│   ├── permission_handler.py       #   도구 권한 관리
│   ├── stream_processor.py         #   NDJSON 스트림 파싱
│   ├── watcher.py                  #   파일 감시
│   ├── agents/
│   │   ├── architect.py            #   Phase 1
│   │   ├── implementer.py          #   Phase 2
│   │   ├── reviewer.py             #   Phase 3
│   │   ├── tester.py               #   Phase 3
│   │   ├── comparator.py           #   Phase 4 (alternative)
│   │   ├── integrator.py           #   Phase 4 (concern)
│   │   └── simplifier.py           #   후처리
│   ├── queue/                      #   질문 큐 시스템
│   ├── tui/                        #   TUI 대시보드 (Textual)
│   └── utils/
│       ├── git_manager.py          #   Git clone/worktree/신규 프로젝트
│       ├── project_analyzer.py     #   프로젝트 정적 분석
│       ├── spec_parser.py          #   기획서 파싱
│       └── spec_validator.py       #   기획서 검증
│
├── prompts/                        # 에이전트 프롬프트 템플릿
│   ├── architect.md
│   ├── implementer.md
│   ├── reviewer.md
│   ├── tester.md
│   ├── comparator.md
│   ├── integrator.md
│   └── simplifier.md
│
└── workspaces/                     # 서비스별 워크스페이스
    └── {service}/
        ├── {service}-BE/           #   Root Project (GitHub 클론)
        ├── {service}-FE/           #   Root Project (선택)
        ├── .cache/                 #   Git 캐시 (자동 관리)
        ├── planning/
        │   ├── in-progress/
        │   └── completed/
        └── work/
            └── task-{timestamp}/
```

---

## AI 에이전트

| 에이전트 | Phase | 역할 |
|---------|-------|------|
| **Architect** | 1 | 기획서 + 프로젝트 컨텍스트 → N개 구현 설계 (approaches.json) |
| **Implementer** | 2 | 할당된 설계를 git worktree에서 구현 + 커밋 |
| **Reviewer** | 3 | 5가지 관점 코드 리뷰 (품질/설계/보안/성능/테스트용이성) |
| **Tester** | 3 | 테스트 작성·실행·결과 분석 |
| **Comparator** | 4 | N개 구현 비교·순위·추천 (alternative 모드, N≥2) |
| **Integrator** | 4 | N개 구현 통합·충돌 해결·글루 코드 (concern 모드) |
| **Simplifier** | 후처리 | 선택된 구현 코드 품질 개선 |

---

## 파이프라인 모드

### Alternative 모드 (기본)
각 approach가 독립적인 대안. Comparator가 최적을 추천.

### Concern 모드
각 approach가 보완적 관심사 (예: FE/BE). Integrator가 모두 통합.

기획서에서 지정:
```markdown
**파이프라인 모드: concern**
```

---

## 신규 프로젝트 지원

GitHub 레포 없이 처음부터 시작하는 경우 `target_repo`를 비워두면 됩니다.

```yaml
projects:
  new-module:
    target_repo: ""    # 빈 값 = 로컬 git 저장소 자동 초기화
```

시스템이 `.cache/project/`에 `git init` + 빈 초기 커밋을 생성하고, 이후 동일한 worktree 기반 파이프라인을 실행합니다.

---

## CLI 명령어

| 명령어 | 설명 |
|--------|------|
| `init` | config.yaml 생성 |
| `run -s <spec>` | 파이프라인 실행 |
| `watch` | 감시 모드 |
| `approve <task-id>` | 체크포인트 승인 |
| `approve <task-id> --approaches 1,2` | 개별 approach 승인 |
| `approve <task-id> --reject 3` | 개별 approach 반려 |
| `status [task-id]` | 상태 확인 |
| `abort <task-id>` | 태스크 중단 |
| `questions <task-id>` | 대기 중인 질문 확인 |
| `answer <task-id> <q-id> <응답>` | 질문에 답변 |

---

## 문서

- **[.claude/docs/system-overview.md](.claude/docs/system-overview.md)** — 시스템 전체 흐름 및 Phase 상세
- **[.claude/docs/agents.md](.claude/docs/agents.md)** — 에이전트 설계 및 인터페이스
- **[.claude/docs/orchestrator.md](.claude/docs/orchestrator.md)** — Orchestrator 설계 및 config.yaml 전체 스키마
- **[.claude/docs/workspace-structure.md](.claude/docs/workspace-structure.md)** — 워크스페이스 디렉토리 구조
- **[.claude/docs/planning-guide.md](.claude/docs/planning-guide.md)** — 기획서 작성 가이드
- **[USAGE.md](USAGE.md)** — CLI 레퍼런스 및 실전 시나리오

---

**v2.05** | MIT License
