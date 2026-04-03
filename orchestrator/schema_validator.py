"""Schema validator — validates JSON outputs against JSON Schema definitions.

Loads schemas from schemas/*.schema.json and validates agent outputs.
Supports strict (raise on error) and warn (log and continue) modes.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False


logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of a schema validation."""

    __slots__ = ('valid', 'errors', 'schema_name')

    def __init__(self, valid: bool, errors: list[str], schema_name: str):
        self.valid = valid
        self.errors = errors
        self.schema_name = schema_name

    def __bool__(self) -> bool:
        return self.valid

    def __repr__(self) -> str:
        status = "PASS" if self.valid else f"FAIL ({len(self.errors)} errors)"
        return f"ValidationResult({self.schema_name}: {status})"


class SchemaValidator:
    """Validates JSON data against JSON Schema files."""

    def __init__(self, schemas_dir: Path, mode: str = "warn"):
        """
        Args:
            schemas_dir: Directory containing *.schema.json files.
            mode: "strict" raises on validation failure, "warn" logs and continues.
        """
        self.schemas_dir = Path(schemas_dir)
        if not self.schemas_dir.is_dir():
            raise FileNotFoundError(f"Schemas directory not found: {self.schemas_dir}")

        self.mode = mode
        self._cache: Dict[str, dict] = {}

        if not HAS_JSONSCHEMA:
            logger.warning(
                "jsonschema package not installed. "
                "Schema validation will be skipped. "
                "Install with: pip install jsonschema"
            )

    def load_schema(self, schema_name: str) -> dict:
        """Load a schema by name (e.g. 'approaches' loads approaches.schema.json).

        Args:
            schema_name: Short name without '.schema.json' suffix.

        Returns:
            Parsed JSON Schema dict.
        """
        if schema_name in self._cache:
            return self._cache[schema_name]

        file_path = self.schemas_dir / f"{schema_name}.schema.json"
        if not file_path.exists():
            raise FileNotFoundError(f"Schema file not found: {file_path}")

        schema = json.loads(file_path.read_text(encoding='utf-8'))
        self._cache[schema_name] = schema
        logger.debug(f"Loaded schema: {schema_name} from {file_path}")
        return schema

    def validate(self, data: dict, schema_name: str) -> ValidationResult:
        """Validate data against a named schema.

        Args:
            data: JSON-serializable dict to validate.
            schema_name: Schema name (e.g. 'approaches', 'review').

        Returns:
            ValidationResult with valid flag and error list.
        """
        if not HAS_JSONSCHEMA:
            logger.debug(f"Skipping validation for {schema_name} (jsonschema not installed)")
            return ValidationResult(valid=True, errors=[], schema_name=schema_name)

        try:
            schema = self.load_schema(schema_name)
        except FileNotFoundError as e:
            msg = str(e)
            logger.warning(msg)
            return ValidationResult(valid=False, errors=[msg], schema_name=schema_name)

        errors = []
        validator = jsonschema.Draft7Validator(schema)
        for error in sorted(validator.iter_errors(data), key=lambda e: list(e.path)):
            path = ".".join(str(p) for p in error.absolute_path) or "(root)"
            errors.append(f"{path}: {error.message}")

        result = ValidationResult(
            valid=len(errors) == 0,
            errors=errors,
            schema_name=schema_name,
        )

        if not result.valid:
            if self.mode == "strict":
                error_summary = "; ".join(errors[:5])
                raise jsonschema.ValidationError(
                    f"Schema validation failed for {schema_name}: {error_summary}"
                )
            else:
                logger.warning(f"Schema validation warnings for {schema_name}: {errors[:3]}")

        return result

    def validate_file(self, json_path: Path, schema_name: str) -> ValidationResult:
        """Validate a JSON file against a named schema.

        Args:
            json_path: Path to the JSON file.
            schema_name: Schema name.

        Returns:
            ValidationResult.
        """
        data = json.loads(Path(json_path).read_text(encoding='utf-8'))
        return self.validate(data, schema_name)

    def list_schemas(self) -> list[str]:
        """Return sorted list of available schema short names."""
        return sorted(
            p.stem.removesuffix('.schema')
            for p in self.schemas_dir.glob('*.schema.json')
        )

    def clear_cache(self) -> None:
        """Clear the loaded schema cache."""
        self._cache.clear()
