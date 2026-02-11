# 구현 과제 및 개선 제안

> **작성일**: 2025-02-11
> **대상**: 다중 AI 에이전트 기반 개발 시스템 제안서 (v3 - git worktree 기반)
> **목적**: 기획서를 구현 관점에서 분석하고, 실제 구현 시 어려운 부분과 개선이 필요한 부분을 식별

---

## 1. 핵심 발견사항 요약

### 해결 완료된 문제
- ~~프로젝트 타입 감지/명시~~ → 제거됨. 타겟 프로젝트를 clone하므로 기술 스택은 코드에 이미 존재
- ~~환경 격리 (symlink)~~ → git worktree 기반으로 전환. 각 impl이 독립 브랜치와 작업 디렉토리 보유
- ~~Phase 6 통합 방식 불명확~~ → 사용자가 git merge/cherry-pick으로 직접 수행하도록 확정
- ~~기획서 유효성 검증 부재~~ → Spec Validation 단계 추가됨 (제안서 3.1.1절)
- ~~YAML 프론트매터 파싱~~ → 제거됨. 기획서는 순수 마크다운만 사용

### 남아있는 구현 과제

**난이도: 높음**
1. **Claude Code CLI 통합 방식 불명확**: 에이전트를 실제로 어떻게 실행할지 구체적이지 않음
2. **병렬 실행 메커니즘**: N개의 독립적인 Claude Code 세션을 관리하는 방법이 복잡함
3. **개별 승인/수정/반려 시 비동기 상태 관리**: approach별로 서로 다른 Phase에 있을 때의 동기화

**난이도: 중간**
4. **체크포인트 일시정지 메커니즘**: "자동 일시정지"의 구체적 구현 방법
5. **기획서 파싱 신뢰성**: 순수 마크다운 기획서에서 구현 방법 개수(N), 기술 스택 등을 정확히 추출
6. **git worktree 수명주기 관리**: clone 시점, worktree 생성/정리, 디스크 공간 관리

**난이도: 낮음**
7. **비용 추적 메커니즘**: API 비용 실시간 추적 및 예산 제한
8. **JSON 스키마 정의**: approaches.json, manifest.json 등의 구체적 스키마
9. **에러 복구 전략**: 재시도/타임아웃/부분 성공의 세부 구현

---

## 2. 구현 난이도 높음

### 2.1 Claude Code CLI 통합

#### 문제
기획서에서는 "Claude Code CLI를 사용한다"고만 명시되어 있으나, 에이전트를 프로그래밍 방식으로 실행하는 구체적 방법이 없다.

#### 핵심 질문
- Claude Code를 비대화형(non-interactive)으로 실행할 수 있는가?
- 프롬프트를 파일이나 stdin으로 전달할 수 있는가?
- 실행 결과(생성된 파일, 출력)를 어떻게 캡처하는가?
- 하나의 머신에서 여러 Claude Code 세션을 동시에 실행할 수 있는가?

#### 가능한 접근법

**접근법 A: Claude Code CLI 서브프로세스**
```
장점: Claude Code의 파일 시스템 접근, 도구 사용 기능 그대로 활용
단점: CLI가 비대화형 모드를 지원하는지 불확실
리스크: 높음 (CLI 스펙에 의존)
```

**접근법 B: Anthropic API + 커스텀 도구**
```
장점: 완전한 제어, 안정적
단점: Claude Code의 파일 조작, 코드 실행 기능을 직접 구현해야 함
리스크: 중간 (구현량 많음)
```

**접근법 C: Claude Code SDK (Agent SDK)**
```
장점: 프로그래밍 방식으로 설계됨, 도구 사용 내장
단점: SDK 성숙도에 의존
리스크: 중간 (SDK 변경 가능성)
```

#### 결론
구현 전에 **Claude Code CLI의 비대화형 실행 가능 여부를 먼저 조사**해야 한다. 이것이 전체 아키텍처를 결정하는 핵심 변수다.

---

