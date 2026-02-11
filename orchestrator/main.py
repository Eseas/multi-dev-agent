"""Main orchestrator for managing the multi-agent development pipeline.

v3: git worktree 기반, N=1 MVP, Phase 6 사용자 주도 통합.
"""

import logging
import time
import json
from pathlib import Path
from typing import Dict, Any, Optional
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
)


logger = logging.getLogger(__name__)


class Orchestrator:
    """
    다중 에이전트 개발 파이프라인 오케스트레이터.

    파이프라인:
      Spec Validation → Phase 1 (Architect) → [Checkpoint]
      → Phase 2 (Implementer, worktree) → Phase 3 (Reviewer + Tester)
      → Phase 6 (통합 알림, 사용자 주도)
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
        self.git_manager = GitManager(
            workspace_root=self.workspace_root,
            target_repo=target_repo,
            default_branch=default_branch
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

                validation_result = validate_spec(spec_path)

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

                self._log_timeline(timeline_file, "CHECKPOINT", "approved")

            # === Phase 2: Implementation (N=1 MVP) ===
            self._log_timeline(timeline_file, "PHASE", "implementation_start")
            self._update_manifest(
                manifest_file, manifest, 'phase2_implementation'
            )
            self.notifier.notify_stage_started("Phase 2: Implementation")

            impl_results = []
            for i, approach in enumerate(approaches, start=1):
                # git worktree 생성
                worktree_path = self.git_manager.create_worktree(task_id, i)
                branch_name = self.git_manager.get_branch_name(task_id, i)

                self.logger.info(
                    f"Implementer {i}: worktree={worktree_path}, "
                    f"branch={branch_name}"
                )

                implementer = ImplementerAgent(
                    approach_id=i,
                    workspace=worktree_path,
                    executor=self.executor,
                    prompt_file=self.prompts_dir / 'implementer.md'
                )

                impl_result = implementer.run({
                    'approach': approach,
                    'spec_content': spec_content
                })

                # 변경 요약
                change_summary = {}
                if impl_result['success']:
                    try:
                        change_summary = self.git_manager.get_change_summary(
                            worktree_path
                        )
                    except GitError as e:
                        self.logger.warning(f"변경 요약 실패: {e}")

                impl_results.append({
                    'approach_id': i,
                    'approach': approach,
                    'worktree_path': str(worktree_path),
                    'branch': branch_name,
                    'success': impl_result['success'],
                    'change_summary': change_summary
                })

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

            # === Phase 3: Review & Test ===
            self._log_timeline(timeline_file, "PHASE", "review_test_start")
            self._update_manifest(
                manifest_file, manifest, 'phase3_review_test'
            )
            self.notifier.notify_stage_started("Phase 3: Review & Test")

            self._run_reviewers_and_testers(impl_results, task_dir)

            manifest['phases']['phase3'] = {'status': 'completed'}
            self._log_timeline(timeline_file, "PHASE", "review_test_done")
            self.notifier.notify_stage_completed("Phase 3: Review & Test")

            # === Phase 6: 통합 알림 (사용자 주도) ===
            self._log_timeline(timeline_file, "PHASE", "integration_notify")
            self._update_manifest(
                manifest_file, manifest, 'phase6_integration'
            )

            # N=1이므로 첫 번째 성공한 구현 선택
            selected = None
            for r in impl_results:
                if r['success']:
                    selected = r
                    break

            if selected:
                self._notify_integration_ready(
                    task_id=task_id,
                    task_dir=task_dir,
                    branch=selected['branch'],
                    worktree_path=selected['worktree_path']
                )
            else:
                self.logger.error("성공한 구현이 없습니다.")
                self.notifier.notify_pipeline_failed(
                    "모든 구현이 실패했습니다."
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
                'selected_branch': selected['branch'] if selected else None
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

    def _run_reviewers_and_testers(
        self,
        impl_results: list,
        task_dir: Path
    ) -> None:
        """Reviewer + Tester 에이전트를 실행한다."""
        reviewer_prompt = self.prompts_dir / 'reviewer.md'
        tester_prompt = self.prompts_dir / 'tester.md'

        for impl in impl_results:
            if not impl['success']:
                continue

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

            # Tester
            tester = TesterAgent(
                approach_id, test_workspace,
                self.executor, tester_prompt
            )
            test_result = tester.run({'impl_path': impl_path})
            impl['test_success'] = test_result['success']

    def _wait_for_checkpoint(
        self,
        task_dir: Path,
        checkpoint_name: str,
        timeout: int = 3600
    ) -> Optional[Dict[str, Any]]:
        """체크포인트 결정 파일을 폴링으로 대기한다.

        CLI에서 approve/revise/abort 커맨드로
        checkpoint-decision.json을 생성한다.

        Args:
            task_dir: 태스크 디렉토리
            checkpoint_name: 체크포인트 이름 (로깅용)
            timeout: 대기 타임아웃 (초)

        Returns:
            결정 딕셔너리 또는 None (타임아웃)
        """
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
            # 사용된 결정 파일 제거 (다음 체크포인트를 위해)
            try:
                decision_file.unlink()
            except OSError:
                pass

        return decision

    def _notify_integration_ready(
        self,
        task_id: str,
        task_dir: Path,
        branch: str,
        worktree_path: str
    ) -> None:
        """통합 준비 완료를 알리고 브랜치 정보를 저장한다.

        Phase 6은 사용자 주도: 사용자가 직접 git merge를 실행한다.
        """
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
        self.logger.info(f"통합 정보 저장: {task_dir / 'integration-info.json'}")

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
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")

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
                'default_branch': 'main'
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
                'enabled': True
            },
            'notifications': {
                'enabled': True,
                'sound': True
            }
        }

        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            yaml.dump(default_config, f, default_flow_style=False)
