# 🤖 Multi-Agent Development System

**인간-AI 협업 기획**과 **AI 자동 구현**을 결합한 다중 에이전트 개발 시스템입니다.

하나의 아이디어를 여러 방법으로 구현하고, AI가 자동으로 리뷰, 테스트, 비교하여 최적의 솔루션을 찾아드립니다.

---

## 🎯 핵심 개념

```
당신의 아이디어
    ↓
📝 Phase 0: 기획 (사람 + Claude Code 대화)
    ↓
🤖 Phase 1-6: 자동 구현 (AI 에이전트들)
    ↓        ↑
    └─ N = 1~3개 (적응형 조정)
    ↓
✅ 최적의 구현 선택
```

### 왜 이 시스템을 사용하나요?

- **적응형 탐색**: 문제 복잡도에 맞춰 1~3가지 방법 자동 조정
- **하이브리드 모드**: 기본 N=2로 일상 작업도 빠르게
- **객관적 비교**: AI가 각 방법의 장단점을 리뷰, 테스트, 비교
- **위험 감소**: 한 가지 방법에 올인하지 않고 대안 확보
- **학습 효과**: 다양한 접근법을 보며 시야 확장

---

## 🚀 빠른 시작

### 1. 설치

```bash
# 의존성 설치
pip install watchdog pyyaml aiohttp

# Claude Code CLI가 이미 설치되어 있어야 합니다
# https://claude.ai/claude-code
```

### 2. 프로젝트 초기화

```bash
cd /path/to/mine
python -m orchestrator.main init
```

### 3. Orchestrator 시작 (백그라운드)

```bash
python -m orchestrator.main watch --daemon
```

### 4. 새 기획 시작

```bash
# 새 기획 생성
python -m orchestrator.main plan create "user-authentication"

# workspace/planning/in-progress/user-authentication/ 폴더로 이동
cd workspace/planning/in-progress/user-authentication

# Claude Code 시작
claude
```

### 5. Claude Code와 대화하며 기획서 작성

```
You: "사용자 인증 기능을 추가하고 싶어요. JWT와 세션 방식 중 어떤 게 좋을까요?"

Claude: "두 방식을 모두 탐색해보시겠어요? 다음 3가지 방법을 제안합니다:
1. JWT 토큰 기반
2. 세션 기반
3. OAuth2 + JWT 하이브리드
..."

You: "좋아요! 3개 방법으로 진행해주세요."

Claude: "planning-spec.md를 작성했습니다. 확인해주세요."
```

### 6. 기획 완료

```bash
# 기획서가 완성되면 completed 폴더로 이동
python -m orchestrator.main plan complete "user-authentication"

# 또는 수동으로:
mv planning-spec.md ../../completed/user-authentication-planning-spec.md
```

### 7. 자동 실행 및 알림 확인

이제 AI 에이전트들이 자동으로:
- ✅ 기획서 분석 (Architect)
- ✅ 3가지 방법 구현 (Implementers)
- ✅ 각 구현 리뷰 (Reviewer)
- ✅ 각 구현 테스트 (Tester)
- ✅ 모든 구현 비교 (Comparator)

각 단계마다 알림이 콘솔에 표시됩니다:

```
✅ [SUCCESS] Phase 1 완료
   아키텍처 분석 완료: 3개 구현 방향 도출

✅ [SUCCESS] Phase 2 완료
   모든 구현 완료: 3개

...
```

### 8. 결과 확인 및 선택

```bash
# 비교 보고서 확인
cat workspace/tasks/task-20250210-153045/submit-final/comparison-report.md

# 선택 및 통합
python -m orchestrator.main approve task-20250210-153045 --select impl-1
```

---

## 📁 프로젝트 구조

