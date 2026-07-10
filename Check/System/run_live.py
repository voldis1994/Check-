from __future__ import annotations
import sys
from pathlib import Path
from engine.core.lifecycle import run_live_main
from engine.deployment.path_contract import prepare_deployment_root
CONFIG_RELATIVE_PATH = Path('config') / 'system.json'


def _resolve_project_root() -> Path:
    return Path(__file__).resolve().parent


def setup_only(project_root: Path | None = None) -> int:
    root = project_root or _resolve_project_root()
    config_path = root / CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        print(f'setup failed: config file not found at {config_path}', file=sys.stderr)
        return 1
    prepare_deployment_root(root)
    return 0


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == '--setup-only':
        return setup_only()
    wait_for_mt4_seconds = 30.0
    require_mt4_exports = True
    extra_args = sys.argv[1:]
    if '--no-wait-mt4' in extra_args:
        wait_for_mt4_seconds = 0.0
        extra_args = [arg for arg in extra_args if arg != '--no-wait-mt4']
    if '--allow-no-mt4' in extra_args:
        require_mt4_exports = False
        extra_args = [arg for arg in extra_args if arg != '--allow-no-mt4']
    if extra_args:
        print(f'unrecognized arguments: {" ".join(extra_args)}', file=sys.stderr)
        return 1
    project_root = _resolve_project_root()
    config_path = project_root / CONFIG_RELATIVE_PATH
    if not config_path.is_file():
        print(f'startup failed: config file not found at {config_path}', file=sys.stderr)
        return 1
    prepare_deployment_root(project_root)
    return run_live_main(root_path=project_root, config_path=config_path, require_mt4_exports=require_mt4_exports, wait_for_mt4_seconds=wait_for_mt4_seconds)


if __name__ == '__main__':
    sys.exit(main())
