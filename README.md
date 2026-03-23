# Multi-Agent Development System

하나의 기획서로부터 N개의 AI 구현을 병렬로 생성하고, 자동 리뷰/테스트/비교를 거쳐 최적의 솔루션을 선택하는 다중 에이전트 개발 파이프라인.

---

## 목차

1. [개념 및 동작 방식](#개념-및-동작-방식)
2. [사전 요구사항 및 설치](#사전-요구사항-및-설치)
3. [config.yaml 설정](#configyaml-설정)
4. [워크스페이스 구성](#워크스페이스-구성)
5. [기획서 작성](#기획서-작성)
6. [파이프라인 실행](#파이프라인-실행)
7. [체크포인트 승인](#체크포인트-승인)
8. [결과 확인 및 머지](#결과-확인-및-머지)
9. [CLI 명령어 레퍼런스](#cli-명령어-레퍼런스)
10. [파이프라인 모드](#파이프라인-모드)
11. [도구 권한 시스템](#도구-권한-시스템)
12. [질문 큐 & TUI 대시보드](#질문-큐--tui-대시보드)
13. [에이전트 상세](#에이전트-상세)
14. [프로젝트 구조](#프로젝트-구조)

---

## 개념 및 동작 방식

### 전체 파이프라인

```
기획서 작성 (사람 + Claude Code)
    |
    v
[Validation]        기획서 규칙 검증 (AI 비용 없음)
    |
    v
[Git Setup]         타겟 레포 clone/fetch 또는 신규 프로젝트 로컬 git init
    |
    v
[Project Analysis]  프로젝트 정적 분석 (Python, ~1초, AI 비용 없음)
    |               → 구조/기술스택/모듈 분석 → .project-profile.json 캐싱
    |               → 기획서 관련 모듈만 컨텍스트 추출 → project-context.md
    v
[Phase 1]  Architect: 기획서 + 프로젝트 컨텍스트 → N개 구현 설계 (approaches.json)
    |
    v
[Checkpoint]        사용자 검토 및 승인 (개별 approach 승인/반려 가능)
    |
    v
[Phase 2]  Implementer × N: 각 설계를 독립 git worktree에서 병렬 구현
    |
    v
[Phase 3]  Reviewer + Tester × N: 병렬 코드 리뷰 + 테스트 (개별 ON/OFF 가능)
    |
    v
[Phase 4]  Comparator (alternative 모드, N≥2): N개 구현 비교·순위·추천
           또는 Integrator (concern 모드): N개 구현 통합·글루 코드
    |
    v
[Simplifier]        코드 품질 개선 (선택적)
    |
    v
evaluation-result.md → 사용자가 수동으로 브랜치 머지
```

### 핵심 특징

- **적응형 N값**: 기획서에서 명시하거나(`탐색할 방법 개수: N개`), 시스템이 복잡도에 따라 자동 결정 (1~3)
- **git worktree 격리**: 각 구현체가 독립 브랜치에서 실행되어 서로 간섭 없음
- **토큰 최적화**: 프로젝트 컨텍스트를 파일로 저장하고 에이전트가 Read 도구로 참조 (대규모 레포 탐색 시간 단축)
- **신규/기존 프로젝트 모두 지원**: GitHub 레포 없이 로컬 git으로 동일한 파이프라인 실행
- **파이프라인 모드**: 독립 대안 비교(alternative) 또는 보완적 관심사 통합(concern)
- **세밀한 권한 제어**: allow/deny/ask 규칙으로 Claude의 도구 사용 제어
- **TUI 대시보드**: 병렬 에이전트의 모든 질문/권한/체크포인트를 통합 관리

---

## 사전 요구사항 및 설치

### 요구사항

- Python 3.8+
- Git
- Claude Code CLI (`claude` 명령이 PATH에 있어야 함)

### 설치

```bash
# 저장소 클론 후
pip3 install -e .

# 또는
pip3 install -r requirements.txt
```

설치 후 `multi-agent-dev` 명령 또는 `python3 cli.py` 로 실행할 수 있습니다.

---

## config.yaml 설정

시스템 루트에 `config.yaml` 파일을 작성합니다. `python3 cli.py init` 으로 초기 템플릿을 생성할 수 있습니다.

### 전체 스키마

```yaml
# GitHub 토큰 레지스트리 (키: 이름, 값: 토큰)
github_tokens:
  personal: "ghp_xxxxxxxxxxxx"
  work: "ghp_yyyyyyyyyyyy"

# 서비스별 워크스페이스 등록
workspaces:
  {서비스명}:
    path: ./workspaces/{서비스명}        # 워크스페이스 경로
    projects:
      {프로젝트키}:
        target_repo: "https://github.com/user/repo.git"
        default_branch: "main"
        github_token: "personal"         # github_tokens의 키 이름
      {신규프로젝트키}:
        target_repo: ""                  # 비워두면 로컬 git init (신규 프로젝트)
        default_branch: "main"

# 에이전트 프롬프트 경로
prompts:
  directory: ./prompts

# Claude 실행 설정
execution:
  timeout: 600                           # 실행 타임아웃 (초)
  max_retries: 3

# 파이프라인 설정
pipeline:
  checkpoint_phase1: true               # Phase 1 후 체크포인트 활성화
  num_approaches: 2                     # 기본 구현 개수 (기획서에서 오버라이드 가능)
  enable_review: true                   # Phase 3: Reviewer 활성화
  enable_test: true                     # Phase 3: Tester 활성화
  enable_simplifier: false             # Simplifier 활성화

# Watch 모드: 기획서 자동 감지 경로
watch:
  dirs:
    - workspace: "{서비스명}"           # workspaces의 키 이름
      path: ./workspaces/{서비스명}/planning/completed

# 기획서 검증
validation:
  enabled: true
  auto_revalidate: true
  strict_mode: false                    # true이면 검증 실패 시 파이프라인 중단

# Claude 도구 권한 규칙
permissions:
  allow:                                # 자동 허용
    - "Read(*)"
    - "Glob(*)"
    - "Grep(*)"
  deny:                                 # 자동 거부
    - "Bash(rm -rf *)"
    - "Bash(sudo *)"
  ask:                                  # 사용자 승인 필요
    - "Bash(*)"
    - "Write(*)"
  ask_timeout: 300                      # 승인 대기 시간 (초)

# 질문 큐 타임아웃
queue:
  default_timeout: 3600
  permission_timeout: 300
  checkpoint_timeout: 3600

# 시스템 알림
notifications:
  enabled: true
  sound: true
```

### 신규 프로젝트 (GitHub 레포 없음)

`target_repo`를 비워두면 시스템이 첫 실행 시 `.cache/{프로젝트키}/` 에 자동으로 `git init` + 빈 초기 커밋을 생성하고, 이후 동일한 worktree 기반 파이프라인을 실행합니다.

---

## 워크스페이스 구성

하나의 서비스 = 하나의 워크스페이스. FE/BE/DB 등은 서비스의 하위 프로젝트입니다.

### 디렉토리 구조

```
workspaces/
└── {서비스명}/
    ├── {서비스명}-BE/          # Root Project (GitHub 레포 클론)
    ├── {서비스명}-FE/          # Root Project (선택)
    ├── .cache/                 # Git 캐시 (시스템 자동 관리, 직접 편집 금지)
    │   └── {프로젝트명}/       #   bare clone 또는 로컬 init 저장소
    ├── planning/
    │   ├── in-progress/        # 기획 작성 중
    │   └── completed/          # 완성된 기획서 (여기로 이동하면 자동 실행)
    └── work/
        └── task-{timestamp}/   # 태스크 실행 디렉토리
            ├── manifest.json
            ├── timeline.log
            ├── planning-spec.md
            ├── project-context.md
            ├── architect/
            │   └── approaches.json
            ├── implementations/
            │   ├── impl-1/     # git worktree (브랜치: task-{id}/impl-1)
            │   └── impl-2/     # git worktree (브랜치: task-{id}/impl-2)
            ├── review-1/
            │   └── review.md
            ├── review-2/
            │   └── review.md
            ├── test-1/
            │   └── test-results.json
            ├── comparator/
            │   └── comparison.md
            └── evaluation-result.md
```

### 새 서비스 추가

```bash
# 디렉토리 생성
mkdir -p workspaces/{서비스명}/planning/{in-progress,completed}

# Root Project 클론 (기존 레포가 있는 경우)
git clone {repo-url} workspaces/{서비스명}/{서비스명}-BE

# config.yaml에 workspaces 항목 추가 후 watch.dirs에 경로 등록
```

---

## 기획서 작성

기획서(`planning-spec.md`)는 파이프라인 전체의 입력입니다. Claude Code와 대화하며 작성하거나 직접 작성합니다.

### 저장 위치

```
workspaces/{서비스명}/planning/in-progress/{기능명}/planning-spec.md
```

### 기획서 템플릿

```markdown
# 기획서: {기능명}

## 1. 목표
- 이 기능이 해결하는 문제
- 성공 기준 (측정 가능한 지표)

## 2. 제약사항
- 기술적 제약
- 기존 시스템과의 통합 포인트
- 성능/보안 요구사항

## 3. 구현 방법 탐색

**탐색할 방법 개수: 2개**
<!-- 1, 2, 3 중 하나 지정. 또는 "자동"으로 시스템이 복잡도 기반 판단 -->

**파이프라인 모드: alternative**
<!-- alternative (독립 구현 비교, 기본값) 또는 concern (보완적 통합) -->

### 방법 1: {방법명}
- **핵심 아이디어**: 한 문장 요약
- **예상 장점**: 구체적으로
- **예상 단점**: 솔직하게
- **기술 스택**: 실제 라이브러리명 명시

### 방법 2: {방법명}
- **핵심 아이디어**: 한 문장 요약
- **예상 장점**:
- **예상 단점**:
- **기술 스택**:

## 4. 대상 Root Project
- 반영될 프로젝트 명시 (예: {서비스명}-BE)

## 5. 참고사항
- 관련 이슈, 기존 코드 위치, 외부 문서 링크 등
```

### N값 결정 가이드

| 상황 | 권장 N |
|------|--------|
| 버그 수정, 단순 변경 | 1 |
| 일반 기능 개발 (기본값) | 2 |
| 중요한 아키텍처 결정, 기술 스택 선택 | 3 |
| 시스템이 판단 | 자동 |

---

## 파이프라인 실행

### 방법 1: 직접 실행

```bash
python3 cli.py run -s workspaces/{서비스명}/planning/in-progress/{기능명}/planning-spec.md
```

특정 워크스페이스/프로젝트를 지정하려면:

```bash
python3 cli.py run -s {spec경로} --workspace {서비스명} --project {프로젝트키}
```

### 방법 2: Watch 모드 (자동 감지)

```bash
python3 cli.py watch
```

`watch.dirs`에 등록된 경로를 감시하다가, `completed/`에 기획서가 감지되면 자동 실행합니다.

기획서를 `completed/`로 이동하면 파이프라인이 시작됩니다:

```bash
mv workspaces/{서비스명}/planning/in-progress/{기능명} \
   workspaces/{서비스명}/planning/completed/{기능명}
```

### TUI 대시보드와 함께 실행

```bash
python3 cli.py run -s {spec경로} -v
```

`-v` 플래그를 붙이면 Textual 기반 TUI 대시보드가 활성화됩니다. 병렬 에이전트의 질문, 권한 요청, 체크포인트를 대화형으로 처리할 수 있습니다.

---

## 체크포인트 승인

Phase 1(Architect) 완료 후, `approaches.json`이 생성되고 사용자 승인을 기다립니다. `config.yaml`의 `pipeline.checkpoint_phase1: true`일 때 활성화됩니다.

### 전체 승인

```bash
python3 cli.py approve {task-id}
```

### 개별 approach 승인/반려 (N≥2)

```bash
# 특정 approach만 승인 (나머지는 반려)
python3 cli.py approve {task-id} --approaches 1,2

# 특정 approach 반려 (나머지는 승인)
python3 cli.py approve {task-id} --reject 3
```

### 현재 대기 중인 질문 확인

```bash
python3 cli.py questions {task-id}
python3 cli.py answer {task-id} {question-id} "응답 내용"
```

---

## 결과 확인 및 머지

파이프라인 완료 후 `evaluation-result.md`에 비교 결과와 추천 구현이 기록됩니다.

```bash
cat workspaces/{서비스명}/work/{task-id}/evaluation-result.md
```

원하는 구현 브랜치를 수동으로 머지합니다:

```bash
cd workspaces/{서비스명}/{서비스명}-BE
git merge {task-id}/impl-1   # 또는 impl-2, integrated 등
```

---

## CLI 명령어 레퍼런스

| 명령어 | 설명 |
|--------|------|
| `python3 cli.py init` | config.yaml 초기 템플릿 생성 |
| `python3 cli.py run -s {spec}` | 기획서로 파이프라인 직접 실행 |
| `python3 cli.py run -s {spec} -v` | TUI 대시보드와 함께 실행 |
| `python3 cli.py watch` | Watch 모드 시작 |
| `python3 cli.py approve {task-id}` | Phase 1 체크포인트 전체 승인 |
| `python3 cli.py approve {task-id} --approaches 1,2` | 개별 approach 승인 |
| `python3 cli.py approve {task-id} --reject 3` | 개별 approach 반려 |
| `python3 cli.py status` | 전체 태스크 상태 확인 |
| `python3 cli.py status {task-id}` | 특정 태스크 상태 확인 |
| `python3 cli.py abort {task-id}` | 실행 중인 태스크 중단 |
| `python3 cli.py questions {task-id}` | 대기 중인 질문 목록 확인 |
| `python3 cli.py answer {task-id} {q-id} {응답}` | 질문에 답변 |

> `pip3 install -e .` 설치 후에는 `python3 cli.py` 대신 `multi-agent-dev` 명령을 사용할 수 있습니다.

---

## 파이프라인 모드

기획서의 `**파이프라인 모드:**` 항목으로 지정합니다.

### Alternative 모드 (기본값)

각 approach가 독립적인 대안. Comparator가 비교·순위·추천합니다.

```
Phase 2: N개 독립 구현 → Phase 3: N개 리뷰/테스트 → Phase 4: Comparator → evaluation-result.md
```

N=1인 경우 Phase 4를 건너뛰고 바로 평가 결과를 저장합니다.

### Concern 모드

각 approach가 보완적 관심사 (예: FE/BE, 인증/비즈니스로직). Integrator가 모두 통합합니다.

```
Phase 2: N개 관심사별 구현 → Phase 3: N개 리뷰/테스트 → Phase 4: Integrator → integrated/ 브랜치
```

기획서에서 지정:

```markdown
**파이프라인 모드: concern**
```

---

## 도구 권한 시스템

`config.yaml`의 `permissions` 섹션으로 Claude가 사용하는 도구의 권한을 세밀하게 제어합니다.

### 규칙 형식

```yaml
permissions:
  allow:
    - "Read(*)"              # Read 도구 전체 허용
    - "Bash(npm run *)"      # npm run으로 시작하는 명령만 허용
  deny:
    - "Bash(rm -rf *)"       # rm -rf 명령 차단
    - "Bash(sudo *)"         # sudo 명령 차단
  ask:
    - "Bash(*)"              # Bash 전체는 사용자 승인 필요
    - "Write(src/**)"        # src 하위 파일 쓰기는 승인 필요
  ask_timeout: 300           # 승인 대기 시간 (초), 초과 시 deny
```

### 평가 순서

`deny` → `allow` → `ask` → 기본값(`ask`) 순서로 평가합니다. 더 구체적인 deny 규칙이 더 넓은 allow 규칙보다 우선합니다.

### 도구별 매칭 인자

| 도구 | 매칭 대상 |
|------|-----------|
| `Bash` | `command` 필드 전체 |
| `Write`, `Edit`, `Read` | `file_path` 필드 |
| `Glob`, `Grep` | `pattern` 필드 |

---

## 질문 큐 & TUI 대시보드

병렬로 실행되는 N개의 에이전트가 각각 권한 요청, 체크포인트, 오류 알림을 발생시킬 수 있습니다. 이를 단일 큐로 통합하여 순차 처리합니다.

### 질문 유형

| 유형 | 설명 |
|------|------|
| `permission` | Claude가 특정 도구 사용 승인 요청 |
| `checkpoint` | Phase 전환 시 사용자 확인 필요 |
| `error` | 에이전트 실행 중 오류 발생 |
| `decision` | 분기점에서 방향 선택 필요 |

### TUI 대시보드

`-v` 플래그로 실행 시 Textual 기반 대화형 터미널 UI가 활성화됩니다.

- 실시간 질문 큐 목록 표시
- 질문 선택 후 답변 입력
- 각 에이전트의 실행 상태 모니터링
- 키보드만으로 모든 승인/답변 처리

### CLI로 질문 처리

TUI 없이 CLI로 처리하는 경우:

```bash
# 대기 중인 질문 목록
python3 cli.py questions {task-id}

# 질문에 답변
python3 cli.py answer {task-id} {question-id} "allow"
python3 cli.py answer {task-id} {question-id} "deny"
```

---

## 에이전트 상세

| 에이전트 | Phase | 역할 | 입력 | 출력 |
|----------|-------|------|------|------|
| **Architect** | 1 | 기획서 + 프로젝트 컨텍스트 분석 → N개 구현 설계 | planning-spec.md, project-context.md | `architect/approaches.json` |
| **Implementer × N** | 2 | 각 접근법을 독립 git worktree에서 구현 + 커밋 | approaches.json[i] | 코드 커밋 + `.multi-agent/summary.json` |
| **Reviewer × N** | 3 | 5가지 관점 코드 리뷰 (품질/설계/보안/성능/테스트용이성) | impl-N/ worktree | `review-N/review.md` |
| **Tester × N** | 3 | 테스트 작성·실행·결과 분석 | impl-N/ worktree | `test-N/test-results.json` |
| **Comparator** | 4 | N개 구현 비교·순위·추천 (alternative 모드, N≥2) | 리뷰 + 테스트 결과 전체 | `comparator/comparison.md` |
| **Integrator** | 4 | N개 구현 통합·충돌 해결·글루 코드 (concern 모드) | impl 브랜치 전체 | `integrated/` worktree |
| **Simplifier** | 후처리 | 선택된 구현의 코드 정리·최적화 | 선택된 impl worktree | 정리된 코드 |

### git worktree 격리 구조

```
.cache/{repo-name}/          ← bare clone 또는 로컬 init
    └── .git/

work/task-{id}/implementations/
    ├── impl-1/              ← worktree (브랜치: task-{id}/impl-1)
    └── impl-2/              ← worktree (브랜치: task-{id}/impl-2)
```

각 Implementer는 서로 다른 브랜치에서 작업하므로 파일 충돌이 없습니다. 작업 완료 후 변경 사항이 해당 브랜치에 커밋됩니다.

### 태스크 상태 추적

| 파일 | 내용 |
|------|------|
| `manifest.json` | 태스크 메타데이터 (현재 단계, N값, Phase 이력, 파이프라인 모드) |
| `timeline.log` | Phase 전환 타임라인 |
| `project-profile.json` | 프로젝트 정적 분석 결과 (commit SHA 기반 캐싱) |
| `project-context.md` | 에이전트에게 전달되는 프로젝트 컨텍스트 |

---

## 프로젝트 구조

```
multi-agent-dev-system/
├── cli.py                          # CLI 진입점
├── config.yaml                     # 설정 파일
├── requirements.txt
│
├── orchestrator/                   # 시스템 코어
│   ├── main.py                     #   Orchestrator (파이프라인 전체 관리)
│   ├── executor.py                 #   ClaudeExecutor (Claude Code CLI 실행)
│   ├── permission_handler.py       #   도구 권한 평가 및 승인 흐름
│   ├── stream_processor.py         #   NDJSON 스트림 파싱
│   ├── watcher.py                  #   파일 감시 (completed/ 폴더)
│   ├── agents/
│   │   ├── base.py                 #   BaseAgent
│   │   ├── architect.py            #   Phase 1
│   │   ├── implementer.py          #   Phase 2
│   │   ├── reviewer.py             #   Phase 3
│   │   ├── tester.py               #   Phase 3
│   │   ├── comparator.py           #   Phase 4 (alternative)
│   │   ├── integrator.py           #   Phase 4 (concern)
│   │   └── simplifier.py           #   후처리
│   ├── queue/
│   │   ├── models.py               #   Question, Answer, QuestionType
│   │   └── question_queue.py       #   QuestionQueue (thread-safe, file-backed)
│   ├── tui/
│   │   ├── app.py                  #   DashboardApp (Textual)
│   │   └── widgets.py              #   커스텀 위젯
│   └── utils/
│       ├── git_manager.py          #   clone/worktree/신규 프로젝트 초기화
│       ├── project_analyzer.py     #   프로젝트 정적 분석
│       ├── spec_parser.py          #   기획서 파싱
│       ├── spec_validator.py       #   기획서 검증
│       ├── context_builder.py      #   에이전트 컨텍스트 구성
│       ├── notifier.py             #   시스템 알림
│       ├── logger.py               #   TaskLogger
│       └── atomic_write.py         #   원자적 파일 쓰기
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
    └── {서비스명}/
        ├── {서비스명}-BE/
        ├── {서비스명}-FE/          # 필요한 경우
        ├── .cache/
        ├── planning/
        │   ├── in-progress/
        │   └── completed/
        └── work/
            └── task-{timestamp}/
```

---

## 상세 문서

- [.claude/docs/system-overview.md](.claude/docs/system-overview.md) — 파이프라인 전체 흐름 및 Phase 상세
- [.claude/docs/agents.md](.claude/docs/agents.md) — 에이전트 설계 및 인터페이스
- [.claude/docs/orchestrator.md](.claude/docs/orchestrator.md) — Orchestrator 설계 및 config.yaml 전체 스키마
- [.claude/docs/workspace-structure.md](.claude/docs/workspace-structure.md) — 워크스페이스 디렉토리 구조
- [.claude/docs/planning-guide.md](.claude/docs/planning-guide.md) — 기획서 작성 가이드
- [USAGE.md](USAGE.md) — CLI 레퍼런스 및 실전 시나리오

---

**v2.06** | MIT License
