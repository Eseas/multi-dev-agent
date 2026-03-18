# Multi-Agent Dev System - Base Configuration

이 저장소는 **다중 AI 에이전트 개발 시스템의 베이스 프로젝트**입니다.
각 서비스(프로젝트)는 독립된 workspace를 가지며, 이 시스템이 해당 workspace 내에서 작업을 관리합니다.

## 디렉토리 구조

```
multi-agent-dev-system/           # 베이스 프로젝트 (이 저장소)
├── .claude/
│   ├── claude.md                 # 이 파일 (베이스 설정)
│   └── docs/                     # 시스템 기획 문서
├── orchestrator/                 # 오케스트레이터 코어
├── prompts/                      # 에이전트 프롬프트 템플릿
├── config.yaml                   # 시스템 설정
│
├── workspaces/                   # 서비스별 워크스페이스
│   ├── {service-name}/                    # 하나의 서비스 = 하나의 워크스페이스
│   │   ├── {service-name}-BE/             # 메인 API 서버 레포
│   │   ├── {service-name}-BE-Admin/       # 관리자 API 레포 (분리된 경우)
│   │   ├── {service-name}-BE-Worker/      # 배치/백그라운드 잡 레포 (분리된 경우)
│   │   ├── {service-name}-FE-Web/         # 사용자용 웹 레포 (없으면 생략)
│   │   ├── {service-name}-FE-Admin/       # 관리자 대시보드 웹 레포 (없으면 생략)
│   │   ├── {service-name}-FE-App/         # 모바일 앱 레포 (없으면 생략)
│   │   ├── {service-name}-Infra/          # IaC 레포 (없으면 생략)
│   │   ├── planning/             # 이 서비스의 기획서들
│   │   │   ├── in-progress/
│   │   │   └── completed/
│   │   └── work/                 # 작업 디렉토리 (기존 tasks/ 대체)
│   │       └── task-{id}/
│   │           ├── implementations/
│   │           │   ├── impl-1/
│   │           │   └── impl-2/
│   │           ├── architect/
│   │           ├── manifest.json
│   │           └── timeline.log
│   │
│   └── {another-service}/
│       ├── {another-service}-API/
│       ├── planning/
│       └── work/
```

## 핵심 개념

### 서비스 (Service) = 워크스페이스 (Workspace)
- 하나의 서비스는 하나의 비즈니스 단위
- FE, BE, DB 등은 서비스의 **하위 구성요소**이지 별개의 프로젝트가 아님
- 예: "소셜미디어 앱" 서비스 안에 FE, BE, 알림서버 등이 포함

### Root Project 폴더
- 실제 GitHub 저장소의 master/main 브랜치를 클론한 폴더
- `{service-name}-FE/`, `{service-name}-BE/` 등의 이름 규칙
- 이 폴더들은 항상 원본 저장소와 동기화 상태 유지

### Work 폴더
- 기존 `workspace/tasks/`를 대체
- 각 작업(task)이 독립된 디렉토리에서 실행됨
- root project 폴더와 동일한 depth에 위치

### Planning 폴더
- 서비스별로 독립된 기획 관리
- `in-progress/`: 기획 진행 중
- `completed/`: 완성된 기획서 → work 폴더에서 실행 대기
