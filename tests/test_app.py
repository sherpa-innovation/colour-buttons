from __future__ import annotations

import importlib
import io
import json
import re
from pathlib import Path

import pytest

import app as app_module
from app import app


def call(path: str) -> tuple[str, dict[str, str], str]:
    """The app's answer to a GET of `path`: status, headers, body."""
    said: dict = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        said["status"], said["headers"] = status, dict(headers)

    body = b"".join(app({"REQUEST_METHOD": "GET", "PATH_INFO": path}, start_response)).decode()
    return said["status"], said["headers"], body


def invoke(
    target: object,
    method: str,
    path: str,
    data: dict | None = None,
    environ_extra: dict[str, str] | None = None,
) -> tuple[str, dict, str]:
    """The answer a WSGI callable `target` gives to a request, with an optional JSON body."""
    said: dict = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        said["status"], said["headers"] = status, dict(headers)

    environ: dict = {"REQUEST_METHOD": method, "PATH_INFO": path, "wsgi.input": io.BytesIO(b"")}
    if data is not None:
        body_bytes = json.dumps(data).encode()
        environ["wsgi.input"] = io.BytesIO(body_bytes)
        environ["CONTENT_LENGTH"] = str(len(body_bytes))
        environ["CONTENT_TYPE"] = "application/json"
    if environ_extra:
        environ.update(environ_extra)
    body = b"".join(target(environ, start_response)).decode()
    return said["status"], said["headers"], body


def request(method: str, path: str, data: dict | None = None) -> tuple[str, dict, str]:
    """The current app's answer to a request with an optional JSON body."""
    return invoke(app, method, path, data)


def shows_background(body: str, colour: str) -> bool:
    """Whether the rendered HTML sets the page's background to `colour`."""
    normalized = re.sub(r"\s+", "", body.lower())
    return f"background:{colour}" in normalized or f"background-color:{colour}" in normalized


@pytest.fixture(autouse=True)
def data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


def test_the_home_page_answers() -> None:
    status, headers, body = call("/")
    assert status == "200 OK" and headers["Content-Type"].startswith("text/html") and "<h1>Hello</h1>" in body


def test_health_answers_ok() -> None:
    assert call("/health")[0] == "200 OK"


def test_an_unknown_path_is_not_found() -> None:
    assert call("/nope")[0] == "404 Not Found"


def test_default_colour_is_white_ac1() -> None:
    """Before anyone has ever clicked a button, the shared colour is white: API and page agree."""
    status, _, body = request("GET", "/api/colour")
    assert status == "200 OK"
    assert json.loads(body) == {"colour": "white"}
    _, _, page_body = call("/")
    assert shows_background(page_body, "white")


@pytest.mark.parametrize("colour", ["red", "green", "blue", "yellow"])
def test_clicking_a_button_changes_the_colour_immediately_ac2(colour: str) -> None:
    """Posting one of the four colours is accepted and is reflected immediately by the API."""
    status, _, body = request("POST", "/api/colour", {"colour": colour})
    assert status == "200 OK"
    assert json.loads(body)["colour"] == colour
    status, _, body = request("GET", "/api/colour")
    assert status == "200 OK"
    assert json.loads(body) == {"colour": colour}


def test_home_page_offers_the_four_buttons_wired_to_the_api_ac2() -> None:
    """The home page offers one button per colour, each wired to call POST /api/colour."""
    _, _, body = call("/")
    normalized = body.lower()
    assert "/api/colour" in normalized
    assert "post" in normalized
    labels = [
        match.group(1).strip().lower()
        for match in re.finditer(r"<button[^>]*>([^<]*)</button>", body, re.IGNORECASE)
    ]
    assert {"red", "green", "blue", "yellow"} <= set(labels)


def test_reloading_the_page_keeps_the_clicked_colour_ac3() -> None:
    """After setting a colour, reloading the page still shows that colour as the background."""
    request("POST", "/api/colour", {"colour": "blue"})
    status, _, body = call("/")
    assert status == "200 OK"
    assert shows_background(body, "blue")


