from __future__ import annotations
from engine.protocol.constants import UNIVERSE_FORBIDDEN_FIELDS

def is_universe_forbidden_field(field_name: str) -> bool:
    return field_name in UNIVERSE_FORBIDDEN_FIELDS

def universe_json_contains_forbidden_fields(json_text: str) -> list[str]:
    return [field for field in UNIVERSE_FORBIDDEN_FIELDS if f'"{field}"' in json_text]
