# 토큰 최적화 전략 가이드

Multi-Agent Development System의 Claude API 토큰 사용량을 줄이기 위한 최적화 전략 모음입니다.

## 📊 현재 상태 (v1.1 - ProjectAnalyzer 적용 후)

| Phase | Before | After (ProjectAnalyzer) | 개선율 |
|-------|--------|------------------------|--------|
| Architect | ~252s | ~60-90s | 63~76% |
| Implementer | ~300s+ | ~120-180s | 40~60% |

**개선 방법**: 프로젝트 사전 분석 (Python 기반, AI 비용 없음) + 2-tier 컨텍스트

---

## 🎯 추가 최적화 전략

### 우선순위 요약

| 방안 | 예상 효과 | 구현 난이도 | 즉시 적용 | 우선순위 |
|------|----------|-----------|----------|---------|
| 점진적 프롬프트 | 40% | 높음 | ❌ | 🥇 1순위 (장기) |
| 컨텍스트 압축 | 50% | 중간 | ✅ | 🥈 2순위 (즉시) |
| Implementer 캐싱 | 100%* | 낮음 | ✅ | 🥈 2순위 (즉시) |
| 선택적 Phase | 30% | 낮음 | ✅ | 🥉 3순위 |
| 실패만 재실행 | 60%* | 중간 | ✅ | 🥉 3순위 |
| 프롬프트 최적화 | 10% | 낮음 | ✅ | 4순위 |
| 모듈 스니펫 캐싱 | 90%* | 중간 | ❌ | 5순위 |

*: 재사용/재실행 시에만 해당

---

## 1. 점진적 프롬프트 (Progressive Prompting) 🥇

### 개념
처음엔 최소 정보만 제공하고, Claude가 필요한 정보를 요청하면 동적으로 제공하는 방식.

### 현재 문제
- 타겟 컨텍스트 ~31,490자를 항상 전부 제공
- Claude가 실제로 필요한 것은 일부분만
- 불필요한 정보 전송으로 토큰 낭비

### 해결 방법

#### 1) 프롬프트 수정 (prompts/implementer.md)

```markdown
# Implementer Agent (점진적 버전)

당신은 구현자입니다.

## 타겟 프로젝트 (개요만)
{project_overview}  # 전체 상세 대신 개요만 (~5,000자)

**기술 스택**: {tech_stack}
**아키텍처**: {architecture}
**모듈 목록**: {module_list}

## 작업
다음을 구현하세요:
{approach}

## 추가 정보 요청 방법

필요한 정보가 있으면 다음 형식으로 요청하세요:

```
NEED_INFO: module-admin 전체 코드
NEED_INFO: AuthService 클래스 상세
NEED_INFO: SecurityConfig 설정 예시
```

시스템이 요청한 정보를 제공하고, 구현을 계속할 수 있습니다.

**중요**: 불필요한 탐색 금지. 이미 제공된 정보로 충분합니다.
```

#### 2) Implementer 로직 수정

