# Workspace 구조 설계

## 개념

하나의 **서비스** = 하나의 **워크스페이스**.
서비스란 FE/BE/DB 등으로 나뉘는 기술 단위가 아니라, 하나의 비즈니스 단위를 의미한다.

## 전체 디렉토리 레이아웃

```
multi-agent-dev-system/
│
├── orchestrator/               # 시스템 코어
├── prompts/                    # 에이전트 프롬프트 템플릿
├── config.yaml                 # 시스템 설정
│
└── workspaces/
    └── my-service/             # 워크스페이스 (서비스 단위)
        │
        ├── my-service-BE/      # Root Project: 백엔드 GitHub 레포 클론
        │   ├── .git/
        │   └── src/
        │
        ├── my-service-FE/      # Root Project: 프론트엔드 GitHub 레포 클론 (선택)
        │   ├── .git/
        │   └── src/
        │
        ├── .cache/             # Git 캐시 (시스템이 자동 관리, 직접 편집 금지)
        │   └── my-service-BE/  #   bare clone 또는 로컬 init 저장소
        │       └── .git/
        │
        ├── planning/           # 기획서 관리
        │   ├── in-progress/    #   작성 중인 기획서
        │   │   └── add-auth/
        │   │       └── planning-spec.md
        │   └── completed/      #   완성된 기획서 (여기로 이동하면 자동 실행)
        │       └── user-login/
        │           └── planning-spec.md
        │
        └── work/               # 태스크 실행 디렉토리
            └── task-20260317-143000/
                ├── manifest.json
                ├── timeline.log
                ├── planning-spec.md    # 기획서 복사본
                ├── project-profile.json
                ├── project-context.md  # 프로젝트 분석 결과 (에이전트 참조용)
                ├── architect/
                │   └── approaches.json
                ├── implementations/
                │   ├── impl-1/         # git worktree (브랜치: task-{id}/impl-1)
                │   │   ├── (프로젝트 코드 전체)
                │   │   └── .multi-agent/
                │   │       └── summary.json
                │   └── impl-2/         # git worktree (브랜치: task-{id}/impl-2)
                ├── review-1/
                │   └── review.md
                ├── review-2/
                │   └── review.md
                ├── test-1/
                │   └── test-results.json
                ├── comparator/         # alternative 모드
                │   └── comparison.md
                ├── integrated/         # concern 모드 (git worktree)
                └── evaluation-result.md
```

## Root Project 폴더

### 규칙
- 폴더명: `{서비스명}-{구성요소}` (예: `my-app-FE`, `my-app-BE`)
- 내용: 실제 GitHub 저장소의 main/master 브랜치 클론
- 용도: 프로젝트 분석 시 코드 컨텍스트 참조 대상
- 관리: 시스템이 작업 시작 전 자동으로 `git fetch + reset --hard`로 최신화

### 모노레포인 경우
- 단일 root project 폴더: `{서비스명}/`
- 내부에 FE/BE 등이 하위 디렉토리로 존재

## .cache 폴더

시스템이 자동으로 관리하는 git 저장소 캐시. **직접 편집하지 말 것.**

### 기존 레포가 있는 경우
```
.cache/{repo-name}/   ← git clone 결과
    └── .git/
```
- 작업 시작 시 `git fetch origin` + `git reset --hard origin/main`으로 동기화
- 각 구현체는 이 저장소에서 `git worktree add`로 분기

### 신규 프로젝트 (레포 없는 경우)
```
.cache/project/       ← git init 결과
    └── .git/         (빈 초기 커밋 포함)
```
- `config.yaml`의 `target_repo`를 비워두면 자동으로 로컬 저장소 초기화
- 이후 동일하게 worktree 기반 구현 격리 적용

## Planning 폴더

### 기획서 라이프사이클
```
planning/in-progress/{기능명}/planning-spec.md   (기획 작성 중)
    ↓ (기획 완료 후 이동)
planning/completed/{기능명}/planning-spec.md     (자동 실행 대기)
    ↓ (Orchestrator 감지)
work/task-{timestamp}/ 생성 → 파이프라인 자동 실행
```

### 이동 방법
```bash
mv planning/in-progress/add-auth planning/completed/add-auth
```

## Work 폴더

### Task 디렉토리 핵심 파일

| 파일/폴더 | 설명 |
|-----------|------|
| `manifest.json` | 작업 메타데이터 (현재 단계, Phase 이력, N값 등) |
| `timeline.log` | 전체 진행 타임라인 |
| `planning-spec.md` | 기획서 복사본 |
| `project-profile.json` | 프로젝트 정적 분석 결과 (캐싱용) |
| `project-context.md` | 에이전트에게 전달되는 프로젝트 컨텍스트 |
| `architect/approaches.json` | Architect가 설계한 N개 접근법 |
| `implementations/impl-N/` | git worktree (구현체 N) |
| `review-N/review.md` | Reviewer 출력 |
| `test-N/test-results.json` | Tester 출력 |
| `comparator/comparison.md` | Comparator 출력 (alternative 모드) |
| `integrated/` | Integrator 통합 결과 worktree (concern 모드) |
| `evaluation-result.md` | 최종 평가 결과 |

## 워크스페이스 초기화

새 서비스를 추가할 때:

```bash
# 디렉토리 구조 생성
mkdir -p workspaces/{service}/planning/{in-progress,completed}

# Root project 클론 (레포가 있는 경우)
git clone {be-repo-url} workspaces/{service}/{service}-BE
git clone {fe-repo-url} workspaces/{service}/{service}-FE   # 필요한 경우

# config.yaml에 워크스페이스 등록
# workspaces.{service}.projects.be.target_repo 설정
```

신규 프로젝트(레포 없음)는 `target_repo`를 비워두면 첫 실행 시 자동 초기화된다.
