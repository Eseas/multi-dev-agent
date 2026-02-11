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
[Phase 1] Architect: 기획서 → N개 구현 설계
    |
    v
[Checkpoint] 사용자 검토 + 승인/수정/중단
    |
    v
[Phase 2] Implementer x N: 각 설계를 독립 git worktree에서 구현 (병렬)
    |
    v
[Phase 3] Reviewer + Tester x N: 각 구현을 리뷰/테스트 (병렬)
    |
    v                              (N=1이면 건너뜀)
[Phase 4] Comparator: N개 구현 비교 + 순위 매기기
    |
    v                              (N=1이면 건너뜀)
[Phase 5] Human Selection: 사용자가 최종 구현 선택
    |
    v
[Phase 6] Integration: 선택된 브랜치 정보 알림
```

### 핵심 특징

- **N=1**: 단일 구현. Phase 4/5를 건너뛰고 바로 Phase 6으로 진행
- **N>=2**: 병렬 구현 + 비교 + 선택. 전체 파이프라인 실행
- **git worktree 격리**: 각 구현이 독립 브랜치에서 실행되어 서로 간섭 없음
- **체크포인트**: Phase 1 후 사용자 검토 기회 제공. 개별 approach 승인/반려 가능
- **시스템 알림**: macOS/Linux/Windows 네이티브 알림 지원

---

## 2. 설치 및 초기화

### 사전 요구사항

- Python 3.8+
- git
- [Claude Code CLI](https://claude.ai/claude-code) (시스템 PATH에 `claude` 명령이 있어야 함)

### 설치

```bash
cd /path/to/multi-agent-dev-system
pip install -r requirements.txt
```

`requirements.txt` 내용:
```
pyyaml>=6.0
watchdog>=3.0.0
```

### 초기화

```bash
python cli.py init
```

`config.yaml` 파일이 생성됩니다. 반드시 `project.target_repo`를 설정해야 합니다.

---

## 3. 설정 (config.yaml)

```yaml
workspace:
  root: ./workspace                # 워크스페이스 루트 디렉토리

project:
  target_repo: ""                  # [필수] 타겟 프로젝트 GitHub URL
  default_branch: "main"           # 기본 브랜치 이름

prompts:
  directory: ./prompts             # 에이전트 프롬프트 파일 디렉토리

execution:
  timeout: 300                     # Claude 실행 타임아웃 (초)
  max_retries: 3                   # 실패 시 재시도 횟수

pipeline:
  checkpoint_phase1: true          # Phase 1 후 체크포인트 활성화
  num_approaches: 1                # 기본 구현 개수 (기획서에서 N 지정 시 덮어씀)

validation:
  enabled: true                    # 기획서 유효성 검증 활성화
  auto_revalidate: true            # watch 모드에서 기획서 수정 시 자동 재검증/재실행
  strict_mode: false               # true면 검증 경고도 오류로 처리

notifications:
  enabled: true                    # 시스템 알림 활성화
  sound: true                      # 알림 사운드 활성화
```

### 설정 항목 설명

| 항목 | 설명 | 기본값 |
|------|------|--------|
| `project.target_repo` | 구현 대상 프로젝트의 Git URL. 시스템이 이 저장소를 clone한 후 worktree를 생성 | (빈 문자열, 필수 설정) |
| `pipeline.num_approaches` | 기획서에서 N을 명시하지 않았을 때 사용하는 기본 구현 개수 | 1 |
| `pipeline.checkpoint_phase1` | `false`로 설정하면 Phase 1 후 승인 없이 바로 Phase 2로 진행 | true |
| `validation.strict_mode` | `true`로 설정하면 "기술 스택 미명시" 같은 경고도 검증 실패로 처리 | false |
| `validation.auto_revalidate` | `watch` 모드에서 이미 처리한 기획서가 수정되면 자동으로 재실행 | true |

---

## 4. 기획서 작성법

기획서는 `planning-spec.md` 파일로, 마크다운 형식으로 작성합니다.

### 필수 조건

1. **최소 50자** 이상
2. **`## 구현 방법`** 섹션이 반드시 존재해야 함
3. 기술 스택을 명시하는 것을 권장 (React, Python, FastAPI 등)

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

검증 실패 시 `validation-errors.md` 파일이 task 디렉토리에 생성됩니다.

---

## 5. 파이프라인 실행

### 기본 실행

```bash
python cli.py run -s planning-spec.md
```

### 상세 로깅

```bash
python cli.py run -s planning-spec.md -v
```

### 커스텀 설정 파일

```bash
python cli.py run -s planning-spec.md -c my-config.yaml
```

### 실행 후 흐름

