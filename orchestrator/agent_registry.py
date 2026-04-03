"""Agent registry — maps agents to their skill definitions and output schemas.

Provides a centralized mapping between agent names, skill files, output schemas,
and agent classes. Used by the Orchestrator to dynamically resolve what each
agent needs at runtime.
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Optional, Type

from .skill_loader import SkillLoader, SkillDefinition
from .schema_validator import SchemaValidator, ValidationResult


logger = logging.getLogger(__name__)


@dataclass
class AgentSpec:
    """Specification for a single agent in the pipeline."""
    name: str
    skill_name: str
    output_schema: str
    prompt_file: Optional[str] = None  # legacy prompt in prompts/ (fallback)
    checkpoint_key: Optional[str] = None


# Default pipeline agent specifications.
# skill_name maps to skills/skill-{name}.md
# output_schema maps to schemas/{name}.schema.json
# prompt_file maps to prompts/{name}.md (legacy fallback)
_DEFAULT_SPECS: list[AgentSpec] = [
    AgentSpec(
        name="planner",
        skill_name="planner",
        output_schema="requirements",
        checkpoint_key="requirements",
    ),
    AgentSpec(
        name="pm",
        skill_name="pm",
        output_schema="execution-plan",
        checkpoint_key="execution_plan",
    ),
    AgentSpec(
        name="architect",
        skill_name="architect",
        output_schema="approaches",
        prompt_file="architect.md",
        checkpoint_key="approaches",
    ),
    AgentSpec(
        name="implementer",
        skill_name="implementer",
        output_schema="work-done",
        prompt_file="implementer.md",
        checkpoint_key="implementation",
    ),
    AgentSpec(
        name="reviewer",
        skill_name="reviewer",
        output_schema="review",
        prompt_file="reviewer.md",
        checkpoint_key="review",
    ),
    AgentSpec(
        name="tester",
        skill_name="tester",
        output_schema="test-results",
        prompt_file="tester.md",
        checkpoint_key="test",
    ),
    AgentSpec(
        name="comparator",
        skill_name="comparator",
        output_schema="comparison",
        prompt_file="comparator.md",
        checkpoint_key="comparison",
    ),
    AgentSpec(
        name="integrator",
        skill_name="integrator",
        output_schema="integration-report",
        prompt_file="integrator.md",
        checkpoint_key="integration",
    ),
    AgentSpec(
        name="simplifier",
        skill_name="simplifier",
        output_schema="simplification",
        prompt_file="simplifier.md",
        checkpoint_key="simplification",
    ),
]


class AgentRegistry:
    """Central registry that resolves agent names to skills, schemas, and prompts.

    Usage:
        registry = AgentRegistry(
            skills_dir=Path("skills"),
            schemas_dir=Path("schemas"),
            prompts_dir=Path("prompts"),
        )

        # Get the skill definition for an agent
        skill = registry.get_skill("architect")

        # Get the prompt file path (skill body or legacy fallback)
        prompt_path = registry.get_prompt_path("architect")

        # Validate an agent's output
        result = registry.validate_output("architect", approaches_data)
    """

    def __init__(
        self,
        skills_dir: Path,
        schemas_dir: Path,
        prompts_dir: Path,
        validation_mode: str = "warn",
    ):
        self.skills_dir = Path(skills_dir)
        self.schemas_dir = Path(schemas_dir)
        self.prompts_dir = Path(prompts_dir)

        self.skill_loader = SkillLoader(self.skills_dir)
        self.schema_validator = SchemaValidator(self.schemas_dir, mode=validation_mode)

        # Build lookup from default specs
        self._specs: Dict[str, AgentSpec] = {s.name: s for s in _DEFAULT_SPECS}

    def get_spec(self, agent_name: str) -> AgentSpec:
        """Get the AgentSpec for a given agent name.

        Raises:
            KeyError: If the agent name is not registered.
        """
        if agent_name not in self._specs:
            raise KeyError(
                f"Unknown agent: {agent_name}. "
                f"Available: {sorted(self._specs.keys())}"
            )
        return self._specs[agent_name]

    def get_skill(self, agent_name: str) -> Optional[SkillDefinition]:
        """Load the skill definition for an agent.

        Returns None if the skill file does not exist (falls back to legacy prompt).
        """
        spec = self.get_spec(agent_name)
        try:
            return self.skill_loader.load(spec.skill_name)
        except FileNotFoundError:
            logger.debug(f"No skill file for {agent_name}, will use legacy prompt")
            return None

    def get_prompt_path(self, agent_name: str) -> Path:
        """Resolve the prompt file path for an agent.

        Priority: skill file > legacy prompt file.

        Returns:
            Path to the prompt/skill file.

        Raises:
            FileNotFoundError: If neither skill nor legacy prompt exists.
        """
        spec = self.get_spec(agent_name)

        # Try skill file first
        skill_path = self.skills_dir / f"skill-{spec.skill_name}.md"
        if skill_path.exists():
            return skill_path

        # Fall back to legacy prompt
        if spec.prompt_file:
            legacy_path = self.prompts_dir / spec.prompt_file
            if legacy_path.exists():
                return legacy_path

        raise FileNotFoundError(
            f"No prompt found for {agent_name}. "
            f"Checked: {skill_path}, "
            f"{self.prompts_dir / (spec.prompt_file or '')}"
        )

    def validate_output(self, agent_name: str, data: dict) -> ValidationResult:
        """Validate an agent's output against its schema.

        Args:
            agent_name: Agent name (e.g. 'architect').
            data: Output data to validate.

        Returns:
            ValidationResult.
        """
        spec = self.get_spec(agent_name)
        return self.schema_validator.validate(data, spec.output_schema)

    def get_checkpoint_key(self, agent_name: str) -> Optional[str]:
        """Get the manifest checkpoint key for an agent."""
        return self.get_spec(agent_name).checkpoint_key

    def list_agents(self) -> list[str]:
        """Return sorted list of registered agent names."""
        return sorted(self._specs.keys())

    def list_pipeline_order(self) -> list[str]:
        """Return agent names in pipeline execution order."""
        return [s.name for s in _DEFAULT_SPECS]