```python
# orchestrator/agents/implementer.py

class ImplementerAgent(BaseAgent):
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """점진적 프롬프트로 실행."""
        approach = context['approach']
        spec_content = context['spec_content']
        project_profile = context['project_profile']

        iteration = 1
        max_iterations = 3

        # 1차 실행: 최소 컨텍스트 (개요만)
        minimal_context = self._build_minimal_context(project_profile)
        prompt = self.load_prompt(
            self.prompt_file,
            approach=approach,
            spec_content=spec_content,
            project_overview=minimal_context,  # ~5,000자
            tech_stack=project_profile['tech_stack'],
            architecture=project_profile['architecture'],
            module_list=self._format_module_list(project_profile['modules'])
        )

        result = self.execute_claude(prompt, working_dir=self.workspace)

        # 추가 정보 요청 루프
        while iteration < max_iterations:
            info_requests = self._parse_info_requests(result['output'])

            if not info_requests:
                break  # 완료 - 더 이상 요청 없음

            self.logger.info(f"추가 정보 요청 {len(info_requests)}개 감지")

            # 요청된 정보만 제공
            additional_context = self._fetch_requested_info(
                info_requests, project_profile
            )

            # Follow-up 프롬프트
            followup_prompt = f"""
이전 작업을 계속합니다.

## 요청한 추가 정보
{additional_context}

## 작업
위 정보를 활용하여 구현을 완료하세요.
"""

            result = self.execute_claude(
                followup_prompt,
                working_dir=self.workspace
            )
            iteration += 1

        if iteration >= max_iterations:
            self.logger.warning("최대 반복 횟수 도달")

        return result

    def _build_minimal_context(self, profile: Dict) -> str:
        """최소 컨텍스트 생성 (~5,000자)."""
        return f"""
프로젝트: {profile['project_type']}
모듈 수: {len(profile['modules'])}
아키텍처: {profile['architecture']}

각 모듈 개요:
{self._format_module_overview(profile['modules'])}
"""

    def _parse_info_requests(self, output: str) -> List[str]:
        """Claude 출력에서 NEED_INFO 요청 파싱."""
        import re
        pattern = r'NEED_INFO:\s*(.+)'
        return re.findall(pattern, output, re.MULTILINE)

    def _fetch_requested_info(
        self,
        requests: List[str],
        profile: Dict
    ) -> str:
        """요청된 정보만 추출."""
        context_parts = []

        for req in requests:
            req_lower = req.lower().strip()

            # 모듈 전체 요청
            if 'module-' in req_lower or 'module_' in req_lower:
                module_name = self._extract_module_name(req)
                module_code = self._get_module_code(module_name, profile)
                context_parts.append(f"## {module_name} 모듈\n{module_code}")

            # 특정 클래스 요청
            elif 'class' in req_lower or 'service' in req_lower:
                class_name = self._extract_class_name(req)
                class_code = self._get_class_code(class_name, profile)
                context_parts.append(f"## {class_name} 클래스\n{class_code}")

            # 설정 파일 요청
            elif 'config' in req_lower or '설정' in req_lower:
                config_code = self._get_config_examples(profile)
                context_parts.append(f"## 설정 예시\n{config_code}")

        return "\n\n".join(context_parts)
```

### 예상 효과
- **1차 실행**: ~5,000자 컨텍스트 → 대부분 여기서 완료
- **2차 실행** (필요시): ~10,000자 추가 → 요청한 정보만
- **총 토큰 절감**: ~40% (불필요한 정보 전송 방지)

---

## 2. 컨텍스트 압축 강화 🥈

### 개념
현재 타겟 컨텍스트에서 전체 코드 대신 **시그니처만** 포함.

### 구현

```python
# orchestrator/utils/project_analyzer.py

class ProjectAnalyzer:
    def _format_relevant_code(
        self,
        modules: List[Dict],
        compression_level: str = 'medium'  # low, medium, high
    ) -> str:
        """컨텍스트를 압축하여 생성.

        Args:
            compression_level:
                - low: 전체 코드 (현재 방식)
                - medium: 시그니처 + 주요 메서드 본문
                - high: 시그니처만
        """
        context = []

        for module in modules:
            context.append(f"# 모듈: {module['name']}")
            context.append(f"경로: {module['path']}")
            context.append("")

            for cls in module['key_classes']:
                context.append(f"## {cls['package']}.{cls['name']}")

                # 상속/구현
                if cls.get('extends'):
                    context.append(f"extends {cls['extends']}")
                if cls.get('implements'):
                    context.append(f"implements {', '.join(cls['implements'])}")

                context.append("")

                # 필드
                if cls.get('fields'):
                    context.append("### Fields")
                    for field in cls['fields']:
                        annotations = ' '.join(f"@{a}" for a in field.get('annotations', []))
                        context.append(f"  {annotations} {field['type']} {field['name']}")
                    context.append("")

                # 메서드
                if cls.get('methods'):
                    context.append("### Methods")
                    for method in cls['methods']:
                        annotations = ' '.join(f"@{a}" for a in method.get('annotations', []))
                        signature = method['signature']

                        if compression_level == 'high':
                            # 시그니처만
                            context.append(f"  {annotations} {signature}")

                        elif compression_level == 'medium':
                            # 시그니처 + 주요 메서드만 본문
                            context.append(f"  {annotations} {signature}")
                            if self._is_important_method(method):
                                context.append(f"    {method.get('body_summary', '...')}")

                        else:  # low
                            # 전체 (현재 방식)
                            context.append(f"  {annotations} {signature}")
                            context.append(f"    {method.get('body', '...')}")

                    context.append("")

        return "\n".join(context)

    def _is_important_method(self, method: Dict) -> bool:
        """주요 메서드인지 판단 (로직 포함 필요)."""
        name = method['name'].lower()
        # 생성자, 주요 비즈니스 로직
        return (
            name in ['init', 'constructor', 'execute', 'process', 'handle'] or
            any(ann in ['PostMapping', 'GetMapping', 'Transactional']
                for ann in method.get('annotations', []))
        )
```

