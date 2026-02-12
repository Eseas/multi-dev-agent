# 🤖 Multi-Agent Development System

**하나의 기획서, N개의 AI 구현, 최적의 선택**

인간-AI 협업 기획과 AI 자동 구현을 결합한 다중 에이전트 개발 시스템입니다.
여러 구현 방향을 병렬로 탐색하고, AI가 자동으로 리뷰/테스트/비교하여 최적의 솔루션을 찾습니다.

---

## 🎯 핵심 개념

```
당신의 아이디어 (planning-spec.md)
    ↓
🔍 프로젝트 자동 분석 (Python, 1-2초, AI 비용 없음)
    ↓
🤖 Phase 1-6: AI 에이전트 자동 실행
    ├─ Architect: 기획서 → N개 구현 설계
    ├─ Implementer x N: 병렬 구현 (git worktree 격리)
    ├─ Reviewer + Tester x N: 병렬 리뷰/테스트
    ├─ Comparator: N개 비교 분석 (N≥2)
    └─ Human: 최종 선택 (N≥2)
    ↓
✅ 선택된 브랜치 통합
```

### 왜 이 시스템을 사용하나요?

- **적응형 탐색**: 문제 복잡도에 맞춰 1~3가지 방법 자동 조정
- **하이브리드 모드**: 기본 N=2로 일상 작업도 효율적
- **프로젝트 사전 분석**: Claude가 대규모 프로젝트를 탐색하는 시간 대폭 단축
- **객관적 비교**: AI가 각 방법의 장단점을 리뷰, 테스트, 비교
- **위험 감소**: 한 가지 방법에 올인하지 않고 대안 확보
- **학습 효과**: 다양한 접근법을 보며 시야 확장

---

## 🚀 빠른 시작

### 1. 설치

```bash
# 의존성 설치
pip3 install -r requirements.txt

# 또는 패키지로 설치 (권장)
pip3 install -e .
```

**사전 요구사항**:
- Python 3.8+
- Git
- **Claude Code CLI** (시스템 PATH에 `claude` 명령)

### 2. 초기화

```bash
# 설정 파일 생성
python3 cli.py init

# config.yaml 편집: project.target_repo 설정 필수!
```

### 3. 기획서 작성

`planning-spec.md` 파일을 작성합니다. 기획서는 Claude Code와 대화하며 작성하거나, 직접 작성할 수 있습니다.

**필수 요소**:
- `## 구현 방법` 섹션
- 탐색할 방법 개수 명시 (예: "탐색할 방법 개수: 2개")
- 각 방법의 차별점 명확화

**예시**:
```markdown
# 기획서: 관리자 로그인 시스템

## 요구사항
- Spring Security 기반 ID/PW 인증
- BCrypt 비밀번호 암호화
- JWT 토큰 발급

## 구현 방법

탐색할 방법 개수: 1개

### 방법 1: Spring Security + JWT
- **핵심 아이디어**: SecurityFilterChain에서 JWT 검증
- **기술 스택**: Spring Security, JJWT, BCrypt
...
```

### 4. 파이프라인 실행

```bash
python3 cli.py run -s planning-spec.md -v
```

**자동 진행**:
1. 기획서 검증
2. Git clone/fetch (타겟 프로젝트)
3. **프로젝트 분석** (~1-2초, Python 기반)
   - 프로젝트 구조, 모듈, 기술 스택 분석
   - `.project-profile.json` 캐싱
   - 기획서 관련 모듈만 컨텍스트 생성
4. Phase 1 (Architect) - 프로젝트 컨텍스트 제공으로 탐색 시간 단축
5. **체크포인트** - 사용자 승인 대기
6. Phase 2~6 자동 실행

### 5. 체크포인트 승인

다른 터미널에서:
```bash
# 전체 승인
python3 cli.py approve <task-id>

# N≥2: 특정 approach만 승인
python3 cli.py approve <task-id> --approaches 1,2
```

### 6. 결과 확인 (N≥2)

```bash
# 비교 결과 확인
python3 cli.py status <task-id>

# 비교 보고서 읽기
cat workspace/tasks/<task-id>/comparator/comparison.md

# 구현 선택
python3 cli.py select <task-id> <impl-id>
```

### 7. 통합

```bash
cd <타겟-프로젝트>
git merge <task-id>/impl-<N>
```

---

## 📁 프로젝트 구조

