"""Tester agent for writing and executing tests."""

from pathlib import Path
from typing import Dict, Any
import logging

from .base import BaseAgent


logger = logging.getLogger(__name__)


class TesterAgent(BaseAgent):
    """
    Writes tests for implementation and executes them.
    Output: test files and test_results.json
    """

    def __init__(
        self,
        approach_id: int,
        workspace: Path,
        executor,
        prompt_file: Path
    ):
        """
        Initialize the Tester agent.

        Args:
            approach_id: Approach number being tested
            workspace: Workspace directory
            executor: ClaudeExecutor instance
            prompt_file: Path to tester prompt template
        """
        super().__init__(f'tester-{approach_id}', workspace, executor)
        self.approach_id = approach_id
        self.prompt_file = prompt_file

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Write and execute tests for the implementation.

        Args:
            context: Must contain 'impl_path'

        Returns:
            Dict with test results
        """
        impl_path = context.get('impl_path')

        if not impl_path or not Path(impl_path).exists():
            return {
                'success': False,
                'error': f'Implementation path not found: {impl_path}'
            }

        logger.info(f"Tester {self.approach_id} starting test generation")

        # Load and format prompt
        prompt = self.load_prompt(
            self.prompt_file,
            impl_path=impl_path,
            approach_id=self.approach_id
        )

        # Execute test writing and running
        output_file = self.workspace / 'test_output.log'
        result = self.execute_claude(
            prompt,
            working_dir=Path(impl_path),
            output_file=output_file
        )

        if result['success']:
            # Write test summary
            test_data = {
                'approach_id': self.approach_id,
                'impl_path': str(impl_path),
                'test_log': str(output_file),
                'status': 'completed'
            }
            self.write_output('test_results.json', test_data)

        logger.info(f"Tester {self.approach_id} completed")

        return result
