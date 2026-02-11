"""기획서를 분석하고 구현 계획을 수립하는 Architect 에이전트."""

from pathlib import Path
from typing import Dict, Any
import logging

from .base import BaseAgent


logger = logging.getLogger(__name__)


class ArchitectAgent(BaseAgent):
    """
    기획서를 분석하고 N개의 구현 계획(approaches.json)을 생성한다.
    타겟 프로젝트의 기존 코드를 분석하여 프로젝트 맥락에 맞는 계획을 수립한다.
    """

    def __init__(self, workspace: Path, executor, prompt_file: Path):
        """
        Args:
            workspace: 작업 디렉토리
            executor: ClaudeExecutor 인스턴스
            prompt_file: architect 프롬프트 템플릿 경로
        """
        super().__init__('architect', workspace, executor)
        self.prompt_file = prompt_file

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """기획서를 분석하고 구현 계획을 생성한다.

        Args:
            context:
                - spec_content: 기획서 원문 (마크다운)
                - num_approaches: 생성할 구현 계획 수 (기본값: 1)
                - project_path: 타겟 프로젝트 경로 (clone/worktree)

        Returns:
            {'success': True, 'approaches': [...], 'num_approaches': N}
        """
        spec_content = context.get('spec_content', '')
        num_approaches = context.get('num_approaches', 1)
        project_path = context.get('project_path', '')

        if not spec_content:
            return {
                'success': False,
                'error': '기획서 내용이 없습니다'
            }

        logger.info(f"Architect: {num_approaches}개 구현 계획 생성 시작")

        # 프롬프트 로드 및 포매팅
        prompt = self.load_prompt(
            self.prompt_file,
            spec_content=spec_content,
            num_approaches=num_approaches,
            project_path=project_path
        )

        # Claude 실행 (타겟 프로젝트 디렉토리에서)
        working_dir = Path(project_path) if project_path else self.workspace
        result = self.execute_claude(prompt, working_dir=working_dir)

        if not result['success']:
            return result

        # approaches 파싱
        approaches = self._parse_approaches(result['output'])

        if not approaches:
            return {
                'success': False,
                'error': 'Claude 출력에서 approaches를 파싱할 수 없습니다'
            }

        # approaches.json 저장
        approaches_data = {
            'approaches': approaches,
            'num_approaches': len(approaches)
        }
        self.write_output('approaches.json', approaches_data)

        logger.info(f"Architect: {len(approaches)}개 구현 계획 생성 완료")

        return {
            'success': True,
            'approaches': approaches,
            'num_approaches': len(approaches)
        }

    def _parse_approaches(self, output: str) -> list:
        """Claude 출력에서 approaches JSON을 파싱한다."""
        import json
        import re

        # ```json [...] ``` 블록 탐색
        json_match = re.search(r'```json\s*(\[.*?\])\s*```', output, re.DOTALL)
        if json_match:
            try:
                approaches = json.loads(json_match.group(1))
                if isinstance(approaches, list):
                    return approaches
            except json.JSONDecodeError:
                pass

        # 전체를 JSON으로 파싱 시도
        try:
            data = json.loads(output)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict) and 'approaches' in data:
                return data['approaches']
        except json.JSONDecodeError:
            pass

        logger.warning("approaches를 JSON으로 파싱할 수 없습니다")
        return []
