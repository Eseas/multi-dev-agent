"""Base agent class for all orchestrator agents."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional
import logging
import json
from datetime import datetime

from ..executor import ClaudeExecutor
from ..utils.atomic_write import atomic_write


logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the orchestrator.
    Provides common functionality for execution and state management.
    """

    def __init__(
        self,
        name: str,
        workspace: Path,
        executor: ClaudeExecutor,
        prompt_template: Optional[str] = None
    ):
        """
        Initialize the agent.

        Args:
            name: Agent name/identifier
            workspace: Workspace directory path
            executor: Claude executor instance
            prompt_template: Optional prompt template string
        """
        self.name = name
        self.workspace = Path(workspace)
        self.executor = executor
        self.prompt_template = prompt_template
        self.state = {
            'status': 'initialized',
            'created_at': datetime.now().isoformat(),
            'updated_at': datetime.now().isoformat()
        }

        # Create agent workspace
        self.workspace.mkdir(parents=True, exist_ok=True)
        self.state_file = self.workspace / f'{name}_state.json'

    @abstractmethod
    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the agent's main task.

        Args:
            context: Execution context with input data

        Returns:
            Dict containing execution results
        """
        pass

    def update_state(self, updates: Dict[str, Any]) -> None:
        """
        Update agent state.

        Args:
            updates: Dict of state updates
        """
        self.state.update(updates)
        self.state['updated_at'] = datetime.now().isoformat()
        self._save_state()

    def _save_state(self) -> None:
        """Save current state to file."""
        atomic_write(self.state_file, self.state)

    def _load_state(self) -> Dict[str, Any]:
        """Load state from file."""
        if self.state_file.exists():
            try:
                return json.loads(self.state_file.read_text())
            except json.JSONDecodeError:
                logger.warning(f"Failed to load state for {self.name}")
        return {}

    def load_prompt(self, prompt_file: Path, **kwargs) -> str:
        """
        Load and format a prompt template.

        Args:
            prompt_file: Path to prompt template file
            **kwargs: Variables to substitute in template

        Returns:
            Formatted prompt string
        """
        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_file}")

        template = prompt_file.read_text()

        # Simple string substitution
        for key, value in kwargs.items():
            placeholder = f"{{{key}}}"
            template = template.replace(placeholder, str(value))

        return template

    def execute_claude(
        self,
        prompt: str,
        working_dir: Optional[Path] = None,
        output_file: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        Execute Claude with the given prompt.

        Args:
            prompt: Prompt to execute
            working_dir: Optional working directory (defaults to agent workspace)
            output_file: Optional output file path

        Returns:
            Execution result dict
        """
        if working_dir is None:
            working_dir = self.workspace

        self.update_state({'status': 'running'})

        result = self.executor.execute(
            prompt=prompt,
            working_dir=working_dir,
            output_file=output_file
        )

        if result['success']:
            self.update_state({'status': 'completed'})
        else:
            self.update_state({
                'status': 'failed',
                'error': result.get('error', 'Unknown error')
            })

        return result

    def write_output(self, filename: str, content: Any) -> Path:
        """
        Write output to a file in the workspace.

        Args:
            filename: Output filename
            content: Content to write (str or dict)

        Returns:
            Path to written file
        """
        output_path = self.workspace / filename
        atomic_write(output_path, content)
        logger.info(f"Wrote output: {output_path}")
        return output_path

    def read_input(self, filename: str) -> Any:
        """
        Read input from workspace.

        Args:
            filename: Input filename

        Returns:
            Parsed content (dict for JSON, str otherwise)
        """
        input_path = self.workspace / filename

        if not input_path.exists():
            raise FileNotFoundError(f"Input file not found: {input_path}")

        content = input_path.read_text()

        # Try to parse as JSON
        if filename.endswith('.json'):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse {filename} as JSON")

        return content
