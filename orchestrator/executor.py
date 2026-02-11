"""Claude Code executor for running headless Claude instances."""

import subprocess
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import json


logger = logging.getLogger(__name__)


class ClaudeExecutor:
    """
    Executes Claude Code in headless mode and manages its lifecycle.
    """

    def __init__(
        self,
        timeout: int = 300,
        max_retries: int = 3,
        retry_delay: int = 5
    ):
        """
        Initialize the Claude executor.

        Args:
            timeout: Maximum execution time in seconds
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay

    def execute(
        self,
        prompt: str,
        working_dir: Path,
        output_file: Optional[Path] = None,
        env_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Execute Claude Code with the given prompt.

        Args:
            prompt: The prompt to send to Claude
            working_dir: Working directory for execution
            output_file: Optional file to save output
            env_vars: Optional environment variables

        Returns:
            Dict containing execution results:
                - success: bool
                - output: str
                - error: str (if failed)
                - duration: float (execution time)
        """
        working_dir = Path(working_dir)
        working_dir.mkdir(parents=True, exist_ok=True)

        attempt = 0
        last_error = None

        while attempt < self.max_retries:
            attempt += 1
            logger.info(f"Executing Claude (attempt {attempt}/{self.max_retries})")

            try:
                start_time = time.time()
                result = self._run_claude(prompt, working_dir, env_vars)
                duration = time.time() - start_time

                if result['success']:
                    logger.info(f"Claude execution successful ({duration:.2f}s)")

                    if output_file:
                        output_file.parent.mkdir(parents=True, exist_ok=True)
                        output_file.write_text(result['output'])

                    result['duration'] = duration
                    return result

                last_error = result.get('error', 'Unknown error')
                logger.warning(f"Claude execution failed: {last_error}")

            except Exception as e:
                last_error = str(e)
                logger.error(f"Exception during Claude execution: {e}", exc_info=True)

            if attempt < self.max_retries:
                logger.info(f"Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)

        # All retries failed
        return {
            'success': False,
            'output': '',
            'error': f'Failed after {self.max_retries} attempts. Last error: {last_error}',
            'duration': 0
        }

    def _run_claude(
        self,
        prompt: str,
        working_dir: Path,
        env_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Run Claude Code subprocess.

        Args:
            prompt: The prompt to send
            working_dir: Working directory
            env_vars: Optional environment variables

        Returns:
            Dict with success, output, and error
        """
        # Build command
        cmd = ['claude', '-p', prompt]

        # Prepare environment
        env = None
        if env_vars:
            import os
            env = os.environ.copy()
            env.update(env_vars)

        try:
            # Run Claude in headless mode
            process = subprocess.Popen(
                cmd,
                cwd=working_dir,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )

            # Wait with timeout
            try:
                stdout, stderr = process.communicate(timeout=self.timeout)
                returncode = process.returncode

                if returncode == 0:
                    return {
                        'success': True,
                        'output': stdout,
                        'error': ''
                    }
                else:
                    return {
                        'success': False,
                        'output': stdout,
                        'error': stderr or f'Process exited with code {returncode}'
                    }

            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
                return {
                    'success': False,
                    'output': '',
                    'error': f'Execution timed out after {self.timeout} seconds'
                }

        except FileNotFoundError:
            return {
                'success': False,
                'output': '',
                'error': 'Claude Code CLI not found. Please install it first.'
            }
        except Exception as e:
            return {
                'success': False,
                'output': '',
                'error': f'Unexpected error: {str(e)}'
            }

    def execute_with_file_prompt(
        self,
        prompt_file: Path,
        working_dir: Path,
        output_file: Optional[Path] = None,
        env_vars: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Execute Claude with a prompt loaded from a file.

        Args:
            prompt_file: Path to the prompt file
            working_dir: Working directory
            output_file: Optional output file
            env_vars: Optional environment variables

        Returns:
            Execution results dict
        """
        if not prompt_file.exists():
            return {
                'success': False,
                'output': '',
                'error': f'Prompt file not found: {prompt_file}',
                'duration': 0
            }

        prompt = prompt_file.read_text()
        return self.execute(prompt, working_dir, output_file, env_vars)
