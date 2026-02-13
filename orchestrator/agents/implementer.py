"""특정 구현 방법을 실행하는 Implementer 에이전트."""

from pathlib import Path
from typing import Dict, Any
import logging

from .base import BaseAgent


logger = logging.getLogger(__name__)


class ImplementerAgent(BaseAgent):
    """
    할당된 접근법에 따라 타겟 프로젝트의 git worktree에서 코드를 작성한다.
    워크스페이스가 곧 타겟 프로젝트의 전체 파일이므로, 기존 코드 위에서 작업한다.
    """

    def __init__(
        self,
        approach_id: int,
        workspace: Path,
        executor,
        prompt_file: Path
    ):
        """
        Args:
            approach_id: 접근법 번호 (1부터 시작)
            workspace: git worktree 경로 (타겟 프로젝트 전체 파일 포함)
            executor: ClaudeExecutor 인스턴스
            prompt_file: implementer 프롬프트 템플릿 경로
        """
        super().__init__(f'implementer-{approach_id}', workspace, executor)
        self.approach_id = approach_id
        self.prompt_file = prompt_file

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """할당된 접근법에 따라 구현한다.

        Args:
            context:
                - approach: approaches.json의 단일 접근법 딕셔너리
                - spec_content: 기획서 원문

        Returns:
            구현 결과 딕셔너리
        """
        approach = context.get('approach', {})
        spec_content = context.get('spec_content', '')
        project_context_path = context.get('project_context_path', '')

        if not approach:
            return {
                'success': False,
                'error': '접근법이 제공되지 않았습니다'
            }

        logger.info(f"Implementer {self.approach_id}: 구현 시작")

        # 접근법 설명 포매팅
        approach_desc = self._format_approach(approach)

        # 프롬프트 로드 및 포매팅
        prompt = self.load_prompt(
            self.prompt_file,
            spec_content=spec_content,
            approach=approach_desc,
            approach_id=self.approach_id,
            project_context_path=project_context_path,
        )

        # Claude 실행 (git worktree = 타겟 프로젝트 내부에서)
        output_file = self.workspace / '.multi-agent' / 'implementation.log'
        output_file.parent.mkdir(parents=True, exist_ok=True)
        result = self.execute_claude(
            prompt,
            working_dir=self.workspace,
            output_file=output_file
        )

        if result['success']:
            # 구현 요약 저장
            summary = {
                'approach_id': self.approach_id,
                'approach': approach,
                'status': 'completed',
                'duration': result.get('duration', 0)
            }
            # .multi-agent/ 디렉토리에 메타 파일 저장
            meta_dir = self.workspace / '.multi-agent'
            meta_dir.mkdir(parents=True, exist_ok=True)

            from ..utils.atomic_write import atomic_write
            atomic_write(meta_dir / 'summary.json', summary)

        logger.info(f"Implementer {self.approach_id}: 구현 완료")

        return result

    def _format_approach(self, approach: Dict[str, Any]) -> str:
        """접근법 딕셔너리를 읽기 쉬운 텍스트로 변환한다."""
        lines = []

        if 'name' in approach:
            lines.append(f"접근법: {approach['name']}")

        if 'description' in approach:
            lines.append(f"\n설명:\n{approach['description']}")

        if 'key_decisions' in approach:
            lines.append("\n주요 결정:")
            for decision in approach['key_decisions']:
                lines.append(f"  - {decision}")

        if 'libraries' in approach:
            lines.append(f"\n라이브러리: {', '.join(approach['libraries'])}")

        if 'trade_offs' in approach:
            lines.append("\n트레이드오프:")
            for trade_off in approach['trade_offs']:
                lines.append(f"  - {trade_off}")

        return '\n'.join(lines)