### 2.2 병렬 실행 메커니즘

#### 문제
N개의 구현을 병렬로 실행한다고 했으나, 실제 구현 시 고려사항이 많다.

#### 핵심 도전 과제
1. **리소스 제한**: API rate limit, 동시 세션 수 제한
2. **진행 상황 모니터링**: 각 세션의 실시간 상태 추적
3. **부분 실패 처리**: 일부만 실패했을 때의 처리 흐름
4. **타임아웃 관리**: 세션별 독립적 타임아웃

#### 권장 구현 전략
```
MVP (V1): 순차 실행
  - N개를 하나씩 순서대로 실행
  - 구현 난이도: 낮음
  - 단점: N에 비례하여 시간 증가

V2: 제한된 병렬 실행
  - asyncio + semaphore로 동시 실행 수 제한 (예: 최대 3개)
  - 구현 난이도: 중간
  - 장점: 시간 절약 + 리소스 안전

V3: 완전 병렬 + 모니터링
  - 실시간 진행 상황 대시보드
  - 구현 난이도: 높음
```

---

### 2.3 비동기 상태 관리 (개별 승인/수정/반려)

#### 문제
기획서 2.2절에서 개별 승인/수정/반려가 가능하다고 했으나, 이로 인해 **approach마다 서로 다른 Phase에 있는 상황**이 발생한다.

#### 복잡한 시나리오
```
초기: N=3, 모두 Phase 1 완료 (pending)

시점 T1: 사용자가 Approach 1 승인, Approach 2 수정 요청, Approach 3 반려
  - Approach 1: Phase 2 실행 시작
  - Approach 2: Phase 1 재실행 시작
  - Approach 3: 제거

시점 T2: Approach 1이 Phase 2 완료, Approach 2가 Phase 1 재실행 완료
  - Approach 1: Phase 3 (리뷰/테스트)로 진행?
  - Approach 2: 다시 사용자 확인 필요 (두 번째 체크포인트)

시점 T3: Approach 2 승인
  - Approach 2: Phase 2 실행 시작
  - 이때 Approach 1은 이미 Phase 3 진행 중...

문제: Phase 4 (비교)를 하려면 모든 approach가 Phase 3까지 완료되어야 함.
      Approach 1은 이미 끝났는데 Approach 2를 기다려야 하는 상황.
```

#### 해결 방안

**방안 1: 동기 합류점 (Sync Point)**
```
승인된 approach들이 Phase 2-3를 진행하되,
Phase 4 (비교)에서 모든 approach가 도착할 때까지 대기.

장점: 구현 단순
단점: 먼저 끝난 approach가 대기해야 함 (자원 낭비 아님, 결과만 보관)
```

**방안 2: 점진적 비교 (Incremental Comparison)**
```
모든 approach가 끝날 때까지 기다리지 않고,
도착하는 순서대로 비교 보고서를 점진적으로 업데이트.

장점: 사용자에게 빠른 피드백
단점: 구현 복잡도 높음, 비교 보고서가 계속 변함
```

**권장**: 방안 1 (동기 합류점). MVP에서는 이 방식이 가장 간단하고 안정적이다.

---

## 3. 구현 난이도 중간

### 3.1 체크포인트 일시정지 메커니즘

#### 문제
기획서 2.2절에서 "시스템이 자동으로 일시정지"한다고 했으나, 구체적 구현 방식이 명시되지 않았다.

#### 구현 방식 비교

| 방식 | 구현 난이도 | 반응 속도 | CPU 효율 | 권장 단계 |
|------|-----------|----------|---------|----------|
| 파일 폴링 | 낮음 | 5~10초 | 낮음 | MVP |
| watchdog (파일 감시) | 중간 | 즉시 | 높음 | V2 |
| Unix socket + CLI | 높음 | 즉시 | 높음 | V3 |

