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
        pipeline_mode = context.get('pipeline_mode', 'alternative')
        api_contract_path = context.get('api_contract_path', '')
        architect_context = context.get('architect_context', '')
        architect_summary_path = context.get('architect_summary_path', '')

        if not approach:
            return {
                'success': False,
                'error': '접근법이 제공되지 않았습니다'
            }

        is_retry = context.get('retry', False)
        review_feedback = context.get('review_feedback', '')

        if is_retry:
            logger.info(
                f"Implementer {self.approach_id}: "
                f"리뷰 피드백 기반 재구현 시작"
            )
        else:
            logger.info(f"Implementer {self.approach_id}: 구현 시작")

        # 접근법 설명 포매팅
        approach_desc = self._format_approach(approach)

        # 재시도 시 리뷰 피드백을 포함한 추가 지시사항 구성
        retry_instruction = ''
        if is_retry and review_feedback:
            retry_instruction = self._build_retry_instruction(review_feedback)

        # 프롬프트 로드 및 포매팅
        prompt = self.load_prompt(
            self.prompt_file,
            spec_content=spec_content,
            approach=approach_desc,
            approach_id=self.approach_id,
            project_context_path=project_context_path,
            pipeline_mode=pipeline_mode,
            api_contract_path=api_contract_path,
            architect_context=architect_context,
            architect_summary_path=architect_summary_path,
        )

        # 재시도인 경우 프롬프트 끝에 리뷰 피드백 추가
        if retry_instruction:
            prompt = prompt + '\n\n' + retry_instruction

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

    def _build_retry_instruction(self, review_feedback: str) -> str:
        """리뷰 피드백을 기반으로 재구현 지시사항을 생성한다."""
        return f"""---

## ⚠️ 재구현 지시사항

이전 구현이 목표 달성 리뷰에서 **미달성 또는 부분 달성** 판정을 받았습니다.
아래 리뷰 피드백을 참고하여, 미달성된 요구사항을 **반드시 해결**하세요.

### 이전 리뷰 피드백

{review_feedback}

### 주의사항

1. 리뷰에서 지적된 **미달성 요구사항**에 집중하세요
2. 이미 달성된 부분은 유지하면서 부족한 부분만 보완하세요
3. 기존 코드 위에서 수정하세요 (처음부터 다시 작성하지 마세요)
4. work-done.md를 업데이트하여 수정 내용을 반영하세요
"""
