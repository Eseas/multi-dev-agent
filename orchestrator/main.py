"""Main orchestrator for managing the multi-agent development pipeline.

v4: N≥2 지원, 병렬 실행, Phase 4/5 추가, 개별 승인.
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
      Validation → Phase 1 → [Checkpoint] → Phase 2 → Phase 3 → Phase 6

    파이프라인 (N≥2):
      Validation → Phase 1 → [Checkpoint] → Phase 2 (병렬)
      → Phase 3 (병렬) → Phase 4 (Comparator) → Phase 5 (Selection)
      → Phase 6 (통합 알림)
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
                'project_path': str(clone_path)
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
                task_id, approaches, spec_content
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
            self._log_timeline(timeline_file, "PHASE", "review_test_start")
            self._update_manifest(
                manifest_file, manifest, 'phase3_review_test'
            )
            self.notifier.notify_stage_started("Phase 3: Review & Test")

            self._run_reviewers_and_testers_parallel(impl_results, task_dir)

            manifest['phases']['phase3'] = {'status': 'completed'}
            self._log_timeline(timeline_file, "PHASE", "review_test_done")
            self.notifier.notify_stage_completed("Phase 3: Review & Test")

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

            # === N 분기: N=1이면 바로 Phase 6, N≥2면 Phase 4/5 ===
            if len(successful_impls) >= 2:
                # Phase 4: Comparator
                selected = self._run_phase4_and_phase5(
                    task_id, task_dir, timeline_file,
                    manifest_file, manifest, successful_impls
                )
                if selected is None:
                    return {
                        'success': False,
                        'task_id': task_id,
                        'error': '선택 실패 또는 중단'
                    }
            else:
                # N=1 또는 성공 1개: 바로 선택
                selected = successful_impls[0]

            # === Phase 6: 통합 알림 (사용자 주도) ===
            self._log_timeline(timeline_file, "PHASE", "integration_notify")
            self._update_manifest(
                manifest_file, manifest, 'phase6_integration'
            )

            self._notify_integration_ready(
                task_id=task_id,
                task_dir=task_dir,
                branch=selected['branch'],
                worktree_path=selected['worktree_path']
            )

            # 완료
            self._update_manifest(manifest_file, manifest, 'completed')
            self._log_timeline(timeline_file, "PHASE", "pipeline_completed")
            self.notifier.notify_pipeline_completed(task_id)

            self.logger.info(f"파이프라인 완료: {task_id}")

            return {
                'success': True,
                'task_id': task_id,
                'implementations': impl_results,
                'selected_branch': selected['branch']
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
        spec_content: str
    ) -> List[Dict[str, Any]]:
        """N개 Implementer를 병렬로 실행한다."""
        if len(approaches) == 1:
            # N=1: 순차 실행 (오버헤드 방지)
            return [
                self._run_single_implementation(
                    task_id, 1, approaches[0], spec_content
                )
            ]

        impl_results = [None] * len(approaches)

        with ThreadPoolExecutor(max_workers=len(approaches)) as executor:
            future_to_idx = {}
            for i, approach in enumerate(approaches, start=1):
                future = executor.submit(
                    self._run_single_implementation,
                    task_id, i, approach, spec_content
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
        spec_content: str
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
            'spec_content': spec_content
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
        reviewer_prompt = self.prompts_dir / 'reviewer.md'
        tester_prompt = self.prompts_dir / 'tester.md'

        approach_id = impl['approach_id']
        impl_path = impl['worktree_path']

        review_workspace = task_dir / f'review-{approach_id}'
        test_workspace = task_dir / f'test-{approach_id}'
        review_workspace.mkdir(parents=True, exist_ok=True)
        test_workspace.mkdir(parents=True, exist_ok=True)

        # Reviewer
        reviewer = ReviewerAgent(
            approach_id, review_workspace,
            self.executor, reviewer_prompt
        )
        review_result = reviewer.run({'impl_path': impl_path})
        impl['review_success'] = review_result['success']
        impl['review_workspace'] = str(review_workspace)

        # Tester
        tester = TesterAgent(
            approach_id, test_workspace,
            self.executor, tester_prompt
        )
        test_result = tester.run({'impl_path': impl_path})
        impl['test_success'] = test_result['success']
        impl['test_workspace'] = str(test_workspace)

    # ── Phase 4/5: 비교 + 선택 (N≥2) ────────────────────────

    def _run_phase4_and_phase5(
        self,
        task_id: str,
        task_dir: Path,
        timeline_file: Path,
        manifest_file: Path,
        manifest: Dict,
        successful_impls: List[Dict]
    ) -> Optional[Dict]:
        """Phase 4 (Comparator) + Phase 5 (Human Selection)를 실행한다.

        Returns:
            선택된 impl 딕셔너리 또는 None
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
            # Comparator 실패 시 첫 번째 성공 impl로 fallback
            self.notifier.notify_stage_completed(
                "Phase 4: Comparison (실패, 기본 선택)"
            )
            return successful_impls[0]

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

        # === Phase 5: Human Selection ===
        self._log_timeline(timeline_file, "PHASE", "selection_start")
        self._update_manifest(manifest_file, manifest, 'phase5_selection')
        self.notifier.notify_stage_started("Phase 5: Human Selection")

        selected = self._wait_for_selection(
            task_dir, rankings, successful_impls
        )

        if selected is None:
            self._log_timeline(timeline_file, "PHASE", "selection_timeout")
            self._update_manifest(manifest_file, manifest, 'failed')
            self.notifier.notify_pipeline_failed(
                "선택 타임아웃. select 명령을 실행하세요."
            )
            return None

        manifest['phases']['phase5'] = {
            'status': 'completed',
            'selected_id': selected['approach_id']
        }
        self._log_timeline(
            timeline_file, "PHASE",
            f"selection_done (selected={selected['approach_id']})"
        )
        self.notifier.notify_stage_completed(
            f"Phase 5: impl-{selected['approach_id']} 선택됨"
        )

        return selected

    def _wait_for_selection(
        self,
        task_dir: Path,
        rankings: List[int],
        impl_results: List[Dict],
        timeout: int = 3600
    ) -> Optional[Dict]:
        """Phase 5: 사용자의 구현 선택을 대기한다."""
        # 사용자 검토용 요약 저장
        review_summary = {
            'rankings': rankings,
            'recommended': rankings[0] if rankings else None,
            'implementations': [
                {
                    'approach_id': r['approach_id'],
                    'approach_name': r['approach'].get('name', ''),
                    'branch': r['branch'],
                    'review_success': r.get('review_success'),
                    'test_success': r.get('test_success'),
                }
                for r in impl_results
            ],
            'comparison_file': str(task_dir / 'comparator' / 'comparison.md'),
            'instructions': (
                "다음 명령으로 구현을 선택하세요:\n"
                f"  multi-agent-dev select <task-id> <impl-id>\n"
                f"추천: impl-{rankings[0] if rankings else '?'}"
            )
        }
        atomic_write(task_dir / 'human-review.json', review_summary)

        self.logger.info(
            f"Phase 5: 사용자 선택 대기 중. "
            f"추천: impl-{rankings[0] if rankings else '?'}"
        )
        self.logger.info(
            "CLI에서 select 명령을 실행하세요."
        )

        # selection-decision.json 폴링 대기
        decision_file = task_dir / 'selection-decision.json'
        decision = FileWaitHelper.wait_for_file_content(
            decision_file,
            expected_key='selected_id',
            timeout=timeout
        )

        if not decision:
            return None

        selected_id = decision['selected_id']
        self.logger.info(f"사용자가 impl-{selected_id}를 선택했습니다.")

        # 선택된 impl 찾기
        for r in impl_results:
            if r['approach_id'] == selected_id:
                return r

        # fallback: ID가 맞지 않으면 첫 번째
        self.logger.warning(
            f"선택된 ID {selected_id}를 찾을 수 없습니다. "
            "첫 번째 구현을 사용합니다."
        )
        return impl_results[0]

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

    # ── Phase 6: 통합 알림 ──────────────────────────────────

    def _notify_integration_ready(
        self,
        task_id: str,
        task_dir: Path,
        branch: str,
        worktree_path: str
    ) -> None:
        """통합 준비 완료를 알리고 브랜치 정보를 저장한다."""
        integration_info = {
            'task_id': task_id,
            'branch': branch,
            'worktree_path': worktree_path,
            'status': 'ready_for_integration',
            'created_at': datetime.now().isoformat(),
            'instructions': (
                f"통합하려면 다음을 실행하세요:\n"
                f"  cd <타겟-프로젝트>\n"
                f"  git merge {branch}\n"
                f"또는 GitHub PR을 생성하세요."
            )
        }

        atomic_write(task_dir / 'integration-info.json', integration_info)

        msg = (
            f"구현 완료! 브랜치: {branch}\n"
            f"git merge {branch} 로 통합하세요."
        )
        self.notifier.notify_stage_completed(msg)
        self.logger.info(
            f"통합 정보 저장: {task_dir / 'integration-info.json'}"
        )

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
                'num_approaches': 1
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