### config.yaml에 설정 추가

```yaml
project_analysis:
  compression_level: high  # low, medium, high
  max_context_size: 20000  # 최대 컨텍스트 크기 (자)
```

### 예상 효과

| Compression Level | 컨텍스트 크기 | 정보 손실 | 권장 용도 |
|-------------------|--------------|----------|----------|
| low (현재) | ~31,490자 | 0% | 복잡한 구조 분석 필요 |
| **medium** (권장) | ~15,000자 | 10% | 일반적인 구현 |
| high | ~8,000자 | 30% | 간단한 구현 |

**예상 토큰 절감**: medium 사용 시 ~50%

---

## 3. Implementer 결과 캐싱 🥈

### 개념
같은 approach로 재실행할 때 이전 구현 재사용.

### 구현

```python
# orchestrator/agents/implementer.py

import hashlib

class ImplementerAgent(BaseAgent):
    def __init__(self, approach_id: int, workspace: Path, executor, prompt_file: Path):
        super().__init__(f'implementer-{approach_id}', workspace, executor)
        self.approach_id = approach_id
        self.prompt_file = prompt_file
        self.cache_dir = workspace.parent.parent / '.impl-cache'
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """캐싱을 지원하는 실행."""
        approach = context['approach']
        project_context = context.get('project_context', '')

        # 캐시 키 생성
        cache_key = self._generate_cache_key(
            approach,
            project_context,
            context.get('project_commit', 'unknown')
        )
        cache_file = self.cache_dir / f'{cache_key}.json'

        # 캐시 확인
        if cache_file.exists() and not context.get('force_rerun', False):
            self.logger.info(f"✨ 캐시 히트: {cache_key[:12]}...")
            cached_result = json.loads(cache_file.read_text())

            # 캐시된 파일들을 현재 workspace로 복사
            self._restore_from_cache(cached_result['workspace_snapshot'])

            return {
                'success': cached_result['success'],
                'cached': True,
                'original_timestamp': cached_result['timestamp']
            }

        # 캐시 미스: 실제 실행
        self.logger.info(f"캐시 미스. 새로 실행합니다.")
        result = self._run_implementation(context)

        # 성공 시 캐싱
        if result['success']:
            cache_data = {
                'success': True,
                'timestamp': datetime.now().isoformat(),
                'approach': approach,
                'workspace_snapshot': self._create_workspace_snapshot()
            }
            cache_file.write_text(json.dumps(cache_data, indent=2))
            self.logger.info(f"✅ 캐시 저장: {cache_key[:12]}...")

        return result

    def _generate_cache_key(
        self,
        approach: Dict,
        project_context: str,
        project_commit: str
    ) -> str:
        """캐시 키 생성 (approach + project 상태)."""
        # approach 내용 + 프로젝트 커밋 SHA
        content = json.dumps(approach, sort_keys=True) + project_commit
        return hashlib.sha256(content.encode()).hexdigest()

    def _create_workspace_snapshot(self) -> Dict:
        """현재 workspace의 파일들을 스냅샷으로 저장."""
        snapshot = {}

        for file_path in self.workspace.rglob('*'):
            if file_path.is_file() and not file_path.name.startswith('.'):
                rel_path = file_path.relative_to(self.workspace)
                snapshot[str(rel_path)] = file_path.read_text()

        return snapshot

    def _restore_from_cache(self, snapshot: Dict):
        """캐시된 스냅샷을 현재 workspace로 복원."""
        for rel_path, content in snapshot.items():
            file_path = self.workspace / rel_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content)
```

