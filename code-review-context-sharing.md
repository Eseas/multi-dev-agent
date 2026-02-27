# 코드 리뷰: Phase 간 컨텍스트 공유 시스템

**리뷰 대상**: 3-Tier Summary 시스템 (에이전트 간 컨텍스트 공유)
**리뷰 일시**: 2026-02-27
**변경 파일 수**: 11개 (신규 1, 수정 10)

---

## 1. 변경 요약

| 파일 | 유형 | 핵심 변경 |
|------|------|-----------|
| `orchestrator/utils/context_builder.py` | 신규 | 모든 Phase 간 컨텍스트 추출/포매팅 함수 (603줄) |
| `orchestrator/main.py` | 수정 | Phase 전환 지점에서 context_builder 호출 + 파라미터 전달 |
| `orchestrator/agents/implementer.py` | 수정 | `architect_context`, `architect_summary_path` context 수신 |
| `orchestrator/agents/reviewer.py` | 수정 | `impl_context` context 수신 |
| `orchestrator/agents/tester.py` | 수정 | `impl_context` context 수신 |
| `orchestrator/agents/comparator.py` | 수정 | `phase3_inline`, `phase3_summary_path` 수신, 리뷰 잘림 완화 |
| `prompts/implementer.md` | 수정 | Architect 분석 컨텍스트 섹션 추가 |
| `prompts/reviewer.md` | 수정 | 구현 컨텍스트 섹션 추가 |
| `prompts/tester.md` | 수정 | 구현 컨텍스트 섹션 추가 |
| `prompts/comparator.md` | 수정 | Pre-computed Metrics 섹션 추가 |
| `orchestrator/utils/__init__.py` | 수정 | context_builder 함수 7개 export 추가 |

---

## 2. 아키텍처 평가

### 2.1 설계 원칙 준수 ✅

| 원칙 | 평가 | 비고 |
|------|------|------|
| AI 비용 0 | ✅ | 모든 요약을 순수 Python(regex/문자열)으로 생성 |
| 토큰 효율성 | ✅ | Inline 합계 ~390 토큰 (N=2, 전체 파이프라인) |
| 하위 호환성 | ✅ | 모든 새 파라미터가 기본값 `''` → 기존 호출 영향 없음 |
| Graceful degradation | ✅ | 파일 부재/파싱 실패 시 fallback 텍스트 반환 |
| 기존 코드 최소 변경 | ✅ | 에이전트 run() 메서드에 2-3줄만 추가 |

### 2.2 데이터 흐름

```
Phase 1 (Architect)
   ↓ approaches.json
   ├── build_architect_inline_context()  → Tier 1 (~141 토큰)
   └── build_architect_summary_file()   → Tier 2 (파일 저장, ~454 토큰)

Phase 2 (Implementer)
   ↓ work-done.md + git change_summary
   └── build_implementer_inline_context() → Tier 1 (~18-200 토큰)

Phase 3 (Reviewer + Tester)
   ↓ review.md + test_results.json
   ├── build_review_metrics()    → 구조화된 dict
   ├── build_test_metrics()      → 구조화된 dict
   ├── build_phase3_summary()    → Tier 2 (JSON 파일)
   └── format_phase3_inline()    → Tier 1 (~35 토큰/impl)

Phase 4 (Comparator)
   ← phase3_inline + phase3_summary_path
```

---

## 3. 발견된 이슈

### 3.1 [Medium] `_generate_single_impl_summary`의 중복 import

**위치**: `orchestrator/main.py:931`

```python
def _generate_single_impl_summary(self, impl):
    from .utils.context_builder import build_review_metrics, build_test_metrics  # 중복!
```

**문제**: 파일 상단(36-42행)에서 이미 import한 `build_review_metrics`, `build_test_metrics`를 메서드 내부에서 로컬 import하고 있음.

**영향**: 동작에는 문제 없으나, 유지보수 시 혼란. 상단 import를 수정해도 이 메서드는 영향 안 받음.

**수정 제안**: 로컬 import 제거하고 모듈 레벨 import 사용.

```python
def _generate_single_impl_summary(self, impl):
    # from .utils.context_builder import ... ← 삭제
    summary = { ... }
    review_ws = impl.get('review_workspace', '')
    if review_ws:
        summary['review_metrics'] = build_review_metrics(Path(review_ws))
    ...
```

---

### 3.2 [Medium] Checkpoint 후 architect context 불일치

**위치**: `orchestrator/main.py:337-406`

**문제**:

```python
# 337행: 전체 approaches로 context 생성
approaches_data = {'approaches': approaches}
architect_inline = build_architect_inline_context(approaches_data)

# ... Phase 1 Checkpoint (390행) ...

# 390행: 사용자가 일부만 승인 → approaches 필터링
approaches = self._filter_approaches_by_decision(approaches, decision)

# 417행: 필터링된 approaches + 필터링 전 architect_inline 전달
impl_results = self._run_implementations_parallel(
    ..., architect_inline=architect_inline, ...  # 원본 context
)
```