#### MVP 구현 (파일 폴링)
```
Phase 1 완료 → approaches.json 생성 + checkpoint-status.json("awaiting")
                     ↓
Orchestrator: checkpoint-decision.json 파일 존재 여부를 5초마다 확인
                     ↓
사용자: CLI 명령어 실행 → checkpoint-decision.json 생성
                     ↓
Orchestrator: 파일 감지 → decision 읽기 → Phase 2 진행
```

#### 기획서에 추가 권장
현재 기획서에는 "자동으로 일시정지"만 있고 **어떤 메커니즘으로 정지하는지**가 없다. 구현 방식을 명시하거나, "구현 단계에서 결정"이라고 표기하는 것을 권장한다.

---

### 3.2 기획서 파싱 신뢰성

#### 문제
기획서는 순수 마크다운으로 작성되며, YAML 프론트매터가 없다. 따라서 구현 방법 개수(N), 기술 스택 등의 정보를 **마크다운 본문에서 추출**해야 한다.

#### 잠재적 이슈

1. **N 추출 불확실성**: `## 구현 방법 (2개 비교)` 헤딩에서 숫자 추출 vs `### 방법 N` 개수로 카운트 → 불일치 가능
2. **자유 형식 마크다운**: 사용자마다 기획서 형식이 다를 수 있음
   - `## 구현 방법` vs `## Implementation` vs `## 구현 전략`
   - `### 방법 1` vs `### Approach 1` vs `### 1. JWT`
3. **N=1일 때 구조적 모호성**: N=1이면 `### 방법 1` 헤딩 없이 평문으로 작성될 수 있음

#### 해결 방안

**파싱 전략**:
```
1차: 정규식으로 헤딩 매칭
     "## 구현 방법" → 섹션 위치 확보
     "(N개 비교)" → N 추출
     "### 방법" 카운트 → N 크로스체크

2차: 헤딩 매칭 실패 시 Fallback
     "### 방법" 패턴이 없으면 → N=1로 간주
     "구현 방법" 헤딩이 없으면 → Spec Validation에서 차단됨

3차: Spec Validation이 사전 검증
     헤딩 존재 여부, N 일관성은 이미 검증 완료
     파서는 검증된 기획서만 받으므로 신뢰도 상승
```

**Spec Validation과의 관계**: Spec Validation(3.1.1절)이 사전 검증을 수행하므로, 파서는 **검증을 통과한 기획서만** 처리하면 된다. 이로 인해 파싱 실패 확률이 크게 감소한다.

---

### 3.3 git worktree 수명주기 관리

#### 문제
기획서 3.3절에서 git worktree 기반 작업 공간을 명시했으나, 실제 운영에서 다음 이슈가 있을 수 있다.

#### 잠재적 이슈

**1. 최초 clone 시점과 비용**
- 타겟 프로젝트가 클 경우 (수 GB) clone에 시간이 오래 걸림
- `--depth 1` (shallow clone)으로 해결 가능하나, worktree와의 호환성 확인 필요
- 대안: `--filter=blob:none` (blobless clone)으로 필요한 파일만 점진적 다운로드

**2. worktree 정리 시점**
- 작업 완료 후 worktree를 자동 정리할지, 사용자에게 맡길지 미정
- 현재 기획서에서는 "사용자가 선택적으로 정리"라고만 되어 있음
- 쌓이면 디스크 공간 문제 → 자동 정리 정책 필요

**3. 의존성 설치 중복**
- 각 worktree에서 `npm install`, `pip install` 등을 독립 실행해야 함
- N=3이면 동일 패키지를 3번 설치 → 시간/디스크 낭비
- 대안: 패키지 캐시 공유 (`npm cache`, `pip cache`)

**4. 네트워크 의존성**
- `git clone`은 네트워크가 필요
- 오프라인 환경에서는 동작 불가
- 대안: 이미 로컬에 clone된 저장소를 `--reference`로 활용

**5. GitHub 인증 (비공개 저장소)**
- 공개 저장소: 인증 없이 clone 가능
- 비공개 저장소: SSH key 또는 GitHub Personal Access Token 필요
- config.yaml에 인증 방식 설정이 없음