### CLI 명령 추가

```python
# cli.py

@cli.command()
@click.argument('task_id')
@click.option('--force', is_flag=True, help='캐시 무시하고 강제 재실행')
def rerun(task_id, force):
    """태스크 재실행 (캐시 활용)."""
    ...
    context['force_rerun'] = force
    ...
```

### 예상 효과
- **재실행 시 토큰 절감**: ~100% (Claude 실행 없음)
- **디스크 공간**: 캐시당 ~1-5MB
- **캐시 만료**: project commit SHA 변경 시 자동 무효화

---

## 4. 선택적 Phase 실행 🥉

### 개념
N=1일 때 불필요한 Phase 3 (Reviewer/Tester) 스킵.

### config.yaml 설정

```yaml
pipeline:
  checkpoint_phase1: true
  num_approaches: 1

  # 선택적 Phase 설정
  skip_review_for_single: true   # N=1일 때 Reviewer 생략
  skip_test_for_single: true     # N=1일 때 Tester 생략

  # 또는 항상 스킵
  always_skip_review: false      # 모든 N에서 Reviewer 생략
  always_skip_test: false        # 모든 N에서 Tester 생략
```

### main.py 수정

```python
# orchestrator/main.py

class Orchestrator:
    def run_from_spec(self, spec_path: Path) -> Dict[str, Any]:
        ...

        # === Phase 3: Review & Test ===
        skip_review = (
            (len(successful_impls) == 1 and
             self.config['pipeline'].get('skip_review_for_single', False)) or
            self.config['pipeline'].get('always_skip_review', False)
        )

        skip_test = (
            (len(successful_impls) == 1 and
             self.config['pipeline'].get('skip_test_for_single', False)) or
            self.config['pipeline'].get('always_skip_test', False)
        )

        if not skip_review or not skip_test:
            self._log_timeline(timeline_file, "PHASE", "review_test_start")
            self._update_manifest(manifest_file, manifest, 'phase3_review_test')
            self.notifier.notify_stage_started("Phase 3: Review & Test")

            self._run_reviewers_and_testers_partial(
                impl_results, task_dir,
                run_review=not skip_review,
                run_test=not skip_test
            )

            manifest['phases']['phase3'] = {
                'status': 'completed',
                'review_skipped': skip_review,
                'test_skipped': skip_test
            }
            self._log_timeline(timeline_file, "PHASE", "review_test_done")
            self.notifier.notify_stage_completed("Phase 3: Review & Test")
        else:
            self.logger.info("Phase 3 스킵 (설정에 따라)")
            manifest['phases']['phase3'] = {'status': 'skipped'}

        ...
```

### 예상 효과
- **N=1 파이프라인**: ~30% 토큰 절감
- **빠른 프로토타이핑**: Phase 2 완료 후 바로 Phase 6

---

## 5. 실패 구현만 재실행 🥉

### CLI 명령