```
mine/
├── README.md                    # 이 파일
├── CLAUDE.md                    # Claude Code 설정 (자동 로드됨)
│
├── orchestrator/                # 시스템 코어 (구현 예정)
│   ├── main.py
│   ├── agents/
│   ├── watcher.py
│   ├── executor.py
│   ├── notifier.py
│   └── utils/
│
├── workspace/
│   ├── planning/
│   │   ├── in-progress/         # 📝 여기서 기획서 작성
│   │   └── completed/           # ✅ 완성된 기획서 (자동 실행)
│   │
│   ├── tasks/                   # 실행 중/완료된 작업들
│   │   └── task-20250210-153045/
│   │       ├── planning-spec.md
│   │       ├── approaches.json
│   │       ├── implementations/
│   │       │   ├── impl-1/      # JWT 구현
│   │       │   ├── impl-2/      # 세션 구현
│   │       │   └── impl-3/      # 하이브리드 구현
│   │       ├── submit-stage-2/
│   │       │   ├── impl-1-review.md
│   │       │   ├── impl-1-test-results.md
│   │       │   └── ...
│   │       └── submit-final/
│   │           └── comparison-report.md  # 📊 최종 비교 보고서
│   │
│   └── templates/
│       └── planning-template.md  # 기획서 템플릿
│
├── prompts/                     # 에이전트 프롬프트
│   ├── reviewer.md
│   ├── tester.md
│   └── comparator.md
│
└── config.yaml                  # 설정 파일 (생성 예정)
```

---

## 🎨 작업 흐름 (워크플로우)

### Phase 0: 기획 단계 (사람 주도)

**위치**: `workspace/planning/in-progress/[task-name]/`

1. Claude Code와 대화
2. 요구사항 명확화
3. 구현 방법 N개 결정
4. `planning-spec.md` 작성
5. `completed/` 폴더로 이동

**핵심**: "탐색할 방법 개수: 3개" 명시 필수!

---

### Phase 1-6: 구현 단계 (AI 자동)

#### Phase 1: Architecture Analysis
- Architect Agent가 기획서 분석
- N개 방법을 구체적 구현 계획으로 발전

#### Phase 2: Implementation
- N개 Implementer Agent가 병렬로 구현
- 각각 독립된 환경에서 실행

#### Phase 3: Review & Testing
- Reviewer Agent: 코드 리뷰
- Tester Agent: 테스트 작성 및 실행

#### Phase 4: Comparison
- Comparator Agent: 모든 결과 종합 비교
- 시나리오별 추천 제시

#### Phase 5: Human Approval
- 비교 보고서 확인
- 최적의 구현 선택

#### Phase 6: Integration
- Integrator Agent: 선택된 구현 통합
- 미사용 구현 아카이브

---

## 📋 CLI 명령어

### 시스템 관리

```bash
# 초기화
python -m orchestrator.main init

# 기획 폴더 감시 시작
python -m orchestrator.main watch

# 백그라운드 실행
python -m orchestrator.main watch --daemon
```

### 기획 관리

```bash
# 새 기획 생성
python -m orchestrator.main plan create "feature-name"

# 기획 완료 (completed로 이동)
python -m orchestrator.main plan complete "feature-name"
```

### 작업 관리

```bash
# 작업 목록 보기
python -m orchestrator.main list

# 특정 작업 상태 확인
python -m orchestrator.main status task-20250210-153045

# 작업 승인 및 통합
python -m orchestrator.main approve task-20250210-153045 --select impl-2

# 작업 중단
python -m orchestrator.main abort task-20250210-153045
```

### 로그 확인

```bash
# 알림 로그
tail -f workspace/notifications.log

# 작업 타임라인
tail -f workspace/tasks/task-*/timeline.log
```

---

## ⚙️ 설정

### config.yaml (예시)

```yaml
workspace: "./workspace"
template_path: "./workspace/templates/base-env"
timeout: 300
max_retries: 2

planning:
  watch_enabled: true
  in_progress_dir: "./workspace/planning/in-progress"
  completed_dir: "./workspace/planning/completed"

pipeline:
  num_approaches: 2            # 기본값 (하이브리드 모드)
  adaptive_mode: true          # 적응형 파이프라인 활성화
  complexity_threshold:
    simple: 1                  # 단순 작업: N=1
    medium: 2                  # 일반 작업: N=2 (기본값)
    complex: 3                 # 복잡한 작업: N=3

notifications:
  enabled: true
  on_failure: true
  on_completion: true
  log_file: "./workspace/notifications.log"
  # webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

**적응형 파이프라인**: `adaptive_mode: true`로 설정하면 시스템이 자동으로 복잡도를 판단하여 N을 조정합니다.
**하이브리드 모드**: 기본값 N=2로 일상적인 작업에도 빠르게 적용 가능합니다.

---

## 🎓 사용 팁

### 좋은 기획서 작성하기

**✅ DO**:
- "탐색할 방법 개수: N개" 명확히 명시
- 각 방법의 차별점을 명확히
- 성공 기준을 측정 가능하게
- 제약사항을 구체적으로

**❌ DON'T**:
- "여러 방법이 있어요" (개수 불명확)
- "좋은 성능" (측정 불가)
- "적절한 기술" (구체성 부족)

### Phase 0에서 Claude Code 활용

```
# 좋은 질문 예시
"JWT와 세션 방식의 장단점을 비교해주세요"
"각 방법의 보안 고려사항은 무엇인가요?"
"성능은 어떻게 다를까요?"

