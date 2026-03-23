# Workspace 구조

## 개념

하나의 **서비스** = 하나의 **워크스페이스**.

서비스란 기술 단위(FE/BE)가 아닌 하나의 비즈니스 단위를 의미한다. FE, BE, DB, 알림 서버 등은 모두 같은 서비스의 하위 프로젝트(Root Project)이다.

```
workspaces/
├── {서비스A}/     ← 워크스페이스 (비즈니스 단위)
└── {서비스B}/     ← 워크스페이스 (별개의 비즈니스)
```

---

## 전체 디렉토리 레이아웃

```
multi-agent-dev-system/
│
├── orchestrator/
├── prompts/
├── config.yaml
│
└── workspaces/
    └── {서비스명}/
        │
        ├── {서비스명}-BE/              # Root Project: 백엔드 GitHub 레포 클론
        │   ├── .git/
        │   └── src/
        │
        ├── {서비스명}-FE/              # Root Project: 프론트엔드 GitHub 레포 클론 (선택)
        │   ├── .git/
        │   └── src/
        │
        ├── .cache/                     # 시스템 자동 관리 (직접 편집 금지)
        │   └── {서비스명}-BE/          #   bare clone 또는 로컬 init 저장소
        │       └── .git/
        │
        ├── planning/
        │   ├── in-progress/            # 기획 작성 중
        │   │   └── {기능명}/
        │   │       └── planning-spec.md
        │   └── completed/              # 완성된 기획서 (여기로 이동하면 자동 실행)
        │       └── {기능명}/
        │           └── planning-spec.md
        │
        └── work/
            └── task-{timestamp}/       # 태스크 실행 디렉토리
                ├── manifest.json
                ├── timeline.log
                ├── planning-spec.md    # 기획서 복사본
                ├── project-profile.json
                ├── project-context.md
                ├── architect/
                │   └── approaches.json
                ├── implementations/
                │   ├── impl-1/         # git worktree (브랜치: task-{id}/impl-1)
                │   │   ├── (프로젝트 코드 전체)
                │   │   └── .multi-agent/
                │   │       └── summary.json
                │   └── impl-2/         # git worktree (브랜치: task-{id}/impl-2)
                │       ├── (프로젝트 코드 전체)
                │       └── .multi-agent/
                │           └── summary.json
                ├── review-1/
                │   └── review.md
                ├── review-2/
                │   └── review.md
                ├── test-1/
                │   └── test-results.json
                ├── test-2/
                │   └── test-results.json
                ├── comparator/         # alternative 모드
                │   └── comparison.md
                ├── integrated/         # concern 모드 (git worktree: task-{id}/integrated)
                └── evaluation-result.md
```

---

## Root Project 폴더

실제 GitHub 저장소의 main/master 브랜치를 클론한 폴더.

### 규칙
- 폴더명: `{서비스명}-{구성요소}` (예: `myapp-BE`, `myapp-FE`, `myapp-Admin`)
- 항상 원본 저장소와 동기화 상태 유지
- 시스템이 작업 시작 전 자동으로 `git fetch + reset --hard`로 최신화
- 에이전트가 코드 컨텍스트 참조 시 이 폴더의 파일을 읽음

### 모노레포인 경우
단일 Root Project 폴더 `{서비스명}/`을 사용하고, 내부에 FE/BE 하위 디렉토리가 존재한다.

### 여러 레포가 있는 경우
```
workspaces/{서비스}/
├── {서비스}-BE/         # 백엔드 레포
├── {서비스}-FE-Web/     # 사용자 웹 레포
├── {서비스}-FE-Admin/   # 관리자 웹 레포
└── {서비스}-Worker/     # 배치 처리 레포
```

각각 `config.yaml`의 `projects` 하위에 별도 항목으로 등록한다.

---

## .cache 폴더

시스템이 자동으로 관리하는 git 저장소 캐시. **직접 편집하지 말 것.**

### 기존 레포가 있는 경우

```
.cache/{레포명}/
└── .git/    ← git clone --bare 결과
```

- 작업 시작 시 `git fetch origin` + `git reset --hard origin/{default_branch}`로 동기화
- 각 구현체는 이 저장소에서 `git worktree add`로 분기

### 신규 프로젝트 (target_repo 비어있는 경우)