```python
# cli.py

@cli.command()
@click.argument('task_id')
@click.option('--retry-failed/--retry-all', default=True)
@click.option('--impl-ids', help='재시도할 impl ID (쉼표 구분, 예: 1,3)')
def retry(task_id, retry_failed, impl_ids):
    """구현 재시도.

    예시:
        python cli.py retry task-XXX                # 실패한 것만
        python cli.py retry task-XXX --retry-all    # 전부
        python cli.py retry task-XXX --impl-ids 1,3 # 1, 3번만
    """
    config_path = Path('config.yaml')
    orchestrator = Orchestrator(config_path)

    task_dir = orchestrator.workspace_root / 'tasks' / task_id
    if not task_dir.exists():
        click.echo(f"❌ 태스크를 찾을 수 없습니다: {task_id}")
        return

    # manifest 로드
    manifest_file = task_dir / 'manifest.json'
    manifest = json.loads(manifest_file.read_text())

    # 재시도할 구현 필터링
    all_impls = manifest['phases']['phase2']['implementations']

    if impl_ids:
        # 특정 ID만
        target_ids = [int(i.strip()) for i in impl_ids.split(',')]
        retry_impls = [impl for impl in all_impls if impl['approach_id'] in target_ids]
    elif retry_failed:
        # 실패한 것만
        retry_impls = [impl for impl in all_impls if not impl['success']]
    else:
        # 전부
        retry_impls = all_impls

    if not retry_impls:
        click.echo("✅ 재시도할 구현이 없습니다.")
        return

    click.echo(f"🔄 {len(retry_impls)}개 구현 재시도 중...")

    # 재실행
    for impl in retry_impls:
        click.echo(f"  → impl-{impl['approach_id']} 재실행...")

        result = orchestrator._run_single_implementation(
            task_id=task_id,
            impl_id=impl['approach_id'],
            approach=impl['approach'],
            spec_content=manifest['spec_content'],
            project_context=manifest.get('project_context', '')
        )

        # manifest 업데이트
        for i, orig in enumerate(all_impls):
            if orig['approach_id'] == impl['approach_id']:
                all_impls[i] = result
                break

    # manifest 저장
    atomic_write(manifest_file, manifest)

    click.echo("✅ 재시도 완료!")
```

### 예상 효과
- **부분 실패 시 재실행**: 성공한 것 재사용 → ~60% 토큰 절감
- **디버깅 용이**: 특정 impl만 재실행 가능

---

## 6. 프롬프트 길이 최적화

### 현재 프롬프트 분석

```bash
# 프롬프트 길이 확인
wc -w prompts/*.md

# 예상 출력:
# 450 prompts/architect.md
# 520 prompts/implementer.md
# 380 prompts/reviewer.md
# 340 prompts/tester.md
# 290 prompts/comparator.md
```

### 최적화 방향

1. **불필요한 설명 제거**
2. **예시를 간결하게**
3. **중복 지시사항 통합**

### Before/After 예시

#### Before (implementer.md)
```markdown
# Implementer Agent

당신은 숙련된 개발자입니다. 주어진 기획서와 프로젝트 컨텍스트를 바탕으로,
할당된 구현 방법을 실제로 코딩하는 역할을 담당합니다. 타겟 프로젝트의
기존 코드 스타일과 패턴을 존중하면서, 새로운 기능을 추가하거나 수정합니다.

## 작업 환경

현재 작업 디렉토리는 타겟 프로젝트의 git worktree입니다. 독립된 브랜치에서
작업하므로 다른 구현과 충돌 없이 자유롭게 코드를 수정할 수 있습니다.

## 타겟 프로젝트

다음은 타겟 프로젝트의 구조와 핵심 코드입니다:

{project_context}

## 기획서

...
```

#### After (간소화)
```markdown
# Implementer

구현자 역할. 아래 컨텍스트 활용, 코드 작성.

## 프로젝트 (핵심만)
{project_context}

## 작업
{approach}를 구현하세요.

## 출력
work-done.md에 다음 형식으로:
- 구현 요약 (3-5줄)
- 생성 파일 목록
- 실행 방법
```

### 예상 효과
- 프롬프트 자체: ~5-10% 절감
- 가독성 향상으로 Claude의 이해도 개선 가능

---

## 7. 모듈별 코드 스니펫 캐싱

### 개념
자주 참조되는 모듈(common, core 등)의 코드를 스니펫으로 캐싱.

### 구현

