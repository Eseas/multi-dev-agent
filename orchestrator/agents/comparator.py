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
        """Gather all comparison data for each implementation."""
        data = []

        for impl in implementations:
            impl_data = {
                'approach_id': impl.get('approach_id'),
                'path': impl.get('path'),
                'approach': impl.get('approach', {}),
            }

            # Try to read review
            review_path = Path(impl['path']) / 'review.md'
            if review_path.exists():
                impl_data['review'] = review_path.read_text()

            # Try to read test results
            test_results_path = Path(impl['path']) / 'test_results.json'
            if test_results_path.exists():
                try:
                    import json
                    impl_data['test_results'] = json.loads(test_results_path.read_text())
                except json.JSONDecodeError:
                    pass

            data.append(impl_data)

        return data

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
