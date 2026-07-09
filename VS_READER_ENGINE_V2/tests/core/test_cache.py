from __future__ import annotations

from engine.core.cache import (
    build_market_hash_path,
    content_hash,
    invalidate_startup_cache,
    should_reload,
    write_hash,
)
from engine.core.instance import Instance
from engine.core.paths import SystemPaths


def test_hash_changed_requires_reload(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    paths.ensure_instance_directories(instance.account_id, instance.symbol, instance.magic)
    source_path = paths.account_dir(instance.account_id) / instance.market_filename()
    source_path.write_text("v1", encoding="utf-8")
    hash_path = build_market_hash_path(paths, instance)
    write_hash(source_path, hash_path, "v1")

    source_path.write_text("v2", encoding="utf-8")
    assert should_reload(source_path, hash_path, "v2")


def test_hash_unchanged_skips_reload(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    paths.ensure_instance_directories(instance.account_id, instance.symbol, instance.magic)
    source_path = paths.account_dir(instance.account_id) / instance.market_filename()
    payload = "same-content"
    source_path.write_text(payload, encoding="utf-8")
    hash_path = build_market_hash_path(paths, instance)
    write_hash(source_path, hash_path, payload)

    assert not should_reload(source_path, hash_path, payload)
    assert content_hash(payload) == content_hash(payload)


def test_startup_cache_invalidation_removes_hash_files(tmp_path) -> None:
    paths = SystemPaths(root_path=tmp_path)
    instance = Instance(account_id="12345", symbol="EURUSD", magic=100001)
    paths.ensure_instance_directories(instance.account_id, instance.symbol, instance.magic)
    cache_dir = paths.instance_cache_dir(instance.account_id, instance.symbol, instance.magic)
    (cache_dir / "last_market.hash").write_text("{}", encoding="utf-8")
    (cache_dir / "last_sensor.hash").write_text("{}", encoding="utf-8")

    removed = invalidate_startup_cache(cache_dir)

    assert removed == 2
    assert not (cache_dir / "last_market.hash").exists()
    assert not (cache_dir / "last_sensor.hash").exists()