```python
# orchestrator/utils/project_analyzer.py

class ProjectAnalyzer:
    def __init__(self, project_path: Path):
        self.project_path = project_path
        self.profile_cache = project_path / '.project-profile.json'
        self.snippet_cache_dir = project_path / '.snippet-cache'
        self.snippet_cache_dir.mkdir(exist_ok=True)

    def _get_module_code(
        self,
        module_name: str,
        compression: str = 'medium'
    ) -> str:
        """모듈 코드를 캐시에서 가져오거나 생성."""
        # 캐시 키
        cache_key = f"{module_name}_{compression}"
        cache_file = self.snippet_cache_dir / f'{cache_key}.txt'

        # 캐시 확인
        if cache_file.exists():
            return cache_file.read_text()

        # 스니펫 생성
        module_info = self._find_module_by_name(module_name)
        if not module_info:
            return f"# 모듈 '{module_name}'을 찾을 수 없습니다."

        snippet = self._generate_module_snippet(module_info, compression)

        # 캐싱
        cache_file.write_text(snippet)
        return snippet

    def _generate_module_snippet(
        self,
        module: Dict,
        compression: str
    ) -> str:
        """모듈의 코드 스니펫 생성."""
        if compression == 'high':
            return self._format_signatures_only(module)
        elif compression == 'medium':
            return self._format_signatures_with_important(module)
        else:
            return self._format_full_code(module)
```

### 예상 효과
- **캐시 히트 시**: ~90% 토큰 절감 (재사용)
- **디스크 공간**: 모듈당 ~10-50KB

---

## 🚀 즉시 적용 가능한 Top 3

### 1단계: 컨텍스트 압축 (10분)

```python
# orchestrator/utils/project_analyzer.py
# _format_relevant_code() 수정
# compression_level='medium' 또는 'high' 적용
```

```yaml
# config.yaml
project_analysis:
  compression_level: medium  # 추가
```

**예상 효과**: ~50% 토큰 절감

---

### 2단계: 선택적 Phase 실행 (5분)

```yaml
# config.yaml
pipeline:
  skip_review_for_single: true
  skip_test_for_single: true
```

```python
# orchestrator/main.py
# Phase 3 조건부 실행 로직 추가 (위 코드 참고)
```

**예상 효과**: N=1에서 ~30% 토큰 절감

---

### 3단계: Implementer 캐싱 (30분)

```python
# orchestrator/agents/implementer.py
# 캐싱 로직 추가 (위 코드 참고)
```

**예상 효과**: 재실행 시 ~100% 토큰 절감

---

## 📈 예상 총 효과

| 시나리오 | 기준 (v1.0) | v1.1 (ProjectAnalyzer) | v1.2 (즉시 최적화) | v2.0 (장기 최적화) |
|---------|------------|----------------------|------------------|------------------|
| Architect (첫 실행) | 252s | 60-90s | 30-45s | 20-30s |
| Implementer (첫 실행) | 300s+ | 120-180s | 60-90s | 40-60s |
| Implementer (재실행) | 300s+ | 120-180s | 0s (캐시) | 0s (캐시) |
| N=1 전체 파이프라인 | ~600s | ~250s | ~150s | ~100s |

**v1.2 목표** (즉시 최적화 3가지 적용):
- 첫 실행: 기준 대비 ~75% 개선
- 재실행: 기준 대비 ~90% 개선

**v2.0 목표** (점진적 프롬프트 포함):
- 첫 실행: 기준 대비 ~85% 개선
- 재실행: 기준 대비 ~95% 개선

---

## 🎯 구현 로드맵

### Phase 1: 즉시 최적화 (1-2일)
- [ ] 컨텍스트 압축 (medium/high level)
- [ ] 선택적 Phase 실행 (N=1 최적화)
- [ ] Implementer 결과 캐싱

### Phase 2: 중기 최적화 (1주)
- [ ] 실패만 재실행 CLI
- [ ] 프롬프트 길이 최적화
- [ ] 모듈 스니펫 캐싱

### Phase 3: 장기 최적화 (2-3주)
- [ ] 점진적 프롬프트 (Progressive Prompting)
- [ ] 동적 컨텍스트 조정
- [ ] AI 기반 컨텍스트 압축

---

## 📝 참고 자료

- [프로젝트 구조](README.md)
- [현재 구현 상태](multi-agent-dev-system-implementation-guide.md)
- [사용 가이드](USAGE.md)
- [CLAUDE.md](CLAUDE.md)

---

**최종 업데이트**: 2026-02-11
**버전**: v1.1 (ProjectAnalyzer 적용 후)
