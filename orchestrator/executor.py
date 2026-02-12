"""Claude Code executor for running headless Claude instances."""

import subprocess
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
import json
from datetime import datetime


logger = logging.getLogger(__name__)

# 재시도해도 의미 없는 에러 패턴 (즉시 중단)
_NON_RETRYABLE_PATTERNS = [
    "hit your limit",
    "rate limit",
    "quota exceeded",
    "billing",
    "unauthorized",
    "authentication failed",
]


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

    @staticmethod
    def _is_non_retryable(error_msg: str) -> bool:
        """재시도해도 해결되지 않는 에러인지 판별한다."""
        lower = error_msg.lower()
        return any(p in lower for p in _NON_RETRYABLE_PATTERNS)

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
        timeout_count = 0

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

                    # 대화 내역 저장
                    self._save_transcript(
                        prompt=prompt,
                        output=result['output'],
                        working_dir=working_dir,
                        success=True,
                        duration=duration,
                        returncode=0
                    )

                    result['duration'] = duration
                    return result

                last_error = result.get('error', 'Unknown error')
                logger.warning(f"Claude execution failed: {last_error}")

                # Rate limit 등 재시도 무의미한 에러 → 즉시 중단
                if self._is_non_retryable(last_error):
                    logger.error(
                        f"재시도 불가 에러 감지, 즉시 중단: {last_error}"
                    )
                    # 대화 내역 저장 (디버깅용)
                    self._save_transcript(
                        prompt=prompt,
                        output=result.get('output', ''),
                        working_dir=working_dir,
                        success=False,
                        duration=duration,
                        returncode=-1
                    )
                    return {
                        'success': False,
                        'output': result.get('output', ''),
                        'error': last_error,
                        'duration': duration
                    }

                # 타임아웃 연속 발생 → 재시도해도 같은 결과
                if 'timed out' in last_error.lower():
                    timeout_count += 1
                    if timeout_count >= 2:
                        logger.error(
                            f"연속 타임아웃 {timeout_count}회, "
                            f"재시도 중단 (timeout={self.timeout}s 증가 필요)"
                        )
                        error_msg = (
                            f'연속 타임아웃 {timeout_count}회. '
                            f'config.yaml의 execution.timeout '
                            f'(현재 {self.timeout}s)을 늘려주세요.'
                        )
                        # 대화 내역 저장 (디버깅용)
                        self._save_transcript(
                            prompt=prompt,
                            output=f"[TIMEOUT] {error_msg}",
                            working_dir=working_dir,
                            success=False,
                            duration=0,
                            returncode=-1
                        )
                        return {
                            'success': False,
                            'output': '',
                            'error': error_msg,
                            'duration': 0
                        }

            except Exception as e:
                last_error = str(e)
                logger.error(f"Exception during Claude execution: {e}", exc_info=True)

            if attempt < self.max_retries:
                logger.info(f"Retrying in {self.retry_delay} seconds...")
                time.sleep(self.retry_delay)

        # All retries failed
        # 실패한 경우에도 대화 내역 저장 (디버깅용)
        self._save_transcript(
            prompt=prompt,
            output=f"[FAILED] {last_error}",
            working_dir=working_dir,
            success=False,
            duration=0,
            returncode=-1
        )

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
        # Create .claude/settings in working_dir to enable auto-approval
        # Create both settings.json and settings.local.json since local has higher priority
        claude_dir = working_dir / '.claude'
        claude_dir.mkdir(exist_ok=True)

        settings = {
            "permissionMode": "dontAsk",
            "permissions": {
                "allow": [
                    "Bash(*)",
                    "Write(*)",
                    "Edit(*)",
                    "Read(*)",
                    "Glob(*)",
                    "Grep(*)"
                ]
            }
        }

        # Write both settings.json and settings.local.json
        # settings.local.json has higher priority, so it's critical
        settings_json = claude_dir / 'settings.json'
        settings_local = claude_dir / 'settings.local.json'

        settings_content = json.dumps(settings, indent=2)
        settings_json.write_text(settings_content, encoding='utf-8')
        settings_local.write_text(settings_content, encoding='utf-8')

        # Build command with permission mode to avoid approval prompts
        cmd = ['claude', '-p', prompt, '--permission-mode=dontAsk']

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
                    error_msg = stderr.strip() or stdout.strip() or f'Process exited with code {returncode}'
                    return {
                        'success': False,
                        'output': stdout,
                        'error': error_msg
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

    def _save_transcript(
        self,
        prompt: str,
        output: str,
        working_dir: Path,
        success: bool,
        duration: float,
        returncode: int
    ) -> None:
        """
        대화 내역을 파일로 저장한다.

        1. 각 Phase별 conversation.txt에 저장 (기존)
        2. task-level full-conversation.txt에 append (신규)

        Args:
            prompt: 전송한 프롬프트
            output: Claude의 출력
            working_dir: 작업 디렉토리
            success: 실행 성공 여부
            duration: 실행 시간 (초)
            returncode: 종료 코드
        """
        try:
            timestamp = datetime.now().isoformat()

            # 1. 각 Phase별 conversation.txt 저장 (기존)
            transcript_path = working_dir / 'conversation.txt'
            transcript_content = f"""=== CONVERSATION TRANSCRIPT ===
Generated at: {timestamp}

=== PROMPT ===
{prompt}

=== CLAUDE OUTPUT ===
{output}

=== EXECUTION METADATA ===
Working Directory: {working_dir}
Success: {success}
Duration: {duration:.2f}s
Exit Code: {returncode}
Timestamp: {timestamp}
"""

            transcript_path.write_text(transcript_content, encoding='utf-8')
            logger.debug(f"Conversation transcript saved to {transcript_path}")

            # 2. task-level full-conversation.txt에 append (신규)
            self._append_to_full_transcript(
                prompt=prompt,
                output=output,
                working_dir=working_dir,
                success=success,
                duration=duration,
                returncode=returncode,
                timestamp=timestamp
            )

        except Exception as e:
            # 대화 내역 저장 실패는 치명적이지 않음 (로그만 남김)
            logger.warning(f"Failed to save conversation transcript: {e}")

    def _append_to_full_transcript(
        self,
        prompt: str,
        output: str,
        working_dir: Path,
        success: bool,
        duration: float,
        returncode: int,
        timestamp: str
    ) -> None:
        """
        전체 대화 내역 파일에 append한다.

        working_dir에서 task_dir을 추론하여 full-conversation.txt에 저장.
        패턴: workspace/tasks/task-YYYYMMDD-HHMMSS/

        Args:
            prompt: 전송한 프롬프트
            output: Claude의 출력
            working_dir: 작업 디렉토리
            success: 실행 성공 여부
            duration: 실행 시간 (초)
            returncode: 종료 코드
            timestamp: ISO 타임스탬프
        """
        try:
            import re

            # working_dir에서 task_dir 추출
            # 패턴: .../workspace/tasks/task-YYYYMMDD-HHMMSS/...
            working_dir_str = str(working_dir.resolve())
            match = re.search(r'(.*?/workspace/tasks/(task-\d{8}-\d{6}))', working_dir_str)

            if not match:
                # task 디렉토리가 아니면 스킵
                logger.debug(f"Not a task directory, skipping full transcript: {working_dir}")
                return

            task_dir = Path(match.group(1)).resolve()
            task_id = match.group(2)

            # Phase 이름 추론 (working_dir에서)
            # resolve()로 실제 경로 변환 (심볼릭 링크 해결)
            working_dir_resolved = working_dir.resolve()
            relative_path = working_dir_resolved.relative_to(task_dir)
            phase_name = self._infer_phase_name(relative_path)

            # full-conversation.txt 경로
            full_transcript_path = task_dir / 'full-conversation.txt'

            # append 모드로 저장
            phase_entry = f"""
===== TASK: {task_id} =====
===== {phase_name} =====
Timestamp: {timestamp}
Working Directory: {working_dir}
Duration: {duration:.2f}s
Success: {success}
Exit Code: {returncode}

=== PROMPT ===
{prompt}

=== CLAUDE OUTPUT ===
{output}

========================================

"""

            with open(full_transcript_path, 'a', encoding='utf-8') as f:
                f.write(phase_entry)

            logger.debug(f"Appended to full transcript: {full_transcript_path}")

        except Exception as e:
            logger.debug(f"Failed to append to full transcript: {e}")

    def _infer_phase_name(self, relative_path: Path) -> str:
        """
        relative_path에서 Phase 이름을 추론한다.

        예시:
        - architect/ → "PHASE 1: ARCHITECT"
        - implementations/impl-1/ → "PHASE 2: IMPLEMENTER 1"
        - review-1/ → "PHASE 3: REVIEWER 1"
        - test-2/ → "PHASE 3: TESTER 2"
        - comparator/ → "PHASE 4: COMPARATOR"
        """
        parts = relative_path.parts

        if not parts:
            return "UNKNOWN PHASE"

        first_part = parts[0]

        # Architect
        if first_part == 'architect':
            return "PHASE 1: ARCHITECT"

        # Implementer
        if first_part == 'implementations' and len(parts) > 1:
            impl_num = parts[1].replace('impl-', '')
            return f"PHASE 2: IMPLEMENTER {impl_num}"

        # Reviewer
        if first_part.startswith('review-'):
            review_num = first_part.replace('review-', '')
            return f"PHASE 3: REVIEWER {review_num}"

        # Tester
        if first_part.startswith('test-'):
            test_num = first_part.replace('test-', '')
            return f"PHASE 3: TESTER {test_num}"

        # Comparator
        if first_part == 'comparator':
            return "PHASE 4: COMPARATOR"

        # Unknown
        return f"PHASE UNKNOWN: {first_part}"
