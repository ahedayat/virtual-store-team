"""Lightweight in-process HTTP server for coordinator integration tests."""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


class _CoordinatorRequestHandler(BaseHTTPRequestHandler):
    server_version = "MockCoordinator/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        return

    def do_POST(self) -> None:
        server: MockCoordinatorHTTPServer = self.server  # type: ignore[assignment]
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        server.requests.append(
            {
                "method": "POST",
                "path": self.path,
                "headers": {key: value for key, value in self.headers.items()},
                "body": body.decode("utf-8") if body else "",
            }
        )

        if server.response_delay_seconds:
            time.sleep(server.response_delay_seconds)

        response_body = server.response_body
        self.send_response(server.response_status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response_body)))
        self.end_headers()
        self.wfile.write(response_body)


class MockCoordinatorHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, server_address: tuple[str, int]) -> None:
        super().__init__(server_address, _CoordinatorRequestHandler)
        self.requests: list[dict[str, Any]] = []
        self.response_status = 200
        self.response_body = b'{"status":"accepted"}'
        self.response_delay_seconds = 0.0


class MockCoordinatorServer:
    """Threaded mock coordinator HTTP server bound to an ephemeral localhost port."""

    def __init__(self, *, path: str = "/workflows/daily-report") -> None:
        self._path = path
        self._httpd: MockCoordinatorHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._port = 0

    @property
    def requests(self) -> list[dict[str, Any]]:
        if self._httpd is None:
            return []
        return self._httpd.requests

    @property
    def response_status(self) -> int:
        assert self._httpd is not None
        return self._httpd.response_status

    @response_status.setter
    def response_status(self, value: int) -> None:
        assert self._httpd is not None
        self._httpd.response_status = value

    @property
    def response_body(self) -> bytes:
        assert self._httpd is not None
        return self._httpd.response_body

    @response_body.setter
    def response_body(self, value: bytes) -> None:
        assert self._httpd is not None
        self._httpd.response_body = value

    @property
    def response_delay_seconds(self) -> float:
        assert self._httpd is not None
        return self._httpd.response_delay_seconds

    @response_delay_seconds.setter
    def response_delay_seconds(self, value: float) -> None:
        assert self._httpd is not None
        self._httpd.response_delay_seconds = value

    @property
    def base_url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    @property
    def daily_report_url(self) -> str:
        return f"{self.base_url}{self._path}"

    def start(self) -> None:
        if self._httpd is not None:
            return
        self._httpd = MockCoordinatorHTTPServer(("127.0.0.1", 0))
        self._port = self._httpd.server_address[1]
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._httpd is None:
            return
        self._httpd.shutdown()
        self._httpd.server_close()
        if self._thread is not None:
            self._thread.join(timeout=5)
        self._httpd = None
        self._thread = None

    def reset_requests(self) -> None:
        if self._httpd is not None:
            self._httpd.requests.clear()

    def set_json_response(self, payload: dict[str, Any], *, status: int = 200) -> None:
        self.response_status = status
        self.response_body = json.dumps(payload).encode("utf-8")

    def __enter__(self) -> MockCoordinatorServer:
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
