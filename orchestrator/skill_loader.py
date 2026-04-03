"""Skill loader — loads skill definitions from skills/*.md files.

Parses YAML frontmatter (name, description) and markdown body.
Caches loaded skills for reuse within a session.
"""

import re
import logging
from pathlib import Path
from typing import Dict, Any, Optional

import yaml


logger = logging.getLogger(__name__)


class SkillDefinition:
    """A loaded skill definition."""

    __slots__ = ('name', 'description', 'body', 'path')

    def __init__(self, name: str, description: str, body: str, path: Path):
        self.name = name
        self.description = description
        self.body = body
        self.path = path

    def __repr__(self) -> str:
        return f"SkillDefinition(name={self.name!r})"


_FRONTMATTER_RE = re.compile(
    r'^---\s*\n(.*?)\n---\s*\n(.*)',
    re.DOTALL,
)


class SkillLoader:
    """Loads and caches skill definitions from a directory of .md files."""

    def __init__(self, skills_dir: Path):
        self.skills_dir = Path(skills_dir)
        if not self.skills_dir.is_dir():
            raise FileNotFoundError(f"Skills directory not found: {self.skills_dir}")
        self._cache: Dict[str, SkillDefinition] = {}

    def load(self, skill_name: str) -> SkillDefinition:
        """Load a skill by name (e.g. 'architect' loads skill-architect.md).

        Args:
            skill_name: Short name without 'skill-' prefix or '.md' suffix.

        Returns:
            SkillDefinition with parsed frontmatter and body.

        Raises:
            FileNotFoundError: If the skill file does not exist.
            ValueError: If frontmatter is missing or invalid.
        """
        if skill_name in self._cache:
            return self._cache[skill_name]

        file_path = self.skills_dir / f"skill-{skill_name}.md"
        if not file_path.exists():
            raise FileNotFoundError(f"Skill file not found: {file_path}")

        raw = file_path.read_text(encoding='utf-8')
        match = _FRONTMATTER_RE.match(raw)
        if not match:
            raise ValueError(f"No YAML frontmatter in {file_path}")

        try:
            meta = yaml.safe_load(match.group(1))
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML frontmatter in {file_path}: {e}")

        defn = SkillDefinition(
            name=meta.get('name', skill_name),
            description=meta.get('description', ''),
            body=match.group(2).strip(),
            path=file_path,
        )
        self._cache[skill_name] = defn
        logger.debug(f"Loaded skill: {defn.name} from {file_path}")
        return defn

    def load_all(self) -> Dict[str, SkillDefinition]:
        """Load all skill-*.md files in the directory.

        Returns:
            Dict mapping short names to SkillDefinition objects.
        """
        result = {}
        for path in sorted(self.skills_dir.glob('skill-*.md')):
            short_name = path.stem.removeprefix('skill-')
            try:
                result[short_name] = self.load(short_name)
            except (ValueError, FileNotFoundError) as e:
                logger.warning(f"Skipping {path.name}: {e}")
        return result

    def list_skills(self) -> list[str]:
        """Return sorted list of available skill short names."""
        return sorted(
            p.stem.removeprefix('skill-')
            for p in self.skills_dir.glob('skill-*.md')
        )

    def clear_cache(self) -> None:
        """Clear the loaded skill cache."""
        self._cache.clear()
