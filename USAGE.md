# Multi-Agent Development System 사용 가이드

## 목차

1. [개요](#1-개요)
2. [설치 및 초기화](#2-설치-및-초기화)
3. [설정 (config.yaml)](#3-설정-configyaml)
4. [기획서 작성법](#4-기획서-작성법)
5. [파이프라인 실행](#5-파이프라인-실행)
6. [CLI 명령어 레퍼런스](#6-cli-명령어-레퍼런스)
7. [파이프라인 흐름 상세](#7-파이프라인-흐름-상세)
8. [프로젝트 구조](#8-프로젝트-구조)
9. [실전 시나리오](#9-실전-시나리오)
10. [트러블슈팅](#10-트러블슈팅)

---

## 1. 개요

이 시스템은 **하나의 기획서**로부터 **N개의 구현**을 AI 에이전트가 자동으로 생성하고, 리뷰/테스트/비교를 거쳐 **최적의 구현을 선택**하는 파이프라인입니다.

```
기획서 작성 (사람 + Claude Code)
    |
    v
[Validation] 기획서 검증 (규칙 기반, AI 비용 없음)
    |
    v
[Git Setup] 타겟 프로젝트 clone/fetch + 최신 상태 동기화
    |
    v
[Project Analysis] 프로젝트 사전 분석 (Python 기반, AI 비용 없음)
    |               → 프로젝트 구조, 기술 스택, 핵심 모듈 분석
    |               → .project-profile.json 캐싱 (commit SHA 기반)
    |               → 기획서 관련 모듈만 컨텍스트 생성
    |               → project-context.md 파일로 저장 (에이전트가 Read로 참조)
    v
[Phase 1] Architect: 기획서 + 프로젝트 컨텍스트 파일 참조 → N개 구현 설계
    |
    v
[Checkpoint] 사용자 검토 + 승인/수정/중단
    |
    v
[Phase 2] Implementer x N: 각 설계를 독립 git worktree에서 구현 (병렬)
    |                        + 프로젝트 컨텍스트 파일 참조 (토큰 절감)
    v
[Phase 3] Reviewer + Tester x N: 각 구현을 리뷰/테스트 (병렬)
    |       → enable_review / enable_test로 개별 ON/OFF 가능
    v                              (N=1이면 건너뜀)
[Phase 4] Comparator: N개 구현 비교 + 순위 매기기
    |
    v
[완료] evaluation-result.md 생성 → 사용자가 수동으로 브랜치 머지
```

### 핵심 특징

- **N=1**: 단일 구현. Phase 4를 건너뛰고 바로 평가 결과 저장
- **N>=2**: 병렬 구현 + 비교 평가. Phase 4까지 실행 후 평가 결과 저장
- **git worktree 격리**: 각 구현이 독립 브랜치에서 실행되어 서로 간섭 없음
- **체크포인트**: Phase 1 후 사용자 검토 기회 제공. 개별 approach 승인/반려 가능
- **Phase 3 개별 제어**: `enable_review`, `enable_test`로 리뷰와 테스트를 각각 ON/OFF
- **토큰 최적화**: 프로젝트 컨텍스트를 파일로 저장하고 에이전트가 Read 도구로 참조 (프롬프트 크기 절감)
- **시스템 알림**: macOS/Linux/Windows 네이티브 알림 지원

---

## 2. 설치 및 초기화

### 사전 요구사항

- **Python 3.8+** (`python3 --version`으로 확인)
- **git** (`git --version`으로 확인)
- **Claude Code CLI** (시스템 PATH에 `claude` 명령이 있어야 함)

### 방법 1: pip install (권장)

```bash
cd /path/to/multi-agent-dev-system

# 개발 모드 (코드 수정 시 재설치 불필요)
pip3 install -e .
```

설치 후 어디서든 `multi-agent-dev` 명령으로 실행할 수 있습니다:
```bash
multi-agent-dev init
multi-agent-dev run -s planning-spec.md
multi-agent-dev watch
```

> **참고**: 이 문서의 예제는 `python3 cli.py` 방식을 기준으로 작성되었습니다. `pip install` 후에는 `python3 cli.py`를 `multi-agent-dev`로 바꾸면 됩니다.

### 방법 2: 직접 실행 (설치 없이)

```bash
cd /path/to/multi-agent-dev-system
pip3 install -r requirements.txt
```

이후 프로젝트 디렉토리에서 `python3 cli.py`로 실행합니다.

### 초기화

```bash
python3 cli.py init
```

`config.yaml` 파일이 생성됩니다. **반드시 `project.target_repo`를 설정해야 합니다.**

---

## 3. 설정 (config.yaml)

```yaml
workspace:
  root: ./workspace                # 워크스페이스 루트 디렉토리

project:
  target_repo: ""                  # [필수] 타겟 프로젝트 GitHub URL
  default_branch: "main"           # 기본 브랜치 이름
  github_token: ""                 # GitHub Personal Access Token (private repo용)

prompts:
  directory: ./prompts             # 에이전트 프롬프트 파일 디렉토리

execution:
  timeout: 600                     # Claude 실행 타임아웃 (초)
  max_retries: 3                   # 실패 시 재시도 횟수

pipeline:
  checkpoint_phase1: true          # Phase 1 후 체크포인트 활성화
  num_approaches: 1                # 기본 구현 개수 (기획서에서 N 지정 시 덮어씀)
  enable_review: true              # Phase 3: Review 활성화
  enable_test: true                # Phase 3: Test 활성화

watch:
  dirs:                            # 감시할 디렉토리 목록 (완전한 경로)
    - ./workspace/planning/completed
    # - /other/project/planning/completed  # 여러 경로 추가 가능

validation:
  enabled: true                    # 기획서 유효성 검증 활성화
  auto_revalidate: true            # watch 모드에서 기획서 수정 시 자동 재검증/재실행
  strict_mode: false               # true면 검증 경고도 오류로 처리

notifications:
  enabled: true                    # 시스템 알림 활성화
  sound: true                      # 알림 사운드 활성화
```

> **주의**: `config.yaml`에는 GitHub 토큰 등 민감 정보가 포함될 수 있어 `.gitignore`에 등록되어 있습니다.

### 설정 항목 설명

| 항목 | 설명 | 기본값 |
|------|------|--------|
| `project.target_repo` | 구현 대상 프로젝트의 Git URL | (필수 설정) |
| `project.github_token` | GitHub PAT. private repo 접근 시 필수 | (빈 문자열) |
| `pipeline.num_approaches` | 기획서에서 N을 명시하지 않았을 때 사용하는 기본 구현 개수 | 1 |
| `pipeline.checkpoint_phase1` | `false`로 설정하면 Phase 1 후 승인 없이 바로 Phase 2로 진행 | true |
| `pipeline.enable_review` | `false`로 설정하면 Phase 3에서 리뷰를 건너뜀 | true |
| `pipeline.enable_test` | `false`로 설정하면 Phase 3에서 테스트를 건너뜀 | true |
| `watch.dirs` | 감시 모드에서 모니터링할 디렉토리 경로 목록 | `[./workspace/planning/completed]` |
| `validation.strict_mode` | `true`면 경고도 검증 실패로 처리 | false |
| `validation.auto_revalidate` | watch 모드에서 기존 기획서 수정 시 자동 재실행 | true |

### GitHub 토큰 설정 방법

private 저장소를 사용하려면 GitHub Personal Access Token이 필요합니다.

1. GitHub > Settings > Developer settings > Personal access tokens > Tokens (classic)
2. **Generate new token** 클릭
3. 권한: `repo` (Full control of private repositories) 선택
4. 생성된 토큰을 `config.yaml`에 입력

---

## 4. 기획서 작성법

기획서는 `planning-spec.md` 파일로, 마크다운 형식으로 작성합니다.

### 필수 조건

1. **최소 50자** 이상
2. **`## 구현 방법`** 섹션이 반드시 존재해야 함
3. 기술 스택을 명시하는 것을 권장

### 기본 형식

```markdown
# 기획서: 사용자 인증 시스템

## 요구사항
- 로그인/로그아웃 기능
- 비밀번호 암호화

## 구현 방법

기술 스택: FastAPI, JWT, bcrypt

### 방법 1: JWT 토큰 기반
- **핵심 아이디어**: Stateless 인증
- **예상 장점**: 확장성이 좋음
- **예상 단점**: 토큰 무효화가 복잡
- **기술 스택 제안**: FastAPI, PyJWT

### 방법 2: 세션 기반
- **핵심 아이디어**: 서버 사이드 세션
- **예상 장점**: 구현이 간단
- **예상 단점**: 서버 메모리 사용
- **기술 스택 제안**: FastAPI, Redis
```

### N(구현 개수) 지정 방법

기획서에서 다음 패턴으로 N을 지정할 수 있습니다:

| 패턴 | 의미 |
|------|------|
| `## 구현 방법 (2개 비교)` | 정확히 2개 구현 |
| `탐색할 방법 개수: 3개` | 정확히 3개 구현 |
| `탐색할 방법 개수: 자동` | 기획서에 정의된 방법 개수 사용 |
| (미지정) | `### 방법 N` 섹션 개수 사용, 없으면 config의 `num_approaches` 사용 |

### 검증 규칙

기획서는 실행 전 자동으로 검증됩니다:

**오류 (실행 차단)**:
- 파일이 존재하지 않음
- 내용이 50자 미만
- `## 구현 방법` 섹션 없음
- 헤딩의 N과 실제 `### 방법` 개수 불일치
- 방법명 중복

**경고 (실행은 진행, `strict_mode: true`이면 차단)**:
- H1 제목 없음
- 기술 스택 미명시

---

## 5. 파이프라인 실행

### 기본 실행

```bash
python3 cli.py run -s planning-spec.md
```

### 상세 로깅

```bash
python3 cli.py run -s planning-spec.md -v
```

### 커스텀 설정 파일

```bash
python3 cli.py run -s planning-spec.md -c my-config.yaml
```

### 실행 후 흐름

1. 기획서 검증 → 파싱 → Git clone/fetch
2. **프로젝트 분석**: 타겟 프로젝트 구조 자동 분석 (~1-2초)
   - `.project-profile.json` 캐시 확인 (있으면 재사용)
   - 기획서 키워드와 관련된 모듈만 컨텍스트 생성
   - `project-context.md` 파일로 저장 (에이전트가 Read 도구로 참조)
3. Phase 1 (Architect) 실행
4. **체크포인트**: 터미널에 "승인 대기 중" 메시지 출력
5. 다른 터미널에서 `approve` 명령 실행
6. Phase 2~4 자동 진행
7. `evaluation-result.md` 생성, 사용자가 원하는 브랜치를 수동 머지

---

## 6. CLI 명령어 레퍼런스

### `init` — 설정 파일 생성

```bash
python3 cli.py init [-o config.yaml]
```

기본 `config.yaml`을 생성합니다. 이미 존재하면 덮어쓸지 확인합니다.

---

### `run` — 파이프라인 실행

```bash
python3 cli.py run -s <기획서경로> [-c config.yaml] [-v]
```

| 옵션 | 설명 |
|------|------|
| `-s, --spec` | 기획서(planning-spec.md) 경로 (필수) |
| `-c, --config` | 설정 파일 경로 (기본: config.yaml) |
| `-v, --verbose` | 상세 로깅 (DEBUG 레벨) |

---

### `approve` — 체크포인트 승인

**새로운 터미널에서 실행** (파이프라인 실행 터미널은 대기 중)

```bash
# 전체 승인
python3 cli.py approve <task-id>

# 특정 approach만 승인 (N>=2)
python3 cli.py approve <task-id> --approaches 1,2

# 특정 approach 반려 (N>=2)
python3 cli.py approve <task-id> --reject 3
```

| 옵션 | 설명 |
|------|------|
| `--approaches` | 승인할 approach ID 목록 (쉼표 구분) |
| `--reject` | 반려할 approach ID 목록 (쉼표 구분) |

---

### `select` — 구현 선택 (N>=2)

```bash
python3 cli.py select <task-id> <impl-id>
```

파이프라인 완료 후, 사용자가 최종 구현을 선택하는 명령입니다.

---

### `revise` — 수정 요청

```bash
# 피드백과 함께
python3 cli.py revise <task-id> --feedback "API 설계를 변경해주세요"

# 대화형 입력
python3 cli.py revise <task-id>
```

Phase 1 체크포인트에서 Architect의 설계에 수정이 필요할 때 사용합니다.

---

### `abort` — 태스크 중단

```bash
python3 cli.py abort <task-id>
```

---

### `status` — 상태 확인

```bash
# 전체 태스크 목록
python3 cli.py status

# 특정 태스크 상세
python3 cli.py status <task-id>
```

---

### `watch` — 감시 모드

```bash
python3 cli.py watch [-c config.yaml]
```

`config.yaml`의 `watch.dirs`에 지정된 디렉토리들을 5초 간격으로 감시합니다.

**다중 경로 지원**:
- `watch.dirs`에 여러 경로를 지정할 수 있습니다
- 경로가 2개 이상이면 시작 시 **화살표 키 기반 대화형 UI**로 감시할 디렉토리를 선택합니다
- 경로가 1개면 선택 없이 바로 감시를 시작합니다

**대화형 선택 UI** (경로 2개 이상):
```
  감시할 디렉토리를 선택하세요
  (위/아래: 이동, Space: 선택/해제, Enter: 확정)

  > [*] /Users/.../workspace/planning/completed
    [ ] /Users/.../other-project/planning/completed (자동 생성)

  1개 선택됨
```

**watch.dirs 미설정 시**:
- config에 `watch.dirs`가 없으면 안내 메시지를 출력합니다
- `workspace.root`가 설정되어 있으면 기본 경로(`{root}/planning/completed`)를 제안합니다
- 사용자가 Y를 입력하면 해당 경로로 감시를 시작합니다

**동작**:
- 새 `planning-spec.md` 파일이 감지되면 자동으로 파이프라인 실행
- `auto_revalidate: true`이면 기존 기획서가 수정될 때도 재실행
- 순차 처리: 현재 작업이 끝나야 다음 기획서를 처리
- `Ctrl+C`로 종료

---

## 7. 파이프라인 흐름 상세

### N=1 (단일 구현)

```
기획서 검증 → 파싱 → Git clone/fetch → 프로젝트 분석
    → Phase 1: Architect (구현 설계, 프로젝트 컨텍스트 파일 참조)
    → [Checkpoint: 승인 대기]
    → Phase 2: Implementer 1개 (프로젝트 컨텍스트 파일 참조)
    → Phase 3: Reviewer + Tester (enable_review / enable_test로 개별 ON/OFF)
    → evaluation-result.md 생성
```

- Phase 4 (Comparator) **건너뜀**
- 유일한 성공 구현이 자동으로 선택됨

### N>=2 (복수 구현)

```
기획서 검증 → 파싱 → Git clone/fetch → 프로젝트 분석
    → Phase 1: Architect (N개 구현 설계, 프로젝트 컨텍스트 파일 참조)
    → [Checkpoint: 승인/개별승인/수정/중단 대기]
    → Phase 2: Implementer N개 (ThreadPoolExecutor 병렬, 프로젝트 컨텍스트 파일 참조)
    → Phase 3: Reviewer + Tester N세트 (ThreadPoolExecutor 병렬, 개별 ON/OFF)
    → Phase 4: Comparator (N개 비교, 순위 매기기)
    → evaluation-result.md 생성
```

### 프로젝트 사전 분석 (Project Analysis)

Git clone 후, Phase 1 전에 자동으로 실행됩니다:

**동작 방식**:
1. **프로젝트 타입 감지**: Gradle, Maven, npm, Python 등
2. **모듈 구조 분석**: 각 모듈의 소스 루트, 주요 클래스 스캔
3. **아키텍처 패턴 감지**: 헥사고날, 레이어드 등
4. **프로필 캐싱**: `.project-profile.json` 파일로 커밋 SHA 기반 캐싱
5. **타겟 컨텍스트 생성**: 기획서 키워드와 매칭되는 모듈만 컨텍스트 추출
6. **파일로 저장**: `project-context.md`로 저장 → 에이전트가 Read 도구로 참조 (프롬프트에 직접 삽입하지 않음)

**토큰 최적화**:
- 기존: 프로젝트 컨텍스트(~14,000자)를 Architect/Implementer 프롬프트에 직접 삽입
- 현재: 파일 경로만 프롬프트에 포함, 에이전트가 필요 시 Read로 참조
- N=2일 때 약 ~10,500 토큰 절감

### 각 Phase에서 생성되는 파일

```
workspace/tasks/task-YYYYMMDD-HHMMSS/
├── planning-spec.md         # 기획서 복사본
├── manifest.json            # 태스크 메타데이터 + 단계별 상태
├── timeline.log             # 이벤트 타임라인 로그
├── full-conversation.txt    # 전체 대화 내역 (모든 Phase 통합, 시간순)
├── project-profile.json     # 프로젝트 분석 결과 (디버깅용 복사본)
├── project-context.md       # 프로젝트 컨텍스트 (에이전트 참조)
├── checkpoint-decision.json # Phase 1 체크포인트 결정 (임시)
├── evaluation-result.md     # 최종 평가 결과
│
├── architect/               # Phase 1 출력
│   ├── approaches.json
│   └── conversation.txt
│
├── implementations/
│   ├── impl-1/              # Phase 2: git worktree (독립 브랜치)
│   │   └── conversation.txt
│   └── impl-2/
│       └── conversation.txt
│
├── review-1/                # Phase 3: impl-1 리뷰 결과
│   └── conversation.txt
├── test-1/                  # Phase 3: impl-1 테스트 결과
│   └── conversation.txt
│
└── comparator/              # Phase 4 출력 (N>=2)
    ├── comparison.md
    ├── rankings.json
    └── conversation.txt
```

### Git worktree 구조

각 구현은 독립된 git worktree에서 실행됩니다:

```
workspace/.cache/
└── <project-name>/          # 타겟 프로젝트 clone (공유)
    └── .git/

workspace/tasks/task-XXX/implementations/
├── impl-1/                  # worktree → branch: task-XXX/impl-1
├── impl-2/                  # worktree → branch: task-XXX/impl-2
└── impl-3/                  # worktree → branch: task-XXX/impl-3
```

---

## 8. 프로젝트 구조

```
multi-agent-dev-system/
├── cli.py                         # CLI 진입점
├── config.yaml                    # 설정 파일
├── requirements.txt               # Python 의존성
├── setup.py                       # 패키지 설정
│
├── orchestrator/                  # 핵심 오케스트레이터
│   ├── main.py                    #   Orchestrator 클래스 (파이프라인 전체 관리)
│   ├── executor.py                #   ClaudeExecutor (Claude Code 실행기)
│   ├── watcher.py                 #   FileWaitHelper (파일 대기 헬퍼)
│   ├── agents/                    #   AI 에이전트들
│   │   ├── base.py                #     BaseAgent (공통 기반)
│   │   ├── architect.py           #     Phase 1: 구현 설계
│   │   ├── implementer.py         #     Phase 2: 코드 구현
│   │   ├── reviewer.py            #     Phase 3: 코드 리뷰
│   │   ├── tester.py              #     Phase 3: 테스트 실행
│   │   └── comparator.py          #     Phase 4: 구현 비교
│   └── utils/                     #   유틸리티
│       ├── atomic_write.py        #     원자적 파일 쓰기
│       ├── git_manager.py         #     Git clone/worktree 관리
│       ├── project_analyzer.py    #     프로젝트 사전 분석 (Python 기반)
│       ├── logger.py              #     로깅 설정
│       ├── notifier.py            #     시스템 알림 (macOS/Linux/Windows)
│       ├── spec_parser.py         #     기획서 파싱 (마크다운 → 구조체)
│       └── spec_validator.py      #     기획서 검증 (규칙 기반)
│
├── prompts/                       # 에이전트 프롬프트 템플릿
│   ├── architect.md
│   ├── implementer.md
│   ├── reviewer.md
│   ├── tester.md
│   └── comparator.md
│
└── workspace/                     # 런타임 워크스페이스
    ├── templates/
    │   └── planning-template.md   #   기획서 작성 템플릿
    ├── tasks/                     #   실행 중/완료된 태스크
    └── .cache/                    #   Git clone 캐시
```

---

## 9. 실전 시나리오

### 시나리오 A: 간단한 기능 추가 (N=1)

```bash
# 1. config.yaml에 target_repo 설정 후
python3 cli.py run -s my-spec.md
# → Phase 1 완료, 체크포인트 대기

# 2. 새로운 터미널에서 승인
python3 cli.py approve task-20250211-153000

# 3. Phase 2~3 자동 진행 후 평가 결과 저장
cat workspace/tasks/task-20250211-153000/evaluation-result.md

# 4. 원하면 타겟 프로젝트에 수동 머지
cd <타겟-프로젝트>
git merge task-20250211-153000/impl-1
```

### 시나리오 B: 2개 방법 비교 (N=2)

```bash
# 1. 기획서에 "### 방법 1", "### 방법 2" 작성 후 실행
python3 cli.py run -s auth-spec.md

# 2. Phase 1 후 체크포인트 — 새 터미널에서 승인
python3 cli.py approve task-20250211-160000

# 3. Phase 2(병렬 구현) → Phase 3(병렬 리뷰+테스트) → Phase 4(비교) → 완료

# 4. 평가 결과 확인
cat workspace/tasks/task-20250211-160000/evaluation-result.md
cat workspace/tasks/task-20250211-160000/comparator/comparison.md

# 5. 원하는 브랜치 머지
cd <타겟-프로젝트>
git merge task-20250211-160000/impl-2
```

### 시나리오 C: 리뷰/테스트 없이 빠르게 실행

```yaml
# config.yaml
pipeline:
  enable_review: false
  enable_test: false
```

```bash
python3 cli.py run -s quick-spec.md
# → Phase 1 → Checkpoint → Phase 2 → 완료 (Phase 3 건너뜀)
```

### 시나리오 D: watch 모드로 자동 실행 (다중 경로)

```yaml
# config.yaml
watch:
  dirs:
    - ./workspace/planning/completed
    - /home/user/another-project/planning/completed
```

```bash
# 1. watch 모드 시작
python3 cli.py watch

# 2. 경로가 2개 이상이면 대화형 UI로 선택
#    감시할 디렉토리를 선택하세요
#    (위/아래: 이동, Space: 선택/해제, Enter: 확정)
#
#    > [*] /Users/.../workspace/planning/completed
#      [ ] /home/user/another-project/planning/completed
#
#    1개 선택됨

# 3. 다른 터미널에서 기획서를 completed 디렉토리에 배치
cp my-spec.md workspace/planning/completed/my-feature/planning-spec.md

# 4. 5초 내 자동 감지 → 파이프라인 실행
```

---

## 10. 트러블슈팅

### "기획서 검증 실패"

**해결**:
1. `validation-errors.md` 확인
2. 주요 오류:
   - "구현 방법 섹션이 없습니다" → `## 구현 방법` 헤딩 추가
   - "기획서 내용이 너무 짧습니다" → 50자 이상으로 작성
   - "구현 방법 개수 불일치" → 헤딩의 N과 `### 방법` 개수를 맞춤

### "target_repo가 설정되지 않았습니다"

**해결**: `config.yaml`의 `project.target_repo`에 Git URL 설정

### Git clone 시 인증 실패

**해결**: `config.yaml`에 GitHub 토큰 설정. `repo` 권한이 있는지 확인

### "Claude Code CLI not found"

**해결**: `claude --version`으로 CLI가 PATH에 있는지 확인

### 체크포인트에서 무한 대기

**해결**: 새로운 터미널을 열어서 명령 실행
```bash
python3 cli.py approve <task-id>
# 또는
python3 cli.py abort <task-id>
```

### watch 모드에서 "config에 watch.dirs가 설정되지 않았습니다"

**해결**: config.yaml에 `watch.dirs` 섹션을 추가하세요
```yaml
watch:
  dirs:
    - ./workspace/planning/completed
```
또는 프롬프트에서 기본 경로 사용 여부를 묻는 메시지가 표시되면 Y를 입력하세요.

### 프로젝트 분석이 느리거나 실패

**해결**:
1. 캐시 파일 삭제 후 재실행: `rm workspace/.cache/<project-name>/.project-profile.json`
2. 지원 프로젝트 타입: Gradle, Maven, npm, Python

### Architect/Implementer가 프로젝트 탐색 시간이 긴 경우

**해결**:
1. 기획서에 구체적인 모듈명/패키지명 명시 (예: "module-admin의 로그인 기능")
2. 타겟 컨텍스트 크기 확인 (로그에 "컨텍스트 N자" 출력)
   - 30,000자 이하: 적정
   - 50,000자 이상: 기획서를 더 구체적으로 수정

---

## 부록: 자주 사용하는 명령 모음

```bash
# === 초기 설정 ===
python3 cli.py init                              # config.yaml 생성

# === 실행 ===
python3 cli.py run -s spec.md                    # 파이프라인 실행
python3 cli.py run -s spec.md -v                 # 상세 로깅
python3 cli.py watch                             # 감시 모드 (다중 경로 지원)

# === 체크포인트 (Phase 1 후, 새 터미널에서) ===
python3 cli.py approve <task-id>                 # 전체 승인
python3 cli.py approve <task-id> --approaches 1,2  # 개별 승인
python3 cli.py approve <task-id> --reject 3      # 개별 반려
python3 cli.py revise <task-id> -f "피드백"       # 수정 요청
python3 cli.py abort <task-id>                   # 중단

# === 상태 확인 ===
python3 cli.py status                            # 전체 목록
python3 cli.py status <task-id>                  # 상세 상태

# === 결과 확인 (파이프라인 완료 후) ===
cat workspace/tasks/<task-id>/evaluation-result.md
cat workspace/tasks/<task-id>/comparator/comparison.md  # N≥2

# === 수동 머지 ===
cd <타겟-프로젝트>
git merge <task-id>/impl-<N>
```

> `pip3 install -e .` 설치 후에는 `python3 cli.py` 대신 `multi-agent-dev` 명령을 사용할 수 있습니다.
