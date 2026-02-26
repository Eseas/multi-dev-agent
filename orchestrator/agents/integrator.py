"""관심사별 구현을 하나의 프로젝트로 통합하는 Integrator 에이전트."""

from pathlib import Path
from typing import Dict, Any, List
import logging

from .base import BaseAgent


logger = logging.getLogger(__name__)


class IntegratorAgent(BaseAgent):
    """
    Concern 모드에서 여러 구현체를 하나로 통합한다.
    - 머지 충돌 해결
    - 접착 코드(glue code) 작성
    - 통합 빌드 검증
    """

    def __init__(self, workspace: Path, executor, prompt_file: Path):
        """
        Args:
            workspace: 통합 작업 디렉토리
            executor: ClaudeExecutor 인스턴스
            prompt_file: integrator 프롬프트 템플릿 경로
        """
        super().__init__('integrator', workspace, executor)
        self.prompt_file = prompt_file

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """관심사별 구현을 통합한다.

        Args:
            context:
                - integration_path: 통합 워크트리 경로
                - implementations: 성공한 구현 결과 리스트
                - merge_results: 머지 시도 결과 리스트
                - api_contract_path: API 계약서 경로
                - has_conflicts: 충돌 존재 여부

        Returns:
            통합 결과 딕셔너리
        """
        integration_path = context.get('integration_path', '')
        implementations = context.get('implementations', [])
        merge_results = context.get('merge_results', [])
        api_contract_path = context.get('api_contract_path', '')
        has_conflicts = context.get('has_conflicts', False)

        if not integration_path:
            return {'success': False, 'error': '통합 경로가 없습니다'}

        logger.info(
            f"Integrator: 통합 시작 "
            f"(구현 {len(implementations)}개, 충돌={'있음' if has_conflicts else '없음'})"
        )

        impl_summary = self._format_implementations(implementations, merge_results)

        prompt = self.load_prompt(
            self.prompt_file,
            integration_path=integration_path,
            impl_summary=impl_summary,
            api_contract_path=api_contract_path,
            has_conflicts=str(has_conflicts),
        )

        output_file = self.workspace / 'integration.log'
        result = self.execute_claude(
            prompt,
            working_dir=Path(integration_path),
            output_file=output_file
        )

        logger.info(f"Integrator: 통합 {'완료' if result['success'] else '실패'}")

        return result

    def _format_implementations(
        self,
        impls: List[Dict],
        merge_results: List[Dict]
    ) -> str:
        """구현 목록을 프롬프트용 텍스트로 포매팅한다."""
        lines = []
        for impl in impls:
            branch = impl.get('branch', '')
            approach = impl.get('approach', {})
            name = approach.get('name', 'N/A')
            concern = approach.get('concern', 'N/A')
            mr = next((m for m in merge_results if m['branch'] == branch), {})
            status = 'Conflict' if mr.get('conflict') else 'Merged'
            lines.append(
                f"- {name} (concern: {concern}), "
                f"branch: {branch}, status: {status}"
            )
        return '\n'.join(lines)