**영향**: Implementer가 거부된 approach의 제약사항/경고도 받게 됨. `build_architect_inline_context()`는 모든 approach의 `key_decisions`와 `trade_offs`를 합산하므로, 거부된 approach 특유의 제약이 포함될 수 있음.

**실제 리스크**: **낮음**. 제약사항은 "must/should/반드시" 키워드 기반 필터링이므로 대부분 프로젝트 전체에 해당하는 보편적 제약. approach-specific 제약이 섞여도 Implementer에게 해가 되지 않음.

**수정 제안** (선택적):

```python
# Checkpoint 이후에 context 재생성
if decision.get('action') == 'approve':
    approaches = self._filter_approaches_by_decision(approaches, decision)
    # context 재생성
    approaches_data = {'approaches': approaches}
    architect_inline = build_architect_inline_context(approaches_data)
    architect_summary = build_architect_summary_file(approaches_data)
    atomic_write(architect_summary_path, architect_summary)
```

---

### 3.3 [Medium] comparator.md의 `{task_dir}` 미치환 (기존 이슈)

**위치**: `prompts/comparator.md:11`, `orchestrator/agents/comparator.py:58-64`

**문제**: comparator.md 템플릿에 `{task_dir}` 플레이스홀더가 3곳에 사용됨:
- `{task_dir}/implementations/`
- `{task_dir}/submit-stage-2/`
- `{task_dir}/planning-spec.md`

그런데 `comparator.py`의 `load_prompt()` 호출에서 `task_dir`을 전달하지 않음:

```python
prompt = self.load_prompt(
    self.prompt_file,
    num_implementations=len(implementations),
    comparison_data=comparison_text,
    phase3_inline=phase3_inline,
    phase3_summary_path=phase3_summary_path,
    # task_dir 누락!
)
```

**영향**: Comparator 프롬프트에 `{task_dir}`이 리터럴 문자열로 남음. Claude가 실제 경로를 알지 못해 파일을 직접 참조하기 어려움.

**비고**: 이번 변경에서 도입된 이슈가 아님 (기존 코드에서도 동일). 그러나 새로 추가된 `{phase3_summary_path}`는 절대 경로로 전달되므로 이 문제를 우회함.

**수정 제안**:

```python
prompt = self.load_prompt(
    self.prompt_file,
    num_implementations=len(implementations),
    comparison_data=comparison_text,
    phase3_inline=phase3_inline,
    phase3_summary_path=phase3_summary_path,
    task_dir=context.get('task_dir', ''),  # 추가
)
```

---

### 3.4 [Low] `build_implementer_inline_context`의 빈 문자열 경로

**위치**: `orchestrator/utils/context_builder.py:162-224`

**문제**: `impl_path`가 빈 문자열(`''`)이면 `Path('') / 'work-done.md'`는 `./work-done.md`를 가리킴. 현재 디렉토리에 우연히 `work-done.md`가 있으면 잘못된 파일을 읽게 됨.

**영향**: 사실상 발생 불가. `_review_and_test_single()`에서 `impl['worktree_path']`는 git worktree 경로이며, 구현 실패 시 이 함수 자체가 호출되지 않음.

**수정 제안** (방어적):

```python
def build_implementer_inline_context(impl_path: Path, change_summary: Dict) -> str:
    impl_path = Path(impl_path)
    if not impl_path.is_absolute() or not impl_path.exists():
        # change_summary만으로 context 생성
        ...
```

---

### 3.5 [Low] `_extract_section` regex가 h4 이하 헤더를 무시

**위치**: `orchestrator/utils/context_builder.py:484`

```python
pattern = rf'#{1,3}\s*{re.escape(section_name)}...'
```

**문제**: `#{1,3}`은 `#`, `##`, `###`만 매칭. `####` 이하 헤더의 섹션은 추출 불가.

**영향**: work-done.md가 표준 형식(`## 구현 요약`, `## 기술적 결정`)을 따르면 문제없음. 비표준 포맷에서만 누락 가능.

**수정 제안**: 현재로서는 변경 불필요. 향후 비표준 포맷 지원 시 `#{1,6}`으로 확장 가능.

---

### 3.6 [Low] Comparator 리뷰 텍스트 길이 증가

**위치**: `orchestrator/agents/comparator.py:184-189`

**변경**: 500자 → 1,500자 (3배)

```python
# 변경 전
lines.append(f"\n### Code Review\n{impl['review'][:500]}...")

# 변경 후
if len(review_text) > 1500:
    review_text = review_text[:1500] + '\n\n... (전체 리뷰는 review.md 참조)'
```

**영향**: N=3일 때 리뷰 텍스트만 최대 4,500자(~1,125 토큰) 추가. `phase3_inline`에 구조화된 메트릭이 이미 포함되므로, 이 텍스트는 보조 역할.

**판단**: 리뷰의 맥락 정보(코드 예시, 구체적 위치 등)가 비교 판단에 도움되므로 합리적 결정. 다만 토큰 예산이 우려되면 1,000자로 조정 가능.

---

## 4. 코드 품질 평가

### 4.1 장점