1. 기획서 검증 → 파싱 → Git clone/fetch
2. Phase 1 (Architect) 실행
3. **체크포인트**: 터미널에 "승인 대기 중" 메시지 출력, 시스템 알림 발생
4. 다른 터미널에서 `approve` 명령 실행
5. Phase 2~6 자동 진행
6. 완료 시 통합 브랜치 정보 출력

---

## 6. CLI 명령어 레퍼런스

### `init` — 설정 파일 생성

```bash
python cli.py init [-o config.yaml]
```

기본 `config.yaml`을 생성합니다. 이미 존재하면 덮어쓸지 확인합니다.

---

### `run` — 파이프라인 실행

```bash
python cli.py run -s <기획서경로> [-c config.yaml] [-v]
```

| 옵션 | 설명 |
|------|------|
| `-s, --spec` | 기획서(planning-spec.md) 경로 (필수) |
| `-c, --config` | 설정 파일 경로 (기본: config.yaml) |
| `-v, --verbose` | 상세 로깅 (DEBUG 레벨) |

**출력 예시** (성공):
```
기획서: /path/to/planning-spec.md
============================================================
파이프라인을 시작합니다...

============================================================
[SUCCESS] 파이프라인 완료!
  태스크 ID: task-20250211-153000
  브랜치:    task-20250211-153000/impl-1

통합하려면: git merge task-20250211-153000/impl-1
```

---

### `approve` — 체크포인트 승인

```bash
# 전체 승인
python cli.py approve <task-id>

# 특정 approach만 승인 (N>=2)
python cli.py approve <task-id> --approaches 1,2

# 특정 approach 반려 (N>=2)
python cli.py approve <task-id> --reject 3

# 조합 사용
python cli.py approve <task-id> --approaches 1,2 --reject 3
```

| 옵션 | 설명 |
|------|------|
| `--approaches` | 승인할 approach ID 목록 (쉼표 구분) |
| `--reject` | 반려할 approach ID 목록 (쉼표 구분) |

**동작**:
- 옵션 없이 `approve`하면 모든 approach가 승인됩니다
- `--approaches`를 지정하면 해당 approach만 Phase 2로 진행
- `--reject`로 지정된 approach는 Phase 2에서 제외
- 승인된 approach가 0개면 파이프라인이 중단됩니다

---

### `select` — 구현 선택 (Phase 5, N>=2)

```bash
python cli.py select <task-id> <impl-id>
```

Phase 4(Comparator)가 완료된 후, 사용자가 최종 구현을 선택하는 명령입니다.

**예시**:
```bash
# comparison.md 확인 후
python cli.py select task-20250211-153000 2
# → [SELECTED] task-20250211-153000: impl-2 선택 완료
```

`human-review.json`에 추천 구현 정보가 저장되어 있으니 참고하세요.

---

### `revise` — 수정 요청

```bash
# 피드백과 함께
python cli.py revise <task-id> --feedback "API 설계를 변경해주세요"

# 대화형 입력
python cli.py revise <task-id>
# → 수정 피드백을 입력하세요 (빈 줄로 종료):
```

Phase 1 체크포인트에서 Architect의 설계에 수정이 필요할 때 사용합니다.
파이프라인이 중단되고, 피드백이 결과에 포함됩니다.

---

### `abort` — 태스크 중단

```bash
python cli.py abort <task-id>
```

실행 중인 파이프라인을 즉시 중단합니다.

---

### `status` — 상태 확인

```bash
# 전체 태스크 목록
python cli.py status

# 특정 태스크 상세
python cli.py status <task-id>
```

**상세 출력 예시** (N>=2):
```
태스크: task-20250211-153000
상태:   phase3_review_test
생성:   2025-02-11T15:30:00
갱신:   2025-02-11T15:35:20
기획서: /path/to/planning-spec.md

Phase 상태:
  phase1: completed
  phase2: completed
  phase3: completed
  phase4: completed

구현 목록:
  impl-1: [OK] task-20250211-153000/impl-1
  impl-2: [OK] task-20250211-153000/impl-2
  impl-3: [FAIL] task-20250211-153000/impl-3

Rankings: [2, 1, 3]
비교 보고서: ./workspace/tasks/task-20250211-153000/comparator/comparison.md

추천 구현: impl-2
선택하려면: multi-agent-dev select task-20250211-153000 <impl-id>
```

---

### `watch` — 감시 모드

```bash
python cli.py watch [-c config.yaml]
```

`workspace/planning/completed/` 디렉토리를 5초 간격으로 감시합니다.

- 새 `planning-spec.md` 파일이 감지되면 자동으로 파이프라인 실행
- `auto_revalidate: true`이면 기존 기획서가 수정될 때도 재실행
- `Ctrl+C`로 종료