#### 기획서에 추가 권장

```yaml
# config.yaml에 추가 권장
project:
  target_repo: "https://github.com/user/my-web-app"
  default_branch: "main"
  clone_strategy: "blobless"        # full, shallow, blobless
  auth_method: "ssh"                # ssh, token, none (공개 저장소)

workspace:
  auto_cleanup_worktrees: true      # 작업 완료 후 worktree 자동 정리
  cleanup_delay_hours: 24           # 정리 전 대기 시간
  cache_packages: true              # 패키지 캐시 공유
```

---

## 4. 구현 난이도 낮음

### 4.1 비용 추적 메커니즘

#### 문제
기획서 7.1절에서 "비용은 N에 비례"한다고만 언급되어 있고, 실시간 추적이나 예산 제한 메커니즘이 없다.

#### 권장 구현
- Phase별, Approach별 토큰 사용량 기록
- 작업당 예산 상한 설정 (config.yaml)
- 예산 80% 도달 시 경고 알림
- 예산 초과 시 자동 중단 + 사용자 알림

#### 기획서에 추가 권장
7.1절 비용 섹션에 다음을 추가:
```yaml
# config.yaml
execution:
  budget_usd: 10.0        # 작업당 예산 (달러)
  warn_at_percentage: 80   # 예산 경고 임계값
```

---

### 4.2 JSON 스키마 정의

#### 문제
기획서에서 `approaches.json`, `decision.json`, `manifest.json` 등의 파일을 언급하지만, 정확한 스키마가 없다.

#### 스키마가 필요한 파일들

| 파일 | 생성 시점 | 소비자 | 현재 상태 |
|------|----------|--------|----------|
| `approaches.json` | Phase 1 | Phase 2, 사용자 | 예시만 있음, 스키마 없음 |
| `checkpoint-decision.json` | 사용자 CLI | Orchestrator | 언급만 됨, 형식 미정 |
| `decision.json` | Phase 5 (사용자) | Phase 6 알림 | 간단한 예시만 있음 |
| `manifest.json` | Orchestrator | 전체 | 필드 목록 없음 |
| `timeline.log` | Orchestrator | 모니터링 | 로그 형식만 예시 |
| `work-done.md` | Phase 2 | Phase 3, 사용자 | 마크다운 템플릿 있음 |
| `review-N.md` | Phase 3 | Phase 4, 사용자 | 언급만 됨 |
| `test-N.md` | Phase 3 | Phase 4, 사용자 | 언급만 됨 |
| `comparison-report.md` | Phase 4 | Phase 5, 사용자 | 예시만 있음 |
| `validation-errors.md` | Spec Validation | 사용자 | 예시 있음 |

**참고**: Phase 6이 사용자 수동 통합으로 변경되었으므로, `integration-report.md`는 더 이상 필요하지 않다.

#### 기획서에 추가 권장
핵심 JSON 파일(`approaches.json`, `manifest.json`, `decision.json`)에 대해 정확한 스키마를 부록으로 추가하는 것을 권장한다. 이는 구현 시 에이전트 간 데이터 교환의 정확성을 보장한다.

---

### 4.3 에러 복구 전략 구체화

#### 문제
기획서 4.4절에서 "자동 재시도", "타임아웃", "부분 성공"이라고만 설명되어 있다.

#### 구체화 필요 항목

**재시도 정책**:
- 최대 몇 번? (권장: 3회)
- 재시도 간격? (권장: 지수 백오프, 2초 → 4초 → 8초)
- 어떤 에러를 재시도? (API 5xx → 재시도, 검증 실패 → 재시도 안 함)

**타임아웃**:
- Phase별 타임아웃은 다르게?
  - Spec Validation: 5초 (규칙 기반, 즉시 완료)
  - Phase 1 (Architect): 2분 (계획은 빠름)
  - Phase 2 (Implementation): 10분 (구현은 오래 걸림)
  - Phase 3 (Review/Test): 5분
  - Phase 4 (Comparison): 3분
  - Phase 6: 없음 (사용자 주도)

