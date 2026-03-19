"""Simplifier agent: reviews final implementation for complexity and documents design rationale."""

from pathlib import Path
from typing import Dict, Any, Optional
import logging

from .base import BaseAgent


logger = logging.getLogger(__name__)


class SimplifierAgent(BaseAgent):
    """
    Phase 5 agent that runs after all implementations are complete.

    Two outputs:
    - simplification-review.md: Identifies over-engineered code and suggests
      concrete simplifications without changing functionality.
    - dev-rationale.md: Documents WHY the code was written this way — design
      decisions, trade-offs, considered alternatives. Serves as the foundation
      for a cumulative development guideline document.
    """

    def __init__(
        self,
        approach_id: int,
        workspace: Path,
        executor,
        prompt_file: Path
    ):
        super().__init__(f'simplifier-{approach_id}', workspace, executor)
        self.approach_id = approach_id
        self.prompt_file = prompt_file

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Analyze implementation for complexity and produce rationale docs.

        Args:
            context: Must contain:
                - impl_path: Path to the final implementation directory
                - approach: Approach dict (name, description, etc.)
                - spec_path: Path to the planning spec
                - architect_summary_path: Path to architect-summary.md
                - comparison_file (optional): Path to comparator comparison.md

        Returns:
            Dict with success, simplification_file, rationale_file paths
        """
        impl_path = context.get('impl_path')
        approach = context.get('approach', {})
        spec_path = context.get('spec_path', '')
        architect_summary_path = context.get('architect_summary_path', '')
        comparison_file = context.get('comparison_file')

        if not impl_path or not Path(impl_path).exists():
            return {
                'success': False,
                'error': f'Implementation path not found: {impl_path}'
            }

        logger.info(
            f"SimplifierAgent {self.approach_id}: "
            f"analysing {impl_path}"
        )

        approach_name = approach.get('name', f'impl-{self.approach_id}')

        # Build the optional comparator section only when available
        if comparison_file and Path(comparison_file).exists():
            comparator_section = (
                f"**비교 분석 보고서**: {comparison_file}\n"
                "(여러 접근법이 비교된 경우 이 파일을 참고하여 "
                "왜 이 접근법이 선택되었는지 근거에 포함하세요.)"
            )
        else:
            comparator_section = ""

        prompt = self.load_prompt(
            self.prompt_file,
            impl_dir=impl_path,
            approach_name=approach_name,
            spec_path=spec_path,
            architect_summary_path=architect_summary_path,
            comparator_section=comparator_section,
        )

        result = self.execute_claude(prompt, working_dir=self.workspace)

        if not result['success']:
            return {
                'success': False,
                'error': result.get('error', 'Claude execution failed')
            }

        simplification_file = self.workspace / 'simplification-review.md'
        rationale_file = self.workspace / 'dev-rationale.md'

        # Verify outputs were created
        missing = [
            str(f) for f in [simplification_file, rationale_file]
            if not f.exists()
        ]
        if missing:
            logger.warning(
                f"SimplifierAgent {self.approach_id}: "
                f"expected output(s) not found: {missing}"
            )

        return {
            'success': True,
            'approach_id': self.approach_id,
            'simplification_file': (
                str(simplification_file)
                if simplification_file.exists() else None
            ),
            'rationale_file': (
                str(rationale_file)
                if rationale_file.exists() else None
            ),
        }