---

## 7. 파이프라인 흐름 상세

### N=1 (단일 구현)

```
기획서 검증 → 파싱 → Git clone
    → Phase 1: Architect (구현 설계)
    → [Checkpoint: 승인 대기]
    → Phase 2: Implementer 1개 (순차 실행)
    → Phase 3: Reviewer + Tester 1세트 (순차 실행)
    → Phase 6: 통합 알림 (브랜치 정보)
```

- Phase 4 (Comparator), Phase 5 (Selection) **건너뜀**
- 유일한 성공 구현이 자동으로 선택됨

### N>=2 (복수 구현)

```
기획서 검증 → 파싱 → Git clone
    → Phase 1: Architect (N개 구현 설계)
    → [Checkpoint: 승인/개별승인/수정/중단 대기]
    → Phase 2: Implementer N개 (ThreadPoolExecutor 병렬)
    → Phase 3: Reviewer + Tester N세트 (ThreadPoolExecutor 병렬)
    → Phase 4: Comparator (N개 비교, 순위 매기기)
    → Phase 5: Human Selection (사용자가 select 명령으로 선택)
    → Phase 6: 통합 알림 (선택된 브랜치 정보)
```

### 각 Phase에서 생성되는 파일

```
workspace/tasks/task-YYYYMMDD-HHMMSS/
├── planning-spec.md         # 기획서 복사본
├── manifest.json            # 태스크 메타데이터 + 단계별 상태
├── timeline.log             # 이벤트 타임라인 로그
├── checkpoint-decision.json # Phase 1 체크포인트 결정 (임시, 처리 후 삭제)
├── validation-errors.md     # 검증 실패 시 오류 보고서
│
├── architect/               # Phase 1 출력
│   └── (Architect 결과물)
│
├── implementations/
│   ├── impl-1/              # Phase 2: git worktree (독립 브랜치)
│   ├── impl-2/              # Phase 2: git worktree (독립 브랜치)
│   └── impl-3/              # Phase 2: git worktree (독립 브랜치)
│
├── review-1/                # Phase 3: impl-1 리뷰 결과
├── review-2/                # Phase 3: impl-2 리뷰 결과
├── test-1/                  # Phase 3: impl-1 테스트 결과
├── test-2/                  # Phase 3: impl-2 테스트 결과
│
├── comparator/              # Phase 4 출력 (N>=2)
│   ├── comparison.md        #   비교 보고서
│   └── rankings.json        #   순위 데이터
│
├── human-review.json        # Phase 5: 사용자 선택 요청 (추천 정보 포함)
├── selection-decision.json  # Phase 5: 사용자의 선택 결과
│
└── integration-info.json    # Phase 6: 통합 브랜치 정보
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

- 모든 구현이 **같은 원본 코드**에서 시작
- 각 구현은 **독립 브랜치**에서 작업
- 구현 간 **간섭 없음**
- 선택 후 `git merge <branch>` 로 통합

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
│   ├── watcher.py                 #   DirectoryWatcher + FileWaitHelper
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
│       ├── logger.py              #     로깅 설정
│       ├── notifier.py            #     시스템 알림 (macOS/Linux/Windows)
│       ├── spec_parser.py         #     기획서 파싱 (마크다운 → 구조체)
│       └── spec_validator.py      #     기획서 검증 (규칙 기반)
│
├── prompts/                       # 에이전트 프롬프트 템플릿
│   ├── architect.md               #   Architect 프롬프트
│   ├── implementer.md             #   Implementer 프롬프트
│   ├── reviewer.md                #   Reviewer 프롬프트
│   ├── tester.md                  #   Tester 프롬프트
│   └── comparator.md              #   Comparator 프롬프트
│
└── workspace/                     # 런타임 워크스페이스
    ├── planning/
    │   ├── in-progress/           #   기획 작성 중
    │   └── completed/             #   완성된 기획서 (watch 모드 감지 대상)
    ├── tasks/                     #   실행 중/완료된 태스크
    └── .cache/                    #   Git clone 캐시
```

---

## 9. 실전 시나리오

### 시나리오 A: 간단한 기능 추가 (N=1)

```bash
# 1. config.yaml에 target_repo 설정 후
python cli.py run -s my-spec.md
# → Phase 1 완료, 체크포인트 대기

# 2. 다른 터미널에서 승인
python cli.py approve task-20250211-153000

# 3. Phase 2~6 자동 진행 후 완료
# → git merge task-20250211-153000/impl-1
```

### 시나리오 B: 2개 방법 비교 (N=2)

