from __future__ import annotations
import pytest
from engine.protocol.errors import ValidationError
from engine.protocol.identity import validate_account_id, validate_symbol

def test_validate_account_id_rejects_path_separators() -> None:
    with pytest.raises(ValidationError, match='path traversal'):
        validate_account_id('../12345', 'tests.identity')

def test_validate_account_id_rejects_parent_directory_sequence() -> None:
    with pytest.raises(ValidationError, match='path traversal'):
        validate_account_id('..', 'tests.identity')

def test_validate_symbol_rejects_backslash() -> None:
    with pytest.raises(ValidationError, match='path separators'):
        validate_symbol('EUR\\USD', 'tests.identity')

def test_validate_symbol_rejects_control_characters() -> None:
    with pytest.raises(ValidationError, match='control characters'):
        validate_symbol('EUR\x00USD', 'tests.identity')
