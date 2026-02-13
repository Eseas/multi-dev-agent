"""Main orchestrator for managing the multi-agent development pipeline.

v5: Phase 5/6 제거, 평가까지만 실행 후 종료.
- Phase 1: Architect (접근법 설계)
- Phase 2: Implementer (병렬 구현)
- Phase 3: Reviewer + Tester (병렬 리뷰/테스트)
- Phase 4: Comparator (N≥2일 때만, 평가/비교)
- 평가 결과 저장 후 종료 (merge는 사용자가 수동으로)
"""

import logging
import shutil
import time
import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, Optional, List
from datetime import datetime

from .executor import ClaudeExecutor
from .watcher import FileWaitHelper
from .utils import (
    atomic_write,
    setup_logger,
    GitManager,
    GitError,
    SystemNotifier,
    parse_planning_spec,
    validate_spec,
    write_validation_errors,
    ProjectAnalyzer,
)
from .agents import (
    ArchitectAgent,
    ImplementerAgent,
    ReviewerAgent,
    TesterAgent,
    ComparatorAgent,
)


logger = logging.getLogger(__name__)


class Orchestrator:
    """
    다중 에이전트 개발 파이프라인 오케스트레이터.

    파이프라인 (N=1):
      Validation → Phase 1 → [Checkpoint] → Phase 2 → Phase 3 → 평가 결과 저장

    파이프라인 (N≥2):
      Validation → Phase 1 → [Checkpoint] → Phase 2 (병렬)
      → Phase 3 (병렬) → Phase 4 (Comparator) → 평가 결과 저장

    최종 결과: evaluation-result.md에 평가 결과 저장 후 종료
    사용자가 수동으로 원하는 브랜치를 선택하여 머지
    """

    def __init__(self, config_path: Path):
        self.config = self._load_config(config_path)
        self.workspace_root = Path(self.config['workspace']['root'])
        self.prompts_dir = Path(self.config['prompts']['directory'])

        # 로깅
        log_file = self.workspace_root / 'orchestrator.log'
        self.logger = setup_logger(
            'orchestrator',
            log_file=log_file,
            level=logging.INFO
        )

        # Claude 실행기
        self.executor = ClaudeExecutor(
            timeout=self.config['execution']['timeout'],
            max_retries=self.config['execution']['max_retries']
        )

        # Git 관리자
        target_repo = self.config['project'].get('target_repo', '')
        default_branch = self.config['project'].get('default_branch', 'main')
        github_token = self.config['project'].get('github_token', '')
        self.git_manager = GitManager(
            workspace_root=self.workspace_root,
            target_repo=target_repo,
            default_branch=default_branch,
            github_token=github_token
        )

        # 알림
        notification_config = self.config.get('notifications', {})
        self.notifier = SystemNotifier(
            enabled=notification_config.get('enabled', True),
            sound=notification_config.get('sound', True)
        )

        # 파이프라인 설정
        self.checkpoint_enabled = self.config.get('pipeline', {}).get(
            'checkpoint_phase1', True
        )
        self.validation_enabled = self.config.get('validation', {}).get(
            'enabled', True
        )
        self.strict_mode = self.config.get('validation', {}).get(
            'strict_mode', False
        )
        self.num_approaches = self.config.get('pipeline', {}).get(
            'num_approaches', 1
        )
        self.enable_review = self.config.get('pipeline', {}).get(
            'enable_review', True
        )
        self.enable_test = self.config.get('pipeline', {}).get(
            'enable_test', True
        )

    def run_from_spec(self, spec_path: Path) -> Dict[str, Any]:
        """기획서 기반으로 전체 파이프라인을 실행한다.

        Args:
            spec_path: planning-spec.md 경로

        Returns:
            파이프라인 결과 딕셔너리
        """
        task_id = self._generate_task_id()
        task_dir = self.workspace_root / 'tasks' / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        # 기획서를 task 디렉토리에 복사
        spec_copy = task_dir / 'planning-spec.md'
        shutil.copy2(spec_path, spec_copy)

        # manifest 초기화
        manifest = {
            'task_id': task_id,
            'spec_path': str(spec_path),
            'created_at': datetime.now().isoformat(),
            'stage': 'initialized',
            'phases': {}
        }
        manifest_file = task_dir / 'manifest.json'
        atomic_write(manifest_file, manifest)

        # timeline 로그
        timeline_file = task_dir / 'timeline.log'

        self.logger.info("=" * 70)
        self.logger.info(f"파이프라인 시작: {task_id}")
        self.logger.info("=" * 70)

        try:
            # === Spec Validation ===
            if self.validation_enabled:
                self._log_timeline(timeline_file, "PHASE", "validation_start")
                self._update_manifest(manifest_file, manifest, 'validation')
                self.notifier.notify_stage_started("기획서 검증")

                validation_result = validate_spec(
                    spec_path, strict_mode=self.strict_mode
                )

                if not validation_result.valid:
                    write_validation_errors(validation_result, task_dir)
                    self.notifier.notify_pipeline_failed(
                        "기획서 검증 실패. validation-errors.md를 확인하세요."
                    )
                    self._log_timeline(timeline_file, "ERROR", "validation_failed")
                    manifest['phases']['validation'] = {
                        'status': 'failed',
                        'errors': validation_result.errors
                    }
                    self._update_manifest(manifest_file, manifest, 'failed')
                    return {
                        'success': False,
                        'task_id': task_id,
                        'error': '기획서 검증 실패',
                        'validation_errors': validation_result.errors
                    }

                if validation_result.warnings:
                    self.logger.warning(
                        f"검증 경고: {validation_result.warnings}"
                    )

                self._log_timeline(timeline_file, "PHASE", "validation_done")
                self.notifier.notify_stage_completed("기획서 검증")

            # === 기획서 파싱 ===
            spec = parse_planning_spec(spec_path)
            spec_content = spec.raw_content
            num_approaches = spec.num_approaches or self.num_approaches

            self.logger.info(
                f"기획서 파싱 완료: N={num_approaches}, "
                f"방법 {len(spec.methods)}개 감지"
            )

            # === Git clone/fetch ===
            self._log_timeline(timeline_file, "PHASE", "git_setup_start")
            self._update_manifest(manifest_file, manifest, 'git_setup')

            clone_path = self.git_manager.ensure_clone()
            self.logger.info(f"Git clone 준비 완료: {clone_path}")

            self._log_timeline(timeline_file, "PHASE", "git_setup_done")

            # === 프로젝트 사전 분석 ===
            self._log_timeline(
                timeline_file, "PHASE", "project_analysis_start"
            )
            self._update_manifest(
                manifest_file, manifest, 'project_analysis'
            )

            analyzer = ProjectAnalyzer(clone_path)
            project_profile = analyzer.get_or_create_profile()
            project_context = analyzer.generate_target_context(
                project_profile, spec_content
            )

            self.logger.info(
                f"프로젝트 분석 완료: "
                f"{len(project_profile.get('modules', {}))}개 모듈, "
                f"컨텍스트 {len(project_context)}자"
            )

            # 프로필을 task 디렉토리에 저장 (디버깅용)
            atomic_write(
                task_dir / 'project-profile.json', project_profile
            )

            # 프로젝트 컨텍스트를 파일로 저장 (에이전트가 참조)
            project_context_file = task_dir / 'project-context.md'
            project_context_file.write_text(
                project_context, encoding='utf-8'
            )
            project_context_path = str(project_context_file.resolve())

            self._log_timeline(
                timeline_file, "PHASE", "project_analysis_done"
            )

            # === Phase 1: Architect ===
            self._log_timeline(timeline_file, "PHASE", "architect_start")
            self._update_manifest(manifest_file, manifest, 'phase1_architect')
            self.notifier.notify_stage_started("Phase 1: Architect")

            architect_workspace = task_dir / 'architect'
            architect_workspace.mkdir(parents=True, exist_ok=True)

            architect = ArchitectAgent(
                workspace=architect_workspace,
                executor=self.executor,
                prompt_file=self.prompts_dir / 'architect.md'
            )

            arch_result = architect.run({
                'spec_content': spec_content,
                'num_approaches': num_approaches,
                'project_path': str(clone_path),
                'project_context_path': project_context_path,
            })

            if not arch_result['success']:
                raise RuntimeError(
                    f"Architect 실패: {arch_result.get('error')}"
                )

            approaches = arch_result['approaches']
            manifest['phases']['phase1'] = {
                'status': 'completed',
                'num_approaches': len(approaches)
            }

            self._log_timeline(
                timeline_file, "PHASE",
                f"architect_done (approaches={len(approaches)})"
            )
            self.notifier.notify_stage_completed("Phase 1: Architect")

            # === Phase 1 Checkpoint ===
            if self.checkpoint_enabled:
                self._log_timeline(
                    timeline_file, "CHECKPOINT", "waiting_for_approval"
                )
                self._update_manifest(
                    manifest_file, manifest, 'checkpoint_phase1'
                )
                self.notifier.notify_human_review_needed()

                decision = self._wait_for_checkpoint(task_dir, 'phase1')

                if decision is None or decision.get('action') == 'abort':
                    self._log_timeline(
                        timeline_file, "CHECKPOINT", "aborted"
                    )
                    self._update_manifest(manifest_file, manifest, 'aborted')
                    self.notifier.notify_pipeline_failed("사용자가 중단했습니다.")
                    return {
                        'success': False,
                        'task_id': task_id,
                        'error': '사용자 중단'
                    }

                if decision.get('action') == 'revise':
                    feedback = decision.get('feedback', '')
                    self._log_timeline(
                        timeline_file, "CHECKPOINT",
                        f"revision_requested: {feedback}"
                    )
                    self._update_manifest(manifest_file, manifest, 'revision')
                    return {
                        'success': False,
                        'task_id': task_id,
                        'error': '수정 요청',
                        'feedback': feedback
                    }

                # N≥2 개별 승인 처리
                if decision.get('action') == 'approve':
                    approaches = self._filter_approaches_by_decision(
                        approaches, decision
                    )
                    if not approaches:
                        self._update_manifest(
                            manifest_file, manifest, 'aborted'
                        )
                        return {
                            'success': False,
                            'task_id': task_id,
                            'error': '승인된 접근법이 없습니다'
                        }

                self._log_timeline(
                    timeline_file, "CHECKPOINT",
                    f"approved (approaches={len(approaches)})"
                )

            # === Phase 2: Implementation (병렬) ===
            self._log_timeline(timeline_file, "PHASE", "implementation_start")
            self._update_manifest(
                manifest_file, manifest, 'phase2_implementation'
            )
            self.notifier.notify_stage_started(
                f"Phase 2: Implementation ({len(approaches)}개)"
            )

            impl_results = self._run_implementations_parallel(
                task_id, approaches, spec_content, project_context_path
            )

            manifest['phases']['phase2'] = {
                'status': 'completed',
                'implementations': [
                    {
                        'approach_id': r['approach_id'],
                        'branch': r['branch'],
                        'success': r['success']
                    }
                    for r in impl_results
                ]
            }
            self._log_timeline(timeline_file, "PHASE", "implementation_done")
            self.notifier.notify_stage_completed("Phase 2: Implementation")

            # === Phase 3: Review & Test (병렬) ===
            if self.enable_review or self.enable_test:
                self.logger.info("Phase 3: Review & Test 시작")
                self.notifier.notify_stage_started("Phase 3: Review & Test")

                self._log_timeline(timeline_file, "PHASE", "review_test_start")
                self._update_manifest(
                    manifest_file, manifest, 'phase3_review_test'
                )
                self._run_reviewers_and_testers_parallel(impl_results, task_dir)
                manifest['phases']['phase3'] = {'status': 'completed'}
                self._log_timeline(timeline_file, "PHASE", "review_test_done")

                self.notifier.notify_stage_completed("Phase 3: Review & Test")
            else:
                self.logger.info("Phase 3 (Review & Test) 스킵 - 비활성화됨")
                manifest['phases']['phase3'] = {'status': 'skipped'}

            # 성공한 구현 필터링
            successful_impls = [r for r in impl_results if r['success']]

            if not successful_impls:
                self.logger.error("성공한 구현이 없습니다.")
                self.notifier.notify_pipeline_failed("모든 구현이 실패했습니다.")
                self._update_manifest(manifest_file, manifest, 'failed')
                return {
                    'success': False,
                    'task_id': task_id,
                    'error': '모든 구현이 실패했습니다'
                }

            # === Phase 4: 평가 (N≥2) 또는 요약 (N=1) ===
            evaluation_summary = None
            if len(successful_impls) >= 2:
                # Phase 4: Comparator 실행
                evaluation_summary = self._run_phase4_comparison(
                    task_id, task_dir, timeline_file,
                    manifest_file, manifest, successful_impls
                )
            else:
                # N=1: 평가 없이 단일 구현 요약
                evaluation_summary = self._generate_single_impl_summary(
                    successful_impls[0]
                )

            # === 최종 평가 결과 저장 ===
            self._save_final_evaluation(
                task_dir, evaluation_summary, successful_impls
            )

            # 완료
            self._update_manifest(manifest_file, manifest, 'completed')
            self._log_timeline(timeline_file, "PHASE", "pipeline_completed")
            self.notifier.notify_pipeline_completed(
                f"{task_id} - 평가 완료. evaluation-result.md를 확인하세요."
            )

            self.logger.info(f"파이프라인 완료: {task_id}")
            self.logger.info(f"평가 결과: {task_dir / 'evaluation-result.md'}")

            return {
                'success': True,
                'task_id': task_id,
                'implementations': impl_results,
                'evaluation_summary': evaluation_summary
            }

        except Exception as e:
            self.logger.error(f"파이프라인 실패: {e}", exc_info=True)
            self._update_manifest(manifest_file, manifest, 'failed')
            self._log_timeline(timeline_file, "ERROR", str(e))
            self.notifier.notify_pipeline_failed(str(e))
            return {
                'success': False,
                'task_id': task_id,
                'error': str(e)
            }

    # ── Phase 2: 병렬 구현 ─────────────────────────────────

    def _run_implementations_parallel(
        self,
        task_id: str,
        approaches: List[Dict],
        spec_content: str,
        project_context_path: str = ''
    ) -> List[Dict[str, Any]]:
        """N개 Implementer를 병렬로 실행한다."""
        if len(approaches) == 1:
            # N=1: 순차 실행 (오버헤드 방지)
            return [
                self._run_single_implementation(
                    task_id, 1, approaches[0],
                    spec_content, project_context_path
                )
            ]

        impl_results = [None] * len(approaches)

        with ThreadPoolExecutor(max_workers=len(approaches)) as executor:
            future_to_idx = {}
            for i, approach in enumerate(approaches, start=1):
                future = executor.submit(
                    self._run_single_implementation,
                    task_id, i, approach,
                    spec_content, project_context_path
                )
                future_to_idx[future] = i - 1

            for future in as_completed(future_to_idx):
                idx = future_to_idx[future]
                try:
                    impl_results[idx] = future.result()
                except Exception as e:
                    self.logger.error(f"Implementer {idx+1} 실패: {e}")
                    impl_results[idx] = {
                        'approach_id': idx + 1,
                        'approach': approaches[idx],
                        'worktree_path': '',
                        'branch': '',
                        'success': False,
                        'change_summary': {},
                        'error': str(e)
                    }

        return impl_results

    def _run_single_implementation(
        self,
        task_id: str,
        impl_id: int,
        approach: Dict,
        spec_content: str,
        project_context_path: str = ''
    ) -> Dict[str, Any]:
        """단일 Implementer를 실행한다."""
        worktree_path = self.git_manager.create_worktree(task_id, impl_id)
        branch_name = self.git_manager.get_branch_name(task_id, impl_id)

        self.logger.info(
            f"Implementer {impl_id}: worktree={worktree_path}, "
            f"branch={branch_name}"
        )

        implementer = ImplementerAgent(
            approach_id=impl_id,
            workspace=worktree_path,
            executor=self.executor,
            prompt_file=self.prompts_dir / 'implementer.md'
        )

        impl_result = implementer.run({
            'approach': approach,
            'spec_content': spec_content,
            'project_context_path': project_context_path,
        })

        change_summary = {}
        if impl_result['success']:
            try:
                change_summary = self.git_manager.get_change_summary(
                    worktree_path
                )
            except GitError as e:
                self.logger.warning(f"변경 요약 실패: {e}")

        return {
            'approach_id': impl_id,
            'approach': approach,
            'worktree_path': str(worktree_path),
            'branch': branch_name,
            'success': impl_result['success'],
            'change_summary': change_summary
        }

    # ── Phase 3: 병렬 리뷰/테스트 ──────────────────────────

    def _run_reviewers_and_testers_parallel(
        self,
        impl_results: List[Dict],
        task_dir: Path
    ) -> None:
        """Reviewer + Tester를 병렬로 실행한다."""
        successful = [r for r in impl_results if r['success']]

        if len(successful) <= 1:
            # N=1: 순차 실행
            for impl in successful:
                self._review_and_test_single(impl, task_dir)
            return

        with ThreadPoolExecutor(max_workers=len(successful)) as executor:
            futures = {
                executor.submit(
                    self._review_and_test_single, impl, task_dir
                ): impl
                for impl in successful
            }
            for future in as_completed(futures):
                impl = futures[future]
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(
                        f"Review/Test {impl['approach_id']} 실패: {e}"
                    )
                    impl['review_success'] = False
                    impl['test_success'] = False

    def _review_and_test_single(
        self, impl: Dict, task_dir: Path
    ) -> None:
        """단일 구현에 대해 Reviewer + Tester를 실행한다."""
        approach_id = impl['approach_id']
        impl_path = impl['worktree_path']

        # Reviewer
        if self.enable_review:
            reviewer_prompt = self.prompts_dir / 'reviewer.md'
            review_workspace = task_dir / f'review-{approach_id}'
            review_workspace.mkdir(parents=True, exist_ok=True)

            reviewer = ReviewerAgent(
                approach_id, review_workspace,
                self.executor, reviewer_prompt
            )
            review_result = reviewer.run({
                'impl_path': impl_path,
                'approach': impl.get('approach', {})  # approach 정보 전달
            })
            impl['review_success'] = review_result['success']
            impl['review_workspace'] = str(review_workspace)
        else:
            impl['review_success'] = None
            impl['review_workspace'] = ''

        # Tester
        if self.enable_test:
            tester_prompt = self.prompts_dir / 'tester.md'
            test_workspace = task_dir / f'test-{approach_id}'
            test_workspace.mkdir(parents=True, exist_ok=True)

            tester = TesterAgent(
                approach_id, test_workspace,
                self.executor, tester_prompt
            )
            test_result = tester.run({
                'impl_path': impl_path,
                'approach': impl.get('approach', {})  # approach 정보 전달
            })
            impl['test_success'] = test_result['success']
            impl['test_workspace'] = str(test_workspace)
        else:
            impl['test_success'] = None
            impl['test_workspace'] = ''

    # ── Phase 4: 비교 (N≥2) ────────────────────────────────

    def _run_phase4_comparison(
        self,
        task_id: str,
        task_dir: Path,
        timeline_file: Path,
        manifest_file: Path,
        manifest: Dict,
        successful_impls: List[Dict]
    ) -> Dict[str, Any]:
        """Phase 4 (Comparator)를 실행한다.

        Returns:
            평가 요약 딕셔너리
        """
        # === Phase 4: Comparison ===
        self._log_timeline(timeline_file, "PHASE", "comparison_start")
        self._update_manifest(manifest_file, manifest, 'phase4_comparison')
        self.notifier.notify_stage_started("Phase 4: Comparison")

        comparator_workspace = task_dir / 'comparator'
        comparator_workspace.mkdir(parents=True, exist_ok=True)

        comparator = ComparatorAgent(
            workspace=comparator_workspace,
            executor=self.executor,
            prompt_file=self.prompts_dir / 'comparator.md'
        )

        comp_context = {
            'implementations': [
                {
                    'approach_id': r['approach_id'],
                    'path': r['worktree_path'],
                    'approach': r['approach'],
                    'review_workspace': r.get('review_workspace', ''),
                    'test_workspace': r.get('test_workspace', ''),
                }
                for r in successful_impls
            ],
            'task_dir': str(task_dir)
        }

        comp_result = comparator.run(comp_context)

        if not comp_result['success']:
            self.logger.error(
                f"Comparator 실패: {comp_result.get('error')}"
            )
            # Comparator 실패 시 기본 평가 반환
            self.notifier.notify_stage_completed(
                "Phase 4: Comparison (실패)"
            )
            return {
                'status': 'failed',
                'error': comp_result.get('error'),
                'rankings': []
            }

        rankings = comp_result['rankings']
        manifest['phases']['phase4'] = {
            'status': 'completed',
            'rankings': rankings
        }

        self._log_timeline(
            timeline_file, "PHASE",
            f"comparison_done (rankings={rankings})"
        )
        self.notifier.notify_stage_completed("Phase 4: Comparison")

        return {
            'status': 'completed',
            'rankings': rankings,
            'comparison_file': str(comparator_workspace / 'comparison.md')
        }

    def _generate_single_impl_summary(
        self,
        impl: Dict[str, Any]
    ) -> Dict[str, Any]:
        """N=1일 때 단일 구현 요약을 생성한다."""
        return {
            'status': 'single_implementation',
            'approach_id': impl['approach_id'],
            'approach_name': impl['approach'].get('name', ''),
            'branch': impl['branch'],
            'worktree_path': impl['worktree_path'],
            'review_success': impl.get('review_success'),
            'test_success': impl.get('test_success')
        }

    def _save_final_evaluation(
        self,
        task_dir: Path,
        evaluation_summary: Dict[str, Any],
        implementations: List[Dict]
    ) -> None:
        """최종 평가 결과를 파일로 저장한다."""
        result_file = task_dir / 'evaluation-result.md'

        # Markdown 형식으로 작성
        lines = [
            "# 평가 결과",
            "",
            f"**작업 ID**: {task_dir.name}",
            f"**생성 시각**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "---",
            ""
        ]

        if evaluation_summary.get('status') == 'single_implementation':
            # N=1: 단일 구현
            lines.extend([
                "## 단일 구현",
                "",
                f"**접근법 ID**: {evaluation_summary['approach_id']}",
                f"**접근법 이름**: {evaluation_summary['approach_name']}",
                f"**브랜치**: `{evaluation_summary['branch']}`",
                f"**리뷰 통과**: {'✅' if evaluation_summary.get('review_success') else '❌'}",
                f"**테스트 통과**: {'✅' if evaluation_summary.get('test_success') else '❌'}",
                "",
                "### 구현 위치",
                f"```",
                f"{evaluation_summary['worktree_path']}",
                f"```",
                ""
            ])
        elif evaluation_summary.get('rankings'):
            # N≥2: 비교 평가
            rankings = evaluation_summary['rankings']
            lines.extend([
                "## 비교 평가 결과",
                "",
                f"**평가 순위**: {rankings}",
                f"**추천 구현**: impl-{rankings[0]}",
                "",
                "### 상세 비교",
                ""
            ])

            # 각 구현 정보
            for impl in implementations:
                aid = impl['approach_id']
                rank = rankings.index(aid) + 1 if aid in rankings else '?'
                lines.extend([
                    f"#### impl-{aid} (순위: #{rank})",
                    f"- **접근법**: {impl['approach'].get('name', 'N/A')}",
                    f"- **브랜치**: `{impl['branch']}`",
                    f"- **리뷰**: {'✅' if impl.get('review_success') else '❌'}",
                    f"- **테스트**: {'✅' if impl.get('test_success') else '❌'}",
                    ""
                ])

            comp_file = evaluation_summary.get('comparison_file')
            if comp_file:
                lines.extend([
                    "### 비교 보고서",
                    f"[{comp_file}]({comp_file})",
                    ""
                ])
        else:
            # 평가 실패
            lines.extend([
                "## 평가 실패",
                "",
                f"**오류**: {evaluation_summary.get('error', 'Unknown')}",
                ""
            ])

        lines.extend([
            "---",
            "",
            "## 다음 단계",
            "",
            "1. 위 평가 결과를 검토하세요",
            "2. 각 구현의 코드를 확인하세요:",
            ""
        ])

        for impl in implementations:
            lines.append(f"   - impl-{impl['approach_id']}: `{impl['worktree_path']}`")

        lines.extend([
            "",
            "3. 원하는 구현을 선택하여 타겟 프로젝트에 머지하세요:",
            "   ```bash",
            "   cd <타겟-프로젝트>",
            "   git merge <선택한-브랜치>",
            "   ```",
            ""
        ])

        result_file.write_text('\n'.join(lines), encoding='utf-8')
        self.logger.info(f"평가 결과 저장: {result_file}")

    # ── Checkpoint 처리 ──────────────────────────────────────

    def _filter_approaches_by_decision(
        self,
        approaches: List[Dict],
        decision: Dict
    ) -> List[Dict]:
        """체크포인트 결정에 따라 접근법을 필터링한다.

        N≥2 개별 승인: approved_approaches/rejected_approaches 처리.
        필드가 없으면 전체 승인으로 간주.
        """
        approved = decision.get('approved_approaches')
        rejected = decision.get('rejected_approaches', [])

        if approved is None and not rejected:
            # 전체 승인 (기존 동작)
            return approaches

        filtered = []
        for i, approach in enumerate(approaches, start=1):
            if i in rejected:
                self.logger.info(f"Approach {i}: 반려됨")
                continue
            if approved is not None and i not in approved:
                self.logger.info(f"Approach {i}: 미승인 (제외)")
                continue
            filtered.append(approach)

        self.logger.info(
            f"개별 승인 결과: {len(approaches)}개 중 "
            f"{len(filtered)}개 승인"
        )
        return filtered

    def _wait_for_checkpoint(
        self,
        task_dir: Path,
        checkpoint_name: str,
        timeout: int = 3600
    ) -> Optional[Dict[str, Any]]:
        """체크포인트 결정 파일을 폴링으로 대기한다."""
        decision_file = task_dir / 'checkpoint-decision.json'

        self.logger.info(
            f"체크포인트 '{checkpoint_name}': "
            f"승인 대기 중 ({decision_file})"
        )
        self.logger.info(
            "CLI에서 approve/revise/abort 명령을 실행하세요."
        )

        decision = FileWaitHelper.wait_for_file_content(
            decision_file,
            expected_key='action',
            timeout=timeout
        )

        if decision:
            self.logger.info(
                f"체크포인트 결정: {decision.get('action')}"
            )
            try:
                decision_file.unlink()
            except OSError:
                pass

        return decision

    # ── 유틸리티 ──────────────────────────────────────────────

    def _generate_task_id(self) -> str:
        """고유 태스크 ID를 생성한다."""
        return f"task-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    def _update_manifest(
        self,
        manifest_file: Path,
        manifest: Dict[str, Any],
        stage: str
    ) -> None:
        """manifest.json을 업데이트한다."""
        manifest['stage'] = stage
        manifest['updated_at'] = datetime.now().isoformat()
        atomic_write(manifest_file, manifest)

    def _log_timeline(
        self,
        timeline_file: Path,
        level: str,
        message: str
    ) -> None:
        """timeline.log에 이벤트를 기록한다."""
        timestamp = datetime.now().isoformat()
        line = f"[{timestamp}] [{level}] {message}\n"
        with open(timeline_file, 'a') as f:
            f.write(line)

    def _load_config(self, config_path: Path) -> Dict[str, Any]:
        """YAML 설정 파일을 로드한다."""
        import yaml

        if not config_path.exists():
            raise FileNotFoundError(
                f"설정 파일을 찾을 수 없습니다: {config_path}"
            )

        with open(config_path) as f:
            return yaml.safe_load(f)

    @staticmethod
    def create_default_config(output_path: Path) -> None:
        """기본 설정 파일을 생성한다."""
        import yaml

        default_config = {
            'workspace': {
                'root': './workspace'
            },
            'project': {
                'target_repo': '',
                'default_branch': 'main',
                'github_token': ''
            },
            'prompts': {
                'directory': './prompts'
            },
            'execution': {
                'timeout': 300,
                'max_retries': 3
            },
            'pipeline': {
                'checkpoint_phase1': True,
                'num_approaches': 1,
                'enable_review': True,
                'enable_test': True
            },
            'validation': {
                'enabled': True,
                'auto_revalidate': True,
                'strict_mode': False
            },
            'notifications': {
                'enabled': True,
                'sound': True
            }
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
