"""The application: a WSGI app serving its pages (gunicorn serves `app:app` in production)."""

from __future__ import annotations

import html
import json
import os
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path

StartResponse = Callable[[str, list[tuple[str, str]]], object]

ALLOWED_COLOURS = ("red", "green", "blue", "yellow")
DEFAULT_COLOUR = "white"
COLOUR_FILE_NAME = "colour.txt"


def data_dir() -> Path:
    """Where the app keeps its data: `DATA_DIR`, else `./data`."""
    return Path(os.environ.get("DATA_DIR", "data"))


def colour_file() -> Path:
    """The file the current shared colour is stored in."""
    return data_dir() / COLOUR_FILE_NAME


def read_colour() -> str:
    """The current shared colour, or the default if none has ever been stored."""
    path = colour_file()
    try:
        return path.read_text(encoding="utf-8").strip() or DEFAULT_COLOUR
    except FileNotFoundError:
        return DEFAULT_COLOUR


def write_colour(colour: str) -> None:
    """Durably store `colour` as the new shared colour (atomic, same-filesystem rename).

    Each call writes to its own uniquely-named temp file (via `tempfile.mkstemp`, which picks a
    name atomically) and then `os.replace`s it onto the real file. `os.replace` is an atomic
    rename on the same filesystem, so concurrent writers never corrupt or interleave a read, and
    the last rename to complete is what subsequent readers see (last-write-wins). No lock or other
    in-process state is needed: the file is the only thing shared between calls.
    """
    directory = data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(dir=directory, prefix=f".{COLOUR_FILE_NAME}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as temp_file:
            temp_file.write(colour)
        os.replace(temp_name, directory / COLOUR_FILE_NAME)
    except OSError:
        os.unlink(temp_name)
        raise


def page(title: str, body: str, body_style: str = "") -> bytes:
    """A whole HTML page around `body` (already escaped), with `body_style` on the `<body>` tag."""
    style_attr = f' style="{body_style}"' if body_style else ""
    return (f"<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\"><title>{html.escape(title)}</title>"
            f"</head><body{style_attr}>{body}</body></html>").encode()


def home_page(colour: str) -> bytes:
    """The home page: a heading, the four colour buttons, and the current shared background."""
    style = f"background-color: {html.escape(colour)};"
    buttons = "".join(
        f'<button type="button" data-colour="{html.escape(name)}">{html.escape(name)}</button>'
        for name in ALLOWED_COLOURS
    )
    script = (
        "<script>"
        "document.querySelectorAll('button[data-colour]').forEach(function (button) {"
        "  button.addEventListener('click', function () {"
        "    fetch('/api/colour', {"
        "      method: 'POST',"
        "      headers: {'Content-Type': 'application/json'},"
        "      body: JSON.stringify({colour: button.dataset.colour})"
        "    }).then(function (response) {"
        "      if (response.ok) { document.body.style.backgroundColor = button.dataset.colour; }"
        "    });"
        "  });"
        "});"
        "</script>"
    )
    body = f"<h1>Hello</h1><p>Built with SHERPA.</p>{buttons}{script}"
    return page("Hello", body, body_style=style)


def json_response(start_response: StartResponse, status: str, payload: dict) -> Iterable[bytes]:
    """Answer with a JSON body and the given status."""
    body = json.dumps(payload).encode()
    start_response(status, [("Content-Type", "application/json; charset=utf-8")])
    return [body]


def read_json_body(environ: dict) -> dict | None:
    """The request's JSON body as a dict, or `None` if it is missing, malformed or not an object."""
    try:
        length = int(environ.get("CONTENT_LENGTH") or 0)
    except ValueError:
        return None
    raw = environ["wsgi.input"].read(length) if length > 0 else b"{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def handle_get_colour(start_response: StartResponse) -> Iterable[bytes]:
    """`GET /api/colour`: the current shared colour."""
    return json_response(start_response, "200 OK", {"colour": read_colour()})


def handle_post_colour(environ: dict, start_response: StartResponse) -> Iterable[bytes]:
    """`POST /api/colour`: set the shared colour if it is one of the allowed four."""
    data = read_json_body(environ)
    colour = data.get("colour") if data else None
    if colour not in ALLOWED_COLOURS:
        return json_response(
            start_response,
            "400 Bad Request",
            {"error": "invalid colour", "allowed": list(ALLOWED_COLOURS)},
        )
    write_colour(colour)
    return json_response(start_response, "200 OK", {"colour": colour})


def app(environ: dict, start_response: StartResponse) -> Iterable[bytes]:
    """Answer one request."""
    path = environ.get("PATH_INFO", "/")
    method = environ.get("REQUEST_METHOD", "GET")
    if path == "/health":
        start_response("200 OK", [("Content-Type", "text/plain; charset=utf-8")])
        return [b"ok"]
    if path == "/api/colour" and method == "GET":
        return handle_get_colour(start_response)
    if path == "/api/colour" and method == "POST":
        return handle_post_colour(environ, start_response)
    if path == "/" and method == "GET":
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [home_page(read_colour())]
    start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
    return [b"not found"]


if __name__ == "__main__":
    from wsgiref.simple_server import make_server

    with make_server("", 8000, app) as server:
        server.serve_forever()