**부분 성공 조건** (N≥2):
- 최소 1개 approach가 성공하면 → 나머지 실패해도 다음 단계 진행
- 전부 실패 → 사용자에게 알림 + 전체 중단

**git worktree 실패**:
- clone 실패 → 네트워크 확인 안내 + 재시도
- worktree 생성 실패 → 브랜치 충돌 확인 + 정리 후 재시도

#### 기획서에 추가 권장
4.4절에 구체적인 수치(재시도 횟수, 타임아웃 시간)를 명시하거나, config.yaml에서 설정 가능하다고 표기하는 것을 권장한다.

---

## 5. 구조적 개선 제안

### 5.1 N=1 전용 경량 파이프라인

#### 현재
N=1과 N≥2 모두 동일한 파이프라인 구조를 사용하며, N=1일 때 Phase 4(비교), Phase 5(선택)를 "생략"한다. 제안서 2.4절의 워크플로우 다이어그램에서 N=1/N≥2 분기가 명시되어 있다.

#### 제안
N=1인 경우 파이프라인을 **코드 레벨에서 구조적으로 단순화**하는 것을 고려:

```
N=1 전용 파이프라인:
Phase 0 → Spec Validation → Phase 1 → [Checkpoint] → Phase 2 → Phase 3
→ Phase 6 (사용자 git 통합)

차이점:
- Phase 4, 5: 코드 레벨에서 완전히 생략 (조건문이 아닌 별도 경로)
- Phase 6: 비교 보고서 없이 바로 통합 브랜치 안내
```

**이유**: N=1이 일반적 케이스(기획서 반복 강조)이므로, 이 경로가 가장 효율적이어야 한다. 불필요한 조건 분기를 줄이면 코드가 깔끔해지고 디버깅이 쉬워진다.

---

### 5.2 Phase 3 리뷰/테스트 우선순위

#### 현재
Reviewer와 Tester가 동시(병렬)에 실행된다.

#### 제안
**Tester → Reviewer 순서**를 고려:

```
현재: Reviewer(병렬) + Tester(병렬) → 결과 합산
제안: Tester 먼저 → 테스트 결과를 Reviewer에게 전달 → Reviewer가 참고하여 리뷰
```

**이유**: Reviewer가 테스트 결과를 알면 더 정확한 리뷰가 가능하다. "테스트는 통과하지만 코드 품질이 낮다" vs "테스트도 실패하고 코드도 나쁘다"를 구분할 수 있다.

**트레이드오프**: 순차 실행이므로 시간이 더 걸린다. 하지만 리뷰 품질이 높아진다.

---

### 5.3 타겟 프로젝트 캐시 전략

#### 현재
기획서에서는 "최초 1회 clone"이라고만 되어 있으나, 캐시 관리에 대한 명시가 없다.

#### 제안
`.cache/` 디렉토리에 clone된 저장소를 관리하는 전략을 명시:

```
.cache/
└── my-web-app/          # bare 또는 mirror clone
    └── .git/            # 전체 git 객체 보관

tasks/task-001/implementations/
├── impl-1/              # worktree (from .cache)
└── impl-2/              # worktree (from .cache)

tasks/task-002/implementations/
├── impl-1/              # worktree (from .cache, 새 브랜치)
└── impl-2/              # worktree (from .cache, 새 브랜치)
```

**캐시 전략**:
- 같은 타겟 프로젝트에 대한 여러 task는 **하나의 clone을 공유**
- 새 task 시작 시 `git fetch`로 최신 코드 동기화
- `config.yaml`에서 `target_repo`가 변경되면 새로 clone

**이유**: task마다 전체 프로젝트를 매번 clone하면 시간과 디스크 낭비가 심하다.

---

## 6. 우선순위별 구현 로드맵

### MVP (V1): 핵심 경로만