```
multi-agent-dev-system/
├── cli.py                         # CLI 진입점
├── config.yaml                    # 설정 파일 (git ignore됨)
├── requirements.txt               # Python 의존성
├── setup.py                       # 패키지 설정
│
├── orchestrator/                  # 핵심 오케스트레이터
│   ├── main.py                    #   Orchestrator 클래스
│   ├── executor.py                #   ClaudeExecutor (Claude Code 실행)
│   ├── watcher.py                 #   파일 감시/대기
│   ├── agents/                    #   AI 에이전트
│   │   ├── architect.py           #     Phase 1: 구현 설계
│   │   ├── implementer.py         #     Phase 2: 코드 구현
│   │   ├── reviewer.py            #     Phase 3: 코드 리뷰
│   │   ├── tester.py              #     Phase 3: 테스트
│   │   └── comparator.py          #     Phase 4: 비교 분석
│   └── utils/                     #   유틸리티
│       ├── project_analyzer.py    #     🆕 프로젝트 사전 분석
│       ├── git_manager.py         #     Git clone/worktree
│       ├── notifier.py            #     시스템 알림
│       ├── spec_parser.py         #     기획서 파싱
│       └── spec_validator.py      #     기획서 검증
│
├── prompts/                       # 에이전트 프롬프트 템플릿
│   ├── architect.md
│   ├── implementer.md
│   ├── reviewer.md
│   ├── tester.md
│   └── comparator.md
│
└── workspace/                     # 런타임 워크스페이스
    ├── tasks/                     #   실행 중/완료 태스크
    │   └── task-YYYYMMDD-HHMMSS/  #     각 태스크 디렉토리
    │       ├── planning-spec.md   #       기획서 복사본
    │       ├── manifest.json      #       태스크 상태
    │       ├── full-conversation.txt  #   🆕 전체 대화 내역 (모든 Phase 통합)
    │       ├── project-profile.json  #    🆕 프로젝트 분석 결과
    │       ├── architect/         #       Architect 출력
    │       │   └── conversation.txt  #     🆕 대화 내역 (Phase별)
    │       └── implementations/   #       구현들 (git worktree)
    │           ├── impl-1/
    │           │   └── conversation.txt  # 🆕 대화 내역 (Phase별)
    │           ├── impl-2/
    │           └── impl-3/
    └── .cache/                    #   Git clone 캐시
        └── <project-name>/
            ├── .git/
            ├── .project-profile.json  # 🆕 프로젝트 프로필 캐시
            └── (소스 파일들)
```

---

## 🎨 파이프라인 흐름

### N=1 (단일 구현)

```
기획서 → 검증 → Git clone/fetch → 프로젝트 분석
    → Phase 1: Architect
    → [Checkpoint]
    → Phase 2: Implementer (1개)
    → Phase 3: Reviewer + Tester
    → Phase 6: 통합 알림
```

### N≥2 (복수 구현)

```
기획서 → 검증 → Git clone/fetch → 프로젝트 분석
    → Phase 1: Architect (N개 설계)
    → [Checkpoint]
    → Phase 2: Implementer x N (병렬)
    → Phase 3: Reviewer + Tester x N (병렬)
    → Phase 4: Comparator (비교 분석)
    → Phase 5: Human Selection (선택)
    → Phase 6: 통합 알림
```

---

## 🆕 프로젝트 사전 분석 (ProjectAnalyzer)

Git clone 후, Phase 1 전에 자동으로 실행되는 Python 기반 분석 엔진입니다.

### 목적
Claude가 대규모 프로젝트(수백~수천 파일)를 처음부터 탐색하는 시간을 대폭 단축합니다.

### 동작 방식

1. **프로젝트 타입 감지**: Gradle, Maven, npm, Python 등
2. **모듈 구조 분석**: 각 모듈의 소스 루트, 주요 클래스 스캔
3. **아키텍처 패턴 감지**: 헥사고날, 레이어드 등
4. **프로필 캐싱**: `.project-profile.json` (commit SHA 기반)
5. **타겟 컨텍스트 생성**: 기획서 키워드와 매칭되는 모듈만 추출

### 2-tier 컨텍스트

- **정적 프로필** (캐시됨): 프로젝트 전체 개요, 모듈 목록, 기술 스택
- **동적 타겟 컨텍스트** (매번 생성): 기획서 관련 모듈의 실제 코드

### 성능 개선

| Phase | Before | After | 개선 |
|-------|--------|-------|------|
| Architect | ~252s | ~60-90s | **63~76% 단축** |
| Implementer | ~300s+ | ~120-180s | **40~60% 단축** |

**AI 비용 절감**: Python 분석은 무료, Claude는 필요한 부분만 탐색

