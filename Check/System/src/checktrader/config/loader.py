from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from checktrader.config.models import SystemConfig
from checktrader.config.validation import validate_runtime_safety
from checktrader.domain.errors import ConfigurationError

try:
    from jsonschema import Draft202012Validator
except ModuleNotFoundError:
    Draft202012Validator = None  # type: ignore[assignment,misc]

# Default example config shipped with the package
EXAMPLE_CONFIG_PATH: Path = Path(__file__).parent.parent.parent.parent / "config" / "system.example.json"


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigurationError(f"configuration file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ConfigurationError(f"configuration file is not valid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigurationError("configuration root must be a JSON object")
    return data


def validate_schema(data: dict[str, Any], schema_path: Path) -> None:
    if Draft202012Validator is None:
        return
    schema = _load_json(schema_path)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: list(e.path))
    if errors:
        raise ConfigurationError("; ".join(f"/{'/'.join(map(str, e.path))}: {e.message}" for e in errors))


def load_config(
    path: str | Path | None = None,
    schema_path: str | Path | None = None,
    *,
    validate_live: bool = True,
) -> SystemConfig:
    """
    Load and validate a SystemConfig from a JSON file.

    If `path` is None, the bundled ``config/system.example.json`` is used.
    Pass ``validate_live=False`` to skip the live-mode safety check during
    bootstrap (the bootstrap function calls it separately).
    """
    resolved = Path(path) if path is not None else EXAMPLE_CONFIG_PATH
    data = _load_json(resolved)
    if schema_path is not None:
        validate_schema(data, Path(schema_path))
    try:
        config = SystemConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigurationError(str(exc)) from exc
    if validate_live:
        validate_runtime_safety(config)
    return config
