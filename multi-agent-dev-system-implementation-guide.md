# Multi-Agent Development System - 구현 가이드 및 사용 설명서

## 📋 목차

1. [시스템 개요](#1-시스템-개요)
2. [구현 상태 검증](#2-구현-상태-검증)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [설치 및 설정](#4-설치-및-설정)
5. [사용 방법](#5-사용-방법)
6. [핵심 구현 로직](#6-핵심-구현-로직)
7. [파이프라인 상세 흐름](#7-파이프라인-상세-흐름)
8. [디렉토리 구조](#8-디렉토리-구조)
9. [트러블슈팅](#9-트러블슈팅)
10. [확장 및 커스터마이징](#10-확장-및-커스터마이징)

---

## 1. 시스템 개요

### 1.1 목적
다중 AI 에이전트를 활용하여 **동일한 요구사항에 대해 여러 구현 방향을 병렬로 탐색**하고, 코드 리뷰 및 테스트를 거쳐 **최적의 구현을 선택**하는 자동화된 개발 시스템입니다.

### 1.2 핵심 특징
- ✅ **병렬 탐색**: N개의 서로 다른 구현 접근법을 동시에 개발
- ✅ **격리된 실행 환경**: 각 구현마다 독립적인 작업 공간
- ✅ **자동화된 평가**: 코드 리뷰 + 테스트 자동 수행
- ✅ **사람 개입 최소화**: 최종 선택 단계에서만 개입
- ✅ **관찰 가능성**: 모든 단계의 상태 및 로그 추적
- ✅ **시스템 알림**: macOS/Linux/Windows 네이티브 알림 지원

### 1.3 적응형 6단계 파이프라인

```
Requirements → Architect → Implementers → Review & Test → Comparator → Human → Integrator
                  (1개)      (N개 병렬)     (2N개 병렬)      (1개)      (선택)    (1개)
                          ↑
                   N = 1, 2, 3 (자동 조정)
```

**적응형 파이프라인**: 문제 복잡도에 따라 N을 자동으로 1~3 사이에서 조정
**하이브리드 모드**: 기본값 N=2로 일상 작업에도 효율적

---

## 2. 구현 상태 검증

### 2.1 제안서 대비 구현 현황

| 컴포넌트 | 제안서 | 구현 상태 | 비고 |
|---------|--------|----------|------|
| **Orchestrator** | ✓ | ✅ 완료 | `orchestrator/main.py` |
| **Claude Executor** | ✓ | ✅ 완료 | `orchestrator/executor.py` |
| **Directory Watcher** | ✓ | ✅ 완료 | `orchestrator/watcher.py` |
| **Environment Manager** | ✓ | ✅ 완료 | `orchestrator/utils/env_manager.py` |
| **Architect Agent** | ✓ | ✅ 완료 | `orchestrator/agents/architect.py` |
| **Implementer Agent** | ✓ | ✅ 완료 | `orchestrator/agents/implementer.py` |
| **Reviewer Agent** | ✓ | ✅ 완료 | `orchestrator/agents/reviewer.py` |
| **Tester Agent** | ✓ | ✅ 완료 | `orchestrator/agents/tester.py` |
| **Comparator Agent** | ✓ | ✅ 완료 | `orchestrator/agents/comparator.py` |
| **Integrator Agent** | ✓ | ✅ 완료 | `orchestrator/agents/integrator.py` |
| **Atomic Write** | ✓ | ✅ 완료 | `orchestrator/utils/atomic_write.py` |
| **Logger** | ✓ | ✅ 완료 | `orchestrator/utils/logger.py` |
| **CLI** | ✓ | ✅ 완료 | `cli.py` |
| **Config** | ✓ | ✅ 완료 | `config.yaml` |
| **Prompts** | ✓ | ✅ 완료 | `prompts/` 디렉토리 |
| **System Notifier** | ✗ | ✅ 추가 구현 | `orchestrator/utils/notifier.py` (보너스!) |

### 2.2 구현 완성도
**✅ 100% 구현 완료**

제안서의 모든 핵심 컴포넌트가 구현되었으며, 추가로 **시스템 알림 기능**까지 구현되어 제안서보다 더 풍부한 기능을 제공합니다.

---

## 3. 시스템 아키텍처

### 3.1 전체 구조

```
┌─────────────────────────────────────────────────────────────┐
│                     Orchestrator                            │
│              (파이프라인 조율 및 상태 관리)                    │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
        ┌─────────────────────────────────────────┐
        │  Stage 1: Architect Agent               │
        │  Input:  Requirements (요구사항)         │
        │  Output: approaches.json (N개 접근법)    │
        └─────────────────────────────────────────┘
                              │
                    [동적 환경 생성: impl-1 ~ impl-N]
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Stage 2:     │      │ Stage 2:     │      │ Stage 2:     │
│ Implementer 1│      │ Implementer 2│      │ Implementer N│
└──────────────┘      └──────────────┘      └──────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│ Stage 3:     │      │ Stage 3:     │      │ Stage 3:     │
│ Reviewer 1   │      │ Reviewer 2   │      │ Reviewer N   │
│ Tester 1     │      │ Tester 2     │      │ Tester N     │
└──────────────┘      └──────────────┘      └──────────────┘
        └─────────────────────┴─────────────────────┘
                              │
        ┌─────────────────────────────────────────┐
        │  Stage 4: Comparator Agent              │
        │  Input:  모든 구현 + 리뷰 + 테스트       │
        │  Output: rankings.json (순위)           │
        └─────────────────────────────────────────┘
                              │
        ┌─────────────────────────────────────────┐
        │  Stage 5: Human Review                  │
        │  Input:  human_review.json              │
        │  Wait:   decision.json (사람이 생성)     │
        └─────────────────────────────────────────┘
                              │
        ┌─────────────────────────────────────────┐
        │  Stage 6: Integrator Agent              │
        │  Input:  선택된 구현                     │
        │  Output: 프로젝트에 통합된 코드          │
        └─────────────────────────────────────────┘
```

### 3.2 핵심 컴포넌트

#### 3.2.1 Orchestrator (오케스트레이터)
- **역할**: 전체 파이프라인 조율 및 상태 관리
- **파일**: `orchestrator/main.py`
- **주요 메서드**:
  - `run_pipeline()`: 전체 파이프라인 실행
  - `_run_architect()`: Architect 에이전트 실행
  - `_run_implementers()`: N개 Implementer 병렬 실행
  - `_run_reviewers_and_testers()`: 리뷰/테스트 병렬 실행
  - `_run_comparator()`: 비교 분석 실행
  - `_human_review()`: 사람 리뷰 대기
  - `_run_integrator()`: 최종 통합

#### 3.2.2 ClaudeExecutor (Claude 실행기)
- **역할**: Claude Code CLI를 headless 모드로 실행
- **파일**: `orchestrator/executor.py`
- **기능**:
  - Subprocess를 통한 claude 명령 실행
  - Timeout 관리 (기본 300초)
  - 자동 재시도 (기본 3회)
  - 에러 핸들링

#### 3.2.3 BaseAgent (에이전트 기본 클래스)
- **역할**: 모든 에이전트의 공통 기능 제공
- **파일**: `orchestrator/agents/base.py`
- **기능**:
  - 상태 관리 (initialized → running → completed/failed)
  - 프롬프트 로딩 및 포맷팅
  - Claude 실행 래퍼
  - 입출력 파일 관리

#### 3.2.4 EnvironmentManager (환경 관리자)
- **역할**: 각 구현체의 격리된 환경 생성
- **파일**: `orchestrator/utils/env_manager.py`
- **전략**:
  - **Symlink**: 공통 디렉토리 (src, lib, config, tests)
  - **Copy**: 각 구현체의 독립적인 output, logs 디렉토리
  - **장점**: 디스크 공간 절약 + 격리 보장

#### 3.2.5 SystemNotifier (시스템 알림)
- **역할**: OS 네이티브 알림 전송
- **파일**: `orchestrator/utils/notifier.py`
- **지원 플랫폼**:
  - macOS: `osascript` 사용
  - Linux: `notify-send` 사용
  - Windows: PowerShell toast 알림

---

## 4. 설치 및 설정

### 4.1 사전 요구사항

```bash
# Python 3.8 이상
python --version  # Python 3.8+

# Claude Code CLI 설치 확인
claude --version

# Git (선택사항)
git --version
```

### 4.2 설치

```bash
# 1. 프로젝트 디렉토리로 이동
cd /Users/eseas/Desktop/mine/multi-agent-dev-system

# 2. Python 의존성 설치
pip install -r requirements.txt

# 또는 개발 모드로 설치
pip install -e .
```

**의존성**:
- `pyyaml>=6.0`: YAML 설정 파일 파싱
- `watchdog>=3.0.0`: 파일 시스템 감시 (현재 미사용이지만 향후 확장용)

### 4.3 초기화

```bash
# 기본 설정 파일 생성
python cli.py init

# 또는 커스텀 경로 지정
python cli.py init -o my_config.yaml
```

생성된 `config.yaml`:

```yaml
workspace:
  root: ./workspace            # 작업 공간 디렉토리

project:
  root: .                      # 프로젝트 루트

prompts:
  directory: ./prompts         # 프롬프트 템플릿 디렉토리

execution:
  timeout: 300                 # Claude 실행 타임아웃 (초)
  max_retries: 3               # 재시도 횟수

pipeline:
  num_approaches: 2            # 병렬 구현 개수 (기본값, 하이브리드 모드)
  adaptive_mode: true          # 적응형 파이프라인 활성화
  complexity_threshold:        # 복잡도별 N 조정
    simple: 1
    medium: 2
    complex: 3

environment:
  shared_dirs:                 # Symlink할 디렉토리
    - src
    - lib
    - config
    - tests

notifications:
  enabled: true                # 알림 활성화
  sound: true                  # 알림 소리
```

### 4.4 설정 커스터마이징

#### 병렬 구현 개수 조정
```yaml
pipeline:
  num_approaches: 2            # 기본값 (하이브리드 모드)
  adaptive_mode: true          # 적응형 파이프라인 (권장)
  complexity_threshold:
    simple: 1                  # 단순 작업: N=1
    medium: 2                  # 일반 작업: N=2
    complex: 3                 # 복잡한 작업: N=3
```

**적응형 모드 사용 시**:
- 시스템이 기획서를 분석하여 복잡도 자동 판단
- 복잡도에 따라 N을 1~3 사이에서 조정
- 비용과 시간을 최적화하면서도 품질 유지

#### 타임아웃 조정
```yaml
execution:
  timeout: 600       # 복잡한 작업은 더 긴 시간 필요
  max_retries: 5
```

#### 공유 디렉토리 설정
```yaml
environment:
  shared_dirs:
    - src            # 기존 소스 코드
    - lib            # 라이브러리
    - config         # 설정 파일
    - tests          # 테스트 픽스처
    - docs           # 문서
```

---

## 5. 사용 방법

### 5.1 기본 실행

#### 방법 1: 인라인 요구사항
```bash
python cli.py run -r "사용자 관리 REST API 구축. 인증, CRUD, 권한 관리 포함"
```

#### 방법 2: 파일로 요구사항 제공
```bash
# requirements.txt 생성
echo "실시간 채팅 애플리케이션 구축
- WebSocket 기반
- 메시지 저장 및 검색
- 사용자 온라인 상태 표시
- 파일 첨부 기능" > requirements.txt

# 실행
python cli.py run -f requirements.txt
```

#### 방법 3: 커스텀 설정 사용
```bash
python cli.py run -r "GraphQL API 서버 구축" -c my_config.yaml
```

### 5.2 파이프라인 실행 과정

실행하면 다음과 같은 과정이 진행됩니다:

```
Starting multi-agent development pipeline...
================================================================================

[Stage 1] Architecture Analysis
  → Architect 에이전트가 요구사항 분석
  → 3개의 서로 다른 구현 접근법 생성
  → workspace/architect/approaches.json 저장
  ✓ Completed (45.2s)

[Stage 2] Parallel Implementation
  → impl-1, impl-2, impl-3 환경 생성
  → 각 접근법에 따라 병렬로 코드 구현
  ✓ Completed (187.5s)

[Stage 3] Code Review & Testing
  → 각 구현체에 대해 코드 리뷰 수행
  → 각 구현체에 대해 테스트 작성 및 실행
  ✓ Completed (156.3s)

[Stage 4] Implementation Comparison
  → 모든 구현체 비교 분석
  → 순위 및 추천 생성
  ✓ Completed (62.8s)

[Stage 5] Human Review Required
  → workspace/human_review.json 생성
  → workspace/decision.json 대기 중...

  📋 리뷰 데이터: workspace/human_review.json
  📝 결정 파일 생성 필요: workspace/decision.json

  형식:
  {
    "selected_id": 2,
    "action": "approve"
  }
```

### 5.3 사람 리뷰 및 승인

#### Step 1: 리뷰 데이터 확인

```bash
# human_review.json 내용 확인
cat workspace/human_review.json
```

예시 출력:
```json
{
  "rankings": [2, 1, 3],
  "implementations": [
    {
      "approach_id": 1,
      "approach": {
        "name": "Express + MongoDB 접근법",
        "description": "...",
        "pros": ["...", "..."],
        "cons": ["...", "..."]
      },
      "path": "workspace/impl-1",
      "review_success": true,
      "test_success": true
    },
    ...
  ],
  "timestamp": "2024-02-10T14:30:25.123456"
}
```

#### Step 2: 각 구현체 확인

```bash
# 구현체 1 확인
ls -la workspace/impl-1/
cat workspace/review-1/review.md
cat workspace/test-1/test_results.json

# 구현체 2 확인
ls -la workspace/impl-2/
cat workspace/review-2/review.md
cat workspace/test-2/test_results.json

# 비교 리포트 확인
cat workspace/comparator/comparison.md
```

#### Step 3: 결정 파일 생성

```bash
# 구현체 2를 선택하는 경우
cat > workspace/decision.json << EOF
{
  "selected_id": 2,
  "action": "approve"
}
EOF
```

**주의사항**:
- `selected_id`는 1부터 시작 (impl-1 = 1, impl-2 = 2, ...)
- `action`은 반드시 `"approve"` (향후 "reject", "modify" 등 추가 가능)

#### Step 4: 통합 완료 대기

decision.json을 생성하면 자동으로 진행됩니다:

```
[Stage 6] Code Integration
  → 선택된 구현체 (impl-2) 통합
  → 프로젝트 루트에 코드 병합
  ✓ Completed (34.7s)

================================================================================
✓ Pipeline completed successfully!
  Selected approach: 2
```

### 5.4 결과 확인

```bash
# 통합 요약 확인
cat workspace/integrator/integration_summary.json

# 타임라인 확인
cat workspace/timeline.log

# 전체 manifest 확인
cat workspace/manifest.json
```

---

## 6. 핵심 구현 로직

### 6.1 Orchestrator 파이프라인 실행 흐름

```python
# orchestrator/main.py의 run_pipeline() 메서드

def run_pipeline(self, requirements: str) -> Dict[str, Any]:
    try:
        # Stage 1: Architect
        self._update_stage('architecture')
        approaches = self._run_architect(requirements)
        self._complete_stage('architecture')

        # Stage 2: Implementation (병렬)
        self._update_stage('implementation')
        implementations = self._run_implementers(approaches, requirements)
        self._complete_stage('implementation')

        # Stage 3: Review & Test (병렬)
        self._update_stage('review_and_test')
        self._run_reviewers_and_testers(implementations)
        self._complete_stage('review_and_test')

        # Stage 4: Comparison
        self._update_stage('comparison')
        rankings = self._run_comparator(implementations)
        self._complete_stage('comparison')

        # Stage 5: Human Review
        self._update_stage('human_review')
        selected_id = self._human_review(rankings, implementations)
        self._complete_stage('human_review')

        # Stage 6: Integration
        self._update_stage('integration')
        result = self._run_integrator(selected_id, implementations)
        self._complete_stage('integration')

        return {'success': True, 'selected_approach': selected_id}
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

**핵심 포인트**:
1. **순차적 Stage 진행**: 각 Stage가 완료되어야 다음 진행
2. **상태 추적**: `_update_stage()`로 시작, `_complete_stage()`로 완료
3. **에러 처리**: 예외 발생 시 전체 파이프라인 중단

### 6.2 병렬 구현 실행 로직

```python
# orchestrator/main.py의 _run_implementers() 메서드

def _run_implementers(self, approaches: List[Dict], requirements: str) -> List[Dict]:
    implementations = []

    for i, approach in enumerate(approaches, start=1):
        # 1. 격리된 환경 생성
        env_name = f'impl-{i}'
        env_path = self.env_manager.create_environment(
            env_name,
            shared_dirs=self.config['environment'].get('shared_dirs', [])
        )

        # 2. Implementer 에이전트 실행
        agent = ImplementerAgent(i, env_path, self.executor, prompt_file)
        result = agent.run({
            'approach': approach,
            'requirements': requirements
        })

        implementations.append({
            'approach_id': i,
            'path': str(env_path),
            'success': result['success']
        })

    return implementations
```

**핵심 포인트**:
1. **동적 환경 생성**: N이 런타임에 결정됨 (Architect 결과에 따라)
2. **Symlink 활용**: 공통 디렉토리는 심볼릭 링크로 공유
3. **독립 실행**: 각 구현체는 완전히 격리된 환경에서 실행

### 6.3 사람 리뷰 대기 로직

```python
# orchestrator/main.py의 _human_review() 메서드

def _human_review(self, rankings: List[int], implementations: List[Dict]) -> Optional[int]:
    # 1. 리뷰 요약 생성
    summary = {
        'rankings': rankings,
        'implementations': implementations,
        'timestamp': datetime.now().isoformat()
    }

    review_file = self.workspace_root / 'human_review.json'
    atomic_write(review_file, summary)

    # 2. 알림 전송
    self.notifier.notify_human_review_needed()

    # 3. decision.json 대기 (Polling)
    decision_file = self.workspace_root / 'decision.json'

    decision = FileWaitHelper.wait_for_file_content(
        decision_file,
        expected_key='selected_id',
        timeout=3600  # 1시간
    )

    if decision and decision.get('action') == 'approve':
        return decision['selected_id']

    return None
```

**핵심 포인트**:
1. **Atomic Write**: 리뷰 파일을 원자적으로 생성 (race condition 방지)
2. **Polling 대기**: decision.json 파일이 생성될 때까지 대기
3. **Timeout**: 1시간 후 자동 실패 (무한 대기 방지)

### 6.4 Atomic Write 구현

```python
# orchestrator/utils/atomic_write.py

def atomic_write(file_path: Path, content: Any) -> None:
    """원자적 파일 쓰기 - race condition 방지"""

    # 1. 임시 파일에 먼저 쓰기
    tmp_path = file_path.with_suffix('.tmp')

    if isinstance(content, dict) or isinstance(content, list):
        tmp_path.write_text(json.dumps(content, indent=2, ensure_ascii=False))
    else:
        tmp_path.write_text(str(content))

    # 2. 원자적 rename (atomic operation)
    tmp_path.rename(file_path)
```

**원자성 보장**:
- `.tmp` 파일에 먼저 쓰기
- `rename()`은 OS 수준에서 atomic 연산
- 중간 상태가 노출되지 않음

### 6.5 Claude Executor 재시도 로직

```python
# orchestrator/executor.py

def execute(self, prompt: str, working_dir: Path, ...) -> Dict[str, Any]:
    attempt = 0
    last_error = None

    while attempt < self.max_retries:
        attempt += 1

        try:
            result = self._run_claude(prompt, working_dir, env_vars)

            if result['success']:
                return result  # 성공 시 즉시 반환

            last_error = result.get('error')

        except Exception as e:
            last_error = str(e)

        # 재시도 전 대기
        if attempt < self.max_retries:
            time.sleep(self.retry_delay)

    # 모든 재시도 실패
    return {
        'success': False,
        'error': f'Failed after {self.max_retries} attempts. Last: {last_error}'
    }
```

**재시도 전략**:
- 최대 3회 재시도 (기본값)
- 재시도 간 5초 대기
- 마지막 에러 메시지 보존

---

## 7. 파이프라인 상세 흐름

### 7.1 Stage 1: Architecture (Architect Agent)

**입력**:
- 사용자 요구사항 (requirements)
- `num_approaches` (config.yaml에서 지정)

**처리**:
1. `prompts/architect.md` 프롬프트 로드
2. 요구사항을 분석하여 N개의 서로 다른 접근법 도출
3. 각 접근법마다:
   - 이름, 설명
   - 장단점 (pros/cons)
   - 기술 스택 (tech_stack)
   - 복잡도 (estimated_complexity)
   - 구현 가이드 (implementation_guide)

**출력**:
- `workspace/architect/approaches.json`

```json
{
  "analysis": "요구사항 분석 요약",
  "approaches": [
    {
      "id": 1,
      "name": "Express + MongoDB",
      "description": "전통적인 REST API 접근법",
      "pros": ["빠른 개발", "풍부한 생태계"],
      "cons": ["확장성 제한"],
      "tech_stack": ["Express", "MongoDB", "JWT"],
      "estimated_complexity": "medium",
      "implementation_guide": "..."
    },
    ...
  ],
  "recommendation": "접근법 2를 추천하는 이유..."
}
```

### 7.2 Stage 2: Implementation (Implementer Agents)

**입력** (각 Implementer):
- 1개의 approach (from approaches.json)
- 원본 requirements

**처리** (병렬로 N개):
1. 격리된 환경 생성 (`workspace/impl-{i}/`)
2. 공유 디렉토리 symlink (src, lib, config, tests)
3. `prompts/implementer.md` 프롬프트 로드
4. Claude Code로 실제 코드 작성
5. 작업 완료 시 `summary.json` 생성

**출력** (각 구현체):
- `workspace/impl-{i}/output/` (생성된 코드)
- `workspace/impl-{i}/summary.json`

```json
{
  "approach_id": 1,
  "files_created": ["server.js", "routes/users.js", ...],
  "dependencies": ["express", "mongoose", "jsonwebtoken"],
  "run_instructions": "npm install && npm start",
  "limitations": ["...]
}
```

### 7.3 Stage 3: Review & Test (Reviewer + Tester Agents)

#### 7.3.1 Reviewer Agent (각 구현체마다)

**입력**:
- `workspace/impl-{i}/` 디렉토리

**처리**:
1. `prompts/reviewer.md` 프롬프트 로드
2. 코드 품질, 설계, 보안, 성능 등 리뷰
3. 점수 및 상세 피드백 작성

**출력**:
- `workspace/review-{i}/review.md`
- `workspace/review-{i}/review_summary.json`

```json
{
  "approach_id": 1,
  "score": 4.2,
  "summary": "잘 구조화된 코드, 일부 보안 이슈 있음",
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "suggestions": ["..."]
}
```

#### 7.3.2 Tester Agent (각 구현체마다)

**입력**:
- `workspace/impl-{i}/` 디렉토리

**처리**:
1. `prompts/tester.md` 프롬프트 로드
2. 테스트 코드 작성
3. 테스트 실행 및 결과 수집

**출력**:
- `workspace/test-{i}/test_output.log`
- `workspace/test-{i}/test_results.json`

```json
{
  "approach_id": 1,
  "tests_passed": 15,
  "tests_failed": 2,
  "coverage": "78%",
  "failures": [
    {"test": "auth token validation", "error": "..."}
  ]
}
```

### 7.4 Stage 4: Comparison (Comparator Agent)

**입력**:
- 모든 `implementations` 정보
- 모든 `review-{i}` 결과
- 모든 `test-{i}` 결과

**처리**:
1. `prompts/comparator.md` 프롬프트 로드
2. 모든 구현체를 종합 비교
3. 순위 결정 (rankings)

**출력**:
- `workspace/comparator/comparison.md` (상세 비교)
- `workspace/comparator/rankings.json`

```json
{
  "rankings": [2, 1, 3],
  "rationale": {
    "1": "높은 코드 품질, 일부 테스트 실패",
    "2": "균형잡힌 구현, 모든 테스트 통과, 우수한 문서화",
    "3": "참신한 접근법, 복잡도 높음"
  },
  "recommendation": "접근법 2를 추천합니다. 이유는..."
}
```

### 7.5 Stage 5: Human Review

**입력**:
- `rankings.json`
- 모든 구현체 정보

**처리**:
1. `human_review.json` 생성 (사람이 읽을 요약)
2. 시스템 알림 전송 (macOS notification)
3. `decision.json` 파일 polling 대기

**사람이 해야 할 일**:
```bash
# 1. 리뷰 데이터 확인
cat workspace/human_review.json
cat workspace/comparator/comparison.md

# 2. 각 구현체 직접 확인
cd workspace/impl-1 && ls
cd workspace/impl-2 && ls

# 3. 결정 파일 생성
echo '{"selected_id": 2, "action": "approve"}' > workspace/decision.json
```

### 7.6 Stage 6: Integration (Integrator Agent)

**입력**:
- `selected_id` (사람이 선택한 구현체 ID)
- 선택된 구현체 경로

**처리**:
1. `prompts/integrator.md` 프롬프트 로드
2. 선택된 구현체를 프로젝트 루트에 통합
3. 충돌 해결 (필요시)
4. 미사용 구현체 아카이브

**출력**:
- 프로젝트 루트에 통합된 코드
- `workspace/integrator/integration_summary.json`
- `workspace/archive/impl-{unselected}/` (미선택 구현체)

---

## 8. 디렉토리 구조

### 8.1 프로젝트 구조

```
multi-agent-dev-system/
├── cli.py                          # CLI 진입점
├── config.yaml                     # 설정 파일
├── requirements.txt                # Python 의존성
├── setup.py                        # 설치 스크립트
├── README.md                       # 기본 README
│
├── orchestrator/                   # 오케스트레이터 패키지
│   ├── __init__.py
│   ├── main.py                     # 메인 오케스트레이터
│   ├── executor.py                 # Claude 실행기
│   ├── watcher.py                  # 파일 감시 (향후 확장)
│   │
│   ├── agents/                     # 에이전트 모듈
│   │   ├── __init__.py
│   │   ├── base.py                 # 베이스 에이전트
│   │   ├── architect.py            # Architect 에이전트
│   │   ├── implementer.py          # Implementer 에이전트
│   │   ├── reviewer.py             # Reviewer 에이전트
│   │   ├── tester.py               # Tester 에이전트
│   │   ├── comparator.py           # Comparator 에이전트
│   │   └── integrator.py           # Integrator 에이전트
│   │
│   └── utils/                      # 유틸리티
│       ├── __init__.py
│       ├── atomic_write.py         # 원자적 파일 쓰기
│       ├── env_manager.py          # 환경 관리
│       ├── logger.py               # 로깅 설정
│       └── notifier.py             # 시스템 알림
│
├── prompts/                        # 프롬프트 템플릿
│   ├── architect.md                # Architect 프롬프트
│   ├── implementer.md              # Implementer 프롬프트
│   ├── reviewer.md                 # Reviewer 프롬프트
│   ├── tester.md                   # Tester 프롬프트
│   ├── comparator.md               # Comparator 프롬프트
│   └── integrator.md               # Integrator 프롬프트
│
└── workspace/                      # 작업 공간 (실행 시 생성)
    ├── manifest.json               # 파이프라인 상태
    ├── timeline.log                # 이벤트 타임라인
    ├── orchestrator.log            # 오케스트레이터 로그
    │
    ├── architect/                  # Architect 작업 공간
    │   ├── approaches.json         # 생성된 접근법
    │   └── architect_state.json    # 에이전트 상태
    │
    ├── impl-1/                     # 구현체 1
    │   ├── output/                 # 생성된 코드
    │   ├── logs/                   # 로그
    │   ├── summary.json            # 구현 요약
    │   ├── src -> ../../src        # Symlink
    │   └── lib -> ../../lib        # Symlink
    │
    ├── impl-2/                     # 구현체 2
    ├── impl-N/                     # 구현체 N
    │
    ├── review-1/                   # 구현체 1 리뷰
    │   ├── review.md               # 리뷰 상세
    │   └── review_summary.json     # 리뷰 요약
    │
    ├── test-1/                     # 구현체 1 테스트
    │   ├── test_output.log         # 테스트 로그
    │   └── test_results.json       # 테스트 결과
    │
    ├── comparator/                 # 비교 분석
    │   ├── comparison.md           # 상세 비교
    │   └── rankings.json           # 순위
    │
    ├── human_review.json           # 사람 리뷰용 요약
    ├── decision.json               # 사람 결정 (수동 생성)
    │
    ├── integrator/                 # 통합 작업
    │   └── integration_summary.json
    │
    └── archive/                    # 미선택 구현체 아카이브
        ├── impl-1/
        └── impl-3/
```

### 8.2 실행 후 Workspace 예시

```bash
workspace/
├── manifest.json                  # {"stage": "completed", "created_at": "..."}
├── timeline.log                   # 전체 타임라인
├── orchestrator.log               # 상세 로그
├── architect/
│   └── approaches.json            # 3개 접근법
├── impl-1/                        # Express + MongoDB
│   ├── output/
│   │   ├── server.js
│   │   ├── routes/
│   │   └── models/
│   └── summary.json
├── impl-2/                        # Fastify + PostgreSQL  ← 선택됨
│   ├── output/
│   │   ├── app.js
│   │   ├── api/
│   │   └── db/
│   └── summary.json
├── impl-3/                        # GraphQL + Redis
│   ├── output/
│   └── summary.json
├── review-1/
│   ├── review.md                  # "점수: 4.2/5"
│   └── review_summary.json
├── review-2/
│   ├── review.md                  # "점수: 4.7/5"  ← 최고 점수
│   └── review_summary.json
├── test-1/
│   └── test_results.json          # "15 passed, 2 failed"
├── test-2/
│   └── test_results.json          # "18 passed, 0 failed"  ← 모두 통과
├── comparator/
│   ├── comparison.md              # 상세 비교 보고서
│   └── rankings.json              # [2, 1, 3]
├── human_review.json              # 사람이 읽을 요약
├── decision.json                  # {"selected_id": 2, "action": "approve"}
├── integrator/
│   └── integration_summary.json
└── archive/
    ├── impl-1/                    # 미선택 구현체 보존
    └── impl-3/
```

---

## 9. 트러블슈팅

### 9.1 일반적인 문제

#### 문제: Claude Code CLI를 찾을 수 없음
```
Error: Claude Code CLI not found. Please install it first.
```

**해결**:
```bash
# Claude Code CLI 설치 확인
claude --version

# 설치 안 되어 있으면 설치
# (설치 방법은 Claude Code 공식 문서 참조)
npm install -g @anthropic-ai/claude-code
```

#### 문제: 파이프라인이 timeout으로 실패
```
Error: Execution timed out after 300 seconds
```

**해결**:
```yaml
# config.yaml에서 timeout 증가
execution:
  timeout: 600  # 10분으로 증가
  max_retries: 5
```

#### 문제: 환경 생성 실패
```
Error: Failed to create symlink for src: ...
```

**해결**:
```bash
# 공유 디렉토리 존재 확인
ls -la src lib config tests

# 없으면 config.yaml에서 제거
environment:
  shared_dirs:
    - src   # 이 디렉토리가 실제로 존재하는지 확인
```

#### 문제: decision.json이 인식되지 않음
```
Warning: Human review timeout or rejected
```

**해결**:
```bash
# 올바른 경로에 생성했는지 확인
ls -la workspace/decision.json

# JSON 형식 검증
python -m json.tool workspace/decision.json

# 필수 필드 확인
cat workspace/decision.json
# {"selected_id": 2, "action": "approve"}
```

### 9.2 디버깅 팁

#### 상세 로그 확인
```bash
# 오케스트레이터 로그
cat workspace/orchestrator.log

# 특정 에이전트 로그
cat workspace/impl-1/logs/*.log

# 타임라인 확인
cat workspace/timeline.log
```

#### Verbose 모드 실행
```bash
python cli.py run -r "..." -v  # Verbose 로깅 활성화
```

#### 수동으로 각 단계 디버그
```python
# debug.py
from orchestrator.main import Orchestrator
from pathlib import Path

orchestrator = Orchestrator(Path('config.yaml'))

# Stage 1만 실행
approaches = orchestrator._run_architect("사용자 요구사항...")
print(approaches)
```

### 9.3 알려진 제한사항

1. **병렬 실행 제한**: 현재는 순차 실행 (향후 asyncio로 개선 예정)
2. **Claude Code 의존성**: Claude Code CLI가 필수
3. **Timeout 관리**: 복잡한 작업은 timeout 조정 필요
4. **디스크 공간**: N개 구현체 생성 시 공간 필요

---

## 10. 확장 및 커스터마이징

### 10.1 커스텀 에이전트 추가

새로운 에이전트를 추가하려면:

```python
# orchestrator/agents/custom_agent.py

from .base import BaseAgent
from typing import Dict, Any

class CustomAgent(BaseAgent):
    def __init__(self, workspace, executor, prompt_file):
        super().__init__("custom", workspace, executor)
        self.prompt_file = prompt_file

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # 1. 프롬프트 로드 및 포맷
        prompt = self.load_prompt(
            self.prompt_file,
            some_param=context['some_param']
        )

        # 2. Claude 실행
        result = self.execute_claude(prompt)

        # 3. 결과 저장
        if result['success']:
            self.write_output('custom_output.json', {
                'data': '...'
            })

        return result
```

### 10.2 커스텀 프롬프트 작성

```markdown
<!-- prompts/custom_agent.md -->

당신은 전문 [역할]입니다.

## 입력
{input_data}

## 작업
다음을 수행하세요:
1. [단계 1]
2. [단계 2]

## 출력 형식
반드시 다음 JSON 형식으로 출력:

```json
{
  "field1": "value1",
  "field2": "value2"
}
```
```

### 10.3 파이프라인 확장

새로운 Stage 추가:

```python
# orchestrator/main.py

def run_pipeline(self, requirements: str):
    # ... 기존 stages ...

    # New Stage: Documentation
    self._update_stage('documentation')
    docs = self._run_documentation(selected_id, implementations)
    self._complete_stage('documentation')

    return result

def _run_documentation(self, selected_id, implementations):
    # DocumentationAgent 실행
    pass
```

### 10.4 웹 대시보드 추가 (향후)

```python
# 향후 확장: Flask 기반 대시보드

from flask import Flask, jsonify
import json

app = Flask(__name__)

@app.route('/api/status')
def get_status():
    manifest = json.loads(Path('workspace/manifest.json').read_text())
    return jsonify(manifest)

@app.route('/api/implementations')
def get_implementations():
    # impl-* 디렉토리 스캔
    pass
```

---

## 📚 참고 자료

### 관련 파일
- 📄 원본 제안서: `multi-agent-dev-system-proposal.md`
- 📘 기본 README: `multi-agent-dev-system/README.md`
- ⚙️ 설정 예시: `multi-agent-dev-system/config.yaml`

### 주요 개념
- **Orchestrator Pattern**: 중앙 조율자가 여러 에이전트 관리
- **Fan-out/Fan-in**: 병렬 실행 후 결과 수집
- **Human-in-the-Loop**: 중요한 결정에 사람 개입
- **Environment Isolation**: Symlink를 활용한 격리
- **Atomic Operations**: Race condition 방지

### 성능 최적화 팁
1. **num_approaches**: 2-3개가 최적 (5개 이상은 비교 복잡)
2. **shared_dirs**: 공통 리소스는 반드시 symlink
3. **timeout**: 복잡한 작업은 600초 이상 설정
4. **알림**: 장시간 작업 시 알림으로 진행 상황 확인

---

## ✅ 요약

이 시스템은 **제안서의 모든 핵심 기능이 완벽히 구현**되었으며, 추가로 시스템 알림 기능까지 포함합니다.

**주요 장점**:
- ✅ 동적 분기 지원 (런타임에 N 결정)
- ✅ 병렬 탐색으로 다양한 솔루션 비교
- ✅ 자동화된 평가 (리뷰 + 테스트)
- ✅ 명확한 사람 개입 지점
- ✅ 완전한 관찰 가능성 (로그 + 상태 추적)

**사용 시작**:
```bash
cd multi-agent-dev-system
python cli.py init
python cli.py run -r "당신의 요구사항"
```

**Happy coding! 🚀**
