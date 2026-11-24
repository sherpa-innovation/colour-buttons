"""The application: a WSGI app serving its pages (gunicorn serves `app:app` in production)."""

from __future__ import annotations

import html
import os
from collections.abc import Callable, Iterable
from pathlib import Path

StartResponse = Callable[[str, list[tuple[str, str]]], object]


def data_dir() -> Path:
    """Where the app keeps its data: `DATA_DIR`, else `./data`."""
    return Path(os.environ.get("DATA_DIR", "data"))


def page(title: str, body: str) -> bytes:
    """A whole HTML page around `body` (already escaped)."""
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title>"
            f"</head><body>{body}</body></html>").encode()


def app(environ: dict, start_response: StartResponse) -> Iterable[bytes]:
    """Answer one request."""
    path = environ.get("PATH_INFO", "/")
    if path == "/health":
        start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"ok"]
    if path != "/":
        start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"not found"]
    start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
    return [page("Hello", "<h1>Hello</h1><p>Built with SHERPA.</p>")]


if __name__ == "__main__":
    from wsgiref.simple_server import make_server

    with make_server("", 8000, app) as server:
        server.serve_forever()
