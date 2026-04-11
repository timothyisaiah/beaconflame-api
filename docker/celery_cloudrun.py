"""Celery worker for environments (e.g. Cloud Run) that require a listener on PORT."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class _HealthHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):  # noqa: ARG002
        return

    def do_GET(self):  # noqa: N802
        self.send_response(200)
        self.end_headers()

    do_HEAD = do_GET


def _serve() -> None:
    port = int(os.environ.get("PORT", "8080"))
    server = HTTPServer(("0.0.0.0", port), _HealthHandler)
    server.serve_forever()


def main() -> None:
    threading.Thread(target=_serve, daemon=True).start()
    celery = subprocess.Popen(
        [sys.executable, "-m", "celery", "-A", "config", "worker", "-l", "info"],
    )

    def forward(_sig, _frame):
        celery.send_signal(signal.SIGTERM)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)
    rc = celery.wait()
    raise SystemExit(rc if rc is not None else 1)


if __name__ == "__main__":
    main()
