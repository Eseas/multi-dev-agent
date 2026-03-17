# Workspace 구조 설계

## 개념

하나의 **서비스** = 하나의 **워크스페이스**.
서비스란 FE/BE/DB 등으로 나뉘는 기술 단위가 아니라, 하나의 비즈니스 단위를 의미한다.

## 디렉토리 레이아웃

```
workspaces/
└── my-social-app/                    # 워크스페이스 (서비스 단위)
    │
    ├── my-social-app-FE/             # Root Project: 프론트엔드 GitHub 레포
    │   ├── .git/                     #   master/main 브랜치 기준
    │   ├── src/
    │   ├── package.json
    │   └── ...
    │
    ├── my-social-app-BE/             # Root Project: 백엔드 GitHub 레포
    │   ├── .git/
    │   ├── src/
    │   ├── build.gradle
    │   └── ...
    │
    ├── my-social-app-INFRA/          # Root Project: 인프라 (선택)
    │   └── ...
    │
    ├── planning/                     # 이 서비스의 기획서
    │   ├── in-progress/
    │   │   └── add-notification/
    │   │       └── planning-spec.md
    │   └── completed/
    │       └── user-auth-refactor/
    │           └── planning-spec.md
    │
    └── work/                         # 작업 디렉토리
        ├── task-20260317-143000/
        │   ├── manifest.json         # 작업 메타데이터
        │   ├── timeline.log          # 진행 로그
        │   ├── architect/
        │   │   └── approaches.json
        │   ├── implementations/
        │   │   ├── impl-1/           # 구현체 1
        │   │   └── impl-2/           # 구현체 2
        │   ├── review/
        │   └── test/
        └── task-20260318-090000/
            └── ...
```

## Root Project 폴더

### 규칙
- 폴더명: `{서비스명}-{구성요소}` (예: `my-app-FE`, `my-app-BE`)
- 내용: 실제 GitHub 저장소의 master/main 브랜치 클론
- 용도: 에이전트가 코드 컨텍스트를 읽을 때 참조 + 최종 통합 대상
- 관리: 작업 시작 전 `git pull`로 최신 상태 유지

### 모노레포인 경우
- 단일 root project 폴더: `{서비스명}/`
- 내부에 FE/BE 등이 하위 디렉토리로 존재

## Planning 폴더

### 서비스별 기획 관리
- 각 워크스페이스마다 독립된 `planning/` 디렉토리
- 기획서는 해당 서비스의 컨텍스트 안에서 작성
- root project 코드를 직접 참조 가능

### 기획서 라이프사이클
```
planning/in-progress/{기능명}/planning-spec.md
    ↓ (기획 완료)
planning/completed/{기능명}/planning-spec.md
    ↓ (오케스트레이터가 감지)
work/task-{id}/ 생성 → 자동 실행
```

## Work 폴더

### 기존 tasks/ 대체
- 위치: 워크스페이스 루트의 `work/` 디렉토리
- root project 폴더들과 동일한 depth
- 각 task는 독립된 하위 디렉토리

### Task 디렉토리 구조
```
work/task-{timestamp}/
├── manifest.json          # 작업 정보 (기획서 경로, 상태, N값 등)
├── timeline.log           # 전체 진행 타임라인
├── planning-spec.md       # 기획서 복사본 (원본 참조 유지)
├── architect/
│   ├── approaches.json    # N개 접근법 상세
│   └── architect_state.json
├── implementations/
│   ├── impl-1/            # 독립 구현 디렉토리
│   │   ├── (구현 코드)
│   │   └── work-done.md
│   └── impl-2/
├── review/
│   └── review-report.md
├── test/
│   └── test-report.md
├── comparison/
│   └── comparison-report.md
└── integration/
    └── integration-report.md
```

## 워크스페이스 초기화

새 서비스를 추가할 때:

```bash
# 워크스페이스 생성
mkdir -p workspaces/{service-name}/{planning,work}/{in-progress,completed}

# Root project 클론
git clone {fe-repo-url} workspaces/{service-name}/{service-name}-FE
git clone {be-repo-url} workspaces/{service-name}/{service-name}-BE
```
