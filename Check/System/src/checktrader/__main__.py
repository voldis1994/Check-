from __future__ import annotations
import argparse, os
from pathlib import Path
from checktrader.app.bootstrap import bootstrap
from checktrader.app.live_loop import run_loop, run_once
from checktrader.observability.logging import configure_logging

def build_parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog='checktrader',description='CHECK SYSTEM v3'); p.add_argument('--config',default=os.environ.get('CHECKTRADER_CONFIG','config/system.example.json')); p.add_argument('--once',action='store_true'); p.add_argument('--mode',choices=('paper','live'),default=None); return p
def main(argv: list[str]|None=None) -> int:
    args=build_parser().parse_args(argv); configure_logging(os.environ.get('CHECKTRADER_LOG_LEVEL','INFO')); context=bootstrap(Path(args.config),mode_override=args.mode)
    if args.once: print(run_once(context).to_dict()); return 0
    run_loop(context); return 0
if __name__=='__main__': raise SystemExit(main())
