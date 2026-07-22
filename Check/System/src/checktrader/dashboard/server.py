"""Dashboard HTTP server — HTML UI + JSON snapshot."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from checktrader.dashboard.snapshot import build_dashboard_snapshot
from checktrader.state.store import load_instance_state

_TEMPLATE = Path(__file__).resolve().parent / "templates" / "index.html"


def serve_dashboard(*, host: str, port: int, state_path: Path) -> None:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            path = self.path.split("?", 1)[0]
            if path in {"/api/snapshot", "/snapshot.json", "/json"}:
                state = load_instance_state(state_path)
                body = json.dumps(build_dashboard_snapshot(state), indent=2).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if path in {"/", "/index.html"}:
                html = _TEMPLATE.read_bytes() if _TEMPLATE.exists() else b"<h1>CHECK SYSTEM</h1><p>template missing</p>"
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
                return
            self.send_response(404)
            self.end_headers()

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            return

    HTTPServer((host, port), Handler).serve_forever()
