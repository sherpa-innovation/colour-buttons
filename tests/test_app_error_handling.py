"""Tests for error-handling branches in src/app.py that the acceptance tests don't exercise.

Kept separate from tests/test_app.py, which holds the approved acceptance tests and is not
to be changed.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest

import app as app_module
from app import app, write_colour


def invoke(method: str, path: str, environ_extra: dict[str, str] | None = None) -> tuple[str, dict, bytes]:
    """The app's answer to one request, with extra environ keys merged in."""
    said: dict = {}

    def start_response(status: str, headers: list[tuple[str, str]]) -> None:
        said["status"], said["headers"] = status, dict(headers)

    environ: dict = {"REQUEST_METHOD": method, "PATH_INFO": path, "wsgi.input": io.BytesIO(b"")}
    if environ_extra:
        environ.update(environ_extra)
    body = b"".join(app(environ, start_response))
    return said["status"], said["headers"], body


@pytest.fixture(autouse=True)
def data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point DATA_DIR at a fresh temp directory for every test."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    return tmp_path


def test_a_non_json_body_is_rejected_as_a_bad_request() -> None:
    """A body that isn't valid JSON is refused with 400, not a server error."""
    garbage = b"not json"
    status, headers, _ = invoke(
        "POST",
        "/api/colour",
        environ_extra={"CONTENT_LENGTH": str(len(garbage)), "wsgi.input": io.BytesIO(garbage)},
    )
    assert status == "400 Bad Request"
    assert headers.get("Content-Type", "").startswith("application/json")


def test_a_non_numeric_content_length_is_rejected_as_a_bad_request() -> None:
    """A Content-Length header that isn't a whole number is refused with 400, not a server error."""
    status, headers, _ = invoke(
        "POST",
        "/api/colour",
        environ_extra={"CONTENT_LENGTH": "not-a-number", "wsgi.input": io.BytesIO(b'{"colour": "red"}')},
    )
    assert status == "400 Bad Request"
    assert headers.get("Content-Type", "").startswith("application/json")


def test_write_colour_cleans_up_its_temp_file_and_reraises_on_failure(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """If the final rename fails, the temp file is removed and the error still propagates."""

    def failing_replace(_src: str, _dst: object) -> None:
        raise OSError("simulated failure")

    monkeypatch.setattr(app_module.os, "replace", failing_replace)
    with pytest.raises(OSError):
        write_colour("red")
    leftover = [entry for entry in tmp_path.iterdir() if entry.name.startswith(".colour.txt.")]
    assert leftover == []
