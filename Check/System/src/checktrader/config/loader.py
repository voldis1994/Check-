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
    Draft202012Validator = None

def _load_json(path: Path) -> dict[str, Any]:
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError as exc: raise ConfigurationError(f'configuration file not found: {path}') from exc
    except json.JSONDecodeError as exc: raise ConfigurationError(f'configuration file is not valid JSON: {path}: {exc}') from exc
    if not isinstance(data, dict): raise ConfigurationError('configuration root must be an object')
    return data
def validate_schema(data: dict[str, Any], schema_path: Path) -> None:
    if Draft202012Validator is None:
        return
    schema=_load_json(schema_path); errors=sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e:list(e.path))
    if errors: raise ConfigurationError('; '.join(f"/{'/'.join(map(str,e.path))}: {e.message}" for e in errors))
def load_config(path: str|Path, schema_path: str|Path|None=None, *, validate_live: bool=True) -> SystemConfig:
    data=_load_json(Path(path))
    if schema_path is not None: validate_schema(data, Path(schema_path))
    try: config=SystemConfig.model_validate(data)
    except ValidationError as exc: raise ConfigurationError(str(exc)) from exc
    if validate_live: validate_runtime_safety(config)
    return config
