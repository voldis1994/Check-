from __future__ import annotations
import json
import mimetypes
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse
from engine.dashboard.reader import DashboardSnapshot, snapshot_to_dict
MODULE_NAME = 'dashboard.web'
DEFAULT_PORT = 8765
STATIC_DIR = Path(__file__).resolve().parent / 'static'

# Fallback if static/index.html is missing (keeps old deployments usable).
DASHBOARD_HTML = '<!DOCTYPE html><html><body><h1>SYSTEM</h1><p>Missing static dashboard files.</p></body></html>'

SnapshotProvider = Callable[[], DashboardSnapshot]


def _read_static(name: str) -> bytes | None:
    path = STATIC_DIR / name
    if not path.is_file():
        return None
    return path.read_bytes()


def create_dashboard_handler(provider: SnapshotProvider) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: object) -> None:
            return

        def _send(self, code: int, body: bytes, content_type: str, *, cache: str='no-store') -> None:
            self.send_response(code)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', cache)
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            path = urlparse(self.path).path
            if path in {'/', '/index.html'}:
                body = _read_static('index.html')
                if body is None:
                    body = DASHBOARD_HTML.encode('utf-8')
                self._send(200, body, 'text/html; charset=utf-8')
                return
            if path == '/api/snapshot':
                payload = snapshot_to_dict(provider())
                body = json.dumps(payload, ensure_ascii=False).encode('utf-8')
                self._send(200, body, 'application/json; charset=utf-8')
                return
            static_name = {
                '/manifest.webmanifest': 'manifest.webmanifest',
                '/icon.svg': 'icon.svg',
                '/sw.js': 'sw.js',
            }.get(path)
            if static_name is not None:
                body = _read_static(static_name)
                if body is None:
                    self._send(404, b'not found', 'text/plain; charset=utf-8')
                    return
                content_type = mimetypes.guess_type(static_name)[0] or 'application/octet-stream'
                if static_name.endswith('.webmanifest'):
                    content_type = 'application/manifest+json'
                if static_name.endswith('.js'):
                    content_type = 'application/javascript; charset=utf-8'
                if static_name.endswith('.svg'):
                    content_type = 'image/svg+xml'
                cache = 'public, max-age=300' if static_name != 'sw.js' else 'no-store'
                self._send(200, body, content_type, cache=cache)
                return
            self._send(404, b'not found', 'text/plain; charset=utf-8')

    return DashboardHandler


def start_dashboard_server(*, provider: SnapshotProvider, host: str='127.0.0.1', port: int=DEFAULT_PORT) -> ThreadingHTTPServer:
    handler = create_dashboard_handler(provider)
    server = ThreadingHTTPServer((host, port), handler)
    thread = threading.Thread(target=server.serve_forever, name='system-dashboard-http', daemon=True)
    thread.start()
    return server