# 나쁜 질문 예시
"코드 작성해줘" (아직 기획 단계!)
"어떤 게 좋아요?" (먼저 옵션을 탐색해야 함)
```

### 결과 해석하기

비교 보고서를 읽을 때:
1. **종합 점수**보다 **시나리오별 추천** 중요
2. **절대적 우열**이 아닌 **상황별 적합성** 파악
3. **트레이드오프** 이해하고 선택

---

## 🔧 고급 기능

### 알림 연동

Slack, Discord, Teams 등과 연동 가능:

```yaml
# config.yaml
notifications:
  webhook_url: "https://hooks.slack.com/services/YOUR/WEBHOOK"
```

### 커스텀 프롬프트

각 에이전트의 프롬프트를 수정하여 동작 커스터마이징:

```yaml
# config.yaml
agents:
  reviewer:
    prompt_path: "./prompts/custom-reviewer.md"
```

### 환경 템플릿

프로젝트별 base 환경 설정:

```
workspace/templates/base-env/
├── package.json
├── tsconfig.json
├── .env.example
└── src/
```

---

## 📚 문서

- [CLAUDE.md](CLAUDE.md) - Claude Code 설정 및 가이드라인
- [multi-agent-dev-system-proposal.md](multi-agent-dev-system-proposal.md) - 기술 제안서
- [planning-template.md](workspace/templates/planning-template.md) - 기획서 템플릿

---

## 🤝 기여

이 프로젝트는 실험적 프로토타입입니다. 제안 및 피드백 환영합니다!

---

## 📝 라이선스

MIT License

---

## 🙋 FAQ

### Q: 왜 여러 구현을 만들어야 하나요?

A: 하나의 "정답"은 없습니다. 각 방법은 트레이드오프가 있고, 상황에 따라 최선이 다릅니다. 여러 옵션을 비교해보면 더 나은 결정을 내릴 수 있습니다.

### Q: 비용이 많이 들지 않나요?

A: Claude Code API 비용은 발생합니다. 하지만:
- 중요한 결정일수록 여러 옵션 탐색의 가치가 큼
- 잘못된 선택으로 인한 리팩토링 비용보다 저렴
- 학습 효과까지 고려하면 투자 가치 충분

### Q: 모든 프로젝트에 사용하나요?

A: 아니요. 다음 경우에 적합합니다:
- ✅ 중요한 아키텍처 결정
- ✅ 여러 방법이 존재하는 문제
- ✅ 올바른 선택이 중요한 경우

단순한 기능은 직접 구현하는 게 빠릅니다.

### Q: Claude Code 없이 사용 가능한가요?

A: 아니요. 이 시스템은 Claude Code CLI를 기반으로 설계되었습니다.

### Q: 몇 개 방법을 탐색하는 게 좋나요?

A: **적응형 파이프라인**이 자동으로 조정합니다 (권장):
- **N=1**: 단순하고 명확한 작업
- **N=2** (기본값): 일반적인 개발 작업
- **N=3+**: 중요한 아키텍처 결정

수동으로 지정하려면:
- 2개: 빠르면서도 대안 확보
- 3개: 다양한 비교 (중요 결정)
- 4-5개: 깊은 탐색 (시간 증가)

---

## 🎉 시작하기

```bash
# 1. 설치
pip install watchdog pyyaml aiohttp

# 2. 초기화
python -m orchestrator.main init

# 3. 첫 기획 시작!
python -m orchestrator.main plan create "my-first-feature"
cd workspace/planning/in-progress/my-first-feature
claude
```

**Happy Multi-Agent Development! 🚀**