```
.cache/{프로젝트키}/
└── .git/    ← git init + 빈 초기 커밋
```

- `config.yaml`에서 `target_repo: ""`이면 첫 실행 시 자동 초기화
- 이후 동일하게 worktree 기반 구현 격리 적용

---

## planning 폴더

### 기획서 라이프사이클

```
planning/in-progress/{기능명}/planning-spec.md   ← 기획 작성 중
    |
    | mv planning/in-progress/{기능명} planning/completed/{기능명}
    v
planning/completed/{기능명}/planning-spec.md     ← Orchestrator가 감지
    |
    | (자동 실행)
    v
work/task-{timestamp}/                           ← 태스크 생성 및 파이프라인 시작
```

### 이동 명령

```bash
mv workspaces/{서비스}/planning/in-progress/{기능명} \
   workspaces/{서비스}/planning/completed/{기능명}
```

Watch 모드가 실행 중이면 이동 즉시 파이프라인이 시작된다.
Watch 모드가 꺼져 있으면 `python3 cli.py run -s {spec경로}`로 직접 실행한다.

---

## work 폴더

### Task 디렉토리 주요 파일

| 파일/폴더 | 설명 |
|-----------|------|
| `manifest.json` | 태스크 메타데이터. 현재 단계, N값, 파이프라인 모드, Phase 이력 |
| `timeline.log` | 전체 진행 타임라인. Phase 전환 및 오류 기록 |
| `planning-spec.md` | 기획서 복사본 |
| `project-profile.json` | 프로젝트 정적 분석 결과 (commit SHA 기반 캐싱) |
| `project-context.md` | 에이전트에게 전달되는 프로젝트 컨텍스트 (기획서 관련 모듈 코드) |
| `architect/approaches.json` | Architect가 설계한 N개 접근법 |
| `implementations/impl-N/` | git worktree. 브랜치: `task-{id}/impl-N` |
| `implementations/impl-N/.multi-agent/summary.json` | Implementer의 구현 요약 |
| `review-N/review.md` | Reviewer 출력 (N번째 구현 리뷰) |
| `test-N/test-results.json` | Tester 출력 (N번째 구현 테스트 결과) |
| `comparator/comparison.md` | Comparator 비교 결과 (alternative 모드) |
| `integrated/` | Integrator 통합 결과 worktree (concern 모드) |
| `evaluation-result.md` | 최종 평가 결과 및 머지 가이드 |

### Task ID 형식

`task-{YYYYMMDD}-{HHMMSS}` (예: `task-20260317-143000`)

---

## 워크스페이스 초기화 절차

### 새 서비스를 추가하는 경우

**1. 디렉토리 생성**
```bash
mkdir -p workspaces/{서비스명}/planning/{in-progress,completed}
```

**2. Root Project 클론 (기존 레포가 있는 경우)**
```bash
git clone {be-repo-url} workspaces/{서비스명}/{서비스명}-BE
git clone {fe-repo-url} workspaces/{서비스명}/{서비스명}-FE   # 필요 시
```

**3. config.yaml 업데이트**
```yaml
workspaces:
  {서비스명}:
    path: ./workspaces/{서비스명}
    projects:
      be:
        target_repo: "{be-repo-url}"
        default_branch: "main"
        github_token: "personal"

watch:
  dirs:
    - workspace: "{서비스명}"
      path: ./workspaces/{서비스명}/planning/completed
```

**4. 신규 프로젝트인 경우** — Root Project 클론 불필요, `target_repo`만 비워두면 된다.
```yaml
projects:
  new-module:
    target_repo: ""
    default_branch: "main"
```

---

## 멀티 서비스 운영

여러 서비스를 동시에 운영하는 경우 Watch 모드가 모든 서비스를 동시에 감시한다.

```yaml
watch:
  dirs:
    - workspace: "service-a"
      path: ./workspaces/service-a/planning/completed
    - workspace: "service-b"
      path: ./workspaces/service-b/planning/completed
    - workspace: "service-c"
      path: ./workspaces/service-c/planning/completed
```

각 서비스의 태스크는 독립적으로 실행된다. 동시에 여러 기획서가 `completed/`로 이동해도 각각 별도 태스크로 처리된다.
