"""Reviewer agent for conducting code review."""

from pathlib import Path
from typing import Dict, Any
import logging

from .base import BaseAgent


logger = logging.getLogger(__name__)


class ReviewerAgent(BaseAgent):
    """
    Reviews implementation code for quality, best practices, and issues.
    Output: review.md with detailed review comments
    """

    def __init__(
        self,
        approach_id: int,
        workspace: Path,
        executor,
        prompt_file: Path
    ):
        """
        Initialize the Reviewer agent.

        Args:
            approach_id: Approach number being reviewed
            workspace: Workspace directory
            executor: ClaudeExecutor instance
            prompt_file: Path to reviewer prompt template
        """
        super().__init__(f'reviewer-{approach_id}', workspace, executor)
        self.approach_id = approach_id
        self.prompt_file = prompt_file

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review the implementation.

        Args:
            context: Must contain 'impl_path' and 'approach' to review

        Returns:
            Dict with review results
        """
        impl_path = context.get('impl_path')
        approach = context.get('approach', {})

        if not impl_path or not Path(impl_path).exists():
            return {
                'success': False,
                'error': f'Implementation path not found: {impl_path}'
            }

        logger.info(f"Reviewer {self.approach_id} starting code review")

        # Load and format prompt
        approach_name = approach.get('name', 'Unknown')
        prompt = self.load_prompt(
            self.prompt_file,
            impl_dir=impl_path,  # reviewer.md uses {impl_dir}
            approach_name=approach_name  # reviewer.md uses {approach_name}
        )

        # Execute review
        output_file = self.workspace / 'review.md'
        result = self.execute_claude(
            prompt,
            output_file=output_file
        )

        if result['success']:
            # Parse review metrics
            review_data = {
                'approach_id': self.approach_id,
                'impl_path': str(impl_path),
                'review_file': str(output_file),
                'status': 'completed'
            }
            self.write_output('review_summary.json', review_data)

        logger.info(f"Reviewer {self.approach_id} completed")

        return result
