"""Git 저장소 관리자.

타겟 프로젝트의 clone, worktree 생성/제거를 담당한다.
env_manager.py (symlink 기반)를 대체한다.
"""

import subprocess
import logging
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


class GitError(Exception):
    """Git 명령 실행 실패."""
    pass


class GitManager:
    """타겟 프로젝트의 git clone 및 worktree를 관리한다."""

    def __init__(
        self,
        workspace_root: Path,
        target_repo: str,
        default_branch: str = "main",
        github_token: str = ""
    ):
        """
        Args:
            workspace_root: 워크스페이스 루트 경로
            target_repo: 타겟 프로젝트 GitHub URL
            default_branch: 기본 브랜치 이름
            github_token: GitHub Personal Access Token (private repo용)
        """
        self.workspace_root = Path(workspace_root)
        self.target_repo = target_repo
        self.github_token = github_token
        self.default_branch = default_branch
        self.cache_dir = self.workspace_root / '.cache'
        self.clone_dir = self.cache_dir / self._repo_name()

    def _repo_name(self) -> str:
        """URL에서 저장소 이름을 추출한다.

        예: "https://github.com/user/my-web-app" → "my-web-app"
            "https://github.com/user/my-web-app.git" → "my-web-app"
        """
        parsed = urlparse(self.target_repo)
        path = parsed.path.rstrip('/')
        name = path.split('/')[-1]
        if name.endswith('.git'):
            name = name[:-4]
        return name or 'project'

    def _auth_url(self) -> str:
        """토큰이 설정되어 있으면 인증 URL을 반환한다.

        예: "https://github.com/user/repo.git"
          → "https://<token>@github.com/user/repo.git"
        """
        if not self.github_token:
            return self.target_repo

        parsed = urlparse(self.target_repo)
        auth_url = f"{parsed.scheme}://{self.github_token}@{parsed.hostname}"
        if parsed.port:
            auth_url += f":{parsed.port}"
        auth_url += parsed.path
        return auth_url

    def ensure_clone(self) -> Path:
        """타겟 프로젝트가 clone되어 있는지 확인하고, 없으면 clone한다.

        이미 clone되어 있으면 fetch로 최신 상태 동기화.

        Returns:
            clone된 디렉토리 경로

        Raises:
            GitError: clone 또는 fetch 실패 시
        """
        if not self.target_repo:
            raise GitError(
                "target_repo가 설정되지 않았습니다. "
                "config.yaml의 project.target_repo를 설정해주세요."
            )

        self.cache_dir.mkdir(parents=True, exist_ok=True)

        auth_url = self._auth_url()

        if self.clone_dir.exists() and (self.clone_dir / '.git').exists():
            logger.info(f"기존 clone 사용, fetch 실행: {self.clone_dir}")
            # 토큰이 변경되었을 수 있으므로 remote URL 갱신
            if self.github_token:
                self._run_git(
                    ['remote', 'set-url', 'origin', auth_url],
                    cwd=self.clone_dir
                )
            self._run_git(['fetch', 'origin'], cwd=self.clone_dir)
        else:
            logger.info(f"타겟 프로젝트 clone: {self.target_repo}")
            self._run_git([
                'clone', auth_url, str(self.clone_dir)
            ])

        return self.clone_dir

    def create_worktree(self, task_id: str, impl_id: int) -> Path:
        """구현을 위한 git worktree를 생성한다.

        Args:
            task_id: 작업 ID (예: "task-20250211-153000")
            impl_id: 구현 번호 (1부터 시작)

        Returns:
            생성된 worktree 디렉토리 경로

        Raises:
            GitError: worktree 생성 실패 시
        """
        branch_name = self.get_branch_name(task_id, impl_id)
        worktree_path = (
            self.workspace_root / 'tasks' / task_id
            / 'implementations' / f'impl-{impl_id}'
        )

        # 이미 존재하면 제거 후 재생성
        if worktree_path.exists():
            logger.warning(f"worktree 이미 존재, 제거 후 재생성: {worktree_path}")
            self.remove_worktree(worktree_path)

        worktree_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"worktree 생성: {worktree_path} (branch: {branch_name})")
        self._run_git([
            'worktree', 'add', str(worktree_path),
            '-b', branch_name,
            f'origin/{self.default_branch}'
        ], cwd=self.clone_dir)

        return worktree_path

    def remove_worktree(self, worktree_path: Path) -> None:
        """git worktree를 제거한다.

        Args:
            worktree_path: 제거할 worktree 경로
        """
        worktree_path = Path(worktree_path)

        if not worktree_path.exists():
            return

        try:
            self._run_git([
                'worktree', 'remove', str(worktree_path), '--force'
            ], cwd=self.clone_dir)
            logger.info(f"worktree 제거됨: {worktree_path}")
        except GitError as e:
            logger.warning(f"worktree 제거 실패 (수동 정리 필요): {e}")

    def get_branch_name(self, task_id: str, impl_id: int) -> str:
        """구현용 브랜치 이름을 반환한다.

        Args:
            task_id: 작업 ID
            impl_id: 구현 번호

        Returns:
            브랜치 이름 (예: "task-20250211-153000/impl-1")
        """
        return f"{task_id}/impl-{impl_id}"

    def get_change_summary(self, worktree_path: Path) -> Dict:
        """worktree의 변경 사항 요약을 반환한다.

        Args:
            worktree_path: worktree 경로

        Returns:
            변경 요약 딕셔너리:
                - files_changed: 변경된 파일 수
                - insertions: 추가된 라인 수
                - deletions: 삭제된 라인 수
                - changed_files: 변경된 파일 목록
        """
        try:
            # git diff --stat
            result = self._run_git(
                ['diff', '--stat', f'origin/{self.default_branch}...HEAD'],
                cwd=worktree_path,
                capture=True
            )

            # 변경된 파일 목록
            files_result = self._run_git(
                ['diff', '--name-only', f'origin/{self.default_branch}...HEAD'],
                cwd=worktree_path,
                capture=True
            )
            changed_files = [
                f for f in files_result.strip().split('\n') if f
            ]

            # 숫자 추출 시도
            stat_line = result.strip().split('\n')[-1] if result.strip() else ""
            files_changed = len(changed_files)
            insertions = 0
            deletions = 0

            import re
            ins_match = re.search(r'(\d+)\s+insertion', stat_line)
            del_match = re.search(r'(\d+)\s+deletion', stat_line)
            if ins_match:
                insertions = int(ins_match.group(1))
            if del_match:
                deletions = int(del_match.group(1))

            return {
                'files_changed': files_changed,
                'insertions': insertions,
                'deletions': deletions,
                'changed_files': changed_files,
                'stat': result.strip()
            }

        except GitError:
            return {
                'files_changed': 0,
                'insertions': 0,
                'deletions': 0,
                'changed_files': [],
                'stat': ''
            }

    def list_worktrees(self) -> List[Dict]:
        """현재 활성 worktree 목록을 반환한다."""
        try:
            result = self._run_git(
                ['worktree', 'list', '--porcelain'],
                cwd=self.clone_dir,
                capture=True
            )
            worktrees = []
            current = {}
            for line in result.strip().split('\n'):
                if line.startswith('worktree '):
                    if current:
                        worktrees.append(current)
                    current = {'path': line[len('worktree '):]}
                elif line.startswith('branch '):
                    current['branch'] = line[len('branch '):]
                elif line == '':
                    if current:
                        worktrees.append(current)
                    current = {}
            if current:
                worktrees.append(current)
            return worktrees
        except GitError:
            return []

    def _run_git(
        self,
        args: List[str],
        cwd: Optional[Path] = None,
        capture: bool = False
    ) -> str:
        """git 명령을 실행한다.

        Args:
            args: git 명령 인자 리스트
            cwd: 작업 디렉토리
            capture: True이면 stdout 반환

        Returns:
            capture=True일 때 stdout 텍스트

        Raises:
            GitError: 명령 실패 시
        """
        cmd = ['git'] + args
        logger.debug(f"git 실행: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                raise GitError(
                    f"git 명령 실패 (exit {result.returncode}): "
                    f"{' '.join(args)}\n{error_msg}"
                )

            return result.stdout if capture else ""

        except subprocess.TimeoutExpired:
            raise GitError(f"git 명령 타임아웃: {' '.join(args)}")
        except FileNotFoundError:
            raise GitError("git이 설치되어 있지 않습니다.")