def test_a_different_browser_sees_the_same_shared_colour_ac4() -> None:
    """A request from one client, and a later request from a different client, see the same colour."""
    status, first_headers, _ = invoke(
        app,
        "POST",
        "/api/colour",
        {"colour": "yellow"},
        environ_extra={"REMOTE_ADDR": "10.0.0.1", "HTTP_COOKIE": "session=browser-one"},
    )
    assert status == "200 OK"
    assert "Set-Cookie" not in first_headers
    status, second_headers, body = invoke(
        app,
        "GET",
        "/api/colour",
        environ_extra={"REMOTE_ADDR": "203.0.113.77", "HTTP_COOKIE": "session=browser-two"},
    )
    assert status == "200 OK"
    assert "Set-Cookie" not in second_headers
    assert json.loads(body) == {"colour": "yellow"}


def test_colour_survives_a_simulated_restart_ac5() -> None:
    """The colour set before a (simulated) process restart is still there, read from a fresh module."""
    request("POST", "/api/colour", {"colour": "green"})
    importlib.reload(app_module)
    status, _, body = invoke(app_module.app, "GET", "/api/colour")
    assert status == "200 OK"
    assert json.loads(body) == {"colour": "green"}


def test_an_invalid_colour_is_rejected_and_lists_the_allowed_ones_ac6() -> None:
    """Posting a colour outside the four is refused, names the allowed colours, and changes nothing."""
    request("POST", "/api/colour", {"colour": "blue"})
    status, headers, body = request("POST", "/api/colour", {"colour": "purple"})
    assert status.startswith("4")
    assert headers.get("Content-Type", "").startswith("application/json")
    text = body.lower()
    for allowed in ("red", "green", "blue", "yellow"):
        assert allowed in text
    _, _, body = request("GET", "/api/colour")
    assert json.loads(body) == {"colour": "blue"}


def test_a_missing_colour_field_is_rejected_and_leaves_colour_unchanged_ac6() -> None:
    """Posting without a colour field is refused the same way, and the shared colour is unchanged."""
    request("POST", "/api/colour", {"colour": "red"})
    status, headers, body = request("POST", "/api/colour", {})
    assert status.startswith("4")
    assert headers.get("Content-Type", "").startswith("application/json")
    text = body.lower()
    for allowed in ("red", "green", "blue", "yellow"):
        assert allowed in text
    _, _, body = request("GET", "/api/colour")
    assert json.loads(body) == {"colour": "red"}


def test_a_non_numeric_content_length_is_rejected_and_leaves_colour_unchanged_ac6() -> None:
    """A malformed Content-Length header is refused like any other bad request, not a server error."""
    request("POST", "/api/colour", {"colour": "red"})
    status, headers, _ = invoke(
        app, "POST", "/api/colour", environ_extra={"CONTENT_LENGTH": "not-a-number"}
    )
    assert status == "400 Bad Request"
    assert headers.get("Content-Type", "").startswith("application/json")
    _, _, body = request("GET", "/api/colour")
    assert json.loads(body) == {"colour": "red"}


def test_a_post_with_no_body_is_rejected_and_leaves_colour_unchanged_ac6() -> None:
    """A POST that carries no body at all (no Content-Length) is refused, not treated as valid."""
    request("POST", "/api/colour", {"colour": "red"})
    status, headers, _ = invoke(app, "POST", "/api/colour")
    assert status == "400 Bad Request"
    assert headers.get("Content-Type", "").startswith("application/json")
    _, _, body = request("GET", "/api/colour")
    assert json.loads(body) == {"colour": "red"}


def test_a_non_json_body_is_rejected_and_leaves_colour_unchanged_ac6() -> None:
    """A body that isn't valid JSON is refused the same way, and the shared colour is unchanged."""
    request("POST", "/api/colour", {"colour": "red"})
    garbage = b"not json"
    status, headers, _ = invoke(
        app,
        "POST",
        "/api/colour",
        environ_extra={"CONTENT_LENGTH": str(len(garbage)), "wsgi.input": io.BytesIO(garbage)},
    )
    assert status == "400 Bad Request"
    assert headers.get("Content-Type", "").startswith("application/json")
    _, _, body = request("GET", "/api/colour")
    assert json.loads(body) == {"colour": "red"}
