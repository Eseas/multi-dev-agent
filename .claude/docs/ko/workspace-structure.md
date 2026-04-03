# 워크스페이스 구조

## 개념

하나의 **서비스** = 하나의 **워크스페이스**.

서비스란 기술 단위(FE/BE)가 아닌 하나의 비즈니스 단위. FE, BE, DB, 알림 서버 등은 모두 같은 서비스의 하위 프로젝트(Root Project)이다.

---

## 디렉토리 레이아웃

```
multi-agent-dev-system/
│
├── orchestrator/              # 파이프라인 코어
├── skills/                    # 스킬 정의 (skill-*.md)
├── schemas/                   # JSON 스키마 정의 (*.schema.json)
├── scripts/                   # 유틸리티 스크립트 (json_to_md.py 등)
├── prompts/                   # 레거시 에이전트 프롬프트 (fallback)
├── config.yaml                # 시스템 설정
│
└── workspaces/
    └── {서비스}/
        │
        ├── {서비스}-BE/               # Root Project: 백엔드 레포 클론
        ├── {서비스}-FE/               # Root Project: 프론트엔드 레포 클론 (선택)
        │
        ├── .cache/                    # 시스템 자동 관리 (직접 편집 금지)
        │   └── {서비스}-BE/.git/      #   bare clone 또는 local init
        │
        ├── planning/
        │   ├── in-progress/           # 기획 작성 중
        │   │   └── {기능명}/
        │   │       └── planning-spec.md
        │   └── completed/             # 완성된 기획서 (자동 파이프라인 트리거)
        │       └── {기능명}/
        │           └── planning-spec.md
        │
        └── work/
            └── task-{timestamp}/      # 태스크 실행 디렉토리
                ├── manifest.json
                ├── timeline.log
                ├── docs/              # 모든 JSON 산출물
                │   ├── requirements.json
                │   ├── execution-plan.json
                │   ├── approaches.json
                │   ├── api-contract.json        (concern 모드)
                │   ├── impl-1-review.json
                │   ├── impl-1-test-results.json
                │   ├── comparison.json           (alternative 모드)
                │   ├── integration-report.json   (concern 모드)
                │   └── impl-N-simplification.json
                ├── implementations/
                │   ├── impl-1/        # git worktree (브랜치: task-{id}/impl-1)
                │   │   └── (프로젝트 코드 + work-done.json)
                │   └── impl-2/        # git worktree (브랜치: task-{id}/impl-2)
                │       └── (프로젝트 코드 + work-done.json)
                └── evaluation-result.md
```

---

## Root Project 폴더

GitHub 저장소의 main/master 브랜치를 클론한 폴더.

- 폴더명: `{서비스}-{구성요소}` (예: `myapp-BE`, `myapp-FE`)
- 항상 원격과 동기화 (태스크 시작 전 자동 `git fetch + reset --hard`)
- 에이전트가 코드 컨텍스트 참조 시 이 폴더의 파일을 읽음

### 모노레포
단일 폴더 `{서비스}/` 내부에 FE/BE 하위 디렉토리.

### 복수 레포
```
workspaces/{서비스}/
├── {서비스}-BE/
├── {서비스}-FE-Web/
├── {서비스}-FE-Admin/
└── {서비스}-Worker/
```

---

## .cache 폴더

시스템이 자동 관리하는 git 저장소 캐시. **직접 편집 금지.**

- 기존 레포: `git clone --bare` → `git fetch` + `git reset --hard`
- 신규 프로젝트 (`target_repo: ""`): `git init` + 빈 커밋

---

## Planning 폴더 라이프사이클

```
planning/in-progress/{기능명}/planning-spec.md   ← 작성 중
    |
    | mv to completed/
    v
planning/completed/{기능명}/planning-spec.md     ← Orchestrator 감지
    |
    v
work/task-{timestamp}/                           ← 파이프라인 시작
```

---

## 워크스페이스 초기화

### 새 서비스 추가

1. 디렉토리 생성:
```bash
mkdir -p workspaces/{서비스}/planning/{in-progress,completed}
```

2. 레포 클론 (기존 레포가 있는 경우):
```bash
git clone {be-repo-url} workspaces/{서비스}/{서비스}-BE
```

3. config.yaml 업데이트:
```yaml
workspaces:
  {서비스}:
    path: ./workspaces/{서비스}
    projects:
      be:
        target_repo: "{be-repo-url}"
        default_branch: "main"
        github_token: "personal"
```

4. 신규 프로젝트 (레포 없음): `target_repo: ""`로 설정.