**범위**:
- N=1만 지원
- 순차 실행 (병렬 X)
- 전체 승인/수정/중단만 (개별 제어 없음)
- 파일 폴링 방식 체크포인트
- 단일 타겟 프로젝트 (config.yaml 설정)

**구현 순서**:
1. Claude Code CLI 통합 방식 결정 (조사 + POC)
2. config.yaml 파서 (target_repo, default_branch)
3. git clone + worktree 관리자 (clone, worktree add/remove)
4. 기획서 파서 (순수 마크다운, N 추출)
5. Spec Validation (구조/내용/일관성 검증)
6. Orchestrator 기본 프레임워크 (config, logging, 파일 감시)
7. Phase 1: Architect Agent (프롬프트 + 실행 + approaches.json 생성)
8. Phase 1 체크포인트 (파일 폴링 + CLI 명령어)
9. Phase 2: Implementer Agent (단일 구현, git worktree 위에서 작업)
10. Phase 3: Reviewer + Tester Agent
11. Phase 6: 사용자 알림 (통합 브랜치 정보 제공)
12. 알림 시스템 (콘솔 + OS 알림)
13. 에러 처리 (재시도, 타임아웃)

**결과물**: N=1으로 GitHub 저장소의 프로젝트를 기획서 → 검증 → 구현 → 리뷰 → 테스트 → 사용자 git 통합 안내까지 수행

---

### V2: 다중 구현 + 안정성

**범위**:
- N≥2 지원
- 개별 승인/수정/반려
- 병렬 실행 (제한된)
- Phase 4 (Comparator), Phase 5 (Human Selection) 추가
- git worktree 캐시 전략 (clone 재사용)
- 패키지 캐시 공유

**구현 순서**:
1. ApproachStateMachine (상태 관리)
2. 병렬 실행 (asyncio + semaphore)
3. 다중 worktree 관리 (N개 동시 생성)
4. Phase 4: Comparator Agent
5. Phase 5: 사용자 선택 대기
6. 개별 승인/수정/반려 CLI
7. 부분 성공 처리
8. clone 캐시 전략

---

### V3: 사용성 + 확장

**범위**:
- 비용 추적 + 예산 제한
- watchdog 기반 파일 감시
- 대화형 모드 (`--interactive`)
- JSON 스키마 검증
- worktree 자동 정리 정책
- 비공개 저장소 인증 지원 (SSH, Token)

---

## 7. 결론

### 즉시 해결이 필요한 항목 (구현 시작 전)

1. **Claude Code CLI 자동화 가능 여부 조사**
   - 비대화형 실행, 프롬프트 전달, 결과 캡처
   - 불가능하면 Anthropic API + 커스텀 도구로 전환 결정

2. **approaches.json 스키마 확정**
   - 에이전트 간 데이터 교환의 기본 계약
   - Phase 1 → Phase 2 → Phase 3 → Phase 4 모두 이 파일에 의존

3. **git worktree + shallow/blobless clone 호환성 확인**
   - 대규모 프로젝트에서의 clone 전략 결정
   - worktree와 shallow clone 조합의 안정성 검증

### 기획서 업데이트 권장 사항

| 우선순위 | 항목 | 현재 상태 | 권장 조치 |
|---------|------|----------|----------|
| 높음 | JSON 스키마 | 예시만 있음 | 부록으로 정확한 스키마 추가 |
| 높음 | 체크포인트 메커니즘 | "자동 일시정지" | 구현 방식(폴링/watchdog) 명시 |
| 중간 | 에러 복구 수치 | "자동 재시도" | 구체적 수치 또는 config 설정 명시 |
| 중간 | clone 캐시 전략 | "최초 1회 clone" | 캐시 재사용, fetch 정책 명시 |
| 중간 | GitHub 인증 | 없음 | 비공개 저장소 인증 설정 추가 |
| 낮음 | 비용 추적 | 비례한다고만 | config.yaml 예산 설정 추가 |
| 낮음 | worktree 정리 | 사용자 선택 | 자동 정리 정책 명시 |

---

**문서 끝**
