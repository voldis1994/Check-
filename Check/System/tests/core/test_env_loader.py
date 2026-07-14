from __future__ import annotations
from pathlib import Path
from engine.core.env_loader import load_dotenv_file

def test_load_dotenv_file_sets_missing_keys(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    env_file = tmp_path / '.env'
    env_file.write_text('OPENAI_API_KEY=sk-test-123\n# comment\nEMPTY=\n', encoding='utf-8')
    loaded = load_dotenv_file(env_file)
    assert loaded >= 1
    import os
    assert os.environ['OPENAI_API_KEY'] == 'sk-test-123'

def test_load_dotenv_file_does_not_override_existing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv('OPENAI_API_KEY', 'existing')
    env_file = tmp_path / '.env'
    env_file.write_text('OPENAI_API_KEY=from-file\n', encoding='utf-8')
    load_dotenv_file(env_file)
    import os
    assert os.environ['OPENAI_API_KEY'] == 'existing'