---

## 📚 CLI 명령어

| 명령어 | 설명 |
|--------|------|
| `init` | config.yaml 생성 |
| `run -s <spec>` | 파이프라인 실행 |
| `approve <task-id>` | 체크포인트 승인 |
| `select <task-id> <impl-id>` | 구현 선택 (N≥2) |
| `revise <task-id> -f "피드백"` | 수정 요청 |
| `abort <task-id>` | 태스크 중단 |
| `status [task-id]` | 상태 확인 |
| `watch` | 감시 모드 |

자세한 사용법은 [USAGE.md](USAGE.md)를 참고하세요.

---

## ⚙️ 설정 (config.yaml)

```yaml
workspace:
  root: ./workspace

project:
  target_repo: "https://github.com/your-org/your-project.git"  # 필수!
  default_branch: "main"
  github_token: ""  # private repo용

execution:
  timeout: 600      # Claude 실행 타임아웃 (초)
  max_retries: 3

pipeline:
  checkpoint_phase1: true
  num_approaches: 1  # 기본 구현 개수 (기획서에서 덮어쓸 수 있음)

validation:
  enabled: true
  strict_mode: false

notifications:
  enabled: true
  sound: true
```

---

## 🎓 사용 팁

### 좋은 기획서 작성하기

**✅ DO**:
- "탐색할 방법 개수: N개" 명확히 명시
- 각 방법의 차별점을 명확히 (기술 스택, 아키텍처 등)
- 성공 기준을 측정 가능하게
- 구체적인 모듈명/패키지명 언급 (프로젝트 분석에 도움)

**❌ DON'T**:
- "여러 방법이 있어요" (개수 불명확)
- "좋은 성능" (측정 불가)
- "적절한 기술" (구체성 부족)
- "시스템의 인증" (모호, 모든 모듈 포함)

### N(구현 개수) 선택 가이드

- **N=1**: 단순하고 명확한 작업
- **N=2** (기본값, 권장): 일반적인 개발 작업, 대안 하나 확보
- **N=3**: 중요한 아키텍처 결정, 여러 선택지 비교

---

## 🔧 고급 기능

### Git Worktree 격리

각 구현은 독립된 git worktree + 독립 브랜치에서 실행됩니다:
- 모든 구현이 같은 원본 코드에서 시작
- 구현 간 간섭 없음
- 선택 후 `git merge <branch>`로 통합

### 스마트 재시도

`executor.py`는 다음 상황을 감지하여 무의미한 재시도를 방지합니다:
- API rate limit 감지 → 즉시 중단
- 연속 2회 timeout → 중단 (설정 검토 메시지 출력)

### 시스템 알림

macOS/Linux/Windows 네이티브 알림 지원:
- Phase 시작/완료
- 체크포인트 대기
- 오류 발생

---

## 📖 문서

- **[USAGE.md](USAGE.md)** - 상세 사용 가이드 (필독!)
- **[CLAUDE.md](CLAUDE.md)** - Claude Code 설정 및 가이드라인
- **[multi-agent-dev-system-implementation-guide.md](multi-agent-dev-system-implementation-guide.md)** - 구현 가이드
- **[multi-agent-dev-system-proposal.md](multi-agent-dev-system-proposal.md)** - 기술 제안서

---

## 🙋 FAQ

### Q: 왜 여러 구현을 만들어야 하나요?
A: 하나의 "정답"은 없습니다. 각 방법은 트레이드오프가 있고, 여러 옵션을 비교해보면 더 나은 결정을 내릴 수 있습니다.

### Q: 비용이 많이 들지 않나요?
A: Claude API 비용은 발생하지만, 프로젝트 사전 분석으로 실행 시간을 40~60% 단축했습니다. 잘못된 선택으로 인한 리팩토링 비용보다 저렴합니다.

### Q: 프로젝트 사전 분석은 어떻게 동작하나요?
A: Python으로 build 파일(build.gradle, pom.xml, package.json 등)을 파싱하고, 소스 디렉토리를 스캔하여 주요 클래스를 추출합니다. AI를 사용하지 않으므로 비용이 들지 않고 1-2초 내에 완료됩니다.

### Q: Claude Code 없이 사용 가능한가요?
A: 아니요. 이 시스템은 Claude Code CLI를 기반으로 설계되었습니다.

---

## 🤝 기여

이 프로젝트는 실험적 프로토타입입니다. 제안 및 피드백 환영합니다!

---

## 📝 라이선스

MIT License

---

**Happy Multi-Agent Development! 🚀**
