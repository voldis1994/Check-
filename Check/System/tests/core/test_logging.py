from __future__ import annotations
import re
from pathlib import Path
import pytest
from engine.core.logging_setup import log_event, setup_account_logger, setup_system_logger
from engine.core.paths import SystemPaths
from engine.protocol.errors import ConfigurationError

def _read_single_log(logs_dir: Path, prefix: str) -> str:
    files = sorted(logs_dir.glob(f'{prefix}_*.log'))
    assert len(files) == 1
    return files[0].read_text(encoding='utf-8')

def _flush(logger) -> None:
    for handler in logger.handlers:
        handler.flush()

def test_setup_system_logger_creates_log_file_in_data_logs(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    logger = setup_system_logger(paths, level='INFO', format_name='standard')
    log_event(logger, level='INFO', module='core.test', message='startup')
    _flush(logger)
    text = _read_single_log(paths.logs_dir, 'system')
    assert 'startup' in text

def test_log_format_contains_timestamp_level_and_module(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    logger = setup_system_logger(paths, level='INFO', format_name='standard')
    log_event(logger, level='INFO', module='core.test', message='format-check')
    _flush(logger)
    line = _read_single_log(paths.logs_dir, 'system').strip()
    assert re.fullmatch('\\d{4}-\\d{2}-\\d{2}T\\d{2}:\\d{2}:\\d{2}\\.\\d{3}Z \\| INFO \\| core\\.test \\| - \\| - \\| - \\| format-check', line)

def test_setup_account_logger_creates_account_log_file(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    logger = setup_account_logger(paths, '12345', level='INFO', format_name='standard')
    log_event(logger, level='INFO', module='core.test', message='account-start', account_id='12345')
    _flush(logger)
    text = _read_single_log(paths.logs_dir, 'account_12345')
    assert 'account-start' in text
    assert ' | 12345 | ' in text

def test_all_levels_are_logged(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    logger = setup_system_logger(paths, level='DEBUG', format_name='standard')
    for level in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        log_event(logger, level=level, module='core.test', message=level.lower())
    _flush(logger)
    text = _read_single_log(paths.logs_dir, 'system')
    for level in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
        assert f' | {level} | ' in text

def test_setup_system_logger_rejects_invalid_level(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    with pytest.raises(ConfigurationError, match='unsupported log level'):
        setup_system_logger(paths, level='TRACE')

def test_setup_system_logger_rejects_invalid_format(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    with pytest.raises(ConfigurationError, match='unsupported log format'):
        setup_system_logger(paths, format_name='json')

def test_log_event_rejects_invalid_message(tmp_path: Path) -> None:
    paths = SystemPaths(tmp_path)
    logger = setup_system_logger(paths)
    with pytest.raises(ConfigurationError, match='message must be a non-empty string'):
        log_event(logger, level='INFO', module='core.test', message=' ')