1. **일관된 설계 패턴**: 모든 Transition(A/B/C)이 동일한 패턴 따름
   - `build_*_inline_context()` → Tier 1 (프롬프트 직접 삽입)
   - `build_*_summary_file()` → Tier 2 (파일 저장 + 경로 전달)

2. **Graceful degradation**: 모든 함수가 데이터 부재 시 안전한 fallback 반환
   - `'(Architect 분석 컨텍스트 없음)'`
   - `'(구현 컨텍스트 없음)'`
   - `{'available': False}`

3. **토큰 효율성 달성**: 목표 100-300 토큰/에이전트 대비 실제 18-141 토큰으로 목표 이하.

4. **하위 호환성 보장**: 모든 새 파라미터에 기본값 `''` 설정. context_builder가 없이도 기존 파이프라인 동작.

5. **관심사 분리**: 컨텍스트 생성 로직이 `context_builder.py` 한 곳에 집중. 에이전트 코드는 최소 변경.

6. **프롬프트 템플릿 설계**: Tier 1은 인라인, Tier 2는 "Read 도구로 참조하세요"로 에이전트가 선택적으로 접근.

### 4.2 개선 가능 영역

1. **테스트 부재**: `context_builder.py`에 대한 단위 테스트가 없음. regex 기반 파싱은 입력 형식에 민감하므로 테스트가 중요.

2. **매직 넘버**: 키워드 목록(constraint_keywords, warning_keywords)이 함수 내부에 하드코딩. 향후 확장 시 설정 파일로 분리 고려.

3. **로깅 부재**: `context_builder.py` 함수들에 로깅 없음. 파싱 실패 시 디버깅 어려움.

---

## 5. 토큰 비용 분석

### 5.1 Tier 1 (Inline) — 항상 사용

| Transition | 함수 | 대상 에이전트 | 토큰 (실측) |
|------------|------|--------------|-------------|
| A: Architect → Implementer | `build_architect_inline_context` | Implementer x N | ~141 |
| B: Implementer → Reviewer | `build_implementer_inline_context` | Reviewer x N | ~18-50 |
| B: Implementer → Tester | (동일) | Tester x N | ~18-50 |
| C: Phase 3 → Comparator | `format_phase3_inline` | Comparator x 1 | ~35/impl |

**N=1 총 Inline**: ~141 + 18 + 18 = **~177 토큰**
**N=2 총 Inline**: ~(141×2) + (18×2)×2 + (35×2) = **~424 토큰**
**N=3 총 Inline**: ~(141×3) + (18×3)×2 + (35×3) = **~636 토큰**

### 5.2 Tier 2 (File Reference) — 에이전트가 Read 시에만

| 파일 | 생성 시점 | 크기 (실측) | 비고 |
|------|-----------|-------------|------|
| `architect-summary.md` | Phase 1 후 | ~454 토큰 | Implementer가 선택적 참조 |
| `phase3-summary.json` | Phase 4 전 | ~89 토큰 | Comparator가 선택적 참조 |

### 5.3 비용 대비 효과

| 지표 | 변경 전 | 변경 후 |
|------|---------|---------|
| Comparator에 전달되는 리뷰 정보 | 500자 잘림 텍스트 | 구조화된 메트릭 + 1,500자 |
| Implementer의 설계 이해도 | approach dict만 | 제약사항 + 경고 + 기술 스택 |
| Reviewer의 구현 이해도 | impl_path만 | 요약 + 기술결정 + 제한사항 + 변경통계 |
| 추가 AI 비용 | - | 0원 (순수 Python) |
| 추가 Inline 토큰 | 0 | ~177-636 토큰 |

---

## 6. 수정 권장 사항 정리

| # | 심각도 | 항목 | 상태 |
|---|--------|------|------|
| 1 | Medium | `_generate_single_impl_summary` 중복 import 제거 | ✅ 수정 완료 |
| 2 | Medium | Checkpoint 후 architect context 재생성 | ✅ 수정 완료 |
| 3 | Medium | comparator.py에 `task_dir` 전달 | ✅ 수정 완료 |
| 4 | Low | `build_implementer_inline_context` 빈 경로 방어 | 미수정 (발생 불가) |
| 5 | Low | `_extract_section` h4+ 헤더 지원 | 미수정 (변경 불필요) |
| 6 | Low | Comparator 리뷰 텍스트 길이 조정 | 미수정 (합리적 판단) |
| 7 | 제안 | `context_builder.py` 단위 테스트 작성 | 향후 과제 |
| 8 | 제안 | `context_builder.py` 함수에 debug 로깅 추가 | 향후 과제 |

---

## 7. 결론

**종합 평가**: 설계 의도에 부합하는 깔끔한 구현. 토큰 효율성 목표를 달성하고, 하위 호환성을 유지하면서 에이전트 간 정보 전달 품질을 크게 향상시킴.

**수정 완료**: #1 (중복 import), #2 (checkpoint 후 재생성), #3 (task_dir 전달)
**향후 과제**: #7 (단위 테스트), #8 (로깅)