```bash
# 1. 기획서에 "### 방법 1", "### 방법 2" 작성 후 실행
python cli.py run -s auth-spec.md

# 2. Phase 1 후 체크포인트 — 2개 모두 승인
python cli.py approve task-20250211-160000

# 3. Phase 2(병렬 구현) → Phase 3(병렬 리뷰+테스트) → Phase 4(비교) 자동 진행

# 4. Phase 5 대기 — 비교 결과 확인
python cli.py status task-20250211-160000
# → Rankings: [2, 1]
# → 추천 구현: impl-2

# 5. comparison.md 확인 후 선택
cat workspace/tasks/task-20250211-160000/comparator/comparison.md
python cli.py select task-20250211-160000 2

# 6. Phase 6 완료
# → git merge task-20250211-160000/impl-2
```

### 시나리오 C: 3개 중 1개 반려 (N=3, 개별 승인)

```bash
# 1. 기획서에 3개 방법 작성 후 실행
python cli.py run -s complex-spec.md

# 2. Phase 1 후 — 방법 3이 마음에 들지 않으면
python cli.py approve task-20250211-170000 --approaches 1,2 --reject 3
# → 방법 1, 2만 Phase 2로 진행 (방법 3은 제외)

# 3. 이후 2개 구현에 대해 Phase 2~5 진행
python cli.py select task-20250211-170000 1
```

### 시나리오 D: watch 모드로 자동 실행

```bash
# 1. watch 모드 시작
python cli.py watch

# 2. 다른 터미널에서 기획서를 completed 디렉토리에 배치
cp my-spec.md workspace/planning/completed/my-feature/planning-spec.md

# 3. 5초 내 자동 감지 → 파이프라인 실행
# → 새 기획서 감지: .../planning-spec.md
# → 파이프라인을 시작합니다...

# auto_revalidate가 true이면:
# 기획서를 수정하면 자동으로 재검증/재실행
```

---

## 10. 트러블슈팅

### "기획서 검증 실패"

**원인**: 기획서가 검증 규칙을 통과하지 못함

**해결**:
1. `validation-errors.md` 확인
2. 주요 오류:
   - "구현 방법 섹션이 없습니다" → `## 구현 방법` 헤딩 추가
   - "기획서 내용이 너무 짧습니다" → 50자 이상으로 작성
   - "구현 방법 개수 불일치" → 헤딩의 N과 `### 방법` 개수를 맞춤

### "target_repo가 설정되지 않았습니다"

**해결**: `config.yaml`의 `project.target_repo`에 Git URL 설정
```yaml
project:
  target_repo: "https://github.com/your-org/your-project"
```

### "Claude Code CLI not found"

**원인**: `claude` 명령이 PATH에 없음

**해결**: Claude Code CLI를 설치하고 `claude` 명령이 실행되는지 확인
```bash
claude --version
```

### 체크포인트에서 무한 대기

**원인**: `approve`/`revise`/`abort` 명령을 아직 실행하지 않음

**해결**: 다른 터미널에서 명령 실행
```bash
python cli.py approve <task-id>
# 또는
python cli.py abort <task-id>
```

기본 타임아웃은 1시간(3600초)입니다.

### Phase 5에서 무한 대기 (N>=2)

**원인**: `select` 명령을 아직 실행하지 않음

**해결**:
```bash
# 추천 확인
python cli.py status <task-id>

# 선택
python cli.py select <task-id> <impl-id>
```

### 모든 구현이 실패

**원인**: 기획서가 모호하거나, 타겟 프로젝트 코드에 문제가 있음

**해결**:
1. 각 worktree 디렉토리에서 에러 로그 확인
2. 기획서를 더 구체적으로 수정
3. `timeline.log`에서 실패 지점 확인

---

## 부록: 자주 사용하는 명령 모음

```bash
# === 초기 설정 ===
python cli.py init                              # config.yaml 생성

# === 실행 ===
python cli.py run -s spec.md                    # 파이프라인 실행
python cli.py run -s spec.md -v                 # 상세 로깅
python cli.py watch                             # 감시 모드

# === 체크포인트 (Phase 1 후) ===
python cli.py approve <task-id>                 # 전체 승인
python cli.py approve <task-id> --approaches 1,2  # 개별 승인
python cli.py approve <task-id> --reject 3      # 개별 반려
python cli.py revise <task-id> -f "피드백"       # 수정 요청
python cli.py abort <task-id>                   # 중단

# === 선택 (Phase 5, N>=2) ===
python cli.py select <task-id> <impl-id>        # 구현 선택

# === 상태 확인 ===
python cli.py status                            # 전체 목록
python cli.py status <task-id>                  # 상세 상태

# === 통합 (Phase 6 완료 후) ===
cd <타겟-프로젝트>
git merge <task-id>/impl-<N>                    # 선택된 브랜치 병합
```
