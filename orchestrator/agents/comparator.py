"""Comparator agent for comparing all implementations."""

from pathlib import Path
from typing import Dict, Any, List
import logging

from .base import BaseAgent


logger = logging.getLogger(__name__)


class ComparatorAgent(BaseAgent):
    """
    Compares all implementations, reviews, and test results.
    Output: comparison.md and rankings.json
    """

    def __init__(self, workspace: Path, executor, prompt_file: Path):
        """
        Initialize the Comparator agent.

        Args:
            workspace: Workspace directory
            executor: ClaudeExecutor instance
            prompt_file: Path to comparator prompt template
        """
        super().__init__('comparator', workspace, executor)
        self.prompt_file = prompt_file

    def run(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Compare all implementations and rank them.

        Args:
            context: Must contain 'implementations' list with paths and metadata

        Returns:
            Dict with comparison results and rankings
        """
        implementations = context.get('implementations', [])

        if not implementations:
            return {
                'success': False,
                'error': 'No implementations to compare'
            }

        logger.info(f"Comparator analyzing {len(implementations)} implementations")

        # Gather all data
        comparison_data = self._gather_comparison_data(implementations)

        # Format for prompt
        comparison_text = self._format_comparison_data(comparison_data)

        # Load and format prompt
        prompt = self.load_prompt(
            self.prompt_file,
            num_implementations=len(implementations),
            comparison_data=comparison_text
        )

        # Execute comparison
        output_file = self.workspace / 'comparison.md'
        result = self.execute_claude(
            prompt,
            output_file=output_file
        )

        if result['success']:
            # Parse rankings from output
            rankings = self._parse_rankings(result['output'], len(implementations))

            # Write rankings
            rankings_data = {
                'rankings': rankings,
                'num_implementations': len(implementations)
            }
            self.write_output('rankings.json', rankings_data)

            logger.info(f"Comparator completed with rankings: {rankings}")

            return {
                'success': True,
                'rankings': rankings,
                'comparison_file': str(output_file)
            }

        return result

    def _gather_comparison_data(self, implementations: List[Dict]) -> List[Dict]:
        """Gather all comparison data for each implementation.

        리뷰/테스트 결과 탐색 우선순위:
          1. review_workspace / test_workspace (task_dir/review-N/, test-N/)
          2. worktree 내부 fallback (impl['path']/review.md 등)
        """
        import json

        data = []

        for impl in implementations:
            impl_data = {
                'approach_id': impl.get('approach_id'),
                'path': impl.get('path'),
                'approach': impl.get('approach', {}),
            }

            # 리뷰 결과 탐색
            review_workspace = impl.get('review_workspace', '')
            review_content = self._find_review(review_workspace, impl.get('path', ''))
            if review_content:
                impl_data['review'] = review_content

            # 테스트 결과 탐색
            test_workspace = impl.get('test_workspace', '')
            test_results = self._find_test_results(test_workspace, impl.get('path', ''))
            if test_results is not None:
                impl_data['test_results'] = test_results

            data.append(impl_data)

        return data

    def _find_review(self, review_workspace: str, impl_path: str) -> str:
        """리뷰 결과를 탐색한다."""
        # 1순위: review_workspace 내 review.md
        if review_workspace:
            ws = Path(review_workspace)
            for name in ('review.md', 'code-review.md'):
                candidate = ws / name
                if candidate.exists():
                    return candidate.read_text()

        # 2순위: worktree 내부 fallback
        if impl_path:
            fallback = Path(impl_path) / 'review.md'
            if fallback.exists():
                return fallback.read_text()

        return ''

    def _find_test_results(self, test_workspace: str, impl_path: str):
        """테스트 결과를 탐색한다."""
        import json

        # 1순위: test_workspace 내 test_results.json
        if test_workspace:
            ws = Path(test_workspace)
            for name in ('test_results.json', 'test-results.json'):
                candidate = ws / name
                if candidate.exists():
                    try:
                        return json.loads(candidate.read_text())
                    except json.JSONDecodeError:
                        pass

        # 2순위: worktree 내부 fallback
        if impl_path:
            fallback = Path(impl_path) / 'test_results.json'
            if fallback.exists():
                try:
                    return json.loads(fallback.read_text())
                except json.JSONDecodeError:
                    pass

        return None

    def _format_comparison_data(self, data: List[Dict]) -> str:
        """Format comparison data for the prompt."""
        lines = []

        for impl in data:
            lines.append(f"\n## Implementation {impl['approach_id']}")
            lines.append(f"\nPath: {impl['path']}")

            if 'approach' in impl:
                approach = impl['approach']
                lines.append(f"\nApproach: {approach.get('name', 'N/A')}")
                if 'description' in approach:
                    lines.append(f"Description: {approach['description']}")

            if 'review' in impl:
                lines.append(f"\n### Code Review\n{impl['review'][:500]}...")

            if 'test_results' in impl:
                lines.append(f"\n### Test Results\n{impl['test_results']}")

            lines.append("\n---")

        return '\n'.join(lines)

    def _parse_rankings(self, output: str, num_implementations: int) -> List[int]:
        """
        Parse rankings from comparator output.

        Args:
            output: Raw output from Claude
            num_implementations: Total number of implementations

        Returns:
            List of approach IDs in ranked order (best first)
        """
        import json
        import re

        # Try to find JSON rankings
        json_match = re.search(r'```json\s*(\[.*?\])\s*```', output, re.DOTALL)

        if json_match:
            try:
                rankings = json.loads(json_match.group(1))
                if isinstance(rankings, list) and len(rankings) == num_implementations:
                    return rankings
            except json.JSONDecodeError:
                pass

        # Default to sequential ranking if parsing fails
        logger.warning("Could not parse rankings, using default order")
        return list(range(1, num_implementations + 1))
